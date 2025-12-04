"""
Base classes for pipeline architecture.

Provides the Stage base class and AdProcessingPipeline orchestrator.
"""

from __future__ import annotations

import logging
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from .context import ProcessingContext
from .errors import (
    PipelineError,
    StageError,
    StageSkipped,
    TransientError,
    AdAlreadyExistsError,
)

logger = logging.getLogger("tvads_rag.pipeline")

T = TypeVar("T")


@dataclass
class PipelineConfig:
    """
    Configuration for the ad processing pipeline.
    
    Attributes:
        max_retries: Maximum retry attempts for transient failures
        retry_delay: Initial delay between retries (doubles each attempt)
        vision_enabled: Whether to run vision/storyboard analysis
        physics_enabled: Whether to run physics extraction
        hero_analysis_enabled: Whether to run hero analysis for qualifying ads
        parallel_workers: Number of parallel workers for batch processing
        cleanup_on_error: Whether to clean up temp files on error
    """
    max_retries: int = 3
    retry_delay: float = 2.0
    vision_enabled: bool = True
    physics_enabled: bool = True
    hero_analysis_enabled: bool = True
    parallel_workers: int = 3
    cleanup_on_error: bool = True
    
    # Stage-specific timeouts (seconds)
    transcription_timeout: float = 300.0
    analysis_timeout: float = 120.0
    vision_timeout: float = 180.0
    
    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create config from environment variables."""
        import os
        return cls(
            max_retries=int(os.getenv("INGEST_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("INGEST_RETRY_DELAY", "2.0")),
            vision_enabled=os.getenv("VISION_PROVIDER", "none").lower() != "none",
            physics_enabled=os.getenv("VIDEO_ANALYTICS_ENABLED", "true").lower() == "true",
            hero_analysis_enabled=os.getenv("HERO_ANALYSIS_ENABLED", "true").lower() == "true",
            parallel_workers=int(os.getenv("INGEST_PARALLEL_WORKERS", "3")),
        )


@dataclass
class ProcessingResult:
    """
    Result of processing an ad through the pipeline.
    
    Attributes:
        success: Whether processing completed successfully
        ad_id: Database UUID of the processed ad (if successful)
        external_id: External identifier of the ad
        elapsed_time: Total processing time in seconds
        completed_stages: List of stages that completed successfully
        skipped_stages: List of stages that were skipped
        failed_stages: List of stages that failed
        error: Error message if processing failed
        processing_notes: Notes about processing issues
    """
    success: bool
    ad_id: Optional[str]
    external_id: str
    elapsed_time: float
    completed_stages: List[str] = field(default_factory=list)
    skipped_stages: List[str] = field(default_factory=list)
    failed_stages: List[str] = field(default_factory=list)
    error: Optional[str] = None
    processing_notes: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_context(cls, ctx: ProcessingContext, error: Optional[str] = None) -> "ProcessingResult":
        """Create a result from a processing context."""
        return cls(
            success=error is None and not ctx.failed_stages,
            ad_id=ctx.ad_id,
            external_id=ctx.external_id,
            elapsed_time=ctx.elapsed_time(),
            completed_stages=list(ctx.completed_stages),
            skipped_stages=list(ctx.skipped_stages),
            failed_stages=list(ctx.failed_stages),
            error=error,
            processing_notes=dict(ctx.processing_notes),
        )
    
    @classmethod
    def skipped(cls, external_id: str, reason: str) -> "ProcessingResult":
        """Create a result for a skipped ad."""
        return cls(
            success=True,  # Skipping is not a failure
            ad_id=None,
            external_id=external_id,
            elapsed_time=0.0,
            skipped_stages=["all"],
            error=None,
            processing_notes={"skipped_reason": reason},
        )


class Stage(ABC):
    """
    Base class for pipeline stages.
    
    Each stage is responsible for a specific part of the processing pipeline.
    Stages can be optional, can have dependencies on other stages, and can
    be independently tested.
    
    Subclasses must implement:
    - name: Unique identifier for the stage
    - should_run(): Determine if stage should execute
    - execute(): Perform stage logic
    
    Optionally override:
    - on_error(): Handle stage-specific errors
    - validate_inputs(): Validate required inputs exist
    """
    
    name: str = "BaseStage"
    optional: bool = False
    
    @abstractmethod
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """
        Determine if this stage should execute.
        
        Args:
            ctx: Current processing context
            config: Pipeline configuration
        
        Returns:
            True if stage should run, False to skip
        """
        pass
    
    @abstractmethod
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Execute the stage logic.
        
        Args:
            ctx: Current processing context
            config: Pipeline configuration
        
        Returns:
            Updated processing context
        
        Raises:
            StageError: If stage execution fails
        """
        pass
    
    def on_error(
        self,
        ctx: ProcessingContext,
        error: Exception,
        config: PipelineConfig,
    ) -> None:
        """
        Handle stage-specific errors.
        
        Called when execute() raises an exception. Can be used to:
        - Add processing notes
        - Clean up partial state
        - Log additional context
        
        Args:
            ctx: Current processing context
            error: The exception that was raised
            config: Pipeline configuration
        """
        ctx.add_processing_note(
            f"{self.name}_error",
            {
                "type": type(error).__name__,
                "message": str(error)[:500],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """
        Validate that required inputs exist in the context.
        
        Override to check for stage-specific requirements.
        
        Raises:
            StageError: If required inputs are missing
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, optional={self.optional})"


class AdProcessingPipeline:
    """
    Orchestrates ad processing through configurable stages.
    
    The pipeline runs each stage in sequence, passing a ProcessingContext
    through all stages. Each stage reads its inputs from and writes its
    outputs to the context.
    
    Features:
    - Configurable stage list
    - Automatic retry for transient failures
    - Proper resource cleanup
    - Detailed logging and error tracking
    
    Usage:
        pipeline = AdProcessingPipeline(
            stages=[VideoLoadStage(), MediaProbeStage(), ...],
            config=PipelineConfig(),
        )
        result = pipeline.process(external_id="ad123", source="local", location="/path/to/video.mp4")
    """
    
    def __init__(
        self,
        stages: List[Stage],
        config: Optional[PipelineConfig] = None,
    ):
        """
        Initialize the pipeline.
        
        Args:
            stages: List of stages to execute in order
            config: Pipeline configuration (defaults to from_env())
        """
        self.stages = stages
        self.config = config or PipelineConfig.from_env()
        
        # Validate stage names are unique
        names = [s.name for s in stages]
        if len(names) != len(set(names)):
            raise ValueError("Stage names must be unique")
    
    def process(
        self,
        external_id: str,
        source: str,
        location: str,
        s3_key: Optional[str] = None,
        bucket: Optional[str] = None,
        metadata_entry: Optional[Any] = None,
        vision_tier: Optional[str] = None,
        hero_required: bool = False,
    ) -> ProcessingResult:
        """
        Process an ad through all pipeline stages.
        
        Args:
            external_id: Unique identifier for the ad
            source: Source type ("local" or "s3")
            location: Path or S3 key to the video
            s3_key: S3 object key (if source="s3")
            bucket: S3 bucket name (if source="s3")
            metadata_entry: Optional metadata from CSV
            vision_tier: Vision model tier to use
            hero_required: Whether this ad requires hero analysis
        
        Returns:
            ProcessingResult with success status and details
        """
        ctx = ProcessingContext(
            external_id=external_id,
            source=source,
            location=str(location),
            s3_key=s3_key,
            bucket=bucket,
            metadata_entry=metadata_entry,
            vision_tier=vision_tier,
            hero_required=hero_required,
        )
        
        error_message: Optional[str] = None
        
        try:
            for stage in self.stages:
                ctx = self._run_stage(stage, ctx)
                
        except AdAlreadyExistsError:
            # Not an error - just skip this ad
            logger.info("[%s] Skipped (already indexed)", external_id)
            return ProcessingResult.skipped(external_id, "already indexed")
            
        except StageSkipped as e:
            # Stage was intentionally skipped
            logger.debug("[%s] Stage skipped: %s", external_id, e.reason)
            
        except PipelineError as e:
            error_message = str(e)
            logger.error(
                "[%s] Pipeline failed at %s: %s",
                external_id, e.stage_name, error_message
            )
            
        except Exception as e:
            error_message = str(e)
            logger.exception("[%s] Unexpected error: %s", external_id, error_message[:200])
            
        finally:
            self._cleanup(ctx)
        
        result = ProcessingResult.from_context(ctx, error_message)
        
        if result.success:
            logger.info(
                "[%s] Processed successfully in %.1fs - stages=%d, ad_id=%s",
                external_id, result.elapsed_time, len(result.completed_stages), result.ad_id
            )
        
        return result
    
    def _run_stage(self, stage: Stage, ctx: ProcessingContext) -> ProcessingContext:
        """
        Run a single stage with retry logic.
        
        Args:
            stage: Stage to run
            ctx: Current processing context
        
        Returns:
            Updated processing context
        
        Raises:
            StageError: If stage fails after all retries
            StageSkipped: If stage should be skipped
        """
        # Check if stage should run
        if not stage.should_run(ctx, self.config):
            ctx.mark_stage_skipped(stage.name)
            logger.debug("[%s] Skipping stage: %s", ctx.external_id, stage.name)
            return ctx
        
        # Validate inputs
        try:
            stage.validate_inputs(ctx)
        except StageError as e:
            if stage.optional:
                ctx.mark_stage_skipped(stage.name)
                logger.debug("[%s] Skipping %s (missing inputs): %s", ctx.external_id, stage.name, e)
                return ctx
            raise
        
        # Execute with retry
        last_error: Optional[Exception] = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug("[%s] Running stage: %s", ctx.external_id, stage.name)
                ctx = stage.execute(ctx, self.config)
                ctx.mark_stage_complete(stage.name)
                return ctx
                
            except TransientError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(
                        "[%s] %s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        ctx.external_id, stage.name, attempt + 1, 
                        self.config.max_retries + 1, str(e)[:100], wait_time
                    )
                    time.sleep(wait_time)
                    
            except StageSkipped:
                ctx.mark_stage_skipped(stage.name)
                raise
            
            except AdAlreadyExistsError:
                # Re-raise to be handled at pipeline level (not an error)
                raise
                
            except StageError as e:
                last_error = e
                stage.on_error(ctx, e, self.config)
                ctx.mark_stage_failed(stage.name)
                
                if stage.optional:
                    logger.warning(
                        "[%s] Optional stage %s failed: %s",
                        ctx.external_id, stage.name, str(e)[:100]
                    )
                    return ctx
                raise
                
            except Exception as e:
                last_error = e
                stage.on_error(ctx, e, self.config)
                ctx.mark_stage_failed(stage.name)
                
                if stage.optional:
                    logger.warning(
                        "[%s] Optional stage %s failed: %s",
                        ctx.external_id, stage.name, str(e)[:100]
                    )
                    return ctx
                    
                raise StageError(
                    str(e), stage.name, cause=e, recoverable=False
                )
        
        # All retries exhausted
        ctx.mark_stage_failed(stage.name)
        stage.on_error(ctx, last_error, self.config)  # type: ignore
        
        if stage.optional:
            logger.warning(
                "[%s] Optional stage %s failed after %d retries: %s",
                ctx.external_id, stage.name, self.config.max_retries + 1, str(last_error)[:100]
            )
            return ctx
        
        raise StageError(
            f"Stage failed after {self.config.max_retries + 1} attempts: {last_error}",
            stage.name,
            cause=last_error,
            recoverable=False,
        )
    
    def _cleanup(self, ctx: ProcessingContext) -> None:
        """Clean up all temp resources."""
        for temp_dir in ctx.temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.debug("Cleaned up temp dir: %s", temp_dir)
            except Exception as e:
                logger.warning("Failed to clean up %s: %s", temp_dir, e)

