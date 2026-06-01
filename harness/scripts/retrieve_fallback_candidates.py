#!/usr/bin/env python3
"""retrieve_fallback_candidates.py - find task-context fallback candidates.

Read-only by default. It uses recent retrieve zero-hit logs, simulates
task-context expansion per task, adds compact scoring traces, and recommends
ACCEPT / REVIEW / REJECT. It does not enable fallback unless --accept-task is
explicitly provided.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import harness_retrieve as retrieve_mod  # type: ignore
import retrieve_zero_hit_analysis as zero_hit_mod  # type: ignore

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_REPO = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2])))
DEFAULT_TASKS = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(Path.home() / ".claude" / "tasks" / "active")))
DEFAULT_LOGS = Path.home() / ".claude" / "logs"


def pointer_paths(brief: Any) -> list[str]:
    return [str(p.get("path") or "") for p in brief.relevant_pointers]


def pointers(brief: Any) -> list[dict[str, str]]:
    return [dict(p) for p in brief.relevant_pointers]


def load_rejected_tasks(repo_root: Path) -> set[str]:
    rejected: set[str] = set()
    for path in sorted((repo_root / ".meta" / "evaluations").glob("EV-*-task-context-relevance-review.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("rejected", []) or []:
            task = str(item.get("task") or "").strip() if isinstance(item, dict) else ""
            if task:
                rejected.add(task)
    return rejected


def load_accepted_tasks(repo_root: Path) -> set[str]:
    accepted: set[str] = set()
    for path in sorted((repo_root / ".meta" / "evaluations").glob("EV-*-task-context-relevance-review.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("accepted", []) or []:
            task = str(item.get("task") or "").strip() if isinstance(item, dict) else ""
            if task:
                accepted.add(task)
    return accepted


def task_config_enabled(tasks_root: Path, task: str) -> bool:
    try:
        enabled, _, _ = retrieve_mod.load_task_level_fallback_config(tasks_root, task)
        return enabled
    except Exception:
        return False


def load_candidate_rows(args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    rows = zero_hit_mod.load_rows(Path(args.logs_root) / "retrieve_calls.jsonl", args.days)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in reversed(rows):
        task = str(row.get("task") or "").strip()
        query = str(row.get("query") or "").strip()
        if not task or not query:
            continue
        if zero_hit_mod.classify_query(query) != "human":
            continue
        if int(row.get("hit_count") or 0) != 0:
            continue
        key = (task, query)
        if key in seen:
            continue
        seen.add(key)
        grouped[task].append(row)
    return {task: list(reversed(items)) for task, items in grouped.items()}


def score_query(
    args: argparse.Namespace,
    task: str,
    query: str,
) -> dict[str, Any]:
    memory_root = Path(args.memory_root)
    task_root = Path(args.task_root)
    cache_path = Path(args.cache) if args.cache else retrieve_mod._cache_path_for(memory_root)
    common = {
        "task_name": task,
        "stage": args.stage,
        "memory_root": memory_root,
        "task_root": task_root,
        "cache_path": cache_path,
        "task_tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "top_n": args.top,
        "min_score": args.min_score,
        "task_level_fallback_enabled": False,
    }
    baseline = retrieve_mod.retrieve(**common, user_msg=query)
    expanded_query, context_chars, sources = retrieve_mod.build_task_context_query(
        query,
        task,
        task_root,
        context_limit=args.context_limit,
    )
    expanded = retrieve_mod.retrieve(**common, user_msg=expanded_query)
    base_paths = pointer_paths(baseline)
    expanded_paths = pointer_paths(expanded)
    verdict = "NEW_HIT" if not base_paths and expanded_paths else ("CHANGED" if base_paths != expanded_paths else "UNCHANGED")
    return {
        "task": task,
        "query": query,
        "shape": "short_followup" if zero_hit_mod.is_short_followup(query) else "task_specific",
        "verdict": verdict,
        "context_chars": context_chars,
        "context_sources": sources,
        "default": {
            "pointers": pointers(baseline),
            "warnings": baseline.warnings,
        },
        "expanded": {
            "pointers": pointers(expanded),
            "warnings": expanded.warnings,
        },
        "trace": compact_trace(args, task, expanded_query),
    }


def compact_trace(args: argparse.Namespace, task: str, expanded_query: str) -> list[dict[str, Any]]:
    memory_root = Path(args.memory_root)
    cache_path = Path(args.cache) if args.cache else retrieve_mod._cache_path_for(memory_root)
    entries = retrieve_mod.load_trigger_cache(cache_path, memory_root)
    expanded_with_alias, _ = retrieve_mod.expand_query(expanded_query, retrieve_mod.load_aliases())
    rows = []
    for entry in entries:
        row = retrieve_mod.score_entry_trace(entry, expanded_with_alias, args.stage, [t.strip() for t in args.tags.split(",") if t.strip()])
        score = float(row["final_score"])
        if score < args.min_score and not row.get("contributions"):
            continue
        row["final_score"] = round(score, 4)
        row["passed_min_score"] = score >= args.min_score
        rows.append(row)
    rows.sort(key=lambda r: float(r["final_score"]), reverse=True)
    out = []
    for idx, row in enumerate(rows[: args.trace_candidates], start=1):
        out.append({
            "rank": idx,
            "path": row.get("path", ""),
            "final_score": row.get("final_score", 0),
            "passed_min_score": row.get("passed_min_score", False),
            "why": row.get("why", ""),
            "contributions": row.get("contributions", []),
        })
    return out


def path_family(path: str) -> str:
    text = path.replace("\\", "/")
    parts = [p for p in text.split("/") if p]
    for family in ("fixes", "decisions", "knowledge", "feedback", "docs"):
        if family in parts:
            return family
    return "other"


def assess_task(
    task: str,
    zero_rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    *,
    rejected_tasks: set[str],
    accepted_tasks: set[str],
    enabled: bool,
) -> dict[str, Any]:
    compared = len(comparisons)
    new_hits = sum(1 for c in comparisons if c["verdict"] == "NEW_HIT")
    changed = sum(1 for c in comparisons if c["verdict"] in {"NEW_HIT", "CHANGED"})
    still_empty = sum(1 for c in comparisons if not c["expanded"]["pointers"])
    short_followups = [r for r in zero_rows if zero_hit_mod.is_short_followup(str(r.get("query") or ""))]
    all_paths: list[str] = []
    top1_paths: list[str] = []
    for comp in comparisons:
        paths = [p["path"] for p in comp["expanded"]["pointers"]]
        all_paths.extend(paths)
        if paths:
            top1_paths.append(paths[0])
    family_counts = Counter(path_family(p) for p in all_paths)
    concrete = family_counts["fixes"] + family_counts["decisions"]
    generic = family_counts["feedback"] + family_counts["docs"]
    new_hit_rate = new_hits / compared if compared else 0.0
    still_empty_rate = still_empty / compared if compared else 1.0
    concrete_rate = concrete / len(all_paths) if all_paths else 0.0
    generic_rate = generic / len(all_paths) if all_paths else 0.0
    stable_top1 = len(set(top1_paths)) <= 3 if top1_paths else False

    reasons: list[str] = []
    if task in rejected_tasks:
        recommendation = "REJECT"
        risk = "HIGH"
        reasons.append("previous_relevance_review_rejected")
    elif enabled:
        recommendation = "ALREADY_ENABLED"
        risk = "LOW" if concrete_rate >= 0.5 else "MEDIUM"
        reasons.append("task_level_config_already_enabled")
    elif compared == 0:
        recommendation = "REJECT"
        risk = "HIGH"
        reasons.append("no_samples")
    elif new_hit_rate >= 0.7 and still_empty == 0 and concrete_rate >= 0.6 and stable_top1 and generic_rate <= 0.35:
        recommendation = "ACCEPT"
        risk = "LOW"
        reasons.append("strong_new_hits_with_concrete_stable_pointers")
    elif new_hit_rate >= 0.5 and still_empty_rate <= 0.3 and generic_rate <= 0.5:
        recommendation = "REVIEW"
        risk = "MEDIUM"
        reasons.append("promising_but_needs_human_review")
    else:
        recommendation = "REJECT"
        risk = "HIGH" if generic_rate > 0.5 or still_empty_rate > 0.3 else "MEDIUM"
        reasons.append("weak_or_risky_simulation")
    if task in accepted_tasks:
        reasons.append("previous_relevance_review_accepted")

    return {
        "task": task,
        "recommendation": recommendation,
        "risk": risk,
        "reason_codes": reasons,
        "zero_hit": len(zero_rows),
        "short_followup_zero_hit": len(short_followups),
        "short_followup_rate": round(len(short_followups) / len(zero_rows), 4) if zero_rows else 0.0,
        "compared": compared,
        "new_hits": new_hits,
        "changed": changed,
        "still_empty": still_empty,
        "new_hit_rate": round(new_hit_rate, 4),
        "still_empty_rate": round(still_empty_rate, 4),
        "family_counts": dict(family_counts),
        "concrete_pointer_rate": round(concrete_rate, 4),
        "generic_pointer_rate": round(generic_rate, 4),
        "top1_paths": [{"path": path, "count": count} for path, count in Counter(top1_paths).most_common(5)],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    grouped = load_candidate_rows(args)
    rejected_tasks = load_rejected_tasks(Path(args.repo_root))
    accepted_tasks = load_accepted_tasks(Path(args.repo_root))
    candidates = []
    for task, rows in sorted(grouped.items(), key=lambda kv: len(kv[1]), reverse=True):
        short_count = sum(1 for r in rows if zero_hit_mod.is_short_followup(str(r.get("query") or "")))
        short_rate = short_count / len(rows) if rows else 0.0
        if len(rows) < args.min_zero_hits and task not in rejected_tasks:
            continue
        if short_rate < args.min_short_followup_rate and task not in rejected_tasks:
            continue
        selected = rows[-args.samples_per_task :]
        comparisons = [score_query(args, task, str(row.get("query") or "")) for row in selected]
        enabled = task_config_enabled(Path(args.task_root), task)
        assessment = assess_task(
            task,
            rows,
            comparisons,
            rejected_tasks=rejected_tasks,
            accepted_tasks=accepted_tasks,
            enabled=enabled,
        )
        candidates.append({
            "summary": assessment,
            "samples": [
                {
                    "query": c["query"],
                    "shape": c["shape"],
                    "verdict": c["verdict"],
                    "context_chars": c["context_chars"],
                    "context_sources": c["context_sources"],
                    "default_paths": [p["path"] for p in c["default"]["pointers"]],
                    "expanded_paths": [p["path"] for p in c["expanded"]["pointers"]],
                    "trace": c["trace"],
                }
                for c in comparisons
            ],
        })

    order = {"ACCEPT": 0, "ALREADY_ENABLED": 1, "REVIEW": 2, "REJECT": 3}
    candidates.sort(key=lambda c: (order.get(c["summary"]["recommendation"], 9), -c["summary"]["zero_hit"]))
    report = {
        "schema_version": 1,
        "mode": "read-only-task-context-fallback-candidates",
        "inputs": {
            "logs_root": args.logs_root,
            "repo_root": args.repo_root,
            "task_root": args.task_root,
            "days": args.days,
            "min_zero_hits": args.min_zero_hits,
            "min_short_followup_rate": args.min_short_followup_rate,
            "samples_per_task": args.samples_per_task,
            "context_limit": args.context_limit,
        },
        "summary": {
            "candidate_tasks": len(candidates),
            "accept": sum(1 for c in candidates if c["summary"]["recommendation"] == "ACCEPT"),
            "already_enabled": sum(1 for c in candidates if c["summary"]["recommendation"] == "ALREADY_ENABLED"),
            "review": sum(1 for c in candidates if c["summary"]["recommendation"] == "REVIEW"),
            "reject": sum(1 for c in candidates if c["summary"]["recommendation"] == "REJECT"),
        },
        "candidates": candidates,
    }
    if args.write_review_artifacts:
        write_artifacts(report, Path(args.repo_root), args.artifact_prefix)
    if args.accept_task:
        accept_task(report, args)
    return report


def safe_slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in text).strip("-") or "task"


def write_artifacts(report: dict[str, Any], repo_root: Path, prefix: str) -> None:
    out_dir = repo_root / ".meta" / "candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    for candidate in report["candidates"]:
        task = candidate["summary"]["task"]
        slug = safe_slug(task)
        payload = {
            "schema_version": report["schema_version"],
            "mode": report["mode"],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "inputs": report["inputs"],
            "candidate": candidate,
        }
        json_path = out_dir / f"{prefix}-{stamp}-{slug}.json"
        md_path = out_dir / f"{prefix}-{stamp}-{slug}.md"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(render_candidate_markdown(payload), encoding="utf-8")


def accept_task(report: dict[str, Any], args: argparse.Namespace) -> None:
    matches = [c for c in report["candidates"] if c["summary"]["task"] == args.accept_task]
    if not matches:
        raise SystemExit(f"accept-task failed: no candidate found for {args.accept_task}")
    candidate = matches[0]
    rec = candidate["summary"]["recommendation"]
    if rec not in {"ACCEPT", "ALREADY_ENABLED"} and not args.force_accept:
        raise SystemExit(f"accept-task refused: recommendation is {rec}; use --force-accept only after manual review")
    task_dir = Path(args.task_root) / args.accept_task / "core"
    task_dir.mkdir(parents=True, exist_ok=True)
    config_path = task_dir / "CONFIG.json"
    config = {
        "schema_version": 1,
        "retrieve": {
            "task_context_fallback": {
                "enabled": True,
                "context_limit": args.context_limit,
                "source_candidate": str(Path(args.repo_root) / ".meta" / "candidates"),
                "accepted_at": datetime.now().strftime("%Y-%m-%d"),
                "reason": "; ".join(candidate["summary"]["reason_codes"]),
            }
        }
    }
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    write_optimization_ledger(candidate, args, config_path)


def write_optimization_ledger(candidate: dict[str, Any], args: argparse.Namespace, config_path: Path) -> None:
    repo_root = Path(args.repo_root)
    out_dir = repo_root / ".meta" / "optimizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    task = candidate["summary"]["task"]
    stamp = datetime.now().strftime("%Y-%m-%d")
    opt_id = f"OPT-{stamp}-task-context-fallback-{safe_slug(task)}"
    source_candidate = str(repo_root / ".meta" / "candidates")
    record = {
        "optimization_id": opt_id,
        "status": "applied",
        "scope": "task-scoped",
        "default_enable": False,
        "applied_at": stamp,
        "source_candidate": source_candidate,
        "changed_files": [str(config_path)],
        "rollback": f"Set retrieve.task_context_fallback.enabled=false or remove {config_path}.",
        "notes": f"Accepted via retrieve_fallback_candidates.py recommendation={candidate['summary']['recommendation']}.",
    }
    ledger_path = out_dir / "optimizations.jsonl"
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    md_path = out_dir / f"{opt_id}.md"
    md_path.write_text(
        "\n".join([
            "---",
            f"optimization_id: {opt_id}",
            "status: applied",
            "scope: task-scoped",
            "default_enable: false",
            "---",
            "",
            f"# Optimization: Task-Context Fallback For {task}",
            "",
            "## Decision",
            "",
            f"Enable task-context fallback for `{task}` via task-local config.",
            "",
            "## Evidence",
            "",
            f"- recommendation: `{candidate['summary']['recommendation']}`",
            f"- risk: `{candidate['summary']['risk']}`",
            f"- new_hits: `{candidate['summary']['new_hits']}/{candidate['summary']['compared']}`",
            f"- concrete_pointer_rate: `{candidate['summary']['concrete_pointer_rate']}`",
            f"- generic_pointer_rate: `{candidate['summary']['generic_pointer_rate']}`",
            f"- source_candidate: `{source_candidate}`",
            "",
            "## Rollback",
            "",
            record["rollback"],
            "",
        ]),
        encoding="utf-8",
    )


def render_candidate_markdown(payload: dict[str, Any]) -> str:
    c = payload["candidate"]
    s = c["summary"]
    lines = [
        f"# Task-Context Fallback Candidate: {s['task']}",
        "",
        f"- recommendation / 建议: `{s['recommendation']}`",
        f"- risk / 风险: `{s['risk']}`",
        f"- zero_hit / 空召回: `{s['zero_hit']}`",
        f"- short_followup_rate / 短追问比例: `{s['short_followup_rate']}`",
        f"- new_hits / 新命中: `{s['new_hits']}/{s['compared']}`",
        f"- still_empty / 仍为空: `{s['still_empty']}`",
        f"- concrete_pointer_rate / 具体指针比例: `{s['concrete_pointer_rate']}`",
        f"- generic_pointer_rate / 泛指针比例: `{s['generic_pointer_rate']}`",
        f"- reason_codes / 原因: `{', '.join(s['reason_codes'])}`",
        "",
        "## Samples / 样本",
        "",
    ]
    for sample in c["samples"]:
        lines.append(f"### {sample['verdict']} - {sample['query'][:120]}")
        lines.append(f"- shape / 形态: `{sample['shape']}`")
        lines.append(f"- context_chars / 注入字符数: `{sample['context_chars']}`")
        lines.append(f"- default_paths / 默认路径: `{', '.join(sample['default_paths']) or '-'}`")
        lines.append(f"- expanded_paths / fallback 路径: `{', '.join(sample['expanded_paths']) or '-'}`")
        lines.append("- trace_top / 最高候选:")
        for row in sample["trace"][:3]:
            lines.append(f"  - rank {row['rank']} score={row['final_score']} `{row['path']}` - {row.get('why', '')}")
        lines.append("")
    return "\n".join(lines)


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Task-Context Fallback Candidates / 任务上下文 fallback 候选",
        "",
        f"- candidate_tasks / 候选任务数: `{s['candidate_tasks']}`",
        f"- accept / 建议接受: `{s['accept']}`",
        f"- already_enabled / 已启用: `{s['already_enabled']}`",
        f"- review / 需人工评审: `{s['review']}`",
        f"- reject / 建议拒绝: `{s['reject']}`",
        "",
    ]
    for label in ("ACCEPT", "ALREADY_ENABLED", "REVIEW", "REJECT"):
        rows = [c for c in report["candidates"] if c["summary"]["recommendation"] == label]
        if not rows:
            continue
        lines += [f"## {label}", ""]
        for candidate in rows:
            cs = candidate["summary"]
            lines.append(
                f"- `{cs['task']}` risk={cs['risk']} zero_hit={cs['zero_hit']} "
                f"short={cs['short_followup_zero_hit']} new_hits={cs['new_hits']}/{cs['compared']} "
                f"concrete={cs['concrete_pointer_rate']} generic={cs['generic_pointer_rate']}"
            )
            lines.append(f"  - reason: `{', '.join(cs['reason_codes'])}`")
            if cs["top1_paths"]:
                lines.append("  - top1:")
                for row in cs["top1_paths"][:3]:
                    lines.append(f"    - `{row['path']}` x{row['count']}")
            sample = candidate["samples"][0] if candidate["samples"] else None
            if sample:
                lines.append(f"  - sample: `{sample['query'][:120]}` -> `{', '.join(sample['expanded_paths']) or '-'}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Find task-context fallback candidates from retrieve zero-hit logs.")
    parser.add_argument("--logs-root", default=str(DEFAULT_LOGS))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO))
    parser.add_argument("--task-root", default=str(DEFAULT_TASKS))
    parser.add_argument("--memory-root", default=str(retrieve_mod.DEFAULT_MEMORY_ROOT))
    parser.add_argument("--cache", default=None)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--min-zero-hits", type=int, default=5)
    parser.add_argument("--min-short-followup-rate", type=float, default=0.5)
    parser.add_argument("--samples-per-task", type=int, default=5)
    parser.add_argument("--trace-candidates", type=int, default=3)
    parser.add_argument("--context-limit", type=int, default=600)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--tags", default="")
    parser.add_argument("--top", type=int, default=retrieve_mod.MAX_POINTERS)
    parser.add_argument("--min-score", type=float, default=retrieve_mod.MIN_SCORE_DEFAULT)
    parser.add_argument("--write-review-artifacts", action="store_true")
    parser.add_argument("--artifact-prefix", default="TCF")
    parser.add_argument("--accept-task", default="")
    parser.add_argument("--force-accept", action="store_true")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
