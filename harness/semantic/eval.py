"""Evaluation metrics and fixture runner for semantic retrieval."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping, Sequence

from harness.semantic.index import DEFAULT_INDEX_PATH
from harness.semantic.calibration import accepted_rows, annotate_rows, calibrate_from_results, default_acceptance_config
from harness.semantic.query import EPSILON, acceptance_policy_dict

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _paths(rows: Sequence[Mapping[str, object]]) -> list[str]:
    return [str(row.get("path") or "") for row in rows if row.get("path")]


def evaluate_cases(
    cases: Sequence[Mapping[str, object]],
    results_by_id: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, float | int]:
    total = len(cases)
    if total == 0:
        return {"caseCount": 0, "Recall@5": 0.0, "Recall@10": 0.0, "MRR": 0.0, "Hit@1": 0.0}
    recall5 = 0
    recall10 = 0
    hit1 = 0
    reciprocal_sum = 0.0
    for idx, case in enumerate(cases):
        case_id = str(case.get("id") or idx)
        expected = {str(p) for p in case.get("expect_paths", []) if str(p)}  # type: ignore[arg-type]
        ranked_paths = _paths(results_by_id.get(case_id, []))
        if expected.intersection(ranked_paths[:1]):
            hit1 += 1
        if expected.intersection(ranked_paths[:5]):
            recall5 += 1
        if expected.intersection(ranked_paths[:10]):
            recall10 += 1
        for rank, path in enumerate(ranked_paths, start=1):
            if path in expected:
                reciprocal_sum += 1.0 / rank
                break
    return {
        "caseCount": total,
        "Recall@5": recall5 / total,
        "Recall@10": recall10 / total,
        "MRR": reciprocal_sum / total,
        "Hit@1": hit1 / total,
    }


def evaluate_negative_cases(
    cases: Sequence[Mapping[str, object]],
    results_by_id: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, float | int]:
    total = len(cases)
    if total == 0:
        return {"caseCount": 0, "falsePositiveCount": 0, "falsePositiveRate": 0.0}
    false_positive = 0
    for idx, case in enumerate(cases):
        case_id = str(case.get("id") or idx)
        if _paths(results_by_id.get(case_id, [])):
            false_positive += 1
    return {
        "caseCount": total,
        "falsePositiveCount": false_positive,
        "falsePositiveRate": false_positive / total,
    }


def load_fixture(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError(f"Fixture cases must be a list: {path}")
    return [case for case in cases if isinstance(case, dict)]


def _baseline_paths(query: str, *, top: int, memory_root: Path) -> list[str]:
    script = memory_root / "harness" / "scripts" / "harness_retrieve.py"
    if not script.exists():
        return []
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--task",
            "semantic-eval",
            "--query",
            query,
            "--top",
            str(top),
            "--min-score",
            "0.3",
            "--memory-root",
            str(memory_root),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("- path:"):
            paths.append(stripped.partition(":")[2].strip())
    return paths


def _baseline_metrics(cases: Sequence[Mapping[str, object]], *, memory_root: Path) -> dict[str, object]:
    scoped = [case for case in cases if case.get("baseline_scope") != "out_of_baseline_scope"]
    out_of_scope = [str(case.get("id") or idx) for idx, case in enumerate(cases) if case.get("baseline_scope") == "out_of_baseline_scope"]
    results = {
        str(case.get("id") or idx): [{"path": path} for path in _baseline_paths(str(case.get("query") or ""), top=10, memory_root=memory_root)]
        for idx, case in enumerate(scoped)
    }
    metrics = evaluate_cases(scoped, results)
    return {**metrics, "outOfBaselineScope": out_of_scope}


def run_eval(
    *,
    index_path: Path = DEFAULT_INDEX_PATH,
    fixture: Path | None = None,
    golden_path: Path | None = None,
    negative_path: Path | None = None,
    query_fn: Callable[[str, int], list[dict[str, object]]] | None = None,
    with_baseline: bool = False,
    memory_root: Path | None = None,
    save_policy: bool = False,
) -> dict[str, object]:
    from harness.semantic.engine import query_index

    if fixture is not None:
        golden_path = fixture
    golden_path = golden_path or (FIXTURE_DIR / "golden.json")
    negative_path = negative_path or (FIXTURE_DIR / "negative.json")
    golden_cases = load_fixture(golden_path) if golden_path.exists() else []
    negative_cases = load_fixture(negative_path) if negative_path.exists() else []
    if query_fn is not None:
        golden_results = {str(case.get("id") or idx): query_fn(str(case.get("query") or ""), 10) for idx, case in enumerate(golden_cases)}
        negative_results = {str(case.get("id") or idx): query_fn(str(case.get("query") or ""), 10) for idx, case in enumerate(negative_cases)}
        policy = {"source": "provided_query_fn"}
        details: dict[str, object] = {}
    else:
        golden_raw = {str(case.get("id") or idx): query_index(str(case.get("query") or ""), index_path=index_path, top_n=50, debug=True) for idx, case in enumerate(golden_cases)}
        negative_raw = {str(case.get("id") or idx): query_index(str(case.get("query") or ""), index_path=index_path, top_n=50, debug=True) for idx, case in enumerate(negative_cases)}
        calibrated = calibrate_from_results(golden_cases, golden_raw, negative_cases, negative_raw)
        config = calibrated.config
        golden_results = {str(case.get("id") or idx): accepted_rows(golden_raw.get(str(case.get("id") or idx), []), config)[:10] for idx, case in enumerate(golden_cases)}
        negative_results = {str(case.get("id") or idx): accepted_rows(negative_raw.get(str(case.get("id") or idx), []), config)[:10] for idx, case in enumerate(negative_cases)}
        policy = calibrated.policy
        if save_policy:
            from harness.semantic.index import save_acceptance_policy

            save_acceptance_policy(index_path, policy)
        details = {
            "golden": golden_raw,
            "negative": {case_id: annotate_rows(rows, config) for case_id, rows in negative_raw.items()},
        }
    negative_detail = {}
    for idx, case in enumerate(negative_cases):
        case_id = str(case.get("id") or idx)
        negative_detail[case_id] = {
            "accepted": negative_results.get(case_id, []),
            "raw": details.get("negative", {}).get(case_id, []) if isinstance(details.get("negative", {}), dict) else [],
        }
    out: dict[str, object] = {
        "authority_epsilon": EPSILON,
        "acceptedPointerOnly": True,
        "acceptancePolicy": policy,
        "golden": evaluate_cases(golden_cases, golden_results),
        "negative": evaluate_negative_cases(negative_cases, negative_results),
        "details": {"negative": negative_detail},
    }
    if with_baseline:
        from harness.config import MEMORY_ROOT

        out["baseline"] = _baseline_metrics(golden_cases, memory_root=memory_root or MEMORY_ROOT)
    return out


