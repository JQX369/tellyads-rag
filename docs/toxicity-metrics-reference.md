# Toxicity Scoring Metrics Reference

Complete list of all metrics extracted and analyzed for the Toxic Ad Detector.

---

## Overview

The toxicity score (0-100) is calculated from three pillars:
- **Physiological Harm** (40% weight): Sensory assault metrics
- **Psychological Manipulation** (40% weight): Dark patterns and claim density
- **Regulatory Risk** (20% weight): GARM compliance and disclaimers

---

## 1. Physiological Metrics (40% Weight)

### Source: `physics_data.visual_physics` + `physics_data.audio_physics`

| Metric | Field Path | Threshold | Points | Description |
|--------|------------|-----------|--------|-------------|
| **Cuts Per Minute** | `visual_physics.cuts_per_minute` | > 80 | +20 | Dopamine overload threshold |
| **Loudness (LUFS)** | `audio_physics.loudness_lu` OR `audio_physics.loudness_db` | > -10 | +30 | Loudness war violation |
| **Photosensitivity Risk** | `visual_physics.photosensitivity_fail` | `true` | +50 | Seizure risk (auto high-risk) |
| **Brightness Variance** | `visual_physics.brightness_variance` | > 0.8 | +25 | Flash/strobe warning |
| **Motion Energy** | `visual_physics.motion_energy_score` | > 0.9 | +10 | Hyper-stimulation |

**Total Possible**: 100 points (capped)

---

## 2. Psychological Metrics (40% Weight)

### Source: `transcript` + `claims` + AI Analysis

#### 2.1 Dark Pattern Detection (Regex + AI)

**Regex Patterns** (3 categories):
- **False Scarcity**: "only X left", "selling out", "limited time", "act now", "hurry"
- **Shaming**: "don't be stupid", "if you care about", "you deserve", "aren't you tired of"
- **Forced Continuity**: "free trial", "auto-ship", "cancel anytime", "no commitment*"

**AI-Enhanced Detection** (Gemini 2.5 Flash):
- **Fear Appeals**: Exploiting anxiety, FOMO, health scares
- **Emotional Manipulation**: Guilt trips, sympathy exploitation
- **Unsubstantiated Claims**: "Guaranteed results", "Proven to work"
- **Subtle Patterns**: Implied manipulation not explicit in text

| Detection Method | Points Per Category | Max Points |
|------------------|---------------------|------------|
| Regex Categories | +10 per unique category | 30 (capped) |
| AI Subtle Patterns | +5 per pattern | 15 (capped) |
| AI Manipulation Score | Score × 15 | Up to 15 |

#### 2.2 Claim Density (Gish Gallop)

| Metric | Calculation | Threshold | Points |
|--------|-------------|-----------|--------|
| **Claims Per Minute** | `len(claims) / (duration_seconds / 60)` | > 6 | +20 |

**Total Possible**: 100 points (capped)

---

## 3. Regulatory Metrics (20% Weight)

### Source: `garm_risk_level` + `required_disclaimers` + `present_disclaimers` + `transcript`

| Metric | Source | Value | Points |
|--------|--------|-------|--------|
| **GARM High Risk** | `garm_risk_level` | `"High"` | +50 |
| **GARM Medium Risk** | `garm_risk_level` | `"Medium"` | +25 |
| **Missing Disclaimers** | `required_disclaimers` vs `present_disclaimers` | Any missing | +50 |
| **Regulated Category** | Transcript keywords | Pharma/Alcohol/Gambling/Financial without disclaimers | +15 |

**Regulated Categories Detected**:
- **Pharma**: Requires "side effects", "consult your doctor", "FDA"
- **Alcohol**: Requires "drink responsibly", "21+", "legal drinking age"
- **Gambling**: Requires "gamble responsibly", "18+", "21+"
- **Financial**: Requires "past performance", "risk of loss", "FDIC"

**Total Possible**: 100 points (capped)

---

## 4. Final Score Calculation

```
Weighted Score = 
    (Physiological Score × 0.40) +
    (Psychological Score × 0.40) +
    (Regulatory Score × 0.20)

Final Score = round(Weighted Score) clamped to [0, 100]
```

**Risk Levels**:
- **LOW**: 0-30
- **MEDIUM**: 31-60
- **HIGH**: 61-100

---

## 5. Output Structure

### Complete Toxicity Report

```json
{
  "toxic_score": 70,
  "risk_level": "HIGH",
  "breakdown": {
    "physiological": {
      "score": 100,
      "flags": [
        "Rapid Cuts (95/min exceeds 80)",
        "Extreme Loudness (-6.0 LUFS exceeds -10)",
        "Seizure Risk (Photosensitivity test failed)",
        "Hyper-Stimulation (Motion score 0.95)"
      ]
    },
    "psychological": {
      "score": 54,
      "flags": [
        "Fear Appeal Detected (AI)",
        "False Scarcity Detected (Regex+AI)",
        "Shaming Detected (Regex+AI)",
        "Unsubstantiated Claims Detected (AI)",
        "Subtle Manipulation (AI: ...)",
        "High Manipulation Score (AI: 98%)"
      ],
      "ai_analysis": {
        "model": "gemini-2.5-flash",
        "manipulation_score": 0.98,
        "subtle_patterns": ["..."],
        "fear_appeals": ["..."],
        "unsubstantiated_claims": ["..."],
        "overall_assessment": "..."
      }
    },
    "regulatory": {
      "score": 50,
      "flags": [
        "GARM High Risk Category",
        "Missing Disclaimers: Side effects, Consult doctor"
      ]
    }
  },
  "dark_patterns_detected": [
    "only 2 left",
    "act now",
    "don't be stupid",
    "free trial",
    "..."
  ],
  "recommendation": "DO NOT RUN. This ad poses serious risks...",
  "metadata": {
    "weights": {
      "physiological": 0.40,
      "psychological": 0.40,
      "regulatory": 0.20
    },
    "duration_seconds": 30,
    "claims_count": 12,
    "ai_enabled": true
  },
  "ai_analysis": {
    "model": "gemini-2.5-flash",
    "manipulation_score": 0.98,
    "overall_assessment": "...",
    "subtle_patterns": ["..."],
    "fear_appeals": ["..."],
    "unsubstantiated_claims": ["..."]
  }
}
```

---

## 6. Data Sources

### Required Input Fields

| Field | Source Module | Description |
|-------|---------------|-------------|
| `visual_physics` | `physics_engine.py` | Scene detection, cuts, motion, brightness |
| `audio_physics` | `physics_engine.py` | BPM, loudness (LUFS/dB) |
| `transcript` | `asr.py` (Whisper) | Full transcript text |
| `claims` | `analysis.py` (LLM v2.0) | Extracted claims array |
| `duration_seconds` | `media.py` (ffprobe) | Video duration |
| `garm_risk_level` | External/Manual | GARM category risk level |
| `required_disclaimers` | External/Manual | List of required disclaimers |
| `present_disclaimers` | External/Manual | List of present disclaimers |

---

## 7. Schema Storage

### Database Column: `toxicity_report` (JSONB)

**Migration SQL**: See `schema_toxicity_migration.sql`

**Indexes Created**:
- `idx_ads_toxicity_score` - Query by numeric score
- `idx_ads_risk_level` - Query by risk level (LOW/MEDIUM/HIGH)
- `idx_ads_toxicity_breakdown` - GIN index for breakdown flags

**Query Examples**:
```sql
-- Find high-risk ads
SELECT external_id, toxicity_report->>'toxic_score' as score
FROM ads
WHERE (toxicity_report->>'risk_level') = 'HIGH';

-- Find ads with seizure risk
SELECT external_id
FROM ads
WHERE toxicity_report->'breakdown'->'physiological'->'flags' @> '["Seizure Risk"]';

-- Find ads with AI-detected manipulation
SELECT external_id, toxicity_report->'ai_analysis'->>'manipulation_score' as ai_score
FROM ads
WHERE toxicity_report->'ai_analysis' IS NOT NULL;
```

---

## 8. Configuration

### Environment Variables

```bash
# Enable AI-enhanced detection (default: true if GOOGLE_API_KEY set)
TOXICITY_AI_ENABLED=true

# Override Gemini model (default: gemini-2.5-flash)
TOXICITY_MODEL=gemini-2.5-flash

# Required for AI
GOOGLE_API_KEY=your-key-here
```

### Tunable Constants (in `scoring_engine.py`)

```python
# Weights (must sum to 1.0)
WEIGHT_PHYSIOLOGICAL = 0.40
WEIGHT_PSYCHOLOGICAL = 0.40
WEIGHT_REGULATORY = 0.20

# Thresholds
CUTS_PER_MINUTE_THRESHOLD = 80
LOUDNESS_LU_THRESHOLD = -10
CLAIM_DENSITY_THRESHOLD = 6

# Point values
POINTS_HIGH_CUTS = 20
POINTS_LOUD_AUDIO = 30
POINTS_PHOTOSENSITIVITY = 50
DARK_PATTERN_POINTS = 10
DARK_PATTERN_CAP = 30
POINTS_HIGH_CLAIM_DENSITY = 20
POINTS_GARM_HIGH_RISK = 50
POINTS_MISSING_DISCLAIMER = 50

# AI settings
AI_CONFIDENCE_THRESHOLD = 0.6
AI_MANIPULATION_SCORE_WEIGHT = 15
```

---

## 9. Integration Points

### Pipeline Integration

The toxicity scorer can be called:
1. **During ingestion** (recommended): Calculate and store in `toxicity_report`
2. **On-demand**: Recalculate from stored data
3. **Batch processing**: Score existing ads without re-ingestion

### Usage in Code

```python
from tvads_rag.scoring_engine import ToxicityScorer, score_ad_toxicity

# Build analysis_data from existing ad
analysis_data = {
    "visual_physics": ad["physics_data"]["visual_physics"],
    "audio_physics": ad["physics_data"]["audio_physics"],
    "transcript": ad["raw_transcript"]["text"],
    "claims": [c["text"] for c in ad["claims"]],
    "duration_seconds": ad["duration_seconds"],
    "garm_risk_level": "High",  # From external source
    "required_disclaimers": ["Side effects", "Consult doctor"],
    "present_disclaimers": [],
}

# Score
report = score_ad_toxicity(analysis_data)

# Store in database
db_backend.update_toxicity_report(ad_id, report)
```

---

## 10. Summary of All Metrics

### Physiological (5 metrics)
1. Cuts per minute
2. Loudness (LUFS/dB)
3. Photosensitivity failure
4. Brightness variance
5. Motion energy score

### Psychological (Dark Patterns + Claims)
**Regex Patterns** (3 categories):
6. False scarcity
7. Shaming
8. Forced continuity

**AI Patterns** (4+ categories):
9. Fear appeals
10. Emotional manipulation
11. Unsubstantiated claims
12. Subtle manipulation

**Claim Metrics**:
13. Claim density (claims/min)

### Regulatory (4 checks)
14. GARM risk level
15. Missing disclaimers
16. Regulated category detection (Pharma/Alcohol/Gambling/Financial)
17. Disclaimer presence validation

**Total: 17+ distinct metrics** contributing to the final toxicity score.



