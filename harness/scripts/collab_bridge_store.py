#!/usr/bin/env python3
"""Summarize/replay/snapshot Phase 8 collab bridge host event stores."""
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

from collab.bridge_store import (  # noqa: E402
    BridgeStoreError,
    build_store_summary,
    dumps_bridge_store_json,
    load_store_events,
    migrate_event_log,
    replay_store,
    write_materialized_snapshot,
)
from collab.errors import dumps_json, error_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    summary = sub.add_parser("summary", help="Summarize an events JSONL store.")
    summary.add_argument("--events", required=True, type=Path)
    summary.add_argument("--json", action="store_true")

    snapshot = sub.add_parser("snapshot", help="Write a materialized snapshot from events JSONL.")
    snapshot.add_argument("--events", required=True, type=Path)
    snapshot.add_argument("--out", required=True, type=Path)
    snapshot.add_argument("--json", action="store_true")

    replay = sub.add_parser("replay", help="Read and validate a materialized snapshot.")
    replay.add_argument("--snapshot", required=True, type=Path)
    replay.add_argument("--json", action="store_true")

    migrate = sub.add_parser("migrate", help="Report event schema migration status.")
    migrate.add_argument("--events", required=True, type=Path)
    migrate.add_argument("--from-version", type=int, default=1)
    migrate.add_argument("--to-version", type=int, default=1)
    migrate.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "summary":
            payload = build_store_summary(load_store_events(args.events))
        elif args.command == "snapshot":
            payload = write_materialized_snapshot(load_store_events(args.events), args.out)
        elif args.command == "replay":
            payload = replay_store(args.snapshot)
        elif args.command == "migrate":
            session = load_store_events(args.events)
            payload = migrate_event_log(session["events"], from_version=args.from_version, to_version=args.to_version)
        else:  # pragma: no cover - argparse enforces command
            raise BridgeStoreError(f"unknown command: {args.command}")
    except BridgeStoreError as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_bridge_store_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(dumps_bridge_store_json(payload), end="")
    else:
        print(_render_text(payload), end="")
    return 0


def _render_text(payload: dict[str, object]) -> str:
    return dumps_bridge_store_json(payload)


if __name__ == "__main__":
    raise SystemExit(main())
