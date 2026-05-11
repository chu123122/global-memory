#!/usr/bin/env python3
"""
subagent_stop_logger.py — SubagentStop hook

Records subagent completion. Calculates duration_s by matching
agent_id against the SubagentStart entry in subagent_audit.jsonl.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, append_jsonl, now_iso, LOG_DIR

SUBAGENT_FILE = LOG_DIR / "subagent_audit.jsonl"


def find_start_ts(agent_id: str) -> str | None:
    if not SUBAGENT_FILE.exists():
        return None
    try:
        for line in reversed(SUBAGENT_FILE.read_text(encoding="utf-8").strip().splitlines()):
            entry = json.loads(line)
            if entry.get("agent_id") == agent_id and "event" not in entry:
                return entry.get("ts")
    except Exception:
        pass
    return None


def calc_duration(start_ts: str | None, end_ts: str) -> float | None:
    if not start_ts:
        return None
    try:
        from datetime import datetime
        fmt = "%Y-%m-%dT%H:%M:%S"
        s = datetime.fromisoformat(start_ts[:19])
        e = datetime.fromisoformat(end_ts[:19])
        return round((e - s).total_seconds(), 1)
    except Exception:
        return None


def main():
    data = read_hook_input()
    if not data:
        sys.exit(0)

    end_ts = now_iso()
    agent_id = data.get("agent_id", "")
    start_ts = find_start_ts(agent_id)

    record = {
        "ts": end_ts,
        "event": "stop",
        "session": data.get("session_id", ""),
        "agent_type": data.get("agent_type", "unknown"),
        "agent_id": agent_id,
        "duration_s": calc_duration(start_ts, end_ts),
    }

    try:
        append_jsonl(SUBAGENT_FILE, record)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
