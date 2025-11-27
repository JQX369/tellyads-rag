"""
HTTP-based database helpers using the Supabase Python client.

This module mirrors the public interface of `db.py` but talks to Supabase
over HTTPS (port 443) instead of direct Postgres connections on port 5432.

It is intended for environments where direct Postgres access is blocked but
the Supabase REST/RPC APIs are reachable.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Iterable, Mapping, MutableSequence, Optional, Sequence

from .config import get_db_config
from .db import (
    AD_COLUMNS,
    SEGMENT_COLUMNS,
    CHUNK_COLUMNS,
    CLAIM_COLUMNS,
    SUPER_COLUMNS,
    STORYBOARD_COLUMNS,
    DEFAULT_HYBRID_ITEM_TYPES,
)

logger = logging.getLogger(__name__)

try:
    from supabase import Client, create_client
except ImportError as exc:  # pragma: no cover - import error path
    raise RuntimeError(
        "Supabase HTTP backend requires the 'supabase' package. "
        "Run `pip install -r tvads_rag/requirements.txt` to install it."
    ) from exc


@lru_cache(maxsize=1)
def _get_client() -> Client:
    """
    Lazily construct a Supabase client from DBConfig.

    Uses SUPABASE_URL + SUPABASE_SERVICE_KEY so we never depend on direct
    Postgres connectivity when DB_BACKEND=http.
    """
    cfg = get_db_config()
    if not cfg.supabase_url or not cfg.service_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set when using the "
            "HTTP DB backend (DB_BACKEND=http)."
        )
    return create_client(cfg.supabase_url, cfg.service_key)


def ad_exists(*, external_id: Optional[str] = None, s3_key: Optional[str] = None) -> bool:
    """
    HTTP implementation of ad existence check.
    
    Returns True if an ad record exists (regardless of whether processing completed).
    Use repair scripts to fix incomplete ads rather than re-ingesting.
    """
    if not external_id and not s3_key:
        raise ValueError("Must provide external_id and/or s3_key when checking ad existence.")

    client = _get_client()

    # Check if ad exists by external_id
    if external_id:
        resp = (
            client.table("ads")
            .select("id")
            .eq("external_id", external_id)
            .limit(1)
            .execute()
        )
        if getattr(resp, "data", None) and len(resp.data) > 0:
            return True
    
    # Check by s3_key if external_id not found
    if s3_key:
        resp = (
            client.table("ads")
            .select("id")
            .eq("s3_key", s3_key)
            .limit(1)
            .execute()
        )
        if getattr(resp, "data", None) and len(resp.data) > 0:
            return True
    
    return False


def insert_ad(ad_data: Mapping[str, Any]) -> str:
    """Insert a row into ads and return the generated UUID via HTTP."""
    row = {column: ad_data.get(column) for column in AD_COLUMNS}
    client = _get_client()
    # Insert with returning clause to get the ID back
    resp = client.table("ads").insert(row).execute()
    data = getattr(resp, "data", None) or []
    if not data:
        raise RuntimeError("Failed to insert ad via Supabase HTTP backend (no id returned).")
    ad_id = data[0]["id"]
    logger.info("Inserted ad %s (external_id=%s) via HTTP", ad_id, ad_data.get("external_id"))
    return ad_id


def update_processing_notes(ad_id: str, notes: dict) -> None:
    """Update the processing_notes field for an ad.
    
    Args:
        ad_id: UUID of the ad
        notes: Dictionary containing processing notes (e.g., errors, warnings)
    
    Note: Gracefully handles the case where the column doesn't exist yet.
    """
    client = _get_client()
    try:
        resp = client.table("ads").update({"processing_notes": notes}).eq("id", ad_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            logger.warning("Failed to update processing_notes for ad %s", ad_id)
        else:
            logger.debug("Updated processing_notes for ad %s", ad_id)
    except Exception as e:
        # Handle case where column doesn't exist yet
        error_msg = str(e).lower()
        if "column" in error_msg and "does not exist" in error_msg:
            logger.debug(
                "processing_notes column not yet added to database. "
                "Run migration: ALTER TABLE ads ADD COLUMN processing_notes jsonb;"
            )
        else:
            logger.warning("Failed to update processing_notes for ad %s: %s", ad_id, str(e)[:100])


def _insert_many(table: str, rows: Iterable[Sequence[Any]]) -> Sequence[str]:
    rows_list = list(rows)
    if not rows_list:
        return []
    client = _get_client()
    # Insert with default returning (should include id)
    resp = client.table(table).insert(rows_list).execute()
    data = getattr(resp, "data", None) or []
    return [row["id"] for row in data]


def insert_segments(ad_id: str, segments: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_segments rows via HTTP."""
    rows = []
    for segment in segments or []:
        rows.append(
            {"ad_id": ad_id}
            | {col: segment.get(col) for col in SEGMENT_COLUMNS}
        )
    return _insert_many("ad_segments", rows)


def insert_chunks(ad_id: str, chunks: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_chunks rows via HTTP."""
    rows = []
    for chunk in chunks or []:
        payload = {"ad_id": ad_id}
        for col in CHUNK_COLUMNS:
            payload[col] = chunk.get(col)
        rows.append(payload)
    return _insert_many("ad_chunks", rows)


def insert_claims(ad_id: str, claims: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_claims rows via HTTP."""
    rows = []
    for claim in claims or []:
        rows.append(
            {"ad_id": ad_id}
            | {col: claim.get(col) for col in CLAIM_COLUMNS}
        )
    return _insert_many("ad_claims", rows)


def insert_supers(ad_id: str, supers: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_supers rows via HTTP."""
    rows = []
    for sup in supers or []:
        rows.append(
            {"ad_id": ad_id}
            | {col: sup.get(col) for col in SUPER_COLUMNS}
        )
    return _insert_many("ad_supers", rows)


def insert_storyboards(ad_id: str, shots: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """Insert ad_storyboards rows via HTTP."""
    rows = []
    for shot in shots or []:
        rows.append(
            {"ad_id": ad_id}
            | {col: shot.get(col) for col in STORYBOARD_COLUMNS}
        )
    return _insert_many("ad_storyboards", rows)


def insert_embedding_items(ad_id: str, items: Iterable[Mapping[str, Any]]) -> Sequence[str]:
    """
    Insert embedding_items rows via HTTP.

    Unlike the psycopg2 path, we can send embeddings as plain float lists and let
    PostgREST/pgvector handle casting into the vector type.
    """
    rows = []
    for item in items or []:
        embedding = item.get("embedding")
        if embedding is None:
            raise ValueError("Embedding item missing 'embedding' vector.")
        row = {
            "ad_id": ad_id,
            "chunk_id": item.get("chunk_id"),
            "segment_id": item.get("segment_id"),
            "claim_id": item.get("claim_id"),
            "super_id": item.get("super_id"),
            "storyboard_id": item.get("storyboard_id"),
            "item_type": item.get("item_type"),
            "text": item.get("text"),
            "embedding": embedding,
            "meta": item.get("meta") or {},
        }
        rows.append(row)

    return _insert_many("embedding_items", rows)


def hybrid_search(
    query_embedding: Sequence[float],
    query_text: str,
    limit: int = 50,
    item_types: Optional[Sequence[str]] = None,
) -> Sequence[Mapping[str, Any]]:
    """
    Call the match_embedding_items_hybrid Postgres function via Supabase RPC.
    """
    if limit <= 0:
        raise ValueError("limit must be positive for hybrid search.")

    search_types: MutableSequence[str] = list(item_types or DEFAULT_HYBRID_ITEM_TYPES)
    client = _get_client()
    payload = {
        "query_embedding": list(query_embedding),
        "query_text": query_text,
        "limit_count": int(limit),
        "item_types": search_types,
    }
    resp = client.rpc("match_embedding_items_hybrid", payload).execute()
    data = getattr(resp, "data", None) or []
    return data


__all__ = [
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
    client = _get_client()
    
    # Get all ads with their key fields
    resp = client.table("ads").select(
        "id, external_id, s3_key, extraction_version, impact_scores"
    ).order("created_at", desc=True).limit(limit).execute()
    
    ads = getattr(resp, "data", None) or []
    incomplete = []
    
    for ad in ads:
        ad_id = ad["id"]
        missing = []
        
        # Check v2 extraction
        if check_v2_extraction:
            version = ad.get("extraction_version") or "1.0"
            if version != "2.0":
                missing.append(f"extraction_v{version}")
        
        # Check impact scores
        if check_impact_scores:
            impact = ad.get("impact_scores")
            if not impact or not impact.get("overall_impact"):
                missing.append("impact_scores")
        
        # Check storyboard
        if check_storyboard:
            story_resp = client.table("ad_storyboards").select(
                "id", count="exact"
            ).eq("ad_id", ad_id).limit(1).execute()
            has_storyboard = bool(getattr(story_resp, "data", None) and len(story_resp.data) > 0)
            if not has_storyboard:
                missing.append("storyboard")
        
        # Check embeddings
        if check_embeddings:
            emb_resp = client.table("embedding_items").select(
                "id", count="exact"
            ).eq("ad_id", ad_id).limit(1).execute()
            has_embeddings = bool(getattr(emb_resp, "data", None) and len(emb_resp.data) > 0)
            if not has_embeddings:
                missing.append("embeddings")
        
        if missing:
            incomplete.append({
                "id": ad_id,
                "external_id": ad["external_id"],
                "s3_key": ad.get("s3_key"),
                "missing": missing,
            })
    
    logger.info(
        "Found %d/%d ads with incomplete data",
        len(incomplete), len(ads)
    )
    return incomplete


def delete_ad(ad_id: str) -> bool:
    """
    Delete an ad and all related child records.
    
    Deletes from: embedding_items, ad_storyboards, ad_supers, ad_claims, 
    ad_chunks, ad_segments, then ads.
    
    Returns True if successful.
    """
    client = _get_client()
    
    # Delete in reverse dependency order
    child_tables = [
        "embedding_items",
        "ad_storyboards", 
        "ad_supers",
        "ad_claims",
        "ad_chunks",
        "ad_segments",
    ]
    
    for table in child_tables:
        try:
            client.table(table).delete().eq("ad_id", ad_id).execute()
        except Exception as e:
            logger.warning("Failed to delete from %s: %s", table, e)
    
    # Delete the ad itself
    try:
        client.table("ads").delete().eq("id", ad_id).execute()
        logger.info("Deleted ad %s and all child records", ad_id)
        return True
    except Exception as e:
        logger.error("Failed to delete ad %s: %s", ad_id, e)
        return False


