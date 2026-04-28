"""knowledge/*.md 顶层文件 access_count=0 计数。

frontmatter 用裸正则解析够用。docs/ 子目录暂不扫。
"""
from __future__ import annotations

import re
from pathlib import Path

from ..registry import Signal, register

KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"
ACCESS_PATTERN = re.compile(r"^access_count:\s*(\d+)\s*$", re.MULTILINE)


@register("knowledge_unread")
def check() -> list[Signal]:
    if not KNOWLEDGE_DIR.exists():
        return [Signal("knowledge_unread", "info", "knowledge/ 不存在")]
    files = sorted(KNOWLEDGE_DIR.glob("knowledge_*.md"))
    if not files:
        return [Signal("knowledge_unread", "info", "knowledge/ 顶层无 knowledge_*.md")]
    unread: list[str] = []
    for path in files:
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
        m = ACCESS_PATTERN.search(head)
        if m and int(m.group(1)) == 0:
            unread.append(path.name)
    total = len(files)
    n = len(unread)
    if n == 0:
        status, headline = "ok", f"knowledge 顶层 {total} 文件全部有读取记录"
    elif n / total >= 0.7:
        status, headline = "critical", f"knowledge 顶层 {n}/{total} 从未被读"
    elif n / total >= 0.3:
        status, headline = "warning", f"knowledge 顶层 {n}/{total} 从未被读"
    else:
        status, headline = "info", f"knowledge 顶层 {n}/{total} 从未被读"
    return [
        Signal(
            check_id="knowledge_unread",
            status=status,
            headline=headline,
            value=f"{n}/{total}",
            evidence=unread[:10],
            fix_hint="长期未读文件迁 archives/cold-knowledge/，从 MEMORY.md AUTO-INDEX 摘除",
        )
    ]
