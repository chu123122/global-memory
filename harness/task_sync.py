#!/usr/bin/env python3
"""
task_sync.py — 多 Agent 任务同步 CLI

Provides a shared event stream (.sync.jsonl) for multiple Claude terminals
working on the same task. Supports locks, change notifications, decisions.

Usage:
  python task_sync.py append <task_dir> <event> --detail "..." [--resource R] [--agent NAME]
  python task_sync.py read <task_dir> [--last N]
  python task_sync.py locks <task_dir>
  python task_sync.py release <task_dir> <resource> [--agent NAME]

Events: lock, unlock, change, decision, blocker, session_end
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import _atomic_append_jsonl  # noqa: E402

SYNC_FILE = ".sync.jsonl"
LOCK_EXPIRE_HOURS = 2
VALID_EVENTS = {"lock", "unlock", "change", "decision", "blocker", "session_end", "claim_step", "complete_step"}


def get_agent_name(args_agent=None):
    if args_agent:
        return args_agent
    env = os.environ.get("CLAUDE_SYNC_AGENT")
    if env:
        return env
    return f"PID-{os.getpid()}"


def sync_path(task_dir):
    return Path(task_dir).resolve() / SYNC_FILE


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def read_tail(path, n=20):
    if not path.exists():
        return []
    lines = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        return lines[-n:]
    except Exception:
        return []


def cmd_append(args):
    agent = get_agent_name(args.agent)
    entry = {
        "ts": now_iso(),
        "agent": agent,
        "event": args.event,
    }
    if args.resource:
        entry["resource"] = args.resource
    if args.detail:
        entry["detail"] = args.detail

    path = sync_path(args.task_dir)
    _atomic_append_jsonl(path, entry)
    print(f"✅ {args.event} recorded by {agent}")


def cmd_read(args):
    path = sync_path(args.task_dir)
    lines = read_tail(path, args.last)
    if not lines:
        print("(no sync events)")
        return
    for line in lines:
        try:
            e = json.loads(line)
            ts = e.get("ts", "?")
            agent = e.get("agent", "?")
            event = e.get("event", "?")
            resource = e.get("resource", "")
            detail = e.get("detail", "")
            res_str = f" [{resource}]" if resource else ""
            det_str = f" — {detail}" if detail else ""
            print(f"  {ts} {agent}: {event}{res_str}{det_str}")
        except json.JSONDecodeError:
            continue


def get_active_locks(path):
    """Return dict of resource → lock entry for unexpired, unreleased locks."""
    if not path.exists():
        return {}

    locks = {}
    now = datetime.now(timezone.utc)
    expire = timedelta(hours=LOCK_EXPIRE_HOURS)

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = e.get("event")
                resource = e.get("resource")
                if not resource:
                    continue
                if event == "lock":
                    ts = parse_ts(e.get("ts", ""))
                    if now - ts < expire:
                        locks[resource] = e
                    else:
                        locks.pop(resource, None)
                elif event == "unlock":
                    locks.pop(resource, None)
    except Exception:
        pass
    return locks


def cmd_locks(args):
    path = sync_path(args.task_dir)
    locks = get_active_locks(path)
    if not locks:
        print("(no active locks)")
        return
    now = datetime.now(timezone.utc)
    for resource, e in locks.items():
        agent = e.get("agent", "?")
        detail = e.get("detail", "")
        ts = parse_ts(e.get("ts", ""))
        mins = int((now - ts).total_seconds() / 60)
        det_str = f" — {detail}" if detail else ""
        print(f"  🔒 {resource} locked by {agent}{det_str} ({mins}min ago)")


def cmd_release(args):
    agent = get_agent_name(args.agent)
    entry = {
        "ts": now_iso(),
        "agent": agent,
        "event": "unlock",
        "resource": args.resource,
    }
    path = sync_path(args.task_dir)
    _atomic_append_jsonl(path, entry)
    print(f"🔓 {args.resource} released by {agent}")


def main():
    parser = argparse.ArgumentParser(description="Multi-agent task sync")
    sub = parser.add_subparsers(dest="command")

    p_append = sub.add_parser("append")
    p_append.add_argument("task_dir")
    p_append.add_argument("event", choices=sorted(VALID_EVENTS))
    p_append.add_argument("--resource", default="")
    p_append.add_argument("--detail", default="")
    p_append.add_argument("--agent", default=None)

    p_read = sub.add_parser("read")
    p_read.add_argument("task_dir")
    p_read.add_argument("--last", type=int, default=20)

    p_locks = sub.add_parser("locks")
    p_locks.add_argument("task_dir")

    p_release = sub.add_parser("release")
    p_release.add_argument("task_dir")
    p_release.add_argument("resource")
    p_release.add_argument("--agent", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    {"append": cmd_append, "read": cmd_read, "locks": cmd_locks, "release": cmd_release}[args.command](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
