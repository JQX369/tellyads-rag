# Updated Variables Summary
## Visual, Emotional, and Character Enhancements (Nov 2025)

This document lists all new and updated variables added to the extraction pipeline.

---

## 1. Enhanced Emotional Timeline Variables

### Updated: `emotional_timeline.readings[]`
**New fields per reading:**
- `secondary_emotion` (string | null) - Secondary emotion if present
- `trigger` (string | null) - What caused this emotion: `visual|audio|dialogue|music|pacing|reveal`

**Updated:**
- `t_s` - Now requires readings every **1-2 seconds** (was ~5 seconds)
- `dominant_emotion` - Expanded vocabulary: added `excitement`, `nostalgia`, `tension`, `relief`, `pride`, `empathy`

### New: `emotional_timeline.emotional_transitions[]`
Array of emotion shift moments:
- `from_emotion` (string) - Starting emotion
- `to_emotion` (string) - Ending emotion
- `transition_time_s` (float) - When transition occurs
- `transition_type` (string) - `gradual|sudden|contrast`
- `effectiveness` (float 0.0-1.0) - How well the transition works

### New: `emotional_timeline` summary fields
- `trough_moment_s` (float | null) - Lowest emotional point timestamp
- `trough_emotion` (string | null) - Emotion at trough
- `emotional_range` (float 0.0-1.0) - How much emotion varies (0=flat, 1=extreme variation)
- `final_viewer_state` (string) - Emotion viewer is left feeling at end

---

## 2. Enhanced Character Variables

### Updated: `characters[].ethnicity`
**Changed from:** `ethnicity: "<string or 'diverse_cast'>"`  
**Changed to:** Structured object:
```json
{
  "primary": "<white_european|white_american|black_african|black_caribbean|black_american|east_asian|south_asian|southeast_asian|middle_eastern|hispanic_latino|indigenous|pacific_islander|mixed|unclear>",
  "regional_detail": "<string | null>",  // e.g., "British", "Nigerian", "Korean", "Indian"
  "confidence": <float 0.0-1.0>
}
```

### New: `characters[].physical_traits`
```json
{
  "hair_color": "<blonde|brunette|black|red|grey|bald|other|unclear>",
  "distinctive_features": "<string | null>"
}
```

---

## 3. New: Cast Diversity Section

### New: `cast_diversity` (top-level section)
```json
{
  "total_characters": <int>,
  "gender_breakdown": {
    "male": <int>,
    "female": <int>,
    "non_binary": <int>,
    "unclear": <int>
  },
  "ethnicity_breakdown": {
    "<ethnicity_primary>": <int>  // e.g., {"white_european": 2, "east_asian": 1}
  },
  "age_range_present": ["<age_brackets>"],  // e.g., ["18_24", "25_34"]
  "diversity_score": <float 0.0-10.0>,  // Higher = more diverse
  "representation_notes": "<string | null>"  // Notable patterns, stereotypes, etc.
}
```

---

## 4. New: Visual Object Detection Variables

### New Database Column: `ads.visual_objects` (JSONB)
Stored in database, not in extraction JSON (populated separately via Gemini Vision):

```json
{
  "detected_objects": [
    {
      "frame_index": <int>,
      "timestamp_s": <float>,
      "objects": [
        {
          "category": "<product|logo|text|person|vehicle|food_beverage|technology|animal|location|other>",
          "label": "<string>",  // e.g., "iPhone 15 Pro", "Nike swoosh logo"
          "content": "<string>",  // For text category: exact OCR text
          "confidence": <float 0.0-1.0>,
          "prominence": "<hero|prominent|supporting|background>",
          "position": "<center|left|right|top|bottom|full_screen|corner>",
          "details": "<string | null>"
        }
      ]
    }
  ],
  "aggregate_summary": {
    "unique_products": ["<string>"],
    "unique_logos": ["<string>"],
    "all_text_ocr": ["<string>"],  // All text captured across frames
    "people_count_max": <int>,
    "people_demographics": "<string | null>",
    "primary_setting": "<string | null>",
    "scene_types": ["<string>"],
    "technology_shown": ["<string>"],
    "animals_present": ["<string>"],
    "distinctive_brand_assets": ["<string>"]
  },
  "brand_visibility": {
    "primary_brand": "<string | null>",
    "brand_first_appearance_frame": <int | null>,
    "brand_appearances_count": <int>,
    "logo_positions": ["<string>"],
    "brand_prominence_score": <float 0.0-1.0>
  }
}
```

---

## 5. New Embedding Item Types

New searchable embedding types created from visual object detection:

- `visual_objects` - Products and logos detected
- `visual_ocr` - All on-screen text captured
- `visual_scene` - Scene and setting descriptions
- `brand_visual` - Brand visibility summary
- `brand_assets` - Distinctive brand assets

These are automatically included in hybrid search queries.

---

## 6. Database Schema Updates

### New Column: `ads.visual_objects`
```sql
ALTER TABLE ads ADD COLUMN IF NOT EXISTS visual_objects jsonb DEFAULT '{}'::jsonb;
```

### Updated Function: `match_embedding_items_hybrid()`
Now includes new embedding types in default search:
- `visual_objects`
- `visual_ocr`
- `visual_scene`
- `brand_visual`
- `brand_assets`

---

## Summary of Changes

| Section | Change Type | Details |
|---------|-------------|---------|
| `emotional_timeline.readings[]` | **Enhanced** | Added `secondary_emotion`, `trigger`; granularity 1-2s |
| `emotional_timeline` | **New fields** | `emotional_transitions[]`, `trough_moment_s`, `trough_emotion`, `emotional_range`, `final_viewer_state` |
| `characters[].ethnicity` | **Restructured** | Changed from string to object with `primary`, `regional_detail`, `confidence` |
| `characters[]` | **New field** | `physical_traits` object |
| `cast_diversity` | **New section** | Complete diversity breakdown with scores |
| `ads.visual_objects` | **New DB column** | Object detection results (separate from extraction JSON) |
| Embedding types | **New types** | 5 new visual-related embedding types |

---

## Migration Required

Run this SQL in Supabase Dashboard > SQL Editor:

```sql
ALTER TABLE ads ADD COLUMN IF NOT EXISTS visual_objects jsonb DEFAULT '{}'::jsonb;
```

---

## Backward Compatibility

- All new fields have default values in `DEFAULT_SECTIONS`
- Existing ads will have `null` or empty defaults for new fields
- Old `ethnicity` strings will be automatically converted to structured format during normalization
- Visual object detection is optional (only runs if vision is enabled)



