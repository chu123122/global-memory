from __future__ import annotations

import json
from pathlib import Path

from harness.scripts import retrieve_threshold_report


def test_threshold_report_reads_old_and_new_logs(tmp_path):
    log = tmp_path / "retrieve_calls.jsonl"
    log.write_text(
        "\n".join([
            json.dumps({"ts": "2026-06-25T10:00:00", "query": "old", "hit_count": 0, "hit": False}, ensure_ascii=False),
            json.dumps({
                "ts": "2026-06-25T10:01:00",
                "query_id": "qid-new",
                "query": "new",
                "hit_count": 1,
                "hit": True,
                "abstained": False,
                "decision_reason": "inject",
                "best_reranker_score": 4.7,
                "rerank_threshold": 4.625,
                "top_candidate_paths": ["rules/接入索引.md"],
                "sidecar_status": "ready",
            }, ensure_ascii=False),
            json.dumps({
                "ts": "2026-06-25T10:02:00",
                "query": "blocked",
                "hit_count": 0,
                "hit": False,
                "abstained": True,
                "abstain_reason": "pre_rerank_raw_cosine_below_threshold:0.5<0.622",
                "best_raw_cosine": 0.5,
                "pre_rerank_threshold": 0.622,
                "sidecar_status": "ready",
            }, ensure_ascii=False),
        ]) + "\n",
        encoding="utf-8",
    )

    records = retrieve_threshold_report.load_records(log)
    result = retrieve_threshold_report.analyze(records, labels={}, margin=0.5)

    assert result["total_calls"] == 3
    assert result["injected_calls"] == 1
    assert result["pre_rerank_blocked_calls"] == 1
    assert result["abstain_distribution"]["pre_rerank_raw_cosine_below_threshold:0.5<0.622"] == 1
    assert result["reranker_boundary_samples"][0]["query_id"] == "qid-new"


def test_threshold_report_labels_noise_candidates(tmp_path):
    log = tmp_path / "retrieve_calls.jsonl"
    labels = tmp_path / "labels.jsonl"
    record = {
        "ts": "2026-06-25T10:01:00",
        "query_id": "qid-noise",
        "query": "near boundary",
        "hit_count": 1,
        "hit": True,
        "abstained": False,
        "decision_reason": "inject",
        "best_reranker_score": 4.63,
        "rerank_threshold": 4.625,
    }
    log.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    labels.write_text(json.dumps({"query_id": "qid-noise", "label": "noise"}) + "\n", encoding="utf-8")

    result = retrieve_threshold_report.analyze(
        retrieve_threshold_report.load_records(log),
        retrieve_threshold_report.load_labels(labels),
        margin=0.1,
    )

    assert result["label_distribution"]["noise"] == 1
    assert result["borderline_injected_possible_noise"][0]["query_id"] == "qid-noise"
    assert result["suggestion"]["do_not_auto_change_thresholds"] is True
