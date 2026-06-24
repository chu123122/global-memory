#!/usr/bin/env python3
"""Run Phase 14 worker supervisor scenarios."""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.errors import dumps_json, error_payload  # noqa: E402
from collab.worker_supervisor import (  # noqa: E402
    WorkerSupervisor,
    WorkerSupervisorError,
    append_supervisor_events,
    build_supervisor_snapshot,
    dumps_supervisor_json,
    load_supervisor_events,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)
    scenario = sub.add_parser("scenario", help="Run start/status/send/read/stop in one supervisor process.")
    scenario.add_argument("--events", required=True, type=Path)
    scenario.add_argument("--worker-id", default="worker-01-find")
    scenario.add_argument("--message")
    scenario.add_argument("--sleep", type=float, default=0.15)
    scenario.add_argument("--timeout-seconds", type=float)
    scenario.add_argument("--json", action="store_true")
    scenario.add_argument("command", nargs=argparse.REMAINDER)
    crash = sub.add_parser("crash-scenario", help="Run a command expected to exit non-zero and capture crash status.")
    crash.add_argument("--events", required=True, type=Path)
    crash.add_argument("--worker-id", default="worker-01-find")
    crash.add_argument("--sleep", type=float, default=0.15)
    crash.add_argument("--json", action="store_true")
    crash.add_argument("command", nargs=argparse.REMAINDER)
    timeout = sub.add_parser("timeout-scenario", help="Run a command and enforce supervisor timeout.")
    timeout.add_argument("--events", required=True, type=Path)
    timeout.add_argument("--worker-id", default="worker-01-find")
    timeout.add_argument("--timeout-seconds", type=float, default=0.1)
    timeout.add_argument("--sleep", type=float, default=0.25)
    timeout.add_argument("--json", action="store_true")
    timeout.add_argument("command", nargs=argparse.REMAINDER)
    snapshot = sub.add_parser("snapshot", help="Replay a supervisor event log.")
    snapshot.add_argument("--events", required=True, type=Path)
    snapshot.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command_name == "snapshot":
            payload = build_supervisor_snapshot(load_supervisor_events(args.events))
        elif args.command_name == "scenario":
            payload = _run_scenario(args, mode="normal")
        elif args.command_name == "crash-scenario":
            payload = _run_scenario(args, mode="crash")
        elif args.command_name == "timeout-scenario":
            payload = _run_scenario(args, mode="timeout")
        else:
            raise WorkerSupervisorError(f"unknown command: {args.command_name}")
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_worker_supervisor_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(dumps_supervisor_json(payload), end="")
    return 0


def _run_scenario(args: argparse.Namespace, *, mode: str) -> dict[str, object]:
    command = _clean_remainder(args.command)
    if not command:
        raise WorkerSupervisorError("command is required after --")
    supervisor = WorkerSupervisor()
    events = []
    events.append(supervisor.start_worker(args.worker_id, command, timeout_seconds=getattr(args, "timeout_seconds", None)))
    events.append(supervisor.worker_status(args.worker_id))
    if mode == "normal" and args.message:
        events.append(supervisor.send_to_worker(args.worker_id, args.message))
    time.sleep(float(args.sleep))
    if mode == "timeout":
        timeout_event = supervisor.enforce_timeout(args.worker_id)
        if timeout_event:
            events.append(timeout_event)
    events.append(supervisor.read_worker(args.worker_id))
    if mode == "normal":
        events.append(supervisor.stop_worker(args.worker_id))
    append_supervisor_events(args.events, events)
    all_events = load_supervisor_events(args.events)
    return {"schema_version": 1, "kind": "collab_worker_supervisor_scenario", "phase": 14, "mode": mode, "events_written": len(events), "snapshot": build_supervisor_snapshot(all_events)}


def _clean_remainder(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, WorkerSupervisorError):
        return exc
    return WorkerSupervisorError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
