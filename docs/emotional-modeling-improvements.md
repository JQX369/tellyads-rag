# Emotional Modeling Improvements

## Overview

The emotional timeline extraction has been significantly enhanced to provide **more granular, contextual, and actionable** emotional analysis. This enables better understanding of how ads manipulate viewer emotions throughout their duration.

---

## Key Improvements

### 1. **Granularity: 5x More Frequent Readings**

**Before:**
- Emotional readings every **~5 seconds**
- A 30-second ad would have ~6 readings
- Missed rapid emotional shifts

**After:**
- Emotional readings every **1-2 seconds**
- A 30-second ad now has **15-30 readings**
- Captures subtle emotional transitions

**Impact:** Can now detect micro-emotions, rapid mood shifts, and emotional beats that were previously averaged out.

---

### 2. **Expanded Emotion Vocabulary**

**Before (9 emotions):**
- `joy`, `surprise`, `trust`, `anticipation`, `sadness`, `fear`, `anger`, `disgust`, `neutral`

**After (15 emotions):**
- Added: `excitement`, `nostalgia`, `tension`, `relief`, `pride`, `empathy`
- More nuanced emotional states for advertising context

**Impact:** Better categorization of ad-specific emotions (nostalgia for brand heritage, tension for urgency, pride for achievement).

---

### 3. **New Per-Reading Variables**

Each emotional reading now includes:

#### `secondary_emotion` (NEW)
- **Type:** string | null
- **Purpose:** Captures layered emotions (e.g., "joyful but anxious")
- **Example:** Dominant: `joy`, Secondary: `anticipation` (happy but waiting for reveal)

#### `trigger` (NEW)
- **Type:** string
- **Purpose:** Identifies what caused the emotion
- **Values:** `visual|audio|dialogue|music|pacing|reveal`
- **Example:** `trigger: "music"` - emotion driven by soundtrack change

**Impact:** Understands **why** emotions occur, not just **what** they are. Critical for creative optimization.

---

### 4. **Emotional Transition Tracking** (NEW SECTION)

**New Array:** `emotional_transitions[]`

Tracks significant emotion shifts throughout the ad:

```json
{
  "from_emotion": "tension",
  "to_emotion": "relief",
  "transition_time_s": 12.5,
  "transition_type": "sudden",  // or "gradual" or "contrast"
  "effectiveness": 0.85  // How well does this transition work?
}
```

**Use Cases:**
- Identify emotional pivot points
- Measure transition effectiveness
- Optimize pacing for emotional impact
- Compare transition styles across ads

**Impact:** Can now analyze emotional **arcs** and **pivots**, not just static states.

---

### 5. **Enhanced Summary Metrics**

#### New Fields:

**`trough_moment_s`** (float | null)
- Timestamp of the lowest emotional point
- Complements `peak_moment_s` for full emotional range

**`trough_emotion`** (string | null)
- Emotion at the lowest point
- Useful for problem-solution ads (trough = problem, peak = solution)

**`emotional_range`** (float 0.0-1.0)
- Measures emotional variation throughout ad
- 0.0 = flat/static emotions
- 1.0 = extreme emotional swings
- **Use:** Identify emotionally flat ads vs. dynamic ones

**`final_viewer_state`** (string)
- Emotion the viewer is left feeling at the end
- Critical for brand recall and action intent
- **Use:** Measure if ad ends on desired emotion (e.g., "pride" for luxury brands)

---

## Before vs. After Comparison

### Example: 30-Second Ad

**Before (Old System):**
```json
{
  "emotional_timeline": {
    "readings": [
      {"t_s": 0.0, "dominant_emotion": "neutral", "intensity": 0.3, "valence": 0.0, "arousal": 0.3},
      {"t_s": 5.0, "dominant_emotion": "joy", "intensity": 0.6, "valence": 0.5, "arousal": 0.5},
      {"t_s": 10.0, "dominant_emotion": "joy", "intensity": 0.7, "valence": 0.6, "arousal": 0.6},
      {"t_s": 15.0, "dominant_emotion": "anticipation", "intensity": 0.8, "valence": 0.7, "arousal": 0.8},
      {"t_s": 20.0, "dominant_emotion": "joy", "intensity": 0.9, "valence": 0.8, "arousal": 0.9},
      {"t_s": 25.0, "dominant_emotion": "joy", "intensity": 0.8, "valence": 0.7, "arousal": 0.7}
    ],
    "arc_shape": "rising",
    "peak_moment_s": 20.0,
    "peak_emotion": "joy",
    "average_intensity": 0.68,
    "positive_ratio": 0.83
  }
}
```
**6 readings total** - Misses rapid shifts, no context on triggers

**After (New System):**
```json
{
  "emotional_timeline": {
    "readings": [
      {"t_s": 0.0, "dominant_emotion": "neutral", "secondary_emotion": null, "intensity": 0.3, "valence": 0.0, "arousal": 0.3, "trigger": "visual"},
      {"t_s": 1.5, "dominant_emotion": "curiosity", "secondary_emotion": "anticipation", "intensity": 0.5, "valence": 0.3, "arousal": 0.5, "trigger": "dialogue"},
      {"t_s": 3.0, "dominant_emotion": "joy", "secondary_emotion": null, "intensity": 0.6, "valence": 0.5, "arousal": 0.6, "trigger": "music"},
      {"t_s": 4.5, "dominant_emotion": "joy", "secondary_emotion": "excitement", "intensity": 0.7, "valence": 0.6, "arousal": 0.7, "trigger": "visual"},
      {"t_s": 6.0, "dominant_emotion": "excitement", "secondary_emotion": null, "intensity": 0.8, "valence": 0.7, "arousal": 0.8, "trigger": "reveal"},
      // ... 20+ more readings at 1-2s intervals
      {"t_s": 28.5, "dominant_emotion": "pride", "secondary_emotion": "joy", "intensity": 0.9, "valence": 0.9, "arousal": 0.7, "trigger": "visual"}
    ],
    "emotional_transitions": [
      {"from_emotion": "neutral", "to_emotion": "curiosity", "transition_time_s": 1.5, "transition_type": "gradual", "effectiveness": 0.7},
      {"from_emotion": "curiosity", "to_emotion": "joy", "transition_time_s": 3.0, "transition_type": "sudden", "effectiveness": 0.9},
      {"from_emotion": "joy", "to_emotion": "excitement", "transition_time_s": 6.0, "transition_type": "sudden", "effectiveness": 0.95},
      {"from_emotion": "excitement", "to_emotion": "pride", "transition_time_s": 25.0, "transition_type": "gradual", "effectiveness": 0.85}
    ],
    "arc_shape": "rising",
    "peak_moment_s": 20.0,
    "peak_emotion": "excitement",
    "trough_moment_s": 0.0,
    "trough_emotion": "neutral",
    "average_intensity": 0.72,
    "positive_ratio": 0.92,
    "emotional_range": 0.85,  // High variation = dynamic ad
    "final_viewer_state": "pride"  // Ends on aspirational emotion
  }
}
```
**~20 readings** with triggers, transitions, and context

---

## Variable Reference

### Per-Reading Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `t_s` | float | Timestamp (every 1-2s) | `3.5` |
| `dominant_emotion` | string | Primary emotion (15 options) | `"joy"` |
| `secondary_emotion` | string\|null | **NEW** - Secondary emotion | `"anticipation"` |
| `intensity` | float | Emotion strength (0.0-1.0) | `0.75` |
| `valence` | float | Positive/negative (-1.0 to 1.0) | `0.6` |
| `arousal` | float | Calm/excited (0.0-1.0) | `0.8` |
| `trigger` | string | **NEW** - What caused emotion | `"music"` |

### Transition Variables

| Variable | Type | Description |
|----------|------|-------------|
| `from_emotion` | string | Starting emotion |
| `to_emotion` | string | Ending emotion |
| `transition_time_s` | float | When transition occurs |
| `transition_type` | string | `gradual\|sudden\|contrast` |
| `effectiveness` | float | How well transition works (0.0-1.0) |

### Summary Variables

| Variable | Type | Description |
|----------|------|-------------|
| `arc_shape` | string | Overall emotional arc pattern |
| `peak_moment_s` | float | Highest emotional point |
| `peak_emotion` | string | Emotion at peak |
| `trough_moment_s` | float\|null | **NEW** - Lowest emotional point |
| `trough_emotion` | string\|null | **NEW** - Emotion at trough |
| `average_intensity` | float | Mean intensity across ad |
| `positive_ratio` | float | Proportion of positive moments |
| `emotional_range` | float | **NEW** - Variation measure (0=flat, 1=extreme) |
| `final_viewer_state` | string | **NEW** - Ending emotion |

---

## Use Cases & Applications

### 1. **Creative Optimization**
- **Question:** "Which emotional transitions are most effective?"
- **Answer:** Analyze `emotional_transitions[].effectiveness` scores

### 2. **Pacing Analysis**
- **Question:** "Is this ad emotionally flat or dynamic?"
- **Answer:** Check `emotional_range` (low = flat, high = dynamic)

### 3. **Brand Alignment**
- **Question:** "Does the ad end on the right emotion?"
- **Answer:** Compare `final_viewer_state` to brand values

### 4. **Trigger Analysis**
- **Question:** "What drives emotions in this ad?"
- **Answer:** Count `trigger` values (e.g., "music" appears 8 times)

### 5. **Problem-Solution Structure**
- **Question:** "Does this ad follow problem-solution arc?"
- **Answer:** Check `trough_emotion` (problem) → `peak_emotion` (solution)

### 6. **Competitive Benchmarking**
- **Question:** "How does our emotional arc compare to competitors?"
- **Answer:** Compare `arc_shape`, `emotional_range`, `transition_type` distributions

---

## Technical Implementation

### Prompt Changes
- Updated `EXTRACTION_V2_USER_TEMPLATE` to request 1-2s granularity
- Added explicit instruction: "provide reading every 1-2 seconds for granular tracking"
- Expanded emotion vocabulary in prompt
- Added transition tracking instructions

### Normalization Changes
- Updated `_ensure_valid_emotional_timeline()` in `analysis.py`
- Added defaults for new fields:
  - `secondary_emotion: null`
  - `trigger: null`
  - `emotional_transitions: []`
  - `trough_moment_s: null`
  - `trough_emotion: null`
  - `emotional_range: 0.5`
  - `final_viewer_state: "neutral"`

### Database Storage
- Stored in existing `emotional_metrics` JSONB column
- No schema migration needed (backward compatible)
- Old ads will have `null` defaults for new fields

---

## Summary

**Improvements:**
1. ✅ **5x more granular** (1-2s vs 5s readings)
2. ✅ **6 new emotions** (15 total vs 9)
3. ✅ **2 new per-reading fields** (`secondary_emotion`, `trigger`)
4. ✅ **Transition tracking** (new array with effectiveness scores)
5. ✅ **4 new summary metrics** (trough, range, final state)

**Result:** More actionable emotional intelligence for creative optimization and competitive analysis.




