#!/usr/bin/env python3
"""Run a minimal headless collab UI-shell dashboard flow."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / ".tmp" / "collab-ui-shell-example")
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
    ui_json = out / "ui-shell.json"
    ui_md = out / "ui-shell.md"

    _run([sys.executable, str(ROOT / "examples" / "collab" / "run_minimal_flow.py"), "--out", str(out)])
    _run(
        [
            sys.executable,
            str(ROOT / "harness" / "scripts" / "collab_ui_shell.py"),
            "--plan",
            str(plan),
            "--state",
            str(state),
            "--queue",
            str(queue),
            "--recover",
            str(recover),
            "--dispatch",
            str(dispatch),
            "--report",
            "01-find=example evidence pointer",
            "--json",
        ],
        stdout_path=ui_json,
    )
    _run(
        [
            sys.executable,
            str(ROOT / "harness" / "scripts" / "collab_ui_shell.py"),
            "--plan",
            str(plan),
            "--state",
            str(state),
            "--queue",
            str(queue),
            "--recover",
            str(recover),
            "--dispatch",
            str(dispatch),
            "--report",
            "01-find=example evidence pointer",
        ],
        stdout_path=ui_md,
    )

    summary = {
        "kind": "collab_ui_shell_example_summary",
        "out": str(out),
        "artifacts": [str(path) for path in (plan, state, queue, recover, dispatch, ui_json, ui_md)],
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
