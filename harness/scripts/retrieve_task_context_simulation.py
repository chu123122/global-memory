#!/usr/bin/env python3
"""retrieve_task_context_simulation.py — simulate task-context fallback for zero-hit queries.

Read-only. It compares normal literal-query retrieve with a task-context-expanded
query for recent human zero-hit samples. It does not call the CLI entrypoint and
therefore does not append retrieve_calls.jsonl.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


retrieve_mod = load_module(SCRIPT_DIR / "harness_retrieve.py", "_gm_harness_retrieve_task_context_sim")
zero_hit_mod = load_module(SCRIPT_DIR / "retrieve_zero_hit_analysis.py", "_gm_zero_hit_analysis_sim")


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def read_first_useful(path: Path, limit: int) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---" or re.match(r"^[\w_-]+:\s*", stripped):
            continue
        lines.append(stripped)
        if len(collapse_ws(" ".join(lines))) >= limit:
            break
    return collapse_ws(" ".join(lines))[:limit]


def task_context(task_root: Path, task: str, limit: int) -> str:
    task_dir = task_root / task
    parts = [f"task:{task}"]
    for rel in ("core/HANDOFF.md", "HANDOFF.md", "core/STATUS.md", "STATUS.md"):
        snippet = read_first_useful(task_dir / rel, limit)
        if snippet:
            parts.append(f"{rel}:{snippet}")
        if len(collapse_ws(" ".join(parts))) >= limit:
            break
    return collapse_ws(" ".join(parts))[:limit]


def expand_query(query: str, task: str, task_root: Path, context_limit: int) -> str:
    context = task_context(task_root, task, context_limit)
    if not context:
        return query
    return f"{query}\n\n[task_context]\n{context}"


def pointer_paths(brief: Any) -> list[str]:
    return [str(p.get("path") or "") for p in brief.relevant_pointers]


def pointers(brief: Any) -> list[dict[str, str]]:
    return [dict(p) for p in brief.relevant_pointers]


def load_zero_hit_samples(args: argparse.Namespace) -> list[dict[str, str]]:
    rows = zero_hit_mod.load_rows(Path(args.logs_root) / "retrieve_calls.jsonl", args.days)
    samples: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in reversed(rows):
        query = str(row.get("query") or "")
        task = str(row.get("task") or "")
        if not task or not query.strip():
            continue
        if zero_hit_mod.classify_query(query) != "human":
            continue
        if int(row.get("hit_count") or 0) != 0:
            continue
        key = (task, query)
        if key in seen:
            continue
        seen.add(key)
        samples.append({
            "task": task,
            "query": query,
            "shape": "short_followup" if zero_hit_mod.is_short_followup(query) else "task_specific",
        })
        if len(samples) >= args.samples:
            break
    return list(reversed(samples))


def compare_one(args: argparse.Namespace, sample: dict[str, str]) -> dict[str, Any]:
    task = sample["task"]
    query = sample["query"]
    common = {
        "task_name": task,
        "stage": args.stage,
        "memory_root": Path(args.memory_root),
        "task_root": Path(args.task_root),
        "cache_path": Path(args.cache) if args.cache else retrieve_mod._cache_path_for(Path(args.memory_root)),
        "task_tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "top_n": args.top,
        "min_score": args.min_score,
    }
    baseline = retrieve_mod.retrieve(**common, user_msg=query)
    expanded_query = expand_query(query, task, Path(args.task_root), args.context_limit)
    expanded = retrieve_mod.retrieve(**common, user_msg=expanded_query)
    base_paths = pointer_paths(baseline)
    expanded_paths = pointer_paths(expanded)
    return {
        **sample,
        "verdict": "NEW_HIT" if not base_paths and expanded_paths else ("CHANGED" if base_paths != expanded_paths else "UNCHANGED"),
        "context_chars": len(expanded_query) - len(query),
        "baseline": {
            "pointers": pointers(baseline),
            "warnings": baseline.warnings,
        },
        "expanded": {
            "pointers": pointers(expanded),
            "warnings": expanded.warnings,
        },
    }


def assess(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    compared = len(comparisons)
    new_hits = sum(1 for item in comparisons if item["verdict"] == "NEW_HIT")
    changed = sum(1 for item in comparisons if item["verdict"] in {"NEW_HIT", "CHANGED"})
    still_empty = sum(1 for item in comparisons if not item["expanded"].get("pointers"))
    new_hit_rate = new_hits / compared if compared else 0.0
    if not compared:
        verdict = "NO_SAMPLE"
        conclusion = "没有可模拟的 human zero-hit 样本。"
        recommended = "继续收集日志，不启用 fallback。"
    elif new_hit_rate >= 0.5 and still_empty == 0:
        verdict = "STRONG_VISIBLE_DELTA"
        conclusion = f"task-context expansion 为 {new_hits}/{compared} 条 zero-hit query 带来新 pointer，且无 still-empty。"
        recommended = "进入人工评审；下一步仍需判断新 pointer 是否相关。"
    elif new_hit_rate >= 0.3:
        verdict = "PROMISING_BUT_NEEDS_REVIEW"
        conclusion = f"task-context expansion 为 {new_hits}/{compared} 条 zero-hit query 带来新 pointer，{still_empty}/{compared} 仍为空。"
        recommended = "保留为 proposal 证据；人工看 changed 样本是否真的更贴近任务。"
    else:
        verdict = "WEAK_VISIBLE_DELTA"
        conclusion = f"task-context expansion 只为 {new_hits}/{compared} 条 zero-hit query 带来新 pointer，外显收益不足。"
        recommended = "不要实现 fallback；改查 aliases/frontmatter 或任务文档缺口。"
    return {
        "verdict": verdict,
        "compared": compared,
        "new_hits": new_hits,
        "changed": changed,
        "still_empty": still_empty,
        "new_hit_rate": round(new_hit_rate, 4),
        "conclusion": conclusion,
        "recommended_decision": recommended,
        "default_enable_ready": False,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    samples = load_zero_hit_samples(args)
    comparisons = [compare_one(args, sample) for sample in samples]
    return {
        "schema_version": 1,
        "mode": "read-only-task-context-simulation",
        "inputs": {
            "logs_root": args.logs_root,
            "days": args.days,
            "samples": args.samples,
            "context_limit": args.context_limit,
            "top": args.top,
            "min_score": args.min_score,
        },
        "summary": assess(comparisons),
        "comparisons": comparisons,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Retrieve Task Context Simulation",
        "",
        f"- mode: `{report['mode']}`",
        f"- verdict: `{s['verdict']}`",
        f"- compared: `{s['compared']}`",
        f"- new_hits: `{s['new_hits']}`",
        f"- changed: `{s['changed']}`",
        f"- still_empty: `{s['still_empty']}`",
        f"- conclusion: {s['conclusion']}",
        f"- recommended_decision: {s['recommended_decision']}",
        "",
    ]
    for item in report["comparisons"]:
        lines.append(f"## {item['task']} - {item['verdict']} - {item['shape']}")
        lines.append(f"- query: `{item['query'][:160]}`")
        lines.append(f"- context_chars: `{item['context_chars']}`")
        lines.append("- literal:")
        if item["baseline"]["pointers"]:
            for p in item["baseline"]["pointers"]:
                lines.append(f"  - `{p['path']}` - {p.get('why', '')}")
        else:
            lines.append("  - []")
        lines.append("- task-context-expanded:")
        if item["expanded"]["pointers"]:
            for p in item["expanded"]["pointers"]:
                lines.append(f"  - `{p['path']}` - {p.get('why', '')}")
        else:
            lines.append("  - []")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate task-context-expanded retrieve for human zero-hit queries.")
    parser.add_argument("--logs-root", default=str(Path.home() / ".claude" / "logs"))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--context-limit", type=int, default=600)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--memory-root", default=str(retrieve_mod.DEFAULT_MEMORY_ROOT))
    parser.add_argument("--task-root", default=str(retrieve_mod.DEFAULT_TASK_ROOT))
    parser.add_argument("--cache", default=None)
    parser.add_argument("--tags", default="")
    parser.add_argument("--top", type=int, default=retrieve_mod.MAX_POINTERS)
    parser.add_argument("--min-score", type=float, default=retrieve_mod.MIN_SCORE_DEFAULT)
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
