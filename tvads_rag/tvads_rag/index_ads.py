"""
CLI entry point for indexing TV ad videos into Supabase.
"""

from __future__ import annotations

import argparse
import functools
import logging
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, TypeVar

# Parallel processing configuration (conservative default: 3 workers)
PARALLEL_WORKERS = int(os.getenv("INGEST_PARALLEL_WORKERS", "3"))
_progress_lock = threading.Lock()

# Retry configuration
MAX_RETRIES = int(os.getenv("INGEST_MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = float(os.getenv("INGEST_RETRY_DELAY", "2.0"))

T = TypeVar("T")


def with_retry(
    max_retries: int = MAX_RETRIES,
    delay: float = RETRY_DELAY_SECONDS,
    exceptions: tuple = (Exception,),
    operation_name: str = "operation",
) -> Callable:
    """
    Decorator to retry a function on transient failures.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries (seconds), doubles each attempt
        exceptions: Tuple of exception types to catch and retry
        operation_name: Name for logging
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logging.getLogger("tvads_rag.index_ads").warning(
                            "%s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            operation_name, attempt + 1, max_retries + 1, 
                            str(e)[:100], wait_time
                        )
                        time.sleep(wait_time)
                    else:
                        logging.getLogger("tvads_rag.index_ads").error(
                            "%s failed after %d attempts: %s",
                            operation_name, max_retries + 1, str(e)[:200]
                        )
            raise last_exception  # type: ignore
        return wrapper
    return decorator

from . import asr, embeddings, media, visual_analysis, metadata_ingest, deep_analysis
from .visual_analysis import SafetyBlockError, StoryboardTimeoutError
from .analysis import analyse_ad_transcript, extract_flat_metadata, extract_jsonb_columns, EXTRACTION_VERSION
from .config import (
    describe_active_models,
    get_pipeline_config,
    get_storage_config,
    get_vision_config,
    is_vision_enabled,
)
from . import db_backend

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("tvads_rag.index_ads")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index TV ad videos into Supabase.")
    parser.add_argument("--source", choices=["local", "s3"], help="Video source (local or s3).")
    parser.add_argument("--limit", type=int, default=None, help="Number of ads to process.")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first N ads.")
    parser.add_argument("--single-path", help="Process a single local file (relative or absolute).")
    parser.add_argument("--single-key", help="Process a single S3 object key.")
    parser.add_argument(
        "--vision-tier",
        choices=["fast", "quality"],
        help="Override the default vision model tier (fast vs quality).",
    )
    parser.add_argument(
        "--metadata-csv",
        help="Optional CSV of legacy metadata (record_id, views, etc.) to enrich ads.",
    )
    # Retry incomplete ads
    parser.add_argument(
        "--retry-incomplete",
        action="store_true",
        help="Re-process ads with missing data (storyboard, v2 extraction, impact scores).",
    )
    parser.add_argument(
        "--retry-storyboard-only",
        action="store_true",
        help="Re-process only ads missing storyboard data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which ads would be re-processed without actually processing them.",
    )
    parser.add_argument(
        "--min-id",
        help="Minimum external_id to process (e.g., TA1665). Ads below this will be skipped.",
    )
    return parser.parse_args()


def _external_id_from_path(path: Path) -> str:
    return path.stem


def _external_id_from_key(key: str) -> str:
    return Path(key).stem


def _build_ad_payload(
    external_id: str,
    s3_key: Optional[str],
    probe: Dict[str, Optional[float]],
    transcript: Dict,
    analysis_result: Dict,
    *,
    metadata_entry: Optional[metadata_ingest.AdMetadataEntry] = None,
    performance_metrics: Optional[Dict] = None,
    hero_analysis: Optional[Dict] = None,
) -> Dict:
    """
    Build the ad payload for database insertion using v2.0 extraction.
    
    Extracts flat fields and JSONB columns from the analysis result.
    """
    # Extract flat fields from v2 analysis (brand_name, product_name, etc.)
    flat_fields = extract_flat_metadata(analysis_result)
    
    # Extract JSONB column data
    jsonb_columns = extract_jsonb_columns(analysis_result)
    
    # Ensure has_supers and has_price_claims are set
    flat_fields.setdefault("has_supers", bool(analysis_result.get("supers")))
    flat_fields.setdefault(
        "has_price_claims",
        any(
            (claim.get("claim_type") or "").lower() == "price"
            for claim in analysis_result.get("claims", [])
        ),
    )

    # Override with metadata_entry if provided
    if metadata_entry:
        if metadata_entry.brand_name:
            flat_fields["brand_name"] = metadata_entry.brand_name
        if metadata_entry.title and not flat_fields.get("one_line_summary"):
            flat_fields["one_line_summary"] = metadata_entry.title
        if metadata_entry.duration_seconds and not probe.get("duration_seconds"):
            probe["duration_seconds"] = metadata_entry.duration_seconds

    payload = {**flat_fields}
    payload.update(
        external_id=external_id,
        s3_key=s3_key,
        duration_seconds=probe.get("duration_seconds"),
        width=probe.get("width"),
        height=probe.get("height"),
        aspect_ratio=probe.get("aspect_ratio"),
        fps=probe.get("fps"),
        raw_transcript=transcript,
        analysis_json=analysis_result,
        performance_metrics=performance_metrics or {},
        hero_analysis=hero_analysis,
        # Extraction v2.0 JSONB columns
        impact_scores=jsonb_columns.get("impact_scores"),
        emotional_metrics=jsonb_columns.get("emotional_metrics"),
        effectiveness=jsonb_columns.get("effectiveness"),
        extraction_version=EXTRACTION_VERSION,
        # Legacy columns (for backwards compatibility)
        cta_offer=jsonb_columns.get("cta_offer"),
        brand_asset_timeline=jsonb_columns.get("brand_asset_timeline"),
        audio_fingerprint=jsonb_columns.get("audio_fingerprint"),
        creative_dna=jsonb_columns.get("creative_dna"),
        claims_compliance=jsonb_columns.get("claims_compliance"),
    )
    return payload


def _prepare_embedding_items(
    ad_id: str,
    analysis_result: Dict,
    chunk_ids: Sequence[str],
    segment_ids: Sequence[str],
    claim_ids: Sequence[str],
    super_ids: Sequence[str],
) -> List[Dict]:
    items: List[Dict] = []
    chunks = analysis_result.get("chunks", [])
    segments = analysis_result.get("segments", [])
    claims = analysis_result.get("claims", [])
    supers = analysis_result.get("supers", [])

    for chunk, chunk_id in zip(chunks, chunk_ids):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        items.append(
            {
                "ad_id": ad_id,
                "chunk_id": chunk_id,
                "item_type": "transcript_chunk",
                "text": text,
                "meta": {
                    "aida_stage": chunk.get("aida_stage"),
                    "tags": chunk.get("tags") or [],
                },
            }
        )

    for segment, segment_id in zip(segments, segment_ids):
        text = (segment.get("summary") or segment.get("transcript_text") or "").strip()
        if not text:
            continue
        items.append(
            {
                "ad_id": ad_id,
                "segment_id": segment_id,
                "item_type": "segment_summary",
                "text": text,
                "meta": {
                    "segment_type": segment.get("segment_type"),
                    "aida_stage": segment.get("aida_stage"),
                    "emotion_focus": segment.get("emotion_focus"),
                },
            }
        )

    for claim, claim_id in zip(claims, claim_ids):
        text = (claim.get("text") or "").strip()
        if not text:
            continue
        items.append(
            {
                "ad_id": ad_id,
                "claim_id": claim_id,
                "item_type": "claim",
                "text": text,
                "meta": {
                    "claim_type": claim.get("claim_type"),
                    "is_comparative": claim.get("is_comparative"),
                    "likely_needs_substantiation": claim.get("likely_needs_substantiation"),
                },
            }
        )

    for sup, sup_id in zip(supers, super_ids):
        text = (sup.get("text") or "").strip()
        if not text:
            continue
        items.append(
            {
                "ad_id": ad_id,
                "super_id": sup_id,
                "item_type": "super",
                "text": text,
                "meta": {"super_type": sup.get("super_type")},
            }
        )

    metadata = analysis_result.get("ad_metadata") or {}
    summary_text = (metadata.get("story_summary") or metadata.get("one_line_summary") or "").strip()
    if summary_text:
        items.append(
            {
                "ad_id": ad_id,
                "item_type": "ad_summary",
                "text": summary_text,
                "meta": {
                    "objective": metadata.get("objective"),
                    "funnel_stage": metadata.get("funnel_stage"),
                },
            }
        )

    return items


def _prepare_storyboard_embedding_items(
    ad_id: str,
    storyboard_ids: Sequence[str],
    storyboard_shots: Sequence[Dict],
) -> List[Dict]:
    items: List[Dict] = []
    for shot, shot_id in zip(storyboard_shots, storyboard_ids):
        label = shot.get("shot_label") or f"Shot {shot.get('shot_index', 'n/a')}"
        description = shot.get("description") or ""
        mood = shot.get("mood") or ""
        camera = shot.get("camera_style") or ""
        sections = [
            f"Shot: {label}",
            f"Description: {description}".rstrip(),
            f"Mood: {mood}".rstrip(),
            f"Camera: {camera}".rstrip(),
        ]
        text = "\n".join(section for section in sections if section.strip())
        meta = {
            "shot_index": shot.get("shot_index"),
            "mood": shot.get("mood"),
            "location_hint": shot.get("location_hint"),
        }
        items.append(
            {
                "ad_id": ad_id,
                "storyboard_id": shot_id,
                "item_type": "storyboard_shot",
                "text": text,
                "meta": {k: v for k, v in meta.items() if v is not None},
            }
        )
    return items


def _prepare_extended_embedding_items(
    ad_id: str,
    analysis_result: Dict,
) -> List[Dict]:
    """
    Prepare embedding items for high-leverage texts from extended extraction fields.
    
    Embeds (Moderate Strategy):
    - impact_summary: Combined impact scores with rationale
    - memorable_elements: From memorability.memorable_elements
    - emotional_peaks: Peak emotional moments from timeline
    - distinctive_assets: Asset descriptions with brand linkage
    - effectiveness_insight: Strengths and weaknesses summaries
    - implied_claims: From compliance_assessment
    - cta_offer: Offer summary + endcard text
    - creative_dna: Archetype + devices + hook + arc
    """
    items: List[Dict] = []

    # 1. Impact Summary - Combined impact scores with rationale
    impact_scores = analysis_result.get("impact_scores") or {}
    impact_parts = []
    for score_name in ["overall_impact", "pulse_score", "echo_score", "hook_power", 
                       "brand_integration", "emotional_resonance", "clarity_score", "distinctiveness"]:
        score_data = impact_scores.get(score_name, {})
        if isinstance(score_data, dict) and score_data.get("score"):
            score_val = score_data.get("score", 0)
            rationale = score_data.get("rationale") or score_data.get("evidence") or ""
            if rationale:
                impact_parts.append(f"{score_name}: {score_val}/10 - {rationale[:100]}")
            else:
                impact_parts.append(f"{score_name}: {score_val}/10")
    
    if impact_parts:
        items.append({
            "ad_id": ad_id,
            "item_type": "impact_summary",
            "text": " | ".join(impact_parts),
            "meta": {
                "overall_score": impact_scores.get("overall_impact", {}).get("score"),
                "confidence": impact_scores.get("overall_impact", {}).get("confidence"),
            },
        })

    # 2. Memorable Elements - From memorability section
    memorability = analysis_result.get("memorability") or {}
    memorable_elements = memorability.get("memorable_elements") or []
    for element in memorable_elements:
        if not isinstance(element, dict):
            continue
        element_text = element.get("element", "")
        if not element_text:
            continue
        brand_linked = "brand-linked" if element.get("brand_linked") else "not brand-linked"
        score = element.get("memorability_score", 0)
        items.append({
            "ad_id": ad_id,
            "item_type": "memorable_elements",
            "text": f"{element_text} (memorability: {score}/10, {brand_linked})",
            "meta": {
                "memorability_score": score,
                "brand_linked": element.get("brand_linked"),
                "overall_memorability": memorability.get("overall_memorability_score"),
            },
        })

    # 3. Emotional Peaks - Peak moments from emotional timeline
    emotional_timeline = analysis_result.get("emotional_timeline") or {}
    peak_moment = emotional_timeline.get("peak_moment_s")
    peak_emotion = emotional_timeline.get("peak_emotion")
    arc_shape = emotional_timeline.get("arc_shape")
    
    if peak_emotion and arc_shape:
        items.append({
            "ad_id": ad_id,
            "item_type": "emotional_peaks",
            "text": f"Emotional arc: {arc_shape} | Peak emotion: {peak_emotion} at {peak_moment}s | "
                    f"Average intensity: {emotional_timeline.get('average_intensity', 0):.1f} | "
                    f"Positive ratio: {emotional_timeline.get('positive_ratio', 0):.0%}",
            "meta": {
                "arc_shape": arc_shape,
                "peak_emotion": peak_emotion,
                "peak_moment_s": peak_moment,
            },
        })

    # 4. Distinctive Assets - Asset descriptions with brand linkage
    distinctive_assets = analysis_result.get("distinctive_assets") or []
    for asset in distinctive_assets:
        if not isinstance(asset, dict):
            continue
        description = asset.get("description", "")
        if not description:
            continue
        asset_type = asset.get("asset_type", "unknown")
        brand_linkage = asset.get("brand_linkage", 0)
        ownable = "ownable" if asset.get("is_ownable") else "not ownable"
        items.append({
            "ad_id": ad_id,
            "item_type": "distinctive_assets",
            "text": f"{asset_type}: {description} (brand linkage: {brand_linkage:.0%}, {ownable})",
            "meta": {
                "asset_type": asset_type,
                "brand_linkage": brand_linkage,
                "recognition_potential": asset.get("recognition_potential"),
            },
        })

    # 5. Effectiveness Insight - Strengths and weaknesses summaries
    effectiveness = analysis_result.get("effectiveness_drivers") or {}
    
    # Strengths
    for strength in effectiveness.get("strengths", []):
        if not isinstance(strength, dict):
            continue
        driver = strength.get("driver", "")
        if not driver:
            continue
        impact = strength.get("impact", "medium")
        evidence = strength.get("evidence", "")
        items.append({
            "ad_id": ad_id,
            "item_type": "effectiveness_insight",
            "text": f"STRENGTH ({impact} impact): {driver} - {evidence[:100]}",
            "meta": {
                "insight_type": "strength",
                "impact": impact,
            },
        })
    
    # Weaknesses
    for weakness in effectiveness.get("weaknesses", []):
        if not isinstance(weakness, dict):
            continue
        driver = weakness.get("driver", "")
        if not driver:
            continue
        impact = weakness.get("impact", "medium")
        fix = weakness.get("fix_suggestion", "")
        items.append({
            "ad_id": ad_id,
            "item_type": "effectiveness_insight",
            "text": f"WEAKNESS ({impact} impact): {driver} - Fix: {fix[:100]}",
            "meta": {
                "insight_type": "weakness",
                "impact": impact,
                "fix_difficulty": weakness.get("fix_difficulty"),
            },
        })

    # 6. Implied claims from compliance_assessment
    compliance = analysis_result.get("compliance_assessment") or {}
    for issue in compliance.get("potential_issues", []):
        if not isinstance(issue, dict):
            continue
        description = issue.get("description", "")
        if not description:
            continue
        issue_type = issue.get("issue_type", "other")
        risk = issue.get("risk_level", "low")
        items.append({
            "ad_id": ad_id,
            "item_type": "implied_claim",
            "text": f"{issue_type} ({risk} risk): {description}",
            "meta": {
                "issue_type": issue_type,
                "risk_level": risk,
                "overall_risk": compliance.get("overall_risk"),
            },
        })

    # 7. CTA offer summary + endcard text
    cta_offer = analysis_result.get("cta_offer") or {}
    cta_parts = []
    if cta_offer.get("offer_summary"):
        cta_parts.append(f"Offer: {cta_offer['offer_summary']}")
    if cta_offer.get("price_shown"):
        cta_parts.append(f"Price: {cta_offer['price_shown']}")
    if cta_offer.get("deadline_mentioned"):
        cta_parts.append(f"Urgency: {cta_offer['deadline_mentioned']}")
    if cta_offer.get("cta_text"):
        cta_parts.append(f"CTA: {cta_offer['cta_text']}")
    endcard_elements = cta_offer.get("endcard_elements") or []
    if endcard_elements:
        cta_parts.append(f"Endcard: {', '.join(endcard_elements)}")

    if cta_parts:
        items.append({
            "ad_id": ad_id,
            "item_type": "cta_offer",
            "text": " | ".join(cta_parts),
            "meta": {
                "cta_type": cta_offer.get("cta_type"),
                "has_offer": cta_offer.get("has_offer"),
                "urgency_present": cta_offer.get("urgency_present"),
            },
        })

    # 8. Creative DNA summary
    creative_dna = analysis_result.get("creative_dna") or {}
    dna_parts = []
    if creative_dna.get("archetype"):
        dna_parts.append(f"Archetype: {creative_dna['archetype']}")
    if creative_dna.get("hook_type"):
        dna_parts.append(f"Hook: {creative_dna['hook_type']}")
    if creative_dna.get("narrative_structure"):
        dna_parts.append(f"Structure: {creative_dna['narrative_structure']}")
    devices = creative_dna.get("persuasion_devices") or []
    if devices:
        dna_parts.append(f"Persuasion: {', '.join(devices[:5])}")
    distinctive = creative_dna.get("distinctive_creative_choices") or []
    if distinctive:
        dna_parts.append(f"Distinctive: {', '.join(distinctive[:3])}")

    if dna_parts:
        items.append({
            "ad_id": ad_id,
            "item_type": "creative_dna",
            "text": " | ".join(dna_parts),
            "meta": {
                "archetype": creative_dna.get("archetype"),
                "persuasion_devices": devices,
            },
        })

    return items


def _embed_and_store(ad_id: str, items: List[Dict]) -> None:
    """Generate embeddings and store them with retry for transient network errors."""
    texts = [item["text"] for item in items]
    vectors = embeddings.embed_texts(texts)
    for item, vector in zip(items, vectors):
        item["embedding"] = vector
    
    # Retry logic for transient network errors (Windows socket errors, etc.)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            db_backend.insert_embedding_items(ad_id, items)
            return
        except Exception as e:
            error_str = str(e)
            # Check for transient network errors
            is_transient = any(x in error_str for x in [
                "WinError 10035",  # Windows socket busy
                "WriteError",
                "ConnectionError",
                "TimeoutError",
                "socket",
            ])
            if is_transient and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                logger.warning(
                    "Embedding insert failed (attempt %d/%d): %s. Retrying in %ds...",
                    attempt + 1, max_retries, error_str[:100], wait_time
                )
                time.sleep(wait_time)
            else:
                raise


def _process_local_files(
    paths: Sequence[Path],
) -> List[Tuple[str, Optional[str], Path]]:
    return [( _external_id_from_path(path), None, path) for path in paths]


def _is_compilation_file(external_id: str) -> bool:
    """
    Check if the external_id represents a compilation file (e.g., TA10022-TA10034).
    
    Compilation files are created every ~10 ads and contain multiple ads merged together.
    These should be skipped during ingestion.
    """
    # Check for range pattern: TA####-TA#### or TA####-####
    if "-" in external_id:
        parts = external_id.split("-")
        if len(parts) == 2:
            # Both parts look like TA numbers or just numbers
            p1 = parts[0].replace("TA", "")
            p2 = parts[1].replace("TA", "")
            try:
                int(p1)
                int(p2)
                return True  # It's a range like TA10022-TA10034 or TA10022-10034
            except ValueError:
                pass
    return False


def _process_s3_keys(
    keys: Sequence[str], bucket: str, min_external_id: Optional[str] = None
) -> List[Tuple[str, Optional[str], str]]:
    """
    Process S3 keys into worklist tuples (external_id, s3_key, location).
    
    Args:
        keys: List of S3 keys
        bucket: S3 bucket name
        min_external_id: Optional minimum external_id to process (e.g., "TA1665")
                        Ads with external_id < min_external_id will be skipped.
    """
    worklist = []
    skipped_compilations = 0
    skipped_below_min = 0
    
    for key in keys:
        external_id = _external_id_from_key(key)
        
        # Skip compilation files (ranges like TA10022-TA10034)
        if _is_compilation_file(external_id):
            skipped_compilations += 1
            logger.debug("Skipping compilation file: %s", external_id)
            continue
        
        # Filter by minimum external_id if specified
        if min_external_id:
            # Extract numeric part for comparison (e.g., "TA1665" -> 1665)
            try:
                ext_num = int(external_id.replace("TA", ""))
                min_num = int(min_external_id.replace("TA", ""))
                if ext_num < min_num:
                    skipped_below_min += 1
                    logger.debug("Skipping %s (below minimum %s)", external_id, min_external_id)
                    continue
            except (ValueError, AttributeError):
                # If we can't parse, include it (safer to process than skip)
                logger.debug("Could not parse external_id %s for comparison, including anyway", external_id)
        
        worklist.append((external_id, key, key))
    
    if skipped_compilations > 0:
        logger.info("Skipped %d compilation files (merged ad ranges)", skipped_compilations)
    if skipped_below_min > 0:
        logger.info("Skipped %d ads below minimum ID %s", skipped_below_min, min_external_id)
    
    return worklist


def _load_video(
    source: str,
    location: Path | str,
    bucket: Optional[str],
) -> Path:
    if source == "local":
        return Path(location).resolve()
    if not bucket:
        raise RuntimeError("S3 bucket must be configured for S3 source.")
    return media.download_s3_object_to_tempfile(bucket, str(location))


def _cleanup_files(*paths: Optional[Path]) -> None:
    for path in paths:
        if path and path.exists():
            try:
                path.unlink()
            except OSError:
                logger.warning("Failed to remove temp file %s", path)


def _transcribe_with_retry(audio_path: str, external_id: str) -> Dict:
    """Transcribe audio with retry logic for transient failures."""
    @with_retry(max_retries=2, delay=3.0, operation_name=f"ASR ({external_id})")
    def _do_transcribe():
        return asr.transcribe_audio(audio_path)
    return _do_transcribe()


def _analyse_with_retry(transcript: Dict, external_id: str) -> Dict:
    """Run LLM analysis with retry logic for API failures."""
    @with_retry(max_retries=2, delay=5.0, operation_name=f"LLM analysis ({external_id})")
    def _do_analyse():
        return analyse_ad_transcript(transcript)
    return _do_analyse()


def _storyboard_with_retry(
    frame_samples: List[visual_analysis.FrameSample], 
    tier: str, 
    external_id: str,
    transcript_text: Optional[str] = None
) -> List[Dict]:
    """Run storyboard analysis with retry logic."""
    @with_retry(max_retries=2, delay=3.0, operation_name=f"Storyboard ({external_id})")
    def _do_storyboard():
        return visual_analysis.analyse_frames_to_storyboard(
            frame_samples, tier=tier, transcript_text=transcript_text
        )
    return _do_storyboard()


def _extract_trigger_timestamps(transcript: Dict, brand_name: Optional[str] = None) -> List[float]:
    """Extract timestamps for high-value keywords (CTA, brand) from transcript."""
    if not transcript or "segments" not in transcript:
        return []
    
    triggers = []
    keywords = {"call", "visit", "website", ".com", "scan", "text", "download", "app", "now", "offer", "limited"}
    
    # Add brand name parts if available
    if brand_name:
        for part in str(brand_name).lower().split():
            if len(part) > 3:  # Avoid short words like "the", "and"
                keywords.add(part)
    
    for segment in transcript["segments"]:
        text = segment.get("text", "").lower()
        start = segment.get("start", 0.0)
        
        # Check for keywords
        if any(k in text for k in keywords):
            # Add start time of segment
            triggers.append(start)
            
            # Also add middle of segment if it's long (> 2s)
            end = segment.get("end", start)
            if end - start > 2.0:
                triggers.append(start + (end - start) / 2)
                
    return sorted(list(set(triggers)))


def process_ad_record(
    *,
    source: str,
    external_id: str,
    s3_key: Optional[str],
    location: Path | str,
    bucket: Optional[str],
    vision_tier: Optional[str] = None,
    metadata_entry: Optional[metadata_ingest.AdMetadataEntry] = None,
    hero_required: bool = False,
) -> None:
    """
    Process a single ad record through the full ingestion pipeline.
    
    Pipeline stages:
    1. Video download (if S3)
    2. Audio extraction
    3. ASR transcription
    4. LLM analysis (v2.0 extraction)
    5. Hero analysis (if required)
    6. Database insertion
    7. Vision/storyboard analysis
    8. Embedding generation
    
    Each stage has error handling; non-critical failures (storyboard, hero)
    won't fail the entire ad.
    """
    if db_backend.ad_exists(external_id=external_id, s3_key=s3_key):
        logger.info("Skipping %s (already indexed)", external_id)
        return

    start_time = time.time()
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    temp_audio_dir: Optional[Path] = None
    vision_cfg = get_vision_config()
    vision_enabled = is_vision_enabled(vision_cfg)
    frame_samples: List[visual_analysis.FrameSample] = []
    effective_tier = vision_tier or vision_cfg.default_tier
    hero_analysis: Optional[Dict] = None
    
    try:
        # Stage 1: Load video
        logger.debug("[%s] Stage 1: Loading video...", external_id)
        try:
            video_path = _load_video(source, location, bucket)
            if not video_path or not video_path.exists():
                raise FileNotFoundError(f"Failed to load video for {external_id}")
        except FileNotFoundError as e:
            # Missing S3 file - skip gracefully
            logger.warning(
                "[%s] Skipping - video file not found: %s",
                external_id, str(e)
            )
            return  # Skip this ad, don't fail the entire batch
        
        # Stage 2: Probe and extract audio
        logger.debug("[%s] Stage 2: Probing media and extracting audio...", external_id)
        probe = media.probe_media(str(video_path))
        if not probe.get("duration_seconds"):
            logger.warning("[%s] Could not determine video duration", external_id)
        
        temp_audio_dir = Path(tempfile.mkdtemp(prefix="tvads_audio_"))
        audio_path = media.extract_audio(str(video_path), out_dir=str(temp_audio_dir))
        if not audio_path or not audio_path.exists():
            raise RuntimeError(f"Audio extraction failed for {external_id}")
        
        # Stage 3: Transcription (with retry)
        logger.debug("[%s] Stage 3: Transcribing audio...", external_id)
        transcript = _transcribe_with_retry(str(audio_path), external_id)
        if not transcript.get("text"):
            logger.warning("[%s] Transcript is empty - ad may have no spoken audio", external_id)
        
        # Stage 4: LLM Analysis (with retry)
        logger.debug("[%s] Stage 4: Running LLM analysis...", external_id)
        analysis_result = _analyse_with_retry(transcript, external_id)

        # Stage 5: Hero analysis (optional, non-blocking)
        if hero_required:
            logger.debug("[%s] Stage 5: Running hero analysis...", external_id)
            transcript_text = transcript.get("text") or ""
            try:
                hero_analysis = deep_analysis.analyse_hero_ad(
                    str(video_path),
                    transcript_text,
                    tier="quality",
                )
                logger.info("Hero analysis captured for %s", external_id)
            except Exception as e:
                logger.warning("Hero analysis failed for %s: %s", external_id, str(e)[:100])
                hero_analysis = None

        # Prepare performance metrics from metadata
        perf_metrics: Optional[Dict] = None
        if metadata_entry:
            perf_metrics = {}
            if metadata_entry.views is not None:
                perf_metrics["views"] = metadata_entry.views
            if metadata_entry.date_collected:
                perf_metrics["date_collected"] = metadata_entry.date_collected
            if metadata_entry.raw_row.get("latest_ads"):
                perf_metrics["latest_ads_path"] = metadata_entry.raw_row.get("latest_ads")
            if metadata_entry.record_id:
                perf_metrics["legacy_record_id"] = metadata_entry.record_id
            if not perf_metrics:
                perf_metrics = None

        # Stage 6: Database insertion
        logger.debug("[%s] Stage 6: Inserting into database...", external_id)
        ad_payload = _build_ad_payload(
            external_id,
            s3_key,
            probe,
            transcript,
            analysis_result,
            metadata_entry=metadata_entry,
            performance_metrics=perf_metrics,
            hero_analysis=hero_analysis,
        )
        ad_id = db_backend.insert_ad(ad_payload)

        # Insert child records
        segment_ids = db_backend.insert_segments(ad_id, analysis_result.get("segments", []))
        chunk_ids = db_backend.insert_chunks(ad_id, analysis_result.get("chunks", []))
        claim_ids = db_backend.insert_claims(ad_id, analysis_result.get("claims", []))
        super_ids = db_backend.insert_supers(ad_id, analysis_result.get("supers", []))

        # Stage 7: Vision/storyboard (optional, non-blocking with retry)
        storyboard_items: List[Dict] = []
        processing_notes: Dict = {}
        if vision_enabled:
            logger.debug("[%s] Stage 7: Running storyboard analysis...", external_id)
            try:
                # Extract trigger timestamps from transcript
                transcript_text = transcript.get("text") or ""
                brand_name = analysis_result.get("brand_name") 
                if not brand_name and metadata_entry:
                    brand_name = metadata_entry.brand_name
                
                trigger_timestamps = _extract_trigger_timestamps(transcript, brand_name)
                if trigger_timestamps:
                    logger.debug("[%s] Found %d audio trigger timestamps", external_id, len(trigger_timestamps))

                frame_samples = visual_analysis.sample_frames_for_storyboard(
                    str(video_path), 
                    vision_cfg.frame_sample_seconds,
                    trigger_timestamps=trigger_timestamps
                )
                storyboard_shots = _storyboard_with_retry(
                    frame_samples, 
                    effective_tier, 
                    external_id,
                    transcript_text=transcript_text
                )
                storyboard_ids = db_backend.insert_storyboards(ad_id, storyboard_shots)
                storyboard_items = _prepare_storyboard_embedding_items(
                    ad_id, storyboard_ids, storyboard_shots
                )
            except SafetyBlockError as e:
                logger.warning(
                    "[%s] Storyboard blocked by safety filter: %s",
                    external_id, e.reason
                )
                processing_notes["storyboard_error"] = {
                    "type": "safety_block",
                    "reason": e.reason,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                storyboard_items = []
            except StoryboardTimeoutError as e:
                logger.warning("[%s] Storyboard analysis timed out: %s", external_id, str(e))
                processing_notes["storyboard_error"] = {
                    "type": "timeout",
                    "reason": str(e),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                storyboard_items = []
            except Exception as e:
                logger.exception("Storyboard analysis failed for %s", external_id)
                processing_notes["storyboard_error"] = {
                    "type": "error",
                    "reason": str(e)[:500],
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                storyboard_items = []
        
        # Store processing notes if any issues occurred
        if processing_notes:
            try:
                db_backend.update_processing_notes(ad_id, processing_notes)
                logger.info(
                    "[%s] Recorded processing notes: %s",
                    external_id, list(processing_notes.keys())
                )
            except Exception as notes_err:
                logger.warning(
                    "[%s] Failed to store processing notes: %s",
                    external_id, str(notes_err)[:100]
                )

        embedding_items = _prepare_embedding_items(
            ad_id,
            analysis_result,
            chunk_ids,
            segment_ids,
            claim_ids,
            super_ids,
        )
        if storyboard_items:
            embedding_items.extend(storyboard_items)

        # Add extended embeddings for new extraction fields (Nov 2025)
        extended_items = _prepare_extended_embedding_items(ad_id, analysis_result)
        if extended_items:
            embedding_items.extend(extended_items)
            logger.debug("Added %d extended embedding items", len(extended_items))

        # Stage 8: Embeddings
        logger.debug("[%s] Stage 8: Generating embeddings...", external_id)
        if embedding_items:
            _embed_and_store(ad_id, embedding_items)

        elapsed = time.time() - start_time
        logger.info(
            "Processed ad %s (%s) in %.1fs — segments=%d, claims=%d, storyboard=%d, embeddings=%d",
            ad_id, external_id, elapsed,
            len(segment_ids), len(claim_ids), 
            len(storyboard_items), len(embedding_items)
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            "Failed to process %s after %.1fs: %s",
            external_id, elapsed, str(e)[:200]
        )
        raise
    finally:
        # Cleanup temp files
        if frame_samples:
            visual_analysis.cleanup_frame_samples(frame_samples)
        _cleanup_files(audio_path)
        if temp_audio_dir and temp_audio_dir.exists():
            try:
                temp_audio_dir.rmdir()
            except OSError:
                logger.debug("Could not remove temp directory %s", temp_audio_dir)
        if source == "s3":
            _cleanup_files(video_path)


def _run_retry_incomplete(args, storage_cfg, metadata_index, vision_tier) -> None:
    """Re-process ads with incomplete data."""
    # Determine what to check for
    check_storyboard = True
    check_v2 = not args.retry_storyboard_only
    check_impact = not args.retry_storyboard_only
    
    logger.info(
        "Finding incomplete ads (storyboard=%s, v2=%s, impact=%s)...",
        check_storyboard, check_v2, check_impact
    )
    
    incomplete = db_backend.find_incomplete_ads(
        check_storyboard=check_storyboard,
        check_v2_extraction=check_v2,
        check_impact_scores=check_impact,
        limit=args.limit or 100,
    )
    
    if not incomplete:
        logger.info("No incomplete ads found!")
        return
    
    logger.info("Found %d incomplete ads:", len(incomplete))
    for ad in incomplete:
        logger.info(
            "  %s: missing %s",
            ad["external_id"],
            ", ".join(ad["missing"])
        )
    
    if args.dry_run:
        logger.info("Dry run - no ads will be re-processed")
        return
    
    # Build worklist from incomplete ads that have S3 keys
    worklist = []
    for ad in incomplete:
        if ad.get("s3_key"):
            # Delete the old ad first
            logger.info("Deleting old ad %s for re-processing...", ad["external_id"])
            db_backend.delete_ad(ad["id"])
            worklist.append((ad["external_id"], ad["s3_key"], ad["s3_key"]))
        else:
            logger.warning(
                "Skipping %s - no S3 key available for re-download",
                ad["external_id"]
            )
    
    if not worklist:
        logger.info("No ads with S3 keys to re-process")
        return
    
    logger.info("Re-processing %d ads...", len(worklist))
    
    success = 0
    failed = 0
    total = len(worklist)
    
    for ext_id, s3_key, _ in worklist:
        try:
            process_ad_record(
                source="s3",
                external_id=ext_id,
                s3_key=s3_key,
                location=s3_key,
                bucket=storage_cfg.s3_bucket,
                vision_tier=vision_tier,
                metadata_entry=metadata_index.get(ext_id) if metadata_index else None,
                hero_required=False,
            )
            success += 1
            logger.info("Progress: %d/%d completed (%d failed)", success + failed, total, failed)
        except Exception:
            logger.exception("Failed to re-process %s", ext_id)
            failed += 1
    
    logger.info("Completed retry: %s/%s succeeded", success, total)


def main() -> None:
    args = _parse_args()
    storage_cfg = get_storage_config()
    pipeline_cfg = get_pipeline_config()
    metadata_index: Optional[metadata_ingest.MetadataIndex] = None
    if args.metadata_csv:
        metadata_index = metadata_ingest.load_metadata(args.metadata_csv)
    model_summary = describe_active_models()
    logger.info(
        "Active models • text=%s | embeddings=%s | vision=%s | rerank=%s",
        model_summary["text_llm"],
        model_summary["embeddings"],
        model_summary.get("vision_display", f"{model_summary['vision_provider']}({model_summary['vision_model']})"),
        model_summary["rerank_provider"],
    )
    backend_mode = os.getenv("DB_BACKEND", "postgres")
    logger.info("DB backend • mode=%s", backend_mode)
    source = args.source or pipeline_cfg.index_source_default
    vision_tier = args.vision_tier
    
    # Handle retry-incomplete mode
    if args.retry_incomplete or args.retry_storyboard_only:
        _run_retry_incomplete(args, storage_cfg, metadata_index, vision_tier)
        return

    if source == "local":
        paths = media.list_local_videos(
            storage_cfg.local_video_dir,
            limit=args.limit,
            offset=args.offset,
            single_path=args.single_path,
        )
        worklist = _process_local_files(paths)
    else:
        keys = media.list_s3_videos(
            storage_cfg.s3_bucket,
            storage_cfg.s3_prefix or "",
            limit=args.limit,
            offset=args.offset,
            single_key=args.single_key,
        )
        # Get minimum external_id from CLI arg or env var (optional)
        min_external_id = args.min_id or os.getenv("MIN_EXTERNAL_ID", None)
        if min_external_id:
            logger.info("Filtering: Only processing ads >= %s", min_external_id)
        worklist = _process_s3_keys(keys, storage_cfg.s3_bucket, min_external_id=min_external_id)

    logger.info(
        "Starting ingestion of %s ads from %s (parallel workers: %d)",
        len(worklist), source, PARALLEL_WORKERS
    )

    # Prepare job arguments for each ad
    def _get_job_args(external_id: str, s3_key: Optional[str], location):
        metadata_entry = None
        hero_required = False
        if metadata_index:
            metadata_entry = metadata_index.get(external_id)
            if not metadata_entry and isinstance(location, Path):
                metadata_entry = metadata_index.get(location.stem)
            if not metadata_entry and s3_key:
                metadata_entry = metadata_index.get(Path(str(s3_key)).stem)
            if metadata_entry and metadata_index.is_hero(metadata_entry.external_id):
                hero_required = True
        return {
            "source": source,
            "external_id": external_id,
            "s3_key": s3_key,
            "location": location,
            "bucket": storage_cfg.s3_bucket,
            "vision_tier": vision_tier,
            "metadata_entry": metadata_entry,
            "hero_required": hero_required,
        }

    success = 0
    failed = 0
    total = len(worklist)

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        # Submit all jobs
        futures = {
            executor.submit(process_ad_record, **_get_job_args(ext_id, s3_key, loc)): ext_id
            for ext_id, s3_key, loc in worklist
        }

        # Process completed futures
        for future in as_completed(futures):
            ext_id = futures[future]
            try:
                future.result()
                with _progress_lock:
                    success += 1
                    logger.info(
                        "Progress: %d/%d completed (%d failed)",
                        success + failed, total, failed
                    )
            except Exception:
                logger.exception("Failed to process %s", ext_id)
                with _progress_lock:
                    failed += 1

    logger.info("Completed ingestion: %s/%s succeeded", success, total)


if __name__ == "__main__":
    main()

