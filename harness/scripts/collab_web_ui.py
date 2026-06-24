#!/usr/bin/env python3
"""Serve or smoke-test the Phase 16 local collab web UI."""
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
from collab.web_ui import WebUiError, dumps_web_ui_json, run_web_ui_smoke, serve_web_ui  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--events", required=True, type=Path)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--out", required=True, type=Path)
    smoke.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "serve":
            server = serve_web_ui(args.events, host=args.host, port=args.port)
            print(f"Serving collab UI on http://{args.host}:{server.server_address[1]}", file=sys.stderr)
            server.serve_forever()
            return 0
        if args.command == "smoke":
            payload = run_web_ui_smoke(args.out)
        else:
            raise WebUiError(f"unknown command: {args.command}")
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_web_ui_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(dumps_web_ui_json(payload), end="")
    return 0


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, WebUiError):
        return exc
    return WebUiError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
