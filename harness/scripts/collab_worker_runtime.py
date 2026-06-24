#!/usr/bin/env python3
"""Run Phase 9 standalone collab worker runtime commands."""
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
from collab.worker_runtime import (  # noqa: E402
    WorkerRuntimeError,
    apply_runtime_result,
    build_runtime_run_payload,
    build_worker_runtime_request,
    dumps_worker_runtime_json,
    run_worker_command,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)

    request = sub.add_parser("request", help="Build a non-spawning worker runtime request.")
    request.add_argument("--events", required=True, type=Path)
    request.add_argument("--worker-id", required=True)
    request.add_argument("--cwd", type=Path)
    request.add_argument("--timeout-seconds", type=float, default=30.0)
    request.add_argument("--json", action="store_true")
    request.add_argument("command", nargs=argparse.REMAINDER)

    run = sub.add_parser("run", help="Run an explicit operator-configured worker command.")
    run.add_argument("--events", required=True, type=Path)
    run.add_argument("--worker-id", required=True)
    run.add_argument("--allow-spawn", action="store_true")
    run.add_argument("--timeout-seconds", type=float, default=30.0)
    run.add_argument("--cwd", type=Path)
    run.add_argument("--no-update-events", action="store_true")
    run.add_argument("--now")
    run.add_argument("--json", action="store_true")
    run.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        session = load_session_events(args.events)
        command = _clean_remainder(args.command)
        if args.command_name == "request":
            payload = build_worker_runtime_request(
                session,
                args.worker_id,
                command,
                cwd=args.cwd,
                timeout_seconds=args.timeout_seconds,
            )
        elif args.command_name == "run":
            result = run_worker_command(
                session,
                args.worker_id,
                command,
                allow_spawn=args.allow_spawn,
                timeout_seconds=args.timeout_seconds,
                cwd=args.cwd,
            )
            updated = not args.no_update_events
            if updated:
                session = apply_runtime_result(session, result, now=args.now)
                save_session_events(session, args.events)
            payload = build_runtime_run_payload(session, result, event_log_updated=updated)
        else:  # pragma: no cover - argparse enforces command
            raise WorkerRuntimeError(f"unknown command: {args.command_name}")
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_worker_runtime_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(dumps_worker_runtime_json(payload), end="")
    else:
        print(dumps_worker_runtime_json(payload), end="")
    return 0


def _clean_remainder(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, WorkerRuntimeError):
        return exc
    return WorkerRuntimeError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
