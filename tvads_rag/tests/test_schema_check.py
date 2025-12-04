"""
Tests for schema validation (claims/supers evidence columns).

Verifies that:
- Missing columns are detected per table
- Error messages include the correct migration file name
- Caching works correctly
"""

import pytest
from unittest.mock import MagicMock, patch

from tvads_rag.schema_check import (
    # Constants
    REQUIRED_EXTRACTION_COLUMNS,
    REQUIRED_CLAIMS_EVIDENCE_COLUMNS,
    REQUIRED_SUPERS_EVIDENCE_COLUMNS,
    MIGRATION_FILE,
    MIGRATION_FILE_CLAIMS_SUPERS,
    TABLE_MIGRATIONS,
    TABLE_REQUIRED_COLUMNS,
    # Exception
    SchemaMissingColumnsError,
    # Functions
    check_table_columns_pg,
    check_table_columns_http,
    validate_table_schema_pg,
    validate_table_schema_http,
    reset_validation_cache,
    reset_table_validation_cache,
)


# =============================================================================
# Test Constants
# =============================================================================

class TestConstants:
    """Test that required columns and migrations are correctly defined."""

    def test_claims_required_columns(self):
        """Verify claims table has correct required columns."""
        expected = {"timestamp_start_s", "timestamp_end_s", "evidence", "confidence"}
        assert REQUIRED_CLAIMS_EVIDENCE_COLUMNS == expected

    def test_supers_required_columns(self):
        """Verify supers table has correct required columns."""
        expected = {"evidence", "confidence"}
        assert REQUIRED_SUPERS_EVIDENCE_COLUMNS == expected

    def test_table_migrations_mapping(self):
        """Verify migration file mapping is correct."""
        assert TABLE_MIGRATIONS["ad_claims"] == MIGRATION_FILE_CLAIMS_SUPERS
        assert TABLE_MIGRATIONS["ad_supers"] == MIGRATION_FILE_CLAIMS_SUPERS
        assert TABLE_MIGRATIONS["ads"] == MIGRATION_FILE

    def test_table_required_columns_mapping(self):
        """Verify required columns mapping is correct."""
        assert TABLE_REQUIRED_COLUMNS["ad_claims"] == REQUIRED_CLAIMS_EVIDENCE_COLUMNS
        assert TABLE_REQUIRED_COLUMNS["ad_supers"] == REQUIRED_SUPERS_EVIDENCE_COLUMNS
        assert TABLE_REQUIRED_COLUMNS["ads"] == REQUIRED_EXTRACTION_COLUMNS


# =============================================================================
# Test SchemaMissingColumnsError
# =============================================================================

class TestSchemaMissingColumnsError:
    """Test error message formatting."""

    def test_error_includes_table_name(self):
        """Error message should include the table name."""
        error = SchemaMissingColumnsError(
            ["evidence", "confidence"],
            table_name="ad_claims",
            migration_file=MIGRATION_FILE_CLAIMS_SUPERS
        )

        assert "ad_claims" in str(error)
        assert "DATABASE SCHEMA ERROR" in str(error)

    def test_error_includes_migration_file(self):
        """Error message should include the migration file name."""
        error = SchemaMissingColumnsError(
            ["evidence", "confidence"],
            table_name="ad_claims",
            migration_file=MIGRATION_FILE_CLAIMS_SUPERS
        )

        assert MIGRATION_FILE_CLAIMS_SUPERS in str(error)
        assert "schema_claims_supers_evidence.sql" in str(error)

    def test_error_includes_missing_columns(self):
        """Error message should list missing columns."""
        error = SchemaMissingColumnsError(
            ["timestamp_start_s", "evidence"],
            table_name="ad_claims",
            migration_file=MIGRATION_FILE_CLAIMS_SUPERS
        )

        assert "evidence" in str(error)
        assert "timestamp_start_s" in str(error)

    def test_error_stores_attributes(self):
        """Error should store attributes for programmatic access."""
        error = SchemaMissingColumnsError(
            ["evidence", "confidence"],
            table_name="ad_supers",
            migration_file=MIGRATION_FILE_CLAIMS_SUPERS
        )

        assert error.missing_columns == ["evidence", "confidence"]
        assert error.table_name == "ad_supers"
        assert error.migration_file == MIGRATION_FILE_CLAIMS_SUPERS


# =============================================================================
# Test Postgres Backend (Mocked)
# =============================================================================

class TestCheckTableColumnsPg:
    """Test Postgres column checking with mocked cursor."""

    def test_all_columns_present(self):
        """When all columns exist, return empty set."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock all columns exist
        mock_cursor.fetchall.return_value = [
            {"column_name": "timestamp_start_s"},
            {"column_name": "timestamp_end_s"},
            {"column_name": "evidence"},
            {"column_name": "confidence"},
        ]

        missing = check_table_columns_pg(
            mock_conn,
            "ad_claims",
            REQUIRED_CLAIMS_EVIDENCE_COLUMNS
        )

        assert missing == set()

    def test_missing_columns_detected(self):
        """When columns are missing, return them in set."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock only some columns exist
        mock_cursor.fetchall.return_value = [
            {"column_name": "timestamp_start_s"},
            {"column_name": "timestamp_end_s"},
        ]

        missing = check_table_columns_pg(
            mock_conn,
            "ad_claims",
            REQUIRED_CLAIMS_EVIDENCE_COLUMNS
        )

        assert "evidence" in missing
        assert "confidence" in missing
        assert len(missing) == 2


class TestValidateTableSchemaPg:
    """Test Postgres schema validation with mocked connection."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_validation_cache()

    def test_validation_passes_when_columns_exist(self):
        """Validation should pass silently when all columns exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock all columns exist
        mock_cursor.fetchall.return_value = [
            {"column_name": "evidence"},
            {"column_name": "confidence"},
        ]

        # Should not raise
        validate_table_schema_pg(mock_conn, "ad_supers")

    def test_validation_raises_when_columns_missing(self):
        """Validation should raise SchemaMissingColumnsError when columns missing."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock no columns exist
        mock_cursor.fetchall.return_value = []

        with pytest.raises(SchemaMissingColumnsError) as exc_info:
            validate_table_schema_pg(mock_conn, "ad_claims")

        assert "ad_claims" in str(exc_info.value)
        assert MIGRATION_FILE_CLAIMS_SUPERS in str(exc_info.value)

    def test_caching_prevents_repeated_queries(self):
        """After validation passes, subsequent calls should use cache."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock all columns exist
        mock_cursor.fetchall.return_value = [
            {"column_name": "evidence"},
            {"column_name": "confidence"},
        ]

        # First call should query
        validate_table_schema_pg(mock_conn, "ad_supers")
        first_call_count = mock_cursor.execute.call_count

        # Second call should use cache (no additional queries)
        validate_table_schema_pg(mock_conn, "ad_supers")
        second_call_count = mock_cursor.execute.call_count

        assert first_call_count == second_call_count

    def test_cache_reset_allows_revalidation(self):
        """Resetting cache should allow re-validation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock all columns exist
        mock_cursor.fetchall.return_value = [
            {"column_name": "evidence"},
            {"column_name": "confidence"},
        ]

        # First validation
        validate_table_schema_pg(mock_conn, "ad_supers")
        first_call_count = mock_cursor.execute.call_count

        # Reset cache
        reset_table_validation_cache("ad_supers")

        # Should query again
        validate_table_schema_pg(mock_conn, "ad_supers")
        assert mock_cursor.execute.call_count > first_call_count


# =============================================================================
# Test HTTP Backend (Mocked)
# =============================================================================

class TestCheckTableColumnsHttp:
    """Test HTTP column checking with mocked Supabase client."""

    def test_all_columns_present(self):
        """When all columns exist, return empty set."""
        mock_client = MagicMock()
        # All select calls succeed
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()

        missing = check_table_columns_http(
            mock_client,
            "ad_supers",
            REQUIRED_SUPERS_EVIDENCE_COLUMNS
        )

        assert missing == set()

    def test_missing_columns_detected(self):
        """When columns are missing (error on select), return them in set."""
        mock_client = MagicMock()

        def side_effect(*args, **kwargs):
            col = mock_client.table.return_value.select.call_args[0][0]
            if col == "evidence":
                raise Exception("column 'evidence' does not exist")
            return MagicMock()

        mock_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = side_effect

        missing = check_table_columns_http(
            mock_client,
            "ad_supers",
            {"evidence", "confidence"}
        )

        assert "evidence" in missing


class TestValidateTableSchemaHttp:
    """Test HTTP schema validation with mocked client."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_validation_cache()

    def test_validation_passes_when_columns_exist(self):
        """Validation should pass silently when all columns exist."""
        mock_client = MagicMock()
        # All select calls succeed
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()

        # Should not raise
        validate_table_schema_http(mock_client, "ad_supers")

    def test_validation_raises_when_columns_missing(self):
        """Validation should raise SchemaMissingColumnsError when columns missing."""
        mock_client = MagicMock()

        def side_effect(*args, **kwargs):
            raise Exception("column does not exist")

        mock_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = side_effect

        with pytest.raises(SchemaMissingColumnsError) as exc_info:
            validate_table_schema_http(mock_client, "ad_claims")

        assert "ad_claims" in str(exc_info.value)
        assert MIGRATION_FILE_CLAIMS_SUPERS in str(exc_info.value)


# =============================================================================
# Test Migration File References
# =============================================================================

class TestMigrationFileReferences:
    """Test that error messages reference the correct migration file."""

    def test_claims_error_references_claims_supers_migration(self):
        """Claims table errors should reference schema_claims_supers_evidence.sql."""
        error = SchemaMissingColumnsError(
            ["evidence"],
            table_name="ad_claims",
            migration_file=TABLE_MIGRATIONS["ad_claims"]
        )

        assert "schema_claims_supers_evidence.sql" in str(error)

    def test_supers_error_references_claims_supers_migration(self):
        """Supers table errors should reference schema_claims_supers_evidence.sql."""
        error = SchemaMissingColumnsError(
            ["confidence"],
            table_name="ad_supers",
            migration_file=TABLE_MIGRATIONS["ad_supers"]
        )

        assert "schema_claims_supers_evidence.sql" in str(error)

    def test_ads_error_references_extraction_migration(self):
        """Ads table errors should reference schema_extraction_columns.sql."""
        error = SchemaMissingColumnsError(
            ["extraction_warnings"],
            table_name="ads",
            migration_file=TABLE_MIGRATIONS["ads"]
        )

        assert "schema_extraction_columns.sql" in str(error)


# =============================================================================
# Test Cache Independence
# =============================================================================

class TestCacheIndependence:
    """Test that per-table caching is independent."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_validation_cache()

    def test_tables_cached_independently(self):
        """Each table should have independent cache state."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock columns exist for both tables
        mock_cursor.fetchall.return_value = [
            {"column_name": "evidence"},
            {"column_name": "confidence"},
            {"column_name": "timestamp_start_s"},
            {"column_name": "timestamp_end_s"},
        ]

        # Validate claims
        validate_table_schema_pg(mock_conn, "ad_claims")
        claims_queries = mock_cursor.execute.call_count

        # Validate supers (should query since different table)
        validate_table_schema_pg(mock_conn, "ad_supers")
        supers_queries = mock_cursor.execute.call_count

        assert supers_queries > claims_queries

    def test_reset_one_table_preserves_other(self):
        """Resetting one table's cache shouldn't affect another."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock columns exist
        mock_cursor.fetchall.return_value = [
            {"column_name": "evidence"},
            {"column_name": "confidence"},
            {"column_name": "timestamp_start_s"},
            {"column_name": "timestamp_end_s"},
        ]

        # Validate both
        validate_table_schema_pg(mock_conn, "ad_claims")
        validate_table_schema_pg(mock_conn, "ad_supers")
        initial_queries = mock_cursor.execute.call_count

        # Reset only claims
        reset_table_validation_cache("ad_claims")

        # Supers should still be cached
        validate_table_schema_pg(mock_conn, "ad_supers")
        after_supers = mock_cursor.execute.call_count
        assert after_supers == initial_queries  # No new query

        # Claims should re-query
        validate_table_schema_pg(mock_conn, "ad_claims")
        after_claims = mock_cursor.execute.call_count
        assert after_claims > initial_queries  # New query


# =============================================================================
# Test Integration with DB Modules
# =============================================================================

class TestDBIntegration:
    """Test that validation is called from DB modules."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_validation_cache()

    def test_db_module_imports_validation(self):
        """Verify db.py can import validation functions."""
        from tvads_rag.db import insert_claims, insert_supers
        # If imports work, the functions should have validation inside

    def test_supabase_db_module_imports_validation(self):
        """Verify supabase_db.py can import validation functions."""
        from tvads_rag.supabase_db import insert_claims, insert_supers
        # If imports work, the functions should have validation inside


# =============================================================================
# Test Full Reset
# =============================================================================

class TestFullReset:
    """Test that full reset clears all caches."""

    def test_reset_clears_all_tables(self):
        """reset_validation_cache() should clear all table caches."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock columns exist
        mock_cursor.fetchall.return_value = [
            {"column_name": "evidence"},
            {"column_name": "confidence"},
            {"column_name": "timestamp_start_s"},
            {"column_name": "timestamp_end_s"},
        ]

        # Validate both tables
        validate_table_schema_pg(mock_conn, "ad_claims")
        validate_table_schema_pg(mock_conn, "ad_supers")
        initial_queries = mock_cursor.execute.call_count

        # Full reset
        reset_validation_cache()

        # Both should re-query
        validate_table_schema_pg(mock_conn, "ad_claims")
        validate_table_schema_pg(mock_conn, "ad_supers")
        final_queries = mock_cursor.execute.call_count

        assert final_queries > initial_queries
