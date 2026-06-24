#!/usr/bin/env python3
"""Select one collab replay action and render a dry-run dispatch packet."""
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
from collab.dispatch import (  # noqa: E402
    DispatchError,
    build_dispatch_packet,
    dumps_dispatch_packet_json,
    render_dispatch_packet_markdown,
)
from collab.replay import ReplayError, build_replay_runbook, load_plan  # noqa: E402
from collab.state import StateError, load_state  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="Plan JSON emitted by collab_plan.py --json.")
    parser.add_argument("--state", type=Path, help="Optional state JSON emitted by collab_plan.py --state-out.")
    parser.add_argument("--dispatch-id", help="Specific dispatch id to select. Defaults to first available action.")
    parser.add_argument("--adapter", choices=["codex", "claude-code", "orca", "manual"], help="Only consider one adapter.")
    parser.add_argument("--include-done", action="store_true", help="Allow done dispatches to be selected.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = load_plan(args.plan)
        state = load_state(args.state) if args.state else None
        runbook = build_replay_runbook(
            plan,
            state=state,
            state_path=args.state,
            include_done=args.include_done,
            adapter=args.adapter,
        )
        packet = build_dispatch_packet(runbook, dispatch_id=args.dispatch_id)
    except (DispatchError, ReplayError, StateError) as exc:
        if args.json:
            print(dumps_json(error_payload("collab_dispatch_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(dumps_dispatch_packet_json(packet), end="")
    else:
        print(render_dispatch_packet_markdown(packet), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
