"""扫 maintain.jsonl 最近条目，区分 user_wip 跳过 vs 真失败。

真失败的判定：synced=false 且没有 skipped_reason。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..registry import Signal, register

LOG_PATH = Path.home() / ".claude" / "logs" / "maintain.jsonl"
WINDOW = 30


@register("sync_failures")
def check() -> list[Signal]:
    if not LOG_PATH.exists():
        return [Signal("sync_failures", "info", "maintain.jsonl 不存在")]
    entries: list[dict] = []
    with LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "sync":
                entries.append(obj)
    recent = entries[-WINDOW:]
    failures = [e for e in recent if e.get("synced") is False and not e.get("skipped_reason")]
    skipped = [e for e in recent if e.get("skipped_reason") == "user_wip"]
    successes = [e for e in recent if e.get("synced") is True]

    if not failures:
        status = "ok"
        headline = f"近 {len(recent)} 次 sync：{len(successes)} 成功 / {len(skipped)} WIP 跳过 / 0 真失败"
    elif len(failures) >= 5:
        status = "critical"
        headline = f"近 {len(recent)} 次 sync 中 {len(failures)} 次真失败"
    else:
        status = "warning"
        headline = f"近 {len(recent)} 次 sync 中 {len(failures)} 次真失败"

    evidence: list[str] = []
    for e in failures[-3:]:
        ts = e.get("timestamp", "")[:19]
        summary = e.get("summary", "?")
        stderr = (e.get("stderr") or "").splitlines()[0] if e.get("stderr") else ""
        evidence.append(f"{ts} | {summary} | {stderr[:80]}")

    return [
        Signal(
            check_id="sync_failures",
            status=status,
            headline=headline,
            value=f"{len(failures)}/{len(recent)} 失败",
            evidence=evidence,
            fix_hint="查 maintain.jsonl 末尾失败条目；常见根因：远端冲突 / 自循环 / push rejected",
        )
    ]
