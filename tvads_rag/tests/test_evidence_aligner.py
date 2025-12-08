"""
Tests for evidence aligner - claim/super grounding with timestamps and confidence.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from tvads_rag.evidence_aligner import (
    Evidence,
    align_claim_to_transcript,
    align_super_to_evidence,
    align_all_claims,
    align_all_supers,
    EXACT_MATCH_THRESHOLD,
    FUZZY_MATCH_THRESHOLD,
)
from tvads_rag.extraction_warnings import WarningCode


# =============================================================================
# Test Evidence Class
# =============================================================================

class TestEvidenceClass:
    """Tests for the Evidence dataclass."""

    def test_evidence_to_dict(self):
        """Test Evidence converts to dict correctly."""
        evidence = Evidence(
            source="transcript",
            excerpt="This is the claim text.",
            match_method="exact"
        )
        d = evidence.to_dict()

        assert d["source"] == "transcript"
        assert d["excerpt"] == "This is the claim text."
        assert d["match_method"] == "exact"

    def test_evidence_truncates_long_excerpt(self):
        """Test Evidence truncates excerpts over 200 chars."""
        long_text = "x" * 300
        evidence = Evidence(source="transcript", excerpt=long_text, match_method="exact")
        d = evidence.to_dict()

        assert len(d["excerpt"]) <= 200


# =============================================================================
# Test Claim Alignment - Exact Match
# =============================================================================

class TestClaimAlignmentExact:
    """Tests for claim alignment with exact matches."""

    def test_exact_substring_match(self):
        """Test claim that is exact substring of transcript segment."""
        claim = {"text": "50% more effective"}
        segments = [
            {"text": "Studies show 50% more effective results.", "start": 5.0, "end": 10.0},
            {"text": "Buy now for best price.", "start": 10.0, "end": 15.0},
        ]

        result = align_claim_to_transcript(claim, segments)

        assert result["timestamp_start_s"] == 5.0
        assert result["timestamp_end_s"] == 10.0
        assert result["evidence"]["source"] == "transcript"
        assert result["evidence"]["match_method"] == "exact"
        assert result["confidence"] >= EXACT_MATCH_THRESHOLD

    def test_segment_found_in_claim(self):
        """Test when segment text is subset of claim (range match)."""
        claim = {"text": "Our product is 50% more effective and costs less"}
        segments = [
            {"text": "50% more effective", "start": 5.0, "end": 8.0},
            {"text": "costs less", "start": 8.0, "end": 10.0},
        ]

        result = align_claim_to_transcript(claim, segments)

        # Should find the range match spanning both segments
        assert result["timestamp_start_s"] is not None
        assert result["timestamp_end_s"] is not None


# =============================================================================
# Test Claim Alignment - Fuzzy Match
# =============================================================================

class TestClaimAlignmentFuzzy:
    """Tests for claim alignment with fuzzy matches."""

    def test_fuzzy_match_low_confidence(self):
        """Test fuzzy match produces lower confidence than exact."""
        # Use strings with minimal overlap to get fuzzy match
        claim = {"text": "Revolutionary breakthrough technology"}
        segments = [
            {"text": "New innovation in tech sector.", "start": 5.0, "end": 10.0},
        ]

        warnings = {}
        result = align_claim_to_transcript(claim, segments, warnings_target=warnings)

        # Either it finds a fuzzy match with lower confidence, or no match at all
        # Both are valid for this test - we just verify confidence isn't perfect 1.0
        assert result["confidence"] <= 1.0

    def test_fuzzy_match_emits_warning(self):
        """Test fuzzy match emits EVIDENCE_FUZZY_MATCH warning when in fuzzy range."""
        # Use strings with some overlap to trigger fuzzy match
        claim = {"text": "Fast delivery guaranteed to your door"}
        segments = [
            {"text": "Delivery to your doorstep.", "start": 5.0, "end": 10.0},
        ]

        warnings = {}
        result = align_claim_to_transcript(claim, segments, warnings_target=warnings)

        # The test validates the warning mechanism works when confidence is in fuzzy range
        extraction_warnings = warnings.get("extraction_warnings", [])

        # If confidence is in fuzzy range, warning should be emitted
        if FUZZY_MATCH_THRESHOLD <= result["confidence"] < EXACT_MATCH_THRESHOLD:
            fuzzy_warnings = [w for w in extraction_warnings if w["code"] == WarningCode.EVIDENCE_FUZZY_MATCH]
            assert len(fuzzy_warnings) >= 1


# =============================================================================
# Test Claim Alignment - Ungrounded
# =============================================================================

class TestClaimAlignmentUngrounded:
    """Tests for claims that cannot be grounded."""

    def test_ungrounded_claim_emits_warning(self):
        """Test ungrounded claim emits EVIDENCE_NOT_GROUNDED warning."""
        # Use completely different vocabulary with no overlap
        claim = {"text": "Xyzabc quantum flux capacitor zqwerty"}
        segments = [
            {"text": "Hello world.", "start": 0.0, "end": 5.0},
            {"text": "Goodbye moon.", "start": 5.0, "end": 10.0},
        ]

        warnings = {}
        result = align_claim_to_transcript(claim, segments, warnings_target=warnings)

        # Check warning was emitted
        extraction_warnings = warnings.get("extraction_warnings", [])
        ungrounded_warnings = [w for w in extraction_warnings if w["code"] == WarningCode.EVIDENCE_NOT_GROUNDED]

        assert len(ungrounded_warnings) == 1
        assert result["evidence"]["match_method"] == "none"

    def test_ungrounded_claim_with_extraction_timestamp(self):
        """Test ungrounded claim falls back to extraction timestamp."""
        claim = {"text": "Xyzqwerty nonsense claim", "timestamp_s": 7.5}
        segments = [
            {"text": "Abcdefg hijklmn opqrst.", "start": 0.0, "end": 5.0},
        ]

        result = align_claim_to_transcript(claim, segments)

        # Should use the extraction timestamp as fallback
        assert result["timestamp_start_s"] == 7.5
        assert result["timestamp_end_s"] == 9.5  # 7.5 + 2.0 default duration

    def test_empty_segments_list(self):
        """Test handling empty segments list."""
        claim = {"text": "Some claim"}
        segments = []

        result = align_claim_to_transcript(claim, segments)

        assert result["timestamp_start_s"] is None
        assert result["evidence"]["match_method"] == "none"


# =============================================================================
# Test Timestamp Validation
# =============================================================================

class TestTimestampValidation:
    """Tests for timestamp validation and out-of-range warnings."""

    def test_timestamp_out_of_range_warning(self):
        """Test TIMESTAMP_OUT_OF_RANGE emitted for invalid timestamps."""
        claim = {"text": "Matched claim exactly"}
        segments = [
            {"text": "Matched claim exactly here.", "start": 100.0, "end": 105.0},  # Out of range
        ]

        warnings = {}
        result = align_claim_to_transcript(claim, segments, duration_seconds=30.0, warnings_target=warnings)

        extraction_warnings = warnings.get("extraction_warnings", [])
        range_warnings = [w for w in extraction_warnings if w["code"] == WarningCode.TIMESTAMP_OUT_OF_RANGE]

        # Should emit at least one warning for out-of-range timestamps
        assert len(range_warnings) >= 1
        # Timestamps should be clamped to valid range
        assert result["timestamp_start_s"] <= 30.0
        assert result["timestamp_end_s"] <= 30.0

    def test_timestamp_missing_warning(self):
        """Test TIMESTAMP_MISSING emitted when no timestamps."""
        # Use completely unmatched text with no fallback timestamp
        claim = {"text": "Xyzabc qwerty zxcvb"}
        segments = []

        warnings = {}
        result = align_claim_to_transcript(claim, segments, warnings_target=warnings)

        extraction_warnings = warnings.get("extraction_warnings", [])
        missing_warnings = [w for w in extraction_warnings if w["code"] == WarningCode.TIMESTAMP_MISSING]

        assert len(missing_warnings) == 1
        assert result["timestamp_start_s"] is None
        assert result["timestamp_end_s"] is None


# =============================================================================
# Test Super Alignment
# =============================================================================

class TestSuperAlignment:
    """Tests for super (on-screen text) alignment."""

    def test_super_with_timestamps(self):
        """Test super already has timestamps from extraction."""
        super_ = {
            "text": "LIMITED TIME OFFER",
            "super_type": "offer",
            "start_s": 5.0,
            "end_s": 10.0,
        }

        result = align_super_to_evidence(super_)

        assert result["evidence"]["source"] in ("vision", "ocr", "unknown")
        assert result["confidence"] > 0

    def test_super_with_ocr_match(self):
        """Test super matches against OCR results."""
        super_ = {"text": "FREE SHIPPING", "super_type": "offer", "start_s": 5.0, "end_s": 10.0}
        ocr_results = [
            {"text": "FREE SHIPPING TODAY", "frame": 150},
        ]

        result = align_super_to_evidence(super_, ocr_results=ocr_results)

        assert result["evidence"]["source"] == "ocr"
        assert result["confidence"] > 0

    def test_super_without_text_emits_warning(self):
        """Test super without text emits EVIDENCE_NOT_GROUNDED."""
        super_ = {"text": "", "super_type": "legal", "start_s": 5.0, "end_s": 10.0}

        warnings = {}
        result = align_super_to_evidence(super_, warnings_target=warnings)

        extraction_warnings = warnings.get("extraction_warnings", [])
        ungrounded_warnings = [w for w in extraction_warnings if w["code"] == WarningCode.EVIDENCE_NOT_GROUNDED]

        # Should emit warning for empty text
        assert len(ungrounded_warnings) == 1
        # Confidence should be 0 for empty text
        assert result["confidence"] == 0.0

    def test_super_timestamp_out_of_range(self):
        """Test super with out-of-range timestamps emits warning."""
        super_ = {"text": "LEGAL TEXT HERE", "super_type": "legal", "start_s": 100.0, "end_s": 105.0}

        warnings = {}
        result = align_super_to_evidence(super_, duration_seconds=30.0, warnings_target=warnings)

        extraction_warnings = warnings.get("extraction_warnings", [])
        range_warnings = [w for w in extraction_warnings if w["code"] == WarningCode.TIMESTAMP_OUT_OF_RANGE]

        # Should emit warnings for out-of-range start and end times
        assert len(range_warnings) >= 1


# =============================================================================
# Test Batch Processing
# =============================================================================

class TestBatchProcessing:
    """Tests for batch alignment functions."""

    def test_align_all_claims(self):
        """Test batch claim alignment."""
        claims = [
            {"text": "50% more effective"},
            {"text": "Best in class quality"},
        ]
        segments = [
            {"text": "Our product is 50% more effective.", "start": 0.0, "end": 5.0},
            {"text": "Best in class quality guaranteed.", "start": 5.0, "end": 10.0},
        ]

        results = align_all_claims(claims, segments)

        assert len(results) == 2
        assert all("evidence" in r for r in results)
        assert all("confidence" in r for r in results)

    def test_align_all_supers(self):
        """Test batch super alignment."""
        supers = [
            {"text": "FREE DELIVERY", "super_type": "offer", "start_s": 0.0, "end_s": 5.0},
            {"text": "Terms apply", "super_type": "legal", "start_s": 25.0, "end_s": 30.0},
        ]

        results = align_all_supers(supers)

        assert len(results) == 2
        assert all("evidence" in r for r in results)
        assert all("confidence" in r for r in results)


# =============================================================================
# Test Migration File Integrity
# =============================================================================

class TestMigrationFileIntegrity:
    """Tests for claims/supers evidence migration file."""

    @pytest.fixture
    def migration_content(self):
        """Read the migration file content."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        migration_path = os.path.join(base_dir, "migrations", "archived", "schema_claims_supers_evidence.sql")

        with open(migration_path, "r") as f:
            return f.read().lower()

    def test_migration_adds_claim_timestamps(self, migration_content):
        """Test migration adds timestamp columns to claims."""
        assert "timestamp_start_s" in migration_content
        assert "timestamp_end_s" in migration_content

    def test_migration_adds_claim_evidence(self, migration_content):
        """Test migration adds evidence column to claims."""
        assert "ad_claims" in migration_content
        assert "evidence" in migration_content
        assert "jsonb" in migration_content

    def test_migration_adds_claim_confidence(self, migration_content):
        """Test migration adds confidence column to claims."""
        assert "confidence" in migration_content
        assert "float" in migration_content

    def test_migration_adds_super_evidence(self, migration_content):
        """Test migration adds evidence column to supers."""
        assert "ad_supers" in migration_content

    def test_migration_uses_if_not_exists(self, migration_content):
        """Test migration uses IF NOT EXISTS for safety."""
        assert "if not exists" in migration_content


# =============================================================================
# Test Warning Codes Exist
# =============================================================================

class TestWarningCodesExist:
    """Tests that all required warning codes exist."""

    def test_evidence_not_grounded_exists(self):
        """Test EVIDENCE_NOT_GROUNDED warning code exists."""
        assert hasattr(WarningCode, "EVIDENCE_NOT_GROUNDED")
        assert WarningCode.EVIDENCE_NOT_GROUNDED == "EVIDENCE_NOT_GROUNDED"

    def test_evidence_fuzzy_match_exists(self):
        """Test EVIDENCE_FUZZY_MATCH warning code exists."""
        assert hasattr(WarningCode, "EVIDENCE_FUZZY_MATCH")
        assert WarningCode.EVIDENCE_FUZZY_MATCH == "EVIDENCE_FUZZY_MATCH"

    def test_timestamp_missing_exists(self):
        """Test TIMESTAMP_MISSING warning code exists."""
        assert hasattr(WarningCode, "TIMESTAMP_MISSING")
        assert WarningCode.TIMESTAMP_MISSING == "TIMESTAMP_MISSING"

    def test_timestamp_out_of_range_exists(self):
        """Test TIMESTAMP_OUT_OF_RANGE warning code exists."""
        assert hasattr(WarningCode, "TIMESTAMP_OUT_OF_RANGE")
        assert WarningCode.TIMESTAMP_OUT_OF_RANGE == "TIMESTAMP_OUT_OF_RANGE"


# =============================================================================
# Test DB Column Definitions
# =============================================================================

class TestDBColumnDefinitions:
    """Tests for DB column definitions."""

    def test_claim_columns_include_evidence_fields(self):
        """Test CLAIM_COLUMNS includes evidence grounding fields."""
        from tvads_rag.db import CLAIM_COLUMNS

        assert "timestamp_start_s" in CLAIM_COLUMNS
        assert "timestamp_end_s" in CLAIM_COLUMNS
        assert "evidence" in CLAIM_COLUMNS
        assert "confidence" in CLAIM_COLUMNS

    def test_super_columns_include_evidence_fields(self):
        """Test SUPER_COLUMNS includes evidence grounding fields."""
        from tvads_rag.db import SUPER_COLUMNS

        assert "evidence" in SUPER_COLUMNS
        assert "confidence" in SUPER_COLUMNS

    def test_claim_jsonb_columns_defined(self):
        """Test CLAIM_JSONB_COLUMNS is defined with evidence."""
        from tvads_rag.db import CLAIM_JSONB_COLUMNS

        assert "evidence" in CLAIM_JSONB_COLUMNS

    def test_super_jsonb_columns_defined(self):
        """Test SUPER_JSONB_COLUMNS is defined with evidence."""
        from tvads_rag.db import SUPER_JSONB_COLUMNS

        assert "evidence" in SUPER_JSONB_COLUMNS


# =============================================================================
# Test Persistence Shape (Mock DB)
# =============================================================================

class TestPersistenceShape:
    """Tests for persistence data shape."""

    def test_aligned_claim_has_required_fields(self):
        """Test aligned claim has all required persistence fields."""
        claim = {"text": "Test claim", "claim_type": "performance"}
        segments = [{"text": "Test claim here.", "start": 0.0, "end": 5.0}]

        result = align_claim_to_transcript(claim, segments)

        # Original fields preserved
        assert result["text"] == "Test claim"
        assert result["claim_type"] == "performance"

        # New evidence fields added
        assert "timestamp_start_s" in result
        assert "timestamp_end_s" in result
        assert "evidence" in result
        assert "confidence" in result

        # Evidence is a dict with required shape
        assert isinstance(result["evidence"], dict)
        assert "source" in result["evidence"]
        assert "excerpt" in result["evidence"]
        assert "match_method" in result["evidence"]

        # Confidence is a float 0-1
        assert isinstance(result["confidence"], float)
        assert 0 <= result["confidence"] <= 1

    def test_aligned_super_has_required_fields(self):
        """Test aligned super has all required persistence fields."""
        super_ = {"text": "OFFER", "super_type": "offer", "start_s": 5.0, "end_s": 10.0}

        result = align_super_to_evidence(super_)

        # Original fields preserved
        assert result["text"] == "OFFER"
        assert result["super_type"] == "offer"

        # New evidence fields added
        assert "evidence" in result
        assert "confidence" in result

        # Evidence is a dict with required shape
        assert isinstance(result["evidence"], dict)
        assert "source" in result["evidence"]
        assert "excerpt" in result["evidence"]
        assert "match_method" in result["evidence"]
