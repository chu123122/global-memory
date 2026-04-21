#!/usr/bin/env python3
"""
subagent_logger.py — SubagentStart hook（异步）

子代理启动时追加一行 JSON 到 subagent_audit.jsonl。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, append_jsonl, now_iso, LOG_DIR

SUBAGENT_FILE = LOG_DIR / "subagent_audit.jsonl"


def main():
    data = read_hook_input()
    if not data:
        sys.exit(0)

    record = {
        "ts": now_iso(),
        "session": data.get("session_id", ""),
        "agent_type": data.get("agent_type", "unknown"),
        "agent_id": data.get("agent_id", ""),
    }

    try:
        append_jsonl(SUBAGENT_FILE, record)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
