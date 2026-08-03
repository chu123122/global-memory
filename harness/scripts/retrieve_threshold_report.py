#!/usr/bin/env python
"""retrieve_threshold_report.py — read-only threshold observability for RAG hook logs.

Reads shared retrieve_calls.jsonl records from ~/.global-memory/logs by default.
The report is intentionally advisory: it explains injection/abstain behavior and
suggests observation windows, but never edits production thresholds.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import GLOBAL_MEMORY_LOGS_DIR  # noqa: E402

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCHEMA_VERSION = "retrieve-threshold-report.v1"
DEFAULT_LOG = GLOBAL_MEMORY_LOGS_DIR / "retrieve_calls.jsonl"
DEFAULT_LABELS = GLOBAL_MEMORY_LOGS_DIR / "retrieve_threshold_labels.jsonl"


def parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def load_records(path: Path, *, days: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days) if days else None
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            if cutoff:
                ts = parse_ts(record.get("ts"))
                if ts is not None and ts < cutoff:
                    continue
            records.append(record)
    return records


def query_id(record: dict[str, Any]) -> str:
    existing = record.get("query_id")
    if existing:
        return str(existing)
    seed = "\x1f".join([
        str(record.get("ts") or ""),
        str(record.get("hook_session_id") or record.get("session") or ""),
        str(record.get("query") or ""),
    ])
    return hashlib.sha1(seed.encode("utf-8", errors="replace")).hexdigest()[:16]


def load_labels(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    labels: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            qid = str(record.get("query_id") or "")
            label = str(record.get("label") or record.get("verdict") or "")
            if qid and label in {"useful", "noise", "unclear"}:
                labels[qid] = label
    return labels


def as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        if value is not None and str(value).strip() != "":
            return float(str(value))
    except Exception:
        return None
    return None


def is_injected(record: dict[str, Any]) -> bool:
    decision = str(record.get("decision_reason") or "")
    if decision == "inject":
        return True
    return bool(record.get("hit")) and not bool(record.get("abstained")) and int(record.get("hit_count") or 0) > 0


def abstain_reason(record: dict[str, Any]) -> str:
    if record.get("abstain_reason"):
        return str(record.get("abstain_reason"))
    decision = str(record.get("decision_reason") or "")
    if decision.startswith("abstain:"):
        return decision.removeprefix("abstain:")
    if not is_injected(record):
        return decision or "no_hit"
    return ""


def sample_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": query_id(record),
        "ts": record.get("ts"),
        "query": record.get("query"),
        "decision_reason": record.get("decision_reason") or ("inject" if is_injected(record) else abstain_reason(record)),
        "best_raw_cosine": record.get("best_raw_cosine"),
        "best_reranker_score": record.get("best_reranker_score"),
        "rerank_threshold": record.get("rerank_threshold"),
        "pre_rerank_threshold": record.get("pre_rerank_threshold"),
        "sidecar_status": record.get("sidecar_status"),
        "top_candidate_paths": record.get("top_candidate_paths") or record.get("top_refs") or [],
    }


def boundary_samples(records: list[dict[str, Any]], *, margin: float, limit: int = 20) -> list[dict[str, Any]]:
    samples: list[tuple[float, dict[str, Any]]] = []
    for record in records:
        score = as_float(record.get("best_reranker_score"))
        threshold = as_float(record.get("rerank_threshold"))
        if score is None or threshold is None:
            continue
        distance = abs(score - threshold)
        if distance <= margin:
            samples.append((distance, record))
    samples.sort(key=lambda item: (item[0], str(item[1].get("ts") or "")))
    return [sample_record(record) | {"distance_to_rerank_threshold": round(distance, 6)} for distance, record in samples[:limit]]


def likely_noise_candidates(records: list[dict[str, Any]], labels: dict[str, str], *, margin: float, limit: int = 20) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        if not is_injected(record):
            continue
        qid = query_id(record)
        score = as_float(record.get("best_reranker_score"))
        threshold = as_float(record.get("rerank_threshold"))
        near_boundary = bool(score is not None and threshold is not None and 0 <= score - threshold <= margin)
        labeled_noise = labels.get(qid) == "noise"
        if near_boundary or labeled_noise:
            item = sample_record(record)
            item["label"] = labels.get(qid, "")
            item["reason"] = "labeled_noise" if labeled_noise else "near_rerank_threshold_injected"
            candidates.append(item)
    return candidates[:limit]


def analyze(records: list[dict[str, Any]], labels: dict[str, str], *, margin: float) -> dict[str, Any]:
    total = len(records)
    injected = [record for record in records if is_injected(record)]
    abstained = [record for record in records if not is_injected(record)]
    abstain_counts = Counter(abstain_reason(record) for record in abstained)
    pre_blocked = [record for record in abstained if abstain_reason(record).startswith("pre_rerank")]
    sidecar_counts = Counter(str(record.get("sidecar_status") or "unknown") for record in records)
    labeled_counts = Counter(labels.get(query_id(record), "unlabeled") for record in records)
    scores = [as_float(record.get("best_reranker_score")) for record in records]
    numeric_scores = [score for score in scores if score is not None]
    thresholds = [as_float(record.get("rerank_threshold")) for record in records]
    numeric_thresholds = [value for value in thresholds if value is not None]
    threshold = numeric_thresholds[0] if numeric_thresholds else None
    return {
        "schema_version": SCHEMA_VERSION,
        "total_calls": total,
        "injected_calls": len(injected),
        "injection_rate": round(len(injected) / total, 3) if total else 0.0,
        "abstain_distribution": dict(abstain_counts.most_common()),
        "pre_rerank_blocked_calls": len(pre_blocked),
        "pre_rerank_blocked_rate": round(len(pre_blocked) / total, 3) if total else 0.0,
        "sidecar_status_distribution": dict(sidecar_counts.most_common()),
        "label_distribution": dict(labeled_counts.most_common()),
        "score_observations": {
            "best_reranker_score_count": len(numeric_scores),
            "min": min(numeric_scores) if numeric_scores else None,
            "max": max(numeric_scores) if numeric_scores else None,
            "active_rerank_threshold": threshold,
        },
        "reranker_boundary_samples": boundary_samples(records, margin=margin),
        "borderline_injected_possible_noise": likely_noise_candidates(records, labels, margin=margin),
        "suggestion": {
            "do_not_auto_change_thresholds": True,
            "observation_window": f"rerank_threshold ± {margin}",
            "next_step": "Label sampled query_id rows as useful|noise|unclear, then compare noise/useful counts near the boundary before changing production thresholds.",
        },
    }


def format_report(result: dict[str, Any]) -> str:
    lines = [
        "# Retrieve Threshold Report",
        "",
        f"- 总调用：{result['total_calls']}",
        f"- 注入：{result['injected_calls']} ({result['injection_rate'] * 100:.1f}%)",
        f"- pre-rerank 拦截：{result['pre_rerank_blocked_calls']} ({result['pre_rerank_blocked_rate'] * 100:.1f}%)",
        f"- sidecar 状态：{result['sidecar_status_distribution']}",
        f"- 标注分布：{result['label_distribution']}",
        "",
        "## Abstain 分布",
        "",
    ]
    if not result["abstain_distribution"]:
        lines.append("- 无")
    else:
        for reason, count in result["abstain_distribution"].items():
            lines.append(f"- {count}x `{reason}`")
    lines += ["", "## Reranker 阈值边界样本", ""]
    if not result["reranker_boundary_samples"]:
        lines.append("- 无")
    else:
        for sample in result["reranker_boundary_samples"]:
            lines.append(
                f"- {sample['query_id']} score={sample.get('best_reranker_score')} "
                f"threshold={sample.get('rerank_threshold')} decision={sample.get('decision_reason')} "
                f"query={sample.get('query')!r}"
            )
    lines += ["", "## 踩线注入/疑似噪声候选", ""]
    if not result["borderline_injected_possible_noise"]:
        lines.append("- 无")
    else:
        for sample in result["borderline_injected_possible_noise"]:
            lines.append(
                f"- {sample['query_id']} reason={sample.get('reason')} label={sample.get('label') or '-'} "
                f"score={sample.get('best_reranker_score')} query={sample.get('query')!r}"
            )
    lines += ["", "## 建议", "", f"- {result['suggestion']['next_step']}", "- 本脚本只读，不自动改阈值。", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report RAG hook threshold behavior from retrieve_calls.jsonl")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="retrieve_calls.jsonl path")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS), help="optional JSONL labels: {query_id,label}")
    parser.add_argument("--days", type=int, default=None, help="filter last N days")
    parser.add_argument("--margin", type=float, default=0.5, help="boundary window around rerank threshold")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    records = load_records(Path(args.log), days=args.days)
    labels = load_labels(Path(args.labels) if args.labels else None)
    result = analyze(records, labels, margin=args.margin)
    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
