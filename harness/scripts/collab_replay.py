#!/usr/bin/env python3
"""Render a deterministic collaboration replay/runbook from plan + state."""
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
from collab.replay import (  # noqa: E402
    ReplayError,
    build_replay_runbook,
    dumps_runbook_json,
    load_plan,
    render_runbook_markdown,
)
from collab.state import StateError, load_state  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="Plan JSON emitted by collab_plan.py --json.")
    parser.add_argument("--state", type=Path, help="Optional state JSON emitted by collab_plan.py --state-out.")
    parser.add_argument("--adapter", choices=["codex", "claude-code", "orca", "manual"], help="Only include one adapter.")
    parser.add_argument("--include-done", action="store_true", help="Include dispatches already marked done in state.")
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
    except (ReplayError, StateError) as exc:
        if args.json:
            print(dumps_json(error_payload("collab_replay_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(dumps_runbook_json(runbook), end="")
    else:
        print(render_runbook_markdown(runbook), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
