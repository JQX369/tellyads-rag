"""
CLI entry point for indexing TV ad videos into Supabase.

This module provides the command-line interface for the ad ingestion pipeline.
The actual processing is delegated to the pipeline module.
"""

from __future__ import annotations

import argparse
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import media, metadata_ingest
from .config import (
    describe_active_models,
    get_pipeline_config,
    get_storage_config,
)
from . import db_backend
from .pipeline import (
    AdProcessingPipeline,
    PipelineConfig,
    ProcessingResult,
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PARALLEL_WORKERS = int(os.getenv("INGEST_PARALLEL_WORKERS", "3"))
_progress_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("tvads_rag.index_ads")

# ---------------------------------------------------------------------------
# Pipeline Factory
# ---------------------------------------------------------------------------

def create_pipeline(config: Optional[PipelineConfig] = None) -> AdProcessingPipeline:
    """
    Create the ad processing pipeline with all stages.
    
    Args:
        config: Optional pipeline configuration. If None, loads from environment.
    
    Returns:
        Configured AdProcessingPipeline instance
    """
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


# Global pipeline instance (lazy initialization)
_pipeline: Optional[AdProcessingPipeline] = None


def get_pipeline() -> AdProcessingPipeline:
    """Get or create the global pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = create_pipeline()
    return _pipeline

# ---------------------------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Index TV ad videos into Supabase.")
    parser.add_argument("--source", choices=["local", "s3"], help="Video source (local or s3).")
    parser.add_argument("--limit", type=int, default=None, help="Number of ads to process.")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first N ads.")
    parser.add_argument("--single-path", help="Process a single local file (relative or absolute).")
    parser.add_argument("--single-key", help="Process a single S3 object key.")
    parser.add_argument(
        "--vision-tier",
        choices=["fast", "quality"],
        help="Override the default vision model tier (fast vs quality).",
    )
    parser.add_argument(
        "--metadata-csv",
        help="Optional CSV of legacy metadata (record_id, views, etc.) to enrich ads.",
    )
    parser.add_argument(
        "--retry-incomplete",
        action="store_true",
        help="Re-process ads with missing data (storyboard, v2 extraction, impact scores).",
    )
    parser.add_argument(
        "--retry-storyboard-only",
        action="store_true",
        help="Re-process only ads missing storyboard data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which ads would be re-processed without actually processing them.",
    )
    parser.add_argument(
        "--min-id",
        help="Minimum external_id to process (e.g., TA1665). Ads below this will be skipped.",
    )
    return parser.parse_args()

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def _external_id_from_path(path: Path) -> str:
    """Extract external_id from a local file path."""
    return path.stem


def _external_id_from_key(key: str) -> str:
    """Extract external_id from an S3 key."""
    return Path(key).stem


def _is_compilation_file(external_id: str) -> bool:
    """
    Check if the external_id represents a compilation file (e.g., TA10022-TA10034).
    
    Compilation files are created every ~10 ads and contain multiple ads merged together.
    These should be skipped during ingestion.
    """
    if "-" in external_id:
        parts = external_id.split("-")
        if len(parts) == 2:
            p1 = parts[0].replace("TA", "")
            p2 = parts[1].replace("TA", "")
            try:
                int(p1)
                int(p2)
                return True
            except ValueError:
                pass
    return False


def _process_local_files(
    paths: Sequence[Path],
) -> List[Tuple[str, Optional[str], Path]]:
    """Convert local file paths to worklist tuples."""
    return [(_external_id_from_path(path), None, path) for path in paths]


def _process_s3_keys(
    keys: Sequence[str], bucket: str, min_external_id: Optional[str] = None
) -> List[Tuple[str, Optional[str], str]]:
    """
    Process S3 keys into worklist tuples (external_id, s3_key, location).
    
    Args:
        keys: List of S3 keys
        bucket: S3 bucket name
        min_external_id: Optional minimum external_id to process
    """
    worklist = []
    skipped_compilations = 0
    skipped_below_min = 0
    
    for key in keys:
        external_id = _external_id_from_key(key)
        
        # Skip compilation files
        if _is_compilation_file(external_id):
            skipped_compilations += 1
            continue
        
        # Skip if below minimum
        if min_external_id:
            try:
                current_num = int(external_id.replace("TA", ""))
                min_num = int(min_external_id.replace("TA", ""))
                if current_num < min_num:
                    skipped_below_min += 1
                    continue
            except ValueError:
                pass  # Non-numeric ID, don't filter
        
        worklist.append((external_id, key, key))
    
    if skipped_compilations:
        logger.info("Skipped %d compilation files", skipped_compilations)
    if skipped_below_min:
        logger.info("Skipped %d ads below min_id %s", skipped_below_min, min_external_id)
    
    return worklist

# ---------------------------------------------------------------------------
# Main Processing Function (Backward Compatible)
# ---------------------------------------------------------------------------

def process_ad_record(
    *,
    source: str,
    external_id: str,
    s3_key: Optional[str],
    location: Path | str,
    bucket: Optional[str],
    vision_tier: Optional[str] = None,
    metadata_entry: Optional[metadata_ingest.AdMetadataEntry] = None,
    hero_required: bool = False,
) -> Optional[ProcessingResult]:
    """
    Process a single ad record through the full ingestion pipeline.
    
    This is the main entry point for processing a single ad. It delegates
    to the pipeline architecture while maintaining backward compatibility.
    
    Args:
        source: Video source ("local" or "s3")
        external_id: Unique identifier for the ad
        s3_key: S3 object key (if source="s3")
        location: Path or S3 key to the video
        bucket: S3 bucket name (if source="s3")
        vision_tier: Vision model tier ("fast" or "quality")
        metadata_entry: Optional metadata from CSV
        hero_required: Whether this ad requires hero analysis
    
    Returns:
        ProcessingResult with success status and details, or None if skipped
    """
    pipeline = get_pipeline()
    
    result = pipeline.process(
        external_id=external_id,
        source=source,
        location=str(location),
        s3_key=s3_key,
        bucket=bucket,
        metadata_entry=metadata_entry,
        vision_tier=vision_tier,
        hero_required=hero_required,
    )
    
    # Log result for backward compatibility
    if result.success:
        if "already indexed" in str(result.processing_notes.get("skipped_reason", "")):
            logger.info("Skipping %s (already indexed)", external_id)
            return None
    else:
        # Re-raise error for backward compatibility with existing error handling
        if result.error:
            raise RuntimeError(f"Pipeline failed: {result.error}")
    
    return result

# ---------------------------------------------------------------------------
# Retry Incomplete Ads
# ---------------------------------------------------------------------------

def _run_retry_incomplete(args, storage_cfg, metadata_index, vision_tier) -> None:
    """Re-process ads with incomplete data."""
    check_storyboard = True
    check_v2 = not args.retry_storyboard_only
    check_impact = not args.retry_storyboard_only
    
    logger.info(
        "Finding incomplete ads (storyboard=%s, v2=%s, impact=%s)...",
        check_storyboard, check_v2, check_impact
    )
    
    incomplete = db_backend.find_incomplete_ads(
        check_storyboard=check_storyboard,
        check_v2_extraction=check_v2,
        check_impact_scores=check_impact,
        limit=args.limit or 100,
    )
    
    if not incomplete:
        logger.info("No incomplete ads found!")
        return
    
    logger.info("Found %d incomplete ads:", len(incomplete))
    for ad in incomplete:
        logger.info("  %s: missing %s", ad["external_id"], ", ".join(ad["missing"]))
    
    if args.dry_run:
        logger.info("Dry run - no ads will be re-processed")
        return
    
    # Build worklist from incomplete ads that have S3 keys
    worklist = []
    for ad in incomplete:
        if ad.get("s3_key"):
            logger.info("Deleting old ad %s for re-processing...", ad["external_id"])
            db_backend.delete_ad(ad["id"])
            worklist.append((ad["external_id"], ad["s3_key"], ad["s3_key"]))
        else:
            logger.warning(
                "Skipping %s - no S3 key available for re-download",
                ad["external_id"]
            )
    
    if not worklist:
        logger.info("No ads with S3 keys to re-process")
        return
    
    logger.info("Re-processing %d ads...", len(worklist))
    
    success = 0
    failed = 0
    total = len(worklist)
    
    for ext_id, s3_key, _ in worklist:
        try:
            process_ad_record(
                source="s3",
                external_id=ext_id,
                s3_key=s3_key,
                location=s3_key,
                bucket=storage_cfg.s3_bucket,
                vision_tier=vision_tier,
                metadata_entry=metadata_index.get(ext_id) if metadata_index else None,
                hero_required=False,
            )
            success += 1
            logger.info("Progress: %d/%d completed (%d failed)", success + failed, total, failed)
        except Exception:
            logger.exception("Failed to re-process %s", ext_id)
            failed += 1
    
    logger.info("Completed retry: %s/%s succeeded", success, total)

# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Main CLI entry point."""
    args = _parse_args()
    storage_cfg = get_storage_config()
    pipeline_cfg = get_pipeline_config()
    
    # Load metadata if provided
    metadata_index: Optional[metadata_ingest.MetadataIndex] = None
    if args.metadata_csv:
        metadata_index = metadata_ingest.load_metadata(args.metadata_csv)
    
    # Log active configuration
    model_summary = describe_active_models()
    logger.info(
        "Active models • text=%s | embeddings=%s | vision=%s | rerank=%s",
        model_summary["text_llm"],
        model_summary["embeddings"],
        model_summary.get("vision_display", f"{model_summary['vision_provider']}({model_summary['vision_model']})"),
        model_summary["rerank_provider"],
    )
    
    backend_mode = os.getenv("DB_BACKEND", "postgres")
    logger.info("DB backend • mode=%s", backend_mode)
    
    source = args.source or pipeline_cfg.index_source_default
    vision_tier = args.vision_tier
    
    # Handle retry-incomplete mode
    if args.retry_incomplete or args.retry_storyboard_only:
        _run_retry_incomplete(args, storage_cfg, metadata_index, vision_tier)
        return
    
    # Build worklist
    if source == "local":
        paths = media.list_local_videos(
            storage_cfg.local_video_dir,
            limit=args.limit,
            offset=args.offset,
            single_path=args.single_path,
        )
        worklist = _process_local_files(paths)
    else:
        keys = media.list_s3_videos(
            storage_cfg.s3_bucket,
            storage_cfg.s3_prefix or "",
            limit=args.limit,
            offset=args.offset,
            single_key=args.single_key,
        )
        min_external_id = args.min_id or os.getenv("MIN_EXTERNAL_ID", None)
        if min_external_id:
            logger.info("Filtering: Only processing ads >= %s", min_external_id)
        worklist = _process_s3_keys(keys, storage_cfg.s3_bucket, min_external_id=min_external_id)
    
    logger.info(
        "Starting ingestion of %s ads from %s (parallel workers: %d)",
        len(worklist), source, PARALLEL_WORKERS
    )
    
    # Prepare job arguments for each ad
    def _get_job_args(external_id: str, s3_key: Optional[str], location):
        _metadata_entry = None
        _hero_required = False
        if metadata_index:
            _metadata_entry = metadata_index.get(external_id)
            if not _metadata_entry and isinstance(location, Path):
                _metadata_entry = metadata_index.get(location.stem)
            if not _metadata_entry and s3_key:
                _metadata_entry = metadata_index.get(Path(str(s3_key)).stem)
            if _metadata_entry and metadata_index.is_hero(_metadata_entry.external_id):
                _hero_required = True
        return {
            "source": source,
            "external_id": external_id,
            "s3_key": s3_key,
            "location": location,
            "bucket": storage_cfg.s3_bucket,
            "vision_tier": vision_tier,
            "metadata_entry": _metadata_entry,
            "hero_required": _hero_required,
        }
    
    success = 0
    failed = 0
    total = len(worklist)
    
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(process_ad_record, **_get_job_args(ext_id, s3_key, loc)): ext_id
            for ext_id, s3_key, loc in worklist
        }
        
        for future in as_completed(futures):
            ext_id = futures[future]
            try:
                future.result()
                with _progress_lock:
                    success += 1
                    logger.info(
                        "Progress: %d/%d completed (%d failed)",
                        success + failed, total, failed
                    )
            except Exception:
                logger.exception("Failed to process %s", ext_id)
                with _progress_lock:
                    failed += 1
    
    logger.info("Completed ingestion: %s/%s succeeded", success, total)


if __name__ == "__main__":
    main()
