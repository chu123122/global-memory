"""skills 投入（行数）vs 产出（7 天调用次数）比例。

每个 skill 一行入口，把 skill 文档行数和该 skill 触发的脚本调用次数比较：
  ratio = lines / max(calls, 1)
  ratio > 80 = 写得多用得少（critical 候选）
  ratio > 30 = 失衡（warning 候选）

调用归属：harness_tool_invocations.jsonl 的 `source` 字段已经语义化
（如 work-context-pack / check-prepare / skill-audit），通过名字前缀匹配
对应 skill。无 source 映射的脚本不计入 skill 调用。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..registry import Signal, register

REPO_DIR = Path(__file__).resolve().parents[3]
LOG_PATH = Path.home() / ".claude" / "logs" / "harness_tool_invocations.jsonl"
WINDOW_DAYS = 7

SOURCE_TO_SKILL = {
    "work-context-pack": "work",
    "check-prepare": "check",
    "skill-audit": "skill-auditor",
    "outcomes-reader": "work",
    "session-report": "work",
}


def _skill_lines() -> dict[str, int]:
    out: dict[str, int] = {}
    skills_root = REPO_DIR / "skills"
    if not skills_root.exists():
        return out
    for skill_dir in skills_root.iterdir():
        if not skill_dir.is_dir():
            continue
        total = 0
        for md in skill_dir.rglob("*.md"):
            try:
                total += sum(1 for _ in md.open(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        if total:
            out[skill_dir.name] = total
    return out


def _calls_per_skill() -> Counter:
    counter: Counter[str] = Counter()
    if not LOG_PATH.exists():
        return counter
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    with LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = obj.get("ts", "")
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if t < cutoff:
                continue
            skill = SOURCE_TO_SKILL.get(obj.get("source", ""))
            if skill:
                counter[skill] += 1
    return counter


@register("traffic_imbalance")
def check() -> list[Signal]:
    lines = _skill_lines()
    calls = _calls_per_skill()
    if not lines:
        return [Signal("traffic_imbalance", "info", "skills/ 无文档")]

    rows: list[tuple[str, int, int, float]] = []
    for skill, n_lines in lines.items():
        n_calls = calls.get(skill, 0)
        ratio = n_lines / max(n_calls, 1)
        rows.append((skill, n_lines, n_calls, ratio))
    rows.sort(key=lambda r: -r[3])

    bad = [r for r in rows if r[3] > 80]
    warn = [r for r in rows if 30 < r[3] <= 80]

    if bad:
        status = "critical"
    elif warn:
        status = "warning"
    else:
        status = "ok"

    headline = (
        f"skill 投入产出失衡：{len(bad)} critical / {len(warn)} warning "
        f"/ {len(rows)} 总"
    )
    evidence = [
        f"{name:<18} {nl:>4} 行 / 7d {nc:>3} 次调用 = {r:>6.1f} 行/次"
        for name, nl, nc, r in rows
    ]
    return [
        Signal(
            check_id="traffic_imbalance",
            status=status,
            headline=headline,
            value=f"top: {rows[0][0]}={rows[0][3]:.0f}",
            evidence=evidence,
            fix_hint="比例 > 80 行/次 = 投入过重；考虑精简 skill 文档或证伪它的存在价值",
        )
    ]
