"""Read-only bakeoff for gm.search query rewrite models.

The script compares rewrite models by running gm.search over existing
golden/negative fixtures.  It does not pull models, change thresholds, or write
memories/indexes.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from harness.gm_mcp import search as gm_search
from harness.semantic import eval as semantic_eval
from harness.semantic import rewrite
from harness.semantic.index import DEFAULT_INDEX_PATH

DEFAULT_OLLAMA_MODELS = ["qwen3:4b", "qwen2.5:7b", "phi4-mini"]
DEFAULT_DEEPSEEK_MODELS = ["deepseek-v4-flash"]


def _list_ollama_models(*, timeout_ms: int) -> dict[str, Any]:
    request = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=max(timeout_ms / 1000.0, 0.001)) as response:  # nosec B310 - loopback constant URL only
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"available": False, "error": str(exc), "models": []}
    models = []
    for item in payload.get("models", []) if isinstance(payload, dict) else []:
        if isinstance(item, dict) and item.get("name"):
            models.append(str(item.get("name")))
    return {"available": True, "error": None, "models": sorted(models)}


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


def _case_id(case: Mapping[str, object], idx: int) -> str:
    return str(case.get("id") or idx)


def _paths(rows: Sequence[Mapping[str, object]]) -> list[str]:
    return [str(row.get("path") or "") for row in rows if row.get("path")]


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


def _case_hit(case: Mapping[str, object], rows: Sequence[Mapping[str, object]], *, top: int = 10) -> bool:
    expected = {str(path) for path in case.get("expect_paths", []) if str(path)}  # type: ignore[arg-type]
    if not expected:
        return False
    return bool(expected.intersection(_paths(rows)[:top]))


def _false_positive(rows: Sequence[Mapping[str, object]]) -> bool:
    return bool(_paths(rows))


def _query_count_distribution(counts: Iterable[int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for count in counts:
        key = str(count)
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda item: int(item[0])))


def _search_cases(cases: Sequence[Mapping[str, object]], *, top: int) -> tuple[dict[str, list[dict[str, object]]], list[dict[str, Any]]]:
    results: dict[str, list[dict[str, object]]] = {}
    diagnostics: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        case_id = _case_id(case, idx)
        query = str(case.get("query") or "")
        started = time.perf_counter()
        result = gm_search.search(query, top=top, intent_top=3, index_path=DEFAULT_INDEX_PATH, max_delivered_unique_paths=top)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        pointers = result.get("pointers") if isinstance(result.get("pointers"), list) else []
        results[case_id] = [dict(item) for item in pointers if isinstance(item, dict)]
        diag = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        rewrite_diag = diag.get("rewrite") if isinstance(diag.get("rewrite"), dict) else {}
        diagnostics.append({
            "case_id": case_id,
            "query": query,
            "elapsed_ms": round(elapsed_ms, 3),
            "rewrite": rewrite_diag,
        })
    return results, diagnostics


def _metrics_for(
    *,
    backend: str,
    model: str,
    golden_cases: Sequence[Mapping[str, object]],
    negative_cases: Sequence[Mapping[str, object]],
    baseline_golden_results: Mapping[str, Sequence[Mapping[str, object]]],
    baseline_negative_results: Mapping[str, Sequence[Mapping[str, object]]],
    top: int,
    timeout_ms: int,
) -> dict[str, Any]:
    with _temporary_env({
        "GM_SEARCH_REWRITE": backend,
        "GM_SEARCH_REWRITE_MODEL": model,
        "GM_SEARCH_REWRITE_TIMEOUT_MS": str(timeout_ms),
    }):
        golden_results, golden_diags = _search_cases(golden_cases, top=top)
        negative_results, negative_diags = _search_cases(negative_cases, top=top)
    all_diags = golden_diags + negative_diags
    rewrite_diags = [diag.get("rewrite", {}) for diag in all_diags]
    fallback_count = sum(1 for diag in rewrite_diags if diag.get("fallback_reason"))
    valid_count = sum(1 for diag in rewrite_diags if diag.get("enabled") and not diag.get("fallback_reason"))
    latencies = [float(diag.get("latency_ms") or 0.0) for diag in rewrite_diags]
    query_counts = [int(diag.get("query_count") or 0) for diag in rewrite_diags]
    golden_metrics = semantic_eval.evaluate_cases(golden_cases, golden_results)
    golden_metrics["Hit@1"] = _hit_at(golden_cases, golden_results, 1)
    negative_metrics = semantic_eval.evaluate_negative_cases(negative_cases, negative_results)

    baseline_g6 = False
    model_g6 = False
    baseline_n4_fp = False
    model_n4_fp = False
    for idx, case in enumerate(golden_cases):
        if _case_id(case, idx) == "g6":
            baseline_g6 = _case_hit(case, baseline_golden_results.get("g6", []), top=top)
            model_g6 = _case_hit(case, golden_results.get("g6", []), top=top)
    for idx, case in enumerate(negative_cases):
        if _case_id(case, idx) == "n4":
            baseline_n4_fp = _false_positive(baseline_negative_results.get("n4", []))
            model_n4_fp = _false_positive(negative_results.get("n4", []))

    return {
        "model": model,
        "json_valid_rate": valid_count / max(len(rewrite_diags), 1),
        "fallback_count": fallback_count,
        "rewrite_latency_ms": {
            "avg": round(sum(latencies) / max(len(latencies), 1), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
        },
        "query_count_distribution": _query_count_distribution(query_counts),
        "golden": golden_metrics,
        "negative": negative_metrics,
        "g6_improved": (not baseline_g6) and model_g6,
        "g6_hit": model_g6,
        "n4_worsened": (not baseline_n4_fp) and model_n4_fp,
        "n4_false_positive": model_n4_fp,
        "diagnostics": all_diags,
    }


def _select_winner(results: Sequence[Mapping[str, Any]], *, baseline_fpr: float, timeout_ms: int, model_preference: Sequence[str]) -> str | None:
    eligible = [
        result for result in results
        if float(result.get("json_valid_rate") or 0.0) > 0.0
        and float((result.get("negative") or {}).get("falsePositiveRate") or 0.0) <= baseline_fpr
        and float((result.get("rewrite_latency_ms") or {}).get("p95") or 0.0) <= timeout_ms
        and not bool(result.get("n4_worsened"))
    ]
    if not eligible:
        return None
    preference = {model: idx for idx, model in enumerate(model_preference)}
    eligible.sort(key=lambda result: (
        -float(result.get("json_valid_rate") or 0.0),
        -int(bool(result.get("g6_improved"))),
        -float((result.get("golden") or {}).get("Recall@10") or 0.0),
        -float((result.get("golden") or {}).get("MRR") or 0.0),
        float((result.get("rewrite_latency_ms") or {}).get("p95") or 0.0),
        preference.get(str(result.get("model") or ""), 999),
    ))
    return str(eligible[0].get("model") or "")


def _model_inventory(backend: str, *, timeout_ms: int) -> dict[str, Any]:
    if backend == "ollama-json":
        return _list_ollama_models(timeout_ms=timeout_ms)
    if backend == "deepseek-json":
        return {
            "available": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "error": None if os.environ.get("DEEPSEEK_API_KEY") else "DEEPSEEK_API_KEY missing",
            "models": [],
        }
    return {"available": False, "error": f"unsupported backend: {backend}", "models": []}


def run_bakeoff(
    *,
    models: Sequence[str],
    backend: str = "ollama-json",
    top: int = 10,
    timeout_ms: int = rewrite.DEFAULT_REWRITE_TIMEOUT_MS,
    golden_path: Path | None = None,
    negative_path: Path | None = None,
) -> dict[str, Any]:
    golden_path = golden_path or (semantic_eval.FIXTURE_DIR / "golden.json")
    negative_path = negative_path or (semantic_eval.FIXTURE_DIR / "negative.json")
    golden_cases = semantic_eval.load_fixture(golden_path)
    negative_cases = semantic_eval.load_fixture(negative_path)
    with _temporary_env({"GM_SEARCH_REWRITE": "off"}):
        baseline_golden_results, _baseline_golden_diags = _search_cases(golden_cases, top=top)
        baseline_negative_results, _baseline_negative_diags = _search_cases(negative_cases, top=top)
    baseline_golden = semantic_eval.evaluate_cases(golden_cases, baseline_golden_results)
    baseline_golden["Hit@1"] = _hit_at(golden_cases, baseline_golden_results, 1)
    baseline_negative = semantic_eval.evaluate_negative_cases(negative_cases, baseline_negative_results)
    model_inventory = _model_inventory(backend, timeout_ms=timeout_ms)
    installed_models = set(model_inventory.get("models") or [])
    results = []
    for model in models:
        metrics = _metrics_for(
            backend=backend,
            model=model,
            golden_cases=golden_cases,
            negative_cases=negative_cases,
            baseline_golden_results=baseline_golden_results,
            baseline_negative_results=baseline_negative_results,
            top=top,
            timeout_ms=timeout_ms,
        )
        metrics["model_available"] = (model in installed_models) if backend == "ollama-json" else bool(model_inventory.get("available"))
        results.append(metrics)
    winner = _select_winner(results, baseline_fpr=float(baseline_negative.get("falsePositiveRate") or 0.0), timeout_ms=timeout_ms, model_preference=models)
    return {
        "backend": backend,
        "models": list(models),
        "model_inventory": model_inventory,
        "fixtures": {"golden": str(golden_path), "negative": str(negative_path)},
        "default_rewrite_mode": "off",
        "winner": winner,
        "winner_rule": [
            "highest_json_valid_rate",
            "negative_false_positive_rate_must_not_increase",
            "prefer_g6_improvement",
            f"rewrite_p95_at_or_below_{timeout_ms}ms",
            "prefer_smaller_faster_model_when_quality_is_close",
        ],
        "baseline": {"golden": baseline_golden, "negative": baseline_negative},
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.semantic.rewrite_bakeoff")
    parser.add_argument("--backend", choices=["ollama-json", "deepseek-json"], default="ollama-json")
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--timeout-ms", type=int, default=rewrite.DEFAULT_REWRITE_TIMEOUT_MS)
    parser.add_argument("--golden", type=Path, help="custom golden fixture path")
    parser.add_argument("--negative", type=Path, help="custom negative fixture path")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    models = args.models or (DEFAULT_DEEPSEEK_MODELS if args.backend == "deepseek-json" else DEFAULT_OLLAMA_MODELS)
    result = run_bakeoff(
        models=models,
        backend=args.backend,
        top=max(1, args.top),
        timeout_ms=max(1, args.timeout_ms),
        golden_path=args.golden,
        negative_path=args.negative,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"winner: {result['winner'] or 'none'}")
        for item in result["results"]:
            print(
                f"{item['model']}: valid={item['json_valid_rate']:.2f} "
                f"fallback={item['fallback_count']} "
                f"p95={item['rewrite_latency_ms']['p95']}ms "
                f"R@10={item['golden']['Recall@10']:.2f} "
                f"negFPR={item['negative']['falsePositiveRate']:.2f} "
                f"g6_hit={item['g6_hit']} n4_fp={item['n4_false_positive']}"
            )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
