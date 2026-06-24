#!/usr/bin/env python3
"""Run the Phase 15 real stdio MCP server for collab bridge tools."""
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
from collab.mcp_server import (  # noqa: E402
    RealMcpServerError,
    build_codex_mcp_exec_probe_command,
    build_mcp_server_config,
    classify_codex_mcp_exec_probe,
    dumps_mcp_server_json,
    run_mcp_self_test,
    run_stdio_server,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--events", required=True, type=Path)
    config = sub.add_parser("config")
    config.add_argument("--events", required=True, type=Path)
    config.add_argument("--json", action="store_true")
    self_test = sub.add_parser("self-test")
    self_test.add_argument("--events", required=True, type=Path)
    self_test.add_argument("--json", action="store_true")
    probe_cmd = sub.add_parser("codex-probe-command")
    probe_cmd.add_argument("--events", required=True, type=Path)
    probe_cmd.add_argument("--workdir", required=True, type=Path)
    probe_cmd.add_argument("--output-file", required=True, type=Path)
    probe_cmd.add_argument("--approval-policy", default="never")
    probe_cmd.add_argument("--json", action="store_true")
    classify = sub.add_parser("classify-codex-probe")
    classify.add_argument("--stdout-file", type=Path)
    classify.add_argument("--stderr-file", type=Path)
    classify.add_argument("--output-file", type=Path)
    classify.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "serve":
            return run_stdio_server(args.events)
        if args.command == "config":
            payload = build_mcp_server_config(args.events)
        elif args.command == "self-test":
            payload = run_mcp_self_test(args.events)
        elif args.command == "codex-probe-command":
            payload = build_codex_mcp_exec_probe_command(args.events, workdir=args.workdir, output_file=args.output_file, approval_policy=args.approval_policy)
        elif args.command == "classify-codex-probe":
            payload = classify_codex_mcp_exec_probe(stdout=_read_optional(args.stdout_file), stderr=_read_optional(args.stderr_file), output_text=_read_optional(args.output_file))
        else:
            raise RealMcpServerError(f"unknown command: {args.command}")
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_mcp_server_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(dumps_mcp_server_json(payload), end="")
    return 0


def _read_optional(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, RealMcpServerError):
        return exc
    return RealMcpServerError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
