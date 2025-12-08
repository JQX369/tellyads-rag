#!/usr/bin/env python
"""
Railway Worker for TellyAds RAG Ingestion Pipeline.

Long-running worker process that claims and processes jobs from the
DB-backed queue. Designed for Railway deployment.

Usage:
    python -m tvads_rag.worker [--once] [--limit N] [--poll-interval S]

Environment Variables Required:
    SUPABASE_DB_URL - PostgreSQL connection string
    OPENAI_API_KEY - For embeddings and LLM analysis
    GOOGLE_API_KEY - For vision analysis (optional)
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY - For S3 video access (optional)

Environment Variables Optional:
    WORKER_POLL_INTERVAL - Seconds between poll cycles (default: 5)
    WORKER_BATCH_SIZE - Jobs to claim per cycle (default: 1)
    WORKER_STALE_THRESHOLD - Minutes before releasing stale jobs (default: 30)
    WORKER_CONCURRENCY - Max concurrent jobs (default: 1)
    WORKER_MAX_RUNTIME_PER_JOB - Max seconds per job before timeout (default: 3600)
    WORKER_HEARTBEAT_INTERVAL - Seconds between heartbeats (default: 30)
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

import sentry_sdk
from sentry_sdk.integrations.threading import ThreadingIntegration

from .config import get_db_config, get_storage_config, describe_active_models
from .job_queue import (
    JobQueue,
    Job,
    JobInput,
    JobOutput,
    JobStatus,
)
from .pipeline import AdProcessingPipeline, PipelineConfig, ProcessingResult
from .pipeline.errors import (
    PipelineError,
    TransientError,
    PermanentError,
    AdAlreadyExistsError,
    VideoNotFoundError,
)
from .pipeline.stages import (
    VideoLoadStage,
    MediaProbeStage,
    TranscriptionStage,
    LLMAnalysisStage,
    HeroAnalysisStage,
    DatabaseInsertionStage,
    VisionStage,
    PhysicsStage,
    EmbeddingsStage,
)
from . import db_backend

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "1"))
STALE_THRESHOLD_MINUTES = int(os.getenv("WORKER_STALE_THRESHOLD", "30"))
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "1"))
MAX_RUNTIME_PER_JOB = int(os.getenv("WORKER_MAX_RUNTIME_PER_JOB", "3600"))  # 1 hour default
HEARTBEAT_INTERVAL = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "30"))

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("tvads_rag.worker")


# ---------------------------------------------------------------------------
# Worker State
# ---------------------------------------------------------------------------

@dataclass
class WorkerState:
    """Mutable state for the worker process."""
    running: bool = True
    jobs_processed: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    current_job_id: Optional[uuid.UUID] = None
    started_at: Optional[datetime] = None
    # Track jobs currently being processed (for concurrency)
    active_jobs: Set[uuid.UUID] = field(default_factory=set)
    active_jobs_lock: threading.Lock = field(default_factory=threading.Lock)


# Global state
_state = WorkerState()
_pipeline: Optional[AdProcessingPipeline] = None
_queue: Optional[JobQueue] = None
_heartbeat_stop_events: dict[uuid.UUID, threading.Event] = {}


# ---------------------------------------------------------------------------
# Signal Handlers
# ---------------------------------------------------------------------------

def _handle_sigterm(signum, frame):
    """Handle SIGTERM gracefully - finish current job if safe."""
    logger.warning("Received SIGTERM - initiating graceful shutdown...")
    _state.running = False

    if _state.current_job_id:
        logger.info(f"Finishing current job {_state.current_job_id} before exit...")
    else:
        logger.info("No job in progress, exiting immediately")
        sys.exit(0)


def _handle_sigint(signum, frame):
    """Handle SIGINT (Ctrl+C) - immediate shutdown."""
    logger.warning("Received SIGINT - shutting down...")
    _state.running = False

    if _state.current_job_id and _queue:
        # Mark job as retry if we're in the middle of processing
        logger.info(f"Marking job {_state.current_job_id} for retry...")
        try:
            _queue.fail(
                _state.current_job_id,
                "Worker interrupted by SIGINT",
                error_code="WORKER_INTERRUPTED",
                permanent=False,
            )
        except Exception as e:
            logger.error(f"Failed to mark job for retry: {e}")

    sys.exit(1)


# ---------------------------------------------------------------------------
# Pipeline Factory
# ---------------------------------------------------------------------------

def create_pipeline(config: Optional[PipelineConfig] = None) -> AdProcessingPipeline:
    """Create the ad processing pipeline with all stages."""
    stages = [
        VideoLoadStage(),
        MediaProbeStage(),
        TranscriptionStage(),
        LLMAnalysisStage(),
        HeroAnalysisStage(),
        DatabaseInsertionStage(),
        VisionStage(),
        PhysicsStage(),
        EmbeddingsStage(),
    ]
    return AdProcessingPipeline(stages=stages, config=config)


def get_pipeline() -> AdProcessingPipeline:
    """Get or create the global pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = create_pipeline()
    return _pipeline


def get_queue() -> JobQueue:
    """Get or create the global job queue instance."""
    global _queue
    if _queue is None:
        _queue = JobQueue()
    return _queue


# ---------------------------------------------------------------------------
# Heartbeat Thread
# ---------------------------------------------------------------------------

def _heartbeat_thread(job_id: uuid.UUID, queue: JobQueue, stop_event: threading.Event):
    """
    Background thread that sends heartbeats for a job.

    Runs until stop_event is set.
    """
    while not stop_event.wait(timeout=HEARTBEAT_INTERVAL):
        try:
            queue.heartbeat(job_id)
        except Exception as e:
            logger.warning(f"Heartbeat failed for job {job_id}: {e}")


def _start_heartbeat(job_id: uuid.UUID, queue: JobQueue) -> threading.Event:
    """Start a heartbeat thread for a job. Returns stop event."""
    stop_event = threading.Event()
    _heartbeat_stop_events[job_id] = stop_event

    thread = threading.Thread(
        target=_heartbeat_thread,
        args=(job_id, queue, stop_event),
        daemon=True,
        name=f"heartbeat-{str(job_id)[:8]}"
    )
    thread.start()
    return stop_event


def _stop_heartbeat(job_id: uuid.UUID):
    """Stop the heartbeat thread for a job."""
    stop_event = _heartbeat_stop_events.pop(job_id, None)
    if stop_event:
        stop_event.set()


# ---------------------------------------------------------------------------
# Job Processing
# ---------------------------------------------------------------------------

def process_job(job: Job, pipeline: AdProcessingPipeline, queue: JobQueue) -> bool:
    """
    Process a single job through the ingestion pipeline.

    Args:
        job: Job to process
        pipeline: Pipeline instance
        queue: Queue instance for status updates

    Returns:
        True if job succeeded, False otherwise
    """
    # Track active job
    with _state.active_jobs_lock:
        _state.active_jobs.add(job.id)
    _state.current_job_id = job.id
    start_time = time.time()

    logger.info(
        f"Processing job {job.id} (attempt {job.attempts}/{job.max_attempts}): "
        f"{job.input.source_type}:{job.input.s3_key or job.input.url or job.input.external_id}"
    )

    # Start heartbeat thread
    _start_heartbeat(job.id, queue)

    try:
        # Update stage: validating input
        queue.heartbeat(job.id, stage="validating_input", progress=0.05)
        # Build pipeline parameters from job input
        source = job.input.source_type
        s3_key = job.input.s3_key
        url = job.input.url
        external_id = job.input.external_id
        metadata = job.input.metadata or {}

        # Determine location based on source type
        if source == "s3" and s3_key:
            location = s3_key
            storage_cfg = get_storage_config()
            bucket = storage_cfg.s3_bucket
            if not external_id:
                external_id = Path(s3_key).stem
        elif source == "url" and url:
            location = url
            bucket = None
            if not external_id:
                # Generate external_id from URL hash
                import hashlib
                external_id = f"URL_{hashlib.sha256(url.encode()).hexdigest()[:12]}"
        elif source == "local" and external_id:
            # Local source - we need to find the file
            storage_cfg = get_storage_config()
            local_dir = Path(storage_cfg.local_video_dir)
            # Try common extensions
            for ext in [".mp4", ".mov", ".avi", ".mkv"]:
                candidate = local_dir / f"{external_id}{ext}"
                if candidate.exists():
                    location = str(candidate)
                    break
            else:
                raise VideoNotFoundError(
                    f"No video found for external_id={external_id} in {local_dir}",
                    "VideoLoadStage"
                )
            bucket = None
        else:
            raise PermanentError(
                f"Invalid job input: source={source}, s3_key={s3_key}, url={url}, external_id={external_id}",
                "worker"
            )

        # Check if ad already exists (idempotency)
        if db_backend.ad_exists(external_id=external_id, s3_key=s3_key):
            logger.info(f"Ad already exists: {external_id}")
            elapsed = time.time() - start_time
            output = JobOutput(
                already_existed=True,
                elapsed_seconds=elapsed,
            )
            # Get the ad_id if we can
            try:
                from .db import get_connection
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id FROM ads WHERE external_id = %s",
                            (external_id,)
                        )
                        row = cur.fetchone()
                        if row:
                            output.ad_id = str(row["id"])
            except Exception:
                pass

            queue.complete(job.id, output)
            _state.jobs_succeeded += 1
            return True

        # Update stage: running pipeline
        queue.heartbeat(job.id, stage="pipeline_running", progress=0.1)

        # Run the pipeline
        result = pipeline.process(
            external_id=external_id,
            source=source,
            location=location,
            s3_key=s3_key,
            bucket=bucket,
            metadata_entry=None,  # TODO: Support metadata from job input
            vision_tier=metadata.get("vision_tier"),
            hero_required=metadata.get("hero_required", False),
        )

        elapsed = time.time() - start_time

        if result.success:
            output = JobOutput(
                ad_id=str(result.ad_id) if result.ad_id else None,
                warnings=result.warnings or [],
                extraction_version=result.extraction_version,
                elapsed_seconds=elapsed,
                stage_reached="completed",
            )
            queue.complete(job.id, output, ad_id=result.ad_id)
            logger.info(f"Job {job.id} succeeded in {elapsed:.1f}s: ad_id={result.ad_id}")
            _state.jobs_succeeded += 1
            return True
        else:
            # Pipeline returned failure
            error_msg = result.error or "Pipeline failed with unknown error"
            error_code = result.error_code if hasattr(result, 'error_code') else None
            queue.fail(job.id, error_msg, error_code=error_code, permanent=True)
            logger.error(f"Job {job.id} failed: {error_msg}")
            _state.jobs_failed += 1
            return False

    except AdAlreadyExistsError as e:
        # Already processed - mark as success
        elapsed = time.time() - start_time
        output = JobOutput(
            already_existed=True,
            elapsed_seconds=elapsed,
        )
        queue.complete(job.id, output)
        logger.info(f"Job {job.id} skipped (already exists): {e}")
        _state.jobs_succeeded += 1
        return True

    except TransientError as e:
        # Temporary error - schedule retry
        error_code = e.stage_name if hasattr(e, 'stage_name') else "TRANSIENT"
        queue.fail(job.id, str(e), error_code=error_code, permanent=False)
        logger.warning(f"Job {job.id} transient error (will retry): {e}")
        _state.jobs_failed += 1
        return False

    except (PermanentError, VideoNotFoundError) as e:
        # Permanent error - no retry
        error_code = e.stage_name if hasattr(e, 'stage_name') else "PERMANENT"
        queue.fail(job.id, str(e), error_code=error_code, permanent=True)
        logger.error(f"Job {job.id} permanent error: {e}")
        sentry_sdk.capture_exception(e)
        _state.jobs_failed += 1
        return False

    except PipelineError as e:
        # Generic pipeline error - check if recoverable
        is_permanent = not getattr(e, 'recoverable', False)
        error_code = e.stage_name if hasattr(e, 'stage_name') else "PIPELINE"
        queue.fail(job.id, str(e), error_code=error_code, permanent=is_permanent)
        logger.error(f"Job {job.id} pipeline error: {e}")
        sentry_sdk.capture_exception(e)
        _state.jobs_failed += 1
        return False

    except Exception as e:
        # Unexpected error - treat as transient to allow retry
        logger.exception(f"Job {job.id} unexpected error: {e}")
        sentry_sdk.capture_exception(e)
        queue.fail(job.id, str(e), error_code="UNEXPECTED", permanent=False)
        _state.jobs_failed += 1
        return False

    finally:
        # Stop heartbeat thread
        _stop_heartbeat(job.id)
        # Remove from active jobs
        with _state.active_jobs_lock:
            _state.active_jobs.discard(job.id)
        _state.current_job_id = None
        _state.jobs_processed += 1


# ---------------------------------------------------------------------------
# Worker Loop
# ---------------------------------------------------------------------------

def run_worker(
    once: bool = False,
    batch_size: int = BATCH_SIZE,
    poll_interval: int = POLL_INTERVAL,
    concurrency: int = WORKER_CONCURRENCY,
) -> int:
    """
    Run the worker loop.

    Args:
        once: If True, process one batch and exit
        batch_size: Number of jobs to claim per cycle
        poll_interval: Seconds between poll cycles
        concurrency: Max concurrent jobs

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Initialize Sentry error tracking
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("SENTRY_RELEASE", "tvads-rag-worker@1.0.0"),
            integrations=[
                ThreadingIntegration(propagate_hub=True),
            ],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        )
        logger.info("Sentry error tracking initialized")
    else:
        logger.debug("SENTRY_DSN not set - error tracking disabled")

    # Set up signal handlers
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigint)

    _state.started_at = datetime.now()
    _state.running = True

    logger.info("=" * 60)
    logger.info("TellyAds RAG Worker Starting")
    logger.info("=" * 60)

    # Verify schema
    queue = get_queue()
    try:
        queue.verify_schema()
    except RuntimeError as e:
        logger.error(f"Schema verification failed: {e}")
        return 1

    # Verify configuration
    try:
        cfg = get_db_config()
        logger.info(f"Database: {cfg.url[:30]}...")
        logger.info(f"Worker ID: {queue.worker_id}")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Concurrency: {concurrency}")
        logger.info(f"Poll interval: {poll_interval}s")
        logger.info(f"Max runtime per job: {MAX_RUNTIME_PER_JOB}s")
        logger.info(f"Heartbeat interval: {HEARTBEAT_INTERVAL}s")
        logger.info(f"Stale threshold: {STALE_THRESHOLD_MINUTES}m")
        describe_active_models()

        # Set Sentry context for this worker
        sentry_sdk.set_user({"id": str(queue.worker_id)})
        sentry_sdk.set_tag("worker.batch_size", batch_size)
        sentry_sdk.set_tag("worker.concurrency", concurrency)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sentry_sdk.capture_exception(e)
        return 1

    # Create pipeline
    pipeline = get_pipeline()
    logger.info(f"Pipeline initialized with {len(pipeline.stages)} stages")

    # Release any stale jobs from crashed workers
    released = queue.release_stale_jobs(STALE_THRESHOLD_MINUTES)
    if released:
        logger.info(f"Released {released} stale jobs from crashed workers")

    logger.info("Worker ready - starting poll loop")
    logger.info("-" * 60)

    # Main loop with thread pool for concurrency
    idle_cycles = 0
    executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="job-worker")
    futures: dict[Future, Job] = {}

    try:
        while _state.running:
            try:
                # Release stale jobs every poll cycle
                released = queue.release_stale_jobs(STALE_THRESHOLD_MINUTES)
                if released:
                    logger.info(f"Released {released} stale jobs")

                # Check completed futures
                done_futures = [f for f in futures if f.done()]
                for future in done_futures:
                    job = futures.pop(future)
                    try:
                        future.result()  # Raise any exception
                    except FuturesTimeoutError:
                        logger.error(f"Job {job.id} timed out")
                        queue.fail(job.id, f"Job timed out after {MAX_RUNTIME_PER_JOB}s", error_code="TIMEOUT", permanent=False)
                    except Exception as e:
                        logger.exception(f"Job {job.id} failed in thread: {e}")

                # Calculate how many jobs we can claim
                active_count = len(futures)
                available_slots = concurrency - active_count

                if available_slots > 0:
                    # Claim jobs up to available slots
                    claim_count = min(batch_size, available_slots)
                    jobs = queue.claim_jobs(limit=claim_count)

                    if jobs:
                        idle_cycles = 0
                        for job in jobs:
                            if not _state.running:
                                break
                            # Submit job to thread pool
                            future = executor.submit(process_job, job, pipeline, queue)
                            futures[future] = job

                        if once and not futures:
                            break
                    else:
                        idle_cycles += 1
                        if idle_cycles == 1:
                            logger.debug("No jobs available, waiting...")

                        if once and not futures:
                            logger.info("No jobs to process")
                            break
                else:
                    # At capacity, just wait for completions
                    idle_cycles = 0

                # Sleep between poll cycles
                if not once or futures:
                    # Exponential backoff when idle (capped at poll_interval * 4)
                    if idle_cycles > 0:
                        sleep_time = min(poll_interval * (1 + idle_cycles * 0.5), poll_interval * 4)
                    else:
                        sleep_time = poll_interval
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.exception(f"Error in worker loop: {e}")
                sentry_sdk.capture_exception(e)
                time.sleep(poll_interval)

        # Wait for remaining jobs to complete (with timeout)
        if futures:
            logger.info(f"Waiting for {len(futures)} jobs to complete...")
            for future, job in list(futures.items()):
                try:
                    future.result(timeout=30)  # Give 30s grace period
                except FuturesTimeoutError:
                    logger.warning(f"Job {job.id} did not complete in grace period")
                except Exception as e:
                    logger.error(f"Job {job.id} failed during shutdown: {e}")

    finally:
        executor.shutdown(wait=False)

    # Shutdown
    logger.info("-" * 60)
    logger.info("Worker shutting down")
    logger.info(f"Jobs processed: {_state.jobs_processed}")
    logger.info(f"Jobs succeeded: {_state.jobs_succeeded}")
    logger.info(f"Jobs failed: {_state.jobs_failed}")
    logger.info("=" * 60)

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TellyAds RAG Ingestion Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one batch of jobs and exit",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=BATCH_SIZE,
        help=f"Number of jobs to claim per cycle (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=POLL_INTERVAL,
        help=f"Seconds between poll cycles (default: {POLL_INTERVAL})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=WORKER_CONCURRENCY,
        help=f"Max concurrent jobs (default: {WORKER_CONCURRENCY})",
    )
    parser.add_argument(
        "--release-stale",
        action="store_true",
        help="Release stale jobs and exit (maintenance mode)",
    )
    parser.add_argument(
        "--show-running",
        action="store_true",
        help="Show currently running jobs and exit",
    )

    args = parser.parse_args()

    if args.release_stale:
        queue = get_queue()
        try:
            queue.verify_schema()
        except RuntimeError as e:
            logger.error(f"Schema verification failed: {e}")
            sys.exit(1)

        released = queue.release_stale_jobs(STALE_THRESHOLD_MINUTES)
        logger.info(f"Released {released} stale jobs")
        sys.exit(0)

    if args.show_running:
        queue = get_queue()
        try:
            queue.verify_schema()
        except RuntimeError as e:
            logger.error(f"Schema verification failed: {e}")
            sys.exit(1)

        running = queue.get_running_jobs()
        if running:
            logger.info(f"Running jobs: {len(running)}")
            for job in running:
                logger.info(
                    f"  {job['id']}: stage={job['stage']} "
                    f"progress={job['progress']:.0%} "
                    f"running={job['running_seconds']}s "
                    f"heartbeat_age={job['heartbeat_age_seconds']}s"
                )
        else:
            logger.info("No jobs currently running")
        sys.exit(0)

    sys.exit(run_worker(
        once=args.once,
        batch_size=args.limit,
        poll_interval=args.poll_interval,
        concurrency=args.concurrency,
    ))


if __name__ == "__main__":
    main()
