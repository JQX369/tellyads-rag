"""
Simple CLI for running pgvector similarity queries against embedding_items.
"""

from __future__ import annotations

import argparse
import json
from typing import List

from .retrieval import retrieve_with_rerank

DEFAULT_ITEM_TYPES = ["transcript_chunk", "segment_summary", "claim"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Similarity search demo over embedding_items.")
    parser.add_argument("--query", required=False, help="Natural language query string.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results to display.")
    parser.add_argument(
        "--item-types",
        nargs="+",
        default=DEFAULT_ITEM_TYPES,
        help="embedding_items.item_type values to include.",
    )
    return parser.parse_args()


def _run_query(query_text: str, top_k: int, item_types: List[str]) -> List[dict]:
    candidate_k = max(top_k * 5, 50)
    return retrieve_with_rerank(
        query_text,
        candidate_k=candidate_k,
        final_k=top_k,
        item_types=item_types,
    )


def _print_results(rows: List[dict]) -> None:
    if not rows:
        print("No results.")
        return

    for idx, row in enumerate(rows, start=1):
        meta = row.get("meta") or {}
        brand = row.get("brand_name") or "Unknown brand"
        product = row.get("product_name") or "Unknown product"
        summary = row.get("one_line_summary")
        print(f"[{idx}] {row['item_type']} • {brand} / {product}")
        if summary:
            print(f"    Summary: {summary}")
        print(f"    Text: {row['text'][:240]}")
        if row.get("rrf_score") is not None:
            print(f"    RRF score: {row['rrf_score']:.4f}")
        if row.get("rerank_score") is not None:
            print(f"    Rerank score: {row['rerank_score']:.4f}")
        if meta:
            trimmed_meta = json.dumps(meta, ensure_ascii=False)
            print(f"    Meta: {trimmed_meta}")
        print("-" * 80)


def main() -> None:
    args = _parse_args()
    query_text = args.query or input("Enter query: ").strip()
    if not query_text:
        raise ValueError("Query text is required.")

    rows = _run_query(query_text, args.top_k, args.item_types)
    _print_results(rows)


if __name__ == "__main__":
    main()

