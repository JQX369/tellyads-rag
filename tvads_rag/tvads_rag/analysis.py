"""
LLM-powered analysis that turns transcripts into structured creative metadata.

Extraction v2.0: Comprehensive 22-section analysis using GPT-5.1 with impact scores,
emotional metrics, effectiveness drivers, and more.
"""

from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import get_openai_config
from .prompts.extraction_v2 import (
    EXTRACTION_V2_SYSTEM_PROMPT,
    EXTRACTION_V2_USER_TEMPLATE,
    DEFAULT_SECTIONS,
    deep_merge,
)
from .extraction_warnings import (
    WarningCode,
    add_warning,
    ensure_warnings_and_fill_rate,
)

logger = logging.getLogger(__name__)

# Module-level warnings accumulator for JSON repair tracking
_pending_warnings: List[Dict[str, Any]] = []

# Current extraction version
EXTRACTION_VERSION = "2.0"


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    cfg = get_openai_config()
    return OpenAI(api_key=cfg.api_key, base_url=cfg.api_base)


def _call_analysis_model(transcript_text: str, segments: List[Dict[str, Any]]) -> str:
    """Call the LLM with the v2 extraction prompt."""
    client = _get_openai_client()
    cfg = get_openai_config()
    
    user_prompt = EXTRACTION_V2_USER_TEMPLATE.format(
        transcript_text=transcript_text.strip() or "(No transcript available)",
        segments_json=json.dumps(segments, ensure_ascii=False) if segments else "[]",
    )
    
    logger.info("Calling %s for extraction v2.0", cfg.llm_model_name)
    
    # Use response_format for reliable JSON output
    response = client.chat.completions.create(
        model=cfg.llm_model_name,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACTION_V2_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    
    message = response.choices[0].message
    return message.content or ""


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()
    return cleaned


def _repair_json_with_model(bad_output: str) -> Optional[str]:
    """Ask the LLM to repair malformed JSON."""
    client = _get_openai_client()
    cfg = get_openai_config()
    prompt = (
        "The previous response was not valid JSON. "
        "Return only valid JSON matching the required schema.\n\n"
        f"Broken response:\n{bad_output[:8000]}"  # Limit to avoid token overflow
    )
    response = client.chat.completions.create(
        model=cfg.llm_model_name,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return ONLY valid JSON. Fix any syntax errors."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def _try_parse_json(candidate: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _parse_with_retries(raw_output: str, warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse JSON output with multiple fallback strategies.

    Args:
        raw_output: Raw LLM output
        warnings: List to append warnings to
    """
    global _pending_warnings
    cleaned = _strip_markdown_fences(raw_output)

    # Try direct parse first
    parsed = _try_parse_json(cleaned)
    if parsed is not None:
        return parsed

    # Try extracting JSON object
    if "{" in cleaned and "}" in cleaned:
        extracted = cleaned[cleaned.find("{"): cleaned.rfind("}") + 1]
        parsed = _try_parse_json(extracted)
        if parsed is not None:
            warnings.append({
                "code": WarningCode.JSON_PARSE_FALLBACK,
                "message": "JSON parsed after extracting object from response",
                "meta": {"strategy": "extract_object"},
            })
            logger.warning(
                "Extraction warning [%s]: JSON required fallback extraction",
                WarningCode.JSON_PARSE_FALLBACK
            )
            return parsed

    # Last resort: ask model to repair
    logger.warning("Initial JSON parse failed, attempting LLM repair...")
    repaired = _repair_json_with_model(raw_output)
    if repaired:
        parsed = _try_parse_json(_strip_markdown_fences(repaired))
        if parsed is not None:
            warnings.append({
                "code": WarningCode.JSON_REPAIRED,
                "message": "JSON was malformed and required LLM repair",
                "meta": {"original_length": len(raw_output), "repaired_length": len(repaired)},
            })
            logger.warning(
                "Extraction warning [%s]: JSON required LLM repair | original_len=%d, repaired_len=%d",
                WarningCode.JSON_REPAIRED, len(raw_output), len(repaired)
            )
            return parsed

    raise ValueError("LLM analysis output was not valid JSON after retries.")


def _normalise_analysis_v2(
    data: Dict[str, Any],
    warnings: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Ensure the returned dict has all expected sections with safe defaults.

    This comprehensive normalisation handles:
    - Missing sections (replaced with defaults)
    - Missing nested fields (merged with defaults)
    - Type validation for critical fields
    - Version stamping

    Args:
        data: Raw parsed LLM output
        warnings: Optional list to append warnings to
    """
    if warnings is None:
        warnings = []

    result = {}

    # Add extraction metadata
    result["extraction_version"] = data.get("extraction_version", EXTRACTION_VERSION)
    result["extraction_timestamp"] = data.get(
        "extraction_timestamp",
        datetime.now(timezone.utc).isoformat()
    )
    result["confidence_overall"] = data.get("confidence_overall", 0.5)

    # Track missing sections
    missing_sections = []

    # Process each section with defaults
    for section_name, default_value in DEFAULT_SECTIONS.items():
        if section_name not in data or data[section_name] is None:
            # Section missing - use defaults
            result[section_name] = copy.deepcopy(default_value)
            missing_sections.append(section_name)
        elif isinstance(default_value, dict) and isinstance(data[section_name], dict):
            # Merge nested dicts
            result[section_name] = deep_merge(
                copy.deepcopy(default_value),
                data[section_name]
            )
        elif isinstance(default_value, list):
            # Lists are taken as-is (or empty if None)
            result[section_name] = data[section_name] if data[section_name] else []
        else:
            result[section_name] = data[section_name]

    # Log missing sections
    if missing_sections:
        warnings.append({
            "code": WarningCode.SECTION_MISSING,
            "message": f"Missing sections defaulted: {', '.join(missing_sections[:5])}{'...' if len(missing_sections) > 5 else ''}",
            "meta": {"sections": missing_sections, "count": len(missing_sections)},
        })
        logger.warning(
            "Extraction warning [%s]: %d sections missing: %s",
            WarningCode.SECTION_MISSING,
            len(missing_sections),
            missing_sections[:10]
        )

    # Ensure critical nested structures are valid (pass warnings for tracking)
    _ensure_valid_impact_scores(result.get("impact_scores", {}), warnings)
    _ensure_valid_emotional_timeline(result.get("emotional_timeline", {}), warnings)
    _ensure_valid_brain_balance(result.get("brain_balance", {}))
    _ensure_valid_characters(result.get("characters", []), warnings)
    _ensure_valid_cast_diversity(result.get("cast_diversity", {}))

    return result


def _ensure_valid_impact_scores(
    scores: Dict[str, Any],
    warnings: Optional[List[Dict[str, Any]]] = None
) -> None:
    """Validate and fix impact scores structure."""
    if warnings is None:
        warnings = []

    score_fields = [
        "overall_impact", "pulse_score", "echo_score", "hook_power",
        "brand_integration", "emotional_resonance", "clarity_score", "distinctiveness"
    ]

    for field in score_fields:
        if field not in scores or not isinstance(scores[field], dict):
            scores[field] = {
                "score": None,  # Keep as None instead of silent 5.0 default
                "confidence": 0.0,
                "rationale": "Unable to assess" if field == "overall_impact" else "",
            }
            warnings.append({
                "code": WarningCode.SCORE_DEFAULTED,
                "message": f"Impact score '{field}' was missing, defaulted to null",
                "meta": {"field": f"impact_scores.{field}", "default_value": None},
            })
            logger.warning(
                "Extraction warning [%s]: impact_scores.%s missing, set to null",
                WarningCode.SCORE_DEFAULTED, field
            )
        else:
            # Ensure score is in valid range
            if "score" in scores[field]:
                try:
                    original = scores[field]["score"]
                    score_val = float(original)
                    clamped = max(0.0, min(10.0, score_val))
                    if clamped != score_val:
                        warnings.append({
                            "code": WarningCode.SCORE_CLAMPED,
                            "message": f"Impact score '{field}' clamped from {score_val} to {clamped}",
                            "meta": {"field": f"impact_scores.{field}", "original": score_val, "clamped": clamped},
                        })
                        logger.warning(
                            "Extraction warning [%s]: impact_scores.%s clamped %s -> %s",
                            WarningCode.SCORE_CLAMPED, field, score_val, clamped
                        )
                    scores[field]["score"] = clamped
                except (TypeError, ValueError):
                    scores[field]["score"] = None
                    warnings.append({
                        "code": WarningCode.SCORE_DEFAULTED,
                        "message": f"Impact score '{field}' had invalid value, set to null",
                        "meta": {"field": f"impact_scores.{field}", "invalid_value": str(scores[field].get("score"))},
                    })
                    logger.warning(
                        "Extraction warning [%s]: impact_scores.%s invalid, set to null",
                        WarningCode.SCORE_DEFAULTED, field
                    )
            else:
                scores[field]["score"] = None
                warnings.append({
                    "code": WarningCode.SCORE_DEFAULTED,
                    "message": f"Impact score '{field}.score' missing, set to null",
                    "meta": {"field": f"impact_scores.{field}.score"},
                })

            if "confidence" not in scores[field]:
                scores[field]["confidence"] = 0.0


def _ensure_valid_emotional_timeline(
    timeline: Dict[str, Any],
    warnings: Optional[List[Dict[str, Any]]] = None
) -> None:
    """Validate emotional timeline structure with enhanced granular fields."""
    if warnings is None:
        warnings = []

    if "readings" not in timeline or not isinstance(timeline["readings"], list):
        timeline["readings"] = []

    for reading in timeline["readings"]:
        if isinstance(reading, dict):
            reading.setdefault("t_s", 0.0)
            reading.setdefault("dominant_emotion", "neutral")
            reading.setdefault("secondary_emotion", None)
            reading.setdefault("intensity", 0.5)
            reading.setdefault("valence", 0.0)
            reading.setdefault("arousal", 0.5)
            reading.setdefault("trigger", None)

            # Clamp ratio values to 0-1
            for ratio_field in ["intensity", "arousal"]:
                if ratio_field in reading:
                    try:
                        val = float(reading[ratio_field])
                        clamped = max(0.0, min(1.0, val))
                        if clamped != val:
                            warnings.append({
                                "code": WarningCode.RATIO_CLAMPED,
                                "message": f"emotional_timeline.readings.{ratio_field} clamped {val} -> {clamped}",
                                "meta": {"field": f"readings.{ratio_field}", "original": val, "clamped": clamped},
                            })
                        reading[ratio_field] = clamped
                    except (TypeError, ValueError):
                        reading[ratio_field] = 0.5

    # Ensure emotional_transitions exists
    if "emotional_transitions" not in timeline or not isinstance(timeline["emotional_transitions"], list):
        timeline["emotional_transitions"] = []

    for transition in timeline["emotional_transitions"]:
        if isinstance(transition, dict):
            transition.setdefault("from_emotion", "neutral")
            transition.setdefault("to_emotion", "neutral")
            transition.setdefault("transition_time_s", 0.0)
            transition.setdefault("transition_type", "gradual")
            transition.setdefault("effectiveness", 0.5)

    # Ensure new timeline summary fields
    timeline.setdefault("trough_moment_s", None)
    timeline.setdefault("trough_emotion", None)
    timeline.setdefault("emotional_range", 0.5)
    timeline.setdefault("final_viewer_state", "neutral")


def _ensure_valid_brain_balance(balance: Dict[str, Any]) -> None:
    """Validate brain balance structure."""
    if "emotional_elements" not in balance or not isinstance(balance["emotional_elements"], dict):
        balance["emotional_elements"] = {
            "has_characters_with_personality": False,
            "has_relatable_situation": False,
            "has_music_enhancing_emotion": False,
            "has_visual_metaphor": False,
            "has_humor_or_wit": False,
            "has_human_connection": False,
            "dialogue_between_characters": False,
            "shows_consequence_or_payoff": False,
        }
    
    if "rational_elements" not in balance or not isinstance(balance["rational_elements"], dict):
        balance["rational_elements"] = {
            "has_product_demonstration": False,
            "has_feature_callouts": False,
            "has_price_or_offer": False,
            "has_statistics_or_claims": False,
            "has_direct_address_to_camera": False,
            "has_comparison_to_competitor": False,
            "has_instructional_content": False,
            "has_urgency_messaging": False,
        }


def _ensure_valid_characters(
    characters: List[Dict[str, Any]],
    warnings: Optional[List[Dict[str, Any]]] = None
) -> None:
    """Validate and normalize character entries with detailed ethnicity structure."""
    if warnings is None:
        warnings = []

    for idx, char in enumerate(characters):
        if not isinstance(char, dict):
            continue

        # Ensure ethnicity is a structured dict, not a string
        ethnicity = char.get("ethnicity")
        if ethnicity is None or isinstance(ethnicity, str):
            # Convert legacy string format to new structured format
            char["ethnicity"] = {
                "primary": ethnicity if isinstance(ethnicity, str) else "unclear",
                "regional_detail": None,
                "confidence": 0.5,
            }
        elif isinstance(ethnicity, dict):
            ethnicity.setdefault("primary", "unclear")
            ethnicity.setdefault("regional_detail", None)
            ethnicity.setdefault("confidence", 0.5)

        # Ensure physical_traits exists
        if "physical_traits" not in char or not isinstance(char.get("physical_traits"), dict):
            char["physical_traits"] = {
                "hair_color": "unclear",
                "distinctive_features": None,
            }
        else:
            char["physical_traits"].setdefault("hair_color", "unclear")
            char["physical_traits"].setdefault("distinctive_features", None)

        # Ensure other required fields
        char.setdefault("role", "background")
        char.setdefault("screen_time_pct", 0.0)
        char.setdefault("gender", "unclear")
        char.setdefault("age_bracket", "ageless")
        char.setdefault("is_celebrity", False)
        char.setdefault("celebrity_name", None)
        char.setdefault("character_type", "real_person")
        char.setdefault("relatability_score", None)  # Don't default to 5.0
        char.setdefault("likability_score", None)    # Don't default to 5.0


def _ensure_valid_cast_diversity(diversity: Dict[str, Any]) -> None:
    """Validate cast diversity structure."""
    diversity.setdefault("total_characters", 0)
    
    if "gender_breakdown" not in diversity or not isinstance(diversity.get("gender_breakdown"), dict):
        diversity["gender_breakdown"] = {"male": 0, "female": 0, "non_binary": 0, "unclear": 0}
    else:
        diversity["gender_breakdown"].setdefault("male", 0)
        diversity["gender_breakdown"].setdefault("female", 0)
        diversity["gender_breakdown"].setdefault("non_binary", 0)
        diversity["gender_breakdown"].setdefault("unclear", 0)
    
    if "ethnicity_breakdown" not in diversity or not isinstance(diversity.get("ethnicity_breakdown"), dict):
        diversity["ethnicity_breakdown"] = {}
    
    if "age_range_present" not in diversity or not isinstance(diversity.get("age_range_present"), list):
        diversity["age_range_present"] = []
    
    diversity.setdefault("diversity_score", 5.0)
    diversity.setdefault("representation_notes", None)


def extract_flat_metadata(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract flat fields for database columns from the v2 analysis.
    
    Returns a dict with keys matching the ads table columns.
    """
    core = analysis.get("core_metadata", {}) or {}
    strategy = analysis.get("campaign_strategy", {}) or {}
    flags = analysis.get("creative_flags", {}) or {}
    attrs = analysis.get("creative_attributes", {}) or {}
    
    return {
        "brand_name": core.get("brand_name"),
        "product_name": core.get("product_name"),
        "product_category": core.get("product_category"),
        "product_subcategory": core.get("product_subcategory"),
        "country": core.get("country"),
        "language": core.get("language"),
        "year": core.get("year"),
        "objective": strategy.get("objective"),
        "funnel_stage": strategy.get("funnel_stage"),
        "primary_kpi": strategy.get("primary_kpi"),
        "format_type": strategy.get("format_type"),
        "primary_setting": strategy.get("primary_setting"),
        "has_voiceover": flags.get("has_voiceover", False),
        "has_dialogue": flags.get("has_dialogue", False),
        "has_on_screen_text": flags.get("has_on_screen_text", False),
        "has_celeb": flags.get("has_celebrity", False),
        "has_ugc_style": flags.get("has_ugc_style", False),
        "has_supers": flags.get("has_supers", False),
        "has_price_claims": flags.get("has_price_claims", False),
        "has_risk_disclaimer": flags.get("has_risk_disclaimer", False),
        "regulator_sensitive": flags.get("regulator_sensitive", False),
        "music_style": attrs.get("music_style"),
        "editing_pace": attrs.get("editing_pace"),
        "colour_mood": attrs.get("colour_mood"),
        "overall_structure": attrs.get("overall_structure"),
        "one_line_summary": attrs.get("one_line_summary"),
        "story_summary": attrs.get("story_summary"),
    }


def extract_jsonb_columns(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract JSONB column data from the v2 analysis.
    
    Returns a dict with:
    - impact_scores: The impact scoring section
    - emotional_metrics: Combined emotional_timeline, brain_balance, attention_dynamics
    - effectiveness: Combined effectiveness_drivers, memorability, competitive_context
    - Plus legacy columns for backwards compatibility
    """
    return {
        # New v2 columns
        "impact_scores": analysis.get("impact_scores"),
        "emotional_metrics": {
            "emotional_timeline": analysis.get("emotional_timeline"),
            "brain_balance": analysis.get("brain_balance"),
            "attention_dynamics": analysis.get("attention_dynamics"),
        },
        "effectiveness": {
            "effectiveness_drivers": analysis.get("effectiveness_drivers"),
            "memorability": analysis.get("memorability"),
            "competitive_context": analysis.get("competitive_context"),
        },
        # Legacy columns (still populated for backwards compat)
        "cta_offer": analysis.get("cta_offer"),
        "brand_asset_timeline": analysis.get("brand_presence"),  # Map to new name
        "audio_fingerprint": analysis.get("audio_fingerprint"),
        "creative_dna": analysis.get("creative_dna"),
        "claims_compliance": analysis.get("compliance_assessment"),  # Map to new name
    }


def analyse_ad_transcript(
    transcript: Dict[str, Any],
    external_id: str = "unknown"
) -> Dict[str, Any]:
    """
    Run the v2.0 LLM analysis workflow for a transcript dict containing `text` + `segments`.

    Returns the full normalised analysis with all 22 sections, including:
    - extraction_warnings: List of warning entries
    - extraction_fill_rate: Fill rate metrics

    Args:
        transcript: Dict with 'text' and optional 'segments'
        external_id: Optional identifier for logging
    """
    # Initialize warnings list to track issues through the pipeline
    warnings: List[Dict[str, Any]] = []

    transcript_text = transcript.get("text", "")
    segments = transcript.get("segments") or []

    # Warn if transcript is empty
    if not transcript_text.strip():
        warnings.append({
            "code": WarningCode.TRANSCRIPT_EMPTY,
            "message": "Transcript text is empty or missing",
            "meta": {"segments_count": len(segments)},
        })
        logger.warning(
            "Extraction warning [%s]: Transcript empty for %s",
            WarningCode.TRANSCRIPT_EMPTY, external_id
        )

    # Call LLM and parse response (warnings accumulated in list)
    raw_output = _call_analysis_model(transcript_text, segments)
    parsed = _parse_with_retries(raw_output, warnings)
    normalised = _normalise_analysis_v2(parsed, warnings)

    # Attach accumulated warnings
    normalised["extraction_warnings"] = warnings

    # Compute and attach fill rates (also logs)
    ensure_warnings_and_fill_rate(normalised, external_id)

    # Log summary stats
    impact = normalised.get("impact_scores", {})
    overall = impact.get("overall_impact", {})
    emotional = normalised.get("emotional_timeline", {})
    effectiveness = normalised.get("effectiveness_drivers", {})

    logger.info(
        "[%s] Extraction v2.0 complete: overall_impact=%s, hook=%s, echo=%s | "
        "emotion_arc=%s, peak=%s | strengths=%d, weaknesses=%d | "
        "segments=%d, claims=%d, characters=%d | warnings=%d",
        external_id,
        overall.get("score", "null"),
        impact.get("hook_power", {}).get("score", "null"),
        impact.get("echo_score", {}).get("score", "null"),
        emotional.get("arc_shape", "unknown"),
        emotional.get("peak_emotion", "unknown"),
        len(effectiveness.get("strengths", [])),
        len(effectiveness.get("weaknesses", [])),
        len(normalised.get("segments", [])),
        len(normalised.get("claims", [])),
        len(normalised.get("characters", [])),
        len(normalised.get("extraction_warnings", [])),
    )

    return normalised


# Legacy function names for backwards compatibility
def _normalise_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy wrapper - calls v2 normalisation."""
    return _normalise_analysis_v2(data)


__all__ = [
    "analyse_ad_transcript",
    "extract_flat_metadata",
    "extract_jsonb_columns",
    "EXTRACTION_VERSION",
]
