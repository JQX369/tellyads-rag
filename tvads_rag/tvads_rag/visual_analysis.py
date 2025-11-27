"""
Optional storyboard extraction powered by frame sampling + Gemini vision.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore
    types = None  # type: ignore

from .config import get_vision_config, is_vision_enabled, resolve_vision_model, VisionConfig

logger = logging.getLogger(__name__)

MAX_GEMINI_FRAMES = 24


class StoryboardError(Exception):
    """Base exception for storyboard processing errors."""
    pass


class SafetyBlockError(StoryboardError):
    """Raised when content is blocked by safety filters."""
    def __init__(self, reason: str = "Content blocked by safety filter"):
        self.reason = reason
        super().__init__(reason)


class StoryboardTimeoutError(StoryboardError):
    """Raised when storyboard generation times out."""
    pass

STORYBOARD_PROMPT = """You are an expert storyboard analyst and visual creative strategist. Analyse the sequential frames from this TV advertisement.

## Your Task
Group adjacent frames into coherent SHOTS (continuous camera moments without cuts). For each shot, extract detailed visual metadata.

## Analysis Guidelines
1. **Shot Detection - BE GRANULAR**: A new shot begins when there's:
   - A camera cut (hard cut, fade, wipe, dissolve)
   - Significant angle change (wide to close-up, different perspective)
   - Scene transition (location change, time change)
   - Subject change (different person/product becomes focus)
   - Camera movement type change (static to tracking, handheld to steady)
   - Composition change (single subject to multiple, product to person)
   
   **IMPORTANT**: Be sensitive to subtle changes. Even small shifts in focus, framing, or subject can indicate a new shot. Don't group frames that show different moments or perspectives - err on the side of more shots rather than fewer.

2. **Brand Detection**: Look carefully for logos, brand names, product packaging, app screens, URLs, phone numbers. Pay special attention to end cards and final frames.

3. **People & Talent**: Describe any people visible - actors, real customers, celebrities. What are they doing?

4. **Text & Supers**: Capture ALL on-screen text verbatim - legal text, offers, URLs, phone numbers, prices. Note when text appears/disappears as this may indicate a shot boundary.

5. **Product Visibility**: When products appear, describe how they're framed (hero shot, in-use, packshot). Product shots are often distinct shots.

## Output Format
Return STRICT JSON array (no markdown fences, no commentary):
[
  {{
    "shot_index": 0,
    "start_time": 0.0,
    "end_time": 2.5,
    "shot_label": "Brief title (e.g., 'Hero product packshot with logo')",
    "description": "Detailed 2-3 sentence description: what's happening, who's visible, what products/brands appear.",
    "camera_style": "static_wide | handheld_close | tracking | dolly | pov | split_screen | animation | other",
    "location_hint": "Specific setting (e.g., 'modern_kitchen', 'city_street', 'studio_white')",
    "key_objects": ["product", "phone", "logo", "food", "car"],
    "on_screen_text": "Exact visible text (supers, URLs, legal) or null",
    "mood": "Emotional tone (e.g., 'warm_family', 'high_energy', 'aspirational', 'comedic', 'urgent')"
  }}
]

Use the frame timestamps to estimate shot boundaries. Be thorough and granular - capture every distinct shot, even if shots are brief. A typical 30-second ad should have 8-15 shots or more.
"""


@dataclass
class FrameSample:
    frame_path: Path
    timestamp: float


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to sample frames but was not found on PATH.")


def _get_video_duration(video_path: str) -> float:
    """
    Get video duration in seconds using ffprobe.
    
    Returns duration as float, or 0.0 if unable to determine.
    """
    if shutil.which("ffprobe") is None:
        logger.warning("ffprobe not found, cannot determine video duration")
        return 0.0
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        duration = float(result.stdout.strip())
        logger.debug("Video duration: %.2fs for %s", duration, video_path)
        return duration
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.warning("Could not determine video duration: %s", e)
        return 0.0


def sample_frames_for_storyboard(
    video_path: str, 
    frame_every_s: float,
    trigger_timestamps: Optional[List[float]] = None
) -> List[FrameSample]:
    """
    Extract frames at specific timestamps using ffmpeg and return FrameSample instances.
    
    Always includes:
    - First frame (t=0) - captures opening/hook
    - Last frame (t=duration-0.1s) - captures end card with brand/CTA
    - Interval samples in between
    - Trigger timestamps (e.g. from audio keywords) if provided
    """
    _ensure_ffmpeg()
    src = Path(video_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Video not found for storyboard sampling: {src}")

    # Get video duration to ensure we capture the last frame
    duration = _get_video_duration(str(src))
    
    # Calculate timestamps: first frame, interval samples, last frame
    timestamps: List[float] = [0.0]  # Always start with first frame
    
    if duration > 0:
        # Add interval samples (but stop before the last frame zone)
        t = frame_every_s
        while t < duration - 0.5:  # Stop 0.5s before end to avoid overlap with last frame
            timestamps.append(t)
            t += frame_every_s
        
        # Add audio trigger timestamps if valid
        if trigger_timestamps:
            for ts in trigger_timestamps:
                if 0 < ts < duration:
                    timestamps.append(ts)
            
        # Always add last frame (0.1s before end to ensure valid frame exists)
        last_frame_time = max(0.1, duration - 0.1)
        if last_frame_time > max(timestamps) + 0.3:  # Only add if meaningfully different
            timestamps.append(last_frame_time)
        
        # Sort and deduplicate (keep timestamps that are at least 0.2s apart)
        timestamps.sort()
        unique_timestamps = []
        if timestamps:
            unique_timestamps.append(timestamps[0])
            for ts in timestamps[1:]:
                if ts - unique_timestamps[-1] >= 0.2:
                    unique_timestamps.append(ts)
        timestamps = unique_timestamps
        
        logger.debug(
            "Frame timestamps for %.1fs video: %s (including triggers)",
            duration, [f"{t:.1f}s" for t in timestamps]
        )
    else:
        # Fallback: if we couldn't get duration, use old interval-based approach
        logger.warning("Could not get duration, falling back to interval sampling")
        temp_dir = Path(tempfile.mkdtemp(prefix="tvads_frames_"))
        pattern = temp_dir / "frame_%06d.jpg"
        fps_filter = f"fps=1/{frame_every_s:.6f}"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(src), "-vf", fps_filter, "-qscale:v", "2", str(pattern),
        ]
        subprocess.run(cmd, check=True)
        samples: List[FrameSample] = []
        for idx, frame_path in enumerate(sorted(temp_dir.glob("frame_*.jpg"))):
            samples.append(FrameSample(frame_path=frame_path, timestamp=idx * frame_every_s))
        return samples

    # Extract frames at specific timestamps
    temp_dir = Path(tempfile.mkdtemp(prefix="tvads_frames_"))
    samples: List[FrameSample] = []
    
    for idx, ts in enumerate(timestamps):
        frame_path = temp_dir / f"frame_{idx:06d}.jpg"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{ts:.3f}",  # Seek to timestamp
            "-i", str(src),
            "-frames:v", "1",    # Extract exactly 1 frame
            "-qscale:v", "2",
            str(frame_path),
        ]
        try:
            subprocess.run(cmd, check=True)
            if frame_path.exists():
                samples.append(FrameSample(frame_path=frame_path, timestamp=ts))
        except subprocess.CalledProcessError as e:
            logger.warning("Failed to extract frame at %.2fs: %s", ts, e)
    
    logger.debug("Extracted %d frames (first=%.1fs, last=%.1fs)", 
                 len(samples), 
                 samples[0].timestamp if samples else 0,
                 samples[-1].timestamp if samples else 0)
    
    return samples


def cleanup_frame_samples(samples: Sequence[FrameSample]) -> None:
    """Delete sampled frame files and parent folders."""
    seen_dirs = set()
    for sample in samples:
        try:
            if sample.frame_path.exists():
                sample.frame_path.unlink()
        except OSError:
            logger.warning("Unable to delete frame %s", sample.frame_path)
        seen_dirs.add(sample.frame_path.parent)

    for directory in seen_dirs:
        try:
            directory.rmdir()
        except OSError:
            # Directory may not be empty; best-effort cleanup.
            pass


def analyse_frames_to_storyboard(
    samples: Sequence[FrameSample], 
    tier: str | None = None,
    transcript_text: Optional[str] = None
) -> List[dict]:
    """
    Convert sampled frames into storyboard shots via Gemini (if enabled).
    """
    vision_cfg = get_vision_config()
    if not is_vision_enabled(vision_cfg) or not samples:
        return []
    if vision_cfg.provider == "google":
        if genai is None:
            raise RuntimeError(
                "google-genai package is required for Gemini vision but is not installed."
            )
        model_name = resolve_vision_model(tier, vision_cfg)
        if not model_name:
            raise RuntimeError("Vision model could not be resolved for the requested tier.")
        return _analyse_with_gemini(samples, vision_cfg, model_name, transcript_text)
    return []


def _analyse_with_gemini(
    samples: Sequence[FrameSample], 
    cfg: VisionConfig, 
    model_name: str,
    transcript_text: Optional[str] = None
) -> List[dict]:
    if genai is None:
        raise RuntimeError("google-genai package is not installed.")

    client = genai.Client(api_key=cfg.api_key)
    limited = list(samples)[:MAX_GEMINI_FRAMES]
    timeline = "\n".join(
        f"Frame {idx}: timestamp={sample.timestamp:.2f}s" for idx, sample in enumerate(limited)
    )
    
    # Inject transcript context if available
    context_injection = ""
    if transcript_text:
        context_injection = f"\n\n## Audio Context (Transcript)\nUse this transcript to help identify what is happening, especially for brand mentions, dialogue context, and matching visuals to spoken words:\n\n{transcript_text}\n"
    
    prompt = f"{STORYBOARD_PROMPT}{context_injection}\nFrames timeline:\n{timeline}"

    content_parts = [types.Part.from_text(text=prompt)]
    for sample in limited:
        with open(sample.frame_path, "rb") as fh:
            content_parts.append(
                types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg")
            )

    response = client.models.generate_content(
        model=model_name,
        contents=content_parts,
    )
    
    # Check for blocked/filtered responses
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        # Check for content filtering
        if hasattr(candidate, "finish_reason"):
            finish_reason = str(candidate.finish_reason).upper()
            if "SAFETY" in finish_reason or "BLOCKED" in finish_reason:
                logger.warning(
                    "Gemini storyboard blocked by safety filter: %s",
                    finish_reason
                )
                raise SafetyBlockError(f"Content blocked by Gemini safety filter: {finish_reason}")
    
    raw = getattr(response, "text", None) or ""
    
    # Handle empty responses gracefully
    if not raw.strip():
        logger.warning(
            "Gemini returned empty storyboard response for %d frames. "
            "This may indicate content filtering or a video with no clear shots.",
            len(samples)
        )
        return []  # Return empty list instead of failing
    
    parsed = _parse_storyboard_json(raw)
    return _normalise_shots(parsed)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ``` or ``` ... ```) from text."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    
    # Remove opening fence (with optional language tag like ```json)
    first_newline = cleaned.find("\n")
    if first_newline != -1:
        cleaned = cleaned[first_newline + 1:]
    else:
        # No newline after opening fence - malformed, return as-is
        return text
    
    # Remove closing fence
    if cleaned.rstrip().endswith("```"):
        cleaned = cleaned.rstrip()[:-3].rstrip()
    
    return cleaned


def _parse_storyboard_json(raw_output: str) -> List[dict]:
    """Parse Gemini storyboard output, handling markdown-wrapped JSON and incomplete responses."""
    # Handle empty input
    if not raw_output or not raw_output.strip():
        logger.debug("Empty storyboard output received")
        return []
    
    # First strip any markdown code fences
    cleaned = _strip_markdown_fences(raw_output)
    
    # If still empty after stripping, return empty list
    if not cleaned.strip():
        return []
    
    # Try to repair incomplete JSON (common with Gemini when response is cut off)
    def _try_repair_incomplete_json(text: str) -> Optional[str]:
        """Attempt to repair incomplete JSON by closing brackets/braces."""
        if not text.strip():
            return None
        
        # Count brackets/braces
        open_brackets = text.count("[") - text.count("]")
        open_braces = text.count("{") - text.count("}")
        
        # If we have unclosed brackets/braces, try to close them
        repaired = text
        if open_brackets > 0:
            repaired += "]" * open_brackets
        if open_braces > 0:
            repaired += "}" * open_braces
        
        return repaired if repaired != text else None
    
    candidates = [
        cleaned,
        # Extract array content
        cleaned[cleaned.find("["):cleaned.rfind("]") + 1]
        if "[" in cleaned and "]" in cleaned
        else None,
        # Extract object content (for {"shots": [...]} format)
        cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
        if "{" in cleaned and "}" in cleaned
        else None,
        # Try repairing incomplete JSON
        _try_repair_incomplete_json(cleaned),
        # Try extracting partial array if JSON is incomplete
        cleaned[cleaned.find("["):] + "]" if "[" in cleaned and cleaned.count("[") > cleaned.count("]") else None,
    ]
    
    for blob in candidates:
        if not blob:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError as e:
            logger.debug("JSON parse attempt failed: %s", str(e)[:100])
            continue
        
        if isinstance(data, dict) and "shots" in data:
            shots = data.get("shots") or []
            if shots:
                return shots
        
        if isinstance(data, list):
            if data:  # Only return non-empty lists
                return data
    
    # Last resort: Try to extract individual shot objects using regex
    # This handles cases where JSON is malformed but individual objects are valid
    import re
    shot_pattern = r'\{\s*"shot_index"\s*:\s*\d+[^}]*\}'
    matches = re.findall(shot_pattern, cleaned, re.DOTALL)
    if matches:
        shots = []
        for match in matches:
            try:
                shot = json.loads(match)
                if isinstance(shot, dict) and "shot_index" in shot:
                    shots.append(shot)
            except json.JSONDecodeError:
                continue
        if shots:
            logger.info("Extracted %d shots using regex fallback (JSON was malformed)", len(shots))
            return shots
    
    # Log the raw output for debugging before raising
    logger.warning(
        "Failed to parse Gemini storyboard JSON. Raw output (first 1000 chars): %s",
        raw_output[:1000]
    )
    logger.warning(
        "Raw output (last 500 chars): %s",
        raw_output[-500:] if len(raw_output) > 500 else raw_output
    )
    raise ValueError("Gemini storyboard output was not valid JSON.")


def _normalise_shots(shots: Iterable[dict]) -> List[dict]:
    normalised: List[dict] = []
    for idx, shot in enumerate(shots):
        key_objects = shot.get("key_objects")
        if isinstance(key_objects, str):
            key_objects = [key_objects]
        normalised.append(
            {
                "shot_index": shot.get("shot_index", idx),
                "start_time": shot.get("start_time"),
                "end_time": shot.get("end_time"),
                "shot_label": shot.get("shot_label"),
                "description": shot.get("description"),
                "camera_style": shot.get("camera_style"),
                "location_hint": shot.get("location_hint"),
                "key_objects": key_objects or [],
                "on_screen_text": shot.get("on_screen_text"),
                "mood": shot.get("mood"),
            }
        )
    return normalised


__all__ = [
    "FrameSample",
    "sample_frames_for_storyboard",
    "cleanup_frame_samples",
    "analyse_frames_to_storyboard",
]

