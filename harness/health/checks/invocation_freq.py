"""harness_tool_invocations.jsonl 7 天调用排行 + 找零调用脚本。"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..registry import Signal, register

LOG_PATH = Path.home() / ".claude" / "logs" / "harness_tool_invocations.jsonl"
WINDOW_DAYS = 7


@register("invocation_freq")
def check() -> list[Signal]:
    if not LOG_PATH.exists():
        return [Signal("invocation_freq", "info", "harness_tool_invocations.jsonl 不存在")]
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    counter: Counter[str] = Counter()
    with LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = obj.get("ts") or obj.get("timestamp") or ""
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if t < cutoff:
                continue
            script = obj.get("script") or obj.get("source") or "?"
            counter[script] += 1
    if not counter:
        return [
            Signal(
                check_id="invocation_freq",
                status="warning",
                headline=f"近 {WINDOW_DAYS} 天 token saver 调用 0 次",
                fix_hint="未走 /work /check /skill-auditor → token saver 不会被触发",
            )
        ]
    rows = counter.most_common()
    total = sum(counter.values())
    evidence = [f"{name:<30} {n} 次" for name, n in rows]
    return [
        Signal(
            check_id="invocation_freq",
            status="info",
            headline=f"近 {WINDOW_DAYS} 天 harness 脚本调用 {total} 次（{len(rows)} 个脚本）",
            value=f"{total} calls / {len(rows)} scripts",
            evidence=evidence,
            fix_hint="排名靠后或 0 次的 token saver 是死代码候选",
        )
    ]
