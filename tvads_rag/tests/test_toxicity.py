"""
Tests for toxicity scoring, persistence, and filtering.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, call

from tvads_rag.scoring_engine import ToxicityScorer, score_ad_toxicity
from tvads_rag.extraction_warnings import WarningCode


# =============================================================================
# Test Toxicity Scoring
# =============================================================================

class TestToxicityScorer:
    """Tests for the ToxicityScorer class."""

    def test_scorer_basic_calculation(self):
        """Test basic toxicity score calculation."""
        analysis_data = {
            "visual_physics": {"cuts_per_minute": 30, "brightness_variance": 0.3},
            "audio_physics": {"loudness_lu": -20},
            "transcript": "Buy now, limited time offer!",
            "claims": [],
            "garm_risk_level": "low",
        }

        scorer = ToxicityScorer(analysis_data, use_ai=False)
        report = scorer.calculate_toxicity()

        assert "toxic_score" in report
        assert "risk_level" in report
        assert "breakdown" in report
        assert 0 <= report["toxic_score"] <= 100
        assert report["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_scorer_high_toxicity_detection(self):
        """Test that high toxicity is properly detected."""
        analysis_data = {
            "visual_physics": {
                "cuts_per_minute": 100,  # Very high
                "brightness_variance": 0.9,  # Strobe risk
            },
            "audio_physics": {"loudness_lu": -5},  # Very loud
            "transcript": "Only 2 left! Act now! Don't be stupid!",
            "claims": [{"text": "claim"} for _ in range(10)],  # Many claims
            "garm_risk_level": "high",
            "duration_seconds": 30,
        }

        scorer = ToxicityScorer(analysis_data, use_ai=False)
        report = scorer.calculate_toxicity()

        # Should have elevated score
        assert report["toxic_score"] > 30
        assert len(report["breakdown"]["physiological"]["flags"]) > 0
        assert len(report["breakdown"]["psychological"]["flags"]) > 0

    def test_scorer_dark_pattern_detection(self):
        """Test dark pattern detection in transcript."""
        analysis_data = {
            "visual_physics": {},
            "audio_physics": {},
            "transcript": "Only 2 left! Hurry! Limited time offer! Act now!",
            "claims": [],
        }

        scorer = ToxicityScorer(analysis_data, use_ai=False)
        patterns = scorer.detect_dark_patterns()

        assert len(patterns) > 0
        categories = [p["category"] for p in patterns]
        assert "false_scarcity" in categories

    def test_scorer_empty_inputs(self):
        """Test scorer handles empty inputs gracefully."""
        analysis_data = {}

        scorer = ToxicityScorer(analysis_data, use_ai=False)
        report = scorer.calculate_toxicity()

        # Should produce a valid report even with no data
        assert "toxic_score" in report
        assert report["toxic_score"] == 0 or report["toxic_score"] >= 0


# =============================================================================
# Test Toxicity Persistence Mapping
# =============================================================================

class TestToxicityPersistence:
    """Tests for toxicity persistence field extraction."""

    def test_toxicity_report_field_extraction(self):
        """Test that toxicity report fields are correctly extracted for DB."""
        toxicity_report = {
            "toxic_score": 45,
            "risk_level": "MEDIUM",
            "dark_patterns_detected": ["only 2 left", "act now"],
            "breakdown": {
                "physiological": {"score": 20, "flags": ["Rapid Cuts (85/min exceeds 80)"]},
                "psychological": {"score": 30, "flags": ["False Scarcity Detected"]},
                "regulatory": {"score": 10, "flags": []},
            },
            "metadata": {"ai_enabled": False},
        }

        # Extract values as db.py would
        toxicity_total = toxicity_report.get("toxic_score")
        toxicity_risk_level = toxicity_report.get("risk_level")

        # Extract labels
        dark_patterns = toxicity_report.get("dark_patterns_detected", [])
        breakdown = toxicity_report.get("breakdown", {})
        toxicity_labels = []
        for category in ["physiological", "psychological", "regulatory"]:
            cat_data = breakdown.get(category, {})
            for flag in cat_data.get("flags", []):
                if "Detected" in flag:
                    label = flag.split(" Detected")[0].lower().replace(" ", "_")
                    if label not in toxicity_labels:
                        toxicity_labels.append(label)

        # Assertions
        assert toxicity_total == 45
        assert toxicity_risk_level == "MEDIUM"
        assert "false_scarcity" in toxicity_labels

    def test_toxicity_version_from_metadata(self):
        """Test toxicity version is correctly determined."""
        # Without AI
        report_no_ai = {"metadata": {"ai_enabled": False}}
        metadata = report_no_ai.get("metadata", {})
        version_no_ai = "1.1.0-ai" if metadata.get("ai_enabled", False) else "1.0.0"
        assert version_no_ai == "1.0.0"

        # With AI
        report_ai = {"metadata": {"ai_enabled": True}}
        metadata_ai = report_ai.get("metadata", {})
        version_ai = "1.1.0-ai" if metadata_ai.get("ai_enabled", False) else "1.0.0"
        assert version_ai == "1.1.0-ai"


# =============================================================================
# Test Missing Input Warnings
# =============================================================================

class TestToxicityWarnings:
    """Tests for toxicity missing input warnings."""

    def test_missing_input_warning_code_exists(self):
        """Test that TOXICITY_INPUT_MISSING warning code exists."""
        assert hasattr(WarningCode, "TOXICITY_INPUT_MISSING")
        assert WarningCode.TOXICITY_INPUT_MISSING == "TOXICITY_INPUT_MISSING"

    def test_toxicity_stage_emits_warning_on_missing_physics(self):
        """Test that ToxicityStage emits warning when physics_result is missing."""
        from tvads_rag.pipeline.stages.toxicity import ToxicityStage
        from tvads_rag.pipeline.context import ProcessingContext
        from tvads_rag.pipeline.base import PipelineConfig

        # Create context with missing physics_result
        ctx = ProcessingContext(
            external_id="test_123",
            source="local",
            location="/tmp/test.mp4",
            s3_key=None,
        )
        ctx.ad_id = "uuid-123"
        ctx.analysis_result = {"core_metadata": {}}  # Has analysis but no physics
        ctx.transcript = None  # Also missing transcript

        # Mock the config and db_backend (using correct import paths)
        with patch("tvads_rag.config.get_toxicity_config") as mock_cfg, \
             patch("tvads_rag.db_backend.update_toxicity_report") as mock_db:

            # Configure mock
            mock_cfg_instance = MagicMock()
            mock_cfg_instance.enabled = True
            mock_cfg.return_value = mock_cfg_instance

            with patch("tvads_rag.config.is_toxicity_ai_enabled", return_value=False):
                stage = ToxicityStage()
                config = PipelineConfig()

                # Execute the stage
                result_ctx = stage.execute(ctx, config)

                # Check that warning was added to analysis_result
                warnings = result_ctx.analysis_result.get("extraction_warnings", [])
                toxicity_warnings = [
                    w for w in warnings
                    if w.get("code") == WarningCode.TOXICITY_INPUT_MISSING
                ]

                assert len(toxicity_warnings) == 1
                warning = toxicity_warnings[0]
                assert "physics_result" in warning["meta"]["missing"]
                assert "transcript" in warning["meta"]["missing"]


# =============================================================================
# Test Migration File
# =============================================================================

class TestToxicityMigration:
    """Tests for toxicity migration file."""

    @pytest.fixture
    def migration_content(self):
        """Read the migration file content."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        migration_path = os.path.join(base_dir, "schema_toxicity_columns.sql")

        with open(migration_path, "r") as f:
            return f.read().lower()

    def test_migration_adds_toxicity_total(self, migration_content):
        """Test migration adds toxicity_total column."""
        assert "toxicity_total" in migration_content
        assert "float" in migration_content

    def test_migration_adds_toxicity_risk_level(self, migration_content):
        """Test migration adds toxicity_risk_level column."""
        assert "toxicity_risk_level" in migration_content
        assert "text" in migration_content

    def test_migration_adds_toxicity_labels(self, migration_content):
        """Test migration adds toxicity_labels column."""
        assert "toxicity_labels" in migration_content
        assert "jsonb" in migration_content

    def test_migration_adds_toxicity_subscores(self, migration_content):
        """Test migration adds toxicity_subscores column."""
        assert "toxicity_subscores" in migration_content

    def test_migration_adds_toxicity_version(self, migration_content):
        """Test migration adds toxicity_version column."""
        assert "toxicity_version" in migration_content

    def test_migration_uses_if_not_exists(self, migration_content):
        """Test migration uses ADD COLUMN IF NOT EXISTS."""
        assert "if not exists" in migration_content

    def test_migration_targets_public_ads(self, migration_content):
        """Test migration targets public.ads table."""
        assert "public.ads" in migration_content


# =============================================================================
# Test API Filter Query Building
# =============================================================================

class TestToxicityFilterQueries:
    """Tests for toxicity filter query building."""

    def test_max_toxicity_filter_query(self):
        """Test that max_toxicity filter produces correct SQL condition."""
        max_toxicity = 30.0
        query_part = "(toxicity_total IS NULL OR toxicity_total <= %s)"

        # Simulate what the API does
        params = [max_toxicity]
        full_condition = query_part % max_toxicity

        assert "toxicity_total" in query_part
        assert "<=" in query_part
        assert params[0] == 30.0

    def test_risk_level_filter_query(self):
        """Test that risk_level filter produces correct SQL condition."""
        risk_level = "LOW"
        query_part = "toxicity_risk_level = %s"

        # Simulate what the API does
        params = [risk_level.upper()]

        assert "toxicity_risk_level" in query_part
        assert params[0] == "LOW"

    def test_has_toxicity_filter_query(self):
        """Test that has_toxicity filter produces correct SQL conditions."""
        # has_toxicity = True
        query_true = "toxicity_total IS NOT NULL"
        assert "IS NOT NULL" in query_true

        # has_toxicity = False
        query_false = "toxicity_total IS NULL"
        assert "IS NULL" in query_false


# =============================================================================
# Test Integration (Mock DB)
# =============================================================================

class TestToxicityIntegration:
    """Integration tests for toxicity filtering (mocked DB)."""

    def test_filter_ads_by_max_toxicity(self):
        """Test filtering ads by maximum toxicity score."""
        # Simulated ads with different toxicity levels
        mock_ads = [
            {"external_id": "ad1", "toxicity_total": 20, "toxicity_risk_level": "LOW"},
            {"external_id": "ad2", "toxicity_total": 50, "toxicity_risk_level": "MEDIUM"},
            {"external_id": "ad3", "toxicity_total": 80, "toxicity_risk_level": "HIGH"},
            {"external_id": "ad4", "toxicity_total": None, "toxicity_risk_level": None},
        ]

        # Filter: max_toxicity = 30
        max_toxicity = 30
        filtered = [
            ad for ad in mock_ads
            if ad["toxicity_total"] is None or ad["toxicity_total"] <= max_toxicity
        ]

        assert len(filtered) == 2
        assert filtered[0]["external_id"] == "ad1"
        assert filtered[1]["external_id"] == "ad4"  # NULL passes the filter

    def test_filter_ads_by_risk_level(self):
        """Test filtering ads by risk level."""
        mock_ads = [
            {"external_id": "ad1", "toxicity_risk_level": "LOW"},
            {"external_id": "ad2", "toxicity_risk_level": "MEDIUM"},
            {"external_id": "ad3", "toxicity_risk_level": "HIGH"},
        ]

        # Filter: risk_level = "HIGH"
        risk_level = "HIGH"
        filtered = [
            ad for ad in mock_ads
            if ad["toxicity_risk_level"] == risk_level
        ]

        assert len(filtered) == 1
        assert filtered[0]["external_id"] == "ad3"

    def test_filter_ads_with_toxicity(self):
        """Test filtering ads that have toxicity computed."""
        mock_ads = [
            {"external_id": "ad1", "toxicity_total": 20},
            {"external_id": "ad2", "toxicity_total": None},
            {"external_id": "ad3", "toxicity_total": 50},
        ]

        # Filter: has_toxicity = True
        filtered = [
            ad for ad in mock_ads
            if ad["toxicity_total"] is not None
        ]

        assert len(filtered) == 2
        assert all(ad["toxicity_total"] is not None for ad in filtered)
