"""
Type definitions for the TV Ads RAG pipeline.

Provides TypedDict definitions for structured data passing through the pipeline.
This enables better IDE autocomplete and type checking.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict, Union


# ---------------------------------------------------------------------------
# Media/Probe Types
# ---------------------------------------------------------------------------

class ProbeResult(TypedDict, total=False):
    """Result from ffprobe media analysis."""
    duration_seconds: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    codec: Optional[str]
    bitrate: Optional[int]
    has_audio: bool


# ---------------------------------------------------------------------------
# Transcript Types
# ---------------------------------------------------------------------------

class TranscriptSegment(TypedDict, total=False):
    """A segment of transcribed audio."""
    start: float
    end: float
    text: str


class TranscriptResult(TypedDict, total=False):
    """Result from ASR transcription."""
    text: str
    segments: List[TranscriptSegment]
    language: Optional[str]
    duration: Optional[float]


# ---------------------------------------------------------------------------
# Analysis Types (v2.0 extraction)
# ---------------------------------------------------------------------------

class ImpactScore(TypedDict, total=False):
    """Individual impact score with metadata."""
    score: float
    description: str
    confidence: float


class ImpactScores(TypedDict, total=False):
    """All impact scores from analysis."""
    pulse: ImpactScore
    echo: ImpactScore
    hook_power: ImpactScore
    brand_integration: ImpactScore
    emotional_resonance: ImpactScore
    clarity_score: ImpactScore
    distinctiveness: ImpactScore


class EmotionalReading(TypedDict, total=False):
    """Single emotional timeline reading."""
    timestamp_s: float
    dominant_emotion: str
    secondary_emotion: Optional[str]
    intensity: float
    trigger: Optional[str]


class EmotionalTimeline(TypedDict, total=False):
    """Emotional arc of the ad."""
    readings: List[EmotionalReading]
    arc_shape: str
    peak_moment_s: Optional[float]
    peak_emotion: Optional[str]
    average_intensity: float
    positive_ratio: float


class Character(TypedDict, total=False):
    """Character in the ad."""
    role: str
    description: str
    screen_time_pct: float
    age_range: str
    gender: str
    ethnicity: Dict[str, Any]
    physical_traits: Dict[str, Any]


class CastDiversity(TypedDict, total=False):
    """Cast diversity metrics."""
    total_characters: int
    gender_breakdown: Dict[str, int]
    ethnicity_breakdown: Dict[str, int]
    age_range_present: List[str]
    diversity_score: float
    representation_notes: str


class AnalysisResult(TypedDict, total=False):
    """
    Full LLM analysis result (v2.0 extraction).
    
    Contains 22 sections of structured creative analysis.
    """
    # Core identification
    brand_name: str
    product_name: Optional[str]
    industry: str
    sub_industry: Optional[str]
    
    # Format analysis
    format_type: str
    duration_bucket: str
    
    # Creative elements
    one_line_summary: str
    narrative_structure: str
    hook_summary: str
    
    # Impact metrics
    impact_scores: ImpactScores
    
    # Emotional analysis
    emotional_timeline: EmotionalTimeline
    
    # Character analysis
    characters: List[Character]
    cast_diversity: CastDiversity
    
    # Claims and messaging
    claims: List[Dict[str, Any]]
    supers: List[Dict[str, Any]]
    
    # Audio analysis
    audio_structure: Dict[str, Any]
    
    # Visual analysis
    visual_patterns: Dict[str, Any]
    
    # Effectiveness
    effectiveness_drivers: Dict[str, Any]
    memorability: Dict[str, Any]
    competitive_context: Dict[str, Any]
    
    # Creative DNA
    creative_dna: Dict[str, Any]
    
    # Segments (AIDA breakdown)
    segments: List[Dict[str, Any]]
    
    # Raw chunks
    chunks: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Database Payload Types
# ---------------------------------------------------------------------------

class AdPayload(TypedDict, total=False):
    """Payload for inserting an ad into the database."""
    external_id: str
    s3_key: Optional[str]
    video_url: Optional[str]
    duration_seconds: Optional[float]
    transcript: Optional[str]
    analysis_json: Dict[str, Any]
    
    # Flat metadata fields
    brand_name: Optional[str]
    product_name: Optional[str]
    industry: Optional[str]
    sub_industry: Optional[str]
    format_type: Optional[str]
    duration_bucket: Optional[str]
    one_line_summary: Optional[str]
    narrative_structure: Optional[str]
    hook_summary: Optional[str]
    
    # JSONB columns
    impact_scores: Optional[Dict[str, Any]]
    emotional_metrics: Optional[Dict[str, Any]]
    effectiveness: Optional[Dict[str, Any]]
    cta_offer: Optional[Dict[str, Any]]
    brand_asset_timeline: Optional[Dict[str, Any]]
    audio_fingerprint: Optional[Dict[str, Any]]
    creative_dna: Optional[Dict[str, Any]]
    claims_compliance: Optional[Dict[str, Any]]
    
    # Metadata
    extraction_version: str
    processing_notes: Optional[Dict[str, Any]]
    hero_analysis: Optional[Dict[str, Any]]
    performance_metrics: Optional[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Vision/Storyboard Types
# ---------------------------------------------------------------------------

class StoryboardShot(TypedDict, total=False):
    """Single shot from storyboard analysis."""
    shot_number: int
    timestamp_s: float
    duration_s: float
    description: str
    camera_angle: str
    shot_type: str
    motion: str
    subjects: List[str]
    mood: str


class VisualObject(TypedDict, total=False):
    """Object detected in a frame."""
    category: str
    label: str
    confidence: float
    prominence: str
    position: str
    content: Optional[str]  # For text/OCR


class VisualObjectsResult(TypedDict, total=False):
    """Result from visual object detection."""
    detected_objects: List[Dict[str, Any]]
    aggregate_summary: Dict[str, Any]
    brand_visibility: Dict[str, Any]


# ---------------------------------------------------------------------------
# Physics Types
# ---------------------------------------------------------------------------

class VisualPhysics(TypedDict, total=False):
    """Visual physics metrics from scene analysis."""
    duration: float
    cut_count: int
    cuts_per_minute: float
    motion_energy_score: float
    brightness_variance: float
    dominant_colors: List[str]


class AudioPhysics(TypedDict, total=False):
    """Audio physics metrics."""
    tempo_bpm: float
    loudness_db: float


class SpatialData(TypedDict, total=False):
    """Spatial/bounding box data."""
    max_object_box: Optional[List[float]]


class PhysicsResult(TypedDict, total=False):
    """Complete physics extraction result."""
    physics_version: str
    visual_physics: VisualPhysics
    audio_physics: Optional[AudioPhysics]
    objects_detected: List[str]
    spatial_data: SpatialData
    keyframes_saved: List[str]
    keyframes_urls: List[str]


# ---------------------------------------------------------------------------
# Embedding Types
# ---------------------------------------------------------------------------

class EmbeddingItem(TypedDict, total=False):
    """Single embedding item for vector storage."""
    ad_id: str
    item_type: str
    text: str
    meta: Dict[str, Any]
    embedding: Optional[List[float]]


# ---------------------------------------------------------------------------
# Processing Result Types
# ---------------------------------------------------------------------------

class ProcessingSummary(TypedDict):
    """Summary of processing for an ad."""
    external_id: str
    ad_id: Optional[str]
    source: str
    elapsed_time: float
    completed_stages: List[str]
    skipped_stages: List[str]
    failed_stages: List[str]
    segments: int
    chunks: int
    claims: int
    storyboard_shots: int
    embeddings: int
    has_processing_notes: bool


# ---------------------------------------------------------------------------
# Toxicity Scoring Types
# ---------------------------------------------------------------------------

class ToxicityBreakdownItem(TypedDict):
    """Breakdown item for a toxicity category."""
    score: int
    flags: List[str]


class ToxicityBreakdown(TypedDict):
    """Breakdown of toxicity scores by category."""
    physiological: ToxicityBreakdownItem
    psychological: ToxicityBreakdownItem
    regulatory: ToxicityBreakdownItem


class ToxicityWeights(TypedDict):
    """Weights used in toxicity calculation."""
    physiological: float
    psychological: float
    regulatory: float


class ToxicityMetadata(TypedDict, total=False):
    """Metadata about the toxicity calculation."""
    weights: ToxicityWeights
    duration_seconds: float
    claims_count: int


class ToxicityReport(TypedDict):
    """
    Complete toxicity report for an advertisement.
    
    The report acts as a "Nutrition Label" for ad safety,
    explaining why an ad may be harmful to viewers.
    """
    toxic_score: int  # 0-100
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    breakdown: ToxicityBreakdown
    dark_patterns_detected: List[str]
    recommendation: str
    metadata: ToxicityMetadata


class DarkPatternMatch(TypedDict):
    """A detected dark pattern in ad content."""
    category: str  # e.g., "false_scarcity", "shaming", "forced_continuity"
    label: str  # Human-readable label
    matched_text: str  # The actual text that matched


class AIDarkPattern(TypedDict, total=False):
    """A dark pattern detected by AI analysis."""
    category: str  # e.g., "false_scarcity", "emotional_manipulation"
    text: str  # The text containing the pattern
    confidence: float  # 0.0-1.0 confidence score
    reasoning: str  # AI explanation of why this is manipulative


class AIToxicityAnalysis(TypedDict, total=False):
    """Complete AI toxicity analysis result."""
    dark_patterns: List[AIDarkPattern]
    manipulation_score: float  # 0.0-1.0 overall manipulation intensity
    subtle_patterns: List[str]  # Implied tactics that aren't explicit text
    fear_appeals: List[str]  # Fear-based manipulation detected
    unsubstantiated_claims: List[str]  # Claims that may be misleading
    overall_assessment: str  # Brief AI summary
    ai_model: str  # Model used for analysis
    analysis_confidence: float  # Overall confidence in the analysis

