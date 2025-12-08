"""
Stage 6: Database Insertion

Builds ad payload and inserts main ad record plus child records
(segments, chunks, claims, supers) into the database.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError, DatabaseError, TransientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.db_insertion")


class DatabaseInsertionStage(Stage):
    """
    Stage 6: Insert ad and related records into database.
    
    Responsibilities:
    - Build ad payload from analysis result
    - Insert main ad record
    - Insert child records (segments, chunks, claims, supers)
    - Set ctx.ad_id, ctx.segment_ids, ctx.chunk_ids, ctx.claim_ids, ctx.super_ids
    
    Raises:
        DatabaseError: If database operations fail
    """
    
    name = "DatabaseInsertionStage"
    optional = False
    
    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if analysis complete but not yet inserted."""
        return ctx.analysis_result is not None and ctx.ad_id is None
    
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Build payload and insert records into database.
        """
        from ... import db_backend
        from ...analysis import extract_flat_metadata, extract_jsonb_columns, EXTRACTION_VERSION
        from ...media import normalize_ad_duration
        
        logger.debug("[%s] Inserting into database...", ctx.external_id)
        
        try:
            # Build ad payload
            ad_payload = self._build_ad_payload(ctx)
            
            # Insert main ad record
            ad_id = db_backend.insert_ad(ad_payload)
            ctx.ad_id = ad_id
            
            # Insert child records
            analysis = ctx.analysis_result or {}
            
            segment_ids = db_backend.insert_segments(ad_id, analysis.get("segments", []))
            ctx.segment_ids = list(segment_ids)
            
            chunk_ids = db_backend.insert_chunks(ad_id, analysis.get("chunks", []))
            ctx.chunk_ids = list(chunk_ids)
            
            claim_ids = db_backend.insert_claims(ad_id, analysis.get("claims", []))
            ctx.claim_ids = list(claim_ids)
            
            super_ids = db_backend.insert_supers(ad_id, analysis.get("supers", []))
            ctx.super_ids = list(super_ids)
            
            logger.debug(
                "[%s] Database insert complete: ad_id=%s, segments=%d, chunks=%d, claims=%d, supers=%d",
                ctx.external_id, ad_id, len(segment_ids), len(chunk_ids), 
                len(claim_ids), len(super_ids)
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for transient errors
            transient_indicators = [
                "timeout", "connection", "temporarily",
                "too many connections", "deadlock",
            ]
            is_transient = any(ind in error_str for ind in transient_indicators)
            
            if is_transient:
                raise TransientError(
                    f"Database error: {e}",
                    self.name,
                    cause=e,
                )
            
            raise DatabaseError(
                f"Database insertion failed: {e}",
                self.name,
                cause=e,
            )
        
        return ctx
    
    def _build_ad_payload(self, ctx: ProcessingContext) -> Dict[str, Any]:
        """
        Build the ad payload for database insertion.
        
        Extracts flat fields and JSONB columns from the analysis result.
        """
        from ...analysis import extract_flat_metadata, extract_jsonb_columns, EXTRACTION_VERSION
        from ...media import normalize_ad_duration
        
        analysis_result = ctx.analysis_result or {}
        transcript = ctx.transcript or {}
        probe = ctx.probe_result or {}
        metadata_entry = ctx.metadata_entry
        hero_analysis = ctx.hero_analysis
        
        # Extract flat fields from v2 analysis
        flat_fields = extract_flat_metadata(analysis_result)
        
        # Extract JSONB column data
        jsonb_columns = extract_jsonb_columns(analysis_result)
        
        # Ensure has_supers and has_price_claims are set
        flat_fields.setdefault("has_supers", bool(analysis_result.get("supers")))
        flat_fields.setdefault(
            "has_price_claims",
            any(
                (claim.get("claim_type") or "").lower() == "price"
                for claim in analysis_result.get("claims", [])
            ),
        )
        
        # Override with metadata_entry if provided
        if metadata_entry:
            if metadata_entry.brand_name:
                flat_fields["brand_name"] = metadata_entry.brand_name
            if metadata_entry.title and not flat_fields.get("one_line_summary"):
                flat_fields["one_line_summary"] = metadata_entry.title
            if metadata_entry.duration_seconds and not probe.get("duration_seconds"):
                probe["duration_seconds"] = normalize_ad_duration(metadata_entry.duration_seconds)
        
        # Build performance metrics from metadata
        perf_metrics: Optional[Dict] = None
        if metadata_entry:
            perf_metrics = {}
            if metadata_entry.views is not None:
                perf_metrics["views"] = metadata_entry.views
            if metadata_entry.date_collected:
                perf_metrics["date_collected"] = metadata_entry.date_collected
            if hasattr(metadata_entry, 'raw_row') and metadata_entry.raw_row.get("latest_ads"):
                perf_metrics["latest_ads_path"] = metadata_entry.raw_row.get("latest_ads")
            if metadata_entry.record_id:
                perf_metrics["legacy_record_id"] = metadata_entry.record_id
            if not perf_metrics:
                perf_metrics = None
        
        # Build payload
        payload = {**flat_fields}
        payload.update(
            external_id=ctx.external_id,
            s3_key=ctx.s3_key,
            duration_seconds=probe.get("duration_seconds"),
            width=probe.get("width"),
            height=probe.get("height"),
            aspect_ratio=probe.get("aspect_ratio"),
            fps=probe.get("fps"),
            raw_transcript=transcript,
            analysis_json=analysis_result,
            performance_metrics=perf_metrics or {},
            hero_analysis=hero_analysis,
            # Extraction v2.0 JSONB columns
            impact_scores=jsonb_columns.get("impact_scores"),
            emotional_metrics=jsonb_columns.get("emotional_metrics"),
            effectiveness=jsonb_columns.get("effectiveness"),
            extraction_version=EXTRACTION_VERSION,
            # Legacy columns (for backwards compatibility)
            cta_offer=jsonb_columns.get("cta_offer"),
            brand_asset_timeline=jsonb_columns.get("brand_asset_timeline"),
            audio_fingerprint=jsonb_columns.get("audio_fingerprint"),
            creative_dna=jsonb_columns.get("creative_dna"),
            claims_compliance=jsonb_columns.get("claims_compliance"),
            # Visual object detection (populated later by VisionStage)
            visual_objects={},
            # Extraction observability fields (also in analysis_json, but explicit for querying)
            extraction_warnings=analysis_result.get("extraction_warnings", []),
            extraction_fill_rate=analysis_result.get("extraction_fill_rate", {}),
            extraction_validation=analysis_result.get("extraction_validation", {}),
        )

        return payload
    
    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if ctx.analysis_result is None:
            raise StageError(
                "analysis_result is required (run LLMAnalysisStage first)",
                self.name
            )




