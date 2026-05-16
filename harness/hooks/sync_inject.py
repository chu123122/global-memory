#!/usr/bin/env python3
"""
sync_inject.py — UserPromptSubmit hook for multi-agent task sync.

Reads tasks_root from project_registry.json (not hardcoded).
Scans active task directories for .sync.jsonl, shows active locks
and recent events (last 30 min). Silent when nothing to show.
"""

import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SYNC_FILE = ".sync.jsonl"
RECENCY_MINUTES = 30
LOCK_EXPIRE_HOURS = 2


def get_tasks_root():
    """Read tasks_root from project_registry.json, fallback to env var."""
    env = os.environ.get("CLAUDE_TASKS_ROOT")
    if env:
        return Path(env)
    registry = Path.home() / ".claude" / "projects" / "project_registry.json"
    if registry.exists():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
            root = data.get("tasks_root")
            if root:
                return Path(root)
        except Exception:
            pass
    return None


def parse_ts(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def relative_time(ts, now):
    delta = now - ts
    mins = int(delta.total_seconds() / 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}min ago"
    return f"{mins // 60}h{mins % 60}m ago"


def process_task(task_dir, now):
    sync_file = task_dir / SYNC_FILE
    if not sync_file.exists():
        return None, []

    expire = timedelta(hours=LOCK_EXPIRE_HOURS)
    recency = timedelta(minutes=RECENCY_MINUTES)

    locks = {}
    recent = []

    try:
        lines = sync_file.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return None, []

    for line in lines:
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = parse_ts(e.get("ts", ""))
        event = e.get("event", "")
        resource = e.get("resource", "")

        if resource and event == "lock":
            if now - ts < expire:
                locks[resource] = e
            else:
                locks.pop(resource, None)
        elif resource and event == "unlock":
            locks.pop(resource, None)

        if now - ts < recency and event != "unlock":
            recent.append(e)

    return locks, recent[-5:]


EVENT_ICONS = {
    "change": "📝", "decision": "💡", "blocker": "🚧",
    "lock": "🔒", "session_end": "👋",
    "claim_step": "🏁", "complete_step": "✅",
}


def main():
    sys.stdin.read()

    tasks_root = get_tasks_root()
    if not tasks_root or not tasks_root.is_dir():
        return

    now = datetime.now(timezone.utc)
    output_blocks = []

    try:
        task_dirs = sorted(tasks_root.iterdir())
    except Exception:
        return

    for task_dir in task_dirs:
        if not task_dir.is_dir():
            continue
        locks, recent = process_task(task_dir, now)
        if not locks and not recent:
            continue

        lines = []
        task_name = task_dir.name

        for resource, e in (locks or {}).items():
            agent = e.get("agent", "?")
            detail = e.get("detail", "")
            ts = parse_ts(e.get("ts", ""))
            det = f": \"{detail}\"" if detail else ""
            lines.append(f"  🔒 {resource} locked by {agent}{det} ({relative_time(ts, now)})")

        for e in recent:
            event = e.get("event", "")
            if event in ("lock", "unlock"):
                continue
            agent = e.get("agent", "?")
            detail = e.get("detail", "")
            ts = parse_ts(e.get("ts", ""))
            icon = EVENT_ICONS.get(event, "📌")
            det = f" — {detail}" if detail else ""
            lines.append(f"  {icon} {agent}: {event}{det} ({relative_time(ts, now)})")

        if lines:
            output_blocks.append(f"⚡ Task Sync [{task_name}]:\n" + "\n".join(lines))

    if output_blocks:
        print("\n".join(output_blocks))


if __name__ == "__main__":
    main()
