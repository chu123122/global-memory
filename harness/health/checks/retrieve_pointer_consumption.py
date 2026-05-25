"""retrieve_pointer_consumption.py — retrieve 真消费率 7d 趋势检查。

复用 analyze_retrieve_log.compute_consumption 算 call_rate / pointer_rate。
- call_rate <10% → warning，<3% → critical（召回有 hit 但没人 Read）
- pointer_rate <5% → warning（召回的 pointer 几乎不被 Read）
- 0 调用 → info

不同于 retrieve_hitrate（zero_hit 率，写端 frontmatter 信号），
本 check 是读端注入价值信号，互补不重叠。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..registry import Signal, register

from harness.scripts.analyze_retrieve_log import (  # type: ignore
    compute_consumption,
    load_records,
    load_tool_audit,
)

LOG_PATH = Path.home() / ".claude" / "logs" / "retrieve_calls.jsonl"
AUDIT_PATH = Path.home() / ".claude" / "logs" / "tool_audit.jsonl"
WINDOW_DAYS = 7
CALL_RATE_WARN = 0.10
CALL_RATE_CRIT = 0.03
POINTER_RATE_WARN = 0.05


@register("retrieve_pointer_consumption")
def check() -> list[Signal]:
    if not LOG_PATH.exists():
        return [Signal("retrieve_pointer_consumption", "info",
                       "retrieve_calls.jsonl 不存在")]

    records = load_records(LOG_PATH, days=WINDOW_DAYS)
    if not records:
        return [Signal("retrieve_pointer_consumption", "info",
                       f"近 {WINDOW_DAYS} 天无 retrieve 调用")]

    audits = load_tool_audit(AUDIT_PATH, days=WINDOW_DAYS)
    result = compute_consumption(records, audits)
    if result.get("note"):
        return [Signal("retrieve_pointer_consumption", "info", result["note"])]

    total = result.get("total_retrieve_calls_with_hits", 0)
    call_rate = result.get("call_rate", 0.0)
    pointer_rate = result.get("pointer_rate", 0.0)
    noisy = result.get("noisy_pointers_top10", [])

    if call_rate < CALL_RATE_CRIT:
        status = "critical"
    elif call_rate < CALL_RATE_WARN or pointer_rate < POINTER_RATE_WARN:
        status = "warning"
    else:
        status = "ok"

    evidence: list[str] = []
    for np in noisy[:5]:
        evidence.append(
            f"{np['recalled']}× recalled, 0 read: "
            f"{Path(np['path']).name}"
        )

    fix = ""
    if status != "ok":
        fix = "高噪声 pointer → 修 frontmatter keyword（删泛 kw）或降 MAX_POINTERS"

    return [Signal(
        check_id="retrieve_pointer_consumption",
        status=status,
        headline=(
            f"近 {WINDOW_DAYS} 天 retrieve {total} 次：call_rate "
            f"{call_rate * 100:.1f}% / pointer_rate {pointer_rate * 100:.1f}%"
        ),
        value=(
            f"calls_with_read={result.get('calls_with_any_pointer_read', 0)} / {total}, "
            f"pointers_read={result.get('pointers_actually_read', 0)} / "
            f"{result.get('total_pointers_recalled', 0)}"
        ),
        evidence=evidence,
        fix_hint=fix,
    )]
