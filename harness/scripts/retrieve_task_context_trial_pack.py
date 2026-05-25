#!/usr/bin/env python3
"""retrieve_task_context_trial_pack.py — before/after pack for task-scoped fallback.

Read-only. It compares default retrieve with explicit task-context fallback for
human queries in the configured task allowlist. It imports harness_retrieve
directly and does not append retrieve_calls.jsonl.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = Path("D:/global-memory/.meta/experiments/retrieve_task_context_fallback_review.json")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


retrieve_mod = load_module(SCRIPT_DIR / "harness_retrieve.py", "_gm_harness_retrieve_trial_pack")
trace_mod = load_module(SCRIPT_DIR / "retrieve_trace.py", "_gm_retrieve_trace_trial_pack")


def classify_query(query: str) -> str:
    stripped = (query or "").strip()
    if stripped.startswith("<task-notification>"):
        return "automation"
    if stripped.startswith("# Autonomous"):
        return "automation"
    if stripped.startswith("/goal"):
        return "control"
    return "human"


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"config must be object: {path}")
    return data


def allowed_tasks(config: dict[str, Any]) -> list[str]:
    return [str(x) for x in config.get("allowed_tasks", []) if str(x).strip()]


def load_recent_queries(log_path: Path, task: str, limit: int, zero_hit_only: bool) -> list[str]:
    if not log_path.exists():
        return []
    seen: set[str] = set()
    out: list[str] = []
    for line in reversed(log_path.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("task") or "") != task:
            continue
        query = str(row.get("query") or "").strip()
        if not query or classify_query(query) != "human":
            continue
        if zero_hit_only and int(row.get("hit_count") or 0) != 0:
            continue
        if query in seen:
            continue
        seen.add(query)
        out.append(query)
        if len(out) >= limit:
            break
    return list(reversed(out))


def pointers(brief: Any) -> list[dict[str, str]]:
    return [dict(p) for p in brief.relevant_pointers]


def compact_trace(args: argparse.Namespace, task: str, query: str) -> dict[str, Any]:
    trace_args = argparse.Namespace(
        task=task,
        query=query,
        stage=args.stage,
        memory_root=args.memory_root,
        task_root=args.task_root,
        cache=args.cache,
        tags=args.tags,
        top=args.top,
        min_score=args.min_score,
        candidates=args.trace_candidates,
        downrank_config=None,
        task_context_fallback_config=args.config,
    )
    report = trace_mod.build_report(trace_args)
    opt = report.get("opt_in") or {}
    candidates = []
    for row in opt.get("candidates", [])[: args.trace_candidates]:
        candidates.append({
            "rank": row.get("rank"),
            "path": row.get("path"),
            "final_score": row.get("final_score"),
            "raw_score": row.get("raw_score"),
            "passed_min_score": row.get("passed_min_score"),
            "why": row.get("why"),
            "contributions": row.get("contributions", []),
        })
    return {
        "default_hits": report["summary"]["default_hits"],
        "opt_in_hits": report["summary"]["opt_in_hits"],
        "new_hits": report["summary"]["new_hits"],
        "fallback_triggered": report["fallback"]["triggered"],
        "fallback_context_chars": report["fallback"]["context_chars"],
        "fallback_sources": report["fallback"]["context_sources"],
        "brief_bytes_default": report["summary"]["brief_bytes_default"],
        "brief_bytes_opt_in": report["summary"]["brief_bytes_opt_in"],
        "alias_targets": opt.get("alias_targets", []),
        "top_candidates": candidates,
    }


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
    default = retrieve_mod.retrieve(**common, task_level_fallback_enabled=False)
    opt_in = retrieve_mod.retrieve(**common, task_context_fallback_config=Path(args.config))
    default_paths = [p["path"] for p in default.relevant_pointers]
    opt_paths = [p["path"] for p in opt_in.relevant_pointers]
    if not default_paths and opt_paths:
        verdict = "NEW_HIT"
    elif default_paths != opt_paths:
        verdict = "CHANGED"
    else:
        verdict = "UNCHANGED"
    return {
        "task": task,
        "query": query,
        "verdict": verdict,
        "default": {
            "pointers": pointers(default),
            "warnings": default.warnings,
        },
        "opt_in": {
            "pointers": pointers(opt_in),
            "warnings": opt_in.warnings,
        },
        "trace": compact_trace(args, task, query) if args.include_trace else None,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    config = load_config(config_path)
    allowed = allowed_tasks(config)
    task = args.task or (allowed[0] if allowed else "")
    if not task:
        raise ValueError("No task specified and config allowed_tasks is empty.")
    if allowed and task not in allowed:
        raise ValueError(f"Task {task!r} is not in config allowed_tasks: {allowed}")

    queries = [q.strip() for q in args.query if q.strip()]
    if not queries:
        queries = load_recent_queries(Path(args.logs_root) / "retrieve_calls.jsonl", task, args.samples, args.zero_hit_only)
    comparisons = [compare_one(args, task, query) for query in queries]
    new_hits = sum(1 for item in comparisons if item["verdict"] == "NEW_HIT")
    changed = sum(1 for item in comparisons if item["verdict"] in {"NEW_HIT", "CHANGED"})
    still_empty = sum(1 for item in comparisons if not item["opt_in"]["pointers"])
    if not comparisons:
        verdict = "NO_SAMPLE"
        conclusion = "没有可对照的 human query 样本。"
    elif new_hits > 0 and still_empty == 0:
        verdict = "VISIBLE_TASK_SCOPED_TRIAL"
        conclusion = f"task-scoped opt-in 为 {new_hits}/{len(comparisons)} 条样本补出新 pointer，且 opt-in 后无空首屏。"
    elif changed > 0:
        verdict = "MIXED_TASK_SCOPED_TRIAL"
        conclusion = f"task-scoped opt-in 改变 {changed}/{len(comparisons)} 条样本，{still_empty}/{len(comparisons)} 条仍为空。"
    else:
        verdict = "NO_VISIBLE_DELTA"
        conclusion = "task-scoped opt-in 没有产生可见首屏变化。"
    return {
        "schema_version": 1,
        "mode": "read-only-task-context-trial-pack",
        "inputs": {
            "config": str(config_path),
            "task": task,
            "samples": args.samples,
            "zero_hit_only": args.zero_hit_only,
            "top": args.top,
            "min_score": args.min_score,
        },
        "summary": {
            "verdict": verdict,
            "task": task,
            "compared": len(comparisons),
            "new_hits": new_hits,
            "changed": changed,
            "still_empty": still_empty,
            "default_enable_ready": False,
            "conclusion": conclusion,
            "recommended_decision": "Keep task-scoped opt-in only; do not default-enable from this pack.",
        },
        "comparisons": comparisons,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Retrieve Task-Scoped Trial Pack",
        "",
        f"- mode: `{report['mode']}`",
        f"- verdict: `{s['verdict']}`",
        f"- task: `{s['task']}`",
        f"- compared: `{s['compared']}`",
        f"- new_hits: `{s['new_hits']}`",
        f"- changed: `{s['changed']}`",
        f"- still_empty: `{s['still_empty']}`",
        f"- default_enable_ready: `{s['default_enable_ready']}`",
        f"- conclusion: {s['conclusion']}",
        "",
    ]
    for item in report["comparisons"]:
        lines.append(f"## {item['verdict']} — {item['query'][:160]}")
        lines.append("- default:")
        if item["default"]["pointers"]:
            for p in item["default"]["pointers"]:
                lines.append(f"  - `{p['path']}` — {p.get('why', '')}")
        else:
            lines.append("  - []")
        lines.append("- opt-in:")
        if item["opt_in"]["pointers"]:
            for p in item["opt_in"]["pointers"]:
                lines.append(f"  - `{p['path']}` — {p.get('why', '')}")
        else:
            lines.append("  - []")
        if item["opt_in"].get("warnings"):
            lines.append("- opt-in warnings:")
            for w in item["opt_in"]["warnings"]:
                lines.append(f"  - `{w}`")
        trace = item.get("trace")
        if trace:
            lines.append("- trace / 追踪摘要:")
            lines.append(f"  - fallback_context_chars / fallback 注入字符数: `{trace['fallback_context_chars']}`")
            lines.append(f"  - fallback_sources / fallback 上下文来源: `{', '.join(trace['fallback_sources']) or '-'}`")
            lines.append(f"  - brief_bytes: `{trace['brief_bytes_default']}` -> `{trace['brief_bytes_opt_in']}`")
            lines.append(f"  - alias_targets / 命中的别名扩展: `{', '.join(trace['alias_targets']) or '-'}`")
            lines.append("  - top_candidates / 最高候选:")
            for row in trace["top_candidates"]:
                lines.append(
                    f"    - rank {row['rank']} score={row['final_score']} "
                    f"`{row['path']}` — {row.get('why', '')}"
                )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a read-only before/after pack for task-scoped task-context fallback.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--task", default="")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--zero-hit-only", action="store_true")
    parser.add_argument("--logs-root", default=str(Path.home() / ".claude" / "logs"))
    parser.add_argument("--stage", default=None)
    parser.add_argument("--memory-root", default=str(retrieve_mod.DEFAULT_MEMORY_ROOT))
    parser.add_argument("--task-root", default=str(retrieve_mod.DEFAULT_TASK_ROOT))
    parser.add_argument("--cache", default=None)
    parser.add_argument("--tags", default="")
    parser.add_argument("--top", type=int, default=retrieve_mod.MAX_POINTERS)
    parser.add_argument("--min-score", type=float, default=retrieve_mod.MIN_SCORE_DEFAULT)
    parser.add_argument("--include-trace", action="store_true", default=True)
    parser.add_argument("--no-trace", dest="include_trace", action="store_false")
    parser.add_argument("--trace-candidates", type=int, default=3)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
