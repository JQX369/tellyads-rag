"""
Stage 5: Hero Analysis (Optional)

Performs deep analysis for hero ads (top-performing ads based on views).
Uses premium vision model for enhanced creative analysis.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.hero_analysis")


class HeroAnalysisStage(Stage):
    """
    Stage 5: Deep analysis for hero ads (optional).
    
    Responsibilities:
    - Check if ad qualifies for hero analysis (top 10% by views)
    - Run enhanced deep analysis with premium vision model
    - Set ctx.hero_analysis
    
    This stage is optional - failures don't stop the pipeline.
    """
    
    name = "HeroAnalysisStage"
    optional = True  # Non-blocking - failures don't stop pipeline
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run only if hero analysis is enabled and ad qualifies."""
        if not config.hero_analysis_enabled:
            return False
        
        if ctx.hero_analysis is not None:
            return False  # Already analyzed
        
        # Check if ad qualifies for hero analysis
        return ctx.hero_required or self._qualifies_for_hero(ctx)
    
    def _qualifies_for_hero(self, ctx: ProcessingContext) -> bool:
        """
        Determine if ad qualifies for hero analysis.
        
        Criteria:
        - Has metadata with view count
        - View count exceeds threshold (top 10%)
        """
        if not ctx.metadata_entry:
            return False
        
        # Check if views field exists and exceeds threshold
        views = getattr(ctx.metadata_entry, "views", None)
        if views is None:
            return False
        
        # Hero threshold: 1M+ views (configurable)
        HERO_VIEWS_THRESHOLD = 1_000_000
        return views >= HERO_VIEWS_THRESHOLD
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Run deep hero analysis.
        """
        from ... import deep_analysis
        
        logger.debug("[%s] Running hero analysis...", ctx.external_id)
        
        # Prepare inputs for deep analysis
        transcript_text = ""
        if ctx.transcript:
            transcript_text = ctx.transcript.get("text", "")
        
        analysis_summary = ""
        if ctx.analysis_result:
            analysis_summary = ctx.analysis_result.get("one_line_summary", "")
        
        video_path = ctx.video_path
        if not video_path:
            logger.warning("[%s] No video path for hero analysis", ctx.external_id)
            return ctx
        
        try:
            hero_result = deep_analysis.analyse_hero_ad(
                video_path=str(video_path),
                transcript=transcript_text,
                analysis_summary=analysis_summary,
                tier="quality",  # Use premium model for hero ads
            )
            
            if hero_result:
                ctx.hero_analysis = hero_result
                logger.info(
                    "[%s] Hero analysis complete: score=%.1f",
                    ctx.external_id,
                    hero_result.get("overall_score", 0)
                )
            else:
                logger.warning("[%s] Hero analysis returned empty result", ctx.external_id)
                
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
                    f"Hero analysis API error: {e}",
                    self.name,
                    cause=e,
                )
            
            # For optional stage, log warning but don't fail
            logger.warning(
                "[%s] Hero analysis failed (non-blocking): %s",
                ctx.external_id, str(e)[:100]
            )
            ctx.add_processing_note(
                "hero_analysis_error",
                {"type": type(e).__name__, "message": str(e)[:500]}
            )
        
        return ctx
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if not ctx.video_path:
            raise StageError(
                "video_path is required (run VideoLoadStage first)",
                self.name
            )



