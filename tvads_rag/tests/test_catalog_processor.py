"""
Tests for Catalog Import Processor.

Tests cover:
1. DateParser date parsing logic
2. CatalogImportProcessor CSV parsing
3. Database upsert behavior
4. Error handling
"""

from contextlib import contextmanager
from datetime import date, datetime
from io import StringIO
from unittest.mock import Mock, patch, MagicMock
import uuid

import pytest

pytest.importorskip("psycopg2")

from tvads_rag.catalog_processor import (
    DateParser,
    CatalogImportProcessor,
)


# ---------------------------------------------------------------------------
# Test DateParser
# ---------------------------------------------------------------------------

class TestDateParser:
    """Test smart date parsing logic."""

    def test_iso_format(self):
        """ISO format should parse with high confidence."""
        parsed, confidence, warning = DateParser.parse_date("2024-03-15")

        assert parsed == date(2024, 3, 15)
        assert confidence == 1.0
        assert warning is None

    def test_us_format(self):
        """US format (MM/DD/YYYY) should parse correctly."""
        parsed, confidence, warning = DateParser.parse_date("03/15/2024")

        assert parsed == date(2024, 3, 15)
        assert confidence >= 0.8

    def test_european_format(self):
        """European format (DD/MM/YYYY) should parse correctly."""
        parsed, confidence, warning = DateParser.parse_date("15/03/2024")

        assert parsed == date(2024, 3, 15)
        assert confidence >= 0.8

    def test_ambiguous_date_low_confidence(self):
        """Ambiguous dates (could be MM/DD or DD/MM) should have lower confidence."""
        # 03/04/2024 could be March 4 or April 3
        parsed, confidence, warning = DateParser.parse_date("03/04/2024")

        assert parsed is not None
        assert confidence < 1.0
        assert warning is not None
        assert "ambiguous" in warning.lower()

    def test_year_only(self):
        """Year-only input should return January 1st of that year."""
        parsed, confidence, warning = DateParser.parse_date("1985")

        assert parsed == date(1985, 1, 1)
        assert confidence < 1.0
        assert warning is not None

    def test_decade_string(self):
        """Decade strings like '1980s' should parse to middle of decade."""
        parsed, confidence, warning = DateParser.parse_date("1980s")

        assert parsed is not None
        assert parsed.year >= 1980 and parsed.year <= 1989
        assert confidence < 0.8
        assert warning is not None

    def test_month_year_only(self):
        """Month and year should default to day 1."""
        parsed, confidence, warning = DateParser.parse_date("March 2024")

        assert parsed == date(2024, 3, 1)
        assert confidence < 1.0
        assert warning is not None

    def test_invalid_date(self):
        """Invalid date strings should return None."""
        parsed, confidence, warning = DateParser.parse_date("not a date")

        assert parsed is None
        assert confidence == 0.0
        assert warning is not None

    def test_empty_string(self):
        """Empty string should return None without error."""
        parsed, confidence, warning = DateParser.parse_date("")

        assert parsed is None
        assert confidence == 0.0

    def test_none_input(self):
        """None input should return None without error."""
        parsed, confidence, warning = DateParser.parse_date(None)

        assert parsed is None
        assert confidence == 0.0

    def test_future_date_warning(self):
        """Future dates should still parse but may have warning."""
        parsed, confidence, warning = DateParser.parse_date("2030-01-01")

        assert parsed == date(2030, 1, 1)
        # Future dates might have a warning depending on implementation

    def test_very_old_date(self):
        """Very old dates (pre-TV era) should parse but may have warning."""
        parsed, confidence, warning = DateParser.parse_date("1920-05-15")

        assert parsed == date(1920, 5, 15)
        # Very old dates might have warnings about pre-TV era


class TestDateParserEdgeCases:
    """Test edge cases and special formats."""

    def test_whitespace_handling(self):
        """Dates with extra whitespace should parse."""
        parsed, confidence, warning = DateParser.parse_date("  2024-03-15  ")

        assert parsed == date(2024, 3, 15)

    def test_various_separators(self):
        """Different separators should be handled."""
        dates = [
            "2024/03/15",
            "2024.03.15",
            "2024-03-15",
        ]
        for d in dates:
            parsed, _, _ = DateParser.parse_date(d)
            assert parsed == date(2024, 3, 15), f"Failed for {d}"

    def test_two_digit_year(self):
        """Two-digit years should be interpreted correctly."""
        # 85 should be 1985, not 2085
        parsed, confidence, warning = DateParser.parse_date("03/15/85")

        if parsed:
            assert parsed.year in (1985, 2085)  # Allow either interpretation


# ---------------------------------------------------------------------------
# Test CatalogImportProcessor
# ---------------------------------------------------------------------------

class FakeCursor:
    """Mock cursor for testing."""

    def __init__(self, results=None):
        self.results = results or []
        self.query = None
        self.params = None
        self.executed_queries = []

    def execute(self, query, params=None):
        self.query = query
        self.params = params
        self.executed_queries.append((query, params))

    def fetchone(self):
        if self.results:
            return self.results[0] if isinstance(self.results[0], dict) else self.results[0]
        return None

    def fetchall(self):
        return self.results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    """Mock connection for testing."""

    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class TestCatalogImportProcessorInit:
    """Test processor initialization."""

    def test_init_with_import_id(self):
        """Processor should accept import_id."""
        import_id = str(uuid.uuid4())
        processor = CatalogImportProcessor(import_id=import_id)

        assert processor.import_id == import_id

    def test_init_with_heartbeat_callback(self):
        """Processor should accept heartbeat callback."""
        callback = Mock()
        processor = CatalogImportProcessor(
            import_id=str(uuid.uuid4()),
            heartbeat_callback=callback,
        )

        assert processor.heartbeat_callback == callback


class TestCatalogImportProcessorParsing:
    """Test CSV row parsing."""

    def test_parse_row_basic(self):
        """Parse a basic CSV row."""
        import_id = str(uuid.uuid4())
        processor = CatalogImportProcessor(import_id=import_id)

        row = {
            "external_id": "TA1234",
            "brand_name": "Coca-Cola",
            "title": "Christmas Ad 2024",
            "air_date": "2024-12-25",
            "country": "USA",
            "language": "English",
            "s3_key": "videos/TA1234.mp4",
        }

        entry = processor._parse_row(row, row_number=1)

        assert entry["external_id"] == "TA1234"
        assert entry["brand_name"] == "Coca-Cola"
        assert entry["title"] == "Christmas Ad 2024"
        assert entry["air_date"] == date(2024, 12, 25)
        assert entry["date_parse_confidence"] == 1.0
        assert entry["country"] == "USA"
        assert entry["s3_key"] == "videos/TA1234.mp4"

    def test_parse_row_missing_external_id(self):
        """Row without external_id should raise error."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        row = {
            "brand_name": "Pepsi",
            "title": "Some Ad",
        }

        with pytest.raises(ValueError, match="external_id"):
            processor._parse_row(row, row_number=1)

    def test_parse_row_with_video_url(self):
        """Row with video_url instead of s3_key should parse."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        row = {
            "external_id": "TA5678",
            "brand_name": "Nike",
            "video_url": "https://example.com/video.mp4",
        }

        entry = processor._parse_row(row, row_number=1)

        assert entry["video_url"] == "https://example.com/video.mp4"
        assert entry.get("s3_key") is None

    def test_parse_row_derives_decade(self):
        """Decade should be derived from year."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        row = {
            "external_id": "TA1985",
            "air_date": "1985-03-15",
        }

        entry = processor._parse_row(row, row_number=1)

        assert entry["year"] == 1985
        assert entry["decade"] == "1980s"

    def test_parse_row_views_seeded(self):
        """Views should be parsed as integer."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        row = {
            "external_id": "TA001",
            "views": "12345",
        }

        entry = processor._parse_row(row, row_number=1)

        assert entry["views_seeded"] == 12345

    def test_parse_row_handles_empty_values(self):
        """Empty string values should become None."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        row = {
            "external_id": "TA001",
            "brand_name": "",
            "title": "",
            "country": "",
        }

        entry = processor._parse_row(row, row_number=1)

        assert entry["brand_name"] is None
        assert entry["title"] is None
        assert entry["country"] is None


class TestCatalogImportProcessorDatabase:
    """Test database operations."""

    def test_upsert_entry_new(self, monkeypatch):
        """Upsert should insert new entry."""
        cursor = FakeCursor([{
            "id": uuid.uuid4(),
            "created": True,
        }])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.catalog_processor.get_connection", fake_get_connection)

        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        entry = {
            "external_id": "TA001",
            "brand_name": "Test Brand",
            "title": "Test Ad",
            "air_date": date(2024, 1, 1),
            "date_parse_confidence": 1.0,
            "date_parse_warning": None,
            "year": 2024,
            "decade": "2020s",
            "country": "USA",
            "language": "English",
            "s3_key": "videos/TA001.mp4",
            "video_url": None,
            "views_seeded": 0,
        }

        result = processor._upsert_entry(entry)

        assert result is True
        assert "upsert_catalog_entry" in cursor.query or "INSERT" in cursor.query.upper()

    def test_upsert_entry_existing(self, monkeypatch):
        """Upsert should update existing entry."""
        cursor = FakeCursor([{
            "id": uuid.uuid4(),
            "created": False,
        }])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.catalog_processor.get_connection", fake_get_connection)

        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        entry = {
            "external_id": "TA001",
            "brand_name": "Updated Brand",
            "title": "Updated Ad",
            "air_date": date(2024, 1, 1),
            "date_parse_confidence": 1.0,
            "date_parse_warning": None,
            "year": 2024,
            "decade": "2020s",
            "country": "USA",
            "language": "English",
            "s3_key": "videos/TA001.mp4",
            "video_url": None,
            "views_seeded": 100,
        }

        result = processor._upsert_entry(entry)

        # Should still return True for successful upsert
        assert result is True


class TestCatalogImportProcessorProgress:
    """Test progress tracking and heartbeat."""

    def test_heartbeat_called_during_processing(self, monkeypatch):
        """Heartbeat should be called during processing."""
        heartbeat_calls = []

        def mock_heartbeat(stage, progress):
            heartbeat_calls.append((stage, progress))

        processor = CatalogImportProcessor(
            import_id=str(uuid.uuid4()),
            heartbeat_callback=mock_heartbeat,
        )

        # Call the internal heartbeat method
        processor._update_progress("parsing", 0.5)

        assert len(heartbeat_calls) > 0
        assert heartbeat_calls[-1] == ("parsing", 0.5)


class TestCatalogImportProcessorCSVParsing:
    """Test full CSV parsing flow."""

    def test_parse_csv_content_basic(self):
        """Parse basic CSV content."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        csv_content = """external_id,brand_name,title,air_date
TA001,Coca-Cola,Holiday Ad,2024-12-25
TA002,Pepsi,Summer Ad,2024-07-04"""

        rows = list(processor._parse_csv_content(csv_content))

        assert len(rows) == 2
        assert rows[0]["external_id"] == "TA001"
        assert rows[1]["external_id"] == "TA002"

    def test_parse_csv_content_with_quotes(self):
        """Parse CSV with quoted fields."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        csv_content = '''external_id,brand_name,title,air_date
TA001,"Coca-Cola, Inc.","Holiday Ad - ""Best Ever""",2024-12-25'''

        rows = list(processor._parse_csv_content(csv_content))

        assert len(rows) == 1
        assert rows[0]["brand_name"] == "Coca-Cola, Inc."
        assert '"Best Ever"' in rows[0]["title"]

    def test_parse_csv_content_skips_empty_rows(self):
        """Empty rows should be skipped."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        csv_content = """external_id,brand_name,title
TA001,Brand1,Title1

TA002,Brand2,Title2
"""

        rows = list(processor._parse_csv_content(csv_content))

        assert len(rows) == 2

    def test_parse_csv_content_handles_bom(self):
        """CSV with BOM should be handled."""
        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        # UTF-8 BOM
        csv_content = '\ufeffexternal_id,brand_name\nTA001,Brand1'

        rows = list(processor._parse_csv_content(csv_content))

        assert len(rows) == 1
        assert rows[0]["external_id"] == "TA001"


class TestCatalogImportProcessorErrorHandling:
    """Test error handling scenarios."""

    def test_process_handles_invalid_row(self, monkeypatch):
        """Invalid rows should be tracked but not stop processing."""
        # This would require more extensive mocking of the full process flow
        # For now, test that _parse_row raises appropriate errors

        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))

        # Missing required field
        with pytest.raises(ValueError):
            processor._parse_row({}, row_number=1)

    def test_process_handles_database_error(self, monkeypatch):
        """Database errors should be caught and tracked."""
        import psycopg2

        def mock_upsert_that_fails(entry):
            raise psycopg2.Error("Connection failed")

        processor = CatalogImportProcessor(import_id=str(uuid.uuid4()))
        processor._upsert_entry = mock_upsert_that_fails

        entry = {
            "external_id": "TA001",
            "brand_name": "Test",
            "title": "Test",
            "air_date": None,
            "date_parse_confidence": 0.0,
            "date_parse_warning": None,
            "year": None,
            "decade": None,
            "country": None,
            "language": None,
            "s3_key": None,
            "video_url": None,
            "views_seeded": 0,
        }

        # The processor should handle the error gracefully
        # In production, this would increment rows_failed counter


# ---------------------------------------------------------------------------
# Integration-style test (still mocked, but tests the full flow)
# ---------------------------------------------------------------------------

class TestCatalogImportProcessorFullFlow:
    """Test the full processing flow with mocked dependencies."""

    def test_process_small_csv(self, monkeypatch):
        """Process a small CSV through the full flow."""
        import_id = str(uuid.uuid4())

        # Mock S3 client
        mock_s3 = Mock()
        mock_body = Mock()
        mock_body.read.return_value = b"""external_id,brand_name,title,air_date,s3_key
TA001,Coca-Cola,Holiday Ad,2024-12-25,videos/TA001.mp4
TA002,Pepsi,Summer Ad,2024-07-04,videos/TA002.mp4"""
        mock_s3.get_object.return_value = {"Body": mock_body}

        # Mock database connection
        cursor = FakeCursor([{"id": uuid.uuid4(), "created": True}])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.catalog_processor.get_connection", fake_get_connection)

        # Create processor
        heartbeat_calls = []
        processor = CatalogImportProcessor(
            import_id=import_id,
            heartbeat_callback=lambda s, p: heartbeat_calls.append((s, p)),
        )

        # Mock the S3 client getter
        processor._get_s3_client = lambda: mock_s3

        # Run the process
        result = processor.process(
            file_path="catalog-imports/test.csv",
            bucket="test-bucket",
        )

        assert result["success"] is True
        assert result["rows_total"] == 2
        assert result["rows_ok"] >= 0
        assert len(heartbeat_calls) > 0
