"""L4-C: hitrate gate. 跑全部 L4-A fuzzy 用例，统计命中率 ≥80%。

并写 $env:CLAUDE_TASKS_ACTIVE/harness-context-governance/L4-METRICS.md，
保留每次跑的快照供 TEST-LOG 追溯。
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

import pytest

import harness_retrieve as hr  # type: ignore

from .test_l4_fuzzy import FUZZY_CASES

THRESHOLD = 0.80
TASKS_ACTIVE = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(Path.home() / ".claude" / "tasks" / "active")))
METRICS_PATH = TASKS_ACTIVE / "harness-context-governance" / "L4-METRICS.md"


def _paths(brief: hr.ContextBrief) -> list[str]:
    return [p["path"] for p in brief.relevant_pointers]


def test_l4c_hitrate_gate(memory_root, task_root, cache_path):
    hr.load_aliases(force=True)
    expected_total = 0
    hits = 0
    rows: list[tuple[str, str, str, bool]] = []  # (label, query, expected, hit)
    for query, expected, label in FUZZY_CASES:
        if expected is None:
            continue
        expected_total += 1
        brief = hr.retrieve(
            task_name="demo-task", user_msg=query,
            memory_root=memory_root, task_root=task_root, cache_path=cache_path,
        )
        ok = any(expected in p for p in _paths(brief))
        if ok:
            hits += 1
        rows.append((label, query, expected, ok))

    rate = hits / expected_total if expected_total else 0.0
    _write_metrics(rows, hits, expected_total, rate)
    assert rate >= THRESHOLD, (
        f"hitrate={rate:.0%} < {THRESHOLD:.0%}; details written to {METRICS_PATH}"
    )


def _write_metrics(rows, hits, total, rate):
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# L4 命中率快照",
        "",
        f"> 最新跑: {ts}",
        f"> 阈值: ≥{int(THRESHOLD * 100)}%",
        f"> 结果: **{rate:.0%}** ({hits}/{total})",
        "",
        "| 标签 | Query | 期望文件 | 命中 |",
        "|---|---|---|---|",
    ]
    for label, query, expected, ok in rows:
        mark = "✅" if ok else "🔴"
        q_display = query.replace("|", "\\|")
        if len(q_display) > 40:
            q_display = q_display[:40] + "…"
        lines.append(f"| {label} | `{q_display}` | {expected} | {mark} |")
    lines.append("")
    METRICS_PATH.write_text("\n".join(lines), encoding="utf-8")
