#!/usr/bin/env python3
"""
panel_api.py — 桌面主控台的本地事件 API

This is intentionally file-based instead of an HTTP server:
- no dependencies
- works when the panel is not running
- safe for AI/CLI tools to call from the repo
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import sys

EVENT_LOG = Path.home() / ".claude" / "logs" / "control_panel_events.jsonl"
OUTCOME_LOG = Path.home() / ".claude" / "logs" / "task_outcomes.jsonl"
LEVELS = {"info", "success", "warning", "error"}
OUTCOMES = {"completed", "partial", "abandoned", "blocked"}
OUTCOME_SCHEMA_VERSION = 1

# Phase 4-A: 调 _lib.py 新增的原子 append + 轮转(避开 panel_api 自己 import _lib 的循环)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import _atomic_append_jsonl, rotate_log  # noqa: E402


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def append_event(record: dict) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def notify(args: argparse.Namespace) -> int:
    level = args.level.lower()
    if level not in LEVELS:
        raise SystemExit(f"invalid level: {args.level}")
    record = {
        "type": "notify",
        "timestamp": now_iso(),
        "source": args.source,
        "level": level,
        "title": args.title,
        "message": args.message,
    }
    if args.data:
        try:
            record["data"] = json.loads(args.data)
        except json.JSONDecodeError:
            record["data"] = args.data
    append_event(record)
    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        print(f"panel event written: [{level}] {args.title}")
    return 0


def outcome(args: argparse.Namespace) -> int:
    """Phase 4-A: 写一条 task outcome 到 ~/.claude/logs/task_outcomes.jsonl

    Schema v1(7 字段最小集,详见 DESIGN §3.2):
      schema_version / ts / task / phase / outcome / metrics / lesson
    """
    if args.outcome not in OUTCOMES:
        raise SystemExit(f"invalid outcome: {args.outcome}; expected one of {sorted(OUTCOMES)}")
    if not args.task:
        raise SystemExit("--task is required")

    record = {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "ts": now_iso(),
        "task": args.task,
        "outcome": args.outcome,
        "metrics": {
            "rework_count": args.rework,
            "tool_calls": args.tools,
            "doc_gate_blocks": args.gate_blocks,
            "memory_writes": args.mem_writes,
            "duration_min": args.duration,
        },
    }
    if args.phase:
        record["phase"] = args.phase
    if args.lesson:
        record["lesson"] = args.lesson

    # 轮转(本场景几乎不会触发,但工具铺设到位)
    rotate_log(OUTCOME_LOG, max_size_bytes=5 * 1024 * 1024, max_lines=10000, keep=3)
    # 原子 append(跨平台锁,_lib 实现)
    _atomic_append_jsonl(OUTCOME_LOG, record)

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        phase_tag = f" phase={args.phase}" if args.phase else ""
        print(f"outcome appended: task={args.task}{phase_tag} outcome={args.outcome}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="local event API for harness control panel")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_notify = sub.add_parser("notify", help="send a notification event to the panel")
    p_notify.add_argument("--source", default="external-ai", help="event source shown in the panel")
    p_notify.add_argument("--level", default="info", choices=sorted(LEVELS))
    p_notify.add_argument("--title", required=True)
    p_notify.add_argument("--message", required=True)
    p_notify.add_argument("--data", default="", help="optional JSON payload or plain text")
    p_notify.add_argument("--json", action="store_true")
    p_notify.set_defaults(func=notify)

    p_outcome = sub.add_parser("outcome", help="append a task outcome record (Phase 4-A)")
    p_outcome.add_argument("--task", required=True, help="task name (matches active_tasks)")
    p_outcome.add_argument("--phase", default="", help="phase identifier, e.g. '0' or '1-A'")
    p_outcome.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    p_outcome.add_argument("--rework", type=int, default=0, help="rework_count metric")
    p_outcome.add_argument("--tools", type=int, default=0, help="tool_calls metric")
    p_outcome.add_argument("--gate-blocks", type=int, default=0, help="doc_gate_blocks metric")
    p_outcome.add_argument("--mem-writes", type=int, default=0, help="memory_writes metric")
    p_outcome.add_argument("--duration", type=int, default=0, help="duration_min metric")
    p_outcome.add_argument("--lesson", default="", help="one-line lesson learned (optional)")
    p_outcome.add_argument("--json", action="store_true")
    p_outcome.set_defaults(func=outcome)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
