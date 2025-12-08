"""
Backfill video_url column in ads table from CSV metadata.

This script:
1. Loads CSV metadata using the existing metadata_ingest module
2. Fetches all ads from the database (or only those missing video_url)
3. Matches ads to CSV entries by external_id (with fallbacks)
4. Updates video_url column for matched ads
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import tvads_rag
sys.path.insert(0, str(Path(__file__).parent.parent))

from tvads_rag.tvads_rag import metadata_ingest, db_backend
from tvads_rag.tvads_rag.config import get_db_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_all_ads(only_missing_url: bool = False):
    """Fetch all ads from database, optionally filtering to those missing video_url."""
    backend_mode = os.getenv("DB_BACKEND", "postgres")
    
    if backend_mode == "http":
        from tvads_rag.tvads_rag.supabase_db import _get_client
        client = _get_client()
        
        query = client.table("ads").select("id, external_id, video_url, s3_key")
        
        if only_missing_url:
            query = query.is_("video_url", "null")
        
        resp = query.execute()
        return resp.data or []
    else:
        # Postgres backend
        from tvads_rag.tvads_rag.db import get_connection
        from psycopg2.extras import RealDictCursor
        
        with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            if only_missing_url:
                query = "SELECT id, external_id, video_url, s3_key FROM ads WHERE video_url IS NULL"
            else:
                query = "SELECT id, external_id, video_url, s3_key FROM ads"
            
            cur.execute(query)
            return cur.fetchall()


def update_video_url(ad_id: str, video_url: str):
    """Update video_url for a specific ad."""
    backend_mode = os.getenv("DB_BACKEND", "postgres")
    
    if backend_mode == "http":
        from tvads_rag.tvads_rag.supabase_db import _get_client
        client = _get_client()
        
        resp = client.table("ads").update({"video_url": video_url}).eq("id", ad_id).execute()
        if resp.data:
            logger.debug("Updated video_url for ad %s", ad_id)
            return True
        return False
    else:
        # Postgres backend
        from tvads_rag.tvads_rag.db import get_connection
        
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE ads SET video_url = %s WHERE id = %s",
                (video_url, ad_id)
            )
            conn.commit()
            if cur.rowcount > 0:
                logger.debug("Updated video_url for ad %s", ad_id)
                return True
            return False


def find_video_url_for_ad(ad: dict, metadata_index: metadata_ingest.MetadataIndex) -> str | None:
    """
    Find video_url for an ad by matching against CSV metadata.
    
    Tries multiple matching strategies:
    1. Match by external_id (primary)
    2. Match by record_id (if external_id looks like a number)
    3. Match by movie_filename (if external_id starts with "TA")
    """
    external_id = ad.get("external_id")
    if not external_id:
        return None
    
    # Try direct match by external_id
    entry = metadata_index.get(external_id)
    if entry and entry.video_url:
        return entry.video_url
    
    # Try matching by record_id if external_id is numeric
    try:
        record_id = str(int(external_id.replace("TA", "")))
        entry = metadata_index.get(record_id)
        if entry and entry.video_url:
            logger.debug("Matched %s via record_id %s", external_id, record_id)
            return entry.video_url
    except (ValueError, AttributeError):
        pass
    
    # Try matching by movie_filename if external_id starts with "TA"
    if external_id.startswith("TA"):
        # Try without "TA" prefix
        try:
            numeric_part = external_id.replace("TA", "")
            entry = metadata_index.get(numeric_part)
            if entry and entry.video_url:
                logger.debug("Matched %s via numeric part %s", external_id, numeric_part)
                return entry.video_url
        except (ValueError, AttributeError):
            pass
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Backfill video_url column from CSV metadata"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to CSV metadata file (e.g., 'TELLY+ADS (2).csv')"
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only update ads that currently have NULL video_url"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without actually updating"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of ads to process (for testing)"
    )
    
    args = parser.parse_args()
    
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return 1
    
    logger.info("Loading CSV metadata from %s...", csv_path)
    try:
        metadata_index = metadata_ingest.load_metadata(str(csv_path))
        logger.info("Loaded %d metadata entries", len(metadata_index.entries))
    except Exception as e:
        logger.error("Failed to load CSV metadata: %s", e)
        return 1
    
    logger.info("Fetching ads from database (only_missing=%s)...", args.only_missing)
    ads = get_all_ads(only_missing_url=args.only_missing)
    
    if args.limit:
        ads = ads[:args.limit]
        logger.info("Limited to first %d ads", args.limit)
    
    logger.info("Found %d ads to process", len(ads))
    
    if not ads:
        logger.info("No ads to process!")
        return 0
    
    matched = 0
    updated = 0
    skipped = 0
    failed = 0
    
    for ad in ads:
        ad_id = ad.get("id")
        external_id = ad.get("external_id")
        current_url = ad.get("video_url")
        
        if not external_id:
            logger.warning("Skipping ad %s (no external_id)", ad_id)
            skipped += 1
            continue
        
        # Find video_url from CSV
        video_url = find_video_url_for_ad(ad, metadata_index)
        
        if not video_url:
            logger.debug("No video_url found in CSV for %s", external_id)
            skipped += 1
            continue
        
        matched += 1
        
        # Skip if URL already matches
        if current_url == video_url:
            logger.debug("Ad %s already has correct video_url", external_id)
            skipped += 1
            continue
        
        if args.dry_run:
            logger.info(
                "Would update %s (%s): %s -> %s",
                external_id, ad_id, current_url or "(NULL)", video_url
            )
            updated += 1
        else:
            try:
                if update_video_url(ad_id, video_url):
                    logger.info(
                        "Updated %s (%s): %s",
                        external_id, ad_id, video_url[:80] + ("..." if len(video_url) > 80 else "")
                    )
                    updated += 1
                else:
                    logger.warning("Failed to update %s (no rows affected)", external_id)
                    failed += 1
            except Exception as e:
                logger.error("Failed to update %s: %s", external_id, e)
                failed += 1
    
    logger.info("=" * 80)
    logger.info("Backfill Summary:")
    logger.info("  Total ads processed: %d", len(ads))
    logger.info("  Matched in CSV: %d", matched)
    logger.info("  Updated: %d", updated)
    logger.info("  Skipped (no match/already set): %d", skipped)
    logger.info("  Failed: %d", failed)
    logger.info("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())






