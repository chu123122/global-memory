#!/usr/bin/env python3
"""
statusline.py — Claude Code statusLine: git branch + context pressure warning.
Normal state: just branch name. Warns at 40+ msgs, alerts at 80+.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

COMPACT_MARKER = b'"This session is being continued from a previous conversation'

RESET = "\033[0m"
RED = "\033[1;31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
CYAN = "\033[36m"

SESSION_TASKS_DIR = Path.home() / ".claude" / ".session_tasks"


def count_user_msgs(data):
    transcript = data.get("transcript_path", "")
    if not transcript:
        return 0
    jsonl = Path(transcript)
    if not jsonl.exists():
        return 0
    try:
        last_compact_idx = -1
        real_user_indices = []
        with open(jsonl, "rb") as f:
            for i, line in enumerate(f):
                if b'"type":"user"' not in line:
                    continue
                if COMPACT_MARKER in line:
                    last_compact_idx = i
                else:
                    real_user_indices.append(i)
        return sum(1 for idx in real_user_indices if idx > last_compact_idx)
    except Exception:
        return 0


def get_branch(cwd):
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    cwd = data.get("cwd", "")
    branch = get_branch(cwd)
    user_msgs = count_user_msgs(data)

    task_name = ""
    session_id = data.get("session_id", "") or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if session_id:
        marker = SESSION_TASKS_DIR / session_id
        try:
            if marker.exists():
                task_name = marker.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    parts = []
    if task_name:
        parts.append(f"{CYAN}{task_name}{RESET}")
    if branch:
        parts.append(f"{DIM}{branch}{RESET}")

    if user_msgs >= 80:
        parts.append(f"{RED}🛑 new session recommended{RESET}")
    elif user_msgs >= 40:
        parts.append(f"{YELLOW}⚠ /compact{RESET}")

    if parts:
        print(" | ".join(parts), end="")


if __name__ == "__main__":
    main()
