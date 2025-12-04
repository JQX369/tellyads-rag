"""
Stage 4: LLM Analysis

Analyzes transcript with LLM to extract structured creative metadata (v2.0 extraction).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, AnalysisError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.llm_analysis")


class LLMAnalysisStage(Stage):
    """
    Stage 4: LLM analysis of transcript.
    
    Responsibilities:
    - Call LLM (GPT) to analyze transcript
    - Extract 22 sections of structured creative metadata
    - Normalize and validate response
    - Set ctx.analysis_result
    
    Raises:
        AnalysisError: If LLM analysis fails
        TransientError: For retryable API errors
    """
    
    name = "LLMAnalysisStage"
    optional = False
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if transcript exists but not yet analyzed."""
        return ctx.transcript is not None and ctx.analysis_result is None
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Analyze transcript with LLM.
        """
        from ...analysis import analyse_ad_transcript
        
        transcript = ctx.transcript
        if transcript is None:
            raise StageError("transcript is required", self.name)
        
        logger.debug("[%s] Running LLM analysis...", ctx.external_id)

        try:
            analysis_result = analyse_ad_transcript(transcript, external_id=ctx.external_id)

            if not analysis_result:
                analysis_result = {}
                logger.warning(
                    "[%s] LLM analysis returned empty result",
                    ctx.external_id
                )

            ctx.analysis_result = analysis_result

            # Log analysis summary including warning count
            brand = analysis_result.get("brand_name", "Unknown")
            format_type = analysis_result.get("format_type", "unknown")
            warnings_count = len(analysis_result.get("extraction_warnings", []))
            logger.debug(
                "[%s] LLM analysis complete: brand=%s, format=%s, warnings=%d",
                ctx.external_id, brand, format_type, warnings_count
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for transient errors
            transient_indicators = [
                "timeout", "rate limit", "429", "503", "502",
                "connection", "temporarily", "retry", "overloaded",
            ]
            is_transient = any(ind in error_str for ind in transient_indicators)
            
            if is_transient:
                raise TransientError(
                    f"LLM API error: {e}",
                    self.name,
                    cause=e,
                )
            
            raise AnalysisError(
                f"LLM analysis failed: {e}",
                self.name,
                cause=e,
            )
        
        return ctx
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if ctx.transcript is None:
            raise StageError(
                "transcript is required (run TranscriptionStage first)",
                self.name
            )



