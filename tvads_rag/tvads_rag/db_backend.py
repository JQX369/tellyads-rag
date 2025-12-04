"""
DB backend router.

This module presents the same interface as `db.py` but dispatches to either
the direct Postgres backend (`db`) or the Supabase HTTP backend
(`supabase_db`) based on the DB_BACKEND environment variable.

DB_BACKEND:
    - "postgres" (default): use psycopg2 + SUPABASE_DB_URL
    - "http": use Supabase Python client over HTTPS
"""

from __future__ import annotations

import logging
import os

from . import db as _db_pg

logger = logging.getLogger(__name__)

# Lazy import of supabase_db to avoid errors if supabase package isn't installed
_db_http = None
_impl = None


def _select_backend():
    """Select backend based on DB_BACKEND env var, with fallback to postgres if http fails."""
    global _impl
    if _impl is not None:
        return _impl
    
    mode = (os.getenv("DB_BACKEND") or "postgres").lower()
    
    if mode == "http":
        try:
            from . import supabase_db
            _impl = supabase_db
            logger.info("Using Supabase HTTP backend")
            return _impl
        except (RuntimeError, ImportError) as e:
            if "supabase" in str(e).lower() or isinstance(e, ImportError):
                logger.warning(
                    "DB_BACKEND=http requested but supabase package not available. "
                    "Falling back to postgres backend. Install 'supabase' package to use HTTP backend."
                )
                # Fall back to postgres backend
                _impl = _db_pg
                return _impl
            raise
    
    # Default to postgres backend
    _impl = _db_pg
    return _impl


# Lazy wrapper functions that select backend on first call
def _get_impl():
    """Get the selected backend implementation."""
    return _select_backend()


def get_connection():
    """Get database connection (postgres backend only)."""
    impl = _get_impl()
    return getattr(impl, "get_connection", None)


def ad_exists(*, external_id=None, s3_key=None):
    """Check if ad exists."""
    return _get_impl().ad_exists(external_id=external_id, s3_key=s3_key)


def insert_ad(ad_data):
    """Insert ad record."""
    return _get_impl().insert_ad(ad_data)


def insert_segments(ad_id, segments):
    """Insert ad segments."""
    return _get_impl().insert_segments(ad_id, segments)


def insert_chunks(ad_id, chunks):
    """Insert ad chunks."""
    return _get_impl().insert_chunks(ad_id, chunks)


def insert_claims(ad_id, claims):
    """Insert ad claims."""
    return _get_impl().insert_claims(ad_id, claims)


def insert_supers(ad_id, supers):
    """Insert ad supers."""
    return _get_impl().insert_supers(ad_id, supers)


def insert_storyboards(ad_id, storyboards):
    """Insert ad storyboards."""
    return _get_impl().insert_storyboards(ad_id, storyboards)


def insert_embedding_items(ad_id, items):
    """Insert embedding items."""
    return _get_impl().insert_embedding_items(ad_id, items)


def hybrid_search(query_embedding, query_text, limit=50, item_types=None):
    """Run hybrid search."""
    return _get_impl().hybrid_search(query_embedding, query_text, limit, item_types)


def find_incomplete_ads(
    check_storyboard=True,
    check_v2_extraction=True,
    check_impact_scores=True,
    check_embeddings=True,
    limit=100
):
    """Find ads with incomplete data."""
    return _get_impl().find_incomplete_ads(
        check_storyboard=check_storyboard,
        check_v2_extraction=check_v2_extraction,
        check_impact_scores=check_impact_scores,
        check_embeddings=check_embeddings,
        limit=limit,
    )


def delete_ad(ad_id):
    """Delete an ad and all child records."""
    return _get_impl().delete_ad(ad_id)


def update_processing_notes(ad_id, notes):
    """Update processing notes for an ad (to track errors, warnings, etc.)."""
    return _get_impl().update_processing_notes(ad_id, notes)


def update_visual_objects(ad_id, visual_objects):
    """Update visual_objects field for an ad (object detection results)."""
    return _get_impl().update_visual_objects(ad_id, visual_objects)


def update_video_analytics(ad_id, visual_physics, spatial_telemetry, color_psychology):
    """Update video analytics fields for an ad (visual physics, spatial, color)."""
    return _get_impl().update_video_analytics(ad_id, visual_physics, spatial_telemetry, color_psychology)


def update_physics_data(ad_id, physics_data):
    """Update unified physics_data field for an ad (from PhysicsExtractor)."""
    return _get_impl().update_physics_data(ad_id, physics_data)


def update_toxicity_report(ad_id, toxicity_report):
    """Update toxicity_report field for an ad (toxicity scoring results)."""
    return _get_impl().update_toxicity_report(ad_id, toxicity_report)


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
    "update_processing_notes",
    "update_visual_objects",
    "update_video_analytics",
    "update_physics_data",
    "update_toxicity_report",
]


