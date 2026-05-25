#!/usr/bin/env python3
"""retrieve_fallback_cost.py - summarize task-context fallback runtime cost.

Read-only. Uses retrieve_calls.jsonl records written by harness_retrieve.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_LOGS = Path.home() / ".claude" / "logs"
FALLBACK_RE = re.compile(r"task_context_fallback:source=([^,]+),context_chars=(\d+),docs=([^;]+)")


def parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def load_rows(path: Path, days: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        ts = parse_ts(row.get("ts") or row.get("timestamp"))
        if ts and ts < cutoff:
            continue
        rows.append(row)
    return rows


def fallback_info(row: dict[str, Any]) -> dict[str, Any] | None:
    for warning in row.get("warnings", []) or []:
        match = FALLBACK_RE.search(str(warning))
        if match:
            return {
                "source": match.group(1),
                "context_chars": int(match.group(2)),
                "docs": [x for x in match.group(3).split(",") if x],
            }
    return None


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    rows = load_rows(Path(args.logs_root) / "retrieve_calls.jsonl", args.days)
    fallback_rows: list[dict[str, Any]] = []
    for row in rows:
        info = fallback_info(row)
        if not info:
            continue
        fallback_rows.append({**row, "_fallback": info})

    by_task: Counter[str] = Counter(str(r.get("task") or "<no-task>") for r in fallback_rows)
    by_source: Counter[str] = Counter(str(r["_fallback"]["source"]) for r in fallback_rows)
    context_values = [int(r["_fallback"]["context_chars"]) for r in fallback_rows]
    hit_values = [int(r.get("hit_count") or 0) for r in fallback_rows]
    top_paths: Counter[str] = Counter(str(r.get("top1_path") or "<none>") for r in fallback_rows)
    total = len(rows)
    triggered = len(fallback_rows)
    avg_context = sum(context_values) / triggered if triggered else 0.0
    avg_hits = sum(hit_values) / triggered if triggered else 0.0

    return {
        "schema_version": 1,
        "mode": "read-only-fallback-cost-ledger",
        "inputs": {
            "logs_root": args.logs_root,
            "days": args.days,
        },
        "summary": {
            "total_retrieve_calls": total,
            "fallback_triggered": triggered,
            "fallback_trigger_rate": round(triggered / total, 4) if total else 0.0,
            "avg_context_chars": round(avg_context, 1),
            "avg_hit_count_after_fallback": round(avg_hits, 2),
            "max_context_chars": max(context_values) if context_values else 0,
            "min_context_chars": min(context_values) if context_values else 0,
        },
        "by_task": [{"task": task, "count": count} for task, count in by_task.most_common(10)],
        "by_source": [{"source": source, "count": count} for source, count in by_source.most_common(10)],
        "top1_paths": [{"path": path, "count": count} for path, count in top_paths.most_common(10)],
        "recent_samples": [
            {
                "ts": r.get("ts"),
                "task": r.get("task"),
                "query": r.get("query"),
                "hit_count": r.get("hit_count"),
                "context_chars": r["_fallback"]["context_chars"],
                "source": r["_fallback"]["source"],
                "top1_path": r.get("top1_path"),
            }
            for r in fallback_rows[-args.samples :]
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Retrieve Fallback Cost Ledger / fallback 成本账本",
        "",
        f"- total_retrieve_calls / 总 retrieve 调用: `{s['total_retrieve_calls']}`",
        f"- fallback_triggered / fallback 触发次数: `{s['fallback_triggered']}`",
        f"- fallback_trigger_rate / fallback 触发率: `{s['fallback_trigger_rate']}`",
        f"- avg_context_chars / 平均注入字符数: `{s['avg_context_chars']}`",
        f"- avg_hit_count_after_fallback / fallback 后平均命中数: `{s['avg_hit_count_after_fallback']}`",
        f"- min_context_chars / 最小注入字符数: `{s['min_context_chars']}`",
        f"- max_context_chars / 最大注入字符数: `{s['max_context_chars']}`",
        "",
        "## By Task / 按任务",
    ]
    if not report["by_task"]:
        lines.append("- none / 无")
    for row in report["by_task"]:
        lines.append(f"- `{row['task']}`: {row['count']}")
    lines += ["", "## By Source / 按来源"]
    if not report["by_source"]:
        lines.append("- none / 无")
    for row in report["by_source"]:
        lines.append(f"- `{row['source']}`: {row['count']}")
    lines += ["", "## Recent Samples / 最近样本"]
    if not report["recent_samples"]:
        lines.append("- none / 无")
    for row in report["recent_samples"]:
        lines.append(
            f"- `{row['task']}` query=`{row['query']}` context_chars={row['context_chars']} "
            f"hit_count={row['hit_count']} top1=`{row['top1_path']}`"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize task-context fallback cost from retrieve logs.")
    parser.add_argument("--logs-root", default=str(DEFAULT_LOGS))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--samples", type=int, default=5)
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
