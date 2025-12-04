"""
Database helpers for Supabase Postgres.

Provides small, focused functions so the ingestion CLI can remain readable and
idempotent when inserting ads + related child records.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterable, Mapping, MutableSequence, Optional, Sequence

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor, execute_values

from .config import get_db_config

logger = logging.getLogger(__name__)

AD_COLUMNS = [
    "external_id",
    "s3_key",
    "duration_seconds",
    "width",
    "height",
    "aspect_ratio",
    "fps",
    "brand_name",
    "product_name",
    "product_category",
    "product_subcategory",
    "country",
    "region",
    "language",
    "year",
    "objective",
    "funnel_stage",
    "primary_kpi",
    "format_type",
    "primary_setting",
    "has_voiceover",
    "has_dialogue",
    "has_on_screen_text",
    "has_celeb",
    "has_ugc_style",
    "music_style",
    "editing_pace",
    "colour_mood",
    "overall_structure",
    "one_line_summary",
    "story_summary",
    "has_supers",
    "has_price_claims",
    "has_risk_disclaimer",
    "regulator_sensitive",
    "performance_metrics",
    "hero_analysis",
    "raw_transcript",
    "analysis_json",
    # Extended extraction fields (Nov 2025)
    "cta_offer",
    "brand_asset_timeline",
    "audio_fingerprint",
    "creative_dna",
    "claims_compliance",
    # Extraction v2.0 fields (Nov 2025)
    "impact_scores",
    "emotional_metrics",
    "effectiveness",
    "extraction_version",
    # Extraction observability columns (Dec 2025)
    "extraction_warnings",
    "extraction_fill_rate",
    "extraction_validation",
    # Regulatory clearance columns (Dec 2025)
    "clearance_body",
    "clearance_id",
    "clearance_country",
    # Note: processing_notes is NOT in this list - it's updated separately after insert
    # when storyboard errors occur (safety blocks, timeouts, etc.)
]

SEGMENT_COLUMNS = [
    "segment_type",
    "aida_stage",
    "emotion_focus",
    "start_time",
    "end_time",
    "transcript_text",
    "summary",
]

CHUNK_COLUMNS = [
    "chunk_index",
    "start_time",
    "end_time",
    "text",
    "aida_stage",
    "tags",
]

CLAIM_COLUMNS = [
    "text",
    "claim_type",
    "is_comparative",
    "likely_needs_substantiation",
    # Evidence grounding columns (Dec 2025)
    "timestamp_start_s",
    "timestamp_end_s",
    "evidence",
    "confidence",
]

SUPER_COLUMNS = [
    "start_time",
    "end_time",
    "text",
    "super_type",
    # Evidence grounding columns (Dec 2025)
    "evidence",
    "confidence",
]

# JSONB columns in claims/supers (need Json wrapper for psycopg2)
CLAIM_JSONB_COLUMNS = {"evidence"}
SUPER_JSONB_COLUMNS = {"evidence"}

STORYBOARD_COLUMNS = [
    "shot_index",
    "start_time",
    "end_time",
    "shot_label",
    "description",
    "camera_style",
    "location_hint",
    "key_objects",
    "on_screen_text",
    "mood",
]

EMBEDDING_COLUMNS = [
    "chunk_id",
    "segment_id",
    "claim_id",
    "super_id",
    "storyboard_id",
    "item_type",
    "text",
    "embedding",
    "meta",
]

DEFAULT_HYBRID_ITEM_TYPES = (
    "transcript_chunk",
    "segment_summary",
    "claim",
    "super",
    "storyboard_shot",
    "ad_summary",
    "implied_claim",
    "cta_offer",
    "creative_dna",
    # Extraction v2.0 embedding types
    "impact_summary",
    "memorable_elements",
    "emotional_peaks",
    "distinctive_assets",
    "effectiveness_insight",
)


@contextmanager
def get_connection():
    """Yield a psycopg2 connection with sensible defaults."""
    cfg = get_db_config()
    conn = psycopg2.connect(cfg.url, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _vector_literal(values: Sequence[float]) -> str:
    """Convert a python list into a pgvector literal string."""
    if not values:
        raise ValueError("Embedding vectors must be non-empty.")
    formatted = ",".join(f"{v:.10g}" for v in values)
    return f"[{formatted}]"


def ad_exists(*, external_id: Optional[str] = None, s3_key: Optional[str] = None) -> bool:
    """
    Return True if an ad record exists (regardless of whether processing completed).
    Use repair scripts to fix incomplete ads rather than re-ingesting.
    """
    if not external_id and not s3_key:
        raise ValueError("Must provide external_id and/or s3_key when checking ad existence.")

    conditions: MutableSequence[str] = []
    params: MutableSequence[str] = []
    if external_id:
        conditions.append("external_id = %s")
        params.append(external_id)
    if s3_key:
        conditions.append("s3_key = %s")
        params.append(s3_key)
    where_clause = " OR ".join(conditions)
    
    # Simple check - does the ad record exist?
    query = f"SELECT 1 FROM ads WHERE ({where_clause}) LIMIT 1"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone() is not None


JSONB_COLUMNS = {
    "raw_transcript",
    "analysis_json",
    "performance_metrics",
    "hero_analysis",
    "cta_offer",
    "brand_asset_timeline",
    "audio_fingerprint",
    "creative_dna",
    "claims_compliance",
    "impact_scores",
    "emotional_metrics",
    "effectiveness",
    # Extraction observability columns
    "extraction_warnings",
    "extraction_fill_rate",
    "extraction_validation",
}


def insert_ad(ad_data: Mapping[str, Any]) -> str:
    """Insert a row into ads and return the generated UUID."""
    from .schema_check import validate_schema_pg

    row = []
    for column in AD_COLUMNS:
        value = ad_data.get(column)
        if column in JSONB_COLUMNS and value is not None:
            value = Json(value)
        row.append(value)

    placeholders = ", ".join(["%s"] * len(AD_COLUMNS))
    query = f"""
        INSERT INTO ads ({', '.join(AD_COLUMNS)})
        VALUES ({placeholders})
        RETURNING id
    """

    with get_connection() as conn, conn.cursor() as cur:
        # Validate schema has required columns (cached after first call)
        validate_schema_pg(conn)

        cur.execute(query, row)
        inserted = cur.fetchone()
        ad_id = inserted["id"]
        logger.info("Inserted ad %s (external_id=%s)", ad_id, ad_data.get("external_id"))
        return ad_id


def insert_segments(ad_id: str, segments: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_segments rows."""
    rows = []
    for segment in segments or []:
        rows.append(
            [ad_id] + [segment.get(col) for col in SEGMENT_COLUMNS]
        )
    if not rows:
        return []

    query = f"""
        INSERT INTO ad_segments (ad_id, {', '.join(SEGMENT_COLUMNS)})
        VALUES %s
        RETURNING id
    """

    with get_connection() as conn, conn.cursor() as cur:
        execute_values(cur, query, rows)
        return [row["id"] for row in cur.fetchall()]


def insert_chunks(ad_id: str, chunks: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_chunks rows."""
    rows = []
    for chunk in chunks or []:
        tags = chunk.get("tags")
        rows.append(
            [ad_id]
            + [chunk.get(col) if col != "tags" else tags for col in CHUNK_COLUMNS]
        )

    if not rows:
        return []

    query = f"""
        INSERT INTO ad_chunks (ad_id, {', '.join(CHUNK_COLUMNS)})
        VALUES %s
        RETURNING id
    """

    with get_connection() as conn, conn.cursor() as cur:
        execute_values(cur, query, rows)
        return [row["id"] for row in cur.fetchall()]


def insert_claims(ad_id: str, claims: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_claims rows with evidence grounding."""
    from .schema_check import validate_table_schema_pg

    rows = []
    for claim in claims or []:
        row = [ad_id]
        for col in CLAIM_COLUMNS:
            value = claim.get(col)
            # Wrap JSONB columns with Json adapter
            if col in CLAIM_JSONB_COLUMNS and value is not None:
                value = Json(value)
            row.append(value)
        rows.append(row)

    if not rows:
        return []

    query = f"""
        INSERT INTO ad_claims (ad_id, {', '.join(CLAIM_COLUMNS)})
        VALUES %s
        RETURNING id
    """
    with get_connection() as conn, conn.cursor() as cur:
        # Validate schema has required evidence columns (cached after first call)
        validate_table_schema_pg(conn, "ad_claims")

        execute_values(cur, query, rows)
        return [row["id"] for row in cur.fetchall()]


def insert_supers(ad_id: str, supers: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_supers rows with evidence grounding."""
    from .schema_check import validate_table_schema_pg

    rows = []
    for sup in supers or []:
        row = [ad_id]
        for col in SUPER_COLUMNS:
            value = sup.get(col)
            # Wrap JSONB columns with Json adapter
            if col in SUPER_JSONB_COLUMNS and value is not None:
                value = Json(value)
            row.append(value)
        rows.append(row)

    if not rows:
        return []

    query = f"""
        INSERT INTO ad_supers (ad_id, {', '.join(SUPER_COLUMNS)})
        VALUES %s
        RETURNING id
    """
    with get_connection() as conn, conn.cursor() as cur:
        # Validate schema has required evidence columns (cached after first call)
        validate_table_schema_pg(conn, "ad_supers")

        execute_values(cur, query, rows)
        return [row["id"] for row in cur.fetchall()]


def insert_storyboards(ad_id: str, shots: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_storyboards rows."""
    rows = []
    for shot in shots or []:
        rows.append([ad_id] + [shot.get(col) for col in STORYBOARD_COLUMNS])

    if not rows:
        return []

    query = f"""
        INSERT INTO ad_storyboards (ad_id, {', '.join(STORYBOARD_COLUMNS)})
        VALUES %s
        RETURNING id
    """

    with get_connection() as conn, conn.cursor() as cur:
        execute_values(cur, query, rows)
        return [row["id"] for row in cur.fetchall()]


def insert_embedding_items(
    ad_id: str, items: Iterable[Mapping[str, Any]]
) -> Sequence[str]:
    """Insert embedding_items rows in bulk."""
    rows = []
    for item in items or []:
        embedding = item.get("embedding")
        if embedding is None:
            raise ValueError("Embedding item missing 'embedding' vector.")
        vector_literal = _vector_literal(embedding)
        row = [
            ad_id,
            item.get("chunk_id"),
            item.get("segment_id"),
            item.get("claim_id"),
            item.get("super_id"),
            item.get("storyboard_id"),
            item.get("item_type"),
            item.get("text"),
            vector_literal,
            Json(item.get("meta") or {}),
        ]
        rows.append(row)

    if not rows:
        return []

    query = """
        INSERT INTO embedding_items (
            ad_id, chunk_id, segment_id, claim_id, super_id, storyboard_id,
            item_type, text, embedding, meta
        )
        VALUES %s
        RETURNING id
    """

    with get_connection() as conn, conn.cursor() as cur:
        execute_values(cur, query, rows)
        return [row["id"] for row in cur.fetchall()]


def hybrid_search(
    query_embedding: Sequence[float],
    query_text: str,
    limit: int = 50,
    item_types: Optional[Sequence[str]] = None,
) -> Sequence[Mapping[str, Any]]:
    """Call the match_embedding_items_hybrid Postgres function."""
    if limit <= 0:
        raise ValueError("limit must be positive for hybrid search.")
    vector = _vector_literal(query_embedding)
    search_types = list(item_types or DEFAULT_HYBRID_ITEM_TYPES)
    sql_query = """
        SELECT *
        FROM match_embedding_items_hybrid(
            %s::vector,
            %s::text,
            %s::int,
            %s::text[]
        )
    """
    params = (vector, query_text, limit, search_types)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql_query, params)
        return cur.fetchall()


__all__ = [
    "get_connection",
    "ad_exists",
    "insert_ad",
    "insert_segments",
    "insert_chunks",
    "insert_claims",
    "insert_supers",
    "insert_storyboards",
    "insert_embedding_items",
    "hybrid_search",
    "find_incomplete_ads",
    "delete_ad",
]


def find_incomplete_ads(
    check_storyboard: bool = True,
    check_v2_extraction: bool = True,
    check_impact_scores: bool = True,
    check_embeddings: bool = True,
    limit: int = 100,
) -> list[dict]:
    """
    Find ads that have incomplete data and should be re-processed.
    
    An ad is considered incomplete if it's missing:
    - Storyboard shots (if check_storyboard=True)
    - v2.0 extraction (extraction_version != '2.0' if check_v2_extraction=True)
    - Impact scores (if check_impact_scores=True)
    - Embeddings (if check_embeddings=True)
    
    Returns list of dicts with {id, external_id, s3_key, missing_components}.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Build query to find incomplete ads
            query = """
                SELECT 
                    a.id,
                    a.external_id,
                    a.s3_key,
                    a.extraction_version,
                    a.impact_scores,
                    (SELECT COUNT(*) FROM ad_storyboards WHERE ad_id = a.id) as storyboard_count,
                    (SELECT COUNT(*) FROM embedding_items WHERE ad_id = a.id) as embedding_count
                FROM ads a
                ORDER BY a.created_at DESC
                LIMIT %s
            """
            cur.execute(query, (limit,))
            rows = cur.fetchall()
            
    incomplete = []
    for row in rows:
        ad_id, external_id, s3_key, version, impact_scores, storyboard_count, embedding_count = row
        missing = []
        
        # Check v2 extraction
        if check_v2_extraction:
            version = version or "1.0"
            if version != "2.0":
                missing.append(f"extraction_v{version}")
        
        # Check impact scores
        if check_impact_scores:
            if not impact_scores or not impact_scores.get("overall_impact"):
                missing.append("impact_scores")
        
        # Check storyboard
        if check_storyboard and storyboard_count == 0:
            missing.append("storyboard")
        
        # Check embeddings
        if check_embeddings and embedding_count == 0:
            missing.append("embeddings")
        
        if missing:
            incomplete.append({
                "id": str(ad_id),
                "external_id": external_id,
                "s3_key": s3_key,
                "missing": missing,
            })
    
    logger.info(
        "Found %d/%d ads with incomplete data",
        len(incomplete), len(rows)
    )
    return incomplete


def delete_ad(ad_id: str) -> bool:
    """
    Delete an ad and all related child records.
    
    Deletes from: embedding_items, ad_storyboards, ad_supers, ad_claims, 
    ad_chunks, ad_segments, then ads.
    
    Returns True if successful.
    """
    child_tables = [
        "embedding_items",
        "ad_storyboards", 
        "ad_supers",
        "ad_claims",
        "ad_chunks",
        "ad_segments",
    ]
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in child_tables:
                try:
                    cur.execute(f"DELETE FROM {table} WHERE ad_id = %s", (ad_id,))
                except Exception as e:
                    logger.warning("Failed to delete from %s: %s", table, e)
            
            # Delete the ad itself
            try:
                cur.execute("DELETE FROM ads WHERE id = %s", (ad_id,))
                conn.commit()
                logger.info("Deleted ad %s and all child records", ad_id)
                return True
            except Exception as e:
                conn.rollback()
                logger.error("Failed to delete ad %s: %s", ad_id, e)
                return False


def update_processing_notes(ad_id: str, notes: dict) -> None:
    """
    Update the processing_notes field for an ad.
    
    Args:
        ad_id: UUID of the ad
        notes: Dictionary containing processing notes (e.g., errors, warnings)
    
    Note: Gracefully handles the case where the column doesn't exist yet.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "UPDATE ads SET processing_notes = %s WHERE id = %s",
                    (Json(notes), ad_id)
                )
                conn.commit()
                logger.debug("Updated processing_notes for ad %s", ad_id)
            except Exception as e:
                conn.rollback()
                error_msg = str(e).lower()
                if "column" in error_msg and "does not exist" in error_msg:
                    logger.debug(
                        "processing_notes column not yet added to database. "
                        "Run migration: ALTER TABLE ads ADD COLUMN processing_notes jsonb;"
                    )
                else:
                    logger.warning("Failed to update processing_notes for ad %s: %s", ad_id, e)


def update_visual_objects(ad_id: str, visual_objects: dict) -> None:
    """
    Update the visual_objects field for an ad.
    
    Args:
        ad_id: UUID of the ad
        visual_objects: Dictionary containing visual object detection results
    
    Note: Gracefully handles the case where the column doesn't exist yet.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "UPDATE ads SET visual_objects = %s WHERE id = %s",
                    (Json(visual_objects), ad_id)
                )
                conn.commit()
                logger.debug("Updated visual_objects for ad %s", ad_id)
            except Exception as e:
                conn.rollback()
                error_msg = str(e).lower()
                if "column" in error_msg and "does not exist" in error_msg:
                    logger.debug(
                        "visual_objects column not yet added to database. "
                        "Run migration: ALTER TABLE ads ADD COLUMN visual_objects jsonb DEFAULT '{}'::jsonb;"
                    )
                else:
                    logger.warning("Failed to update visual_objects for ad %s: %s", ad_id, e)


def update_video_analytics(
    ad_id: str,
    visual_physics: dict,
    spatial_telemetry: dict,
    color_psychology: dict,
) -> None:
    """
    Update video analytics fields for an ad.
    
    Args:
        ad_id: UUID of the ad
        visual_physics: Dict with cuts_per_minute, optical_flow_score, etc.
        spatial_telemetry: Dict with bounding boxes, screen coverage, etc.
        color_psychology: Dict with dominant_hex, ratios, contrast, etc.
    
    Note: Gracefully handles the case where columns don't exist yet.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    UPDATE ads SET 
                        visual_physics = %s,
                        spatial_telemetry = %s,
                        color_psychology = %s
                    WHERE id = %s
                    """,
                    (Json(visual_physics), Json(spatial_telemetry), Json(color_psychology), ad_id)
                )
                conn.commit()
                logger.debug("Updated video analytics for ad %s", ad_id)
            except Exception as e:
                conn.rollback()
                error_msg = str(e).lower()
                if "column" in error_msg and "does not exist" in error_msg:
                    logger.debug(
                        "Video analytics columns not yet added to database. "
                        "Run migration to add visual_physics, spatial_telemetry, color_psychology columns."
                    )
                else:
                    logger.warning("Failed to update video analytics for ad %s: %s", ad_id, e)


def update_physics_data(ad_id: str, physics_data: dict) -> None:
    """
    Update the unified physics_data field for an ad.
    
    Args:
        ad_id: UUID of the ad
        physics_data: Complete physics extraction result from PhysicsExtractor
    
    Note: Gracefully handles the case where column doesn't exist yet.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "UPDATE ads SET physics_data = %s WHERE id = %s",
                    (Json(physics_data), ad_id)
                )
                conn.commit()
                logger.debug("Updated physics_data for ad %s", ad_id)
            except Exception as e:
                conn.rollback()
                error_msg = str(e).lower()
                if "column" in error_msg and "does not exist" in error_msg:
                    logger.debug(
                        "physics_data column not yet added to database. "
                        "Run migration: ALTER TABLE ads ADD COLUMN physics_data jsonb DEFAULT '{}'::jsonb;"
                    )
                else:
                    logger.warning("Failed to update physics_data for ad %s: %s", ad_id, e)


def update_toxicity_report(ad_id: str, toxicity_report: dict) -> None:
    """
    Update toxicity fields for an ad.

    Persists both:
    - Explicit columns for filtering (toxicity_total, toxicity_risk_level, etc.)
    - Full toxicity_report JSONB for detailed analysis

    Args:
        ad_id: UUID of the ad
        toxicity_report: Complete toxicity scoring report from ToxicityScorer

    Note: Gracefully handles the case where columns don't exist yet.
    """
    # Extract explicit column values from the report
    toxicity_total = toxicity_report.get("toxic_score")
    toxicity_risk_level = toxicity_report.get("risk_level")

    # Extract dark pattern labels
    dark_patterns = toxicity_report.get("dark_patterns_detected", [])
    # Get unique category labels from breakdown
    breakdown = toxicity_report.get("breakdown", {})
    toxicity_labels = []
    for category in ["physiological", "psychological", "regulatory"]:
        cat_data = breakdown.get(category, {})
        for flag in cat_data.get("flags", []):
            # Extract category from flag text (e.g., "False Scarcity Detected" -> "false_scarcity")
            if "Detected" in flag:
                label = flag.split(" Detected")[0].lower().replace(" ", "_")
                if label not in toxicity_labels:
                    toxicity_labels.append(label)
    # Also add dark pattern categories
    for pattern in dark_patterns:
        if pattern and pattern not in toxicity_labels:
            toxicity_labels.append(pattern)

    # Extract subscores
    toxicity_subscores = {
        "physiological": breakdown.get("physiological", {}),
        "psychological": breakdown.get("psychological", {}),
        "regulatory": breakdown.get("regulatory", {}),
    }

    # Determine version (check if AI was used)
    metadata = toxicity_report.get("metadata", {})
    ai_enabled = metadata.get("ai_enabled", False)
    toxicity_version = "1.1.0-ai" if ai_enabled else "1.0.0"

    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                # Try to update all columns (new schema)
                cur.execute(
                    """
                    UPDATE ads SET
                        toxicity_total = %s,
                        toxicity_risk_level = %s,
                        toxicity_labels = %s,
                        toxicity_subscores = %s,
                        toxicity_version = %s,
                        toxicity_report = %s
                    WHERE id = %s
                    """,
                    (
                        toxicity_total,
                        toxicity_risk_level,
                        Json(toxicity_labels),
                        Json(toxicity_subscores),
                        toxicity_version,
                        Json(toxicity_report),
                        ad_id
                    )
                )
                conn.commit()
                logger.debug(
                    "Updated toxicity for ad %s (score: %s, risk: %s, version: %s)",
                    ad_id, toxicity_total, toxicity_risk_level, toxicity_version
                )
            except Exception as e:
                conn.rollback()
                error_msg = str(e).lower()

                # Check if it's a missing column error
                if "column" in error_msg and "does not exist" in error_msg:
                    # Fallback: try updating just toxicity_report (old schema)
                    try:
                        with conn.cursor() as cur2:
                            cur2.execute(
                                "UPDATE ads SET toxicity_report = %s WHERE id = %s",
                                (Json(toxicity_report), ad_id)
                            )
                            conn.commit()
                            logger.debug(
                                "Updated toxicity_report (legacy) for ad %s. "
                                "Run schema_toxicity_columns.sql for full support.",
                                ad_id
                            )
                    except Exception as e2:
                        conn.rollback()
                        logger.warning(
                            "Failed to update toxicity for ad %s. "
                            "Run migration: tvads_rag/schema_toxicity_columns.sql. Error: %s",
                            ad_id, str(e2)[:100]
                        )
                else:
                    logger.warning("Failed to update toxicity for ad %s: %s", ad_id, str(e)[:100])

