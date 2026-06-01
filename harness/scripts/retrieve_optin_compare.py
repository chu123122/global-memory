#!/usr/bin/env python3
"""retrieve_optin_compare.py — side-by-side default vs opt-in retrieve output.

Read-only. This is a user-visible trial helper for judging whether an opt-in
retrieve experiment feels better before enabling anything globally.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2])))
DEFAULT_CONFIG = DEFAULT_REPO / ".meta" / "experiments" / "retrieve_downrank_0_5.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


retrieve_mod = load_module(SCRIPT_DIR / "harness_retrieve.py", "_gm_harness_retrieve_compare")


def pointers(brief: Any) -> list[dict[str, str]]:
    return [dict(p) for p in brief.relevant_pointers]


def compare_one(args: argparse.Namespace, task: str, query: str) -> dict[str, Any]:
    common = {
        "task_name": task,
        "user_msg": query,
        "stage": args.stage,
        "memory_root": Path(args.memory_root),
        "task_root": Path(args.task_root),
        "cache_path": Path(args.cache) if args.cache else retrieve_mod._cache_path_for(Path(args.memory_root)),
        "task_tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "top_n": args.top,
        "min_score": args.min_score,
    }
    baseline = retrieve_mod.retrieve(**common)
    optin = retrieve_mod.retrieve(**common, downrank_config=Path(args.downrank_config))
    base_paths = [p["path"] for p in baseline.relevant_pointers]
    opt_paths = [p["path"] for p in optin.relevant_pointers]
    return {
        "task": task,
        "query": query,
        "query_type": classify_query(query),
        "verdict": "CHANGED" if base_paths != opt_paths else "UNCHANGED",
        "baseline": {
            "pointers": pointers(baseline),
            "warnings": baseline.warnings,
        },
        "opt_in": {
            "pointers": pointers(optin),
            "warnings": optin.warnings,
        },
    }


def classify_query(query: str) -> str:
    stripped = (query or "").strip()
    if stripped.startswith("<task-notification>"):
        return "automation"
    if stripped.startswith("# Autonomous"):
        return "automation"
    if stripped.startswith("/goal"):
        return "control"
    return "human"


def load_recent_queries(log_path: Path, limit: int, human_only: bool = False) -> list[tuple[str, str]]:
    if not log_path.exists():
        return []
    seen: set[tuple[str, str]] = set()
    rows: list[tuple[str, str]] = []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except Exception:
            continue
        task = str(row.get("task") or "")
        query = str(row.get("query") or "")
        if not task or not query.strip():
            continue
        if human_only and classify_query(query) != "human":
            continue
        key = (task, query)
        if key in seen:
            continue
        seen.add(key)
        rows.append(key)
        if len(rows) >= limit:
            break
    return list(reversed(rows))


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    if args.recent:
        query_pairs = load_recent_queries(Path(args.logs_root) / "retrieve_calls.jsonl", args.recent, args.human_only)
    else:
        query_pairs = [(args.task, args.query)]
    comparisons = [compare_one(args, task, query) for task, query in query_pairs]
    changed = sum(1 for item in comparisons if item["verdict"] == "CHANGED")
    by_type: dict[str, int] = {}
    for item in comparisons:
        by_type[item["query_type"]] = by_type.get(item["query_type"], 0) + 1
    return {
        "schema_version": 1,
        "mode": "read-only-opt-in-compare",
        "inputs": {
            "downrank_config": args.downrank_config,
            "top": args.top,
            "recent": args.recent,
            "human_only": args.human_only,
        },
        "summary": {
            "compared": len(comparisons),
            "changed": changed,
            "unchanged": len(comparisons) - changed,
            "by_query_type": by_type,
        },
        "external_assessment": assess_user_visible_effect(comparisons),
        "comparisons": comparisons,
    }


def assess_user_visible_effect(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    compared = len(comparisons)
    changed = sum(1 for item in comparisons if item["verdict"] == "CHANGED")
    both_empty = sum(
        1
        for item in comparisons
        if not item["baseline"].get("pointers") and not item["opt_in"].get("pointers")
    )
    changed_rate = changed / compared if compared else 0.0
    both_empty_rate = both_empty / compared if compared else 0.0

    if not compared:
        verdict = "NO_SAMPLE"
        conclusion = "没有可比较的真实 query 样本，不能判断用户体感。"
        recommended_decision = "先收集 human query 样本，不启用实验。"
    elif both_empty_rate >= 0.5:
        verdict = "LIMITED_BY_ZERO_HIT"
        conclusion = (
            f"外显收益有限：{changed}/{compared} 条 human query 改变首屏，"
            f"{both_empty}/{compared} 条优化前后都没有 memory pointer。"
        )
        recommended_decision = "保持 opt-in；下一步优先修 zero-hit，而不是继续调 downrank。"
    elif changed_rate < 0.5:
        verdict = "WEAK_VISIBLE_DELTA"
        conclusion = (
            f"外显变化偏弱：{changed}/{compared} 条 human query 改变首屏，"
            "不足以证明默认启用会明显改善体验。"
        )
        recommended_decision = "保持 opt-in，只在相关任务局部试用。"
    else:
        verdict = "VISIBLE_DELTA_REVIEWABLE"
        conclusion = (
            f"外显变化可评审：{changed}/{compared} 条 human query 改变首屏，"
            f"{both_empty}/{compared} 条仍然 zero-hit。"
        )
        recommended_decision = "进入人工评审；仍需确认 changed 样本是否确实更好。"

    return {
        "verdict": verdict,
        "compared": compared,
        "changed": changed,
        "unchanged": compared - changed,
        "both_empty": both_empty,
        "changed_rate": round(changed_rate, 4),
        "both_empty_rate": round(both_empty_rate, 4),
        "conclusion": conclusion,
        "recommended_decision": recommended_decision,
        "default_enable_ready": verdict == "VISIBLE_DELTA_REVIEWABLE" and both_empty == 0,
    }


def render_markdown(report: dict[str, Any]) -> str:
    assessment = report.get("external_assessment", {})
    lines = [
        "# Retrieve Opt-In Compare",
        "",
        f"- mode: `{report['mode']}`",
        f"- compared: `{report['summary']['compared']}`",
        f"- changed: `{report['summary']['changed']}`",
        f"- unchanged: `{report['summary']['unchanged']}`",
        f"- by_query_type: `{report['summary']['by_query_type']}`",
        f"- external_verdict: `{assessment.get('verdict', 'UNKNOWN')}`",
        f"- conclusion: {assessment.get('conclusion', '')}",
        f"- recommended_decision: {assessment.get('recommended_decision', '')}",
        "",
    ]
    for item in report["comparisons"]:
        lines.append(f"## {item['task']} — {item['verdict']} — {item['query_type']}")
        lines.append(f"- query: `{item['query'][:160]}`")
        lines.append("- default:")
        for p in item["baseline"]["pointers"]:
            lines.append(f"  - `{p['path']}` — {p.get('why', '')}")
        if not item["baseline"]["pointers"]:
            lines.append("  - []")
        lines.append("- opt-in:")
        for p in item["opt_in"]["pointers"]:
            lines.append(f"  - `{p['path']}` — {p.get('why', '')}")
        if not item["opt_in"]["pointers"]:
            lines.append("  - []")
        opt_warnings = item["opt_in"].get("warnings") or []
        if opt_warnings:
            lines.append("- opt-in warnings:")
            for w in opt_warnings:
                lines.append(f"  - `{w}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare default retrieve output with an explicit opt-in experiment config.")
    parser.add_argument("--task", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--recent", type=int, default=0, help="compare last N unique retrieve queries instead of --task/--query")
    parser.add_argument("--human-only", action="store_true", help="with --recent, skip task notifications and autonomous control prompts")
    parser.add_argument("--logs-root", default=str(Path.home() / ".claude" / "logs"))
    parser.add_argument("--downrank-config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--stage", default=None)
    parser.add_argument("--memory-root", default=str(retrieve_mod.DEFAULT_MEMORY_ROOT))
    parser.add_argument("--task-root", default=str(retrieve_mod.DEFAULT_TASK_ROOT))
    parser.add_argument("--cache", default=None)
    parser.add_argument("--tags", default="")
    parser.add_argument("--top", type=int, default=retrieve_mod.MAX_POINTERS)
    parser.add_argument("--min-score", type=float, default=retrieve_mod.MIN_SCORE_DEFAULT)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    if not args.recent and (not args.task or not args.query):
        parser.error("--task and --query are required unless --recent is used")
    report = build_report(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
