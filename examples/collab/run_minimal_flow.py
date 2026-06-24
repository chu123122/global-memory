#!/usr/bin/env python3
"""Run a minimal headless collab plan -> state -> queue -> recover flow."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / ".tmp" / "collab-example")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    plan = out / "plan.json"
    state = out / "state.json"
    queue = out / "queue.json"
    recover = out / "recover.json"
    dispatch = out / "dispatch.json"

    _run([
        sys.executable,
        str(ROOT / "harness" / "scripts" / "collab_plan.py"),
        "--intent",
        "Phase 4 executable example",
        "--adapter-payloads",
        "--state-out",
        str(state),
        "--json",
    ], stdout_path=plan)
    _run([sys.executable, str(ROOT / "harness" / "scripts" / "collab_queue.py"), "create", "--plan", str(plan), "--queue", str(queue), "--json"])
    _run([
        sys.executable,
        str(ROOT / "harness" / "scripts" / "collab_queue.py"),
        "lease",
        "--queue",
        str(queue),
        "--worker-id",
        "example-worker",
        "--now",
        "2026-06-20T00:00:00Z",
        "--json",
    ])
    _run([
        sys.executable,
        str(ROOT / "harness" / "scripts" / "collab_state.py"),
        "--state",
        str(state),
        "--dispatch-id",
        "01-find",
        "--status",
        "running",
        "--worker-id",
        "example-worker",
        "--updated-at",
        "2026-06-20T00:00:00Z",
        "--json",
    ])
    _run([
        sys.executable,
        str(ROOT / "harness" / "scripts" / "collab_recover.py"),
        "--plan",
        str(plan),
        "--state",
        str(state),
        "--queue",
        str(queue),
        "--now",
        "2026-06-20T02:00:00Z",
        "--json",
    ], stdout_path=recover)
    _run([
        sys.executable,
        str(ROOT / "harness" / "scripts" / "collab_dispatch.py"),
        "--plan",
        str(plan),
        "--state",
        str(state),
        "--dispatch-id",
        "02-designer",
        "--json",
    ], stdout_path=dispatch)

    summary = {
        "kind": "collab_example_summary",
        "out": str(out),
        "artifacts": [str(path) for path in (plan, state, queue, recover, dispatch)],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _run(command: list[str], *, stdout_path: Path | None = None) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    if stdout_path:
        stdout_path.write_text(result.stdout, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
