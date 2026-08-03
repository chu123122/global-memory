"""Tests for Phase 7 reranker preflight/calibration reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

from harness.semantic import phase7_eval


def _fixture(path: Path, cases: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"cases": cases}, ensure_ascii=False), encoding="utf-8")
    return path


def test_preflight_marks_any_reranker_fallback_config_invalid(tmp_path: Path) -> None:
    golden = _fixture(tmp_path / "golden.json", [{"id": "g", "query": "q", "expect_paths": ["good.md"]}])
    negative = _fixture(tmp_path / "negative.json", [{"id": "n", "query": "weather"}])

    def fake_baseline(**_kwargs):
        return {
            "golden": {"caseCount": 1, "Recall@5": 1.0, "Recall@10": 1.0, "MRR": 1.0, "Hit@1": 1.0},
            "negative": {"caseCount": 1, "falsePositiveCount": 0, "falsePositiveRate": 0.0},
        }

    def fake_search_cases(cases, **_kwargs):
        results = {}
        diags = []
        for idx, case in enumerate(cases):
            case_id = str(case.get("id") or idx)
            if case.get("expect_paths"):
                results[case_id] = [{"path": "good.md", "reranker_score": 0.9}]
            else:
                results[case_id] = []
            diags.append({"case_id": case_id, "reranker": {"fallback_reason": "timeout_ms_exceeded:21>20", "latency_ms": 21.0}})
        return results, diags

    with mock.patch("harness.semantic.phase7_eval._baseline", side_effect=fake_baseline), \
        mock.patch("harness.semantic.phase7_eval._search_cases", side_effect=fake_search_cases):
        report = phase7_eval.run_preflight(configs=[(10, 800)], golden_path=golden, negative_path=negative)

    item = report["results"][0]
    assert item["valid"] is False
    assert item["reranker"]["reranker_fallback_count"] == 2
    assert "reranker_fallback_count>0" in item["invalid_reason"]
    assert report["selected_config"] is None


def test_calibration_report_with_fallback_does_not_suggest_thresholds(tmp_path: Path) -> None:
    golden = _fixture(tmp_path / "golden.json", [{"id": "g", "query": "q", "expect_paths": ["good.md"]}])
    negative = _fixture(tmp_path / "negative.json", [{"id": "n", "query": "weather"}])
    hard = _fixture(tmp_path / "hard.json", [{"id": "h", "query": "near miss", "must_not_return": ["bad.md"], "expected_abstain": True}])
    semantic = _fixture(tmp_path / "semantic.json", [{"id": "s", "query": "paraphrase", "expect_paths": ["good.md"]}])

    def fake_search_cases(cases, **_kwargs):
        results = {}
        diags = []
        for idx, case in enumerate(cases):
            case_id = str(case.get("id") or idx)
            if case.get("must_not_return"):
                results[case_id] = [{"path": "bad.md", "reranker_score": 0.7}]
            elif case.get("expect_paths"):
                results[case_id] = [{"path": "good.md", "reranker_score": 0.9}]
            else:
                results[case_id] = []
            diags.append({"case_id": case_id, "reranker": {"fallback_reason": "timeout_ms_exceeded", "latency_ms": 20001.0}})
        return results, diags

    with mock.patch("harness.semantic.phase7_eval._search_cases", side_effect=fake_search_cases):
        report = phase7_eval.run_calibration(
            top_k=10,
            max_chars=800,
            golden_path=golden,
            negative_path=negative,
            hard_negative_path=hard,
            semantic_positive_path=semantic,
        )

    assert report["valid_for_calibration"] is False
    assert report["invalid_reason"] == "reranker_fallback_count>0"
    assert report["suggested_thresholds"]["rerank_threshold"] is None
    assert report["must_not_return_violations"][0]["paths"] == ["bad.md"]


def test_env_for_config_forces_rewrite_off() -> None:
    env = phase7_eval._env_for_config(
        backend="sentence-transformers",
        model="Qwen/Qwen3-Reranker-0.6B",
        top_k=15,
        max_chars=1000,
        timeout_ms=20000,
    )
    assert env["GM_SEARCH_REWRITE"] == "off"
    assert env["GM_SEARCH_RERANK_TOPK"] == "15"
    assert env["GM_SEARCH_RERANK_MAX_CHARS"] == "1000"
