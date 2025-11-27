import pytest

from tvads_rag import reranker
from tvads_rag.config import RerankConfig


def test_rerank_candidates_no_provider_returns_slice():
    cfg = RerankConfig(provider="none", model_name=None, api_key=None)
    candidates = [{"text": "a"}, {"text": "b"}, {"text": "c"}]
    result = reranker.rerank_candidates("query", candidates, top_n=2, config=cfg)
    assert [row["text"] for row in result] == ["a", "b"]


def test_cohere_rerank_orders_by_scores(monkeypatch):
    cfg = RerankConfig(provider="cohere", model_name="rerank-english-v3.0", api_key="test")
    candidates = [{"text": "first"}, {"text": "second"}, {"text": "third"}]

    class FakeResult:
        def __init__(self, index, relevance_score):
            self.index = index
            self.relevance_score = relevance_score

    class FakeResponse:
        def __init__(self, results):
            self.results = results

    class FakeClient:
        def __init__(self, results):
            self._results = results

        def rerank(self, **kwargs):
            return FakeResponse(self._results)

    results = [FakeResult(2, 0.9), FakeResult(0, 0.5), FakeResult(1, 0.1)]
    fake_client = FakeClient(results)
    monkeypatch.setattr(reranker, "_get_cohere_client", lambda api_key: fake_client)

    ranked = reranker.rerank_candidates("query", candidates, top_n=3, config=cfg)
    assert [row["text"] for row in ranked] == ["third", "first", "second"]
    assert ranked[0]["rerank_score"] == pytest.approx(0.9)

