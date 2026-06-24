#!/usr/bin/env python3
"""Probe and call the Phase 10 lead CLI MCP-style collab bridge."""
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
from collab.mcp_bridge import (  # noqa: E402
    LeadCliMcpError,
    build_lead_cli_mcp_schema,
    call_bridge_tool,
    dumps_lead_cli_mcp_json,
    load_args_json,
    probe_lead_cli_mcp,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema", help="Emit MCP-style bridge tool schema.")
    schema.add_argument("--json", action="store_true")

    probe = sub.add_parser("probe", help="Probe bridge-side MCP readiness without claiming lead CLI registration.")
    probe.add_argument("--events", type=Path)
    probe.add_argument("--json", action="store_true")

    call = sub.add_parser("call", help="Call one MCP-style bridge tool against an events JSONL session.")
    call.add_argument("--events", required=True, type=Path)
    call.add_argument("--tool", required=True)
    call.add_argument("--args-json", required=True)
    call.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "schema":
            payload = build_lead_cli_mcp_schema()
        elif args.command == "probe":
            session = load_session_events(args.events) if args.events else None
            payload = probe_lead_cli_mcp(session)
        elif args.command == "call":
            session = load_session_events(args.events)
            payload, session, updated = call_bridge_tool(session, args.tool, load_args_json(args.args_json))
            if updated:
                save_session_events(session, args.events)
        else:  # pragma: no cover - argparse enforces command
            raise LeadCliMcpError(f"unknown command: {args.command}")
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_lead_cli_mcp_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(dumps_lead_cli_mcp_json(payload), end="")
    return 0


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, LeadCliMcpError):
        return exc
    return LeadCliMcpError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
