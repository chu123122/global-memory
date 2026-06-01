#!/usr/bin/env python3
"""self_loop_report.py - one-screen view of the current self-optimization loop."""
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
DEFAULT_TASKS = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(Path.home() / ".claude" / "tasks" / "active")))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fallback_cost = load_module(SCRIPT_DIR / "retrieve_fallback_cost.py", "_gm_fallback_cost_report")
assurance_gate = load_module(SCRIPT_DIR / "assurance_gate.py", "_gm_assurance_report")
fallback_candidates = load_module(SCRIPT_DIR / "retrieve_fallback_candidates.py", "_gm_fallback_candidates_report")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            data = json.loads(line)
        except Exception:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


def enabled_task_configs(tasks_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not tasks_root.exists():
        return out
    for config in sorted(tasks_root.glob("*/core/CONFIG.json")):
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except Exception:
            continue
        retrieve = data.get("retrieve") if isinstance(data, dict) else None
        fallback = retrieve.get("task_context_fallback") if isinstance(retrieve, dict) else None
        enabled = fallback is True or (isinstance(fallback, dict) and fallback.get("enabled") is True)
        if not enabled:
            continue
        task = config.parent.parent.name
        out.append({
            "task": task,
            "config": str(config),
            "context_limit": fallback.get("context_limit", 600) if isinstance(fallback, dict) else 600,
            "source_review": fallback.get("source_review", "") if isinstance(fallback, dict) else "",
            "source_trial": fallback.get("source_trial", "") if isinstance(fallback, dict) else "",
        })
    return out


def assurance_summary(task: str, tasks_root: Path) -> dict[str, Any]:
    task_dir = tasks_root / task
    if not task_dir.exists():
        return {"task": task, "verdict": "NOT_APPLICABLE", "summary": "task not found"}
    result = assurance_gate.task_handoff_ready(task_dir)
    return {
        "task": task,
        "verdict": result.get("verdict"),
        "summary": result.get("summary"),
        "evidence": result.get("evidence", [])[:5],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_root)
    tasks = Path(args.tasks_root)
    ledger = load_jsonl(repo / ".meta" / "optimizations" / "optimizations.jsonl")
    cost = fallback_cost.build_report(argparse.Namespace(logs_root=args.logs_root, days=args.days, samples=args.samples))
    candidate_report = fallback_candidates.build_report(argparse.Namespace(
        logs_root=args.logs_root,
        repo_root=args.repo_root,
        task_root=args.tasks_root,
        memory_root=args.repo_root,
        cache=None,
        days=args.days,
        min_zero_hits=args.min_zero_hits,
        min_short_followup_rate=args.min_short_followup_rate,
        samples_per_task=args.candidate_samples,
        trace_candidates=2,
        context_limit=600,
        stage=None,
        tags="",
        top=2,
        min_score=1.0,
        write_review_artifacts=False,
        artifact_prefix="TCF",
        accept_task="",
        force_accept=False,
    ))
    enabled = enabled_task_configs(tasks)
    assurance = [assurance_summary(task["task"], tasks) for task in enabled]
    return {
        "schema_version": 1,
        "mode": "self-loop-overview",
        "inputs": {
            "repo_root": str(repo),
            "tasks_root": str(tasks),
            "logs_root": args.logs_root,
            "days": args.days,
        },
        "enabled_task_fallbacks": enabled,
        "optimization_ledger": {
            "count": len(ledger),
            "latest": ledger[-5:],
        },
        "fallback_cost": cost,
        "fallback_candidates": candidate_report,
        "assurance": assurance,
    }


def render_markdown(report: dict[str, Any]) -> str:
    cost = report["fallback_cost"]["summary"]
    lines = [
        "# Self-Loop Overview / 自循环总览",
        "",
        "## Current State / 当前状态",
        "",
        f"- enabled_task_fallbacks / 已启用任务级 fallback: `{len(report['enabled_task_fallbacks'])}`",
        f"- optimization_ledger_count / 优化记录数: `{report['optimization_ledger']['count']}`",
        f"- fallback_triggered_7d / 7天 fallback 触发: `{cost['fallback_triggered']}`",
        f"- avg_context_chars / 平均注入字符数: `{cost['avg_context_chars']}`",
        f"- avg_hit_count_after_fallback / fallback 后平均命中数: `{cost['avg_hit_count_after_fallback']}`",
        f"- fallback_candidates / fallback 候选任务: `{report['fallback_candidates']['summary']['candidate_tasks']}`",
        f"- candidate_accept_review_reject / 接受-评审-拒绝: "
        f"`{report['fallback_candidates']['summary']['accept']}-"
        f"{report['fallback_candidates']['summary']['review']}-"
        f"{report['fallback_candidates']['summary']['reject']}`",
        "",
        "## Enabled Tasks / 已启用任务",
    ]
    if not report["enabled_task_fallbacks"]:
        lines.append("- none / 无")
    for row in report["enabled_task_fallbacks"]:
        lines.append(f"- `{row['task']}` context_limit={row['context_limit']}")
        lines.append(f"  - config: `{row['config']}`")
        if row.get("source_review"):
            lines.append(f"  - review: `{row['source_review']}`")
        if row.get("source_trial"):
            lines.append(f"  - trial: `{row['source_trial']}`")

    lines += ["", "## Assurance / 完成门禁"]
    if not report["assurance"]:
        lines.append("- none / 无")
    for row in report["assurance"]:
        lines.append(f"- `{row['task']}` verdict={row['verdict']} — {row['summary']}")
        for evidence in row.get("evidence", []):
            lines.append(f"  - {evidence}")

    lines += ["", "## Latest Optimizations / 最近优化记录"]
    if not report["optimization_ledger"]["latest"]:
        lines.append("- none / 无")
    for row in report["optimization_ledger"]["latest"]:
        lines.append(
            f"- `{row.get('optimization_id')}` status={row.get('status')} "
            f"scope={row.get('scope')} default_enable={row.get('default_enable')}"
        )
        if row.get("rollback"):
            lines.append(f"  - rollback: {row['rollback']}")

    lines += ["", "## Candidate Preview / 候选预览"]
    preview = report["fallback_candidates"].get("candidates", [])[:5]
    if not preview:
        lines.append("- none / 无")
    for candidate in preview:
        cs = candidate["summary"]
        lines.append(
            f"- `{cs['task']}` recommendation={cs['recommendation']} risk={cs['risk']} "
            f"new_hits={cs['new_hits']}/{cs['compared']} generic={cs['generic_pointer_rate']}"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a one-screen self-loop overview.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO))
    parser.add_argument("--tasks-root", default=str(DEFAULT_TASKS))
    parser.add_argument("--logs-root", default=str(Path.home() / ".claude" / "logs"))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--min-zero-hits", type=int, default=5)
    parser.add_argument("--min-short-followup-rate", type=float, default=0.5)
    parser.add_argument("--candidate-samples", type=int, default=3)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--json", action="store_true", help="Alias for --format json.")
    args = parser.parse_args()
    if args.json:
        args.format = "json"

    report = build_report(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
