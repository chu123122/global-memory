#!/usr/bin/env python3
"""Product entry and readiness gate for the collab bridge."""
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

from collab.entry import build_product_runbook, build_readiness_report, build_xdmaker_like_readiness_report, dumps_entry_json, run_product_smoke, run_xdmaker_like_smoke  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    runbook = sub.add_parser("runbook")
    runbook.add_argument("--json", action="store_true")
    readiness = sub.add_parser("readiness")
    readiness.add_argument("--runtime-smoke", action="store_true")
    readiness.add_argument("--json", action="store_true")
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--out", required=True, type=Path)
    smoke.add_argument("--allow-spawn", action="store_true")
    smoke.add_argument("--json", action="store_true")
    smoke.add_argument("command_args", nargs=argparse.REMAINDER)
    xready = sub.add_parser("xdmaker-readiness")
    xready.add_argument("--real-worker-e2e", action="store_true")
    xready.add_argument("--supervisor", action="store_true")
    xready.add_argument("--mcp-server", action="store_true")
    xready.add_argument("--mcp-registration", action="store_true")
    xready.add_argument("--mcp-tool-call", action="store_true")
    xready.add_argument("--web-ui", action="store_true")
    xready.add_argument("--persistence", action="store_true")
    xready.add_argument("--claude-blocked", action="store_true")
    xready.add_argument("--json", action="store_true")
    xsmoke = sub.add_parser("xdmaker-smoke")
    xsmoke.add_argument("--out", required=True, type=Path)
    xsmoke.add_argument("--real-worker-evidence", type=Path)
    xsmoke.add_argument("--mcp-registration-evidence", type=Path)
    xsmoke.add_argument("--claude-blocker-evidence", type=Path)
    xsmoke.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "runbook":
            payload = build_product_runbook()
        elif args.command == "readiness":
            payload = build_readiness_report(runtime_smoke=args.runtime_smoke)
        elif args.command == "smoke":
            command = _clean_remainder(args.command_args)
            payload = run_product_smoke(args.out, allow_spawn=args.allow_spawn, command=command or None)
        elif args.command == "xdmaker-readiness":
            payload = build_xdmaker_like_readiness_report(real_worker_e2e=args.real_worker_e2e, supervisor=args.supervisor, mcp_server=args.mcp_server, mcp_registration=args.mcp_registration, mcp_tool_call=args.mcp_tool_call, web_ui=args.web_ui, persistence=args.persistence, claude_blocked=args.claude_blocked)
        elif args.command == "xdmaker-smoke":
            payload = run_xdmaker_like_smoke(args.out, real_worker_evidence=args.real_worker_evidence, mcp_registration_evidence=args.mcp_registration_evidence, claude_blocker_evidence=args.claude_blocker_evidence)
        else:
            raise ValueError(f"unknown command: {args.command}")
    except Exception as exc:
        print(dumps_entry_json({"ok": False, "kind": "collab_entry_error", "error": str(exc), "message": str(exc), "details": {}}), end="")
        return 1
    print(dumps_entry_json(payload), end="")
    return 0


def _clean_remainder(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


if __name__ == "__main__":
    raise SystemExit(main())
