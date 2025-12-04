"""
Stage 7: Vision Analysis

Performs storyboard analysis and object detection using vision models.
Samples video frames and analyzes with Gemini Vision API.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, VisionError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.vision")


class VisionStage(Stage):
    """
    Stage 7: Vision/storyboard analysis (optional).
    
    Responsibilities:
    - Sample frames from video at key timestamps
    - Run storyboard analysis with vision model
    - Run object detection on same frames
    - Insert storyboard records into database
    - Update ad with visual_objects
    - Set ctx.storyboard_shots, ctx.storyboard_ids, ctx.visual_objects, ctx.frame_samples
    
    This stage is optional - failures don't stop the pipeline.
    """
    
    name = "VisionStage"
    optional = True  # Non-blocking - failures don't stop pipeline
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if vision enabled and ad_id exists."""
        if not config.vision_enabled:
            return False
        if ctx.ad_id is None:
            return False
        if ctx.video_path is None:
            return False
        return len(ctx.storyboard_shots) == 0  # Haven't run yet
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Sample frames and run vision analysis.
        """
        from ... import visual_analysis, db_backend
        from ...visual_analysis import SafetyBlockError, StoryboardTimeoutError, analyse_frames_for_objects
        from ...config import get_vision_config
        
        vision_cfg = get_vision_config()
        effective_tier = ctx.vision_tier or vision_cfg.default_tier
        
        logger.debug("[%s] Running storyboard and object detection...", ctx.external_id)
        
        try:
            # Extract trigger timestamps from transcript
            trigger_timestamps = self._extract_trigger_timestamps(ctx)
            if trigger_timestamps:
                logger.debug(
                    "[%s] Found %d audio trigger timestamps",
                    ctx.external_id, len(trigger_timestamps)
                )
            
            # Sample frames
            frame_samples = visual_analysis.sample_frames_for_storyboard(
                str(ctx.video_path),
                vision_cfg.frame_sample_seconds,
                trigger_timestamps=trigger_timestamps
            )
            ctx.frame_samples = frame_samples
            
            # Run storyboard analysis with retry
            storyboard_shots = self._storyboard_with_retry(
                frame_samples,
                effective_tier,
                ctx.external_id,
                ctx.transcript.get("text", "") if ctx.transcript else ""
            )
            ctx.storyboard_shots = storyboard_shots
            
            # Insert storyboard records
            if ctx.ad_id and storyboard_shots:
                storyboard_ids = db_backend.insert_storyboards(ctx.ad_id, storyboard_shots)
                ctx.storyboard_ids = list(storyboard_ids)
            
            # Run object detection
            self._run_object_detection(ctx, frame_samples, effective_tier)
            
        except SafetyBlockError as e:
            logger.warning(
                "[%s] Storyboard blocked by safety filter: %s",
                ctx.external_id, e.reason
            )
            ctx.add_processing_note("storyboard_error", {
                "type": "safety_block",
                "reason": e.reason,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            
        except StoryboardTimeoutError as e:
            logger.warning("[%s] Storyboard analysis timed out: %s", ctx.external_id, str(e))
            ctx.add_processing_note("storyboard_error", {
                "type": "timeout",
                "reason": str(e),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            
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
                    f"Vision API error: {e}",
                    self.name,
                    cause=e,
                )
            
            logger.warning("[%s] Storyboard analysis failed: %s", ctx.external_id, str(e)[:100])
            ctx.add_processing_note("storyboard_error", {
                "type": "error",
                "reason": str(e)[:500],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        
        return ctx
    
    def _extract_trigger_timestamps(self, ctx: ProcessingContext) -> List[float]:
        """
        Extract timestamps of key moments from transcript.
        
        Looks for brand mentions, product mentions, and key phrases.
        """
        triggers: List[float] = []
        
        if not ctx.transcript:
            return triggers
        
        segments = ctx.transcript.get("segments", [])
        brand_name = None
        
        # Get brand name from analysis or metadata
        if ctx.analysis_result:
            brand_name = ctx.analysis_result.get("brand_name")
        if not brand_name and ctx.metadata_entry:
            brand_name = ctx.metadata_entry.brand_name
        
        brand_pattern = None
        if brand_name:
            # Create pattern for brand name (case insensitive)
            brand_pattern = re.compile(re.escape(brand_name), re.IGNORECASE)
        
        for segment in segments:
            text = (segment.get("text") or "").strip().lower()
            start = segment.get("start")
            
            if start is None or not text:
                continue
            
            # Check for brand mentions
            if brand_pattern and brand_pattern.search(text):
                triggers.append(float(start))
                continue
            
            # Check for key phrases
            key_phrases = [
                "introducing", "new", "now", "today", "announcing",
                "presenting", "welcome", "finally", "available",
                "order now", "buy now", "get yours", "call now",
                "visit", "click", "download", "subscribe",
            ]
            
            for phrase in key_phrases:
                if phrase in text:
                    triggers.append(float(start))
                    break
        
        return sorted(list(set(triggers)))
    
    def _storyboard_with_retry(
        self,
        frame_samples: List[Any],
        tier: str,
        external_id: str,
        transcript_text: str = ""
    ) -> List[Dict]:
        """
        Run storyboard analysis with retry logic.
        """
        from ... import visual_analysis
        from ...visual_analysis import SafetyBlockError, StoryboardTimeoutError
        
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return visual_analysis.analyse_frames_to_storyboard(
                    frame_samples,
                    tier=tier,
                    transcript_text=transcript_text
                )
            except (SafetyBlockError, StoryboardTimeoutError):
                # Don't retry safety blocks or timeouts
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 3.0 * (2 ** attempt)
                    logger.warning(
                        "[%s] Storyboard failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        external_id, attempt + 1, max_retries + 1,
                        str(e)[:100], wait_time
                    )
                    time.sleep(wait_time)
        
        raise last_error  # type: ignore
    
    def _run_object_detection(
        self,
        ctx: ProcessingContext,
        frame_samples: List[Any],
        tier: str
    ) -> None:
        """
        Run object detection on sampled frames.
        """
        from ... import db_backend
        from ...visual_analysis import SafetyBlockError, analyse_frames_for_objects
        
        logger.debug("[%s] Running object detection...", ctx.external_id)
        
        try:
            visual_objects_result = analyse_frames_for_objects(frame_samples, tier=tier)
            
            if visual_objects_result and ctx.ad_id:
                # Update ad with visual_objects
                db_backend.update_visual_objects(ctx.ad_id, visual_objects_result)
                ctx.visual_objects = visual_objects_result
                
                agg = visual_objects_result.get("aggregate_summary", {})
                logger.debug(
                    "[%s] Object detection: %d products, %d logos, %d text items",
                    ctx.external_id,
                    len(agg.get("unique_products", [])),
                    len(agg.get("unique_logos", [])),
                    len(agg.get("all_text_ocr", [])),
                )
                
        except SafetyBlockError as e:
            logger.warning(
                "[%s] Object detection blocked by safety filter: %s",
                ctx.external_id, e.reason
            )
            ctx.add_processing_note("object_detection_error", {
                "type": "safety_block",
                "reason": e.reason,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            
        except Exception as e:
            logger.warning(
                "[%s] Object detection failed: %s",
                ctx.external_id, str(e)[:100]
            )
            ctx.add_processing_note("object_detection_error", {
                "type": "error",
                "reason": str(e)[:500],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if not ctx.video_path:
            raise StageError(
                "video_path is required (run VideoLoadStage first)",
                self.name
            )
        if not ctx.ad_id:
            raise StageError(
                "ad_id is required (run DatabaseInsertionStage first)",
                self.name
            )
    
    def on_error(
        self,
        ctx: ProcessingContext,
        error: Exception,
        config: PipelineConfig,
    ) -> None:
        """Clean up frame samples on error."""
        from ... import visual_analysis
        
        if ctx.frame_samples:
            visual_analysis.cleanup_frame_samples(ctx.frame_samples)
            ctx.frame_samples = []
        
        super().on_error(ctx, error, config)

