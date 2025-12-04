"""
Extraction warnings and fill-rate utilities.

This module provides primitives for:
- Tracking warnings during extraction and normalization
- Computing field fill rates for observability
- Standardized warning codes and structures
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("tvads_rag.extraction_warnings")

# =============================================================================
# Warning Codes (stable identifiers)
# =============================================================================

class WarningCode:
    """Standardized warning codes for extraction issues."""

    # JSON/Parse issues
    JSON_REPAIRED = "JSON_REPAIRED"
    JSON_PARSE_FALLBACK = "JSON_PARSE_FALLBACK"

    # Validation issues
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATION_TYPE_MISMATCH = "VALIDATION_TYPE_MISMATCH"
    VALIDATION_ENUM_INVALID = "VALIDATION_ENUM_INVALID"

    # Score issues
    SCORE_CLAMPED = "SCORE_CLAMPED"
    SCORE_DEFAULTED = "SCORE_DEFAULTED"
    RATIO_CLAMPED = "RATIO_CLAMPED"

    # Input issues
    TRANSCRIPT_EMPTY = "TRANSCRIPT_EMPTY"
    TRANSCRIPT_TRUNCATED = "TRANSCRIPT_TRUNCATED"

    # Stage issues
    STAGE_SKIPPED = "STAGE_SKIPPED"
    STAGE_FAILED = "STAGE_FAILED"

    # Vision issues
    VISION_SAFETY_BLOCK = "VISION_SAFETY_BLOCK"
    VISION_TIMEOUT = "VISION_TIMEOUT"
    VISION_EMPTY_RESPONSE = "VISION_EMPTY_RESPONSE"

    # Field issues
    FIELD_MISSING_CRITICAL = "FIELD_MISSING_CRITICAL"
    FIELD_DEFAULTED = "FIELD_DEFAULTED"
    SECTION_MISSING = "SECTION_MISSING"

    # Toxicity issues
    TOXICITY_INPUT_MISSING = "TOXICITY_INPUT_MISSING"
    TOXICITY_SCORING_FAILED = "TOXICITY_SCORING_FAILED"

    # Evidence grounding issues (claims & supers)
    EVIDENCE_NOT_GROUNDED = "EVIDENCE_NOT_GROUNDED"
    EVIDENCE_FUZZY_MATCH = "EVIDENCE_FUZZY_MATCH"
    TIMESTAMP_MISSING = "TIMESTAMP_MISSING"
    TIMESTAMP_OUT_OF_RANGE = "TIMESTAMP_OUT_OF_RANGE"


# =============================================================================
# Warning Entry Structure
# =============================================================================

def create_warning(
    code: str,
    message: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a standardized warning entry.

    Args:
        code: Warning code from WarningCode class
        message: Human-readable description
        meta: Optional metadata (field names, values, etc.)

    Returns:
        Warning dict: {code, message, meta, ts}
    """
    return {
        "code": code,
        "message": message,
        "meta": meta or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def add_warning(
    target: Union[Dict[str, Any], List[Dict[str, Any]]],
    code: str,
    message: str,
    meta: Optional[Dict[str, Any]] = None,
    log_level: str = "warning",
) -> Dict[str, Any]:
    """
    Add a warning to an analysis dict or warnings list.

    If target is a dict, ensures 'extraction_warnings' key exists and appends.
    If target is a list, appends directly.

    Also logs the warning with structured data.

    Args:
        target: Analysis dict or warnings list
        code: Warning code
        message: Human-readable message
        meta: Optional metadata
        log_level: Log level (debug, info, warning, error)

    Returns:
        The created warning entry
    """
    warning = create_warning(code, message, meta)

    # Add to target
    if isinstance(target, dict):
        if "extraction_warnings" not in target:
            target["extraction_warnings"] = []
        target["extraction_warnings"].append(warning)
    elif isinstance(target, list):
        target.append(warning)

    # Log with structured data
    log_fn = getattr(logger, log_level, logger.warning)
    log_fn(
        "Extraction warning [%s]: %s | meta=%s",
        code, message, meta or {}
    )

    return warning


# =============================================================================
# Fill Rate Computation
# =============================================================================

# Critical sections that should always be present
CRITICAL_SECTIONS = {
    "core_metadata",
    "campaign_strategy",
    "creative_flags",
    "impact_scores",
}

# Fields that are considered "filled" if present and non-empty
FILLABLE_FIELDS = {
    "core_metadata": ["brand_name", "product_name", "product_category", "country", "language"],
    "campaign_strategy": ["objective", "funnel_stage", "format_type"],
    "creative_flags": [
        "has_voiceover", "has_dialogue", "has_on_screen_text", "has_celebrity",
        "has_ugc_style", "has_supers", "has_price_claims", "has_risk_disclaimer",
    ],
    "impact_scores": [
        "overall_impact", "pulse_score", "echo_score", "hook_power",
        "brand_integration", "emotional_resonance", "clarity_score", "distinctiveness",
    ],
    "emotional_timeline": ["arc_shape", "peak_emotion", "peak_moment_s", "readings"],
    "effectiveness_drivers": ["primary_strength", "strengths", "weaknesses"],
    "memorability": ["hook_effectiveness", "memorable_elements"],
    "cta_offer": ["call_to_action", "urgency_level"],
    "brand_presence": ["brand_first_mention_s", "brand_mention_count"],
    "compliance_assessment": ["overall_risk", "garm_categories"],
}


def _is_filled(value: Any) -> bool:
    """Check if a value counts as 'filled' (non-empty, non-default)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    if isinstance(value, bool):
        return True  # Booleans are always "filled" even if False
    if isinstance(value, (int, float)):
        return True  # Numbers are filled even if 0
    return True


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Get a nested value from a dict using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def compute_fill_rates(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute fill rates for an analysis dict.

    Returns:
        {
            "overall": 0.0-1.0,
            "by_section": {"section_name": 0.0-1.0, ...},
            "missing_top": ["section.field", ...],
            "critical_sections_present": ["section", ...],
            "critical_sections_missing": ["section", ...],
        }
    """
    total_fields = 0
    filled_fields = 0
    missing_fields: List[str] = []
    by_section: Dict[str, float] = {}

    critical_present = []
    critical_missing = []

    for section, fields in FILLABLE_FIELDS.items():
        section_data = analysis.get(section, {})
        section_total = len(fields)
        section_filled = 0

        # Track critical sections
        if section in CRITICAL_SECTIONS:
            if section_data and isinstance(section_data, dict):
                critical_present.append(section)
            else:
                critical_missing.append(section)

        for field in fields:
            total_fields += 1

            # Handle nested fields in impact_scores
            if section == "impact_scores":
                field_value = _get_nested_value(section_data, f"{field}.score")
            else:
                field_value = section_data.get(field) if isinstance(section_data, dict) else None

            if _is_filled(field_value):
                filled_fields += 1
                section_filled += 1
            else:
                missing_fields.append(f"{section}.{field}")

        # Compute section fill rate
        by_section[section] = section_filled / section_total if section_total > 0 else 0.0

    # Sort missing fields by section priority (critical first)
    def sort_key(field_path: str) -> tuple:
        section = field_path.split(".")[0]
        is_critical = section in CRITICAL_SECTIONS
        return (0 if is_critical else 1, field_path)

    missing_fields.sort(key=sort_key)

    return {
        "overall": filled_fields / total_fields if total_fields > 0 else 0.0,
        "by_section": by_section,
        "missing_top": missing_fields[:20],  # Top 20 missing
        "total_fields": total_fields,
        "filled_fields": filled_fields,
        "critical_sections_present": critical_present,
        "critical_sections_missing": critical_missing,
    }


def log_fill_rates(analysis: Dict[str, Any], external_id: str = "unknown") -> Dict[str, Any]:
    """
    Compute and log fill rates for an analysis.

    Returns the fill rate dict.
    """
    fill_rates = compute_fill_rates(analysis)

    overall_pct = fill_rates["overall"] * 100

    # Log summary
    logger.info(
        "[%s] Extraction fill rate: %.1f%% (%d/%d fields) | "
        "critical_present=%s, critical_missing=%s",
        external_id,
        overall_pct,
        fill_rates["filled_fields"],
        fill_rates["total_fields"],
        fill_rates["critical_sections_present"],
        fill_rates["critical_sections_missing"],
    )

    # Log sections below 50% fill rate
    low_sections = [
        (section, rate) for section, rate in fill_rates["by_section"].items()
        if rate < 0.5
    ]
    if low_sections:
        logger.warning(
            "[%s] Low fill rate sections: %s",
            external_id,
            {s: f"{r*100:.0f}%" for s, r in low_sections}
        )

    # Log top missing fields if overall rate is low
    if overall_pct < 70 and fill_rates["missing_top"]:
        logger.warning(
            "[%s] Top missing fields: %s",
            external_id,
            fill_rates["missing_top"][:10]
        )

    return fill_rates


def ensure_warnings_and_fill_rate(analysis: Dict[str, Any], external_id: str = "unknown") -> None:
    """
    Ensure analysis dict has extraction_warnings and extraction_fill_rate fields.

    Call this after normalization to ensure outputs are always present.
    Also runs validation and adds any validation warnings.
    """
    # Ensure warnings list exists
    if "extraction_warnings" not in analysis:
        analysis["extraction_warnings"] = []

    # Run validation (adds warnings to the analysis["extraction_warnings"] list)
    validation_result = validate_extraction(analysis, analysis["extraction_warnings"])
    analysis["extraction_validation"] = {
        "valid": validation_result["valid"],
        "errors": validation_result["errors"],
    }

    # Compute and store fill rates
    fill_rates = log_fill_rates(analysis, external_id)
    analysis["extraction_fill_rate"] = fill_rates

    # Add warning if critical sections are missing
    for section in fill_rates.get("critical_sections_missing", []):
        add_warning(
            analysis,
            WarningCode.SECTION_MISSING,
            f"Critical section '{section}' is missing",
            {"section": section},
        )


# =============================================================================
# Structural + Semantic Validation
# =============================================================================

# Valid enum values for key fields
VALID_ENUMS = {
    "objective": [
        "awareness", "consideration", "conversion", "loyalty", "brand_building",
        "lead_generation", "direct_response", "social_proof", "education", "other"
    ],
    "funnel_stage": [
        "awareness", "interest", "consideration", "intent", "evaluation",
        "purchase", "loyalty", "advocacy", "other"
    ],
    "format_type": [
        "narrative", "testimonial", "demonstration", "problem_solution",
        "slice_of_life", "comparison", "animation", "montage", "documentary",
        "musical", "humorous", "emotional", "informational", "other"
    ],
    "arc_shape": [
        "rising", "falling", "peak_middle", "peak_end", "flat", "wave",
        "crescendo", "decrescendo", "u_shape", "inverted_u", "other"
    ],
    "overall_risk": ["low", "medium", "high", "critical"],
}


def validate_extraction(
    analysis: Dict[str, Any],
    warnings: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Validate extraction output structure and semantic constraints.

    Checks:
    - Root is a dict
    - Critical sections exist
    - Score ranges (0-10)
    - Ratio ranges (0-1)
    - Enum values (warn if invalid, don't crash)

    Returns:
        {
            "valid": True/False,
            "errors": [...],
            "warnings_added": int,
        }
    """
    if warnings is None:
        warnings = []

    errors = []
    warnings_added = 0

    # Check root is dict
    if not isinstance(analysis, dict):
        errors.append("Analysis is not a dict")
        return {"valid": False, "errors": errors, "warnings_added": 0}

    # Check critical sections exist
    for section in CRITICAL_SECTIONS:
        if section not in analysis or not isinstance(analysis.get(section), dict):
            errors.append(f"Critical section '{section}' missing or invalid")

    # Validate impact scores (0-10 range)
    impact_scores = analysis.get("impact_scores", {})
    if isinstance(impact_scores, dict):
        for score_name, score_data in impact_scores.items():
            if isinstance(score_data, dict) and "score" in score_data:
                score_val = score_data.get("score")
                if score_val is not None:
                    try:
                        fval = float(score_val)
                        if not (0.0 <= fval <= 10.0):
                            warnings.append({
                                "code": WarningCode.VALIDATION_FAILED,
                                "message": f"impact_scores.{score_name}.score={fval} outside 0-10 range",
                                "meta": {"field": f"impact_scores.{score_name}.score", "value": fval},
                            })
                            warnings_added += 1
                    except (TypeError, ValueError):
                        pass  # Already handled in normalization

    # Validate emotional timeline ratios (0-1 range)
    timeline = analysis.get("emotional_timeline", {})
    if isinstance(timeline, dict):
        readings = timeline.get("readings", [])
        if isinstance(readings, list):
            for i, reading in enumerate(readings):
                if isinstance(reading, dict):
                    for ratio_field in ["intensity", "arousal"]:
                        val = reading.get(ratio_field)
                        if val is not None:
                            try:
                                fval = float(val)
                                if not (0.0 <= fval <= 1.0):
                                    warnings.append({
                                        "code": WarningCode.VALIDATION_FAILED,
                                        "message": f"emotional_timeline.readings[{i}].{ratio_field}={fval} outside 0-1 range",
                                        "meta": {"field": f"readings.{ratio_field}", "value": fval, "index": i},
                                    })
                                    warnings_added += 1
                            except (TypeError, ValueError):
                                pass

    # Validate enum values (warn if invalid)
    for field_path, valid_values in VALID_ENUMS.items():
        # Get the value based on path
        if "." in field_path:
            section, field = field_path.split(".", 1)
            section_data = analysis.get(section, {})
            value = section_data.get(field) if isinstance(section_data, dict) else None
        else:
            # Check in multiple likely locations
            value = None
            for section in ["core_metadata", "campaign_strategy", "emotional_timeline", "compliance_assessment"]:
                section_data = analysis.get(section, {})
                if isinstance(section_data, dict) and field_path in section_data:
                    value = section_data.get(field_path)
                    break

        if value is not None and isinstance(value, str):
            normalized = value.lower().strip()
            if normalized not in [v.lower() for v in valid_values] and normalized != "":
                warnings.append({
                    "code": WarningCode.VALIDATION_ENUM_INVALID,
                    "message": f"Field '{field_path}' has invalid enum value: '{value}'",
                    "meta": {"field": field_path, "value": value, "valid_values": valid_values[:5]},
                })
                warnings_added += 1
                logger.warning(
                    "Extraction warning [%s]: '%s' = '%s' not in valid enum values",
                    WarningCode.VALIDATION_ENUM_INVALID, field_path, value
                )

    # Log validation summary
    if errors:
        logger.error("Extraction validation failed: %s", errors)
    if warnings_added > 0:
        logger.warning("Extraction validation added %d warnings", warnings_added)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings_added": warnings_added,
    }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "WarningCode",
    "create_warning",
    "add_warning",
    "compute_fill_rates",
    "validate_extraction",
    "log_fill_rates",
    "ensure_warnings_and_fill_rate",
    "CRITICAL_SECTIONS",
    "FILLABLE_FIELDS",
]
