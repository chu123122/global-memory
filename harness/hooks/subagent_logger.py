#!/usr/bin/env python3
"""
subagent_logger.py — SubagentStart hook（异步）

子代理启动时追加一行 JSON 到 subagent_audit.jsonl。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, append_jsonl, now_iso, LOG_DIR, CLAUDE_DIR

SUBAGENT_FILE = LOG_DIR / "subagent_audit.jsonl"
TURN_FILE = CLAUDE_DIR / ".current_turn.json"


def read_turn_id() -> str:
    try:
        return json.loads(TURN_FILE.read_text(encoding="utf-8")).get("turn_id", "")
    except Exception:
        return ""


def main():
    data = read_hook_input()
    if not data:
        sys.exit(0)

    record = {
        "ts": now_iso(),
        "session": data.get("session_id", ""),
        "turn_id": read_turn_id(),
        "event": "start",
        "agent_type": data.get("agent_type", "unknown"),
        "agent_id": data.get("agent_id", ""),
        "description": (data.get("agent_description") or data.get("description") or "")[:120],
    }

    try:
        append_jsonl(SUBAGENT_FILE, record)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
