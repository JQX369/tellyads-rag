"""
Stage 1: Video Load

Loads video from local filesystem or S3 bucket.
Performs idempotency check to skip already-processed ads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import (
    AdAlreadyExistsError,
    VideoNotFoundError,
    StageError,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.video_load")


class VideoLoadStage(Stage):
    """
    Stage 1: Load video from local path or S3.
    
    Responsibilities:
    - Check if ad already exists (idempotency)
    - Load video from local filesystem or download from S3
    - Set ctx.video_path
    
    Raises:
        AdAlreadyExistsError: If ad has already been processed
        VideoNotFoundError: If video file cannot be found/accessed
    """
    
    name = "VideoLoadStage"
    optional = False
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Always run unless video already loaded."""
        return ctx.video_path is None
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Load video and perform idempotency check.
        
        For local source: Resolve path
        For S3 source: Download to temp file
        """
        from ... import db_backend, media
        
        # Idempotency check - skip if already processed
        if db_backend.ad_exists(external_id=ctx.external_id, s3_key=ctx.s3_key):
            raise AdAlreadyExistsError(ctx.external_id)
        
        # Load video based on source
        try:
            if ctx.source == "local":
                video_path = self._load_local(ctx.location)
            elif ctx.source == "s3":
                video_path = self._load_s3(ctx.location, ctx.bucket)
            else:
                raise StageError(
                    f"Unknown source type: {ctx.source}",
                    self.name,
                )
            
            ctx.video_path = video_path
            logger.debug("[%s] Loaded video: %s", ctx.external_id, video_path)
            
        except FileNotFoundError as e:
            raise VideoNotFoundError(ctx.location, self.name)
        except Exception as e:
            raise StageError(
                f"Failed to load video: {e}",
                self.name,
                cause=e,
            )
        
        return ctx
    
    def _load_local(self, location: str) -> Path:
        """Load video from local filesystem."""
        video_path = Path(location).resolve()
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        return video_path
    
    def _load_s3(self, location: str, bucket: str | None) -> Path:
        """Download video from S3 to temp file."""
        from ... import media
        
        if not bucket:
            raise StageError(
                "S3 bucket must be configured for S3 source",
                self.name,
            )
        
        # Download to temp file
        video_path = media.download_s3_object_to_tempfile(bucket, str(location))
        
        if not video_path or not video_path.exists():
            raise FileNotFoundError(f"Failed to download from S3: {location}")
        
        return video_path
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if not ctx.location:
            raise StageError("location is required", self.name)
        if not ctx.source:
            raise StageError("source is required", self.name)
        if ctx.source == "s3" and not ctx.bucket:
            raise StageError("bucket is required for S3 source", self.name)



