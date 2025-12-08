"""
DB-backed job queue for TellyAds RAG ingestion.

Provides atomic job claiming with SKIP LOCKED for concurrent workers.
Uses PostgreSQL functions defined in migrations/003_ingestion_jobs.sql.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterator, Optional, Sequence

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .config import get_db_config

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job state machine states."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRY = "RETRY"


@dataclass
class JobInput:
    """Job input payload."""
    source_type: str  # "s3", "url", "local"
    s3_key: Optional[str] = None
    url: Optional[str] = None
    external_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = {"source_type": self.source_type}
        if self.s3_key:
            d["s3_key"] = self.s3_key
        if self.url:
            d["url"] = self.url
        if self.external_id:
            d["external_id"] = self.external_id
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    def compute_idempotency_key(self) -> str:
        """Compute stable hash for deduplication."""
        if self.s3_key:
            canonical = f"s3:{self.s3_key}"
        elif self.url:
            canonical = f"url:{self.url}"
        elif self.external_id:
            canonical = f"id:{self.external_id}"
        else:
            raise ValueError("JobInput must have s3_key, url, or external_id")
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]


@dataclass
class JobOutput:
    """Job output payload."""
    ad_id: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    extraction_version: Optional[str] = None
    already_existed: bool = False
    elapsed_seconds: Optional[float] = None
    stage_reached: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "ad_id": self.ad_id,
            "warnings": self.warnings,
            "extraction_version": self.extraction_version,
            "already_existed": self.already_existed,
            "elapsed_seconds": self.elapsed_seconds,
            "stage_reached": self.stage_reached,
        }


@dataclass
class Job:
    """Represents a claimed job ready for processing."""
    id: uuid.UUID
    input: JobInput
    attempts: int
    max_attempts: int
    created_at: datetime
    raw_input: dict[str, Any]  # Original JSON for passthrough

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Job":
        """Create Job from database row."""
        raw_input = row["job_input"]
        return cls(
            id=row["job_id"],
            input=JobInput(
                source_type=raw_input.get("source_type", "s3"),
                s3_key=raw_input.get("s3_key"),
                url=raw_input.get("url"),
                external_id=raw_input.get("external_id"),
                metadata=raw_input.get("metadata"),
            ),
            attempts=row["job_attempts"],
            max_attempts=row["job_max_attempts"],
            created_at=row["job_created_at"],
            raw_input=raw_input,
        )


@dataclass
class EnqueueResult:
    """Result of enqueue operation."""
    job_id: uuid.UUID
    status: str
    already_existed: bool


def _generate_worker_id() -> str:
    """Generate unique worker instance ID."""
    hostname = socket.gethostname()[:20]
    pid = os.getpid()
    rand = uuid.uuid4().hex[:8]
    return f"{hostname}-{pid}-{rand}"


@contextmanager
def get_connection():
    """Yield a psycopg2 connection for job queue operations."""
    cfg = get_db_config()
    conn = psycopg2.connect(cfg.url, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class JobQueue:
    """
    DB-backed job queue with atomic claiming.

    Usage:
        queue = JobQueue()

        # Enqueue a job
        result = queue.enqueue(JobInput(source_type="s3", s3_key="videos/foo.mp4"))

        # Claim and process jobs
        for job in queue.claim_jobs(limit=5):
            try:
                ad_id = process_ad(job.input)
                queue.complete(job.id, JobOutput(ad_id=ad_id))
            except TransientError as e:
                queue.fail(job.id, str(e), permanent=False)
            except PermanentError as e:
                queue.fail(job.id, str(e), permanent=True)
    """

    def __init__(self, worker_id: Optional[str] = None):
        """Initialize job queue with optional worker ID."""
        self.worker_id = worker_id or _generate_worker_id()
        logger.info(f"JobQueue initialized with worker_id={self.worker_id}")

    def verify_schema(self) -> bool:
        """
        Verify that the ingestion_jobs table exists with required columns.
        Returns True if schema is valid, raises exception otherwise.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'ingestion_jobs'
                """)
                columns = {row["column_name"] for row in cur.fetchall()}

        required = {
            "id", "status", "priority", "attempts", "max_attempts",
            "locked_at", "locked_by", "run_after", "last_error",
            "input", "output", "idempotency_key"
        }
        missing = required - columns

        if missing:
            raise RuntimeError(
                f"ingestion_jobs table missing required columns: {missing}. "
                "Run migration: psql $SUPABASE_DB_URL -f tvads_rag/migrations/003_ingestion_jobs.sql"
            )

        logger.info("Job queue schema verified")
        return True

    def enqueue(
        self,
        job_input: JobInput,
        priority: int = 0,
        max_attempts: int = 5,
    ) -> EnqueueResult:
        """
        Enqueue a new job (idempotent - returns existing job if duplicate).

        Args:
            job_input: Job input payload
            priority: Higher = more urgent (default 0)
            max_attempts: Max retry attempts before permanent failure

        Returns:
            EnqueueResult with job_id, status, and whether it already existed
        """
        idempotency_key = job_input.compute_idempotency_key()

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM enqueue_job(%s::jsonb, %s, %s, %s)",
                    (Json(job_input.to_dict()), idempotency_key, priority, max_attempts)
                )
                row = cur.fetchone()

        result = EnqueueResult(
            job_id=row["job_id"],
            status=row["status"],
            already_existed=row["already_existed"],
        )

        if result.already_existed:
            logger.info(f"Job already exists: {result.job_id} (status={result.status})")
        else:
            logger.info(f"Job enqueued: {result.job_id}")

        return result

    def claim_jobs(self, limit: int = 1) -> list[Job]:
        """
        Atomically claim jobs for processing.

        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming.

        Args:
            limit: Maximum number of jobs to claim

        Returns:
            List of claimed Job objects
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM claim_jobs(%s, %s)",
                    (limit, self.worker_id)
                )
                rows = cur.fetchall()

        jobs = [Job.from_row(row) for row in rows]
        if jobs:
            logger.info(f"Claimed {len(jobs)} jobs: {[str(j.id)[:8] for j in jobs]}")
        return jobs

    def complete(
        self,
        job_id: uuid.UUID,
        output: Optional[JobOutput] = None,
        ad_id: Optional[uuid.UUID] = None,
    ) -> None:
        """
        Mark job as successfully completed.

        Args:
            job_id: Job UUID
            output: Job output payload
            ad_id: Optional UUID of created ad
        """
        output_dict = output.to_dict() if output else {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT complete_job(%s, %s::jsonb, %s)",
                    (job_id, Json(output_dict), ad_id)
                )

        logger.info(f"Job completed: {job_id}")

    def fail(
        self,
        job_id: uuid.UUID,
        error: str,
        error_code: Optional[str] = None,
        permanent: bool = False,
    ) -> None:
        """
        Mark job as failed or schedule for retry.

        Args:
            job_id: Job UUID
            error: Error message
            error_code: Optional structured error code
            permanent: If True, don't retry
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fail_job(%s, %s, %s, %s)",
                    (job_id, error[:2000], error_code, permanent)  # Truncate long errors
                )

        action = "permanently failed" if permanent else "scheduled for retry"
        logger.warning(f"Job {action}: {job_id} - {error[:100]}")

    def cancel(self, job_id: uuid.UUID) -> bool:
        """
        Cancel a queued job.

        Args:
            job_id: Job UUID

        Returns:
            True if job was cancelled, False if not in cancellable state
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT cancel_job(%s)", (job_id,))
                result = cur.fetchone()

        cancelled = result["cancel_job"] if result else False
        if cancelled:
            logger.info(f"Job cancelled: {job_id}")
        else:
            logger.warning(f"Job not cancellable: {job_id}")
        return cancelled

    def release_stale_jobs(self, stale_threshold_minutes: int = 30) -> int:
        """
        Release jobs stuck in RUNNING state (crashed workers).

        Args:
            stale_threshold_minutes: Jobs running longer than this are released

        Returns:
            Number of jobs released
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT release_stale_jobs(%s)",
                    (stale_threshold_minutes,)
                )
                result = cur.fetchone()

        released = result["release_stale_jobs"] if result else 0
        if released:
            logger.warning(f"Released {released} stale jobs")
        return released

    def get_job(self, job_id: uuid.UUID) -> Optional[dict[str, Any]]:
        """Get full job details by ID."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ingestion_jobs WHERE id = %s",
                    (job_id,)
                )
                return cur.fetchone()

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List jobs with optional status filter.

        Args:
            status: Filter by status (QUEUED, RUNNING, etc.)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of job dicts
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id, created_at, updated_at, status, priority,
                               attempts, max_attempts, last_error, error_code,
                               input, output, ad_id
                        FROM ingestion_jobs
                        WHERE status = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (status.upper(), limit, offset)
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, created_at, updated_at, status, priority,
                               attempts, max_attempts, last_error, error_code,
                               input, output, ad_id
                        FROM ingestion_jobs
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset)
                    )
                return cur.fetchall()

    def get_stats(self) -> dict[str, Any]:
        """Get job queue statistics."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM job_queue_stats")
                rows = cur.fetchall()

        stats = {
            "by_status": {row["status"]: row["count"] for row in rows},
            "total": sum(row["count"] for row in rows),
        }
        return stats

    def get_dead_letter_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get failed jobs that exceeded max attempts."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM dead_letter_jobs LIMIT %s",
                    (limit,)
                )
                return cur.fetchall()

    def heartbeat(
        self,
        job_id: uuid.UUID,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> None:
        """
        Update job heartbeat to indicate worker is still alive.

        Should be called periodically during processing to prevent
        the job from being reclaimed as stale.

        Args:
            job_id: Job UUID
            stage: Current pipeline stage name (e.g., "transcription", "llm_analysis")
            progress: Progress from 0.0 to 1.0
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT update_job_heartbeat(%s, %s, %s)",
                    (job_id, stage, progress)
                )

        if stage:
            logger.debug(f"Heartbeat: job={str(job_id)[:8]} stage={stage} progress={progress}")

    def get_running_jobs(self) -> list[dict[str, Any]]:
        """
        Get currently running jobs with timing info.

        Returns jobs from running_jobs_monitor view.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM running_jobs_monitor")
                return cur.fetchall()

    def get_timing_stats(self) -> list[dict[str, Any]]:
        """
        Get job duration statistics by status.

        Returns stats from job_timing_stats view.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM job_timing_stats")
                return cur.fetchall()


# Convenience functions for simple usage

_default_queue: Optional[JobQueue] = None


def get_queue() -> JobQueue:
    """Get or create default JobQueue instance."""
    global _default_queue
    if _default_queue is None:
        _default_queue = JobQueue()
    return _default_queue


def enqueue_job(
    source_type: str,
    s3_key: Optional[str] = None,
    url: Optional[str] = None,
    external_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    priority: int = 0,
) -> EnqueueResult:
    """
    Convenience function to enqueue a job.

    Args:
        source_type: "s3", "url", or "local"
        s3_key: S3 key if source_type="s3"
        url: URL if source_type="url"
        external_id: Optional external ID
        metadata: Optional metadata dict
        priority: Higher = more urgent

    Returns:
        EnqueueResult with job_id and status
    """
    job_input = JobInput(
        source_type=source_type,
        s3_key=s3_key,
        url=url,
        external_id=external_id,
        metadata=metadata,
    )
    return get_queue().enqueue(job_input, priority=priority)
