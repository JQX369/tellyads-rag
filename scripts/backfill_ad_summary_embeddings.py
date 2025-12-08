#!/usr/bin/env python3
"""
Backfill ad_summary embeddings for existing ads.

This script:
1. Finds all ads that don't have an ad_summary embedding
2. Generates embedding text from one_line_summary or story_summary
3. Calls OpenAI to generate embeddings
4. Inserts into embedding_items with item_type='ad_summary'

Usage:
    python scripts/backfill_ad_summary_embeddings.py [--limit N] [--dry-run]

Environment:
    SUPABASE_DB_URL - PostgreSQL connection string
    OPENAI_API_KEY - OpenAI API key
"""

import argparse
import os
import sys
from typing import List, Dict, Any

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_values
from openai import OpenAI


def get_db_connection():
    """Get database connection."""
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("SUPABASE_DB_URL environment variable required")
    return psycopg2.connect(db_url)


def get_openai_client():
    """Get OpenAI client."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable required")
    return OpenAI(api_key=api_key)


def get_ads_without_embeddings(conn, limit: int = None) -> List[Dict[str, Any]]:
    """Get ads that don't have ad_summary embeddings."""
    with conn.cursor() as cur:
        query = """
            SELECT
                a.id,
                a.external_id,
                a.one_line_summary,
                a.story_summary,
                a.brand_name,
                a.product_name,
                a.objective,
                a.funnel_stage
            FROM ads a
            LEFT JOIN embedding_items ei ON ei.ad_id = a.id AND ei.item_type = 'ad_summary'
            WHERE ei.id IS NULL
            ORDER BY a.created_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def generate_embedding_text(ad: Dict[str, Any]) -> str:
    """Generate the text to embed for an ad."""
    # Use story_summary if available, otherwise one_line_summary
    summary = (ad.get("story_summary") or ad.get("one_line_summary") or "").strip()

    if not summary:
        # Fallback: construct from available fields
        parts = []
        if ad.get("brand_name"):
            parts.append(f"Brand: {ad['brand_name']}")
        if ad.get("product_name"):
            parts.append(f"Product: {ad['product_name']}")
        if ad.get("objective"):
            parts.append(f"Objective: {ad['objective']}")
        summary = ". ".join(parts) if parts else f"Ad {ad.get('external_id', 'unknown')}"

    return summary


def generate_embeddings_batch(client: OpenAI, texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=texts,
        dimensions=1536
    )
    return [item.embedding for item in response.data]


def insert_embeddings(conn, items: List[Dict[str, Any]]):
    """Insert embedding items into database."""
    with conn.cursor() as cur:
        # Prepare data for bulk insert
        values = [
            (
                item["ad_id"],
                "ad_summary",
                item["text"],
                item["embedding"],
                "{}"  # empty meta
            )
            for item in items
        ]

        execute_values(
            cur,
            """
            INSERT INTO embedding_items (ad_id, item_type, text, embedding, meta)
            VALUES %s
            ON CONFLICT DO NOTHING
            """,
            values,
            template="(%s, %s, %s, %s::vector, %s::jsonb)"
        )

        conn.commit()
        return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description="Backfill ad_summary embeddings")
    parser.add_argument("--limit", type=int, help="Limit number of ads to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't insert, just show what would be done")
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size for OpenAI API calls")
    args = parser.parse_args()

    print("[*] Backfill ad_summary embeddings")
    print("=" * 50)

    conn = get_db_connection()
    openai_client = get_openai_client()

    # Get ads without embeddings
    print("\n[*] Finding ads without embeddings...")
    ads = get_ads_without_embeddings(conn, args.limit)
    print(f"    Found {len(ads)} ads without ad_summary embeddings")

    if not ads:
        print("\n[OK] All ads already have embeddings!")
        return

    if args.dry_run:
        print("\n[DRY RUN] Would process these ads:")
        for ad in ads[:10]:
            text = generate_embedding_text(ad)
            print(f"    - {ad['external_id']}: {text[:60]}...")
        if len(ads) > 10:
            print(f"    ... and {len(ads) - 10} more")
        return

    # Process in batches
    total_inserted = 0
    batch_size = args.batch_size

    for i in range(0, len(ads), batch_size):
        batch = ads[i:i + batch_size]
        print(f"\n[*] Processing batch {i // batch_size + 1} ({len(batch)} ads)...")

        # Generate texts
        texts = [generate_embedding_text(ad) for ad in batch]

        # Get embeddings from OpenAI
        print(f"    Generating embeddings...")
        embeddings = generate_embeddings_batch(openai_client, texts)

        # Prepare items for insertion
        items = [
            {
                "ad_id": ad["id"],
                "text": text,
                "embedding": f"[{','.join(map(str, emb))}]"
            }
            for ad, text, emb in zip(batch, texts, embeddings)
        ]

        # Insert into database
        print(f"    Inserting into database...")
        inserted = insert_embeddings(conn, items)
        total_inserted += inserted
        print(f"    [OK] Inserted {inserted} embeddings")

    print("\n" + "=" * 50)
    print(f"[OK] Done! Inserted {total_inserted} ad_summary embeddings")

    # Verify
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM embedding_items WHERE item_type = 'ad_summary'")
        count = cur.fetchone()[0]
        print(f"[*] Total ad_summary embeddings: {count}")

    conn.close()


if __name__ == "__main__":
    main()
