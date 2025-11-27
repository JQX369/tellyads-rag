import pytest

from tvads_rag import config


def _reset_config_caches():
    config.get_openai_config.cache_clear()
    config.get_vision_config.cache_clear()
    config.get_rerank_config.cache_clear()


def test_openai_config_prefers_new_env_names(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("TEXT_LLM_MODEL", "gpt-5")
    monkeypatch.setenv("LLM_MODEL_NAME", "legacy-model")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "legacy-embed")

    _reset_config_caches()
    cfg = config.get_openai_config()
    assert cfg.llm_model_name == "gpt-5"
    assert cfg.embedding_model_name == "text-embedding-3-large"


def test_openai_config_defaults_to_latest_models(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("TEXT_LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)

    _reset_config_caches()
    cfg = config.get_openai_config()
    assert cfg.llm_model_name == "gpt-5.1"
    assert cfg.embedding_model_name == "text-embedding-3-large"


def test_vision_config_supports_fast_and_quality_models(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "google")
    monkeypatch.setenv("VISION_MODEL_FAST", "gemini-fast")
    monkeypatch.setenv("VISION_MODEL_QUALITY", "gemini-pro")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("FRAME_SAMPLE_SECONDS", "0.5")

    _reset_config_caches()
    cfg = config.get_vision_config()
    assert cfg.fast_model_name == "gemini-fast"
    assert cfg.quality_model_name == "gemini-pro"
    assert cfg.model_name == "gemini-fast"
    assert cfg.default_tier == "fast"


def test_vision_config_defaults_to_flash(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "google")
    monkeypatch.delenv("VISION_MODEL_FAST", raising=False)
    monkeypatch.delenv("VISION_MODEL_QUALITY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("VISION_MODEL_NAME", raising=False)

    _reset_config_caches()
    cfg = config.get_vision_config()
    assert cfg.fast_model_name == "gemini-2.0-flash-exp"
    assert cfg.model_name == "gemini-2.0-flash-exp"


def test_resolve_vision_model_prefers_quality_when_available(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "google")
    monkeypatch.setenv("VISION_MODEL_FAST", "gemini-fast")
    monkeypatch.setenv("VISION_MODEL_QUALITY", "gemini-pro")
    monkeypatch.setenv("VISION_DEFAULT_TIER", "quality")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    _reset_config_caches()
    cfg = config.get_vision_config()
    chosen = config.resolve_vision_model("quality", cfg)
    assert chosen == "gemini-pro"


def test_rerank_config_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("RERANK_PROVIDER", raising=False)
    monkeypatch.delenv("RERANK_MODEL", raising=False)

    _reset_config_caches()
    cfg = config.get_rerank_config()
    assert cfg.provider == "none"
    assert cfg.model_name is None
    assert cfg.api_key is None


def test_rerank_config_requires_api_key_for_cohere(monkeypatch):
    monkeypatch.setenv("RERANK_PROVIDER", "cohere")
    monkeypatch.setenv("RERANK_MODEL", "rerank-english-v3.0")
    monkeypatch.delenv("COHERE_API_KEY", raising=False)

    _reset_config_caches()
    with pytest.raises(RuntimeError):
        config.get_rerank_config()

    monkeypatch.setenv("COHERE_API_KEY", "ch-123")
    _reset_config_caches()
    cfg = config.get_rerank_config()
    assert cfg.provider == "cohere"
    assert cfg.model_name == "rerank-english-v3.0"
    assert cfg.api_key == "ch-123"

