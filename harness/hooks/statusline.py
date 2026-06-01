#!/usr/bin/env python3
"""
statusline.py — Claude Code statusLine: git branch + context pressure warning.
Normal state: just branch name. Warns at 40+ msgs, alerts at 80+.
"""

import io
import json
import os
import sys
import subprocess
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

COMPACT_MARKER = b'"This session is being continued from a previous conversation'

RESET = "\033[0m"
RED = "\033[1;31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
CYAN = "\033[36m"

CURRENT_TASK_FILE = Path.home() / ".claude" / ".current_task"
DISPLAY_NAMES_FILE = Path.home() / ".claude" / "projects" / "task_display_names.json"


def load_display_name(task_id: str) -> str:
    """Look up Chinese display name for task; fallback to raw id."""
    if not task_id:
        return ""
    try:
        if DISPLAY_NAMES_FILE.is_file():
            data = json.loads(DISPLAY_NAMES_FILE.read_text(encoding="utf-8"))
            name = data.get(task_id)
            if isinstance(name, str) and name.strip():
                return name.strip()
    except Exception:
        pass
    return task_id


def resolve_task_name() -> str:
    """Read .current_task (single source of truth)."""
    try:
        if CURRENT_TASK_FILE.is_file():
            name = CURRENT_TASK_FILE.read_text(encoding="utf-8").strip()
            if name:
                return name
    except Exception:
        pass
    return ""


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

    task_id = resolve_task_name()
    task_display = load_display_name(task_id) if task_id else ""

    parts = []
    if task_display:
        parts.append(f"{CYAN}{task_display}{RESET}")
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
