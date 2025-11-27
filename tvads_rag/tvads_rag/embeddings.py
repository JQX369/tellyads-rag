"""
OpenAI-compatible embeddings helper with simple batching.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable, List, Sequence

from openai import OpenAI

from .config import get_openai_config

DEFAULT_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    cfg = get_openai_config()
    return OpenAI(api_key=cfg.api_key, base_url=cfg.api_base)


def embed_texts(texts: Sequence[str], batch_size: int = DEFAULT_BATCH_SIZE) -> List[List[float]]:
    """
    Embed a list of texts and return vectors in the same order.
    """
    if not texts:
        return []

    cfg = get_openai_config()
    client = _get_openai_client()
    vectors: List[List[float]] = []

    batch: List[str] = []
    for text in texts:
        batch.append(text)
        if len(batch) >= batch_size:
            # Always request 1536 dimensions to match schema (vector(1536))
            # text-embedding-3-large supports dimensions parameter for size reduction
            response = client.embeddings.create(
                model=cfg.embedding_model_name,
                input=batch,
                dimensions=1536
            )
            vectors.extend([data.embedding for data in response.data])
            batch.clear()

    if batch:
        # Always request 1536 dimensions to match schema (vector(1536))
        response = client.embeddings.create(
            model=cfg.embedding_model_name,
            input=batch,
            dimensions=1536
        )
        vectors.extend([data.embedding for data in response.data])

    return vectors


__all__ = ["embed_texts"]

