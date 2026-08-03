"""Tests for optional semantic reranker backends."""
from __future__ import annotations

import time

from harness.semantic import reranker


def _candidates():
    return [
        {"path": "low.md", "summary": "low", "score": 0.9, "signals": {"raw_cosine": 0.9}},
        {"path": "high.md", "summary": "high", "score": 0.1, "signals": {"raw_cosine": 0.1}},
    ]


def test_mock_reranker_score_drives_order_without_calibrated_confidence():
    config = reranker.RerankerConfig(backend="sentence-transformers", model="mock", top_k=2, timeout_ms=5000, max_chars=1000)
    rows, diagnostics = reranker.rerank_candidates(
        "q",
        _candidates(),
        top_n=2,
        config=config,
        backend_impl=reranker.MockRerankerBackend({"high.md": 3.0, "low.md": -1.0}),
    )

    assert [row["path"] for row in rows] == ["high.md", "low.md"]
    assert rows[0]["reranker_enabled"] is True
    assert rows[0]["reranker_score"] == 3.0
    assert rows[0]["confidence_calibrated"] is False
    assert rows[0]["retrieval_score"] == 0.1
    assert diagnostics["enabled"] is True
    assert diagnostics["fallback_reason"] is None


def test_backend_off_preserves_retrieval_order_and_marks_fallback_reason():
    config = reranker.RerankerConfig(backend="off", model="mock", top_k=2, timeout_ms=5000, max_chars=1000)
    rows, diagnostics = reranker.rerank_candidates("q", _candidates(), top_n=2, config=config)

    assert [row["path"] for row in rows] == ["low.md", "high.md"]
    assert all(row["reranker_enabled"] is False for row in rows)
    assert diagnostics["enabled"] is False
    assert diagnostics["fallback_reason"] == "backend_off"


class _ExplodingBackend:
    name = "exploding"

    def score(self, query, candidates, *, instruction, max_chars):
        raise RuntimeError("boom")


def test_backend_exception_falls_back_without_claiming_success():
    config = reranker.RerankerConfig(backend="sentence-transformers", model="mock", top_k=2, timeout_ms=5000, max_chars=1000)
    rows, diagnostics = reranker.rerank_candidates("q", _candidates(), top_n=2, config=config, backend_impl=_ExplodingBackend())

    assert [row["path"] for row in rows] == ["low.md", "high.md"]
    assert diagnostics["enabled"] is False
    assert "boom" in diagnostics["fallback_reason"]
    assert rows[0]["fallback_reason"] == diagnostics["fallback_reason"]


class _SlowBackend:
    name = "slow"

    def score(self, query, candidates, *, instruction, max_chars):
        time.sleep(0.002)
        return [10.0, 1.0]


def test_backend_timeout_falls_back_without_returning_scored_order():
    config = reranker.RerankerConfig(backend="sentence-transformers", model="mock", top_k=2, timeout_ms=1, max_chars=1000)
    rows, diagnostics = reranker.rerank_candidates("q", _candidates(), top_n=2, config=config, backend_impl=_SlowBackend())

    assert [row["path"] for row in rows] == ["low.md", "high.md"]
    assert diagnostics["enabled"] is False
    assert "timeout_ms_exceeded" in diagnostics["fallback_reason"]


def test_candidate_document_includes_context_and_truncates_text():
    doc = reranker.candidate_document(
        {"path": "p.md", "heading_path": "H", "summary": "S", "why": "W", "chunk_text": "x" * 200},
        max_chars=80,
    )

    assert "Path: p.md" in doc
    assert "Heading: H" in doc
    assert "...[truncated]" in doc
