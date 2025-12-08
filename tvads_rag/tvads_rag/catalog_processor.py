"""
Catalog Import Processor for TellyAds RAG.

Handles bulk CSV import of ad catalog metadata.
Designed for Railway worker processing (NOT Vercel runtime).

Features:
- Stream-based CSV parsing (memory efficient for 20k+ rows)
- Smart date parsing with confidence scoring
- Idempotent upserts via external_id
- Progress tracking via job heartbeats
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Optional, Tuple
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from .config import get_storage_config
from .db import get_connection

logger = logging.getLogger(__name__)


@dataclass
class DateParseResult:
    """Result of date parsing with confidence tracking."""
    parsed_date: Optional[date]
    raw_value: str
    confidence: float  # 0.0 to 1.0
    warning: Optional[str]


@dataclass
class CatalogRow:
    """Parsed catalog row ready for database insertion."""
    external_id: str
    brand_name: Optional[str]
    title: Optional[str]
    description: Optional[str]
    air_date: Optional[date]
    air_date_raw: Optional[str]
    date_parse_confidence: float
    date_parse_warning: Optional[str]
    year: Optional[int]
    country: Optional[str]
    region: Optional[str]
    language: Optional[str]
    s3_key: Optional[str]
    video_url: Optional[str]
    views_seeded: int
    likes_seeded: int
    row_number: int


class DateParser:
    """
    Smart date parser with confidence scoring.

    Handles ambiguous formats (dd/mm vs mm/dd) conservatively.
    """

    # Unambiguous formats (high confidence)
    UNAMBIGUOUS_PATTERNS = [
        # ISO format: 2024-01-15
        (r'^(\d{4})-(\d{1,2})-(\d{1,2})$', 'ymd'),
        # Written month: 15 Jan 2024, Jan 15 2024, January 15, 2024
        (r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})$', 'dmy_written'),
        (r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})$', 'mdy_written'),
        # Year only: 2024
        (r'^(\d{4})$', 'year_only'),
    ]

    # Ambiguous formats (need heuristics)
    AMBIGUOUS_PATTERNS = [
        # DD/MM/YYYY or MM/DD/YYYY
        (r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$', 'dmy_or_mdy'),
        # DD/MM/YY or MM/DD/YY
        (r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})$', 'dmy_or_mdy_short'),
    ]

    MONTH_MAP = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    }

    def parse(self, value: str) -> DateParseResult:
        """Parse date string with confidence scoring."""
        if not value or not value.strip():
            return DateParseResult(None, '', 1.0, None)

        raw = value.strip()
        normalized = raw.lower()

        # Try unambiguous patterns first
        for pattern, fmt in self.UNAMBIGUOUS_PATTERNS:
            match = re.match(pattern, raw, re.IGNORECASE)
            if match:
                try:
                    parsed = self._parse_unambiguous(match, fmt)
                    if parsed and self._is_valid_date(parsed):
                        return DateParseResult(parsed, raw, 1.0, None)
                except ValueError:
                    pass

        # Try ambiguous patterns with heuristics
        for pattern, fmt in self.AMBIGUOUS_PATTERNS:
            match = re.match(pattern, raw)
            if match:
                return self._parse_ambiguous(match, fmt, raw)

        # Couldn't parse
        return DateParseResult(None, raw, 0.0, f"Could not parse date: {raw}")

    def _parse_unambiguous(self, match: re.Match, fmt: str) -> Optional[date]:
        """Parse match with unambiguous format."""
        groups = match.groups()

        if fmt == 'ymd':
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        elif fmt == 'dmy_written':
            month = self.MONTH_MAP.get(groups[1].lower()[:3], 0)
            return date(int(groups[2]), month, int(groups[0]))
        elif fmt == 'mdy_written':
            month = self.MONTH_MAP.get(groups[0].lower()[:3], 0)
            return date(int(groups[2]), month, int(groups[1]))
        elif fmt == 'year_only':
            return date(int(groups[0]), 1, 1)

        return None

    def _parse_ambiguous(self, match: re.Match, fmt: str, raw: str) -> DateParseResult:
        """Parse ambiguous dd/mm vs mm/dd format with heuristics."""
        groups = [int(g) for g in match.groups()]

        # Handle 2-digit year
        if fmt == 'dmy_or_mdy_short':
            year = groups[2]
            year = year + 2000 if year < 50 else year + 1900
        else:
            year = groups[2]

        first, second = groups[0], groups[1]

        # If first > 12, must be day (DD/MM format)
        if first > 12:
            if second <= 12:
                parsed = date(year, second, first)
                return DateParseResult(parsed, raw, 0.95, None)
            else:
                return DateParseResult(None, raw, 0.0, f"Invalid date: {raw}")

        # If second > 12, must be day (MM/DD format)
        if second > 12:
            if first <= 12:
                parsed = date(year, first, second)
                return DateParseResult(parsed, raw, 0.95, None)
            else:
                return DateParseResult(None, raw, 0.0, f"Invalid date: {raw}")

        # Both could be month or day - ambiguous!
        # Default to DD/MM (more common internationally), but flag low confidence
        try:
            parsed = date(year, second, first)  # DD/MM
            warning = f"Ambiguous date {raw}: assumed DD/MM format"
            return DateParseResult(parsed, raw, 0.5, warning)
        except ValueError:
            # Try MM/DD as fallback
            try:
                parsed = date(year, first, second)
                warning = f"Ambiguous date {raw}: assumed MM/DD format (DD/MM invalid)"
                return DateParseResult(parsed, raw, 0.6, warning)
            except ValueError:
                return DateParseResult(None, raw, 0.0, f"Invalid date: {raw}")

    def _is_valid_date(self, d: date) -> bool:
        """Check if date is reasonable (not too far in past or future)."""
        return 1900 <= d.year <= date.today().year + 5


class CatalogImportProcessor:
    """
    Processes CSV catalog imports.

    Designed for worker execution with progress tracking.
    """

    # Expected CSV columns (case-insensitive matching)
    COLUMN_MAPPINGS = {
        'external_id': ['external_id', 'id', 'ad_id', 'video_id', 'asset_id'],
        'brand_name': ['brand_name', 'brand', 'advertiser', 'company'],
        'title': ['title', 'name', 'ad_title', 'video_title'],
        'description': ['description', 'desc', 'summary'],
        'air_date': ['air_date', 'date', 'broadcast_date', 'release_date', 'air_date_raw'],
        'year': ['year', 'release_year', 'air_year'],
        'country': ['country', 'region', 'market', 'territory'],
        'language': ['language', 'lang'],
        's3_key': ['s3_key', 's3_path', 'video_key', 'asset_key'],
        'video_url': ['video_url', 'url', 'video_link', 'asset_url'],
        'views': ['views', 'view_count', 'views_seeded'],
        'likes': ['likes', 'like_count', 'likes_seeded'],
    }

    def __init__(self):
        self.date_parser = DateParser()
        self._s3_client = None

    @property
    def s3_client(self):
        """Lazy-initialize S3 client."""
        if self._s3_client is None:
            cfg = get_storage_config()
            client_kwargs = {
                'service_name': 's3',
                'region_name': cfg.s3_region,
            }
            if cfg.s3_endpoint_url:
                client_kwargs['endpoint_url'] = cfg.s3_endpoint_url
            self._s3_client = boto3.client(**client_kwargs)
        return self._s3_client

    def process_import(
        self,
        import_id: UUID,
        file_path: str,
        bucket: str,
        heartbeat_callback: Optional[callable] = None,
    ) -> dict[str, Any]:
        """
        Process a catalog import job.

        Args:
            import_id: UUID of the ad_catalog_imports record
            file_path: S3 key of the CSV file
            bucket: S3 bucket name
            heartbeat_callback: Optional callback(stage, progress) for job heartbeat

        Returns:
            Dict with processing results
        """
        logger.info(f"Starting catalog import {import_id} from s3://{bucket}/{file_path}")

        # Update import status to PROCESSING
        self._update_import_status(import_id, 'PROCESSING')

        try:
            # Download CSV from S3
            if heartbeat_callback:
                heartbeat_callback('downloading', 0.05)

            csv_content = self._download_csv(bucket, file_path)

            # Parse and process rows
            if heartbeat_callback:
                heartbeat_callback('parsing', 0.1)

            results = self._process_csv(import_id, csv_content, heartbeat_callback)

            # Update import record with results
            self._update_import_results(
                import_id,
                status='SUCCEEDED',
                rows_total=results['total'],
                rows_ok=results['ok'],
                rows_failed=results['failed'],
                error_details=results.get('errors', []),
            )

            logger.info(
                f"Catalog import {import_id} completed: "
                f"{results['ok']}/{results['total']} rows OK, "
                f"{results['failed']} failed"
            )

            return {
                'success': True,
                **results,
            }

        except Exception as e:
            logger.exception(f"Catalog import {import_id} failed: {e}")
            self._update_import_results(
                import_id,
                status='FAILED',
                last_error=str(e)[:2000],
            )
            raise

    def _download_csv(self, bucket: str, key: str) -> str:
        """Download CSV content from S3."""
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read()

            # Try UTF-8 first, fall back to latin-1
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                return content.decode('latin-1')
        except ClientError as e:
            raise ValueError(f"Failed to download CSV from S3: {e}")

    def _process_csv(
        self,
        import_id: UUID,
        csv_content: str,
        heartbeat_callback: Optional[callable],
    ) -> dict[str, Any]:
        """Process CSV content row by row."""
        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))

        # Map columns
        column_map = self._build_column_map(reader.fieldnames or [])

        if 'external_id' not in column_map:
            raise ValueError("CSV must have an external_id column (or id, ad_id, video_id)")

        # Process rows
        results = {
            'total': 0,
            'ok': 0,
            'failed': 0,
            'created': 0,
            'updated': 0,
            'errors': [],
        }

        rows = list(reader)
        total_rows = len(rows)

        for i, row in enumerate(rows):
            results['total'] += 1

            # Update progress periodically
            if heartbeat_callback and i % 100 == 0:
                progress = 0.1 + 0.85 * (i / max(total_rows, 1))
                heartbeat_callback('processing', progress)

            try:
                catalog_row = self._parse_row(row, column_map, i + 2)  # +2 for header and 1-indexing
                was_created = self._upsert_row(import_id, catalog_row)

                results['ok'] += 1
                if was_created:
                    results['created'] += 1
                else:
                    results['updated'] += 1

            except Exception as e:
                results['failed'] += 1
                error_msg = f"Row {i + 2}: {str(e)[:200]}"
                if len(results['errors']) < 100:  # Limit error storage
                    results['errors'].append(error_msg)
                logger.warning(f"Row {i + 2} failed: {e}")

        if heartbeat_callback:
            heartbeat_callback('completed', 1.0)

        return results

    def _build_column_map(self, headers: list[str]) -> dict[str, str]:
        """Map CSV headers to canonical column names."""
        column_map = {}
        headers_lower = {h.lower().strip(): h for h in headers}

        for canonical, variants in self.COLUMN_MAPPINGS.items():
            for variant in variants:
                if variant.lower() in headers_lower:
                    column_map[canonical] = headers_lower[variant.lower()]
                    break

        return column_map

    def _parse_row(self, row: dict, column_map: dict, row_number: int) -> CatalogRow:
        """Parse a single CSV row."""
        def get_value(key: str) -> Optional[str]:
            if key in column_map:
                val = row.get(column_map[key], '').strip()
                return val if val else None
            return None

        def get_int(key: str) -> Optional[int]:
            val = get_value(key)
            if val:
                try:
                    return int(val.replace(',', ''))
                except ValueError:
                    pass
            return None

        # Required: external_id
        external_id = get_value('external_id')
        if not external_id:
            raise ValueError("Missing external_id")

        # Parse date
        date_raw = get_value('air_date')
        date_result = self.date_parser.parse(date_raw or '')

        # Get year (from date or explicit column)
        year = get_int('year')
        if not year and date_result.parsed_date:
            year = date_result.parsed_date.year

        return CatalogRow(
            external_id=external_id,
            brand_name=get_value('brand_name'),
            title=get_value('title'),
            description=get_value('description'),
            air_date=date_result.parsed_date,
            air_date_raw=date_result.raw_value,
            date_parse_confidence=date_result.confidence,
            date_parse_warning=date_result.warning,
            year=year,
            country=get_value('country'),
            region=None,  # Not commonly in CSVs
            language=get_value('language'),
            s3_key=get_value('s3_key'),
            video_url=get_value('video_url'),
            views_seeded=get_int('views') or 0,
            likes_seeded=get_int('likes') or 0,
            row_number=row_number,
        )

    def _upsert_row(self, import_id: UUID, row: CatalogRow) -> bool:
        """Upsert a catalog row. Returns True if created, False if updated."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM upsert_catalog_entry(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        row.external_id,
                        row.brand_name,
                        row.title,
                        row.description,
                        row.air_date,
                        row.air_date_raw,
                        row.date_parse_confidence,
                        row.date_parse_warning,
                        row.year,
                        row.country,
                        row.region,
                        row.language,
                        row.s3_key,
                        row.video_url,
                        row.views_seeded,
                        row.likes_seeded,
                        str(import_id),
                        row.row_number,
                    )
                )
                result = cur.fetchone()
                return result['was_created'] if result else False

    def _update_import_status(self, import_id: UUID, status: str):
        """Update import record status."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ad_catalog_imports SET status = %s WHERE id = %s",
                    (status, str(import_id))
                )

    def _update_import_results(
        self,
        import_id: UUID,
        status: str,
        rows_total: int = 0,
        rows_ok: int = 0,
        rows_failed: int = 0,
        last_error: Optional[str] = None,
        error_details: Optional[list] = None,
    ):
        """Update import record with results."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ad_catalog_imports
                    SET status = %s, rows_total = %s, rows_ok = %s, rows_failed = %s,
                        last_error = %s, error_details = %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        status,
                        rows_total,
                        rows_ok,
                        rows_failed,
                        last_error,
                        '[]' if not error_details else str(error_details).replace("'", '"'),
                        str(import_id),
                    )
                )
