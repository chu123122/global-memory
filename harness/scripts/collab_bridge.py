#!/usr/bin/env python3
"""Emit standalone collab bridge spec and optional worker launch blueprint."""
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

from collab.bridge import (  # noqa: E402
    BridgeError,
    build_standalone_bridge_bundle,
    dumps_bridge_json,
    load_bridge_plan,
    render_bridge_markdown,
)
from collab.errors import dumps_json, error_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, help="Optional plan JSON emitted by collab_plan.py --json.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable bridge spec/bundle instead of Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = load_bridge_plan(args.plan) if args.plan else None
        bundle = build_standalone_bridge_bundle(plan)
    except BridgeError as exc:
        if args.json:
            print(dumps_json(error_payload("collab_bridge_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(dumps_bridge_json(bundle), end="")
    else:
        print(render_bridge_markdown(bundle), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
