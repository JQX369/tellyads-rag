"""
Media utilities for listing, probing, and extracting data from ad video assets.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

try:
    import boto3
except ImportError:  # pragma: no cover - optional dependency guard
    boto3 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".mpg", ".mpeg"}


def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def list_local_videos(
    root_dir: str,
    limit: Optional[int] = None,
    offset: int = 0,
    single_path: Optional[str] = None,
) -> List[Path]:
    """
    Return a list of video Paths under root_dir filtered by extension.

    Args:
        root_dir: Base directory containing ad videos.
        limit: Optional maximum number of files to return.
        offset: Skip the first N files (after sorting by name).
        single_path: If provided, return only this path (resolved relative to root).
    """
    root = Path(root_dir).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Local video directory does not exist: {root}")

    if single_path:
        candidate = Path(single_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Single video path not found: {candidate}")
        if not _is_video_file(candidate):
            raise ValueError(f"Path is not a supported video file: {candidate}")
        return [candidate]

    files = sorted(
        [p for p in root.rglob("*") if p.is_file() and _is_video_file(p)],
        key=lambda p: str(p).lower(),
    )

    if offset:
        files = files[offset:]
    if limit is not None:
        files = files[:limit]
    return files


def _natural_sort_key(key: str) -> tuple:
    """
    Generate a sort key for natural/numeric sorting.
    
    Example: "TA1000.mp4" -> ("ta", 1000, ".mp4")
    This ensures TA1000 comes before TA10000 numerically.
    """
    parts = re.split(r'(\d+)', key)
    result = []
    for part in parts:
        if part.isdigit():
            result.append(int(part))
        else:
            result.append(part.lower())
    return tuple(result)


def list_s3_videos(
    bucket: str,
    prefix: str,
    limit: Optional[int] = None,
    offset: int = 0,
    single_key: Optional[str] = None,
) -> List[str]:
    """
    List video object keys from S3 using pagination.
    
    Returns keys sorted naturally (numeric-aware) so TA1000 comes before TA10000.
    S3 returns keys in lexicographic order, which causes TA10000 to come before TA1000.
    """
    if boto3 is None:
        raise RuntimeError("boto3 is required for S3 operations but is not installed.")
    s3 = boto3.client("s3")
    if single_key:
        return [single_key]

    collected: List[str] = []
    continuation_token = None

    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        resp = s3.list_objects_v2(**kwargs)
        contents = resp.get("Contents", [])
        for obj in contents:
            key = obj["Key"]
            if _is_video_file(Path(key)):
                collected.append(key)

        if resp.get("IsTruncated"):
            continuation_token = resp.get("NextContinuationToken")
        else:
            break

        if limit is not None and len(collected) >= offset + limit:
            break

    # Sort naturally (numeric-aware) so TA1000 comes before TA10000
    collected.sort(key=_natural_sort_key)

    if offset:
        collected = collected[offset:]
    if limit is not None:
        collected = collected[:limit]
    return collected


def s3_object_exists(bucket: str, key: str) -> bool:
    """
    Check if an S3 object exists without downloading it.
    """
    if boto3 is None:
        raise RuntimeError("boto3 is required for S3 operations but is not installed.")
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as e:
        # boto3 raises ClientError (from botocore.exceptions) for 404s
        error_code = ""
        if hasattr(e, "response"):
            error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404" or error_code == "NoSuchKey" or "Not Found" in str(e):
            return False
        # Re-raise other errors (permissions, etc.)
        raise


def download_s3_object_to_tempfile(bucket: str, key: str) -> Path:
    """
    Download a single S3 object to a temporary file and return the local Path.
    
    Raises FileNotFoundError if the object doesn't exist in S3.
    """
    if boto3 is None:
        raise RuntimeError("boto3 is required for S3 operations but is not installed.")
    
    # Check if file exists first
    if not s3_object_exists(bucket, key):
        raise FileNotFoundError(f"S3 object not found: s3://{bucket}/{key}")
    
    s3 = boto3.client("s3")
    suffix = Path(key).suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    tmp.close()
    logger.info("Downloading s3://%s/%s -> %s", bucket, key, tmp_path)
    with open(tmp_path, "wb") as fh:
        s3.download_fileobj(bucket, key, fh)
    return tmp_path


def _ensure_binary_exists(binary: str) -> None:
    if shutil.which(binary) is None:
        raise RuntimeError(
            f"Required binary '{binary}' not found on PATH. Please install ffmpeg."
        )


def _parse_frame_rate(rate_str: Optional[str]) -> Optional[float]:
    if not rate_str:
        return None
    if "/" in rate_str:
        numerator, denominator = rate_str.split("/", 1)
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(rate_str)
    except ValueError:
        return None


def normalize_ad_duration(duration: float, tolerance: float = 0.5) -> float:
    """
    Round duration to standard TV ad lengths (15s, 30s, 45s, 60s, 90s, 120s).
    
    TV ads are typically exactly 15s, 30s, 60s, etc., but video encoding can introduce
    small variations (e.g., 29.97s, 30.03s). This function rounds to the nearest
    standard length if within tolerance.
    
    Args:
        duration: Raw duration from video file
        tolerance: Maximum deviation from standard length to round (default 0.5s)
    
    Returns:
        Normalized duration (standard length if within tolerance, otherwise original)
    """
    if duration <= 0:
        return duration
    
    # Standard TV ad lengths (in seconds)
    standard_lengths = [15, 30, 45, 60, 90, 120, 180]
    
    # Find nearest standard length
    for standard in standard_lengths:
        if abs(duration - standard) <= tolerance:
            logger.debug(
                "Normalizing duration %.2fs -> %ds (within %.1fs tolerance)",
                duration, standard, tolerance
            )
            return float(standard)
    
    # If no standard length matches, return original (might be non-standard like 10s, 20s)
    return duration


def probe_media(path: str) -> dict:
    """
    Use ffprobe to extract duration, resolution, fps, and aspect ratio metadata.
    
    Duration is normalized to standard TV ad lengths (15s, 30s, 60s, etc.)
    if within 0.5s tolerance.
    """
    _ensure_binary_exists("ffprobe")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    logger.debug("Running ffprobe: %s", " ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=True  # noqa: S603,S607
    )
    info = json.loads(result.stdout)
    raw_duration = float(info["format"].get("duration", 0.0))
    duration = normalize_ad_duration(raw_duration)
    
    video_stream = next(
        (stream for stream in info.get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    width = video_stream.get("width")
    height = video_stream.get("height")
    fps = _parse_frame_rate(video_stream.get("r_frame_rate"))

    aspect_ratio = None
    if width and height:
        aspect_ratio = f"{width}:{height}"

    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "aspect_ratio": aspect_ratio,
    }


def extract_audio(video_path: str, out_dir: Optional[str] = None) -> Path:
    """
    Use ffmpeg to extract mono 16kHz audio suitable for ASR.
    """
    _ensure_binary_exists("ffmpeg")
    src = Path(video_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Video file not found: {src}")

    target_dir = Path(out_dir).expanduser() if out_dir else Path(tempfile.gettempdir())
    target_dir.mkdir(parents=True, exist_ok=True)
    audio_path = target_dir / f"{src.stem}_audio.wav"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        "-f",
        "wav",
        str(audio_path),
    ]
    logger.debug("Running ffmpeg: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)  # noqa: S603,S607
    return audio_path


__all__ = [
    "list_local_videos",
    "list_s3_videos",
    "s3_object_exists",
    "download_s3_object_to_tempfile",
    "probe_media",
    "normalize_ad_duration",
    "extract_audio",
]

