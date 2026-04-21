#!/usr/bin/env python3
"""
memory_file_protector.py — PreToolUse Write|Edit hook

保护关键配置文件（conventions.md、CLAUDE.md、agents/*.md 等）。
保护文件 → 弹用户确认（ask）；非保护记忆文件 → 放行 + 记日志；其他 → 放行。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import (
    read_hook_input, ask, allow, append_jsonl,
    now_iso, LOG_DIR, MEMORY_DIR
)

# 保护文件模式（endswith 匹配）
PROTECTED_SUFFIXES = [
    "decisions/conventions.md",
    "memory-rules.md",
]

# 保护文件名（basename 匹配，适用于多位置出现的文件）
PROTECTED_BASENAMES = [
    "CLAUDE.md",
]

# 保护目录模式
AGENT_PATTERN = re.compile(r'agents/[^/]+\.md$')

# 记忆目录标识
MEMORY_MARKERS = ["/global-memory/", "\\.claude\\\\global-memory\\\\", "\\\\global-memory\\\\"]


def normalize(path: str) -> str:
    """统一为正斜杠。"""
    return path.replace("\\", "/")


def is_protected(normalized: str) -> tuple:
    """检查是否是受保护文件。返回 (是否保护, 匹配到的模式)。"""
    for suffix in PROTECTED_SUFFIXES:
        if normalized.endswith(suffix):
            return True, suffix

    basename = normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized
    for name in PROTECTED_BASENAMES:
        if basename == name:
            return True, name

    if AGENT_PATTERN.search(normalized):
        return True, "agents/*.md"

    return False, ""


def is_memory_file(normalized: str) -> bool:
    """检查是否在 global-memory 目录下。"""
    return "/global-memory/" in normalized


def main():
    data = read_hook_input()
    if not data:
        allow()

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        allow()

    normalized = normalize(file_path)

    # 检查保护文件
    protected, pattern = is_protected(normalized)
    if protected:
        ask(f"Protected file: {pattern}")

    # 非保护记忆文件：放行 + 记日志
    if is_memory_file(normalized):
        record = {
            "ts": now_iso(),
            "session": data.get("session_id", ""),
            "tool": data.get("tool_name", ""),
            "file": file_path,
        }
        try:
            append_jsonl(LOG_DIR / "memory_writes.jsonl", record)
        except Exception:
            pass
        allow()

    # 其他文件：直接放行
    allow()


if __name__ == "__main__":
    main()
