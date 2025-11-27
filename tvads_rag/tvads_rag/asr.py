"""
ASR wrapper for extracting transcripts with timestamps.

Defaults to the OpenAI Whisper API but also supports a lightweight stub for
offline testing via USE_DUMMY_ASR env var or force_stub argument.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, List, Optional

from openai import OpenAI

from .config import get_openai_config

DEFAULT_ASR_MODEL = os.getenv("ASR_MODEL_NAME", "whisper-1")
USE_DUMMY_ASR = os.getenv("USE_DUMMY_ASR", "").lower() in {"1", "true", "yes"}


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    cfg = get_openai_config()
    return OpenAI(api_key=cfg.api_key, base_url=cfg.api_base)


def _call_whisper(audio_path: str, model: Optional[str] = None) -> Dict[str, object]:
    """Invoke the OpenAI Whisper transcription API with verbose segments."""
    client = _get_openai_client()
    model_name = model or DEFAULT_ASR_MODEL
    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=model_name,
            file=audio_file,
            response_format="verbose_json",
            temperature=0,
        )

    segments = [
        {"start": seg.start, "end": seg.end, "text": seg.text or ""}
        for seg in response.segments or []
    ]
    return {"text": response.text, "segments": segments}


def _stub_transcript(audio_path: str) -> Dict[str, object]:
    """Return a placeholder transcript useful for smoke tests."""
    basename = os.path.basename(audio_path)
    placeholder = f"Transcription stub for {basename}"
    return {"text": placeholder, "segments": [{"start": 0.0, "end": 0.0, "text": placeholder}]}


def transcribe_audio(audio_path: str, *, force_stub: Optional[bool] = None) -> Dict[str, object]:
    """
    Transcribe an audio file into a dict with `text` + `segments`.

    Args:
        audio_path: Path to the mono 16kHz WAV file.
        force_stub: Optional override to force the stub transcript.
    """
    if force_stub is True or (force_stub is None and USE_DUMMY_ASR):
        return _stub_transcript(audio_path)
    return _call_whisper(audio_path)


__all__ = ["transcribe_audio"]

