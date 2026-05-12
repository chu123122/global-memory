#!/usr/bin/env python3
"""
UserPromptSubmit hook: inject CHANGELOG tail when user mentions pull/sync.
Reads user message from stdin, checks for keywords, outputs last 20 lines.
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

KEYWORDS = ["pull", "拉取", "更新", "同步"]
CHANGELOG = Path("D:/global-memory/CHANGELOG.md")
TAIL_LINES = 20


def main():
    user_msg = sys.stdin.read().lower()
    if not any(kw in user_msg for kw in KEYWORDS):
        return

    if not CHANGELOG.exists():
        return

    lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    tail = lines[-TAIL_LINES:] if len(lines) >= TAIL_LINES else lines
    print("📋 CHANGELOG 最近变更：")
    print("\n".join(tail))


if __name__ == "__main__":
    main()
