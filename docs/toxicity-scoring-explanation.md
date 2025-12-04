# Toxicity Score Calculation - Complete Guide

## Overview

The **Toxicity Score** is a 0-100 metric that evaluates video advertisements for potential harm across three pillars:
1. **Physiological Harm** (40% weight) - Sensory assault metrics
2. **Psychological Manipulation** (40% weight) - Dark patterns and manipulative language
3. ** Regulatory Risk** (20% weight) - Compliance violations

The final score is a **weighted linear combination** of these three component scores.

---

## Formula

```
Toxicity Score = (Physiological × 0.40) + (Psychological × 0.40) + (Regulatory × 0.20)
```

**Score Range:** 0-100  
**Risk Levels:**
- **LOW**: 0-30
- **MEDIUM**: 31-60
- **HIGH**: 61-100

---

## Pillar 1: Physiological Harm (40% Weight)

Measures **sensory assault** - how much the ad overwhelms the viewer's senses.

### Data Keys Required:
```python
{
    "visual_physics": {
        "cuts_per_minute": float,      # Required: Cuts per minute
        "motion_energy_score": float,   # Optional: 0-1 motion score
        "optical_flow_score": float,    # Optional: Alias for motion_energy_score
        "brightness_variance": float,   # Required: Variance in brightness (0-1)
        "photosensitivity_fail": bool   # Optional: Auto-set if high cuts + high variance
    },
    "audio_physics": {
        "loudness_lu": float,          # Required: Loudness in LUFS (or loudness_db)
        "loudness_db": float,          # Optional: Alias for loudness_lu
    }
}
```

### Scoring Rules:

| Metric | Threshold | Points | Flag |
|--------|-----------|--------|------|
| **Cuts/Minute** | > 80 cuts/min | +20 | "Rapid Cuts (X/min exceeds 80)" |
| **Loudness** | > -10 LUFS | +30 | "Extreme Loudness (X LUFS exceeds -10)" |
| **Photosensitivity** | `photosensitivity_fail == True` | +50 | "Seizure Risk (Photosensitivity test failed)" |
| **Brightness Variance** | > 0.8 | +25 | "Flash Warning (Brightness variance X)" |
| **Motion Energy** | > 0.9 | +10 | "Hyper-Stimulation (Motion score X)" |

**Maximum Physiological Score:** 100 points (capped)

**Example:**
```python
visual_physics = {
    "cuts_per_minute": 95,        # +20 points
    "brightness_variance": 0.85,   # +25 points
    "motion_energy_score": 0.95    # +10 points
}
audio_physics = {
    "loudness_lu": -8              # +30 points
}
# Total: 20 + 25 + 10 + 30 = 85 points
```

---

## Pillar 2: Psychological Manipulation (40% Weight)

Measures **dark patterns** and manipulative language using **hybrid detection**:
1. **Regex patterns** (fast, rule-based)
2. **AI detection** via Gemini 2.5 Flash (contextual, subtle)

### Data Keys Required:
```python
{
    "transcript": str,              # Required: Full ad transcript text
    "claims": [                     # Required: List of claims from LLM analysis
        {
            "text": str,
            "claim_type": str,
            "is_comparative": bool,
            "likely_needs_substantiation": bool
        }
    ],
    "duration_seconds": float       # Required: Ad duration in seconds
}
```

### Dark Pattern Categories (Regex):

#### 1. False Scarcity (+10 points per category)
**Patterns:** "only X left", "selling out", "limited time", "act now", "hurry", "expires soon"

**Example Matches:**
- "Only 2 left!"
- "Limited time offer"
- "Act now before it's too late"

#### 2. Shaming (+10 points per category)
**Patterns:** "don't be stupid", "if you care about", "you deserve", "aren't you tired of"

**Example Matches:**
- "Don't be stupid - buy now"
- "If you really care about your family..."
- "Aren't you tired of looking broke?"

#### 3. Forced Continuity (+10 points per category)
**Patterns:** "free trial", "auto-ship", "cancel anytime", "no commitment"

**Example Matches:**
- "Free trial*" (asterisk indicates fine print)
- "Auto-ship every month"
- "Cancel anytime*"

**Maximum from Dark Patterns:** 30 points (capped at 3 categories)

### AI-Enhanced Detection (Gemini 2.5 Flash):

The AI detects **subtle patterns** that regex misses:
- **Fear appeals** (exploiting anxiety)
- **Emotional manipulation** (guilt trips)
- **Unsubstantiated claims** (too good to be true)
- **Implied urgency** (not explicitly stated)

**AI Scoring:**
- **Manipulation Score** (0-1): Adds up to +15 points if > 0.5
- **Subtle Patterns**: +5 points each (capped at 15)
- **High Confidence Patterns**: Included in category count

**Example AI Output:**
```json
{
    "dark_patterns": [
        {
            "category": "fear_appeal",
            "text": "Before it's too late",
            "confidence": 0.85,
            "reasoning": "Creates anxiety about missing out"
        }
    ],
    "manipulation_score": 0.75,
    "subtle_patterns": ["Implied urgency without evidence"],
    "fear_appeals": ["Fear of missing out", "Health consequences"]
}
```

### Claim Density (Gish Gallop):

**Formula:**
```
claim_density = (num_claims / duration_minutes) * 60
```

**Threshold:** > 6 claims/minute  
**Points:** +20 if exceeded

**Example:**
- 30-second ad with 4 claims = 8 claims/min → **+20 points**

### Psychological Score Calculation:

```python
score = 0

# Step 1: Count unique dark pattern categories (regex + AI)
categories = set(regex_categories) | set(ai_categories)
score += min(len(categories) * 10, 30)  # Cap at 30

# Step 2: Add AI subtle patterns
score += min(len(ai_subtle_patterns) * 5, 15)  # Cap at 15

# Step 3: Add AI manipulation score
if ai_manipulation_score > 0.5:
    score += int(ai_manipulation_score * 15)  # Up to 15 points

# Step 4: Check claim density
if claim_density > 6:
    score += 20

# Cap at 100
score = min(score, 100)
```

**Maximum Psychological Score:** 100 points (capped)

---

## Pillar 3: Regulatory Risk (20% Weight)

Measures **compliance violations** and missing safety disclaimers.

### Data Keys Required:
```python
{
    "garm_risk_level": str,              # Required: "low", "medium", "high"
    "required_disclaimers": [str],       # Required: List of required disclaimers
    "present_disclaimers": [str],        # Required: List of disclaimers found in ad
    "transcript": str                     # Required: For keyword detection
}
```

### Scoring Rules:

| Metric | Condition | Points | Flag |
|--------|-----------|--------|------|
| **GARM Risk** | `garm_risk_level == "high"` | +50 | "GARM High Risk Category" |
| **GARM Risk** | `garm_risk_level == "medium"` | +25 | "GARM Medium Risk Category" |
| **Missing Disclaimers** | Any required disclaimer missing | +50 | "Missing Disclaimers: X, Y, Z" |
| **Regulated Category** | Pharma/Alcohol/Gambling/Financial without disclaimers | +15 | "Category Disclaimer May Be Required" |

**Regulated Category Keywords:**
- **Pharma**: "medication", "prescription", "drug" → needs "side effects", "consult doctor"
- **Alcohol**: "beer", "wine", "vodka" → needs "drink responsibly", "21+"
- **Gambling**: "bet", "casino", "poker" → needs "gamble responsibly", "18+"
- **Financial**: "invest", "stock", "loan" → needs "past performance", "risk of loss"

**Maximum Regulatory Score:** 100 points (capped)

**Example:**
```python
{
    "garm_risk_level": "high",           # +50 points
    "required_disclaimers": ["Side effects may occur"],
    "present_disclaimers": []             # +50 points (missing)
}
# Total: 50 + 50 = 100 points
```

---

## Final Score Calculation

### Step-by-Step:

1. **Calculate Component Scores** (each 0-100):
   ```python
   physio_score = score_physiological()      # 0-100
   psycho_score = score_psychological()      # 0-100
   regulatory_score = score_regulatory()     # 0-100
   ```

2. **Apply Weights**:
   ```python
   weighted_physio = physio_score * 0.40
   weighted_psycho = psycho_score * 0.40
   weighted_regulatory = regulatory_score * 0.20
   ```

3. **Sum and Round**:
   ```python
   total_score = round(weighted_physio + weighted_psycho + weighted_regulatory)
   total_score = min(max(total_score, 0), 100)  # Clamp to 0-100
   ```

### Example Calculation:

```python
# Component scores
physio = 85      # High cuts, loud audio, strobe effects
psycho = 40      # 2 dark patterns, moderate claim density
regulatory = 50  # Medium GARM risk

# Weighted scores
weighted_physio = 85 * 0.40 = 34.0
weighted_psycho = 40 * 0.40 = 16.0
weighted_regulatory = 50 * 0.20 = 10.0

# Final score
total_score = round(34.0 + 16.0 + 10.0) = 60

# Risk level
risk_level = "MEDIUM"  # (31-60 range)
```

---

## Output Structure

The toxicity report includes:

```python
{
    "toxic_score": 60,                    # Final weighted score (0-100)
    "risk_level": "MEDIUM",                # LOW, MEDIUM, or HIGH
    "breakdown": {
        "physiological": {
            "score": 85,                   # Raw score (0-100)
            "flags": [                     # List of issues found
                "Rapid Cuts (95/min exceeds 80)",
                "Extreme Loudness (-8 LUFS exceeds -10)",
                "Flash Warning (Brightness variance 0.85)"
            ]
        },
        "psychological": {
            "score": 40,
            "flags": [
                "False Scarcity Detected (Regex)",
                "Shaming Detected (AI)",
                "Claim Overload (8.0 claims/min exceeds 6)"
            ],
            "ai_analysis": {               # If AI enabled
                "model": "gemini-2.5-flash",
                "manipulation_score": 0.75,
                "subtle_patterns": ["Implied urgency"],
                "fear_appeals": ["Fear of missing out"]
            }
        },
        "regulatory": {
            "score": 50,
            "flags": [
                "GARM Medium Risk Category"
            ]
        }
    },
    "dark_patterns_detected": [            # All matched text
        "only 2 left",
        "don't be stupid",
        "free trial*"
    ],
    "recommendation": "MODERATE RISK. Address flagged concerns...",
    "metadata": {
        "weights": {
            "physiological": 0.40,
            "psychological": 0.40,
            "regulatory": 0.20
        },
        "duration_seconds": 30.0,
        "claims_count": 4,
        "ai_enabled": true
    },
    "ai_analysis": {                       # Full AI analysis if enabled
        "model": "gemini-2.5-flash",
        "manipulation_score": 0.75,
        "overall_assessment": "This ad uses moderate manipulation...",
        "subtle_patterns": [...],
        "fear_appeals": [...],
        "unsubstantiated_claims": [...]
    }
}
```

---

## Data Flow

### How Data Gets to ToxicityScorer:

1. **Pipeline Stage: ToxicityStage** (Stage 9)
   - Runs after PhysicsStage and LLMAnalysisStage
   - Builds `analysis_data` dict from multiple sources

2. **Data Sources:**
   ```python
   analysis_data = {
       # From PhysicsStage (physics_result)
       "visual_physics": ctx.physics_result["visual_physics"],
       "audio_physics": ctx.physics_result["audio_physics"],
       
       # From LLMAnalysisStage (analysis_result)
       "claims": ctx.analysis_result["claims"],
       "garm_risk_level": ctx.analysis_result["compliance_assessment"]["overall_risk"],
       "required_disclaimers": [...],
       
       # From TranscriptionStage
       "transcript": ctx.transcript["text"],
       
       # From MediaProbeStage
       "duration_seconds": ctx.probe_result["duration"]
   }
   ```

3. **ToxicityScorer Initialization:**
   ```python
   scorer = ToxicityScorer(analysis_data, use_ai=True)
   report = scorer.calculate_toxicity()
   ```

4. **Database Storage:**
   ```python
   db_backend.update_toxicity_report(ad_id, report)
   ```

---

## Key Constants (Tunable)

All thresholds and weights can be adjusted in `scoring_engine.py`:

```python
# Weights (must sum to 1.0)
WEIGHT_PHYSIOLOGICAL = 0.40
WEIGHT_PSYCHOLOGICAL = 0.40
WEIGHT_REGULATORY = 0.20

# Thresholds
CUTS_PER_MINUTE_THRESHOLD = 80
LOUDNESS_LU_THRESHOLD = -10
CLAIM_DENSITY_THRESHOLD = 6

# Point Values
POINTS_HIGH_CUTS = 20
POINTS_LOUD_AUDIO = 30
POINTS_PHOTOSENSITIVITY = 50
DARK_PATTERN_POINTS = 10
POINTS_GARM_HIGH_RISK = 50
```

---

## Summary

The toxicity score is a **weighted linear equation** that combines:
- **40%** sensory assault metrics (cuts, loudness, strobe effects)
- **40%** manipulative language detection (regex + AI)
- **20%** compliance violations (GARM, missing disclaimers)

The score ranges from **0 (safe)** to **100 (critical risk)**, with clear flags explaining why an ad received its score.

