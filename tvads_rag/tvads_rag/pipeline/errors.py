"""
Pipeline-specific exceptions.

Provides a clear hierarchy for different error types:
- PipelineError: Base exception for all pipeline errors
- StageError: Error during stage execution
- StageSkipped: Stage was intentionally skipped
- TransientError: Temporary error that may succeed on retry
- PermanentError: Unrecoverable error
"""

from __future__ import annotations

from typing import Optional


class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    
    def __init__(self, message: str, stage_name: Optional[str] = None):
        self.stage_name = stage_name
        super().__init__(message)


class StageError(PipelineError):
    """Error during stage execution."""
    
    def __init__(
        self,
        message: str,
        stage_name: str,
        cause: Optional[Exception] = None,
        recoverable: bool = False,
    ):
        self.cause = cause
        self.recoverable = recoverable
        super().__init__(message, stage_name)


class StageSkipped(PipelineError):
    """Stage was intentionally skipped (not an error)."""
    
    def __init__(self, stage_name: str, reason: str):
        self.reason = reason
        super().__init__(f"Stage skipped: {reason}", stage_name)


class TransientError(StageError):
    """
    Temporary error that may succeed on retry.
    
    Examples:
    - Network timeout
    - API rate limit
    - Temporary service unavailability
    """
    
    def __init__(
        self,
        message: str,
        stage_name: str,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, stage_name, cause, recoverable=True)


class PermanentError(StageError):
    """
    Unrecoverable error that should not be retried.
    
    Examples:
    - Invalid input data
    - Missing required resource
    - Configuration error
    """
    
    def __init__(
        self,
        message: str,
        stage_name: str,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, stage_name, cause, recoverable=False)


class AdAlreadyExistsError(PipelineError):
    """Ad has already been processed (idempotency check)."""
    
    def __init__(self, external_id: str):
        self.external_id = external_id
        super().__init__(f"Ad already exists: {external_id}")


class VideoNotFoundError(PermanentError):
    """Video file not found or inaccessible."""
    
    def __init__(self, path: str, stage_name: str = "VideoLoadStage"):
        self.path = path
        super().__init__(f"Video not found: {path}", stage_name)


class AudioExtractionError(StageError):
    """Failed to extract audio from video."""
    pass


class TranscriptionError(StageError):
    """Failed to transcribe audio."""
    pass


class AnalysisError(StageError):
    """Failed to analyze transcript with LLM."""
    pass


class DatabaseError(StageError):
    """Database operation failed."""
    pass


class VisionError(StageError):
    """Vision/storyboard analysis failed."""
    pass


class EmbeddingError(StageError):
    """Embedding generation or storage failed."""
    pass




