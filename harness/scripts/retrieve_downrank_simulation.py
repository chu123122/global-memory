#!/usr/bin/env python3
"""retrieve_downrank_simulation.py — replay retrieve queries with candidate downrank.

Read-only. This does not change retrieve ranking, cache, frontmatter, or logs.
It replays recent retrieve_calls.jsonl records through the current scorer, then
applies a simulated score penalty to candidate_downrank pointers reported by
retrieve_candidate_quality.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOGS = Path.home() / ".claude" / "logs"
DEFAULT_MEMORY_ROOT = Path("D:/global-memory")
SCHEMA_VERSION = 1


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


retrieve_mod = load_module(SCRIPT_DIR / "harness_retrieve.py", "_gm_harness_retrieve")
quality_mod = load_module(SCRIPT_DIR / "retrieve_candidate_quality.py", "_gm_retrieve_candidate_quality")


def parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def load_jsonl(path: Path, days: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days) if days else None
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            ts = parse_ts(row.get("ts") or row.get("timestamp"))
            if cutoff and ts and ts < cutoff:
                continue
            out.append(row)
    return out


def norm_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().lower()


def family_for(path: str) -> str:
    return quality_mod.family_for(path)


def score_query(query: str, stage: str | None, task_tags: list[str], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = retrieve_mod.load_aliases()
    expanded, _ = retrieve_mod.expand_query(query, aliases)
    scored = []
    for entry in entries:
        score, why = retrieve_mod._score_entry(entry, expanded, stage, task_tags)
        if score >= retrieve_mod.MIN_SCORE_DEFAULT:
            scored.append({
                "path": retrieve_mod.normalize_path(entry["path"]),
                "why": why,
                "score": score,
                "family": family_for(entry["path"]),
            })
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored


def apply_downrank(scored: list[dict[str, Any]], candidate_paths: set[str], factor: float, min_score: float) -> list[dict[str, Any]]:
    adjusted = []
    for item in scored:
        copied = dict(item)
        if norm_path(copied["path"]) in candidate_paths:
            copied["original_score"] = copied["score"]
            copied["score"] = copied["score"] * factor
            copied["simulated_downrank"] = True
        else:
            copied["simulated_downrank"] = False
        if copied["score"] >= min_score:
            adjusted.append(copied)
    adjusted.sort(key=lambda item: item["score"], reverse=True)
    return adjusted


def top_paths(items: list[dict[str, Any]], top_n: int) -> list[str]:
    return [item["path"] for item in items[:top_n]]


def count_families(rows: list[list[dict[str, Any]]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for row in rows:
        for item in row:
            c[item.get("family", "unknown")] += 1
    return dict(c.most_common())


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    logs = Path(args.logs_root)
    memory_root = Path(args.memory_root)
    quality_args = argparse.Namespace(
        logs_root=str(logs),
        days=args.days,
        min_recalled=args.min_recalled,
        limit=10000,
    )
    quality = quality_mod.build_report(quality_args)
    candidate_paths = {norm_path(row["path"]) for row in quality.get("candidate_downrank", [])}

    cache_path = retrieve_mod._cache_path_for(memory_root)
    entries = retrieve_mod.load_trigger_cache(cache_path, memory_root)
    rows = load_jsonl(logs / "retrieve_calls.jsonl", args.days)

    evaluated = 0
    baseline_zero = adjusted_zero = 0
    top1_changed = 0
    topn_changed = 0
    baseline_tops: list[list[dict[str, Any]]] = []
    adjusted_tops: list[list[dict[str, Any]]] = []
    examples = []

    for row in rows:
        query = str(row.get("query") or "")
        if not query.strip():
            continue
        stage = row.get("stage") if isinstance(row.get("stage"), str) else None
        scored = score_query(query, stage, [], entries)
        adjusted = apply_downrank(scored, candidate_paths, args.penalty_factor, retrieve_mod.MIN_SCORE_DEFAULT)
        baseline_top = scored[: args.top]
        adjusted_top = adjusted[: args.top]
        evaluated += 1
        if not baseline_top:
            baseline_zero += 1
        if not adjusted_top:
            adjusted_zero += 1
        if top_paths(baseline_top, 1) != top_paths(adjusted_top, 1):
            top1_changed += 1
        if top_paths(baseline_top, args.top) != top_paths(adjusted_top, args.top):
            topn_changed += 1
        baseline_tops.append(baseline_top)
        adjusted_tops.append(adjusted_top)
        if len(examples) < args.examples and top_paths(baseline_top, args.top) != top_paths(adjusted_top, args.top):
            examples.append({
                "task": row.get("task"),
                "query": query[:120],
                "baseline": [summarize_item(x) for x in baseline_top],
                "adjusted": [summarize_item(x) for x in adjusted_top],
            })

    zero_delta = adjusted_zero - baseline_zero
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "read-only-simulation",
        "inputs": {
            "logs_root": str(logs),
            "memory_root": str(memory_root),
            "days": args.days,
            "top": args.top,
            "min_recalled": args.min_recalled,
            "penalty_factor": args.penalty_factor,
            "candidate_paths": len(candidate_paths),
        },
        "summary": {
            "evaluated_queries": evaluated,
            "baseline_zero_hit": baseline_zero,
            "adjusted_zero_hit": adjusted_zero,
            "zero_hit_delta": zero_delta,
            "top1_changed": top1_changed,
            "topn_changed": topn_changed,
            "baseline_family_counts": count_families(baseline_tops),
            "adjusted_family_counts": count_families(adjusted_tops),
            "guardrail_status": "PASS" if zero_delta <= max(1, round(evaluated * 0.05)) else "WARN",
        },
        "candidate_quality_summary": quality.get("summary", {}),
        "examples": examples,
    }


def summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": item.get("path"),
        "family": item.get("family"),
        "score": round(float(item.get("score", 0)), 3),
        "original_score": round(float(item.get("original_score", item.get("score", 0))), 3),
        "downranked": bool(item.get("simulated_downrank")),
        "why": item.get("why"),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Retrieve Downrank Simulation",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- mode: `{report['mode']}`",
        f"- evaluated_queries: `{summary['evaluated_queries']}`",
        f"- candidate_paths: `{report['inputs']['candidate_paths']}`",
        f"- penalty_factor: `{report['inputs']['penalty_factor']}`",
        "",
        "## Summary",
        "",
        f"- top1_changed: `{summary['top1_changed']}`",
        f"- top{report['inputs']['top']}_changed: `{summary['topn_changed']}`",
        f"- zero_hit_delta: `{summary['zero_hit_delta']}`",
        f"- guardrail_status: `{summary['guardrail_status']}`",
        "",
        "## Family Counts",
        "",
        "| family | baseline | adjusted | delta |",
        "|---|---:|---:|---:|",
    ]
    families = set(summary["baseline_family_counts"]) | set(summary["adjusted_family_counts"])
    for family in sorted(families):
        before = summary["baseline_family_counts"].get(family, 0)
        after = summary["adjusted_family_counts"].get(family, 0)
        lines.append(f"| {family} | {before} | {after} | {after - before} |")
    lines.extend(["", "## Changed Examples", ""])
    if not report["examples"]:
        lines.append("- No top-N changes in the evaluated window.")
    for ex in report["examples"]:
        lines.append(f"### {ex.get('task') or '<no-task>'}")
        lines.append(f"- query: `{ex['query']}`")
        lines.append("- baseline:")
        for item in ex["baseline"]:
            lines.append(f"  - `{item['family']}` `{item['path']}` score={item['score']} why={item['why']}")
        lines.append("- adjusted:")
        for item in ex["adjusted"]:
            mark = " downranked" if item["downranked"] else ""
            lines.append(f"  - `{item['family']}` `{item['path']}` score={item['score']}{mark} why={item['why']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay retrieve queries with simulated downrank for candidate pointers.")
    parser.add_argument("--logs-root", default=str(DEFAULT_LOGS))
    parser.add_argument("--memory-root", default=str(DEFAULT_MEMORY_ROOT))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--top", type=int, default=2)
    parser.add_argument("--min-recalled", type=int, default=10)
    parser.add_argument("--penalty-factor", type=float, default=0.2)
    parser.add_argument("--examples", type=int, default=5)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
