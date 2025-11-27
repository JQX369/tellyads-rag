"""
CLI utility for running the retrieval stack against a golden set of analyst queries.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Sequence

from . import retrieval


GoldenSample = Mapping[str, object]
RetrieveFn = Callable[[str], Sequence[Mapping[str, object]]]


def _load_golden_set(path: Path) -> List[GoldenSample]:
    if not path.exists():
        raise FileNotFoundError(f"Golden set file not found: {path}")
    samples: List[GoldenSample] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))
    if not samples:
        raise ValueError(f"Golden set file {path} was empty.")
    return samples


def evaluate_samples(
    samples: Sequence[GoldenSample],
    retrieve: RetrieveFn,
) -> Dict[str, object]:
    """Return per-sample hits plus aggregate accuracy."""
    evaluations: List[Dict[str, object]] = []
    hits = 0
    for sample in samples:
        query = str(sample.get("query"))
        expected_brands = {
            brand.lower()
            for brand in sample.get("expected_brands", [])
            if isinstance(brand, str)
        }
        rows = list(retrieve(query))
        hit_row = next(
            (
                row
                for row in rows
                if expected_brands
                and str(row.get("brand_name") or "").lower() in expected_brands
            ),
            None,
        )
        hit = hit_row is not None
        if hit:
            hits += 1
        evaluations.append(
            {
                "query": query,
                "expected_brands": list(expected_brands),
                "hit": hit,
                "top_brand": rows[0].get("brand_name") if rows else None,
                "matched_brand": hit_row.get("brand_name") if hit_row else None,
            }
        )
    accuracy = hits / len(samples) if samples else 0.0
    return {"accuracy": accuracy, "samples": evaluations}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate hybrid retrieval + rerank pipeline.")
    parser.add_argument(
        "--golden-path",
        default="docs/golden_set.jsonl",
        help="Path to the JSONL file containing golden queries.",
    )
    parser.add_argument("--candidate-k", type=int, default=50, help="Candidates retrieved before reranking.")
    parser.add_argument("--final-k", type=int, default=10, help="Context chunks kept after reranking.")
    parser.add_argument(
        "--item-types",
        nargs="+",
        default=None,
        help="Optional embedding_items.item_type filters.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    samples = _load_golden_set(Path(args.golden_path))

    def _retrieve(query: str):
        return retrieval.retrieve_with_rerank(
            query,
            candidate_k=args.candidate_k,
            final_k=args.final_k,
            item_types=args.item_types,
        )

    report = evaluate_samples(samples, _retrieve)
    print(f"Golden set accuracy: {report['accuracy']:.2%}")
    for sample in report["samples"]:
        status = "✅" if sample["hit"] else "⚠️"
        expected = ", ".join(sample["expected_brands"])
        print(f"{status} {sample['query']}")
        print(f"    Expected brands: {expected or 'n/a'}")
        print(f"    Top brand: {sample['top_brand']}")
        print(f"    Matched brand: {sample['matched_brand']}")


if __name__ == "__main__":
    main()

