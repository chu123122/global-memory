#!/usr/bin/env python3
"""Operate a Phase 7 local collab bridge host session over fake/manual runtime."""
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

from collab.bridge_host import (  # noqa: E402
    BridgeHostError,
    create_session_from_blueprint,
    dumps_bridge_host_json,
    focus_worker,
    ingest_worker_report,
    load_session_events,
    materialize_bridge_host,
    save_session_events,
    send_worker_message,
)
from collab.errors import dumps_json, error_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a local bridge host session from a worker launch blueprint.")
    create.add_argument("--blueprint", required=True, type=Path)
    create.add_argument("--events", required=True, type=Path)
    create.add_argument("--worker-limit", type=int, default=None)
    create.add_argument("--runtime-mode", choices=["fake", "manual"], default="fake")
    create.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Show the current local bridge host view model.")
    show.add_argument("--events", required=True, type=Path)
    show.add_argument("--json", action="store_true")

    focus = sub.add_parser("focus", help="Focus a worker.")
    focus.add_argument("--events", required=True, type=Path)
    focus.add_argument("--worker-id", required=True)
    focus.add_argument("--json", action="store_true")

    send = sub.add_parser("send", help="Append a fake/manual message to a worker.")
    send.add_argument("--events", required=True, type=Path)
    send.add_argument("--worker-id", required=True)
    send.add_argument("--message", required=True)
    send.add_argument("--now")
    send.add_argument("--json", action="store_true")

    report = sub.add_parser("report", help="Ingest a worker report pointer.")
    report.add_argument("--events", required=True, type=Path)
    report.add_argument("--worker-id", required=True)
    report.add_argument("--report", required=True)
    report.add_argument("--status", default="done")
    report.add_argument("--now")
    report.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            blueprint = _load_blueprint(args.blueprint)
            session = create_session_from_blueprint(blueprint, worker_limit=args.worker_limit, runtime_mode=args.runtime_mode)
        else:
            session = load_session_events(args.events)
            if args.command == "focus":
                session = focus_worker(session, args.worker_id)
            elif args.command == "send":
                session = send_worker_message(session, args.worker_id, args.message, now=args.now)
            elif args.command == "report":
                session = ingest_worker_report(session, args.worker_id, args.report, status=args.status, now=args.now)
        if args.command != "show":
            save_session_events(session, args.events)
        model = materialize_bridge_host(session)
    except BridgeHostError as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_bridge_host_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(dumps_bridge_host_json(model), end="")
    else:
        print(_render_markdown(model), end="")
    return 0


def _load_blueprint(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BridgeHostError(f"failed to read blueprint {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BridgeHostError(f"blueprint {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BridgeHostError("blueprint root must be an object")
    return payload


def _render_markdown(model: dict[str, object]) -> str:
    lines = [
        "# Collaboration Bridge Host",
        "",
        f"Workflow: `{model.get('workflow')}`",
        f"Plan ID: `{model.get('plan_id')}`",
        f"Focused worker: `{model.get('focused_worker_id')}`",
        "",
        "| worker | agent | status | messages | report |",
        "|---|---|---|---:|---|",
    ]
    for row in model.get("worker_rows", []):
        lines.append(f"| `{row['worker_id']}` | {row['agent']} | {row['status']} | {row['message_count']} | {row.get('report_pointer') or ''} |")
    return "\n".join(lines).rstrip() + "\n"



if __name__ == "__main__":
    raise SystemExit(main())
