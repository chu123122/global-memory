#!/usr/bin/env python3
"""Render a deterministic optional UI-shell model/dashboard from collab artifacts."""
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
from collab.ui_shell import (  # noqa: E402
    UiShellError,
    build_ui_shell_model,
    dumps_ui_shell_json,
    load_ui_shell_inputs,
    render_ui_shell_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="Plan JSON emitted by collab_plan.py --json.")
    parser.add_argument("--state", type=Path, help="Optional state JSON emitted by collab_plan.py --state-out.")
    parser.add_argument("--queue", type=Path, help="Optional queue JSON emitted by collab_queue.py create.")
    parser.add_argument("--recover", type=Path, help="Optional recovery report JSON emitted by collab_recover.py --json.")
    parser.add_argument("--dispatch", type=Path, help="Optional dry-run dispatch packet emitted by collab_dispatch.py --json.")
    parser.add_argument("--report", action="append", default=[], help="Optional dispatch_id=report_pointer mapping; repeatable.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable UI model instead of Markdown dashboard.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan, state, queue, recovery, dispatch = load_ui_shell_inputs(
            plan_path=args.plan,
            state_path=args.state,
            queue_path=args.queue,
            recover_path=args.recover,
            dispatch_path=args.dispatch,
        )
        model = build_ui_shell_model(
            plan=plan,
            state=state,
            queue=queue,
            recovery=recovery,
            dispatch_packet=dispatch,
            report_pointers=_parse_reports(args.report),
            artifact_paths=_artifact_paths(args),
        )
    except UiShellError as exc:
        if args.json:
            print(dumps_json(error_payload("collab_ui_shell_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(dumps_ui_shell_json(model), end="")
    else:
        print(render_ui_shell_markdown(model), end="")
    return 0


def _parse_reports(values: list[str]) -> dict[str, str]:
    reports: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise UiShellError("--report must use dispatch_id=report_pointer")
        dispatch_id, pointer = value.split("=", 1)
        dispatch_id = dispatch_id.strip()
        pointer = pointer.strip()
        if not dispatch_id or not pointer:
            raise UiShellError("--report requires non-empty dispatch_id and report_pointer")
        reports[dispatch_id] = pointer
    return reports


def _artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    paths = {"plan": str(args.plan)}
    for name in ("state", "queue", "recover", "dispatch"):
        value = getattr(args, name)
        if value:
            paths[name] = str(value)
    return paths


if __name__ == "__main__":
    raise SystemExit(main())
