"""Phase 7 reranker preflight and threshold calibration reports.

The module is read-only for production settings: it runs gm.search with query
rewrite forced off, records reranker fallback diagnostics, and prints JSON reports
that can be archived by the caller.  Configurations with any reranker fallback are
marked invalid and must not be used for threshold calibration.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from harness.gm_mcp import search as gm_search
from harness.semantic import eval as semantic_eval
from harness.semantic import reranker
from harness.semantic.index import DEFAULT_INDEX_PATH

DEFAULT_PREFLIGHT_CONFIGS: tuple[tuple[int, int], ...] = (
    (10, 800),
    (15, 1000),
    (20, 1000),
    (30, 2000),
)
DEFAULT_TIMEOUT_MS = 20000
DEFAULT_TOP = 10
DEFAULT_GOLDEN = semantic_eval.FIXTURE_DIR / "golden_expanded_100.json"
DEFAULT_NEGATIVE = semantic_eval.FIXTURE_DIR / "negative_expanded_50.json"
DEFAULT_HARD_NEGATIVE = semantic_eval.FIXTURE_DIR / "hard_negative_qdoc.json"
DEFAULT_SEMANTIC_POSITIVE = semantic_eval.FIXTURE_DIR / "semantic_positives.json"


@contextmanager
def _temporary_env(values: Mapping[str, str]):
    old = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _case_id(case: Mapping[str, object], idx: int) -> str:
    return str(case.get("id") or idx)


def _paths(rows: Sequence[Mapping[str, object]]) -> list[str]:
    return [str(row.get("path") or "") for row in rows if row.get("path")]


def _scores(rows: Iterable[Mapping[str, object]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = row.get("reranker_score")
        if isinstance(value, (int, float)):
            out.append(float(value))
    return out


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: Sequence[float]) -> dict[str, object]:
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None, "p50": None, "p95": None}
    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "avg": round(sum(values) / len(values), 6),
        "p50": round(statistics.median(values), 6),
        "p95": round(_percentile(values, 0.95), 6),
    }


def _hit_at(cases: Sequence[Mapping[str, object]], results_by_id: Mapping[str, Sequence[Mapping[str, object]]], top: int) -> float:
    if not cases:
        return 0.0
    hits = 0
    for idx, case in enumerate(cases):
        expected = {str(path) for path in case.get("expect_paths", []) if str(path)}  # type: ignore[arg-type]
        ranked = _paths(results_by_id.get(_case_id(case, idx), []))[:top]
        if expected.intersection(ranked):
            hits += 1
    return hits / len(cases)


def _metrics(cases: Sequence[Mapping[str, object]], results_by_id: Mapping[str, Sequence[Mapping[str, object]]]) -> dict[str, object]:
    metrics = dict(semantic_eval.evaluate_cases(cases, results_by_id))
    metrics["Hit@1"] = _hit_at(cases, results_by_id, 1)
    return metrics


def _case_limit(cases: list[dict[str, object]], limit: int | None) -> list[dict[str, object]]:
    if limit is None or limit <= 0:
        return cases
    return cases[:limit]


def _load_optional_fixture(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return semantic_eval.load_fixture(path)


def _env_for_config(*, backend: str, model: str, top_k: int, max_chars: int, timeout_ms: int) -> dict[str, str]:
    return {
        "GM_SEARCH_REWRITE": "off",
        "GM_SEARCH_RERANKER": backend,
        "GM_SEARCH_RERANK_MODEL": model,
        "GM_SEARCH_RERANK_TOPK": str(top_k),
        "GM_SEARCH_RERANK_MAX_CHARS": str(max_chars),
        "GM_SEARCH_RERANK_TIMEOUT_MS": str(timeout_ms),
    }


def _search_cases(
    cases: Sequence[Mapping[str, object]],
    *,
    top: int,
    index_path: Path,
) -> tuple[dict[str, list[dict[str, object]]], list[dict[str, Any]]]:
    results: dict[str, list[dict[str, object]]] = {}
    diagnostics: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        case_id = _case_id(case, idx)
        query = str(case.get("query") or "")
        started = time.perf_counter()
        result = gm_search.search(
            query,
            top=top,
            intent_top=3,
            index_path=index_path,
            max_delivered_unique_paths=top,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        pointers = result.get("pointers") if isinstance(result.get("pointers"), list) else []
        results[case_id] = [dict(item) for item in pointers if isinstance(item, dict)]
        diag = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        rerank_diag = diag.get("reranker") if isinstance(diag.get("reranker"), dict) else {}
        deliver_gate = (result.get("debug") or {}).get("deliver_gate") if isinstance(result.get("debug"), dict) else {}
        diagnostics.append({
            "case_id": case_id,
            "query": query,
            "elapsed_ms": round(elapsed_ms, 3),
            "reranker": rerank_diag,
            "abstained": bool(result.get("abstained")),
            "delivered_count": len(results[case_id]),
            "deliver_gate": deliver_gate if isinstance(deliver_gate, dict) else {},
        })
    return results, diagnostics


def _reranker_summary(diags: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    rerank_diags = [diag.get("reranker", {}) for diag in diags]
    fallback_reasons = [str(diag.get("fallback_reason")) for diag in rerank_diags if diag.get("fallback_reason")]
    latencies = [float(diag.get("latency_ms") or 0.0) for diag in rerank_diags]
    return {
        "reranker_fallback_count": len(fallback_reasons),
        "fallback_reasons": sorted(set(fallback_reasons)),
        "latency_ms": {
            "avg": round(sum(latencies) / max(len(latencies), 1), 3),
            "p50": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95": round(_percentile(latencies, 0.95), 3) if latencies else 0.0,
        },
    }


def _score_distribution(
    cases: Sequence[Mapping[str, object]],
    results_by_id: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    matching: list[float] = []
    non_matching: list[float] = []
    for idx, case in enumerate(cases):
        expected = {str(path) for path in case.get("expect_paths", []) if str(path)}  # type: ignore[arg-type]
        for row in results_by_id.get(_case_id(case, idx), []):
            row_scores = _scores([row])
            if not row_scores:
                continue
            if str(row.get("path") or "") in expected:
                matching.extend(row_scores)
            else:
                non_matching.extend(row_scores)
    return {"matching_expected": _distribution(matching), "non_matching": _distribution(non_matching)}


def _must_not_violations(
    cases: Sequence[Mapping[str, object]],
    results_by_id: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    threshold: float | None = None,
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for idx, case in enumerate(cases):
        blocked = {str(path) for path in case.get("must_not_return", []) if str(path)}  # type: ignore[arg-type]
        if not blocked:
            continue
        rows = results_by_id.get(_case_id(case, idx), [])
        if threshold is not None:
            rows = [row for row in rows if isinstance(row.get("reranker_score"), (int, float)) and float(row.get("reranker_score")) >= threshold]
        returned = sorted(blocked.intersection(_paths(rows)))
        if returned:
            violations.append({"case_id": _case_id(case, idx), "query": case.get("query"), "paths": returned})
    return violations


def _filter_results_by_threshold(
    results_by_id: Mapping[str, Sequence[Mapping[str, object]]],
    threshold: float,
) -> dict[str, list[dict[str, object]]]:
    filtered: dict[str, list[dict[str, object]]] = {}
    for case_id, rows in results_by_id.items():
        filtered[case_id] = [
            dict(row) for row in rows
            if isinstance(row.get("reranker_score"), (int, float)) and float(row.get("reranker_score")) >= threshold
        ]
    return filtered


def _abstain_metrics(
    positive_cases: Sequence[Mapping[str, object]],
    positive_results: Mapping[str, Sequence[Mapping[str, object]]],
    negative_cases: Sequence[Mapping[str, object]],
    negative_results: Mapping[str, Sequence[Mapping[str, object]]],
    threshold: float,
) -> dict[str, object]:
    abstained_expected = 0
    abstained_total = 0
    expected_total = len(negative_cases)
    for idx, case in enumerate(positive_cases):
        rows = _filter_results_by_threshold({_case_id(case, idx): positive_results.get(_case_id(case, idx), [])}, threshold)[_case_id(case, idx)]
        if not rows:
            abstained_total += 1
    for idx, case in enumerate(negative_cases):
        rows = _filter_results_by_threshold({_case_id(case, idx): negative_results.get(_case_id(case, idx), [])}, threshold)[_case_id(case, idx)]
        if not rows:
            abstained_total += 1
            abstained_expected += 1
    return {
        "threshold": round(threshold, 6),
        "precision": round(abstained_expected / max(abstained_total, 1), 6),
        "recall": round(abstained_expected / max(expected_total, 1), 6),
        "abstained_total": abstained_total,
        "expected_abstain_total": expected_total,
    }


def _threshold_sweep(
    *,
    golden_cases: Sequence[Mapping[str, object]],
    golden_results: Mapping[str, Sequence[Mapping[str, object]]],
    negative_cases: Sequence[Mapping[str, object]],
    negative_results: Mapping[str, Sequence[Mapping[str, object]]],
    hard_negative_cases: Sequence[Mapping[str, object]],
    hard_negative_results: Mapping[str, Sequence[Mapping[str, object]]],
    semantic_positive_cases: Sequence[Mapping[str, object]],
    semantic_positive_results: Mapping[str, Sequence[Mapping[str, object]]],
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    all_scores = sorted(set(round(score, 6) for rows in list(golden_results.values()) + list(negative_results.values()) + list(hard_negative_results.values()) + list(semantic_positive_results.values()) for score in _scores(rows)))
    if not all_scores:
        return [], None
    probes = sorted(set([min(all_scores)] + all_scores + [max(all_scores) + 1e-6]))
    rows: list[dict[str, object]] = []
    positives = list(golden_cases) + list(semantic_positive_cases)
    positive_results = {**{_case_id(case, idx): golden_results.get(_case_id(case, idx), []) for idx, case in enumerate(golden_cases)}, **{_case_id(case, idx): semantic_positive_results.get(_case_id(case, idx), []) for idx, case in enumerate(semantic_positive_cases)}}
    all_negative_cases = list(negative_cases) + list(hard_negative_cases)
    all_negative_results = {**{_case_id(case, idx): negative_results.get(_case_id(case, idx), []) for idx, case in enumerate(negative_cases)}, **{_case_id(case, idx): hard_negative_results.get(_case_id(case, idx), []) for idx, case in enumerate(hard_negative_cases)}}
    for threshold in probes:
        fg = _filter_results_by_threshold(golden_results, threshold)
        fn = _filter_results_by_threshold(negative_results, threshold)
        fh = _filter_results_by_threshold(hard_negative_results, threshold)
        fs = _filter_results_by_threshold(semantic_positive_results, threshold)
        positive_filtered = {**fg, **fs}
        negative_filtered = {**fn, **fh}
        golden_metrics = _metrics(golden_cases, fg)
        semantic_metrics = _metrics(semantic_positive_cases, fs)
        negative_metrics = semantic_eval.evaluate_negative_cases(negative_cases, fn)
        hard_negative_metrics = semantic_eval.evaluate_negative_cases(hard_negative_cases, fh)
        violations = _must_not_violations(hard_negative_cases, fh, threshold=None)
        abstain = _abstain_metrics(positives, positive_filtered, all_negative_cases, negative_filtered, threshold=threshold)
        rows.append({
            "threshold": round(threshold, 6),
            "golden_Recall@10": golden_metrics["Recall@10"],
            "semantic_positive_Recall@10": semantic_metrics["Recall@10"],
            "negative_FPR": negative_metrics["falsePositiveRate"],
            "hard_negative_FPR": hard_negative_metrics["falsePositiveRate"],
            "must_not_return_violation_count": len(violations),
            "abstain_precision": abstain["precision"],
            "abstain_recall": abstain["recall"],
        })
    rows.sort(key=lambda row: float(row["threshold"]))
    best = sorted(rows, key=lambda row: (
        int(row["must_not_return_violation_count"]),
        float(row["negative_FPR"]),
        float(row["hard_negative_FPR"]),
        -float(row["golden_Recall@10"]),
        -float(row["semantic_positive_Recall@10"]),
        -float(row["abstain_recall"]),
        float(row["threshold"]),
    ))[0]
    return rows, best


def _baseline(
    *,
    golden_cases: Sequence[Mapping[str, object]],
    negative_cases: Sequence[Mapping[str, object]],
    top: int,
    index_path: Path,
) -> dict[str, object]:
    with _temporary_env({"GM_SEARCH_REWRITE": "off", "GM_SEARCH_RERANKER": "off"}):
        golden_results, _ = _search_cases(golden_cases, top=top, index_path=index_path)
        negative_results, _ = _search_cases(negative_cases, top=top, index_path=index_path)
    return {
        "golden": _metrics(golden_cases, golden_results),
        "negative": semantic_eval.evaluate_negative_cases(negative_cases, negative_results),
    }


def run_preflight(
    *,
    configs: Sequence[tuple[int, int]] = DEFAULT_PREFLIGHT_CONFIGS,
    backend: str = reranker.DEFAULT_RERANK_BACKEND,
    model: str = reranker.DEFAULT_RERANK_MODEL,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    top: int = DEFAULT_TOP,
    golden_path: Path = DEFAULT_GOLDEN,
    negative_path: Path = DEFAULT_NEGATIVE,
    index_path: Path = DEFAULT_INDEX_PATH,
    case_limit: int | None = None,
) -> dict[str, object]:
    golden_cases = _case_limit(semantic_eval.load_fixture(golden_path), case_limit)
    negative_cases = _case_limit(semantic_eval.load_fixture(negative_path), case_limit)
    baseline = _baseline(golden_cases=golden_cases, negative_cases=negative_cases, top=top, index_path=index_path)
    baseline_recall10 = float((baseline.get("golden") or {}).get("Recall@10") or 0.0)  # type: ignore[union-attr]
    baseline_fpr = float((baseline.get("negative") or {}).get("falsePositiveRate") or 0.0)  # type: ignore[union-attr]
    results: list[dict[str, object]] = []
    for top_k, max_chars in configs:
        with _temporary_env(_env_for_config(backend=backend, model=model, top_k=top_k, max_chars=max_chars, timeout_ms=timeout_ms)):
            golden_results, golden_diags = _search_cases(golden_cases, top=top, index_path=index_path)
            negative_results, negative_diags = _search_cases(negative_cases, top=top, index_path=index_path)
        summary = _reranker_summary(golden_diags + negative_diags)
        fallback_count = int(summary["reranker_fallback_count"])
        golden_metrics = _metrics(golden_cases, golden_results)
        negative_metrics = semantic_eval.evaluate_negative_cases(negative_cases, negative_results)
        invalid_reasons: list[str] = []
        if fallback_count > 0:
            invalid_reasons.append("reranker_fallback_count>0")
        if float(golden_metrics.get("Recall@10") or 0.0) < max(0.0, baseline_recall10 - 0.05):
            invalid_reasons.append("Recall@10_below_baseline_tolerance_0.05")
        if float(negative_metrics.get("falsePositiveRate") or 0.0) > baseline_fpr:
            invalid_reasons.append("negative_FPR_above_baseline")
        all_rows = [row for rows in list(golden_results.values()) + list(negative_results.values()) for row in rows]
        results.append({
            "config": {"topK": top_k, "max_chars": max_chars, "timeout_ms": timeout_ms, "backend": backend, "model": model},
            "valid": not invalid_reasons,
            "invalid_reason": ";".join(invalid_reasons) if invalid_reasons else None,
            "golden": golden_metrics,
            "negative": negative_metrics,
            "reranker": summary,
            "score_distribution": _distribution(_scores(all_rows)),
        })
    eligible = [item for item in results if item.get("valid")]
    eligible.sort(key=lambda item: (
        -float((item.get("golden") or {}).get("Recall@10") or 0.0),  # type: ignore[union-attr]
        float((item.get("negative") or {}).get("falsePositiveRate") or 0.0),  # type: ignore[union-attr]
        float(((item.get("reranker") or {}).get("latency_ms") or {}).get("p95") or 0.0),  # type: ignore[union-attr]
    ))
    return {
        "schema_version": 1,
        "report": "phase7_reranker_stable_config_preflight",
        "fixtures": {"golden": str(golden_path), "negative": str(negative_path)},
        "case_counts": {"golden": len(golden_cases), "negative": len(negative_cases)},
        "rewrite": {"mode": "off", "reason": "paused_for_phase7_calibration"},
        "selection_criteria": [
            "reranker_fallback_count == 0",
            "Recall@10 >= baseline Recall@10 - 0.05",
            "negative FPR <= baseline negative FPR",
            "lower reranker latency p95 breaks quality ties",
        ],
        "baseline": baseline,
        "results": results,
        "selected_config": eligible[0].get("config") if eligible else None,
    }


def run_calibration(
    *,
    top_k: int,
    max_chars: int,
    backend: str = reranker.DEFAULT_RERANK_BACKEND,
    model: str = reranker.DEFAULT_RERANK_MODEL,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    top: int = DEFAULT_TOP,
    golden_path: Path = DEFAULT_GOLDEN,
    negative_path: Path = DEFAULT_NEGATIVE,
    hard_negative_path: Path = DEFAULT_HARD_NEGATIVE,
    semantic_positive_path: Path = DEFAULT_SEMANTIC_POSITIVE,
    index_path: Path = DEFAULT_INDEX_PATH,
    case_limit: int | None = None,
) -> dict[str, object]:
    golden_cases = _case_limit(semantic_eval.load_fixture(golden_path), case_limit)
    negative_cases = _case_limit(semantic_eval.load_fixture(negative_path), case_limit)
    hard_negative_cases = _case_limit(_load_optional_fixture(hard_negative_path), case_limit)
    semantic_positive_cases = _case_limit(_load_optional_fixture(semantic_positive_path), case_limit)
    config = {"topK": top_k, "max_chars": max_chars, "timeout_ms": timeout_ms, "backend": backend, "model": model}
    with _temporary_env(_env_for_config(backend=backend, model=model, top_k=top_k, max_chars=max_chars, timeout_ms=timeout_ms)):
        golden_results, golden_diags = _search_cases(golden_cases, top=top, index_path=index_path)
        negative_results, negative_diags = _search_cases(negative_cases, top=top, index_path=index_path)
        hard_negative_results, hard_negative_diags = _search_cases(hard_negative_cases, top=top, index_path=index_path)
        semantic_positive_results, semantic_positive_diags = _search_cases(semantic_positive_cases, top=top, index_path=index_path)
    all_diags = golden_diags + negative_diags + hard_negative_diags + semantic_positive_diags
    rerank_summary = _reranker_summary(all_diags)
    fallback_count = int(rerank_summary["reranker_fallback_count"])
    config_valid = fallback_count == 0
    negative_scores = [score for rows in list(negative_results.values()) + list(hard_negative_results.values()) for score in _scores(rows)]
    positive_match_scores: list[float] = []
    for cases, results in ((golden_cases, golden_results), (semantic_positive_cases, semantic_positive_results)):
        for idx, case in enumerate(cases):
            expected = {str(path) for path in case.get("expect_paths", []) if str(path)}  # type: ignore[arg-type]
            positive_match_scores.extend(score for row in results.get(_case_id(case, idx), []) if str(row.get("path") or "") in expected for score in _scores([row]))
    sweep, suggested = _threshold_sweep(
        golden_cases=golden_cases,
        golden_results=golden_results,
        negative_cases=negative_cases,
        negative_results=negative_results,
        hard_negative_cases=hard_negative_cases,
        hard_negative_results=hard_negative_results,
        semantic_positive_cases=semantic_positive_cases,
        semantic_positive_results=semantic_positive_results,
    )
    all_must_not_cases = list(golden_cases) + list(negative_cases) + list(hard_negative_cases) + list(semantic_positive_cases)
    all_must_not_results = {**golden_results, **negative_results, **hard_negative_results, **semantic_positive_results}
    must_not = _must_not_violations(all_must_not_cases, all_must_not_results)
    abstain = _abstain_metrics(
        list(golden_cases) + list(semantic_positive_cases),
        {**golden_results, **semantic_positive_results},
        list(negative_cases) + list(hard_negative_cases),
        {**negative_results, **hard_negative_results},
        threshold=float(suggested["threshold"]) if suggested else float("inf"),
    ) if suggested else {}
    return {
        "schema_version": 1,
        "report": "phase7_threshold_calibration",
        "config": config,
        "valid_for_calibration": config_valid,
        "invalid_reason": None if config_valid else "reranker_fallback_count>0",
        "rewrite": {"mode": "off", "reason": "paused_for_phase7_calibration"},
        "coverage": {
            "golden": {"path": str(golden_path), "case_count": len(golden_cases), "purpose": "curated and expanded exact positive query-doc checks"},
            "negative": {"path": str(negative_path), "case_count": len(negative_cases), "purpose": "out-of-domain abstain/FPR checks"},
            "hard_negative": {"path": str(hard_negative_path), "case_count": len(hard_negative_cases), "purpose": "near-miss and must-not-return regression checks"},
            "semantic_positive": {"path": str(semantic_positive_path), "case_count": len(semantic_positive_cases), "purpose": "paraphrase and cross-language positive checks"},
        },
        "metrics": {
            "golden": _metrics(golden_cases, golden_results),
            "negative": semantic_eval.evaluate_negative_cases(negative_cases, negative_results),
            "hard_negative": semantic_eval.evaluate_negative_cases(hard_negative_cases, hard_negative_results),
            "semantic_positive": _metrics(semantic_positive_cases, semantic_positive_results),
        },
        "score_distribution": {
            "positive_expected_matches": _distribution(positive_match_scores),
            "negative_returned": _distribution(negative_scores),
            "golden": _score_distribution(golden_cases, golden_results),
            "semantic_positive": _score_distribution(semantic_positive_cases, semantic_positive_results),
        },
        "suggested_thresholds": {
            "rerank_threshold": suggested.get("threshold") if suggested and config_valid else None,
            "abstain_threshold": suggested.get("threshold") if suggested and config_valid else None,
            "source": "threshold_sweep_minimize_must_not_then_negative_fpr_then_preserve_recall",
            "not_applied_to_production": True,
        },
        "per_source_penalty_boost_suggestions": [
            {
                "suggestion": "no_auto_change",
                "reason": "Phase 7 report is advisory; source-specific boosts/penalties require a separate implementation diff after reviewing regression cases.",
            }
        ],
        "must_not_return_violations": must_not,
        "abstain_precision_recall": abstain,
        "threshold_sweep": sweep,
        "latency_ms": rerank_summary["latency_ms"],
        "reranker_fallback_count": fallback_count,
        "fallback_reasons": rerank_summary["fallback_reasons"],
    }


def _parse_config(value: str) -> tuple[int, int]:
    if ":" in value:
        left, right = value.split(":", 1)
    elif "/" in value:
        left, right = value.split("/", 1)
    elif "," in value:
        left, right = value.split(",", 1)
    else:
        raise argparse.ArgumentTypeError("config must be topK:max_chars, e.g. 10:800")
    return max(1, int(left)), max(200, int(right))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.semantic.phase7_eval")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--backend", default=reranker.DEFAULT_RERANK_BACKEND)
    common.add_argument("--model", default=reranker.DEFAULT_RERANK_MODEL)
    common.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    common.add_argument("--top", type=int, default=DEFAULT_TOP)
    common.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    common.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    common.add_argument("--negative", type=Path, default=DEFAULT_NEGATIVE)
    common.add_argument("--case-limit", type=int, help="smoke-test only; omit for full report")

    preflight = sub.add_parser("preflight", parents=[common])
    preflight.add_argument("--config", action="append", type=_parse_config, help="topK:max_chars; repeatable")

    calibration = sub.add_parser("calibrate", parents=[common])
    calibration.add_argument("--top-k", type=int, required=True)
    calibration.add_argument("--max-chars", type=int, required=True)
    calibration.add_argument("--hard-negative", type=Path, default=DEFAULT_HARD_NEGATIVE)
    calibration.add_argument("--semantic-positive", type=Path, default=DEFAULT_SEMANTIC_POSITIVE)

    args = parser.parse_args(argv)
    if args.command == "preflight":
        result = run_preflight(
            configs=args.config or DEFAULT_PREFLIGHT_CONFIGS,
            backend=args.backend,
            model=args.model,
            timeout_ms=max(1, args.timeout_ms),
            top=max(1, args.top),
            golden_path=args.golden,
            negative_path=args.negative,
            index_path=args.index,
            case_limit=args.case_limit,
        )
    else:
        result = run_calibration(
            top_k=max(1, args.top_k),
            max_chars=max(200, args.max_chars),
            backend=args.backend,
            model=args.model,
            timeout_ms=max(1, args.timeout_ms),
            top=max(1, args.top),
            golden_path=args.golden,
            negative_path=args.negative,
            hard_negative_path=args.hard_negative,
            semantic_positive_path=args.semantic_positive,
            index_path=args.index,
            case_limit=args.case_limit,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
