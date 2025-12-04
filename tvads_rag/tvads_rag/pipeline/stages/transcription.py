"""
Stage 3: Transcription

Transcribes audio using ASR (Automatic Speech Recognition).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, TranscriptionError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.transcription")


class TranscriptionStage(Stage):
    """
    Stage 3: Transcribe audio with ASR.
    
    Responsibilities:
    - Call ASR service (OpenAI Whisper) to transcribe audio
    - Handle transient API failures with retry
    - Set ctx.transcript
    
    Raises:
        TranscriptionError: If transcription fails
        TransientError: For retryable API errors
    """
    
    name = "TranscriptionStage"
    optional = False
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if audio extracted but not yet transcribed."""
        return ctx.audio_path is not None and ctx.transcript is None
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Transcribe audio using ASR service.
        """
        from ... import asr
        
        audio_path = ctx.audio_path
        if not audio_path:
            raise StageError("audio_path is required", self.name)
        
        logger.debug("[%s] Transcribing audio...", ctx.external_id)
        
        try:
            transcript = asr.transcribe_audio(str(audio_path))
            
            if not transcript:
                transcript = {"text": "", "segments": []}
                logger.warning(
                    "[%s] Transcription returned empty result - ad may have no spoken audio",
                    ctx.external_id
                )
            elif not transcript.get("text"):
                logger.warning(
                    "[%s] Transcript is empty - ad may have no spoken audio",
                    ctx.external_id
                )
            
            ctx.transcript = transcript
            
            # Log transcript stats
            text_length = len(transcript.get("text", ""))
            segment_count = len(transcript.get("segments", []))
            logger.debug(
                "[%s] Transcription complete: %d chars, %d segments",
                ctx.external_id, text_length, segment_count
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for transient errors
            transient_indicators = [
                "timeout", "rate limit", "429", "503", "502",
                "connection", "temporarily", "retry",
            ]
            is_transient = any(ind in error_str for ind in transient_indicators)
            
            if is_transient:
                raise TransientError(
                    f"Transcription API error: {e}",
                    self.name,
                    cause=e,
                )
            
            raise TranscriptionError(
                f"Transcription failed: {e}",
                self.name,
                cause=e,
            )
        
        return ctx
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if not ctx.audio_path:
            raise StageError("audio_path is required (run MediaProbeStage first)", self.name)
        if not ctx.audio_path.exists():
            raise StageError(f"audio_path does not exist: {ctx.audio_path}", self.name)



