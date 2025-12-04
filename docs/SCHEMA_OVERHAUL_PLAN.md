# Schema Overhaul Implementation Plan

## Vision
Make the "everything schema" **reliable, grounded, versioned, queryable, and cost-scalable** — without pruning for the sake of pruning.

---

## Priority 1: Evidence + Timestamps for High-Stakes Outputs

### Principle
Every high-stakes field must have **grounded evidence** (transcript excerpt, frame reference, or OCR source) and a **timestamp** (when in the ad it occurs). No evidence = warning flag.

### Fields Requiring Evidence

| Field Category | Fields | Evidence Type |
|---------------|--------|---------------|
| **Claims** | `claims[].text`, `claims[].claim_type`, `claims[].likely_needs_substantiation` | Transcript excerpt + timestamp |
| **Supers** | `supers[].text`, `supers[].super_type` | Frame reference + OCR confidence + timestamp |
| **Brand Moments** | `brand_first_mention`, `brand_logo_appearances` | Frame reference OR transcript excerpt + timestamp |
| **CTAs** | `cta_offer.call_to_action`, `cta_offer.urgency_elements` | Transcript excerpt + timestamp |
| **Compliance Flags** | `regulator_sensitive`, `required_disclaimers`, `garm_categories` | Source (transcript/visual) + timestamp |
| **Toxicity Flags** | `dark_patterns_detected[]` | Pattern match source + timestamp range |

### Schema Changes

```sql
-- Evidence structure for all high-stakes fields
CREATE TYPE evidence_source AS (
    source_type text,           -- 'transcript' | 'visual' | 'ocr' | 'audio' | 'derived'
    excerpt text,               -- Verbatim text or frame description
    timestamp_start_s float,    -- When it appears
    timestamp_end_s float,      -- When it ends (null for instant)
    frame_index int,            -- Frame reference (for visual evidence)
    confidence float,           -- 0.0-1.0 confidence score
    model_attribution text      -- Which model/stage produced this
);

-- Add evidence columns to child tables
ALTER TABLE ad_claims ADD COLUMN evidence jsonb DEFAULT '[]'::jsonb;
ALTER TABLE ad_claims ADD COLUMN extraction_confidence float;
ALTER TABLE ad_claims ADD COLUMN has_evidence boolean GENERATED ALWAYS AS (
    jsonb_array_length(evidence) > 0
) STORED;

ALTER TABLE ad_supers ADD COLUMN evidence jsonb DEFAULT '[]'::jsonb;
ALTER TABLE ad_supers ADD COLUMN ocr_confidence float;
ALTER TABLE ad_supers ADD COLUMN frame_index int;

-- Add extraction_warnings to ads table
ALTER TABLE ads ADD COLUMN extraction_warnings jsonb DEFAULT '[]'::jsonb;
```

### Prompt Changes (extraction_v2.py)

```python
# Add to claims section
CLAIMS_WITH_EVIDENCE = """
## 8. CLAIMS (with evidence)
Extract ALL claims with grounding evidence.

Return array of:
{
  "text": "<exact claim text>",
  "claim_type": "benefit|comparison|price|testimonial|performance|safety|health|environmental|social_proof",
  "is_comparative": true/false,
  "likely_needs_substantiation": true/false,
  "evidence": {
    "source_type": "transcript|visual|ocr",
    "excerpt": "<verbatim quote from transcript or OCR>",
    "timestamp_start_s": 12.5,
    "timestamp_end_s": 14.0,
    "confidence": 0.95
  }
}

CRITICAL: Every claim MUST have evidence.excerpt matching the actual transcript or OCR text.
If you cannot ground a claim in evidence, mark confidence < 0.5 and add to extraction_warnings.
"""
```

### Validation Logic (analysis.py)

```python
def validate_evidence_grounding(analysis: Dict, transcript_text: str) -> List[str]:
    """Validate that claims/supers have grounded evidence."""
    warnings = []

    for i, claim in enumerate(analysis.get("claims", [])):
        evidence = claim.get("evidence", {})
        excerpt = evidence.get("excerpt", "")

        if not excerpt:
            warnings.append(f"claim[{i}]: Missing evidence excerpt")
        elif evidence.get("source_type") == "transcript":
            # Fuzzy match excerpt against transcript
            if not fuzzy_contains(transcript_text, excerpt, threshold=0.8):
                warnings.append(f"claim[{i}]: Evidence excerpt not found in transcript")

        if evidence.get("confidence", 1.0) < 0.5:
            warnings.append(f"claim[{i}]: Low confidence ({evidence.get('confidence')})")

    return warnings
```

---

## Priority 2: Progressive Disclosure (Pass A / Pass B)

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     PASS A: Always-On (Fast)                     │
│  - Core metadata (brand, product, category, duration)            │
│  - Compliance flags (regulator_sensitive, has_disclaimers)       │
│  - High-ROI scores (hook_power, brand_integration)               │
│  - Claims + Supers (with evidence)                               │
│  - CTA extraction                                                │
│  - Toxicity scoring (regex-only, no AI)                          │
│  ~1,500 tokens output | ~$0.02/ad | ~3-5 seconds                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PASS B: Deep Analysis (On-Demand)              │
│  - Full emotional timeline (readings every 1-2s)                 │
│  - Character analysis + demographics                             │
│  - Memorability analysis                                         │
│  - Creative DNA + brand asset timeline                           │
│  - Full effectiveness scoring                                    │
│  - AI-enhanced toxicity (Gemini dark pattern detection)          │
│  - Hero analysis (for flagged ads)                               │
│  ~4,000 tokens output | ~$0.08/ad | ~10-15 seconds               │
└─────────────────────────────────────────────────────────────────┘
```

### Pass A Schema (Always Run)

```python
PASS_A_SECTIONS = [
    "core_metadata",           # brand, product, category, country, language
    "campaign_strategy",       # objective, funnel_stage, format_type
    "creative_flags_minimal",  # has_voiceover, has_celeb, regulator_sensitive (10 flags)
    "impact_scores_core",      # overall_impact, hook_power, brand_integration (3 scores)
    "claims",                  # All claims with evidence
    "supers",                  # All supers with evidence
    "cta_offer",              # Call to action extraction
    "compliance_quick",        # GARM risk, required disclaimers
]

PASS_A_TOKEN_BUDGET = 1500  # Target output tokens
```

### Pass B Schema (On-Demand)

```python
PASS_B_SECTIONS = [
    "impact_scores_full",     # All 8 impact scores with rationales
    "emotional_timeline",      # Full timeline with readings
    "characters",              # Character analysis (gated: demographics)
    "memorability",            # Memorable elements analysis
    "audio_profile",           # Music, VO, sound design
    "brand_presence",          # Brand visibility metrics
    "effectiveness",           # Full effectiveness assessment
    "creative_dna",            # Creative DNA + brand assets
    "compliance_full",         # Detailed compliance assessment
]

PASS_B_TOKEN_BUDGET = 4000
```

### Trigger Logic

```python
class PassBTrigger:
    """Determine when to run Pass B analysis."""

    TRIGGERS = {
        "hero_flagged": lambda ctx: ctx.hero_required,
        "high_views": lambda ctx: (ctx.metadata_entry and
                                   ctx.metadata_entry.views and
                                   ctx.metadata_entry.views > 100000),
        "compliance_risk": lambda ctx: (ctx.analysis_result and
                                        ctx.analysis_result.get("compliance_assessment", {})
                                        .get("overall_risk") == "high"),
        "toxicity_concern": lambda ctx: (ctx.toxicity_report and
                                         ctx.toxicity_report.get("toxic_score", 0) > 50),
        "explicit_request": lambda ctx: ctx.force_deep_analysis,
    }

    @classmethod
    def should_run_pass_b(cls, ctx: ProcessingContext) -> Tuple[bool, List[str]]:
        triggered = []
        for name, check in cls.TRIGGERS.items():
            if check(ctx):
                triggered.append(name)
        return len(triggered) > 0, triggered
```

### Database Schema

```sql
-- Track extraction passes
ALTER TABLE ads ADD COLUMN extraction_pass text DEFAULT 'A';  -- 'A' | 'B' | 'A+B'
ALTER TABLE ads ADD COLUMN pass_b_triggered_by text[];        -- Trigger reasons
ALTER TABLE ads ADD COLUMN pass_b_completed_at timestamptz;

-- Index for finding ads needing Pass B
CREATE INDEX idx_ads_pass_a_only ON ads (id)
WHERE extraction_pass = 'A' AND pass_b_triggered_by IS NOT NULL;
```

### Pipeline Changes

```python
# Modified LLMAnalysisStage

class LLMAnalysisStage(Stage):
    def execute(self, ctx: ProcessingContext, config: PipelineConfig) -> ProcessingContext:
        # Always run Pass A
        pass_a_result = self._run_pass_a(ctx)
        ctx.analysis_result = pass_a_result
        ctx.extraction_pass = "A"

        # Check Pass B triggers
        should_run_b, triggers = PassBTrigger.should_run_pass_b(ctx)

        if should_run_b:
            pass_b_result = self._run_pass_b(ctx)
            ctx.analysis_result = self._merge_passes(pass_a_result, pass_b_result)
            ctx.extraction_pass = "A+B"
            ctx.pass_b_triggers = triggers

        return ctx
```

---

## Priority 3: Toxicity Scoring End-to-End

### Current State (VERIFIED WORKING)
- ToxicityStage runs as Stage 9 (after Physics)
- ToxicityScorer computes: physiological, psychological, regulatory scores
- `update_toxicity_report()` persists to `ads.toxicity_report` JSONB
- Indexes exist for `toxic_score` and `risk_level`

### Missing Pieces

1. **Backend API exposure** - No toxicity filtering in search endpoints
2. **Subscores not individually indexed** - Can't filter by "high physiological harm"
3. **Version tracking** - No scorer version stored
4. **AI analysis not toggleable** - Always on/off globally

### Schema Additions

```sql
-- Add individual subscore columns for efficient filtering
ALTER TABLE ads ADD COLUMN toxicity_score_overall int
    GENERATED ALWAYS AS ((toxicity_report->>'toxic_score')::int) STORED;

ALTER TABLE ads ADD COLUMN toxicity_risk_level text
    GENERATED ALWAYS AS (toxicity_report->>'risk_level') STORED;

ALTER TABLE ads ADD COLUMN toxicity_physiological int
    GENERATED ALWAYS AS ((toxicity_report->'breakdown'->'physiological'->>'score')::int) STORED;

ALTER TABLE ads ADD COLUMN toxicity_psychological int
    GENERATED ALWAYS AS ((toxicity_report->'breakdown'->'psychological'->>'score')::int) STORED;

ALTER TABLE ads ADD COLUMN toxicity_regulatory int
    GENERATED ALWAYS AS ((toxicity_report->'breakdown'->'regulatory'->>'score')::int) STORED;

-- Version tracking
ALTER TABLE ads ADD COLUMN toxicity_scorer_version text;

-- Indexes for filtering
CREATE INDEX idx_ads_toxicity_overall ON ads (toxicity_score_overall);
CREATE INDEX idx_ads_toxicity_risk ON ads (toxicity_risk_level);
CREATE INDEX idx_ads_high_toxicity ON ads (id) WHERE toxicity_score_overall > 60;
```

### Backend API Changes (main.py)

```python
# Add toxicity filters to search endpoint
@app.get("/api/search")
async def search_ads(
    query: str,
    limit: int = 10,
    # Existing filters...
    # New toxicity filters:
    max_toxicity: Optional[int] = None,
    risk_level: Optional[str] = None,  # LOW, MEDIUM, HIGH
    exclude_dark_patterns: bool = False,
):
    filters = {}
    if max_toxicity is not None:
        filters["toxicity_score_overall"] = ("<=", max_toxicity)
    if risk_level:
        filters["toxicity_risk_level"] = ("=", risk_level)
    # ... apply filters to search
```

### Scorer Versioning

```python
# scoring_engine.py

SCORER_VERSION = "1.2.0"

class ToxicityScorer:
    def calculate_toxicity(self) -> Dict[str, Any]:
        result = {
            "toxic_score": total_score,
            "risk_level": self._get_risk_level(total_score),
            "breakdown": breakdown,
            # ... existing fields
            "scorer_version": SCORER_VERSION,
            "scored_at": datetime.utcnow().isoformat(),
            "ai_enhanced": self._should_use_ai(),
        }
        return result
```

---

## Priority 4: Canonical Field Registry

### Purpose
Single source of truth for ALL extracted fields, eliminating prompt/schema drift.

### Registry Structure

```python
# tvads_rag/registry.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any

class FieldCategory(Enum):
    CORE = "core"                    # Always extracted
    COMPLIANCE = "compliance"        # Regulatory fields
    CREATIVE = "creative"            # Creative analysis
    EMOTIONAL = "emotional"          # Emotional metrics
    EFFECTIVENESS = "effectiveness"  # Impact/effectiveness
    SENSITIVE = "sensitive"          # Gated fields

class StorageLocation(Enum):
    FLAT = "flat"           # ads.field_name column
    JSONB = "jsonb"         # ads.column_name->>'field'
    CHILD_TABLE = "child"   # Separate table

class UsageType(Enum):
    RETRIEVAL = "retrieval"   # Used in search/filter
    GENERATION = "generation" # Used in output generation
    UI = "ui"                 # Displayed in frontend
    INTERNAL = "internal"     # Internal processing only

@dataclass
class FieldDefinition:
    """Canonical definition of an extracted field."""

    # Identity
    name: str                           # Canonical field name
    path: str                           # JSON path (e.g., "impact_scores.hook_power.score")
    version_introduced: str             # e.g., "2.0"

    # Type
    field_type: str                     # string, int, float, bool, array, object
    enum_values: Optional[List[str]]    # For enum types
    nullable: bool = True

    # Evidence requirements
    requires_evidence: bool = False
    evidence_types: List[str] = None    # ["transcript", "visual", "ocr"]

    # Confidence
    confidence_field: Optional[str] = None  # Path to confidence score
    min_confidence: float = 0.0             # Minimum required

    # Storage
    storage: StorageLocation = StorageLocation.JSONB
    storage_column: str = "analysis_json"   # Target column
    indexed: bool = False

    # Usage
    usage: List[UsageType] = None
    pass_assignment: str = "A"              # "A", "B", or "A+B"

    # Sensitivity
    category: FieldCategory = FieldCategory.CORE
    gated: bool = False                     # Requires feature flag
    gate_flag: Optional[str] = None         # Flag name if gated

    # Documentation
    description: str = ""
    prompt_section: str = ""                # Section in extraction prompt

    def __post_init__(self):
        if self.usage is None:
            self.usage = []
        if self.evidence_types is None:
            self.evidence_types = []


# The Registry
FIELD_REGISTRY: Dict[str, FieldDefinition] = {}

def register_field(field: FieldDefinition) -> None:
    FIELD_REGISTRY[field.name] = field

def get_field(name: str) -> Optional[FieldDefinition]:
    return FIELD_REGISTRY.get(name)

def get_pass_a_fields() -> List[FieldDefinition]:
    return [f for f in FIELD_REGISTRY.values() if f.pass_assignment in ("A", "A+B")]

def get_pass_b_fields() -> List[FieldDefinition]:
    return [f for f in FIELD_REGISTRY.values() if f.pass_assignment in ("B", "A+B")]

def get_evidence_required_fields() -> List[FieldDefinition]:
    return [f for f in FIELD_REGISTRY.values() if f.requires_evidence]

def get_gated_fields() -> List[FieldDefinition]:
    return [f for f in FIELD_REGISTRY.values() if f.gated]
```

### Registry Definitions

```python
# tvads_rag/registry_definitions.py

from .registry import (
    register_field, FieldDefinition, FieldCategory,
    StorageLocation, UsageType
)

# =============================================================================
# CORE METADATA (Pass A)
# =============================================================================

register_field(FieldDefinition(
    name="brand_name",
    path="core_metadata.brand_name",
    version_introduced="1.0",
    field_type="string",
    nullable=False,
    storage=StorageLocation.FLAT,
    storage_column="brand_name",
    indexed=True,
    usage=[UsageType.RETRIEVAL, UsageType.UI],
    pass_assignment="A",
    category=FieldCategory.CORE,
    description="Primary brand name featured in the ad",
    prompt_section="core_metadata",
))

register_field(FieldDefinition(
    name="product_category",
    path="core_metadata.product_category",
    version_introduced="1.0",
    field_type="string",
    enum_values=[
        "food_beverage", "retail", "automotive", "technology",
        "financial_services", "healthcare", "entertainment",
        "travel_hospitality", "telecommunications", "fmcg",
        "education", "real_estate", "government", "nonprofit", "other"
    ],
    storage=StorageLocation.FLAT,
    storage_column="product_category",
    indexed=True,
    usage=[UsageType.RETRIEVAL, UsageType.UI],
    pass_assignment="A",
    category=FieldCategory.CORE,
))

# =============================================================================
# CLAIMS (Pass A, Evidence Required)
# =============================================================================

register_field(FieldDefinition(
    name="claims",
    path="claims",
    version_introduced="1.0",
    field_type="array",
    storage=StorageLocation.CHILD_TABLE,
    storage_column="ad_claims",
    requires_evidence=True,
    evidence_types=["transcript", "visual", "ocr"],
    usage=[UsageType.RETRIEVAL, UsageType.GENERATION],
    pass_assignment="A",
    category=FieldCategory.COMPLIANCE,
    description="Product/service claims extracted from ad",
))

register_field(FieldDefinition(
    name="claims.text",
    path="claims[].text",
    version_introduced="1.0",
    field_type="string",
    nullable=False,
    requires_evidence=True,
    confidence_field="claims[].evidence.confidence",
    min_confidence=0.5,
    usage=[UsageType.RETRIEVAL, UsageType.GENERATION],
    pass_assignment="A",
    category=FieldCategory.COMPLIANCE,
))

# =============================================================================
# IMPACT SCORES (Pass A: Core, Pass B: Full)
# =============================================================================

register_field(FieldDefinition(
    name="impact_scores.hook_power",
    path="impact_scores.hook_power.score",
    version_introduced="2.0",
    field_type="float",
    storage=StorageLocation.JSONB,
    storage_column="impact_scores",
    indexed=True,
    usage=[UsageType.RETRIEVAL, UsageType.UI],
    pass_assignment="A",  # Core score
    category=FieldCategory.EFFECTIVENESS,
    description="How effectively the ad grabs attention in first 3 seconds (0-10)",
))

register_field(FieldDefinition(
    name="impact_scores.emotional_resonance",
    path="impact_scores.emotional_resonance.score",
    version_introduced="2.0",
    field_type="float",
    storage=StorageLocation.JSONB,
    storage_column="impact_scores",
    usage=[UsageType.GENERATION],
    pass_assignment="B",  # Deep analysis
    category=FieldCategory.EMOTIONAL,
))

# =============================================================================
# SENSITIVE/GATED FIELDS
# =============================================================================

register_field(FieldDefinition(
    name="characters.ethnicity",
    path="characters[].ethnicity",
    version_introduced="2.0",
    field_type="object",
    gated=True,
    gate_flag="ENABLE_DEMOGRAPHIC_ANALYSIS",
    confidence_field="characters[].ethnicity.confidence",
    min_confidence=0.7,  # High bar for sensitive fields
    usage=[UsageType.INTERNAL],  # Never expose directly
    pass_assignment="B",
    category=FieldCategory.SENSITIVE,
    description="Character ethnicity (gated, internal only, high confidence required)",
))

register_field(FieldDefinition(
    name="cast_diversity",
    path="cast_diversity",
    version_introduced="2.0",
    field_type="object",
    gated=True,
    gate_flag="ENABLE_DEMOGRAPHIC_ANALYSIS",
    usage=[UsageType.INTERNAL],
    pass_assignment="B",
    category=FieldCategory.SENSITIVE,
))
```

### Registry Validation

```python
# tvads_rag/registry_validator.py

def validate_extraction_against_registry(
    analysis: Dict[str, Any],
    transcript: str
) -> Dict[str, Any]:
    """
    Validate extraction output against the field registry.

    Returns:
        {
            "valid": bool,
            "warnings": [...],
            "errors": [...],
            "field_coverage": {"present": 45, "required": 50, "percentage": 0.90}
        }
    """
    warnings = []
    errors = []
    fields_present = 0
    fields_required = 0

    for field in FIELD_REGISTRY.values():
        if field.pass_assignment == "B" and not deep_analysis_enabled:
            continue

        fields_required += 1
        value = get_nested_value(analysis, field.path)

        if value is not None:
            fields_present += 1

            # Type validation
            if not validate_type(value, field.field_type, field.enum_values):
                errors.append(f"{field.name}: Invalid type (expected {field.field_type})")

            # Evidence validation
            if field.requires_evidence:
                evidence = get_nested_value(analysis, f"{field.path.rsplit('.', 1)[0]}.evidence")
                if not evidence:
                    warnings.append(f"{field.name}: Missing required evidence")
                elif field.min_confidence > 0:
                    conf = evidence.get("confidence", 0)
                    if conf < field.min_confidence:
                        warnings.append(
                            f"{field.name}: Low confidence ({conf} < {field.min_confidence})"
                        )

        elif not field.nullable:
            errors.append(f"{field.name}: Required field is null")

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "field_coverage": {
            "present": fields_present,
            "required": fields_required,
            "percentage": fields_present / fields_required if fields_required > 0 else 0,
        }
    }
```

---

## Priority 5: Unified Event Timeline

### Concept
A single, chronological timeline of ALL significant events in the ad.

```python
@dataclass
class TimelineEvent:
    """A single event on the ad timeline."""

    timestamp_start_s: float
    timestamp_end_s: Optional[float]

    event_type: str  # shot, claim, super, cta, brand_moment, emotion_peak, compliance_flag

    # Content
    content: str                    # Human-readable description
    raw_data: Dict[str, Any]        # Full structured data

    # Evidence
    source: str                     # transcript, visual, audio, derived
    confidence: float

    # Linkages
    linked_ids: Dict[str, str]      # {"claim_id": "uuid", "shot_id": "uuid"}

    # Importance
    importance: str                 # critical, high, medium, low
    brand_relevance: float          # 0.0-1.0, how brand-connected
```

### Timeline Event Types

| Type | Source | Example |
|------|--------|---------|
| `shot` | VisionStage | "Wide establishing shot of city skyline" |
| `scene` | VisionStage | "Scene change: Kitchen to Living Room" |
| `claim` | LLMAnalysis | "50% more effective than competitors" |
| `super` | VisionStage/OCR | "Limited time offer. T&Cs apply" |
| `cta` | LLMAnalysis | "Call now: 1-800-XXX" |
| `brand_moment` | LLMAnalysis+Vision | "Brand logo prominently displayed" |
| `emotion_peak` | LLMAnalysis | "Peak emotion: Joy at 18.5s" |
| `compliance_flag` | LLMAnalysis | "Unsubstantiated health claim" |
| `dark_pattern` | ToxicityScorer | "False scarcity: 'Only 3 left'" |
| `audio_moment` | ASR+Audio | "Music crescendo / Jingle / Silence" |

### Schema

```sql
-- New timeline table
CREATE TABLE ad_timeline_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid REFERENCES ads(id) ON DELETE CASCADE,

    -- Timing
    timestamp_start_s float NOT NULL,
    timestamp_end_s float,

    -- Event data
    event_type text NOT NULL,
    content text NOT NULL,
    raw_data jsonb DEFAULT '{}'::jsonb,

    -- Evidence
    source text NOT NULL,
    confidence float DEFAULT 1.0,

    -- Linkages
    linked_claim_id uuid REFERENCES ad_claims(id),
    linked_super_id uuid REFERENCES ad_supers(id),
    linked_shot_id uuid REFERENCES ad_storyboards(id),

    -- Importance
    importance text DEFAULT 'medium',
    brand_relevance float DEFAULT 0.0,

    -- Metadata
    created_at timestamptz DEFAULT now(),
    extraction_version text,

    CONSTRAINT valid_event_type CHECK (
        event_type IN ('shot', 'scene', 'claim', 'super', 'cta',
                       'brand_moment', 'emotion_peak', 'compliance_flag',
                       'dark_pattern', 'audio_moment')
    )
);

-- Index for timeline queries
CREATE INDEX idx_timeline_ad_time ON ad_timeline_events (ad_id, timestamp_start_s);
CREATE INDEX idx_timeline_type ON ad_timeline_events (ad_id, event_type);
CREATE INDEX idx_timeline_importance ON ad_timeline_events (ad_id, importance)
    WHERE importance IN ('critical', 'high');
```

### Timeline Builder

```python
# tvads_rag/timeline.py

class TimelineBuilder:
    """Build unified timeline from multiple pipeline stages."""

    def __init__(self, ctx: ProcessingContext):
        self.ctx = ctx
        self.events: List[TimelineEvent] = []

    def build(self) -> List[TimelineEvent]:
        """Build complete timeline from all sources."""

        # From storyboard (shots/scenes)
        self._add_storyboard_events()

        # From claims
        self._add_claim_events()

        # From supers
        self._add_super_events()

        # From emotional timeline
        self._add_emotion_events()

        # From CTA
        self._add_cta_events()

        # From brand presence
        self._add_brand_events()

        # From toxicity (dark patterns)
        self._add_toxicity_events()

        # Sort by timestamp
        self.events.sort(key=lambda e: e.timestamp_start_s)

        return self.events

    def _add_claim_events(self):
        analysis = self.ctx.analysis_result or {}
        for i, claim in enumerate(analysis.get("claims", [])):
            evidence = claim.get("evidence", {})
            self.events.append(TimelineEvent(
                timestamp_start_s=evidence.get("timestamp_start_s", 0),
                timestamp_end_s=evidence.get("timestamp_end_s"),
                event_type="claim",
                content=claim.get("text", ""),
                raw_data=claim,
                source=evidence.get("source_type", "transcript"),
                confidence=evidence.get("confidence", 0.8),
                linked_ids={"claim_id": self.ctx.claim_ids[i] if i < len(self.ctx.claim_ids) else None},
                importance="high" if claim.get("likely_needs_substantiation") else "medium",
                brand_relevance=0.5,
            ))

    # ... similar for other event types
```

### Timeline Embedding

```python
# Add to EmbeddingsStage

def _prepare_timeline_items(self, ctx: ProcessingContext) -> List[Dict]:
    """Prepare timeline events for embedding."""
    items = []

    # Build timeline
    timeline = TimelineBuilder(ctx).build()

    # Group events by type and create embeddings
    for event_type in ["claim", "super", "brand_moment", "cta"]:
        events = [e for e in timeline if e.event_type == event_type]
        if events:
            # Create summary embedding for this event type
            text = f"{event_type.replace('_', ' ').title()} events: " + \
                   " | ".join(e.content for e in events[:5])
            items.append({
                "ad_id": ctx.ad_id,
                "item_type": f"timeline_{event_type}",
                "text": text,
                "meta": {
                    "event_count": len(events),
                    "timestamps": [e.timestamp_start_s for e in events[:5]],
                }
            })

    return items
```

---

## Priority 6: Sensitive Field Gating

### Principle
Sensitive or low-confidence fields are:
1. Never treated as ground truth
2. Gated behind feature flags
3. Never exposed in public APIs without explicit opt-in
4. Always include confidence scores

### Gated Field Categories

| Category | Fields | Default State | Gate Flag |
|----------|--------|---------------|-----------|
| Demographics | `characters[].ethnicity`, `characters[].age_range`, `cast_diversity` | OFF | `ENABLE_DEMOGRAPHIC_ANALYSIS` |
| Subjective | `uses_nostalgia`, `uses_cultural_moment`, `emotional_resonance` | ON (but flagged) | `TRUST_SUBJECTIVE_FIELDS` |
| Low Confidence | Any field with confidence < 0.5 | Included with warning | `INCLUDE_LOW_CONFIDENCE` |

### Implementation

```python
# tvads_rag/config.py

@dataclass
class FeatureFlags:
    """Feature flags for gating sensitive functionality."""

    ENABLE_DEMOGRAPHIC_ANALYSIS: bool = False
    TRUST_SUBJECTIVE_FIELDS: bool = True
    INCLUDE_LOW_CONFIDENCE: bool = True
    EXPOSE_DEMOGRAPHICS_API: bool = False  # Even if enabled internally

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        return cls(
            ENABLE_DEMOGRAPHIC_ANALYSIS=os.getenv("ENABLE_DEMOGRAPHIC_ANALYSIS", "false").lower() == "true",
            TRUST_SUBJECTIVE_FIELDS=os.getenv("TRUST_SUBJECTIVE_FIELDS", "true").lower() == "true",
            INCLUDE_LOW_CONFIDENCE=os.getenv("INCLUDE_LOW_CONFIDENCE", "true").lower() == "true",
            EXPOSE_DEMOGRAPHICS_API=os.getenv("EXPOSE_DEMOGRAPHICS_API", "false").lower() == "true",
        )
```

### Extraction Gating

```python
# In extraction prompt builder

def build_extraction_prompt(flags: FeatureFlags) -> str:
    sections = []

    # Always include core sections
    sections.extend(PASS_A_SECTIONS)

    # Conditionally include gated sections
    if flags.ENABLE_DEMOGRAPHIC_ANALYSIS:
        sections.append(CHARACTERS_WITH_DEMOGRAPHICS)
    else:
        sections.append(CHARACTERS_NO_DEMOGRAPHICS)

    return compose_prompt(sections)

CHARACTERS_NO_DEMOGRAPHICS = """
## CHARACTERS (Privacy-Safe Mode)
Extract visible characters WITHOUT demographic analysis.

Return array of:
{
  "label": "Primary character (e.g., 'Narrator', 'Customer 1')",
  "role": "protagonist|supporting|background",
  "speaking": true/false,
  "on_screen_time_s": 15.0
}

DO NOT extract: age, gender, ethnicity, or other demographic attributes.
"""
```

### API Response Filtering

```python
# backend/main.py

def filter_sensitive_fields(ad_data: Dict, flags: FeatureFlags) -> Dict:
    """Remove sensitive fields from API responses."""

    if not flags.EXPOSE_DEMOGRAPHICS_API:
        # Remove demographic data from characters
        if "analysis_json" in ad_data and "characters" in ad_data["analysis_json"]:
            for char in ad_data["analysis_json"]["characters"]:
                char.pop("ethnicity", None)
                char.pop("age_range", None)
                char.pop("gender", None)

        # Remove cast_diversity entirely
        if "analysis_json" in ad_data:
            ad_data["analysis_json"].pop("cast_diversity", None)

    return ad_data
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
1. Create field registry (`registry.py`, `registry_definitions.py`)
2. Add evidence schema to claims/supers
3. Add extraction_warnings column
4. Wire toxicity to backend API

### Phase 2: Progressive Disclosure (Week 3-4)
1. Split extraction prompt into Pass A / Pass B
2. Implement PassBTrigger logic
3. Add extraction_pass tracking
4. Create backfill job for existing ads needing Pass B

### Phase 3: Timeline (Week 5-6)
1. Create `ad_timeline_events` table
2. Implement TimelineBuilder
3. Add timeline embedding items
4. Add timeline API endpoint

### Phase 4: Polish (Week 7-8)
1. Registry validation in CI
2. Field coverage dashboard
3. Evidence grounding tests
4. Sensitivity gating audit

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Evidence coverage (claims) | >95% | % claims with non-empty evidence |
| Extraction warnings | <5% | % ads with warnings |
| Pass A latency | <5s | P95 latency |
| Pass B trigger rate | 10-20% | % ads getting deep analysis |
| Timeline event coverage | >90% | % ads with complete timeline |
| Registry compliance | 100% | CI check on prompt changes |

---

## Appendix: Migration Scripts

### A. Add Evidence to Existing Claims

```python
async def backfill_claim_evidence():
    """Backfill evidence for existing claims using transcript matching."""
    ads = await db.fetch_all("SELECT id, raw_transcript FROM ads WHERE raw_transcript IS NOT NULL")

    for ad in ads:
        claims = await db.fetch_all(
            "SELECT id, text FROM ad_claims WHERE ad_id = %s AND evidence IS NULL",
            (ad["id"],)
        )

        for claim in claims:
            # Find claim text in transcript
            transcript = ad["raw_transcript"].get("text", "")
            match = fuzzy_find(claim["text"], transcript)

            if match:
                evidence = {
                    "source_type": "transcript",
                    "excerpt": match.text,
                    "timestamp_start_s": match.start_time,
                    "confidence": match.score,
                }
                await db.execute(
                    "UPDATE ad_claims SET evidence = %s WHERE id = %s",
                    (Json(evidence), claim["id"])
                )
```

### B. Rebuild Timeline for Existing Ads

```python
async def rebuild_all_timelines():
    """Rebuild timeline events for all existing ads."""
    ads = await db.fetch_all("SELECT id FROM ads")

    for ad in ads:
        ctx = await load_processing_context(ad["id"])
        timeline = TimelineBuilder(ctx).build()

        # Clear existing
        await db.execute("DELETE FROM ad_timeline_events WHERE ad_id = %s", (ad["id"],))

        # Insert new
        for event in timeline:
            await db.execute(
                """INSERT INTO ad_timeline_events
                   (ad_id, timestamp_start_s, timestamp_end_s, event_type, content,
                    raw_data, source, confidence, importance, brand_relevance)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (ad["id"], event.timestamp_start_s, event.timestamp_end_s,
                 event.event_type, event.content, Json(event.raw_data),
                 event.source, event.confidence, event.importance, event.brand_relevance)
            )
```
