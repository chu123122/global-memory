"""lint_failure_rate.py — memory_lint_gate.jsonl 7d 失败率检查。

读 ~/.claude/logs/memory_lint_gate.jsonl 算 FAIL/TOTAL。
- FAIL rate ≥40% → critical
- FAIL rate ≥20% → warning
- 0 调用 → info

把 lint_gate.jsonl 从 write-only 转活，让记忆合规失败趋势可观测。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from ..registry import Signal, register

LOG_PATH = Path.home() / ".claude" / "logs" / "memory_lint_gate.jsonl"
WINDOW_DAYS = 7
FAIL_RATE_WARN = 0.20
FAIL_RATE_CRIT = 0.40
TOP_FAIL_FILES = 5


@register("lint_failure_rate")
def check() -> list[Signal]:
    if not LOG_PATH.exists():
        return [Signal("lint_failure_rate", "info",
                       "memory_lint_gate.jsonl 不存在（lint hook 未触发）")]

    cutoff = datetime.now() - timedelta(days=WINDOW_DAYS)
    total = 0
    fail = 0
    fail_files: Counter[str] = Counter()
    with LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = datetime.fromisoformat(r.get("ts", ""))
                if ts < cutoff:
                    continue
            except ValueError:
                continue
            total += 1
            if not r.get("ok", True):
                fail += 1
                fname = Path(r.get("file", "")).name or "<unknown>"
                fail_files[fname] += 1

    if total == 0:
        return [Signal("lint_failure_rate", "info",
                       f"近 {WINDOW_DAYS} 天 lint hook 未触发")]

    rate = fail / total
    if rate >= FAIL_RATE_CRIT:
        status = "critical"
    elif rate >= FAIL_RATE_WARN:
        status = "warning"
    else:
        status = "ok"

    evidence = [f"{n}× FAIL: {f}" for f, n in fail_files.most_common(TOP_FAIL_FILES)]
    fix = ""
    if status != "ok":
        fix = "看 fail_files 高频项，按模板修 frontmatter（keywords 带 namespace 前缀 / tags 走 vocab）"

    return [Signal(
        check_id="lint_failure_rate",
        status=status,
        headline=f"近 {WINDOW_DAYS} 天 memory lint {fail}/{total} FAIL ({rate * 100:.1f}%)",
        value=f"fail={fail} / total={total}",
        evidence=evidence,
        fix_hint=fix,
    )]
