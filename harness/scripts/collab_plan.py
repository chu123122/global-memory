#!/usr/bin/env python3
"""Generate or validate host-neutral collaboration dispatch plans."""
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

from collab.adapters import build_adapter_payloads  # noqa: E402
from collab.config import ConfigError, load_config  # noqa: E402
from collab.errors import dumps_json, error_payload  # noqa: E402
from collab.plan import build_dispatch_plan, dumps_plan_json, render_plan_markdown  # noqa: E402
from collab.state import StateError, save_state, state_from_plan  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Optional JSON config path; defaults to built-in five-agent config.")
    parser.add_argument("--intent", default="Coordinate a global-memory collaboration task.")
    parser.add_argument("--decision", action="append", default=[], help="Decision to include; repeatable.")
    parser.add_argument("--boundary", action="append", default=[], help="Boundary to include; repeatable.")
    parser.add_argument("--task", default="Execute the assigned collaboration role and report only decisive evidence.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of Markdown.")
    parser.add_argument("--validate", action="store_true", help="Only validate the config and return the normalized config.")
    parser.add_argument(
        "--adapter-payloads",
        action="store_true",
        help="Include declarative runtime-shaped adapter payloads; this does not call runtime tools.",
    )
    parser.add_argument(
        "--state-out",
        type=Path,
        help="Optional path for an initial pending collaboration state JSON file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.validate:
            payload = config.to_dict()
            if args.json:
                print(dumps_plan_json({"kind": "collab_config", "config": payload}), end="")
            else:
                print("collab config: OK")
            return 0
        plan = build_dispatch_plan(
            config,
            intent=args.intent,
            decisions=args.decision,
            boundaries=args.boundary,
            task=args.task,
        )
        if args.adapter_payloads:
            plan["adapter_payloads"] = build_adapter_payloads(plan)
        if args.state_out:
            state = state_from_plan(plan)
            save_state(state, args.state_out)
            plan["state_path"] = str(args.state_out)
    except (ConfigError, StateError, KeyError, TypeError) as exc:
        if args.json:
            print(dumps_json(error_payload("collab_plan_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(dumps_plan_json(plan), end="")
    else:
        markdown = render_plan_markdown(plan)
        if args.adapter_payloads:
            markdown += render_adapter_payloads_markdown(plan["adapter_payloads"])
        if args.state_out:
            markdown += f"\nState written: `{args.state_out}`\n"
        print(markdown, end="")
    return 0


def render_adapter_payloads_markdown(payloads: list[dict[str, object]]) -> str:
    lines = ["", "## Adapter Payloads"]
    for payload in payloads:
        tool = payload.get("tool")
        tool_name = tool.get("name") if isinstance(tool, dict) else "manual"
        lines.extend(
            [
                "",
                f"### {payload.get('dispatch_id')}",
                f"- adapter: {payload.get('adapter')}",
                f"- tool: {tool_name}",
                f"- spawns_process: {payload.get('spawns_process')}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
