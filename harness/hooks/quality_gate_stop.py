#!/usr/bin/env python3
"""Optional Claude Code Stop hook adapter for quality_gate.py.

Default mode is warn-only. Set HARNESS_QUALITY_GATE_ENFORCE=1 to make BLOCK
verdicts return a non-zero exit code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = HARNESS_DIR.parent
QUALITY_GATE = HARNESS_DIR / "scripts" / "quality_gate.py"


def main() -> int:
    if os.environ.get("HARNESS_QUALITY_GATE", "1") in {"0", "false", "False"}:
        return 0

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(QUALITY_GATE), "verify", "--json"],
            cwd=str(REPO_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            env=env,
        )
    except Exception as exc:
        print(f"quality_gate hook WARN: failed to run quality gate: {exc}", file=sys.stderr)
        return 0

    try:
        data = json.loads(proc.stdout)
        verdict = data.get("verdict", "UNKNOWN")
        tier = data.get("plan", {}).get("tier", "?")
        missing = data.get("missing", [])
        print(f"quality_gate: verdict={verdict}, tier={tier}, missing={missing[:6]}", file=sys.stderr)
    except Exception:
        print("quality_gate hook WARN: invalid JSON output", file=sys.stderr)
        verdict = "ERROR"

    enforce = os.environ.get("HARNESS_QUALITY_GATE_ENFORCE", "0") in {"1", "true", "True"}
    if enforce and verdict == "BLOCK":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
