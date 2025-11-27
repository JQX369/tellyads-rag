"""
Configuration helpers for the TV Ads RAG pipeline.

Centralises environment variable loading/validation so the rest of the codebase
can depend on typed config objects instead of sprinkling os.getenv calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

VIDEO_SOURCE_CHOICES = {"local", "s3"}
VISION_PROVIDER_CHOICES = {"none", "google"}
VISION_TIER_CHOICES = {"fast", "quality"}
RERANK_PROVIDER_CHOICES = {"none", "cohere"}
DEFAULT_VISION_FAST_MODEL = "gemini-2.5-flash"  # Used for regular storyboard analysis
DEFAULT_VISION_QUALITY_MODEL = "gemini-3-pro-preview"  # Used for hero ads (top 10% by views) - deep analysis


@dataclass(frozen=True)
class DBConfig:
    """Connection info for Supabase Postgres."""

    url: str
    supabase_url: Optional[str]
    service_key: Optional[str]


@dataclass(frozen=True)
class OpenAIConfig:
    """OpenAI-compatible API credentials and model names."""

    api_key: str
    api_base: str
    llm_model_name: str
    embedding_model_name: str


@dataclass(frozen=True)
class RerankConfig:
    """Optional reranking service configuration."""

    provider: str
    model_name: Optional[str]
    api_key: Optional[str]


@dataclass(frozen=True)
class StorageConfig:
    """Source media storage (local directory or S3 bucket)."""

    video_source_type: str
    local_video_dir: Optional[str]
    s3_bucket: Optional[str]
    s3_prefix: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    aws_region: Optional[str]


@dataclass(frozen=True)
class PipelineConfig:
    """Misc pipeline knobs."""

    log_level: str
    index_source_default: str


@dataclass(frozen=True)
class VisionConfig:
    """Optional vision/storyboard configuration."""

    provider: str
    model_name: Optional[str]
    fast_model_name: Optional[str]
    quality_model_name: Optional[str]
    default_tier: str
    api_key: Optional[str]
    frame_sample_seconds: float


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Wrapper around os.getenv that trims whitespace."""
    value = os.getenv(name, default)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or default


def _require_env(name: str) -> str:
    """Fetch an environment variable or raise a helpful error."""
    value = _get_env(name)
    if not value:
        raise RuntimeError(f"Expected environment variable '{name}' to be set.")
    return value


def _normalize_source(value: Optional[str]) -> str:
    normalized = (value or "local").lower()
    if normalized not in VIDEO_SOURCE_CHOICES:
        raise ValueError(
            f"VIDEO_SOURCE_TYPE must be one of {sorted(VIDEO_SOURCE_CHOICES)}, got '{value}'."
        )
    return normalized


def _get_float_env(name: str, default: float) -> float:
    raw = _get_env(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float, got '{raw}'.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}.")
    return value


@lru_cache(maxsize=1)
def get_db_config() -> DBConfig:
    """Return Supabase/Postgres connection info."""
    url = _require_env("SUPABASE_DB_URL")
    return DBConfig(
        url=url,
        supabase_url=_get_env("SUPABASE_URL"),
        service_key=_get_env("SUPABASE_SERVICE_KEY"),
    )


@lru_cache(maxsize=1)
def get_openai_config() -> OpenAIConfig:
    """Return OpenAI-compatible API configuration."""
    text_llm = _get_env("TEXT_LLM_MODEL") or _get_env("LLM_MODEL_NAME") or "gpt-5.1"
    # Validate known model names and provide helpful warnings
    known_models = {"gpt-5.1", "gpt-4o", "gpt-4-turbo", "gpt-4o-mini", "gpt-4-turbo-preview"}
    if text_llm not in known_models:
        import logging
        logging.getLogger(__name__).warning(
            f"TEXT_LLM_MODEL '{text_llm}' is not a known model. Known models: {sorted(known_models)}"
        )
    embedding_model = (
        _get_env("EMBEDDING_MODEL") or _get_env("EMBEDDING_MODEL_NAME") or "text-embedding-3-large"
    )
    return OpenAIConfig(
        api_key=_require_env("OPENAI_API_KEY"),
        api_base=_get_env("OPENAI_API_BASE") or "https://api.openai.com/v1",
        llm_model_name=text_llm,
        embedding_model_name=embedding_model,
    )


@lru_cache(maxsize=1)
def get_storage_config() -> StorageConfig:
    """Return info about where videos reside (local dir or S3)."""
    video_source_type = _normalize_source(_get_env("VIDEO_SOURCE_TYPE"))

    local_video_dir = _get_env("LOCAL_VIDEO_DIR")
    s3_bucket = _get_env("S3_BUCKET")
    s3_prefix = _get_env("S3_PREFIX")

    if video_source_type == "local" and not local_video_dir:
        raise RuntimeError("LOCAL_VIDEO_DIR must be set when VIDEO_SOURCE_TYPE=local")
    if video_source_type == "s3" and not (s3_bucket and s3_prefix):
        raise RuntimeError(
            "S3_BUCKET and S3_PREFIX must be set when VIDEO_SOURCE_TYPE=s3"
        )

    return StorageConfig(
        video_source_type=video_source_type,
        local_video_dir=local_video_dir,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        aws_access_key_id=_get_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_get_env("AWS_SECRET_ACCESS_KEY"),
        aws_region=_get_env("AWS_REGION"),
    )


@lru_cache(maxsize=1)
def get_pipeline_config() -> PipelineConfig:
    """Return misc pipeline toggles."""
    index_source_default = _normalize_source(_get_env("INDEX_SOURCE_DEFAULT"))
    return PipelineConfig(
        log_level=_get_env("LOG_LEVEL") or "INFO",
        index_source_default=index_source_default,
    )


@lru_cache(maxsize=1)
def get_vision_config() -> VisionConfig:
    """Return configuration for optional Gemini storyboard analysis."""
    provider = (_get_env("VISION_PROVIDER") or "none").lower()
    if provider not in VISION_PROVIDER_CHOICES:
        raise ValueError(
            f"VISION_PROVIDER must be one of {sorted(VISION_PROVIDER_CHOICES)}, got '{provider}'."
        )
    fast_model = _get_env("VISION_MODEL_FAST")
    quality_model = _get_env("VISION_MODEL_QUALITY")
    legacy_model = _get_env("VISION_MODEL_NAME")
    if provider == "google":
        fast_model = fast_model or legacy_model or DEFAULT_VISION_FAST_MODEL
        quality_model = quality_model or DEFAULT_VISION_QUALITY_MODEL
        
        # Validate and auto-fix invalid model names
        if quality_model == "gemini-3.0-pro":
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "VISION_MODEL_QUALITY='gemini-3.0-pro' is invalid (model doesn't exist). "
                "Auto-fixing to 'gemini-3-pro-preview'. Please update your environment variable."
            )
            quality_model = DEFAULT_VISION_QUALITY_MODEL
    elif not fast_model and not quality_model:
        fast_model = legacy_model
    # Default to "fast" tier for regular storyboards (Gemini 2.5 Flash)
    # Quality tier is automatically used for hero ads regardless of this setting
    env_tier = _get_env("VISION_DEFAULT_TIER")
    if env_tier:
        default_tier = env_tier.lower()
        if default_tier not in VISION_TIER_CHOICES:
            raise ValueError(
                f"VISION_DEFAULT_TIER must be one of {sorted(VISION_TIER_CHOICES)}, got '{default_tier}'."
            )
    else:
        # Force "fast" as default (no environment variable set)
        default_tier = "fast"
    
    # Warn if default_tier is quality for regular storyboards (should be fast)
    if provider == "google" and default_tier == "quality":
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "VISION_DEFAULT_TIER='quality' will use expensive Gemini 3 Pro for all storyboards. "
            "Consider setting VISION_DEFAULT_TIER='fast' for regular storyboards (Gemini 2.5 Flash). "
            "Quality tier is automatically used for hero ads."
        )

    primary_model = (
        (quality_model or fast_model) if default_tier == "quality" else (fast_model or quality_model)
    )
    api_key = _get_env("GOOGLE_API_KEY")
    frame_sample_seconds = _get_float_env("FRAME_SAMPLE_SECONDS", 0.5)  # Default: 2 frames/second for better shot detection

    if provider == "google":
        if not primary_model:
            raise RuntimeError(
                "VISION_MODEL_FAST (or VISION_MODEL_QUALITY / legacy VISION_MODEL_NAME) must be set when VISION_PROVIDER=google."
            )
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY must be set when VISION_PROVIDER=google.")

    return VisionConfig(
        provider=provider,
        model_name=primary_model,
        fast_model_name=fast_model,
        quality_model_name=quality_model,
        default_tier=default_tier,
        api_key=api_key,
        frame_sample_seconds=frame_sample_seconds,
    )


@lru_cache(maxsize=1)
def get_rerank_config() -> RerankConfig:
    """Return configuration for optional reranking provider."""
    provider = (_get_env("RERANK_PROVIDER") or "none").lower()
    if provider not in RERANK_PROVIDER_CHOICES:
        raise ValueError(
            f"RERANK_PROVIDER must be one of {sorted(RERANK_PROVIDER_CHOICES)}, got '{provider}'."
        )
    model_name = _get_env("RERANK_MODEL")
    api_key: Optional[str] = None

    if provider == "cohere":
        api_key = _get_env("COHERE_API_KEY")
        if not api_key:
            raise RuntimeError("COHERE_API_KEY must be set when RERANK_PROVIDER=cohere.")
        if not model_name:
            model_name = "rerank-english-v3.0"

    return RerankConfig(provider=provider, model_name=model_name, api_key=api_key)


def is_vision_enabled(config: Optional[VisionConfig] = None) -> bool:
    """Convenience helper for gating storyboard logic."""
    cfg = config or get_vision_config()
    return cfg.provider != "none"


def resolve_vision_model(
    tier: Optional[str] = None, config: Optional[VisionConfig] = None
) -> Optional[str]:
    """Resolve the appropriate vision model for the requested tier."""
    cfg = config or get_vision_config()
    requested = (tier or cfg.default_tier or "fast").lower()
    if requested not in VISION_TIER_CHOICES:
        raise ValueError(
            f"Vision tier must be one of {sorted(VISION_TIER_CHOICES)}, got '{requested}'."
        )
    if requested == "quality":
        return cfg.quality_model_name or cfg.fast_model_name or cfg.model_name
    return cfg.fast_model_name or cfg.quality_model_name or cfg.model_name


def is_rerank_enabled(config: Optional[RerankConfig] = None) -> bool:
    """Return True when a reranking provider is configured."""
    cfg = config or get_rerank_config()
    return cfg.provider != "none"


def describe_active_models() -> dict:
    """Return a summary of the currently selected providers/models."""
    openai_cfg = get_openai_config()
    vision_cfg = get_vision_config()
    rerank_cfg = get_rerank_config()
    
    # Show both fast and quality models for vision
    vision_display = vision_cfg.provider
    if vision_cfg.provider != "none":
        if vision_cfg.fast_model_name and vision_cfg.quality_model_name:
            vision_display = f"{vision_cfg.provider}(fast={vision_cfg.fast_model_name}, quality={vision_cfg.quality_model_name})"
        else:
            vision_display = f"{vision_cfg.provider}({vision_cfg.model_name})"
    
    return {
        "text_llm": openai_cfg.llm_model_name,
        "embeddings": openai_cfg.embedding_model_name,
        "vision_provider": vision_cfg.provider,
        "vision_model": vision_cfg.model_name,
        "vision_display": vision_display,
        "rerank_provider": rerank_cfg.provider,
        "rerank_model": rerank_cfg.model_name,
    }


__all__ = [
    "DBConfig",
    "OpenAIConfig",
    "RerankConfig",
    "StorageConfig",
    "PipelineConfig",
    "VisionConfig",
    "resolve_vision_model",
    "get_db_config",
    "get_openai_config",
    "get_rerank_config",
    "get_storage_config",
    "get_pipeline_config",
    "get_vision_config",
    "is_vision_enabled",
    "is_rerank_enabled",
    "describe_active_models",
]

