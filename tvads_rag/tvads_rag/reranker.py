"""
Reranking helpers for blending Cohere scores into retrieval results.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable, List, Mapping, MutableMapping, Sequence

from .config import RerankConfig

try:  # pragma: no cover - optional dependency checked at runtime
    import cohere  # type: ignore
except ImportError:  # pragma: no cover - optional dependency checked at runtime
    cohere = None  # type: ignore[assignment]


def _ensure_cohere_installed() -> None:
    if cohere is None:  # pragma: no cover - exercised via unit tests
        raise RuntimeError(
            "cohere package is required for reranking but is not installed. "
            "Run `pip install cohere` or remove RERANK_PROVIDER=cohere."
        )


@lru_cache(maxsize=1)
def _get_cohere_client(api_key: str):
    _ensure_cohere_installed()
    return cohere.Client(api_key=api_key)


def rerank_candidates(
    query_text: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    top_n: int,
    config: RerankConfig,
) -> List[Mapping[str, Any]]:
    """
    Apply reranking based on the configured provider.

    Currently only Cohere is supported; when disabled the original order
    is preserved (truncated to ``top_n``).
    """
    if not candidates or top_n <= 0:
        return []
    limit = min(top_n, len(candidates))
    if config.provider != "cohere":
        return [dict(candidates[idx]) for idx in range(limit)]
    return _cohere_rerank(query_text, candidates, limit, config)


def _cohere_rerank(
    query_text: str,
    candidates: Sequence[Mapping[str, Any]],
    top_n: int,
    config: RerankConfig,
) -> List[Mapping[str, Any]]:
    client = _get_cohere_client(config.api_key or "")
    documents = [{"text": str(candidate.get("text", "") or "")} for candidate in candidates]
    response = client.rerank(
        model=config.model_name,
        query=query_text,
        documents=documents,
        top_n=top_n,
    )
    scores = {result.index: getattr(result, "relevance_score", 0.0) for result in response.results}
    ordered_indices = sorted(
        range(len(candidates)),
        key=lambda idx: (scores.get(idx, 0.0), -idx),
        reverse=True,
    )[:top_n]

    reranked: List[Mapping[str, Any]] = []
    for idx in ordered_indices:
        item = dict(candidates[idx])
        item["rerank_score"] = scores.get(idx)
        reranked.append(item)
    return reranked


__all__ = ["rerank_candidates"]

