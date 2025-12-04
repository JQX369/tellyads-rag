"""
Evidence aligner for claims and supers.

Provides grounding for extracted claims and supers by:
- Aligning them to transcript segments with timestamps
- Computing confidence scores based on match quality
- Generating evidence objects with source, excerpt, and match method
- Emitting warnings for ungrounded or low-confidence extractions
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from .extraction_warnings import WarningCode, add_warning

logger = logging.getLogger("tvads_rag.evidence_aligner")

# =============================================================================
# Constants
# =============================================================================

MAX_EXCERPT_LENGTH = 200
EXACT_MATCH_THRESHOLD = 0.90  # SequenceMatcher ratio for "exact" match
FUZZY_MATCH_THRESHOLD = 0.50  # Below this is "none"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Evidence:
    """Evidence object for a claim or super."""
    source: str  # "transcript" | "super" | "vision" | "ocr" | "unknown"
    excerpt: str  # Short text quote (<= 200 chars)
    match_method: str  # "exact" | "fuzzy" | "range" | "none"

    def to_dict(self) -> Dict[str, str]:
        return {
            "source": self.source,
            "excerpt": self.excerpt[:MAX_EXCERPT_LENGTH],
            "match_method": self.match_method,
        }


@dataclass
class AlignmentResult:
    """Result of aligning a claim/super to transcript."""
    timestamp_start_s: Optional[float]
    timestamp_end_s: Optional[float]
    evidence: Evidence
    confidence: float  # 0.0 - 1.0


# =============================================================================
# Text Matching Utilities
# =============================================================================

def _normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase, collapse whitespace."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _get_similarity(text1: str, text2: str) -> float:
    """Get similarity ratio between two strings (0.0 - 1.0)."""
    if not text1 or not text2:
        return 0.0
    n1 = _normalize_text(text1)
    n2 = _normalize_text(text2)
    return SequenceMatcher(None, n1, n2).ratio()


def _find_substring(needle: str, haystack: str) -> bool:
    """Check if needle is a substring of haystack (normalized)."""
    if not needle or not haystack:
        return False
    return _normalize_text(needle) in _normalize_text(haystack)


def _truncate_excerpt(text: str, max_len: int = MAX_EXCERPT_LENGTH) -> str:
    """Truncate text to max length, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3].rsplit(' ', 1)[0] + "..."


# =============================================================================
# Transcript Segment Alignment
# =============================================================================

def _find_best_segment_match(
    claim_text: str,
    segments: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], float, str]:
    """
    Find the best matching transcript segment for a claim.

    Args:
        claim_text: The claim text to match
        segments: List of transcript segments with {text, start, end}

    Returns:
        (best_segment, confidence, match_method)
    """
    if not claim_text or not segments:
        return None, 0.0, "none"

    best_segment = None
    best_score = 0.0
    best_method = "none"

    norm_claim = _normalize_text(claim_text)

    for seg in segments:
        seg_text = seg.get("text", "")
        if not seg_text:
            continue

        norm_seg = _normalize_text(seg_text)

        # Check for exact substring match first
        if norm_claim in norm_seg:
            # Exact substring match
            score = 1.0
            method = "exact"
        elif norm_seg in norm_claim:
            # Segment is subset of claim (claim spans multiple segments)
            score = len(norm_seg) / len(norm_claim) if norm_claim else 0
            method = "range"
        else:
            # Fuzzy match
            score = _get_similarity(claim_text, seg_text)
            method = "fuzzy" if score >= FUZZY_MATCH_THRESHOLD else "none"

        if score > best_score:
            best_score = score
            best_segment = seg
            best_method = method

    # Adjust match_method based on final score
    if best_score >= EXACT_MATCH_THRESHOLD:
        best_method = "exact"
    elif best_score >= FUZZY_MATCH_THRESHOLD:
        best_method = "fuzzy" if best_method == "none" else best_method
    else:
        best_method = "none"

    return best_segment, best_score, best_method


def _find_multi_segment_range(
    claim_text: str,
    segments: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float], str, float]:
    """
    Find timestamp range when a claim spans multiple segments.

    Returns:
        (start_s, end_s, combined_excerpt, confidence)
    """
    if not claim_text or not segments:
        return None, None, "", 0.0

    norm_claim = _normalize_text(claim_text)

    # Find all segments that contain parts of the claim
    matching_segments = []
    total_matched_len = 0

    for seg in segments:
        seg_text = seg.get("text", "")
        if not seg_text:
            continue

        norm_seg = _normalize_text(seg_text)

        # Check if any significant overlap
        sim = _get_similarity(norm_claim, norm_seg)
        if sim >= 0.3 or _find_substring(norm_seg, norm_claim):
            matching_segments.append(seg)
            total_matched_len += len(norm_seg)

    if not matching_segments:
        return None, None, "", 0.0

    # Sort by start time
    matching_segments.sort(key=lambda s: s.get("start", 0))

    start_s = matching_segments[0].get("start")
    end_s = matching_segments[-1].get("end")

    # Combine excerpts
    combined = " ".join(s.get("text", "") for s in matching_segments[:3])
    excerpt = _truncate_excerpt(combined)

    # Confidence based on coverage
    confidence = min(1.0, total_matched_len / max(len(norm_claim), 1))

    return start_s, end_s, excerpt, confidence


# =============================================================================
# Claim Alignment
# =============================================================================

def align_claim_to_transcript(
    claim: Dict[str, Any],
    transcript_segments: List[Dict[str, Any]],
    duration_seconds: Optional[float] = None,
    warnings_target: Optional[Dict[str, Any]] = None,
    claim_index: int = 0,
) -> Dict[str, Any]:
    """
    Align a claim to transcript segments and add evidence + timestamps.

    Args:
        claim: Claim dict with at least 'text'
        transcript_segments: List of {text, start, end} from ASR
        duration_seconds: Total video duration for validation
        warnings_target: Dict to add warnings to (optional)
        claim_index: Index of claim for warning context

    Returns:
        Enhanced claim dict with timestamp_start_s, timestamp_end_s, evidence, confidence
    """
    claim_text = claim.get("text", "")
    claim_id = claim.get("id") or f"claim_{claim_index}"

    # Start with any existing timestamp from extraction
    existing_ts = claim.get("timestamp_s")

    # Try to find best segment match
    best_seg, score, match_method = _find_best_segment_match(
        claim_text, transcript_segments
    )

    # If single segment match isn't great, try multi-segment range
    if score < EXACT_MATCH_THRESHOLD and transcript_segments:
        range_start, range_end, range_excerpt, range_conf = _find_multi_segment_range(
            claim_text, transcript_segments
        )
        if range_conf > score:
            # Use range match
            result = claim.copy()
            result["timestamp_start_s"] = range_start
            result["timestamp_end_s"] = range_end
            result["evidence"] = Evidence(
                source="transcript",
                excerpt=range_excerpt,
                match_method="range"
            ).to_dict()
            result["confidence"] = range_conf

            # Emit fuzzy match warning if confidence is low
            if range_conf < EXACT_MATCH_THRESHOLD and warnings_target is not None:
                add_warning(
                    warnings_target,
                    WarningCode.EVIDENCE_FUZZY_MATCH,
                    f"Claim '{claim_text[:50]}...' aligned with fuzzy range match (confidence={range_conf:.2f})",
                    {"claim_id": claim_id, "confidence": range_conf, "match_method": "range"},
                    log_level="debug"
                )

            return _validate_claim_timestamps(result, duration_seconds, warnings_target, claim_id)

    # Use single segment match or fallback
    if best_seg and match_method != "none":
        timestamp_start_s = best_seg.get("start")
        timestamp_end_s = best_seg.get("end")
        excerpt = _truncate_excerpt(best_seg.get("text", ""))
        confidence = score
        evidence = Evidence(
            source="transcript",
            excerpt=excerpt,
            match_method=match_method
        )
    elif existing_ts is not None:
        # Fall back to extraction timestamp (single point)
        timestamp_start_s = existing_ts
        timestamp_end_s = existing_ts + 2.0  # Assume ~2s for spoken claim
        excerpt = claim_text[:100]
        confidence = 0.5  # Medium confidence since we don't have real match
        evidence = Evidence(
            source="unknown",
            excerpt=excerpt,
            match_method="none"
        )
    else:
        # No grounding at all
        timestamp_start_s = None
        timestamp_end_s = None
        excerpt = ""
        confidence = 0.0
        evidence = Evidence(
            source="unknown",
            excerpt="",
            match_method="none"
        )

    # Build result
    result = claim.copy()
    result["timestamp_start_s"] = timestamp_start_s
    result["timestamp_end_s"] = timestamp_end_s
    result["evidence"] = evidence.to_dict()
    result["confidence"] = confidence

    # Emit warnings
    if match_method == "none" and warnings_target is not None:
        add_warning(
            warnings_target,
            WarningCode.EVIDENCE_NOT_GROUNDED,
            f"Claim '{claim_text[:50]}...' could not be grounded in transcript",
            {"claim_id": claim_id, "claim_text": claim_text[:100]},
            log_level="warning"
        )
    elif match_method == "fuzzy" and warnings_target is not None:
        add_warning(
            warnings_target,
            WarningCode.EVIDENCE_FUZZY_MATCH,
            f"Claim '{claim_text[:50]}...' has fuzzy match (confidence={confidence:.2f})",
            {"claim_id": claim_id, "confidence": confidence, "match_method": match_method},
            log_level="debug"
        )

    return _validate_claim_timestamps(result, duration_seconds, warnings_target, claim_id)


def _validate_claim_timestamps(
    claim: Dict[str, Any],
    duration_seconds: Optional[float],
    warnings_target: Optional[Dict[str, Any]],
    claim_id: str,
) -> Dict[str, Any]:
    """Validate and emit warnings for timestamp issues."""
    start_s = claim.get("timestamp_start_s")
    end_s = claim.get("timestamp_end_s")

    if start_s is None and end_s is None:
        if warnings_target is not None:
            add_warning(
                warnings_target,
                WarningCode.TIMESTAMP_MISSING,
                f"Claim '{claim_id}' has no timestamps",
                {"claim_id": claim_id},
                log_level="debug"
            )

    if duration_seconds is not None:
        if start_s is not None and (start_s < 0 or start_s > duration_seconds):
            if warnings_target is not None:
                add_warning(
                    warnings_target,
                    WarningCode.TIMESTAMP_OUT_OF_RANGE,
                    f"Claim '{claim_id}' start_s={start_s} out of range (duration={duration_seconds})",
                    {"claim_id": claim_id, "timestamp": start_s, "duration": duration_seconds},
                    log_level="warning"
                )
            # Clamp to valid range
            claim["timestamp_start_s"] = max(0, min(start_s, duration_seconds))

        if end_s is not None and (end_s < 0 or end_s > duration_seconds):
            if warnings_target is not None:
                add_warning(
                    warnings_target,
                    WarningCode.TIMESTAMP_OUT_OF_RANGE,
                    f"Claim '{claim_id}' end_s={end_s} out of range (duration={duration_seconds})",
                    {"claim_id": claim_id, "timestamp": end_s, "duration": duration_seconds},
                    log_level="warning"
                )
            # Clamp to valid range
            claim["timestamp_end_s"] = max(0, min(end_s, duration_seconds))

    return claim


# =============================================================================
# Super Alignment
# =============================================================================

def align_super_to_evidence(
    super_: Dict[str, Any],
    ocr_results: Optional[List[Dict[str, Any]]] = None,
    duration_seconds: Optional[float] = None,
    warnings_target: Optional[Dict[str, Any]] = None,
    super_index: int = 0,
) -> Dict[str, Any]:
    """
    Add evidence and confidence to a super.

    Supers already have timestamps from extraction (start_s, end_s mapped to start_time, end_time).
    This adds:
    - evidence with OCR source if available
    - confidence based on OCR match or extraction confidence

    Args:
        super_: Super dict with text, super_type, start_s/start_time, end_s/end_time
        ocr_results: Optional OCR results to match against
        duration_seconds: Total video duration for validation
        warnings_target: Dict to add warnings to (optional)
        super_index: Index of super for warning context

    Returns:
        Enhanced super dict with evidence and confidence
    """
    super_text = super_.get("text", "")
    super_id = super_.get("id") or f"super_{super_index}"

    # Get timestamps (extraction uses start_s/end_s, DB uses start_time/end_time)
    start_s = super_.get("start_s") or super_.get("start_time")
    end_s = super_.get("end_s") or super_.get("end_time")

    # Try to find OCR match
    ocr_match = None
    ocr_score = 0.0

    if ocr_results and super_text:
        for ocr in ocr_results:
            ocr_text = ocr.get("text", "")
            sim = _get_similarity(super_text, ocr_text)
            if sim > ocr_score:
                ocr_score = sim
                ocr_match = ocr

    # Build evidence
    if ocr_match and ocr_score >= FUZZY_MATCH_THRESHOLD:
        match_method = "exact" if ocr_score >= EXACT_MATCH_THRESHOLD else "fuzzy"
        evidence = Evidence(
            source="ocr",
            excerpt=_truncate_excerpt(ocr_match.get("text", "")),
            match_method=match_method
        )
        confidence = ocr_score
    elif super_text:
        # No OCR match, use vision as source (from LLM extraction)
        evidence = Evidence(
            source="vision",
            excerpt=_truncate_excerpt(super_text),
            match_method="exact"  # LLM saw it directly
        )
        confidence = 0.8  # High confidence for LLM extraction but not perfect
    else:
        evidence = Evidence(
            source="unknown",
            excerpt="",
            match_method="none"
        )
        confidence = 0.0

    # Build result
    result = super_.copy()
    result["evidence"] = evidence.to_dict()
    result["confidence"] = confidence

    # Validate timestamps
    if start_s is None and end_s is None:
        if warnings_target is not None:
            add_warning(
                warnings_target,
                WarningCode.TIMESTAMP_MISSING,
                f"Super '{super_id}' has no timestamps",
                {"super_id": super_id, "super_text": super_text[:50]},
                log_level="debug"
            )

    if duration_seconds is not None:
        if start_s is not None and (start_s < 0 or start_s > duration_seconds):
            if warnings_target is not None:
                add_warning(
                    warnings_target,
                    WarningCode.TIMESTAMP_OUT_OF_RANGE,
                    f"Super '{super_id}' start_time={start_s} out of range",
                    {"super_id": super_id, "timestamp": start_s, "duration": duration_seconds},
                    log_level="warning"
                )

        if end_s is not None and (end_s < 0 or end_s > duration_seconds):
            if warnings_target is not None:
                add_warning(
                    warnings_target,
                    WarningCode.TIMESTAMP_OUT_OF_RANGE,
                    f"Super '{super_id}' end_time={end_s} out of range",
                    {"super_id": super_id, "timestamp": end_s, "duration": duration_seconds},
                    log_level="warning"
                )

    # Emit ungrounded warning if no text
    if not super_text and warnings_target is not None:
        add_warning(
            warnings_target,
            WarningCode.EVIDENCE_NOT_GROUNDED,
            f"Super '{super_id}' has no text content",
            {"super_id": super_id},
            log_level="warning"
        )

    return result


# =============================================================================
# Batch Processing
# =============================================================================

def align_all_claims(
    claims: List[Dict[str, Any]],
    transcript_segments: List[Dict[str, Any]],
    duration_seconds: Optional[float] = None,
    warnings_target: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Align all claims to transcript and add evidence.

    Args:
        claims: List of claim dicts
        transcript_segments: List of {text, start, end} from ASR
        duration_seconds: Total video duration
        warnings_target: Dict to add warnings to

    Returns:
        List of enhanced claim dicts
    """
    result = []
    for i, claim in enumerate(claims or []):
        aligned = align_claim_to_transcript(
            claim,
            transcript_segments,
            duration_seconds,
            warnings_target,
            claim_index=i
        )
        result.append(aligned)
    return result


def align_all_supers(
    supers: List[Dict[str, Any]],
    ocr_results: Optional[List[Dict[str, Any]]] = None,
    duration_seconds: Optional[float] = None,
    warnings_target: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Add evidence and confidence to all supers.

    Args:
        supers: List of super dicts
        ocr_results: Optional OCR results
        duration_seconds: Total video duration
        warnings_target: Dict to add warnings to

    Returns:
        List of enhanced super dicts
    """
    result = []
    for i, super_ in enumerate(supers or []):
        aligned = align_super_to_evidence(
            super_,
            ocr_results,
            duration_seconds,
            warnings_target,
            super_index=i
        )
        result.append(aligned)
    return result


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "Evidence",
    "AlignmentResult",
    "align_claim_to_transcript",
    "align_super_to_evidence",
    "align_all_claims",
    "align_all_supers",
    "EXACT_MATCH_THRESHOLD",
    "FUZZY_MATCH_THRESHOLD",
]
