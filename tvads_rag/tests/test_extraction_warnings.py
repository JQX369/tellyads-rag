"""
Tests for extraction warnings and fill-rate utilities.
"""

import pytest
from datetime import datetime

from tvads_rag.extraction_warnings import (
    WarningCode,
    create_warning,
    add_warning,
    compute_fill_rates,
    validate_extraction,
    ensure_warnings_and_fill_rate,
    CRITICAL_SECTIONS,
    FILLABLE_FIELDS,
)


# =============================================================================
# Test Warning Creation
# =============================================================================

class TestWarningCreation:
    """Tests for warning creation functions."""

    def test_create_warning_basic(self):
        """Test basic warning creation."""
        warning = create_warning(
            WarningCode.SCORE_CLAMPED,
            "Score was clamped",
            {"field": "impact_scores.hook_power", "original": 15, "clamped": 10}
        )

        assert warning["code"] == WarningCode.SCORE_CLAMPED
        assert warning["message"] == "Score was clamped"
        assert warning["meta"]["field"] == "impact_scores.hook_power"
        assert warning["meta"]["original"] == 15
        assert "ts" in warning  # Timestamp should be present

    def test_create_warning_no_meta(self):
        """Test warning creation without metadata."""
        warning = create_warning(WarningCode.TRANSCRIPT_EMPTY, "No transcript")

        assert warning["code"] == WarningCode.TRANSCRIPT_EMPTY
        assert warning["meta"] == {}

    def test_add_warning_to_dict(self):
        """Test adding warning to analysis dict."""
        analysis = {}
        add_warning(
            analysis,
            WarningCode.JSON_REPAIRED,
            "JSON was repaired",
            {"original_length": 1000},
            log_level="debug"
        )

        assert "extraction_warnings" in analysis
        assert len(analysis["extraction_warnings"]) == 1
        assert analysis["extraction_warnings"][0]["code"] == WarningCode.JSON_REPAIRED

    def test_add_warning_to_list(self):
        """Test adding warning to warnings list."""
        warnings = []
        add_warning(
            warnings,
            WarningCode.SCORE_DEFAULTED,
            "Score defaulted",
            {"field": "overall_impact"}
        )

        assert len(warnings) == 1
        assert warnings[0]["code"] == WarningCode.SCORE_DEFAULTED

    def test_add_multiple_warnings(self):
        """Test adding multiple warnings."""
        analysis = {"extraction_warnings": []}

        add_warning(analysis, WarningCode.SCORE_CLAMPED, "First warning")
        add_warning(analysis, WarningCode.SCORE_DEFAULTED, "Second warning")
        add_warning(analysis, WarningCode.SECTION_MISSING, "Third warning")

        assert len(analysis["extraction_warnings"]) == 3


# =============================================================================
# Test Fill Rate Computation
# =============================================================================

class TestFillRateComputation:
    """Tests for fill rate computation."""

    def test_fill_rate_empty_analysis(self):
        """Test fill rate for empty analysis dict."""
        fill_rates = compute_fill_rates({})

        assert fill_rates["overall"] == 0.0
        assert fill_rates["filled_fields"] == 0
        assert len(fill_rates["missing_top"]) > 0
        assert len(fill_rates["critical_sections_missing"]) == len(CRITICAL_SECTIONS)

    def test_fill_rate_complete_analysis(self):
        """Test fill rate for complete analysis dict."""
        analysis = {
            "core_metadata": {
                "brand_name": "TestBrand",
                "product_name": "TestProduct",
                "product_category": "technology",
                "country": "US",
                "language": "en",
            },
            "campaign_strategy": {
                "objective": "awareness",
                "funnel_stage": "consideration",
                "format_type": "testimonial",
            },
            "creative_flags": {
                "has_voiceover": True,
                "has_dialogue": False,
                "has_on_screen_text": True,
                "has_celebrity": False,
                "has_ugc_style": False,
                "has_supers": True,
                "has_price_claims": False,
                "has_risk_disclaimer": False,
            },
            "impact_scores": {
                "overall_impact": {"score": 7.5},
                "pulse_score": {"score": 6.0},
                "echo_score": {"score": 7.0},
                "hook_power": {"score": 8.0},
                "brand_integration": {"score": 7.5},
                "emotional_resonance": {"score": 6.5},
                "clarity_score": {"score": 8.0},
                "distinctiveness": {"score": 7.0},
            },
        }

        fill_rates = compute_fill_rates(analysis)

        # Core sections should be 100% filled
        assert fill_rates["by_section"]["core_metadata"] == 1.0
        assert fill_rates["by_section"]["campaign_strategy"] == 1.0
        assert fill_rates["by_section"]["creative_flags"] == 1.0
        assert fill_rates["by_section"]["impact_scores"] == 1.0

        # All critical sections should be present
        assert len(fill_rates["critical_sections_present"]) == len(CRITICAL_SECTIONS)
        assert len(fill_rates["critical_sections_missing"]) == 0

    def test_fill_rate_partial_analysis(self):
        """Test fill rate for partially filled analysis."""
        analysis = {
            "core_metadata": {
                "brand_name": "TestBrand",
                # Missing: product_name, product_category, country, language
            },
            "impact_scores": {
                "overall_impact": {"score": 7.5},
                # Missing other scores
            },
        }

        fill_rates = compute_fill_rates(analysis)

        assert fill_rates["by_section"]["core_metadata"] == 0.2  # 1/5 fields
        assert fill_rates["by_section"]["impact_scores"] == 0.125  # 1/8 fields
        assert "core_metadata.product_name" in fill_rates["missing_top"]

    def test_fill_rate_missing_top_sorted_by_critical(self):
        """Test that missing_top is sorted with critical fields first."""
        analysis = {
            "effectiveness_drivers": {
                "strengths": [],  # Non-critical section with missing fields
            }
        }

        fill_rates = compute_fill_rates(analysis)

        # Critical sections should come first in missing_top
        if fill_rates["missing_top"]:
            first_section = fill_rates["missing_top"][0].split(".")[0]
            assert first_section in CRITICAL_SECTIONS


# =============================================================================
# Test Validation
# =============================================================================

class TestValidation:
    """Tests for structural and semantic validation."""

    def test_validate_not_dict(self):
        """Test validation fails for non-dict input."""
        result = validate_extraction("not a dict")

        assert result["valid"] is False
        assert "not a dict" in result["errors"][0]

    def test_validate_missing_critical_sections(self):
        """Test validation identifies missing critical sections."""
        analysis = {"some_field": "value"}
        result = validate_extraction(analysis)

        assert result["valid"] is False
        for section in CRITICAL_SECTIONS:
            assert any(section in err for err in result["errors"])

    def test_validate_score_out_of_range(self):
        """Test validation warns on scores outside 0-10."""
        warnings = []
        analysis = {
            "core_metadata": {},
            "campaign_strategy": {},
            "creative_flags": {},
            "impact_scores": {
                "hook_power": {"score": 15.0},  # Invalid: > 10
                "overall_impact": {"score": -5.0},  # Invalid: < 0
            },
        }

        result = validate_extraction(analysis, warnings)

        # Should have warnings for out-of-range scores
        range_warnings = [w for w in warnings if w["code"] == WarningCode.VALIDATION_FAILED]
        assert len(range_warnings) >= 2

    def test_validate_valid_analysis(self):
        """Test validation passes for valid analysis."""
        analysis = {
            "core_metadata": {"brand_name": "Test"},
            "campaign_strategy": {"objective": "awareness"},
            "creative_flags": {"has_voiceover": True},
            "impact_scores": {
                "hook_power": {"score": 7.5},
                "overall_impact": {"score": 6.0},
            },
        }

        result = validate_extraction(analysis)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_invalid_enum(self):
        """Test validation warns on invalid enum values."""
        warnings = []
        analysis = {
            "core_metadata": {},
            "campaign_strategy": {"objective": "invalid_objective_value"},
            "creative_flags": {},
            "impact_scores": {},
        }

        result = validate_extraction(analysis, warnings)

        enum_warnings = [w for w in warnings if w["code"] == WarningCode.VALIDATION_ENUM_INVALID]
        assert len(enum_warnings) >= 1
        assert "objective" in enum_warnings[0]["meta"]["field"]


# =============================================================================
# Test ensure_warnings_and_fill_rate
# =============================================================================

class TestEnsureWarningsAndFillRate:
    """Tests for the combined ensure function."""

    def test_ensures_warnings_list_exists(self):
        """Test that extraction_warnings list is created if missing."""
        analysis = {"core_metadata": {}}

        ensure_warnings_and_fill_rate(analysis)

        assert "extraction_warnings" in analysis
        assert isinstance(analysis["extraction_warnings"], list)

    def test_ensures_fill_rate_exists(self):
        """Test that extraction_fill_rate is computed and added."""
        analysis = {"core_metadata": {}}

        ensure_warnings_and_fill_rate(analysis)

        assert "extraction_fill_rate" in analysis
        assert "overall" in analysis["extraction_fill_rate"]

    def test_ensures_validation_exists(self):
        """Test that extraction_validation is computed and added."""
        analysis = {"core_metadata": {}}

        ensure_warnings_and_fill_rate(analysis)

        assert "extraction_validation" in analysis
        assert "valid" in analysis["extraction_validation"]

    def test_adds_warnings_for_missing_critical_sections(self):
        """Test that warnings are added for missing critical sections."""
        analysis = {}

        ensure_warnings_and_fill_rate(analysis)

        section_warnings = [
            w for w in analysis["extraction_warnings"]
            if w["code"] == WarningCode.SECTION_MISSING
        ]
        assert len(section_warnings) > 0


# =============================================================================
# Test Integration with Normalization
# =============================================================================

class TestIntegrationWithNormalization:
    """Tests for integration between warnings and normalization flow."""

    def test_score_clamping_produces_warning(self):
        """Test that score clamping in normalization produces warnings."""
        from tvads_rag.analysis import _ensure_valid_impact_scores

        warnings = []
        scores = {
            "hook_power": {"score": 15.0},  # Will be clamped to 10
            "overall_impact": {"score": 5.0},  # Valid
        }

        _ensure_valid_impact_scores(scores, warnings)

        assert scores["hook_power"]["score"] == 10.0  # Clamped
        clamp_warnings = [w for w in warnings if w["code"] == WarningCode.SCORE_CLAMPED]
        assert len(clamp_warnings) == 1
        assert clamp_warnings[0]["meta"]["original"] == 15.0
        assert clamp_warnings[0]["meta"]["clamped"] == 10.0

    def test_score_defaulting_produces_warning(self):
        """Test that score defaulting produces warnings."""
        from tvads_rag.analysis import _ensure_valid_impact_scores

        warnings = []
        scores = {}  # All scores missing

        _ensure_valid_impact_scores(scores, warnings)

        # All 8 scores should produce SCORE_DEFAULTED warnings
        default_warnings = [w for w in warnings if w["code"] == WarningCode.SCORE_DEFAULTED]
        assert len(default_warnings) == 8

    def test_ratio_clamping_produces_warning(self):
        """Test that ratio clamping in emotional timeline produces warnings."""
        from tvads_rag.analysis import _ensure_valid_emotional_timeline

        warnings = []
        timeline = {
            "readings": [
                {"t_s": 0.0, "intensity": 1.5, "arousal": 0.5},  # intensity > 1
            ]
        }

        _ensure_valid_emotional_timeline(timeline, warnings)

        assert timeline["readings"][0]["intensity"] == 1.0  # Clamped
        ratio_warnings = [w for w in warnings if w["code"] == WarningCode.RATIO_CLAMPED]
        assert len(ratio_warnings) == 1


# =============================================================================
# Test Warning Codes
# =============================================================================

class TestWarningCodes:
    """Tests for warning code constants."""

    def test_all_codes_are_unique(self):
        """Test that all warning codes are unique strings."""
        codes = [
            WarningCode.JSON_REPAIRED,
            WarningCode.JSON_PARSE_FALLBACK,
            WarningCode.VALIDATION_FAILED,
            WarningCode.VALIDATION_TYPE_MISMATCH,
            WarningCode.VALIDATION_ENUM_INVALID,
            WarningCode.SCORE_CLAMPED,
            WarningCode.SCORE_DEFAULTED,
            WarningCode.RATIO_CLAMPED,
            WarningCode.TRANSCRIPT_EMPTY,
            WarningCode.TRANSCRIPT_TRUNCATED,
            WarningCode.STAGE_SKIPPED,
            WarningCode.STAGE_FAILED,
            WarningCode.VISION_SAFETY_BLOCK,
            WarningCode.VISION_TIMEOUT,
            WarningCode.VISION_EMPTY_RESPONSE,
            WarningCode.FIELD_MISSING_CRITICAL,
            WarningCode.FIELD_DEFAULTED,
            WarningCode.SECTION_MISSING,
        ]

        assert len(codes) == len(set(codes)), "Duplicate warning codes found"

    def test_codes_are_strings(self):
        """Test that all codes are non-empty strings."""
        assert isinstance(WarningCode.JSON_REPAIRED, str)
        assert len(WarningCode.JSON_REPAIRED) > 0
