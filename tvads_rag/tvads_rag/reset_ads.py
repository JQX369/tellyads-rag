"""
CLI utility to reset (delete) ingested ads from the database.

Usage:
    python -m tvads_rag.tvads_rag.reset_ads --mode=lastN --n=3
    python -m tvads_rag.tvads_rag.reset_ads --mode=all

All child records (chunks, segments, claims, supers, storyboards, embeddings)
are automatically deleted via CASCADE foreign keys.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tvads_rag.reset_ads")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset (delete) ingested ads from the database."
    )
    parser.add_argument(
        "--mode",
        choices=["lastN", "all"],
        required=True,
        help="Reset mode: 'lastN' to delete last N ads, 'all' to delete all ads.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=3,
        help="Number of ads to delete when mode=lastN (default: 3).",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting.",
    )
    return parser.parse_args()


def _get_ads_to_delete_http(mode: str, n: int) -> List[dict]:
    """Get ads to delete using Supabase HTTP client."""
    from .supabase_db import _get_client
    
    client = _get_client()
    
    if mode == "all":
        response = client.table("ads").select("id, external_id, brand_name, created_at").order(
            "created_at", desc=True
        ).execute()
    else:
        response = client.table("ads").select("id, external_id, brand_name, created_at").order(
            "created_at", desc=True
        ).limit(n).execute()
    
    return response.data or []


def _get_ads_to_delete_postgres(mode: str, n: int) -> List[dict]:
    """Get ads to delete using direct Postgres connection."""
    from .db import get_connection
    
    with get_connection() as conn, conn.cursor() as cur:
        if mode == "all":
            cur.execute("""
                SELECT id, external_id, brand_name, created_at
                FROM ads
                ORDER BY created_at DESC
            """)
        else:
            cur.execute("""
                SELECT id, external_id, brand_name, created_at
                FROM ads
                ORDER BY created_at DESC
                LIMIT %s
            """, (n,))
        
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def _delete_ads_http(ad_ids: List[str]) -> int:
    """Delete ads using Supabase HTTP client. Returns count deleted."""
    from .supabase_db import _get_client
    
    client = _get_client()
    deleted = 0
    
    for ad_id in ad_ids:
        try:
            client.table("ads").delete().eq("id", ad_id).execute()
            deleted += 1
            logger.info("Deleted ad %s", ad_id)
        except Exception as e:
            logger.error("Failed to delete ad %s: %s", ad_id, e)
    
    return deleted


def _delete_ads_postgres(ad_ids: List[str]) -> int:
    """Delete ads using direct Postgres connection. Returns count deleted."""
    from .db import get_connection
    
    with get_connection() as conn, conn.cursor() as cur:
        for ad_id in ad_ids:
            try:
                cur.execute("DELETE FROM ads WHERE id = %s", (ad_id,))
                logger.info("Deleted ad %s", ad_id)
            except Exception as e:
                logger.error("Failed to delete ad %s: %s", ad_id, e)
        
        conn.commit()
    
    return len(ad_ids)


def get_ads_to_delete(mode: str, n: int) -> List[dict]:
    """Get list of ads that would be deleted."""
    backend = os.getenv("DB_BACKEND", "postgres")
    
    if backend == "http":
        return _get_ads_to_delete_http(mode, n)
    else:
        return _get_ads_to_delete_postgres(mode, n)


def delete_ads(ad_ids: List[str]) -> int:
    """Delete ads by ID. Returns count deleted."""
    backend = os.getenv("DB_BACKEND", "postgres")
    
    if backend == "http":
        return _delete_ads_http(ad_ids)
    else:
        return _delete_ads_postgres(ad_ids)


def main() -> None:
    args = _parse_args()
    
    backend = os.getenv("DB_BACKEND", "postgres")
    logger.info("DB backend: %s", backend)
    logger.info("Mode: %s", args.mode)
    if args.mode == "lastN":
        logger.info("N: %d", args.n)
    
    # Get ads to delete
    ads = get_ads_to_delete(args.mode, args.n)
    
    if not ads:
        logger.info("No ads found to delete.")
        return
    
    # Display what will be deleted
    logger.info("=" * 60)
    logger.info("Ads to be deleted (%d total):", len(ads))
    logger.info("=" * 60)
    for ad in ads:
        logger.info(
            "  %s | %s | %s | created: %s",
            ad.get("id", "?")[:8] + "...",
            ad.get("external_id", "N/A"),
            ad.get("brand_name", "Unknown"),
            ad.get("created_at", "N/A"),
        )
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN - No ads were deleted.")
        return
    
    # Confirmation
    if not args.yes:
        print(f"\n⚠️  This will DELETE {len(ads)} ads and ALL their data (chunks, segments, claims, supers, storyboards, embeddings).")
        print("This action CANNOT be undone.\n")
        confirm = input("Type 'DELETE' to confirm: ").strip()
        if confirm != "DELETE":
            logger.info("Aborted by user.")
            return
    
    # Perform deletion
    ad_ids = [ad["id"] for ad in ads]
    deleted = delete_ads(ad_ids)
    
    logger.info("=" * 60)
    logger.info("Deleted %d/%d ads successfully.", deleted, len(ads))
    logger.info("=" * 60)


if __name__ == "__main__":
    main()








