"""
High-level retrieval helpers combining hybrid search + reranking.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence

from . import embeddings
from . import db_backend as db_helpers
from . import reranker
from .config import get_rerank_config, is_rerank_enabled

DEFAULT_CANDIDATE_K = 50
DEFAULT_FINAL_K = 10


def retrieve_with_rerank(
    query_text: str,
    *,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    final_k: int = DEFAULT_FINAL_K,
    item_types: Optional[Sequence[str]] = None,
) -> List[Mapping[str, Any]]:
    """
    Run hybrid search followed by optional reranking.
    """
    if final_k <= 0 or candidate_k <= 0:
        raise ValueError("candidate_k and final_k must be positive.")

    embedding = embeddings.embed_texts([query_text])[0]
    candidates = db_helpers.hybrid_search(embedding, query_text, candidate_k, item_types)
    rerank_cfg = get_rerank_config()
    if is_rerank_enabled(rerank_cfg):
        return reranker.rerank_candidates(
            query_text,
            candidates,
            top_n=final_k,
            config=rerank_cfg,
        )
    return list(candidates)[: min(final_k, len(candidates))]


__all__ = ["retrieve_with_rerank"]

