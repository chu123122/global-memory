#!/usr/bin/env python3
"""retrieve_zero_hit_analysis.py — read-only user-query zero-hit report."""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_LOGS = Path.home() / ".claude" / "logs"


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


def classify_query(query: str) -> str:
    stripped = (query or "").strip()
    if stripped.startswith("<task-notification>"):
        return "automation"
    if stripped.startswith("# Autonomous"):
        return "automation"
    if stripped.startswith("/goal"):
        return "control"
    return "human"


def is_short_followup(query: str) -> bool:
    stripped = (query or "").strip()
    if len(stripped) <= 20:
        return True
    markers = ("目前", "为啥", "为什么", "这是什么", "这个", "那个", "呢", "可以", "现在")
    return len(stripped) <= 60 and any(marker in stripped for marker in markers)


def load_rows(log_path: Path, days: int) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        ts = parse_ts(row.get("ts") or row.get("timestamp"))
        if ts and ts < cutoff:
            continue
        rows.append(row)
    return rows


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    rows = load_rows(Path(args.logs_root) / "retrieve_calls.jsonl", args.days)
    human = [r for r in rows if classify_query(str(r.get("query") or "")) == "human"]
    zero = [r for r in human if int(r.get("hit_count") or 0) == 0]
    recent_zero = zero[-args.samples :]

    by_task = Counter(str(r.get("task") or "<no-task>") for r in zero)
    short_followups = [r for r in zero if is_short_followup(str(r.get("query") or ""))]
    task_specific = [r for r in zero if not is_short_followup(str(r.get("query") or ""))]

    zero_rate = len(zero) / len(human) if human else 0.0
    short_rate = len(short_followups) / len(zero) if zero else 0.0
    task_specific_rate = len(task_specific) / len(zero) if zero else 0.0

    if not human:
        verdict = "NO_HUMAN_SAMPLE"
        conclusion = "没有 human retrieve 样本，不能评估 zero-hit 的用户体感。"
        recommended = "继续收集日志，不要修改 retrieve。"
    elif zero_rate < args.zero_rate_threshold:
        verdict = "LOW_ZERO_HIT"
        conclusion = f"human query zero-hit={len(zero)}/{len(human)} ({zero_rate:.1%})，暂不需要专门优化。"
        recommended = "保持观测，不进入行为改动。"
    elif short_rate >= 0.5:
        verdict = "TASK_CONTEXT_FALLBACK_NEEDED"
        conclusion = (
            f"human query zero-hit={len(zero)}/{len(human)} ({zero_rate:.1%})；"
            f"其中 {len(short_followups)}/{len(zero)} 更像任务内短追问。"
        )
        recommended = "先设计 task-context fallback/别名补全 proposal，不直接放宽全局召回。"
    else:
        verdict = "ALIASES_OR_FRONTMATTER_NEEDED"
        conclusion = (
            f"human query zero-hit={len(zero)}/{len(human)} ({zero_rate:.1%})；"
            "多数不是短追问，更可能是 aliases/frontmatter 覆盖不足。"
        )
        recommended = "先基于高频任务补 aliases/frontmatter proposal，并用 before/after 样本验证。"

    return {
        "schema_version": 1,
        "mode": "read-only-zero-hit-analysis",
        "inputs": {
            "logs_root": args.logs_root,
            "days": args.days,
            "samples": args.samples,
            "zero_rate_threshold": args.zero_rate_threshold,
        },
        "summary": {
            "human_calls": len(human),
            "human_zero_hit": len(zero),
            "human_zero_hit_rate": round(zero_rate, 4),
            "short_followup_zero_hit": len(short_followups),
            "short_followup_zero_hit_rate": round(short_rate, 4),
            "task_specific_zero_hit": len(task_specific),
            "task_specific_zero_hit_rate": round(task_specific_rate, 4),
            "top_zero_hit_tasks": [{"task": task, "count": count} for task, count in by_task.most_common(8)],
        },
        "external_assessment": {
            "verdict": verdict,
            "conclusion": conclusion,
            "recommended_first_action": recommended,
            "do_not_do_now": "不要为了减少 zero-hit 直接降低 min_score 或扩大 MAX_POINTERS；这会把噪声重新带回首屏。",
        },
        "visible_failure_samples": [
            {
                "task": str(r.get("task") or ""),
                "query": str(r.get("query") or ""),
                "shape": "short_followup" if is_short_followup(str(r.get("query") or "")) else "task_specific",
            }
            for r in recent_zero
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    a = report["external_assessment"]
    lines = [
        "# Retrieve Human Zero-Hit Analysis",
        "",
        f"- mode: `{report['mode']}`",
        f"- human_calls: `{s['human_calls']}`",
        f"- human_zero_hit: `{s['human_zero_hit']}`",
        f"- human_zero_hit_rate: `{s['human_zero_hit_rate']}`",
        f"- short_followup_zero_hit: `{s['short_followup_zero_hit']}`",
        f"- external_verdict: `{a['verdict']}`",
        f"- conclusion: {a['conclusion']}",
        f"- recommended_first_action: {a['recommended_first_action']}",
        f"- do_not_do_now: {a['do_not_do_now']}",
        "",
        "## Top Tasks",
        "",
    ]
    for item in s["top_zero_hit_tasks"]:
        lines.append(f"- `{item['task']}`: {item['count']}")
    lines.extend(["", "## Visible Failure Samples", ""])
    for sample in report["visible_failure_samples"]:
        lines.append(f"- `{sample['task']}` [{sample['shape']}]: {sample['query'][:160]}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze human retrieve zero-hit samples without changing behavior.")
    parser.add_argument("--logs-root", default=str(DEFAULT_LOGS))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--zero-rate-threshold", type=float, default=0.25)
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
