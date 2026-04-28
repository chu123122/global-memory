"""MEMORY.md 文件数 / 80 上限。

阈值：< 60 ok / 60-72 warning / >= 73 critical。
"""
from __future__ import annotations

import re
from pathlib import Path

from ..registry import Signal, register

MEMORY_PATH = Path(__file__).resolve().parents[3] / "MEMORY.md"
PATTERN = re.compile(r"总文件数[：:]\s*(\d+)\s*/\s*(\d+)")


@register("memory_usage")
def check() -> list[Signal]:
    if not MEMORY_PATH.exists():
        return [Signal("memory_usage", "critical", "MEMORY.md 不存在", evidence=[str(MEMORY_PATH)])]
    text = MEMORY_PATH.read_text(encoding="utf-8", errors="replace")
    m = PATTERN.search(text)
    if not m:
        return [Signal("memory_usage", "warning", "MEMORY.md 未找到统计行", fix_hint="跑 update_stats.py")]
    used, cap = int(m.group(1)), int(m.group(2))
    pct = used / cap if cap else 0
    if pct >= 0.9:
        status, hint = "critical", "拆 MEMORY.md：ACTIVE_PROJECTS 30 行 + AUTO-INDEX 单独"
    elif pct >= 0.75:
        status, hint = "warning", "考虑冷藏冷门 knowledge 文件，从 AUTO-INDEX 摘除"
    else:
        status, hint = "ok", ""
    return [
        Signal(
            check_id="memory_usage",
            status=status,
            headline=f"MEMORY.md 占用 {used}/{cap}（{pct:.0%}）",
            value=f"{used}/{cap}",
            evidence=[str(MEMORY_PATH)],
            fix_hint=hint,
        )
    ]
