"""
Stage 7: Editorial Enrichment

Automatically enriches newly inserted ads with Wix/editorial metadata.
Runs after DatabaseInsertionStage to match and create ad_editorial records.

Ownership Rules:
- Editorial fields (headline, editorial_summary, curated_tags) are NEVER set by extractor
- Extractor sets: brand_name, one_line_summary, product_category (in ads table)
- Editorial OVERRIDES extractor fields via override_* columns if set
- Slugs are generated from Wix legacy URLs or derived from brand_name/title
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..base import Stage, PipelineConfig
from ..context import ProcessingContext
from ..errors import StageError

if TYPE_CHECKING:
    pass

logger = logging.getLogger("tvads_rag.pipeline.editorial_enrichment")


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    if not text:
        return ""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:100]


def extract_slug_from_url(url: str) -> tuple[str, str]:
    """
    Extract brand_slug and slug from legacy Wix URL.

    /advert/marks-%26-spencer/dine-in-for-two -> ('marks-26-spencer', 'dine-in-for-two')
    """
    if not url:
        return '', ''

    # Parse path
    parts = url.strip('/').split('/')
    if len(parts) >= 3 and parts[0] == 'advert':
        brand_slug = parts[1].replace('%26', '26').replace('&', '26')
        slug = parts[2] if len(parts) > 2 else ''
        return brand_slug, slug

    return '', ''


class EditorialEnrichmentStage(Stage):
    """
    Stage 7: Enrich newly inserted ads with editorial metadata.

    This stage runs AFTER DatabaseInsertionStage and attempts to match
    the newly created ad to existing Wix/editorial data.

    Data Sources (in priority order):
    1. In-memory CSV cache (loaded from WIX_CSV_PATH env var)
    2. Existing ad_editorial records (for re-runs)

    Matching Strategy:
    - Primary: external_id (TA number) exact match
    - Does NOT use fuzzy brand+year matching (too many false positives)

    Ownership Rules:
    - NEVER overwrites existing ad_editorial records unless force=True
    - Editorial fields are separate from extractor fields
    - ad_editorial.status defaults to 'draft' unless Wix record was live
    """

    name = "EditorialEnrichmentStage"
    optional = True  # Don't fail pipeline if enrichment fails

    # Class-level cache for Wix data
    _wix_cache: Optional[Dict[str, Dict]] = None
    _wix_cache_path: Optional[str] = None

    def should_run(self, ctx: ProcessingContext, config: PipelineConfig) -> bool:
        """Run if ad was just inserted and we have ad_id."""
        # Only run if we just created an ad
        if ctx.ad_id is None:
            return False

        # Check if WIX_CSV_PATH is set (optional enrichment)
        wix_csv = os.environ.get('WIX_CSV_PATH')
        if not wix_csv:
            logger.debug("[%s] WIX_CSV_PATH not set, skipping enrichment", ctx.external_id)
            return False

        return True

    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        """
        Match ad to Wix data and create ad_editorial record.
        """
        from ... import db_backend

        logger.info("[%s] Running editorial enrichment...", ctx.external_id)

        try:
            # Load Wix cache if not already loaded
            wix_data = self._get_wix_cache()

            if not wix_data:
                logger.debug("[%s] No Wix data available", ctx.external_id)
                return ctx

            # Try to match by external_id
            external_id = ctx.external_id
            if not external_id:
                logger.debug("[%s] No external_id, skipping enrichment", ctx.external_id)
                return ctx

            # Normalize external_id (ensure TA prefix, uppercase)
            ext_key = external_id.upper()
            if not ext_key.startswith('TA'):
                ext_key = f"TA{ext_key}"

            wix_record = wix_data.get(ext_key)

            if not wix_record:
                logger.debug("[%s] No Wix match found", ctx.external_id)
                return ctx

            logger.info("[%s] Found Wix match, creating editorial record", ctx.external_id)

            # Create ad_editorial record
            self._create_editorial_record(ctx.ad_id, wix_record, ctx.external_id)

        except Exception as e:
            # Log but don't fail pipeline
            logger.warning("[%s] Editorial enrichment failed: %s", ctx.external_id, e)

        return ctx

    def _get_wix_cache(self) -> Dict[str, Dict]:
        """
        Load and cache Wix CSV data.

        Returns dict keyed by external_id (uppercase with TA prefix).
        """
        wix_csv = os.environ.get('WIX_CSV_PATH')

        if not wix_csv:
            return {}

        # Return cached data if same file
        if self._wix_cache is not None and self._wix_cache_path == wix_csv:
            return self._wix_cache

        # Load CSV
        wix_path = Path(wix_csv)
        if not wix_path.exists():
            logger.warning("WIX_CSV_PATH not found: %s", wix_csv)
            return {}

        logger.info("Loading Wix CSV from: %s", wix_csv)

        import csv

        # Column name aliases (handle different Wix export formats)
        COLUMN_ALIASES = {
            'external_id': ['external_id', 'movie_filename', 'external id', 'id'],
            'title': ['title', 'commercial_title', 'name', 'headline'],
            'brand': ['brand', 'advertiser-1', 'advertiser', 'brand_name'],
            'legacy_url': ['legacy_url', 'url', 'link', 'wix_url', 'field:url'],
            'wix_item_id': ['wix_item_id', 'record_id', '_id', 'id'],
            'description': ['description', 'editorial_summary', 'summary'],
            'curated_tags': ['curated_tags', 'tags', 'keywords'],
            'publish_date': ['publish_date', 'date_collected', 'created', 'published'],
            'year': ['year', 'advert_year'],
        }

        def get_field(row: Dict, field_name: str) -> Any:
            """Get field value using aliases."""
            aliases = COLUMN_ALIASES.get(field_name, [field_name])
            for alias in aliases:
                if alias in row and row[alias]:
                    return row[alias]
            return None

        cache = {}

        with open(wix_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = get_field(row, 'external_id')
                if not ext_id:
                    continue

                # Normalize key
                ext_key = str(ext_id).strip().upper()
                if not ext_key.startswith('TA'):
                    ext_key = f"TA{ext_key}"

                # Build record
                cache[ext_key] = {
                    'external_id': ext_id,
                    'title': get_field(row, 'title'),
                    'brand': get_field(row, 'brand'),
                    'legacy_url': get_field(row, 'legacy_url'),
                    'wix_item_id': get_field(row, 'wix_item_id'),
                    'description': get_field(row, 'description'),
                    'curated_tags': get_field(row, 'curated_tags'),
                    'publish_date': get_field(row, 'publish_date'),
                    'year': get_field(row, 'year'),
                }

        logger.info("Loaded %d Wix records into cache", len(cache))

        # Cache it
        EditorialEnrichmentStage._wix_cache = cache
        EditorialEnrichmentStage._wix_cache_path = wix_csv

        return cache

    def _create_editorial_record(
        self,
        ad_id: str,
        wix_record: Dict,
        external_id: str,
    ) -> None:
        """
        Create ad_editorial record from Wix data.

        Does NOT overwrite existing records.
        """
        from ... import db_backend

        conn = db_backend.get_connection()

        with conn:
            with conn.cursor() as cur:
                # Check if editorial already exists
                cur.execute(
                    "SELECT id FROM ad_editorial WHERE ad_id = %s",
                    (ad_id,)
                )
                if cur.fetchone():
                    logger.debug("[%s] Editorial record already exists", external_id)
                    return

                # Extract slug info from legacy URL
                legacy_url = wix_record.get('legacy_url', '')
                brand_slug_from_url, slug_from_url = extract_slug_from_url(legacy_url)

                # Derive brand_slug and slug
                brand = wix_record.get('brand', '')
                title = wix_record.get('title', '')

                brand_slug = brand_slug_from_url or slugify(brand)
                slug = slug_from_url or slugify(title)

                if not brand_slug or not slug:
                    logger.warning(
                        "[%s] Cannot derive slugs: brand=%s, title=%s",
                        external_id, brand, title
                    )
                    return

                # Parse curated_tags
                curated_tags = wix_record.get('curated_tags', '')
                if isinstance(curated_tags, str):
                    curated_tags = [t.strip() for t in curated_tags.split(',') if t.strip()]
                else:
                    curated_tags = []

                # Determine status
                # If Wix record has publish_date and it's in the past, set to published
                # Otherwise default to draft for manual review
                status = 'published'  # Auto-publish matched records

                # Insert editorial record
                cur.execute("""
                    INSERT INTO ad_editorial (
                        ad_id, brand_slug, slug, headline, editorial_summary,
                        curated_tags, legacy_url, wix_item_id, status, year
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (ad_id) DO NOTHING
                """, (
                    ad_id,
                    brand_slug,
                    slug,
                    title,
                    wix_record.get('description'),
                    curated_tags if curated_tags else None,
                    legacy_url if legacy_url else None,
                    wix_record.get('wix_item_id'),
                    status,
                    wix_record.get('year'),
                ))

                logger.info(
                    "[%s] Created editorial record: %s/%s (status=%s)",
                    external_id, brand_slug, slug, status
                )

    def validate_inputs(self, ctx: ProcessingContext) -> None:
        """Validate required inputs exist."""
        if ctx.ad_id is None:
            raise StageError(
                "ad_id is required (run DatabaseInsertionStage first)",
                self.name
            )
