#!/usr/bin/env python3
"""Analyze collab plan/state/queue artifacts and print recovery advice."""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.errors import dumps_json, error_payload  # noqa: E402
from collab.queue import CollabQueue, QueueError  # noqa: E402
from collab.recover import (  # noqa: E402
    RecoverError,
    build_recovery_report,
    dumps_recovery_json,
    load_json_object,
    render_recovery_markdown,
)
from collab.state import CollabState, StateError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="Plan JSON emitted by collab_plan.py --json.")
    parser.add_argument("--state", type=Path, help="Optional state JSON emitted by collab_plan.py --state-out.")
    parser.add_argument("--queue", type=Path, help="Optional queue JSON emitted by collab_queue.py create.")
    parser.add_argument("--now", help="Timestamp for deterministic stale checks, e.g. 2026-06-20T00:00:00Z.")
    parser.add_argument("--stale-after-seconds", type=int, default=3600)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = load_json_object(args.plan, label="plan")
        state_raw = load_json_object(args.state, label="state") if args.state else None
        queue_raw = load_json_object(args.queue, label="queue") if args.queue else None
        state = CollabState.from_mapping(state_raw) if state_raw and state_raw.get("schema_version") == 1 else None
        queue = CollabQueue.from_mapping(queue_raw) if queue_raw and queue_raw.get("schema_version") == 1 else None
        report = build_recovery_report(
            plan=plan,
            state=state,
            state_raw=state_raw,
            queue=queue,
            queue_raw=queue_raw,
            now=args.now,
            stale_after_seconds=args.stale_after_seconds,
        )
    except (RecoverError, QueueError, StateError) as exc:
        if args.json:
            print(dumps_json(error_payload("collab_recover_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(dumps_recovery_json(report), end="")
    else:
        print(render_recovery_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
