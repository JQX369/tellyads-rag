# TellyAds Go-Live Pack: Staging → Production

**Date:** 2025-12-04
**Version:** 1.0.0

---

## Table of Contents

1. [Staging → Prod Checklist](#1-staging--prod-checklist)
2. [Excel/Wix Import Implementation](#2-excelwix-import-implementation)
3. [URLs + Redirects (SEO Continuity)](#3-urls--redirects-seo-continuity)
4. [Frontend Wiring](#4-frontend-wiring)
5. [Ops + Rollback Plan](#5-ops--rollback-plan)
6. [Done Acceptance Criteria](#6-done-acceptance-criteria)

---

## 1. Staging → Prod Checklist

### Phase 1: Database Migrations

#### Step 1.1: Backup Production Database

```bash
# STOP/GO: Must complete backup before proceeding
pg_dump "$SUPABASE_DB_URL" > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -la backup_*.sql
```

**STOP/GO Gate:** ✓ Backup file exists and has reasonable size (>1MB if data exists)

#### Step 1.2: Apply Editorial + Feedback Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback.sql
```

**Expected output:** Tables created, indexes created, no errors

#### Step 1.3: Verify Editorial Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback_verify.sql
```

**STOP/GO Gate:** All verification queries return `✓ PASS` or `EXISTS`

#### Step 1.4: Apply Micro-Reasons Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons.sql
```

#### Step 1.5: Verify Micro-Reasons Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons_verify.sql
```

**STOP/GO Gate:** All tests pass, `ad_like_reasons` table exists

#### Step 1.6: Apply Scoring V2 Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2.sql
```

#### Step 1.7: Verify Scoring V2 Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2_verify.sql
```

**STOP/GO Gate:**
- `ai_score`, `user_score`, `final_score`, `confidence_weight` columns exist
- Functions `fn_compute_ai_score`, `fn_compute_user_score`, `fn_compute_confidence_weight` exist
- Anti-gaming tests pass (distinct sessions counted, not raw rows)

---

### Phase 2: Backend Deployment

#### Step 2.1: Set Environment Variables

```bash
# Required for admin endpoints
export ADMIN_API_KEY=$(openssl rand -hex 32)

# Add to deployment environment (Railway/Render/Fly.io)
echo "ADMIN_API_KEY=$ADMIN_API_KEY"
```

#### Step 2.2: Deploy Backend

```bash
# Railway
railway up

# Or Render: Push to git, auto-deploys

# Or manual
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**STOP/GO Gate:** `GET /api/status` returns `{"status": "ok"}`

---

### Phase 3: Smoke Tests

Run these against production API after deployment:

#### Test 3.1: SEO Gating (404 for unpublished)

```bash
# Should return 404 (no editorial record exists yet)
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/advert/test-brand/nonexistent-slug"
# Expected: 404
```

#### Test 3.2: Like Toggle

```bash
# Get any ad external_id first
EXTERNAL_ID=$(curl -s "$API_URL/api/recent?limit=1" | jq -r '.[0].external_id')

# Toggle like
curl -X POST "$API_URL/api/ads/$EXTERNAL_ID/like" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "smoke-test-session"}'
# Expected: {"is_liked": true}

# Toggle again (unlike)
curl -X POST "$API_URL/api/ads/$EXTERNAL_ID/like" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "smoke-test-session"}'
# Expected: {"is_liked": false}
```

#### Test 3.3: View Rate Limiting

```bash
# Hit view endpoint 15 times rapidly
for i in {1..15}; do
  curl -X POST "$API_URL/api/ads/$EXTERNAL_ID/view" \
    -H "Content-Type: application/json" \
    -d '{"session_id": "rate-limit-test"}'
done
# Expected: First 10 succeed, remaining return 429
```

#### Test 3.4: Reason Threshold

```bash
# Get feedback for an ad (should have empty reason_counts if <10 distinct sessions)
curl -s "$API_URL/api/ads/$EXTERNAL_ID/feedback" | jq '.reason_threshold_met'
# Expected: false (no reasons yet)
```

#### Test 3.5: Tag Moderation

```bash
# Submit a tag
curl -X POST "$API_URL/api/ads/$EXTERNAL_ID/tag" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "tag-test", "tag": "funny"}'
# Expected: 201 with tag_id

# Approve tag (requires ADMIN_API_KEY)
curl -X POST "$API_URL/api/admin/tags/$TAG_ID/moderate" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"action": "approve"}'
# Expected: {"status": "approved"}
```

#### Test 3.6: Scoring Behavior

```bash
# Check feedback includes new score components
curl -s "$API_URL/api/ads/$EXTERNAL_ID/feedback" | jq '{ai_score, user_score, confidence_weight, final_score}'
# Expected: All fields present, ai_score ~50 (default), confidence_weight ~0 (low engagement)
```

**STOP/GO Gate:** All 6 smoke tests pass

---

## 2. Excel/Wix Import Implementation

### 2A: Import Data Schema

**Minimum required columns:**

| Column | Required | Description |
|--------|----------|-------------|
| `legacy_url` | Yes | Original Wix URL (for matching + redirects) |
| `title` | Yes | Editorial headline |
| `description` | No | Editorial summary |
| `brand` | Yes | Brand name (will be slugified) |
| `year` | No | Year of ad |
| `external_id` | No | TellyAds external_id if known |
| `wix_item_id` | No | Original Wix CMS ID |
| `publish_status` | No | draft/published/archived |
| `publish_date` | No | Original publish date |
| `curated_tags` | No | Comma-separated tags |

**Example Excel structure:**

```
legacy_url                                      | title              | brand      | year | external_id
/ads/specsavers/clown-surprise                  | Clown Surprise Ad  | Specsavers | 2023 | TA12345
/adverts/john-lewis/christmas-2022             | Christmas 2022     | John Lewis | 2022 |
https://wixsite.com/ad-detail/item/abc123      | Summer Sale        | Aldi       | 2024 | TA67890
```

### 2B: Import Script

**File:** `scripts/import_editorial.py`

```python
#!/usr/bin/env python3
"""
TellyAds Editorial Import Script
Import Wix/Excel data into ad_editorial table

Usage:
  python scripts/import_editorial.py --input data/wix.xlsx --dry-run
  python scripts/import_editorial.py --input data/wix.xlsx --apply
  python scripts/import_editorial.py --input data/wix.xlsx --apply --force-overwrite
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse

# Support both xlsx and csv
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

import psycopg2
from psycopg2.extras import RealDictCursor

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Column name mappings (flexible to handle different Excel exports)
COLUMN_ALIASES = {
    'legacy_url': ['legacy_url', 'url', 'wix_url', 'original_url', 'link'],
    'title': ['title', 'headline', 'name', 'ad_title', 'editorial_title'],
    'description': ['description', 'summary', 'editorial_summary', 'body', 'content'],
    'brand': ['brand', 'brand_name', 'advertiser', 'company'],
    'year': ['year', 'ad_year', 'release_year'],
    'external_id': ['external_id', 'ta_id', 'tellyads_id', 'id'],
    'wix_item_id': ['wix_item_id', 'wix_id', 'cms_id', '_id'],
    'publish_status': ['publish_status', 'status', 'state'],
    'publish_date': ['publish_date', 'published_at', 'date_published', 'original_publish_date'],
    'curated_tags': ['curated_tags', 'tags', 'categories'],
}

# --------------------------------------------------------------------------
# Slugify Helper
# --------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to URL-safe slug"""
    if not text:
        return ''
    # Lowercase
    slug = text.lower()
    # Replace special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)
    # Replace whitespace with hyphens
    slug = re.sub(r'[-\s]+', '-', slug)
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def extract_slug_from_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract brand_slug and slug from legacy Wix URL

    Patterns supported:
    - /ads/{brand}/{slug}
    - /adverts/{brand}/{slug}
    - /ad-detail/{brand}/{slug}
    - /collection/{brand}/{slug}
    - /{brand}/{slug} (2-segment paths)
    - Full URLs with paths

    Returns: (brand_slug, slug) or (None, None) if cannot parse
    """
    if not url:
        return None, None

    # Parse URL
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    if not path:
        return None, None

    segments = path.split('/')

    # Remove known prefixes
    prefixes_to_strip = ['ads', 'adverts', 'ad-detail', 'advert', 'collection', 'item']
    while segments and segments[0].lower() in prefixes_to_strip:
        segments = segments[1:]

    # Need at least 2 segments: brand/slug
    if len(segments) >= 2:
        brand_slug = slugify(segments[0])
        slug = slugify(segments[1])
        return brand_slug, slug
    elif len(segments) == 1:
        # Only slug, no brand - will need manual matching
        return None, slugify(segments[0])

    return None, None


# --------------------------------------------------------------------------
# Data Loading
# --------------------------------------------------------------------------

def load_excel(file_path: str) -> List[Dict]:
    """Load data from Excel file"""
    if not HAS_OPENPYXL:
        raise ImportError("openpyxl required for Excel files: pip install openpyxl")

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active

    # Get headers from first row
    headers = []
    for cell in ws[1]:
        headers.append(str(cell.value).lower().strip() if cell.value else '')

    # Map headers to canonical names
    header_map = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for i, h in enumerate(headers):
            if h in aliases:
                header_map[i] = canonical
                break

    # Load rows
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        record = {}
        for i, value in enumerate(row):
            if i in header_map:
                record[header_map[i]] = value
        if any(record.values()):  # Skip empty rows
            rows.append(record)

    return rows


def load_csv(file_path: str) -> List[Dict]:
    """Load data from CSV file"""
    rows = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        # Map headers to canonical names
        header_map = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            for h in reader.fieldnames:
                if h.lower().strip() in aliases:
                    header_map[h] = canonical
                    break

        for row in reader:
            record = {}
            for orig_name, value in row.items():
                if orig_name in header_map:
                    record[header_map[orig_name]] = value
            if any(record.values()):
                rows.append(record)

    return rows


def load_data(file_path: str) -> List[Dict]:
    """Load data from Excel or CSV"""
    ext = Path(file_path).suffix.lower()
    if ext in ['.xlsx', '.xls']:
        return load_excel(file_path)
    elif ext == '.csv':
        return load_csv(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# --------------------------------------------------------------------------
# Matching Logic
# --------------------------------------------------------------------------

def match_to_ad(conn, record: Dict) -> Tuple[Optional[str], str]:
    """
    Match import record to existing ad in database

    Priority:
    1. external_id exact match
    2. wix_item_id match (if already imported)
    3. brand + year + duration (fuzzy)
    4. Manual review bucket

    Returns: (ad_id, match_method) or (None, 'unmatched')
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Priority 1: external_id
        external_id = record.get('external_id')
        if external_id:
            # Normalize: ensure TA prefix
            if not str(external_id).upper().startswith('TA'):
                external_id = f"TA{external_id}"

            cur.execute("SELECT id FROM ads WHERE external_id = %s", (external_id,))
            result = cur.fetchone()
            if result:
                return str(result['id']), 'external_id'

        # Priority 2: wix_item_id (check if already imported)
        wix_id = record.get('wix_item_id')
        if wix_id:
            cur.execute("SELECT ad_id FROM ad_editorial WHERE wix_item_id = %s", (wix_id,))
            result = cur.fetchone()
            if result:
                return str(result['ad_id']), 'wix_item_id_existing'

        # Priority 3: Brand + Year + Title fuzzy match
        brand = record.get('brand')
        year = record.get('year')
        title = record.get('title')

        if brand and title:
            # Fuzzy match on brand_name and one_line_summary
            cur.execute("""
                SELECT id, external_id, brand_name, one_line_summary, year
                FROM ads
                WHERE LOWER(brand_name) = LOWER(%s)
                  AND (%s IS NULL OR year = %s)
                ORDER BY created_at DESC
                LIMIT 10
            """, (brand, year, year))

            candidates = cur.fetchall()
            if len(candidates) == 1:
                return str(candidates[0]['id']), 'brand_year_unique'
            elif len(candidates) > 1:
                # Multiple matches - needs manual review
                return None, 'multiple_matches'

        return None, 'unmatched'


# --------------------------------------------------------------------------
# Import Logic
# --------------------------------------------------------------------------

def import_record(conn, record: Dict, ad_id: str, force_overwrite: bool = False) -> Dict:
    """
    Import single record into ad_editorial

    Returns result dict with status
    """
    # Parse legacy URL for slug
    legacy_url = record.get('legacy_url', '')
    brand_slug_from_url, slug_from_url = extract_slug_from_url(legacy_url)

    # Build brand_slug
    brand = record.get('brand', '')
    brand_slug = brand_slug_from_url or slugify(brand)

    if not brand_slug:
        return {'status': 'error', 'reason': 'Cannot determine brand_slug'}

    # Build slug
    title = record.get('title', '')
    slug = slug_from_url or slugify(title)

    if not slug:
        return {'status': 'error', 'reason': 'Cannot determine slug'}

    # Parse other fields
    year = record.get('year')
    if year:
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = None

    publish_status = record.get('publish_status', 'draft')
    if publish_status not in ('draft', 'published', 'archived'):
        publish_status = 'draft'

    publish_date = record.get('publish_date')
    if publish_date and isinstance(publish_date, str):
        try:
            publish_date = datetime.fromisoformat(publish_date.replace('Z', '+00:00'))
        except ValueError:
            publish_date = None

    curated_tags = record.get('curated_tags', '')
    if isinstance(curated_tags, str):
        curated_tags = [t.strip() for t in curated_tags.split(',') if t.strip()]
    elif not curated_tags:
        curated_tags = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check for existing editorial record
        cur.execute("""
            SELECT id, brand_slug, slug, headline, editorial_summary
            FROM ad_editorial
            WHERE ad_id = %s
        """, (ad_id,))
        existing = cur.fetchone()

        if existing:
            if not force_overwrite:
                # Don't overwrite existing human content
                return {
                    'status': 'skipped',
                    'reason': 'Editorial exists (use --force-overwrite)',
                    'existing_slug': f"{existing['brand_slug']}/{existing['slug']}"
                }

            # Update existing record
            cur.execute("""
                UPDATE ad_editorial SET
                    brand_slug = COALESCE(%s, brand_slug),
                    slug = COALESCE(%s, slug),
                    headline = COALESCE(%s, headline),
                    editorial_summary = COALESCE(%s, editorial_summary),
                    curated_tags = CASE WHEN %s::text[] != '{}' THEN %s ELSE curated_tags END,
                    wix_item_id = COALESCE(%s, wix_item_id),
                    original_publish_date = COALESCE(%s, original_publish_date),
                    override_year = COALESCE(%s, override_year),
                    status = %s,
                    updated_at = now()
                WHERE ad_id = %s
                RETURNING id
            """, (
                brand_slug, slug,
                record.get('title'), record.get('description'),
                curated_tags, curated_tags,
                record.get('wix_item_id'), publish_date, year,
                publish_status,
                ad_id
            ))
            return {'status': 'updated', 'slug': f"{brand_slug}/{slug}"}

        else:
            # Check for slug conflict
            cur.execute("""
                SELECT id FROM ad_editorial
                WHERE brand_slug = %s AND slug = %s
            """, (brand_slug, slug))
            if cur.fetchone():
                # Append suffix to make unique
                base_slug = slug
                for i in range(2, 100):
                    test_slug = f"{base_slug}-{i}"
                    cur.execute("""
                        SELECT id FROM ad_editorial
                        WHERE brand_slug = %s AND slug = %s
                    """, (brand_slug, test_slug))
                    if not cur.fetchone():
                        slug = test_slug
                        break
                else:
                    return {'status': 'error', 'reason': f'Slug conflict: {brand_slug}/{base_slug}'}

            # Insert new record
            cur.execute("""
                INSERT INTO ad_editorial (
                    ad_id, brand_slug, slug,
                    headline, editorial_summary, curated_tags,
                    wix_item_id, original_publish_date,
                    override_year, status
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s
                )
                RETURNING id
            """, (
                ad_id, brand_slug, slug,
                record.get('title'), record.get('description'), curated_tags,
                record.get('wix_item_id'), publish_date,
                year, publish_status
            ))
            return {'status': 'inserted', 'slug': f"{brand_slug}/{slug}"}


# --------------------------------------------------------------------------
# Main Import Flow
# --------------------------------------------------------------------------

def run_import(file_path: str, db_url: str, dry_run: bool = True, force_overwrite: bool = False):
    """
    Main import function
    """
    print(f"Loading data from: {file_path}")
    records = load_data(file_path)
    print(f"Loaded {len(records)} records")

    conn = psycopg2.connect(db_url)

    results = {
        'matched': [],
        'unmatched': [],
        'conflicts': [],
        'inserted': [],
        'updated': [],
        'skipped': [],
        'errors': [],
    }

    for i, record in enumerate(records):
        row_num = i + 2  # Excel row number (1-indexed + header)

        # Match to ad
        ad_id, match_method = match_to_ad(conn, record)

        record_info = {
            'row': row_num,
            'legacy_url': record.get('legacy_url', ''),
            'title': record.get('title', ''),
            'brand': record.get('brand', ''),
            'match_method': match_method,
        }

        if not ad_id:
            if match_method == 'multiple_matches':
                results['conflicts'].append(record_info)
            else:
                results['unmatched'].append(record_info)
            continue

        record_info['ad_id'] = ad_id
        results['matched'].append(record_info)

        if not dry_run:
            # Actually import
            import_result = import_record(conn, record, ad_id, force_overwrite)
            record_info.update(import_result)

            if import_result['status'] == 'inserted':
                results['inserted'].append(record_info)
            elif import_result['status'] == 'updated':
                results['updated'].append(record_info)
            elif import_result['status'] == 'skipped':
                results['skipped'].append(record_info)
            elif import_result['status'] == 'error':
                results['errors'].append(record_info)

    if not dry_run:
        conn.commit()
    conn.close()

    # Output results
    output_dir = Path(file_path).parent
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Write CSVs
    for name in ['matched', 'unmatched', 'conflicts']:
        if results[name]:
            out_file = output_dir / f"{name}_{timestamp}.csv"
            with open(out_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=results[name][0].keys())
                writer.writeheader()
                writer.writerows(results[name])
            print(f"Wrote: {out_file}")

    # Write summary JSON
    summary = {
        'timestamp': timestamp,
        'input_file': str(file_path),
        'dry_run': dry_run,
        'force_overwrite': force_overwrite,
        'total_records': len(records),
        'matched_count': len(results['matched']),
        'unmatched_count': len(results['unmatched']),
        'conflicts_count': len(results['conflicts']),
        'inserted_count': len(results['inserted']),
        'updated_count': len(results['updated']),
        'skipped_count': len(results['skipped']),
        'error_count': len(results['errors']),
        'match_rate': len(results['matched']) / len(records) * 100 if records else 0,
    }

    summary_file = output_dir / f"import_summary_{timestamp}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote: {summary_file}")

    # Console summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"Total records:     {summary['total_records']}")
    print(f"Matched:           {summary['matched_count']} ({summary['match_rate']:.1f}%)")
    print(f"Unmatched:         {summary['unmatched_count']}")
    print(f"Conflicts:         {summary['conflicts_count']}")
    if not dry_run:
        print(f"Inserted:          {summary['inserted_count']}")
        print(f"Updated:           {summary['updated_count']}")
        print(f"Skipped:           {summary['skipped_count']}")
        print(f"Errors:            {summary['error_count']}")
    else:
        print("\n[DRY RUN - No changes made]")
    print("="*60)

    return summary


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Import Wix/Excel data into TellyAds editorial')
    parser.add_argument('--input', required=True, help='Path to Excel/CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--apply', action='store_true', help='Actually apply changes')
    parser.add_argument('--force-overwrite', action='store_true', help='Overwrite existing editorial')
    parser.add_argument('--db-url', default=None, help='Database URL (default: SUPABASE_DB_URL env)')

    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        args.dry_run = True
        print("Note: Running in dry-run mode (use --apply to write changes)")

    import os
    db_url = args.db_url or os.environ.get('SUPABASE_DB_URL')
    if not db_url:
        print("Error: Database URL required (--db-url or SUPABASE_DB_URL env)")
        sys.exit(1)

    run_import(
        file_path=args.input,
        db_url=db_url,
        dry_run=not args.apply,
        force_overwrite=args.force_overwrite
    )


if __name__ == '__main__':
    main()
```

### 2C: CLI Usage

```bash
# Preview import (no changes)
python scripts/import_editorial.py --input data/wix_export.xlsx --dry-run

# Apply import (creates new editorial records)
python scripts/import_editorial.py --input data/wix_export.xlsx --apply

# Force overwrite existing editorial (use with caution)
python scripts/import_editorial.py --input data/wix_export.xlsx --apply --force-overwrite
```

### 2D: SQL Helper Views for Manual Review

```sql
-- =============================================================================
-- IMPORT REVIEW QUERIES
-- Save as: tvads_rag/import_review_queries.sql
-- =============================================================================

-- 1. Unmatched editorial rows (imported but not linked to an ad)
SELECT
    e.id,
    e.brand_slug,
    e.slug,
    e.headline,
    e.wix_item_id,
    e.status
FROM ad_editorial e
WHERE e.ad_id IS NULL
ORDER BY e.created_at DESC;

-- 2. Duplicate slugs per brand
SELECT
    brand_slug,
    slug,
    COUNT(*) as duplicate_count,
    array_agg(ad_id) as ad_ids
FROM ad_editorial
GROUP BY brand_slug, slug
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- 3. Published ads missing editorial (need import or manual creation)
SELECT
    a.id,
    a.external_id,
    a.brand_name,
    a.one_line_summary,
    a.year,
    a.created_at
FROM ads a
LEFT JOIN ad_editorial e ON e.ad_id = a.id
WHERE e.id IS NULL
ORDER BY a.created_at DESC
LIMIT 100;

-- 4. Editorial rows not linked to an ad (orphans)
SELECT
    e.id,
    e.brand_slug,
    e.slug,
    e.headline,
    e.wix_item_id,
    e.created_at
FROM ad_editorial e
LEFT JOIN ads a ON a.id = e.ad_id
WHERE a.id IS NULL
ORDER BY e.created_at DESC;

-- 5. Import match statistics
SELECT
    (SELECT COUNT(*) FROM ads) as total_ads,
    (SELECT COUNT(*) FROM ad_editorial) as total_editorial,
    (SELECT COUNT(*) FROM ads a JOIN ad_editorial e ON e.ad_id = a.id) as matched,
    (SELECT COUNT(*) FROM ads a LEFT JOIN ad_editorial e ON e.ad_id = a.id WHERE e.id IS NULL) as ads_without_editorial,
    (SELECT COUNT(*) FROM ad_editorial WHERE status = 'published') as published_editorial,
    (SELECT COUNT(*) FROM ad_editorial WHERE status = 'draft') as draft_editorial;

-- 6. Legacy URL coverage (for redirect planning)
SELECT
    e.brand_slug,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE e.wix_item_id IS NOT NULL) as has_wix_id
FROM ad_editorial e
WHERE e.status = 'published'
GROUP BY e.brand_slug
ORDER BY count DESC;
```

---

## 3. URLs + Redirects (SEO Continuity)

### 3A: Add Legacy URL Column to ad_editorial

```sql
-- Add legacy_url column for redirect mapping
ALTER TABLE ad_editorial ADD COLUMN IF NOT EXISTS legacy_url text;

-- Index for fast redirect lookups
CREATE INDEX IF NOT EXISTS idx_ad_editorial_legacy_url
    ON ad_editorial(legacy_url)
    WHERE legacy_url IS NOT NULL;
```

### 3B: Legacy URL Resolver API Endpoint

Add to `backend/main.py`:

```python
@app.get("/api/resolve-legacy")
async def resolve_legacy_url(url: str):
    """
    Resolve legacy Wix URL to new canonical path

    GET /api/resolve-legacy?url=/ads/specsavers/clown-surprise
    Returns: {"canonical_path": "/advert/specsavers/clown-surprise", "external_id": "TA12345"}
    """
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Normalize URL
                normalized = url.strip().lower().rstrip('/')

                # Try exact match first
                cur.execute("""
                    SELECT e.brand_slug, e.slug, a.external_id
                    FROM ad_editorial e
                    JOIN ads a ON a.id = e.ad_id
                    WHERE e.legacy_url = %s
                      AND e.status = 'published'
                      AND e.is_hidden = false
                      AND (e.publish_date IS NULL OR e.publish_date <= NOW())
                """, (normalized,))

                result = cur.fetchone()
                if result:
                    return {
                        "canonical_path": f"/advert/{result['brand_slug']}/{result['slug']}",
                        "external_id": result['external_id'],
                        "status": "found"
                    }

                # Try pattern extraction as fallback
                # Parse URL for brand/slug
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path.strip('/')
                segments = path.split('/')

                # Remove known prefixes
                prefixes = ['ads', 'adverts', 'ad-detail', 'advert', 'collection', 'item']
                while segments and segments[0].lower() in prefixes:
                    segments = segments[1:]

                if len(segments) >= 2:
                    brand_slug = segments[0].lower()
                    slug = segments[1].lower()

                    cur.execute("""
                        SELECT e.brand_slug, e.slug, a.external_id
                        FROM ad_editorial e
                        JOIN ads a ON a.id = e.ad_id
                        WHERE LOWER(e.brand_slug) = %s
                          AND LOWER(e.slug) = %s
                          AND e.status = 'published'
                          AND e.is_hidden = false
                          AND (e.publish_date IS NULL OR e.publish_date <= NOW())
                    """, (brand_slug, slug))

                    result = cur.fetchone()
                    if result:
                        return {
                            "canonical_path": f"/advert/{result['brand_slug']}/{result['slug']}",
                            "external_id": result['external_id'],
                            "status": "found"
                        }

                # Not found - log for investigation
                logger.warning(f"Legacy URL not found: {url}")
                return {
                    "canonical_path": None,
                    "external_id": None,
                    "status": "not_found",
                    "original_url": url
                }

    except Exception as e:
        logger.error(f"Legacy URL resolution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 3C: Next.js Middleware for 301 Redirects

**File:** `frontend/middleware.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Legacy URL patterns to intercept
const LEGACY_PATTERNS = [
  /^\/ads\/([^\/]+)\/([^\/]+)\/?$/,           // /ads/{brand}/{slug}
  /^\/adverts\/([^\/]+)\/([^\/]+)\/?$/,       // /adverts/{brand}/{slug}
  /^\/ad-detail\/([^\/]+)\/([^\/]+)\/?$/,     // /ad-detail/{brand}/{slug}
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check if this matches a legacy pattern
  for (const pattern of LEGACY_PATTERNS) {
    if (pattern.test(pathname)) {
      try {
        // Resolve via API
        const resolveUrl = `${API_URL}/api/resolve-legacy?url=${encodeURIComponent(pathname)}`;
        const response = await fetch(resolveUrl, { next: { revalidate: 3600 } });
        const data = await response.json();

        if (data.status === 'found' && data.canonical_path) {
          // 301 Permanent Redirect
          return NextResponse.redirect(
            new URL(data.canonical_path, request.url),
            { status: 301 }
          );
        }
      } catch (error) {
        console.error('Legacy redirect resolution failed:', error);
      }

      // If not found, let it 404 naturally
      break;
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/ads/:path*',
    '/adverts/:path*',
    '/ad-detail/:path*',
  ],
};
```

### 3D: Vercel Redirects (Alternative Static Approach)

If you prefer static redirects (faster, no API call), generate a redirects file:

**Script:** `scripts/generate_redirects.py`

```python
#!/usr/bin/env python3
"""Generate static redirects file from database"""

import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def generate_vercel_redirects():
    conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT e.legacy_url, e.brand_slug, e.slug
            FROM ad_editorial e
            WHERE e.legacy_url IS NOT NULL
              AND e.status = 'published'
              AND e.is_hidden = false
        """)

        redirects = []
        for row in cur.fetchall():
            if row['legacy_url']:
                redirects.append({
                    "source": row['legacy_url'],
                    "destination": f"/advert/{row['brand_slug']}/{row['slug']}",
                    "permanent": True
                })

    conn.close()

    # Write to vercel.json format
    config = {
        "redirects": redirects
    }

    with open('frontend/vercel_redirects.json', 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Generated {len(redirects)} redirects")
    return redirects

if __name__ == '__main__':
    generate_vercel_redirects()
```

### 3E: Canonical Tags

**File:** `frontend/app/advert/[brand]/[slug]/page.tsx` (metadata)

```typescript
export async function generateMetadata({ params }) {
  const { brand, slug } = params;

  return {
    title: `${ad.headline || ad.one_line_summary} | TellyAds`,
    description: ad.summary,
    alternates: {
      canonical: `https://tellyads.com/advert/${brand}/${slug}`,
    },
    openGraph: {
      url: `https://tellyads.com/advert/${brand}/${slug}`,
      // ... other OG tags
    },
  };
}
```

### 3F: Dynamic Sitemap

Update `frontend/app/sitemap.ts`:

```typescript
import { MetadataRoute } from 'next';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://tellyads.com';
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Static routes
  const staticRoutes = ['', '/about', '/search', '/latest', '/brands'].map((route) => ({
    url: `${BASE_URL}${route}`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: route === '' ? 1 : 0.8,
  }));

  // Dynamic editorial routes
  let editorialRoutes: MetadataRoute.Sitemap = [];

  try {
    const response = await fetch(`${API_URL}/api/editorial/sitemap`, {
      next: { revalidate: 3600 }, // Cache 1 hour
    });

    if (response.ok) {
      const items = await response.json();
      editorialRoutes = items.map((item: any) => ({
        url: `${BASE_URL}/advert/${item.brand_slug}/${item.slug}`,
        lastModified: new Date(item.updated_at || item.created_at),
        changeFrequency: 'weekly' as const,
        priority: item.is_featured ? 0.9 : 0.7,
      }));
    }
  } catch (error) {
    console.error('Failed to fetch editorial sitemap:', error);
  }

  return [...staticRoutes, ...editorialRoutes];
}
```

**Backend endpoint for sitemap:**

```python
@app.get("/api/editorial/sitemap")
async def get_editorial_sitemap():
    """Get all published editorial entries for sitemap generation"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        e.brand_slug,
                        e.slug,
                        e.is_featured,
                        e.updated_at,
                        e.created_at
                    FROM ad_editorial e
                    WHERE e.status = 'published'
                      AND e.is_hidden = false
                      AND (e.publish_date IS NULL OR e.publish_date <= NOW())
                    ORDER BY e.updated_at DESC
                """)
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Sitemap fetch failed: {e}")
        return []
```

### 3G: 404 Monitor Plan

Add logging for missing legacy URLs:

```python
# In backend/main.py - add to resolve-legacy endpoint when not found:

# Log to a table for investigation
cur.execute("""
    INSERT INTO legacy_url_misses (url, attempted_at, user_agent, referer)
    VALUES (%s, NOW(), %s, %s)
    ON CONFLICT (url) DO UPDATE SET
        miss_count = legacy_url_misses.miss_count + 1,
        last_attempted_at = NOW()
""", (url, request.headers.get('user-agent'), request.headers.get('referer')))
```

**Create tracking table:**

```sql
CREATE TABLE IF NOT EXISTS legacy_url_misses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    url text UNIQUE NOT NULL,
    miss_count integer DEFAULT 1,
    first_attempted_at timestamptz DEFAULT now(),
    last_attempted_at timestamptz DEFAULT now(),
    user_agent text,
    referer text,
    resolved boolean DEFAULT false,
    resolution_notes text
);

-- Weekly review query
SELECT url, miss_count, first_attempted_at, last_attempted_at
FROM legacy_url_misses
WHERE resolved = false
ORDER BY miss_count DESC
LIMIT 50;
```

---

## 4. Frontend Wiring

### 4A: SEO Route Page

**File:** `frontend/app/advert/[brand]/[slug]/page.tsx`

```typescript
import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { AdDetail } from '@/components/AdDetail';
import { FeedbackPanel } from '@/components/FeedbackPanel';
import { ReasonPrompt } from '@/components/ReasonPrompt';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PageProps {
  params: { brand: string; slug: string };
}

async function getAd(brand: string, slug: string) {
  const res = await fetch(`${API_URL}/api/advert/${brand}/${slug}`, {
    next: { revalidate: 60 }, // Cache 1 minute
  });

  if (res.status === 404) {
    return null;
  }

  if (!res.ok) {
    throw new Error('Failed to fetch ad');
  }

  return res.json();
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const ad = await getAd(params.brand, params.slug);

  if (!ad) {
    return { title: 'Ad Not Found | TellyAds' };
  }

  const title = ad.headline || ad.one_line_summary || 'TV Ad';
  const description = ad.summary || ad.extracted_summary || '';

  return {
    title: `${title} | ${ad.brand_name} | TellyAds`,
    description,
    alternates: {
      canonical: `https://tellyads.com/advert/${params.brand}/${params.slug}`,
    },
    openGraph: {
      title: `${title} | ${ad.brand_name}`,
      description,
      url: `https://tellyads.com/advert/${params.brand}/${params.slug}`,
      type: 'video.other',
      images: ad.thumbnail_url ? [{ url: ad.thumbnail_url }] : [],
    },
    twitter: {
      card: 'summary_large_image',
      title: `${title} | ${ad.brand_name}`,
      description,
    },
  };
}

export default async function AdvertPage({ params }: PageProps) {
  const ad = await getAd(params.brand, params.slug);

  if (!ad) {
    notFound();
  }

  return (
    <main className="container mx-auto px-4 py-8">
      <AdDetail ad={ad} />
      <FeedbackPanel externalId={ad.external_id} />
    </main>
  );
}
```

### 4B: Session ID Helper

**File:** `frontend/lib/session.ts`

```typescript
const SESSION_KEY = 'tellyads_anon_id';

export function getSessionId(): string {
  if (typeof window === 'undefined') {
    return 'server-side-no-session';
  }

  let sessionId = localStorage.getItem(SESSION_KEY);
  if (sessionId) return sessionId;

  // Generate new random UUID
  sessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sessionId);
  return sessionId;
}
```

### 4C: Feedback Panel Component

**File:** `frontend/components/FeedbackPanel.tsx`

```typescript
'use client';

import { useState, useEffect, useCallback } from 'react';
import { getSessionId } from '@/lib/session';
import { ReasonPrompt } from './ReasonPrompt';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface FeedbackPanelProps {
  externalId: string;
}

export function FeedbackPanel({ externalId }: FeedbackPanelProps) {
  const [feedback, setFeedback] = useState<any>(null);
  const [isLiked, setIsLiked] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [showReasonPrompt, setShowReasonPrompt] = useState(false);
  const [lastAction, setLastAction] = useState<'like' | 'save' | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch initial state
  useEffect(() => {
    const fetchFeedback = async () => {
      const sessionId = getSessionId();
      try {
        const res = await fetch(
          `${API_URL}/api/ads/${externalId}/feedback?session_id=${sessionId}`
        );
        if (res.ok) {
          const data = await res.json();
          setFeedback(data);
          setIsLiked(data.user_reaction?.is_liked || false);
          setIsSaved(data.user_reaction?.is_saved || false);
        }
      } catch (error) {
        console.error('Failed to fetch feedback:', error);
      }
      setLoading(false);
    };

    fetchFeedback();

    // Record view
    const sessionId = getSessionId();
    fetch(`${API_URL}/api/ads/${externalId}/view`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    }).catch(() => {}); // Silent fail for views
  }, [externalId]);

  const toggleLike = useCallback(async () => {
    const sessionId = getSessionId();
    const wasLiked = isLiked;

    // Optimistic update
    setIsLiked(!wasLiked);

    try {
      const res = await fetch(`${API_URL}/api/ads/${externalId}/like`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const data = await res.json();
      setIsLiked(data.is_liked);

      // Show reason prompt if just liked (not unliked)
      if (data.is_liked && !wasLiked) {
        setLastAction('like');
        setShowReasonPrompt(true);
      }
    } catch (error) {
      // Revert on error
      setIsLiked(wasLiked);
      console.error('Toggle like failed:', error);
    }
  }, [externalId, isLiked]);

  const toggleSave = useCallback(async () => {
    const sessionId = getSessionId();
    const wasSaved = isSaved;

    // Optimistic update
    setIsSaved(!wasSaved);

    try {
      const res = await fetch(`${API_URL}/api/ads/${externalId}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const data = await res.json();
      setIsSaved(data.is_saved);

      // Show reason prompt if just saved (not unsaved)
      if (data.is_saved && !wasSaved) {
        setLastAction('save');
        setShowReasonPrompt(true);
      }
    } catch (error) {
      // Revert on error
      setIsSaved(wasSaved);
      console.error('Toggle save failed:', error);
    }
  }, [externalId, isSaved]);

  if (loading) {
    return <div className="animate-pulse h-20 bg-gray-800/50 rounded-lg" />;
  }

  return (
    <div className="mt-6 p-4 bg-gray-900/50 rounded-lg border border-white/10">
      {/* Action Buttons */}
      <div className="flex items-center gap-4">
        <button
          onClick={toggleLike}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            isLiked
              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
              : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
          }`}
        >
          <span>{isLiked ? '❤️' : '🤍'}</span>
          <span>Like</span>
          {feedback?.like_count > 0 && (
            <span className="text-sm opacity-70">({feedback.like_count})</span>
          )}
        </button>

        <button
          onClick={toggleSave}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            isSaved
              ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
              : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
          }`}
        >
          <span>{isSaved ? '⭐' : '☆'}</span>
          <span>Save</span>
          {feedback?.save_count > 0 && (
            <span className="text-sm opacity-70">({feedback.save_count})</span>
          )}
        </button>
      </div>

      {/* Scores Display */}
      {feedback && (
        <div className="mt-4 flex items-center gap-6 text-sm text-gray-400">
          <div>
            <span className="font-medium text-gray-300">Score: </span>
            <span className="text-green-400">{feedback.final_score?.toFixed(1) || '—'}</span>
          </div>
          <div className="text-xs opacity-60">
            AI: {feedback.ai_score?.toFixed(0) || 50} |
            User: {feedback.user_score?.toFixed(0) || 0} |
            Weight: {(feedback.confidence_weight * 100)?.toFixed(0) || 0}%
          </div>
        </div>
      )}

      {/* Reason Counts (only if threshold met) */}
      {feedback?.reason_threshold_met && Object.keys(feedback.reason_counts || {}).length > 0 && (
        <div className="mt-4 pt-4 border-t border-white/10">
          <p className="text-sm text-gray-400 mb-2">Why people like this:</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(feedback.reason_counts).map(([reason, count]) => (
              <span
                key={reason}
                className="px-2 py-1 text-xs bg-gray-800 rounded-full text-gray-300"
              >
                {reason.replace('_', ' ')} ({count as number})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Reason Prompt Modal */}
      {showReasonPrompt && lastAction && (
        <ReasonPrompt
          externalId={externalId}
          reactionType={lastAction}
          onClose={() => setShowReasonPrompt(false)}
        />
      )}
    </div>
  );
}
```

### 4D: Reason Prompt Component

**File:** `frontend/components/ReasonPrompt.tsx`

```typescript
'use client';

import { useState } from 'react';
import { getSessionId } from '@/lib/session';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const REASONS = [
  { reason: 'funny', label: 'Funny', emoji: '😂' },
  { reason: 'clever_idea', label: 'Clever idea', emoji: '💡' },
  { reason: 'emotional', label: 'Emotional', emoji: '❤️' },
  { reason: 'great_twist', label: 'Great twist', emoji: '🎬' },
  { reason: 'beautiful_visually', label: 'Beautiful', emoji: '✨' },
  { reason: 'memorable_music', label: 'Great music', emoji: '🎵' },
  { reason: 'relatable', label: 'Relatable', emoji: '🤝' },
  { reason: 'effective_message', label: 'Effective', emoji: '📣' },
  { reason: 'nostalgic', label: 'Nostalgic', emoji: '📼' },
  { reason: 'surprising', label: 'Surprising', emoji: '😮' },
];

interface ReasonPromptProps {
  externalId: string;
  reactionType: 'like' | 'save';
  onClose: () => void;
}

export function ReasonPrompt({ externalId, reactionType, onClose }: ReasonPromptProps) {
  const [selected, setSelected] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const toggleReason = (reason: string) => {
    setSelected(prev =>
      prev.includes(reason)
        ? prev.filter(r => r !== reason)
        : [...prev, reason]
    );
  };

  const submit = async () => {
    if (selected.length === 0) {
      onClose();
      return;
    }

    setSubmitting(true);
    const sessionId = getSessionId();

    try {
      await fetch(`${API_URL}/api/ads/${externalId}/reasons`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          reasons: selected,
          reaction_type: reactionType,
        }),
      });
    } catch (error) {
      console.error('Submit reasons failed:', error);
    }

    setSubmitting(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-2xl p-6 max-w-md w-full border border-white/10">
        <h3 className="text-lg font-semibold text-white mb-2">
          Why did you {reactionType} this?
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Select all that apply (optional)
        </p>

        <div className="grid grid-cols-2 gap-2 mb-6">
          {REASONS.map(({ reason, label, emoji }) => (
            <button
              key={reason}
              onClick={() => toggleReason(reason)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                selected.includes(reason)
                  ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50'
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-transparent'
              }`}
            >
              <span>{emoji}</span>
              <span>{label}</span>
            </button>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            onClick={submit}
            disabled={submitting}
            className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? 'Submitting...' : selected.length > 0 ? 'Submit' : 'Skip'}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 4E: Component Wiring Plan

| Component | Location | Fetches From |
|-----------|----------|--------------|
| `AdDetail` | `/advert/[brand]/[slug]` | Server: `/api/advert/{brand}/{slug}` |
| `FeedbackPanel` | Client component on ad pages | Client: `/api/ads/{external_id}/feedback` |
| `ReasonPrompt` | Modal after like/save | Client: POST `/api/ads/{external_id}/reasons` |
| `SearchResults` | `/search` | Server: `/api/search` |
| `AdCard` | Grid components | Props from parent |

**Key integration points:**

1. **Server-side rendering:** Use `fetch()` in `page.tsx` with `revalidate` for SEO pages
2. **Client-side interactivity:** Use `'use client'` for feedback panel
3. **Session ID:** Always use `getSessionId()` from `lib/session.ts`
4. **Optimistic updates:** Update UI immediately, revert on error

---

## 5. Ops + Rollback Plan

### 5A: Safe Rollout Strategy

#### Phase 1: Shadow Mode (Week 1)

- Deploy backend with new endpoints
- Keep old `/ads/{external_id}` route working
- New `/advert/{brand}/{slug}` route available but not linked
- Import editorial content (draft status)
- Monitor error rates

#### Phase 2: Soft Launch (Week 2)

- Publish editorial content (status → 'published')
- Enable redirects for known legacy URLs
- Add links to new routes in footer/nav
- Keep old route indexed temporarily
- Monitor 404 rates and performance

#### Phase 3: Full Launch (Week 3)

- Add `noindex` to old `/ads/` route
- Update sitemap to only include `/advert/` routes
- Enable all redirects
- Remove old route links from navigation

### 5B: Feature Flags (Optional)

If using environment-based flags:

```typescript
// frontend/lib/flags.ts
export const FLAGS = {
  ENABLE_NEW_ROUTES: process.env.NEXT_PUBLIC_ENABLE_NEW_ROUTES === 'true',
  ENABLE_FEEDBACK: process.env.NEXT_PUBLIC_ENABLE_FEEDBACK === 'true',
  ENABLE_REASONS: process.env.NEXT_PUBLIC_ENABLE_REASONS === 'true',
};
```

### 5C: Rollback Procedures

#### Level 1: Frontend-Only Rollback

```bash
# Revert to previous frontend deployment
# Vercel
vercel rollback

# Or via git
git revert HEAD
git push origin main
```

**Time to recover:** ~2-5 minutes

#### Level 2: Backend Rollback

```bash
# Railway
railway rollback

# Or redeploy previous version
git checkout <previous-commit>
railway up

# Or Render: Redeploy from dashboard
```

**Time to recover:** ~3-10 minutes

#### Level 3: Database Rollback (Last Resort)

```bash
# DANGER: Only if absolutely necessary
# This will lose user feedback data

# 1. Restore from backup
psql "$SUPABASE_DB_URL" < backup_YYYYMMDD_HHMMSS.sql

# OR

# 2. Disable features without dropping tables
# Update backend to skip new endpoints
# Set env var: DISABLE_FEEDBACK=true

# OR

# 3. Drop only new tables (loses all feedback data!)
psql "$SUPABASE_DB_URL" <<EOF
DROP TABLE IF EXISTS ad_like_reasons CASCADE;
DROP TABLE IF EXISTS ad_user_tags CASCADE;
DROP TABLE IF EXISTS ad_user_reactions CASCADE;
DROP TABLE IF EXISTS ad_feedback_agg CASCADE;
DROP TABLE IF EXISTS ad_rate_limits CASCADE;
DROP TABLE IF EXISTS ad_editorial CASCADE;
-- Note: This does NOT touch the 'ads' table
EOF
```

**Time to recover:** ~10-30 minutes

### 5D: Pre-Migration Checklist

```bash
# 1. Backup database
pg_dump "$SUPABASE_DB_URL" > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Verify backup
pg_restore --list backup_*.sql | head -20

# 3. Test restore on staging
createdb tellyads_restore_test
psql tellyads_restore_test < backup_*.sql

# 4. Document current state
psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) FROM ads"
psql "$SUPABASE_DB_URL" -c "SELECT relname, n_live_tup FROM pg_stat_user_tables"

# 5. Notify team
# "Migration starting at HH:MM - estimated 30 min"
```

### 5E: Monitoring During Migration

```bash
# Watch for errors in backend logs
railway logs --follow

# Monitor database connections
psql "$SUPABASE_DB_URL" -c "SELECT count(*) FROM pg_stat_activity"

# Check API health
watch -n 5 'curl -s $API_URL/api/status | jq .'

# Monitor 4xx/5xx rates (if using Vercel Analytics)
# Check Vercel dashboard → Analytics → Errors
```

---

## 6. Done Acceptance Criteria

### 6.1: Import Success

| Metric | Target | Query |
|--------|--------|-------|
| Excel rows matched | ≥80% | `SELECT matched_count / total_records FROM import_summary` |
| Editorial records created | = matched rows | `SELECT COUNT(*) FROM ad_editorial` |
| Zero orphan records | 0 | `SELECT COUNT(*) FROM ad_editorial WHERE ad_id IS NULL` |

### 6.2: Published Pages

| Metric | Target | Query |
|--------|--------|-------|
| Published editorial count | >0 | `SELECT COUNT(*) FROM ad_editorial WHERE status='published'` |
| All published accessible | 100% | Crawl test all `/advert/{brand}/{slug}` URLs |
| SEO gating works | 100% | Draft/hidden returns 404 |

### 6.3: Redirects

| Metric | Target | Test |
|--------|--------|------|
| Known legacy URLs redirect | ≥95% | Test sample of 50 known Wix URLs |
| Redirect status code | 301 | `curl -I old-url` shows 301 |
| No redirect loops | 0 | Automated crawl check |

### 6.4: Search Integration

| Metric | Target | Test |
|--------|--------|------|
| display_title uses editorial | 100% | `SELECT COALESCE(e.headline, a.one_line_summary) ...` |
| Results link to correct URL | 100% | Manual spot check |
| Featured ads appear first | Yes | `ORDER BY is_featured DESC, final_score DESC` |

### 6.5: Feedback System

| Metric | Target | Test |
|--------|--------|------|
| Anonymous like/save works | Yes | Test without login |
| Session persists | Yes | Refresh page, state preserved |
| View rate limiting | 10/hr | Rapid fire test returns 429 |
| Reason threshold | 10 sessions | `reason_counts` empty below 10 |

### 6.6: Scoring V2

| Metric | Target | Test |
|--------|--------|------|
| ai_score computed | 0-100 | Check sample ads |
| confidence_weight excludes views | Yes | Manual formula verification |
| Low engagement → AI dominant | weight ≈ 0 | Test with 0 likes/saves |
| High engagement → user influence | weight ≤ 0.6 | Test with 50+ signals |

### Final Sign-Off Checklist

```
[ ] All migrations applied successfully
[ ] All verification queries pass
[ ] Backend deployed with ADMIN_API_KEY
[ ] Smoke tests pass (all 6)
[ ] Import completed with ≥80% match rate
[ ] Published pages accessible
[ ] Redirects working
[ ] Sitemap includes editorial routes
[ ] Canonical tags present
[ ] Feedback UI working
[ ] Reason prompt appears after like/save
[ ] Scores display correctly
[ ] Rollback procedure documented
[ ] Team notified of launch
```

---

## Appendix: Quick Reference Commands

```bash
# Apply all migrations
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback.sql
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons.sql
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2.sql

# Verify all migrations
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback_verify.sql
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons_verify.sql
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2_verify.sql

# Import editorial
python scripts/import_editorial.py --input data/wix.xlsx --dry-run
python scripts/import_editorial.py --input data/wix.xlsx --apply

# Generate redirects
python scripts/generate_redirects.py

# Deploy backend
railway up

# Deploy frontend
cd frontend && vercel --prod
```

---

**Document version:** 1.0.0
**Last updated:** 2025-12-04
**Author:** Claude Code
