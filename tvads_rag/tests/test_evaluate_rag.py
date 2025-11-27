import pytest

pytest.importorskip("psycopg2")

import tvads_rag.evaluate_rag as evaluate_rag


def test_evaluate_samples_computes_accuracy():
    samples = [
        {"query": "q1", "expected_brands": ["Acme"]},
        {"query": "q2", "expected_brands": ["Bravo"]},
    ]

    def fake_retrieve(query: str):
        if query == "q1":
            return [{"brand_name": "Acme"}]
        return [{"brand_name": "Other"}]

    report = evaluate_rag.evaluate_samples(samples, fake_retrieve)
    assert report["accuracy"] == 0.5
    assert report["samples"][0]["hit"] is True
    assert report["samples"][1]["hit"] is False

