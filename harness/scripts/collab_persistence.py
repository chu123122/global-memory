#!/usr/bin/env python3
"""Manage Phase 17 SQLite persistence for collab bridge events."""
from __future__ import annotations

import argparse
import io
import json
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
from collab.persistence import (  # noqa: E402
    PersistenceError,
    append_persistent_event,
    dumps_persistence_json,
    export_event_log,
    import_event_log,
    init_persistence,
    list_persistent_sessions,
    migrate_persistence,
    recover_persistence,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--db", required=True, type=Path)
    init.add_argument("--json", action="store_true")
    imp = sub.add_parser("import")
    imp.add_argument("--db", required=True, type=Path)
    imp.add_argument("--session-id", required=True)
    imp.add_argument("--events", required=True, type=Path)
    imp.add_argument("--json", action="store_true")
    exp = sub.add_parser("export")
    exp.add_argument("--db", required=True, type=Path)
    exp.add_argument("--session-id", required=True)
    exp.add_argument("--events", required=True, type=Path)
    exp.add_argument("--json", action="store_true")
    append = sub.add_parser("append")
    append.add_argument("--db", required=True, type=Path)
    append.add_argument("--session-id", required=True)
    append.add_argument("--event-json", required=True)
    append.add_argument("--json", action="store_true")
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--db", required=True, type=Path)
    list_cmd.add_argument("--json", action="store_true")
    migrate = sub.add_parser("migrate")
    migrate.add_argument("--db", required=True, type=Path)
    migrate.add_argument("--json", action="store_true")
    recover = sub.add_parser("recover")
    recover.add_argument("--db", required=True, type=Path)
    recover.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            payload = init_persistence(args.db)
        elif args.command == "import":
            payload = import_event_log(args.db, args.session_id, args.events)
        elif args.command == "export":
            payload = export_event_log(args.db, args.session_id, args.events)
        elif args.command == "append":
            event = _event_json(args.event_json)
            payload = append_persistent_event(args.db, args.session_id, event)
        elif args.command == "list":
            payload = list_persistent_sessions(args.db)
        elif args.command == "migrate":
            payload = migrate_persistence(args.db)
        elif args.command == "recover":
            payload = recover_persistence(args.db)
        else:
            raise PersistenceError(f"unknown command: {args.command}")
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_persistence_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(dumps_persistence_json(payload), end="")
    return 0


def _event_json(value: str) -> dict[str, object]:
    raw = value
    path = Path(value)
    if path.exists():
        raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise PersistenceError("event JSON must be an object")
    return payload


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, PersistenceError):
        return exc
    return PersistenceError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
