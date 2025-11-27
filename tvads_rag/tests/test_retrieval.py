import pytest

pytest.importorskip("psycopg2")

from tvads_rag import retrieval, reranker
from tvads_rag.config import RerankConfig


def test_retrieve_with_rerank_invokes_reranker(monkeypatch):
    monkeypatch.setattr(retrieval.embeddings, "embed_texts", lambda texts: [[0.1, 0.2]])
    candidates = [{"text": "one"}, {"text": "two"}]
    monkeypatch.setattr(retrieval.db_helpers, "hybrid_search", lambda *args, **kwargs: candidates)

    cfg = RerankConfig(provider="cohere", model_name="rerank-english-v3.0", api_key="test")
    monkeypatch.setattr(retrieval, "get_rerank_config", lambda: cfg)
    monkeypatch.setattr(retrieval, "is_rerank_enabled", lambda _: True)

    def fake_rerank(query, docs, top_n, config):
        assert top_n == 1
        return [{"text": "two", "rerank_score": 0.9}]

    monkeypatch.setattr(reranker, "rerank_candidates", fake_rerank)

    result = retrieval.retrieve_with_rerank("brand offer", candidate_k=5, final_k=1)
    assert result[0]["text"] == "two"


def test_retrieve_with_rerank_validates_limits():
    with pytest.raises(ValueError):
        retrieval.retrieve_with_rerank("query", candidate_k=0)

