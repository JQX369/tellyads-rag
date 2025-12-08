"""
Stage 2: Media Probe

Probes video metadata with ffprobe and extracts audio for transcription.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, AudioExtractionError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.media_probe")


class MediaProbeStage(Stage):
    """
    Stage 2: Probe media and extract audio.
    
    Responsibilities:
    - Run ffprobe to get video metadata (duration, dimensions, fps)
    - Extract audio track to temp WAV file
    - Register temp directory for cleanup
    - Set ctx.probe_result, ctx.audio_path
    
    Raises:
        AudioExtractionError: If audio extraction fails
    """
    
    name = "MediaProbeStage"
    optional = False
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if video loaded but not yet probed."""
        return ctx.video_path is not None and ctx.probe_result is None
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Probe video and extract audio.
        """
        from ... import media
        
        video_path = ctx.video_path
        if not video_path:
            raise StageError("video_path is required", self.name)
        
        # Stage 2a: Probe media metadata
        logger.debug("[%s] Probing media...", ctx.external_id)
        try:
            probe_result = media.probe_media(str(video_path))
            ctx.probe_result = probe_result
            
            if not probe_result.get("duration_seconds"):
                logger.warning("[%s] Could not determine video duration", ctx.external_id)
                
        except Exception as e:
            logger.warning("[%s] Media probe failed: %s", ctx.external_id, str(e)[:100])
            # Continue with empty probe result - not fatal
            ctx.probe_result = {}
        
        # Stage 2b: Extract audio
        logger.debug("[%s] Extracting audio...", ctx.external_id)
        try:
            temp_audio_dir = Path(tempfile.mkdtemp(prefix="tvads_audio_"))
            ctx.register_temp_dir(temp_audio_dir)
            
            audio_path = media.extract_audio(str(video_path), out_dir=str(temp_audio_dir))
            
            if not audio_path or not audio_path.exists():
                raise AudioExtractionError(
                    f"Audio extraction returned no file",
                    self.name,
                )
            
            ctx.audio_path = audio_path
            logger.debug("[%s] Audio extracted: %s", ctx.external_id, audio_path)
            
        except AudioExtractionError:
            raise
        except Exception as e:
            raise AudioExtractionError(
                f"Audio extraction failed: {e}",
                self.name,
                cause=e,
            )
        
        return ctx
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if not ctx.video_path:
            raise StageError("video_path is required (run VideoLoadStage first)", self.name)
        if not ctx.video_path.exists():
            raise StageError(f"video_path does not exist: {ctx.video_path}", self.name)




