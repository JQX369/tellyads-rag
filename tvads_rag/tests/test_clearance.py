"""
Tests for regulatory clearance inference from external_id prefixes.
"""

import pytest

from tvads_rag.clearance import (
    ClearanceInfo,
    CLEARANCE_PREFIXES,
    infer_clearance_from_external_id,
    enrich_ad_data_with_clearance,
)


# =============================================================================
# Test Constants
# =============================================================================

class TestClearancePrefixes:
    """Test clearance prefix mapping."""

    def test_ta_prefix_maps_to_uk_clearcast(self):
        """TA prefix should map to UK Clearcast."""
        assert "TA" in CLEARANCE_PREFIXES
        body, country = CLEARANCE_PREFIXES["TA"]
        assert body == "UK Clearcast"
        assert country == "UK"


# =============================================================================
# Test Inference
# =============================================================================

class TestInferClearance:
    """Test clearance inference from external_id."""

    def test_ta_prefix_infers_uk_clearcast(self):
        """External ID starting with TA should infer UK Clearcast."""
        result = infer_clearance_from_external_id("TABC12345")

        assert result is not None
        assert result.body == "UK Clearcast"
        assert result.country == "UK"
        assert result.clearance_id == "TABC12345"

    def test_ta_lowercase_still_infers(self):
        """External ID with lowercase TA should still infer."""
        result = infer_clearance_from_external_id("tabc12345")

        assert result is not None
        assert result.body == "UK Clearcast"
        assert result.country == "UK"

    def test_non_ta_prefix_returns_none(self):
        """External ID without known prefix should return None."""
        result = infer_clearance_from_external_id("XXYZ98765")

        assert result is None

    def test_empty_external_id_returns_none(self):
        """Empty external_id should return None."""
        assert infer_clearance_from_external_id("") is None
        assert infer_clearance_from_external_id(None) is None

    def test_partial_match_not_confused(self):
        """External ID containing TA but not at start should not match."""
        result = infer_clearance_from_external_id("NOTAPREFIX")

        # Should NOT match because TA is not at the start
        assert result is None


# =============================================================================
# Test Enrichment
# =============================================================================

class TestEnrichAdData:
    """Test ad_data enrichment with clearance fields."""

    def test_enriches_ta_ad_data(self):
        """Ad data with TA external_id should be enriched."""
        ad_data = {
            "external_id": "TABC99999",
            "brand_name": "Test Brand",
        }

        result = enrich_ad_data_with_clearance(ad_data)

        assert result["clearance_body"] == "UK Clearcast"
        assert result["clearance_country"] == "UK"
        assert result["clearance_id"] == "TABC99999"

    def test_preserves_existing_clearance(self):
        """Should not overwrite existing clearance_body."""
        ad_data = {
            "external_id": "TABC99999",
            "clearance_body": "Manual Override",
            "clearance_country": "FR",
        }

        result = enrich_ad_data_with_clearance(ad_data)

        # Should preserve existing values
        assert result["clearance_body"] == "Manual Override"
        assert result["clearance_country"] == "FR"

    def test_no_enrichment_for_unknown_prefix(self):
        """Ad data without known prefix should not be enriched."""
        ad_data = {
            "external_id": "XXYZ12345",
            "brand_name": "Unknown Brand",
        }

        result = enrich_ad_data_with_clearance(ad_data)

        assert "clearance_body" not in result or result.get("clearance_body") is None

    def test_no_crash_on_missing_external_id(self):
        """Should handle missing external_id gracefully."""
        ad_data = {"brand_name": "No External ID"}

        result = enrich_ad_data_with_clearance(ad_data)

        assert result == ad_data  # Unchanged


# =============================================================================
# Test DB Column Presence
# =============================================================================

class TestDBColumns:
    """Test that clearance columns are in AD_COLUMNS."""

    def test_clearance_body_in_ad_columns(self):
        """clearance_body should be in AD_COLUMNS."""
        from tvads_rag.db import AD_COLUMNS
        assert "clearance_body" in AD_COLUMNS

    def test_clearance_id_in_ad_columns(self):
        """clearance_id should be in AD_COLUMNS."""
        from tvads_rag.db import AD_COLUMNS
        assert "clearance_id" in AD_COLUMNS

    def test_clearance_country_in_ad_columns(self):
        """clearance_country should be in AD_COLUMNS."""
        from tvads_rag.db import AD_COLUMNS
        assert "clearance_country" in AD_COLUMNS


# =============================================================================
# Test Migration File
# =============================================================================

class TestMigrationFile:
    """Test migration file exists and has correct content."""

    def test_migration_file_exists(self):
        """Migration file should exist."""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations", "archived", "schema_clearance.sql"
        )
        assert os.path.exists(migration_path)

    def test_migration_has_clearance_body_column(self):
        """Migration should add clearance_body column."""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations", "archived", "schema_clearance.sql"
        )
        with open(migration_path) as f:
            content = f.read()

        assert "clearance_body" in content
        assert "IF NOT EXISTS" in content

    def test_migration_has_clearance_id_column(self):
        """Migration should add clearance_id column."""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations", "archived", "schema_clearance.sql"
        )
        with open(migration_path) as f:
            content = f.read()

        assert "clearance_id" in content

    def test_migration_has_clearance_country_column(self):
        """Migration should add clearance_country column."""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations", "archived", "schema_clearance.sql"
        )
        with open(migration_path) as f:
            content = f.read()

        assert "clearance_country" in content
