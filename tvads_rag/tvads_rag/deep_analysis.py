"""
High-fidelity hero ad analysis powered by Gemini 3 Pro.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Sequence

from .config import get_vision_config, resolve_vision_model, VisionConfig
from . import visual_analysis

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - optional
    genai = None  # type: ignore
    types = None  # type: ignore

logger = logging.getLogger(__name__)

# Sample more densely for hero ads (roughly every ~0.75s)
HERO_FRAME_SAMPLE_SECONDS = 0.75
MAX_FRAMES = 32
MAX_TRANSCRIPT_CHARS = 6000
SCORE_MIN = 0.0
SCORE_MAX = 100.0

HERO_ANALYSIS_PROMPT = """
You are a senior creative strategist and advertising analyst specialising in award-winning TV campaigns. You will receive:
1) Key frames from the ad with timestamps
2) The full transcript with timestamps

Your task: Provide deep creative analysis of what makes this ad effective (or not).

## Analysis Focus Areas
- **WHY does this creative work?** - Identify the strategic choices that drive effectiveness
- **Emotional journey** - How does the ad manipulate viewer emotions over time?
- **Craft excellence** - Note exceptional cinematography, editing, sound design
- **Brand integration** - How seamlessly is the brand woven into the story?
- **Memorability factors** - What makes this ad stick in memory?

## Output Format
Return STRICT JSON (no markdown fences, no prose outside JSON):
{{
  "cinematography": {{
    "shot_breakdown": [
      {{
        "time_window": "0-3s",
        "camera_moves": ["handheld close-up", "slow push"],
        "composition": "Describe framing (e.g., 'rule of thirds, product in foreground, shallow DOF')",
        "pacing": "cut_rhythm (e.g., 'rapid 0.5s cuts', 'lingering 3s holds')",
        "transitions": ["cut", "dissolve", "match_cut", "whip_pan", "morph"]
      }}
    ],
    "lighting_style": "Describe lighting (e.g., 'warm practicals', 'high-key studio', 'golden hour natural')",
    "colour_palette": ["Primary colour 1", "Accent colour 2", "Brand colour if present"],
    "notable_transitions": ["Describe standout transitions with timestamps"],
    "production_quality": "premium | broadcast | mid_tier | low_budget"
  }},
  "emotional_arc": [
    {{
      "time_window": "0-5s",
      "emotion": "Primary emotion evoked (tension, joy, curiosity, desire, relief, etc.)",
      "tension_curve": "building | peak | release | flat",
      "emotional_hook": "What specifically triggers this emotion"
    }}
  ],
  "creative_tactics": {{
    "hook_type": "How attention is grabbed (celebrity, question, shock, humour, visual_spectacle, music_hook)",
    "pattern_breaks": ["Unexpected moments that reset attention"],
    "humour_or_drama_devices": ["Specific comedic or dramatic techniques used"],
    "brand_reveal_style": "How/when brand is revealed (early_upfront, woven_throughout, late_payoff, end_super)",
    "cta_framing": "How call-to-action is presented",
    "persuasion_techniques": ["social_proof", "scarcity", "authority", "aspirational", "fear_appeal"]
  }},
  "visual_patterns": {{
    "recurring_motifs": ["Visual elements that repeat for brand memory"],
    "logo_usage": "How logo appears (corner_bug, hero_moment, subtle_integration, end_card_only)",
    "packshots": ["Product visibility moments with timestamps"],
    "hero_product_framing": "How product is showcased (glamour_macro, in_use, lifestyle_context)",
    "distinctive_visual_style": "What makes this visually unique"
  }},
  "audio_profile": {{
    "music_style": "Genre and character (e.g., 'orchestral_cinematic', 'lo-fi_chill', 'custom_jingle')",
    "music_mood": "Emotional quality of music",
    "music_brand_fit": "How well music supports brand personality",
    "vocal_profile": "VO description (gender, age, accent, energy, tone)",
    "notable_sound_design": ["SFX, audio logos, or sound moments that stand out"]
  }},
  "effectiveness_drivers": {{
    "primary_strength": "Single most effective element of this ad",
    "memorable_moments": ["Specific moments likely to be remembered"],
    "brand_linkage": "How well creative connects to brand (strong, moderate, weak)",
    "target_audience_fit": "Who this ad is clearly designed for"
  }},
  "overall_score": 75.0
}}

## Scoring Rubric for overall_score (0-100):
- **90-100**: Award-worthy. Exceptional craft, emotional resonance, distinctive creativity, perfect brand integration.
- **70-89**: Strong. Professional execution, clear strategy, memorable elements, effective brand presence.
- **50-69**: Solid. Competent execution, standard approach, adequate brand communication.
- **30-49**: Weak. Missed opportunities, forgettable, poor brand integration, unclear message.
- **0-29**: Poor. Confusing, low production quality, ineffective, brand disconnect.

Score based on: (1) Creative craft 30%, (2) Emotional impact 25%, (3) Brand integration 25%, (4) Memorability 20%.
Always fill every field. If unknown, explain why in that field.
"""


def _get_gemini_client(cfg: VisionConfig):
    if genai is None:
        raise RuntimeError("google-genai package is required for hero analysis but not installed.")
    if not cfg.api_key:
        raise RuntimeError("GOOGLE_API_KEY must be set for hero analysis.")
    return genai.Client(api_key=cfg.api_key)


def _build_content_parts(
    prompt: str, transcript_text: str, samples: Sequence[visual_analysis.FrameSample]
) -> Sequence[types.Part]:
    trimmed_transcript = transcript_text.strip()
    if len(trimmed_transcript) > MAX_TRANSCRIPT_CHARS:
        trimmed_transcript = trimmed_transcript[:MAX_TRANSCRIPT_CHARS] + "\n...[truncated]..."

    frame_timeline = "\n".join(
        f"Frame {idx}: timestamp={sample.timestamp:.2f}s"
        for idx, sample in enumerate(samples)
    )

    preface = (
        f"{prompt}\n\nFrames timeline:\n{frame_timeline}\n\nTranscript (with timestamps):\n"
        f"{trimmed_transcript}\n"
    )
    parts = [types.Part.from_text(text=preface)]
    for sample in samples:
        if len(parts) >= MAX_FRAMES + 1:
            break
        with open(sample.frame_path, "rb") as fh:
            parts.append(types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg"))
    return parts


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    first_newline = cleaned.find("\n")
    if first_newline != -1:
        cleaned = cleaned[first_newline + 1:]
    if cleaned.rstrip().endswith("```"):
        cleaned = cleaned.rstrip()[:-3].rstrip()
    return cleaned


def _parse_json(content: str) -> Dict:
    # Strip markdown fences if Gemini wrapped the response
    cleaned = _strip_markdown_fences(content)
    
    # Try parsing cleaned content first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON object
    if "{" in cleaned and "}" in cleaned:
        try:
            extracted = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass
    
    # Log and raise if all attempts fail
    logger.error("Hero analysis JSON parse failed. Raw (first 500 chars): %s", content[:500])
    raise ValueError("Hero analysis output was not valid JSON.")


def _normalise_hero_analysis(payload: Dict) -> Dict:
    """
    Ensure overall_score exists and is a float within the expected band.
    """
    data = dict(payload) if payload is not None else {}
    score_value = data.get("overall_score")
    normalised_score: float | None = None
    if score_value is not None:
        try:
            normalised_score = float(score_value)
        except (TypeError, ValueError):
            normalised_score = None
        else:
            if not (SCORE_MIN <= normalised_score <= SCORE_MAX):
                normalised_score = None
    data["overall_score"] = normalised_score
    return data


def analyse_hero_ad(
    video_path: str,
    transcript_text: str,
    *,
    tier: str | None = "quality",
) -> Dict:
    """
    Run the deep hero analysis against Gemini 3 Pro (quality tier).
    """
    vision_cfg = get_vision_config()
    if vision_cfg.provider != "google":
        raise RuntimeError("Hero analysis requires VISION_PROVIDER=google.")

    model_name = resolve_vision_model(tier, vision_cfg)
    if not model_name:
        raise RuntimeError("Unable to resolve Gemini model for hero analysis.")

    samples: Sequence[visual_analysis.FrameSample] = []
    try:
        samples = visual_analysis.sample_frames_for_storyboard(
            video_path, HERO_FRAME_SAMPLE_SECONDS
        )
        client = _get_gemini_client(vision_cfg)
        content_parts = _build_content_parts(HERO_ANALYSIS_PROMPT, transcript_text, samples[:MAX_FRAMES])
        response = client.models.generate_content(
            model=model_name,
            contents=content_parts,
        )
        raw_text = getattr(response, "text", None)
        if not raw_text:
            raise RuntimeError("Gemini hero analysis returned empty response.")
        return _normalise_hero_analysis(_parse_json(raw_text))
    finally:
        if samples:
            visual_analysis.cleanup_frame_samples(samples)


__all__ = ["analyse_hero_ad"]


