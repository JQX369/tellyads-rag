"""
Stage 8: Embedding Generation

Generates vector embeddings for all text content and stores them in the database.
Enables semantic search across ad content.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, EmbeddingError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.embeddings")


class EmbeddingsStage(Stage):
    """
    Stage 8: Generate and store embeddings.
    
    Responsibilities:
    - Prepare embedding items from analysis (chunks, segments, claims, supers)
    - Prepare storyboard embeddings
    - Prepare object detection embeddings
    - Prepare extended analysis embeddings (impact, emotional, etc.)
    - Prepare video analytics embeddings
    - Generate vectors via embedding API
    - Store in database
    - Set ctx.embedding_count
    
    This stage runs at the end and consolidates all text for embedding.
    """
    
    name = "EmbeddingsStage"
    optional = False  # Embeddings are required for search
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if ad_id exists and we have content to embed."""
        if ctx.ad_id is None:
            return False
        return ctx.embedding_count == 0  # Haven't embedded yet
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Prepare all embedding items and store them.
        """
        logger.debug("[%s] Generating embeddings...", ctx.external_id)
        
        all_items: List[Dict] = []
        
        # 1. Core embedding items (chunks, segments, claims, supers, summary)
        core_items = self._prepare_core_items(ctx)
        all_items.extend(core_items)
        
        # 2. Storyboard embeddings
        storyboard_items = self._prepare_storyboard_items(ctx)
        all_items.extend(storyboard_items)
        
        # 3. Object detection embeddings
        object_items = self._prepare_object_detection_items(ctx)
        all_items.extend(object_items)
        
        # 4. Extended analysis embeddings
        extended_items = self._prepare_extended_items(ctx)
        all_items.extend(extended_items)
        
        # 5. Video analytics embeddings
        analytics_items = self._prepare_video_analytics_items(ctx)
        all_items.extend(analytics_items)
        
        if not all_items:
            logger.warning("[%s] No embedding items to generate", ctx.external_id)
            return ctx
        
        # Generate and store embeddings
        try:
            self._embed_and_store(ctx.ad_id, all_items)  # type: ignore
            ctx.embedding_count = len(all_items)
            
            logger.debug(
                "[%s] Generated %d embeddings (core=%d, storyboard=%d, objects=%d, extended=%d, analytics=%d)",
                ctx.external_id, len(all_items),
                len(core_items), len(storyboard_items), len(object_items),
                len(extended_items), len(analytics_items)
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for transient errors
            transient_indicators = [
                "timeout", "rate limit", "429", "503", "502",
                "connection", "winerror 10035", "writeerror",
                "socket",
            ]
            is_transient = any(ind in error_str for ind in transient_indicators)
            
            if is_transient:
                raise TransientError(
                    f"Embedding API error: {e}",
                    self.name,
                    cause=e,
                )
            
            raise EmbeddingError(
                f"Embedding generation failed: {e}",
                self.name,
                cause=e,
            )
        
        return ctx
    
    def _prepare_core_items(self, ctx: ProcessingContext) -> List[Dict]:
        """
        Prepare core embedding items: chunks, segments, claims, supers, summary.
        """
        items: List[Dict] = []
        ad_id = ctx.ad_id
        analysis = ctx.analysis_result or {}
        
        chunks = analysis.get("chunks", [])
        segments = analysis.get("segments", [])
        claims = analysis.get("claims", [])
        supers = analysis.get("supers", [])
        
        # Chunks
        for chunk, chunk_id in zip(chunks, ctx.chunk_ids):
            text = (chunk.get("text") or "").strip()
            if not text:
                continue
            items.append({
                "ad_id": ad_id,
                "chunk_id": chunk_id,
                "item_type": "chunk",
                "text": text,
                "meta": {
                    "start_s": chunk.get("start_s"),
                    "end_s": chunk.get("end_s"),
                },
            })
        
        # Segments
        for segment, segment_id in zip(segments, ctx.segment_ids):
            name = (segment.get("segment_name") or "").strip()
            summary = (segment.get("segment_summary") or "").strip()
            if not name and not summary:
                continue
            items.append({
                "ad_id": ad_id,
                "segment_id": segment_id,
                "item_type": "segment",
                "text": f"{name}: {summary}".strip(": "),
                "meta": {
                    "aida_stage": segment.get("aida_stage"),
                    "duration_s": segment.get("duration_s"),
                },
            })
        
        # Claims
        for claim, claim_id in zip(claims, ctx.claim_ids):
            text = (claim.get("text") or "").strip()
            if not text:
                continue
            items.append({
                "ad_id": ad_id,
                "claim_id": claim_id,
                "item_type": "claim",
                "text": text,
                "meta": {
                    "claim_type": claim.get("claim_type"),
                    "is_comparative": claim.get("is_comparative"),
                    "likely_needs_substantiation": claim.get("likely_needs_substantiation"),
                },
            })
        
        # Supers
        for sup, sup_id in zip(supers, ctx.super_ids):
            text = (sup.get("text") or "").strip()
            if not text:
                continue
            items.append({
                "ad_id": ad_id,
                "super_id": sup_id,
                "item_type": "super",
                "text": text,
                "meta": {"super_type": sup.get("super_type")},
            })
        
        # Summary
        metadata = analysis.get("ad_metadata") or {}
        summary_text = (
            metadata.get("story_summary") or
            metadata.get("one_line_summary") or
            analysis.get("one_line_summary") or
            ""
        ).strip()
        if summary_text:
            items.append({
                "ad_id": ad_id,
                "item_type": "ad_summary",
                "text": summary_text,
                "meta": {
                    "objective": metadata.get("objective"),
                    "funnel_stage": metadata.get("funnel_stage"),
                },
            })
        
        return items
    
    def _prepare_storyboard_items(self, ctx: ProcessingContext) -> List[Dict]:
        """Prepare storyboard embedding items."""
        items: List[Dict] = []
        ad_id = ctx.ad_id
        
        for shot, shot_id in zip(ctx.storyboard_shots, ctx.storyboard_ids):
            label = shot.get("shot_label") or f"Shot {shot.get('shot_index', 'n/a')}"
            description = shot.get("description") or ""
            mood = shot.get("mood") or ""
            camera = shot.get("camera_style") or ""
            
            sections = [
                f"Shot: {label}",
                f"Description: {description}".rstrip(),
                f"Mood: {mood}".rstrip(),
                f"Camera: {camera}".rstrip(),
            ]
            text = "\n".join(section for section in sections if section.strip())
            
            if not text.strip():
                continue
                
            items.append({
                "ad_id": ad_id,
                "storyboard_id": shot_id,
                "item_type": "storyboard_shot",
                "text": text,
                "meta": {
                    "shot_index": shot.get("shot_index"),
                    "mood": shot.get("mood"),
                    "location_hint": shot.get("location_hint"),
                },
            })
        
        return items
    
    def _prepare_object_detection_items(self, ctx: ProcessingContext) -> List[Dict]:
        """Prepare object detection embedding items."""
        items: List[Dict] = []
        ad_id = ctx.ad_id
        
        if not ctx.visual_objects:
            return items
        
        # Products
        agg = ctx.visual_objects.get("aggregate_summary", {})
        products = agg.get("unique_products", [])
        logos = agg.get("unique_logos", [])
        text_items = agg.get("all_text_ocr", [])
        
        # Product embeddings
        for product in products:
            if isinstance(product, dict):
                label = product.get("label", "")
                prominence = product.get("prominence", "")
            else:
                label = str(product)
                prominence = ""
            if label:
                items.append({
                    "ad_id": ad_id,
                    "item_type": "visual_objects",
                    "text": f"Product detected: {label} ({prominence})" if prominence else f"Product detected: {label}",
                    "meta": {"category": "product", "label": label},
                })
        
        # Logo embeddings
        for logo in logos:
            if isinstance(logo, dict):
                label = logo.get("label", "")
            else:
                label = str(logo)
            if label:
                items.append({
                    "ad_id": ad_id,
                    "item_type": "brand_visual",
                    "text": f"Logo detected: {label}",
                    "meta": {"category": "logo", "label": label},
                })
        
        # OCR text embeddings
        for text_item in text_items:
            if isinstance(text_item, dict):
                text = text_item.get("content", "") or text_item.get("text", "")
            else:
                text = str(text_item)
            if text:
                items.append({
                    "ad_id": ad_id,
                    "item_type": "visual_ocr",
                    "text": f"On-screen text: {text}",
                    "meta": {"category": "ocr"},
                })
        
        return items
    
    def _prepare_extended_items(self, ctx: ProcessingContext) -> List[Dict]:
        """Prepare extended analysis embedding items."""
        items: List[Dict] = []
        ad_id = ctx.ad_id
        analysis = ctx.analysis_result or {}
        
        # Impact summary
        impact_scores = analysis.get("impact_scores") or {}
        impact_parts = []
        for score_name in ["overall_impact", "pulse_score", "echo_score", "hook_power",
                          "brand_integration", "emotional_resonance", "clarity_score", "distinctiveness"]:
            score_data = impact_scores.get(score_name, {})
            if isinstance(score_data, dict) and score_data.get("score"):
                score_val = score_data.get("score", 0)
                rationale = score_data.get("rationale") or score_data.get("evidence") or ""
                if rationale:
                    impact_parts.append(f"{score_name}: {score_val}/10 - {rationale[:100]}")
                else:
                    impact_parts.append(f"{score_name}: {score_val}/10")
        
        if impact_parts:
            items.append({
                "ad_id": ad_id,
                "item_type": "impact_summary",
                "text": " | ".join(impact_parts),
                "meta": {
                    "overall_score": impact_scores.get("overall_impact", {}).get("score"),
                },
            })
        
        # Emotional peaks
        emotional_timeline = analysis.get("emotional_timeline") or {}
        peak_emotion = emotional_timeline.get("peak_emotion")
        arc_shape = emotional_timeline.get("arc_shape")
        
        if peak_emotion and arc_shape:
            items.append({
                "ad_id": ad_id,
                "item_type": "emotional_peaks",
                "text": f"Emotional arc: {arc_shape} | Peak emotion: {peak_emotion} at {emotional_timeline.get('peak_moment_s')}s",
                "meta": {
                    "arc_shape": arc_shape,
                    "peak_emotion": peak_emotion,
                },
            })
        
        # Memorable elements
        memorability = analysis.get("memorability") or {}
        for element in memorability.get("memorable_elements", []):
            if isinstance(element, dict):
                element_text = element.get("element", "")
                if element_text:
                    brand_linked = "brand-linked" if element.get("brand_linked") else "not brand-linked"
                    score = element.get("memorability_score", 0)
                    items.append({
                        "ad_id": ad_id,
                        "item_type": "memorable_elements",
                        "text": f"{element_text} (memorability: {score}/10, {brand_linked})",
                        "meta": {"memorability_score": score},
                    })
        
        return items
    
    def _prepare_video_analytics_items(self, ctx: ProcessingContext) -> List[Dict]:
        """Prepare video analytics embedding items."""
        items: List[Dict] = []
        ad_id = ctx.ad_id
        
        if not ctx.physics_result:
            return items
        
        visual_physics = ctx.physics_result.get("visual_physics", {})
        
        if visual_physics:
            cuts_per_min = visual_physics.get("cuts_per_minute", 0)
            avg_shot = visual_physics.get("average_shot_duration_s", 0) or (60 / cuts_per_min if cuts_per_min else 0)
            flow_score = visual_physics.get("motion_energy_score", 0)
            brightness_var = visual_physics.get("brightness_variance", 0)
            
            # Describe pacing
            if cuts_per_min > 40:
                pace_desc = "very fast-paced, rapid cuts"
            elif cuts_per_min > 20:
                pace_desc = "fast-paced editing"
            elif cuts_per_min > 10:
                pace_desc = "moderate pacing"
            elif cuts_per_min > 0:
                pace_desc = "slow, deliberate pacing"
            else:
                pace_desc = "unknown pacing"
            
            # Describe motion
            if flow_score > 0.7:
                motion_desc = "high motion, dynamic action"
            elif flow_score > 0.4:
                motion_desc = "moderate movement"
            elif flow_score > 0.1:
                motion_desc = "subtle motion"
            else:
                motion_desc = "static, minimal movement"
            
            physics_text = (
                f"Visual pacing: {pace_desc} ({cuts_per_min:.0f} cuts/minute, "
                f"{avg_shot:.1f}s average shot) | Motion: {motion_desc}"
            )
            
            items.append({
                "ad_id": ad_id,
                "item_type": "visual_physics",
                "text": physics_text,
                "meta": {
                    "cuts_per_minute": cuts_per_min,
                    "motion_energy_score": flow_score,
                },
            })
        
        # Dominant colors
        dominant_colors = visual_physics.get("dominant_colors", [])
        if dominant_colors:
            color_text = f"Dominant colors: {', '.join(dominant_colors[:5])}"
            items.append({
                "ad_id": ad_id,
                "item_type": "color_palette",
                "text": color_text,
                "meta": {"dominant_hex": dominant_colors[:5]},
            })
        
        return items
    
    def _embed_and_store(self, ad_id: str, items: List[Dict]) -> None:
        """Generate embeddings and store them with retry."""
        from ... import embeddings, db_backend
        
        texts = [item["text"] for item in items]
        vectors = embeddings.embed_texts(texts)
        
        for item, vector in zip(items, vectors):
            item["embedding"] = vector
        
        # Retry logic for transient network errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                db_backend.insert_embedding_items(ad_id, items)
                return
            except Exception as e:
                error_str = str(e)
                is_transient = any(x in error_str for x in [
                    "WinError 10035",
                    "WriteError",
                    "ConnectionError",
                    "TimeoutError",
                    "socket",
                ])
                if is_transient and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Embedding insert failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1, max_retries, error_str[:100], wait_time
                    )
                    time.sleep(wait_time)
                else:
                    raise
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if not ctx.ad_id:
            raise StageError(
                "ad_id is required (run DatabaseInsertionStage first)",
                self.name
            )



