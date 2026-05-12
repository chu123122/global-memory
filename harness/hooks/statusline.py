#!/usr/bin/env python3
"""
statusline.py — Claude Code statusLine script (Windows compatible)

Reads session JSON from stdin, counts user messages since last compact,
outputs a colored status line with model name, project, git branch, and message count.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

COMPACT_MARKER = b'"This session is being continued from a previous conversation'

MODEL_MAP = {
    "deepseek-v4-pro": "DSv4-Pro",
    "deepseek-v4-flash": "DSv4-Flash",
    "claude-opus-4-6": "Opus 4.6",
    "claude-opus-4-7": "Opus 4.7",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
}

RESET = "\033[0m"
RED = "\033[1;31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("?", end="")
        return

    session_id = data.get("session_id", "")
    cwd = data.get("cwd") or os.getcwd()
    model_info = data.get("model") or {}
    model_id = model_info.get("id", "")
    model_display = model_info.get("display_name") or model_id or "?"
    model_short = MODEL_MAP.get(model_id, model_display.replace("claude-", "").replace("-20251001", ""))
    proj = os.path.basename(cwd)

    branch = ""
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            branch = r.stdout.strip()
    except Exception:
        pass

    user_msgs = 0

    transcript = data.get("transcript_path", "")
    if transcript:
        jsonl = Path(transcript)
    else:
        sanitized = cwd.replace("\\", "-").replace("/", "-").replace(":", "-")
        jsonl = Path.home() / ".claude" / "projects" / sanitized / f"{session_id}.jsonl"
    if jsonl.exists():
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
            user_msgs = sum(1 for idx in real_user_indices if idx > last_compact_idx)
        except Exception:
            pass

    if user_msgs >= 80:
        msg_str = f"{RED}🛑 {user_msgs} msgs · new session{RESET}"
    elif user_msgs >= 40:
        msg_str = f"{RED}⚠ {user_msgs} msgs · /compact{RESET}"
    elif user_msgs >= 20:
        msg_str = f"{YELLOW}⚡ {user_msgs} msgs{RESET}"
    else:
        msg_str = f"{DIM}{user_msgs} msgs{RESET}"

    branch_str = f" {DIM}({branch}){RESET}" if branch else ""
    print(f"{CYAN}{model_short}{RESET} {GREEN}{proj}{RESET}{branch_str} | {msg_str}", end="")


if __name__ == "__main__":
    main()
