#!/usr/bin/env python3
"""Validate, inspect, or update a collaboration state JSON artifact."""
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

from collab.plan import dumps_plan_json  # noqa: E402
from collab.errors import dumps_json, error_payload  # noqa: E402
from collab.state import (  # noqa: E402
    StateError,
    dumps_state_json,
    load_state,
    save_state,
    summarize_state,
    update_dispatch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path, help="Existing collaboration state JSON path.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--validate", action="store_true", help="Only validate and summarize the state.")
    parser.add_argument("--show", action="store_true", help="Print the full normalized state.")
    parser.add_argument("--out", type=Path, help="Write updated state to a different path; default overwrites --state.")
    parser.add_argument("--dispatch-id", help="Dispatch id to update, for example 01-find.")
    parser.add_argument(
        "--status",
        choices=["pending", "dispatched", "running", "done", "blocked", "error"],
        help="New dispatch status.",
    )
    parser.add_argument("--worker-id", help="Runtime worker id to store.")
    parser.add_argument("--session-id", help="Runtime session id to store.")
    parser.add_argument("--report", help="Short report or evidence pointer to store.")
    parser.add_argument("--updated-at", help="Optional ISO timestamp for stale recovery checks.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        state = load_state(args.state)
        wants_update = any([args.dispatch_id, args.status, args.worker_id, args.session_id, args.report, args.updated_at])
        if wants_update:
            if not args.dispatch_id or not args.status:
                raise StateError("--dispatch-id and --status are required for updates")
            state = update_dispatch(
                state,
                args.dispatch_id,
                status=args.status,
                worker_id=args.worker_id,
                session_id=args.session_id,
                report=args.report,
                updated_at=args.updated_at,
            )
            save_state(state, args.out or args.state)
        if args.show:
            payload = {"kind": "collab_state", "state": state.to_dict()}
        else:
            payload = {
                "kind": "collab_state_summary",
                "state_path": str(args.out or args.state),
                "summary": summarize_state(state),
            }
    except StateError as exc:
        if args.json:
            print(dumps_json(error_payload("collab_state_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(dumps_plan_json(payload), end="")
    elif args.show:
        print(dumps_state_json(state), end="")
    else:
        summary = payload["summary"]
        print(
            f"collab state: {summary['workflow']} plan={summary['plan_id']} "
            f"dispatches={summary['dispatch_count']} all_done={summary['all_done']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
