"""
Pipeline module for ad processing.

Provides a composable, stage-based architecture for processing video advertisements.
Each stage is independently testable and configurable.
"""

from .base import Stage, AdProcessingPipeline, PipelineConfig, ProcessingResult
from .context import ProcessingContext
from .errors import (
    PipelineError,
    StageError,
    StageSkipped,
    TransientError,
    PermanentError,
)

__all__ = [
    # Core classes
    "Stage",
    "AdProcessingPipeline",
    "PipelineConfig",
    "ProcessingResult",
    "ProcessingContext",
    # Exceptions
    "PipelineError",
    "StageError",
    "StageSkipped",
    "TransientError",
    "PermanentError",
]




