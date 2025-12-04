"""
Stage 9: Toxicity Scoring

Analyzes ad content for potential toxicity using the ToxicityScorer.
Evaluates physiological harm, psychological manipulation, and regulatory risks.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.toxicity")


class ToxicityStage(Stage):
    """
    Stage 9: Toxicity scoring (optional).
    
    Responsibilities:
    - Analyze ad content for toxicity indicators
    - Detect dark patterns in transcript (regex + AI)
    - Score physiological harm (cuts/min, loudness, strobe effects)
    - Score psychological manipulation (claims, fear appeals, shaming)
    - Score regulatory risk (GARM levels, missing disclaimers)
    - Generate "Nutrition Label" style toxicity report
    - Store result via db_backend.update_toxicity_report()
    
    This stage is optional - failures don't stop the pipeline.
    Requires: analysis_result (from LLMAnalysisStage), physics_result (from PhysicsStage)
    """
    
    name = "ToxicityStage"
    optional = True  # Non-blocking - failures don't stop pipeline
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if ad_id exists and we have analysis data."""
        if ctx.ad_id is None:
            return False
        if ctx.analysis_result is None:
            return False
        return ctx.toxicity_report is None  # Haven't run yet
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Run toxicity scoring on the ad.
        """
        from ...scoring_engine import ToxicityScorer, score_ad_toxicity
        from ...config import get_toxicity_config, is_toxicity_ai_enabled
        from ...extraction_warnings import WarningCode, add_warning
        from ... import db_backend

        toxicity_cfg = get_toxicity_config()

        if not toxicity_cfg.enabled:
            logger.debug("[%s] Toxicity scoring disabled", ctx.external_id)
            return ctx

        # Check for missing prerequisites and emit warnings
        missing_prereqs = []
        if not ctx.physics_result:
            missing_prereqs.append("physics_result")
        if not ctx.transcript or not ctx.transcript.get("text"):
            missing_prereqs.append("transcript")

        if missing_prereqs:
            # Add warning to analysis_result if it exists
            if ctx.analysis_result:
                add_warning(
                    ctx.analysis_result,
                    WarningCode.TOXICITY_INPUT_MISSING,
                    f"Toxicity scoring running with missing inputs: {', '.join(missing_prereqs)}. "
                    "Physiological scores may be incomplete.",
                    {"missing": missing_prereqs, "stage": self.name},
                    log_level="warning"
                )
            # Still continue - toxicity can run with partial data

        logger.debug("[%s] Running toxicity analysis...", ctx.external_id)

        try:
            # Build analysis_data dict for the scorer
            analysis_data = self._build_analysis_data(ctx)
            
            # Run toxicity scoring
            use_ai = is_toxicity_ai_enabled(toxicity_cfg)
            scorer = ToxicityScorer(analysis_data, use_ai=use_ai)
            toxicity_report = scorer.calculate_toxicity()
            
            ctx.toxicity_report = toxicity_report
            
            # Store in database
            if ctx.ad_id:
                db_backend.update_toxicity_report(ctx.ad_id, toxicity_report)
            
            # Log summary
            score = toxicity_report.get("toxic_score", 0)
            risk = toxicity_report.get("risk_level", "UNKNOWN")
            dark_patterns = toxicity_report.get("dark_patterns_detected", [])
            
            logger.info(
                "[%s] Toxicity: score=%d/100, risk=%s, dark_patterns=%d",
                ctx.external_id, score, risk, len(dark_patterns)
            )
            
            # Warn for high-risk ads
            if risk in ("HIGH", "CRITICAL"):
                logger.warning(
                    "[%s] HIGH TOXICITY DETECTED: score=%d, risk=%s",
                    ctx.external_id, score, risk
                )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for transient errors (API rate limits, etc.)
            transient_indicators = [
                "timeout", "rate limit", "429", "503", "502",
                "connection", "temporarily",
            ]
            is_transient = any(ind in error_str for ind in transient_indicators)
            
            if is_transient:
                raise TransientError(
                    f"Toxicity scoring error: {e}",
                    self.name,
                    cause=e,
                )
            
            logger.warning(
                "[%s] Toxicity scoring failed: %s",
                ctx.external_id, str(e)[:100]
            )
            ctx.add_processing_note("toxicity_error", {
                "type": "error",
                "reason": str(e)[:500],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        
        return ctx
    
    def _build_analysis_data(self, ctx: ProcessingContext) -> Dict[str, Any]:
        """
        Build the analysis_data dict expected by ToxicityScorer.
        
        Combines data from multiple sources:
        - analysis_result (LLM extraction)
        - physics_result (PhysicsExtractor)
        - transcript
        - storyboard data
        """
        analysis_data: Dict[str, Any] = {}
        
        # From analysis_result (LLM extraction v2.0)
        if ctx.analysis_result:
            ar = ctx.analysis_result
            
            # Claims for psychological scoring
            analysis_data["claims"] = ar.get("claims", [])
            
            # GARM risk level
            compliance = ar.get("compliance_assessment", {})
            analysis_data["garm_risk_level"] = compliance.get("overall_risk", "low")
            
            # Required disclaimers
            analysis_data["required_disclaimers"] = compliance.get("required_disclaimers", [])
            analysis_data["actual_disclaimers"] = []  # From supers
            
            # Check supers for disclaimers
            for sup in ar.get("supers", []):
                if isinstance(sup, dict) and sup.get("super_type") == "disclaimer":
                    analysis_data["actual_disclaimers"].append(sup.get("text", ""))
            
            # Creative flags
            flags = ar.get("creative_flags", {})
            analysis_data["has_fear_appeal"] = flags.get("regulator_sensitive", False)
            
            # Impact scores for weighting
            impact = ar.get("impact_scores", {})
            analysis_data["impact_scores"] = impact
        
        # Transcript for dark pattern detection
        if ctx.transcript:
            analysis_data["transcript"] = ctx.transcript.get("text", "")
        else:
            analysis_data["transcript"] = ""
        
        # From physics_result (PhysicsExtractor)
        if ctx.physics_result:
            pr = ctx.physics_result
            
            # Visual physics for physiological scoring
            vp = pr.get("visual_physics", {})
            analysis_data["visual_physics"] = vp
            analysis_data["cuts_per_minute"] = vp.get("cuts_per_minute", 0)
            analysis_data["brightness_variance"] = vp.get("brightness_variance", 0)
            analysis_data["optical_flow_score"] = vp.get("optical_flow_score", 0)
            
            # Audio physics
            ap = pr.get("audio_physics", {}) or {}
            analysis_data["audio_physics"] = ap
            analysis_data["loudness_lu"] = ap.get("loudness_lu") or ap.get("rms_db")
            
            # Check for photosensitivity risk (strobe/flashing)
            # High brightness variance + high cuts = potential seizure risk
            if vp.get("brightness_variance", 0) > 0.7 and vp.get("cuts_per_minute", 0) > 60:
                analysis_data["photosensitivity_fail"] = True
            else:
                analysis_data["photosensitivity_fail"] = False
        else:
            # Defaults when physics not available
            analysis_data["visual_physics"] = {}
            analysis_data["audio_physics"] = {}
            analysis_data["cuts_per_minute"] = 0
            analysis_data["brightness_variance"] = 0
            analysis_data["loudness_lu"] = None
            analysis_data["photosensitivity_fail"] = False
        
        # Calculate claim density (claims per minute)
        duration = ctx.probe_result.get("duration", 30) if ctx.probe_result else 30
        num_claims = len(analysis_data.get("claims", []))
        analysis_data["claim_density"] = (num_claims / duration) * 60 if duration > 0 else 0
        
        return analysis_data
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if not ctx.ad_id:
            raise StageError(
                "ad_id is required (run DatabaseInsertionStage first)",
                self.name
            )
        if not ctx.analysis_result:
            raise StageError(
                "analysis_result is required (run LLMAnalysisStage first)",
                self.name
            )



