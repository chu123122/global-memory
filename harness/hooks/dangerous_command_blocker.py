#!/usr/bin/env python3
"""
dangerous_command_blocker.py — PreToolUse Bash hook

拦截破坏性 shell 命令（rm -rf /、git push --force 等）。
匹配到危险模式时 exit 2 阻止执行，否则 exit 0 放行。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, deny, allow

# 预编译所有拦截正则（模块加载时执行，不影响运行时性能）
DENY_PATTERNS = [
    # ── 宽泛递归删除 ──
    (re.compile(r'\brm\s+.*-[a-zA-Z]*r[a-zA-Z]*\s+(/\s|/\s*$|~|"\s*~|\*\s*$)'),
     "Blocked: broad recursive delete targeting / or ~ or *"),

    # ── Git 破坏性操作 ──
    (re.compile(r'\bgit\s+push\s+.*(-f\b|--force\b)'),
     "Blocked: git push --force"),

    (re.compile(r'\bgit\s+reset\s+--hard\b'),
     "Blocked: git reset --hard discards changes"),

    (re.compile(r'\bgit\s+checkout\s+--\s+\.\s*$'),
     "Blocked: git checkout -- . discards all changes"),

    (re.compile(r'\bgit\s+restore\s+\.\s*$'),
     "Blocked: git restore . discards all changes"),

    (re.compile(r'\bgit\s+clean\s+.*-[a-zA-Z]*f'),
     "Blocked: git clean -f deletes untracked files"),

    (re.compile(r'\bgit\s+branch\s+-D\b'),
     "Blocked: git branch -D force-deletes branch"),

    # ── SQL 破坏 ──
    (re.compile(r'\bDROP\s+(TABLE|DATABASE)\b', re.IGNORECASE),
     "Blocked: DROP TABLE/DATABASE"),

    (re.compile(r'\bTRUNCATE\s+TABLE\b', re.IGNORECASE),
     "Blocked: TRUNCATE TABLE"),

    # ── 磁盘/系统操作 ──
    (re.compile(r'\bmkfs\b'),
     "Blocked: mkfs filesystem format"),

    (re.compile(r'\bdd\s+if='),
     "Blocked: dd raw disk write"),

    (re.compile(r'\bformat\s+[A-Za-z]:', re.IGNORECASE),
     "Blocked: disk format command"),

    # ── Fork bomb ──
    (re.compile(r':\(\)\s*\{'),
     "Blocked: fork bomb pattern"),
]


def main():
    data = read_hook_input()
    if not data:
        allow()

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        allow()

    for pattern, message in DENY_PATTERNS:
        if pattern.search(command):
            deny(message)

    allow()


if __name__ == "__main__":
    main()
