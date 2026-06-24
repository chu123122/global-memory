#!/usr/bin/env python3
"""Operate the Phase 11 collab router and report loop."""
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

from collab.bridge_host import load_session_events, save_session_events  # noqa: E402
from collab.errors import dumps_json, error_payload  # noqa: E402
from collab.router import (  # noqa: E402
    RouterError,
    acknowledge_message,
    build_router_snapshot,
    dumps_router_json,
    enqueue_message,
    fail_message,
    ingest_router_report,
    retry_message,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--events", required=True, type=Path)
    snapshot.add_argument("--json", action="store_true")
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--events", required=True, type=Path)
    enqueue.add_argument("--worker-id", required=True)
    enqueue.add_argument("--message", required=True)
    enqueue.add_argument("--correlation-id")
    enqueue.add_argument("--dedupe-key")
    enqueue.add_argument("--now")
    enqueue.add_argument("--json", action="store_true")
    ack = sub.add_parser("ack")
    ack.add_argument("--events", required=True, type=Path)
    ack.add_argument("--message-id", required=True)
    ack.add_argument("--ack-id")
    ack.add_argument("--now")
    ack.add_argument("--json", action="store_true")
    fail = sub.add_parser("fail")
    fail.add_argument("--events", required=True, type=Path)
    fail.add_argument("--message-id", required=True)
    fail.add_argument("--error", required=True)
    fail.add_argument("--no-retry", action="store_true")
    fail.add_argument("--now")
    fail.add_argument("--json", action="store_true")
    retry = sub.add_parser("retry")
    retry.add_argument("--events", required=True, type=Path)
    retry.add_argument("--message-id", required=True)
    retry.add_argument("--now")
    retry.add_argument("--json", action="store_true")
    report = sub.add_parser("report")
    report.add_argument("--events", required=True, type=Path)
    report.add_argument("--worker-id", required=True)
    report.add_argument("--report", required=True)
    report.add_argument("--status", default="done")
    report.add_argument("--now")
    report.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        session = load_session_events(args.events)
        updated = False
        if args.command == "snapshot":
            payload = build_router_snapshot(session)
        elif args.command == "enqueue":
            session, result = enqueue_message(session, args.worker_id, args.message, correlation_id=args.correlation_id, dedupe_key=args.dedupe_key, now=args.now)
            updated = True
            payload = _payload(session, result, updated)
        elif args.command == "ack":
            session, result = acknowledge_message(session, args.message_id, ack_id=args.ack_id, now=args.now)
            updated = True
            payload = _payload(session, result, updated)
        elif args.command == "fail":
            session, result = fail_message(session, args.message_id, args.error, retryable=not args.no_retry, now=args.now)
            updated = True
            payload = _payload(session, result, updated)
        elif args.command == "retry":
            session, result = retry_message(session, args.message_id, now=args.now)
            updated = True
            payload = _payload(session, result, updated)
        elif args.command == "report":
            session, result = ingest_router_report(session, args.worker_id, args.report, status=args.status, now=args.now)
            updated = True
            payload = _payload(session, result, updated)
        else:
            raise RouterError(f"unknown command: {args.command}")
        if updated:
            save_session_events(session, args.events)
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_router_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(dumps_router_json(payload), end="")
    return 0


def _payload(session, result, updated):
    return {"schema_version": 1, "kind": "collab_router_operation", "phase": 11, "event_log_updated": updated, "result": result, "snapshot": build_router_snapshot(session)}


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, RouterError):
        return exc
    return RouterError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
