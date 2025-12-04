"""
Stage 7b: Physics Extraction

Extracts objective visual and audio metrics using the PhysicsExtractor.
Includes scene detection, motion analysis, dominant colors, object detection, and audio metrics.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.physics")


class PhysicsStage(Stage):
    """
    Stage 7b: Physics extraction (optional).
    
    Responsibilities:
    - Run PhysicsExtractor for scene detection, motion, brightness
    - Extract dominant colors via K-Means clustering
    - Run YOLO object detection on keyframes
    - Extract audio metrics (BPM, loudness) via librosa
    - Upload keyframes to S3 (if configured)
    - Update database with physics_data
    - Set ctx.physics_result
    
    This stage is optional - failures don't stop the pipeline.
    """
    
    name = "PhysicsStage"
    optional = True  # Non-blocking - failures don't stop pipeline
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if physics enabled and ad_id exists."""
        if not config.physics_enabled:
            return False
        if ctx.ad_id is None:
            return False
        if ctx.video_path is None:
            return False
        return ctx.physics_result is None  # Haven't run yet
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Run physics extraction.
        """
        from ...physics_engine import PhysicsExtractor, PHYSICS_VERSION
        from ...config import get_video_analytics_config, is_video_analytics_enabled
        from ... import db_backend
        
        video_analytics_cfg = get_video_analytics_config()
        
        if not is_video_analytics_enabled(video_analytics_cfg):
            logger.debug("[%s] Physics extraction disabled", ctx.external_id)
            return ctx
        
        logger.debug("[%s] Running physics extraction...", ctx.external_id)
        
        # Create temp directory for keyframes
        physics_output_dir = Path(tempfile.mkdtemp(prefix=f"physics_{ctx.external_id}_"))
        ctx.register_temp_dir(physics_output_dir)
        
        try:
            # Run PhysicsExtractor
            extractor = PhysicsExtractor(
                video_path=str(ctx.video_path),
                output_dir=str(physics_output_dir),
                ad_id=ctx.ad_id,
                upload_to_s3=True,  # Upload keyframes to S3
                cleanup_local=True,  # Clean up local files after upload
                yolo_model=video_analytics_cfg.yolo_model,
                motion_sample_rate=video_analytics_cfg.optical_flow_sample_rate,
                color_clusters=video_analytics_cfg.color_clusters,
            )
            physics_result = extractor.extract()
            ctx.physics_result = physics_result
            
            # Store in database
            if ctx.ad_id:
                db_backend.update_physics_data(ctx.ad_id, physics_result)
                
                # Also update legacy video_analytics columns for backward compatibility
                visual_physics = physics_result.get("visual_physics", {})
                spatial_telemetry = {
                    "objects_detected": physics_result.get("objects_detected", []),
                    "spatial_data": physics_result.get("spatial_data", {}),
                }
                
                # Build color_psychology from extracted dominant colors
                dominant_colors = visual_physics.get("dominant_colors", [])
                # Calculate ratios based on keyframe count
                num_colors = len(dominant_colors)
                ratios = [round(1.0 / num_colors, 2)] * num_colors if num_colors > 0 else []
                
                # Estimate brightness from brightness_variance (0=dark, 1=bright)
                brightness_var = visual_physics.get("brightness_variance", 0.5)
                brightness_mean = min(max(0.5 + (brightness_var - 0.5) * 0.3, 0.2), 0.8)
                
                color_psychology = {
                    "dominant_hex": dominant_colors,
                    "ratios": ratios,
                    "contrast_ratio": round(1.0 + brightness_var * 10, 1),  # Higher variance = higher contrast
                    "saturation_mean": round(0.5 + brightness_var * 0.3, 2),  # Estimate
                    "brightness_mean": round(brightness_mean, 2),
                    "color_temperature": "warm" if brightness_mean > 0.55 else "cool" if brightness_mean < 0.45 else "neutral",
                    "color_count": num_colors,
                }
                
                try:
                    db_backend.update_video_analytics(
                        ctx.ad_id,
                        visual_physics,
                        spatial_telemetry,
                        color_psychology,
                    )
                except Exception as legacy_err:
                    # Non-fatal - legacy columns may not exist
                    logger.debug(
                        "[%s] Could not update legacy video_analytics: %s",
                        ctx.external_id, str(legacy_err)[:100]
                    )
            
            # Log summary
            vp = physics_result.get("visual_physics", {})
            ap = physics_result.get("audio_physics") or {}
            logger.debug(
                "[%s] Physics v%s: cuts/min=%.1f, motion=%.2f, bpm=%s, objects=%d",
                ctx.external_id,
                physics_result.get("physics_version", PHYSICS_VERSION),
                vp.get("cuts_per_minute", 0),
                vp.get("motion_energy_score", 0),
                ap.get("tempo_bpm", "N/A"),
                len(physics_result.get("objects_detected", [])),
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for transient errors
            transient_indicators = [
                "timeout", "connection", "temporarily",
                "resource", "memory",
            ]
            is_transient = any(ind in error_str for ind in transient_indicators)
            
            if is_transient:
                raise TransientError(
                    f"Physics extraction error: {e}",
                    self.name,
                    cause=e,
                )
            
            logger.warning(
                "[%s] Physics extraction failed: %s",
                ctx.external_id, str(e)[:100]
            )
            ctx.add_processing_note("physics_error", {
                "type": "error",
                "reason": str(e)[:500],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        
        return ctx
    
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

