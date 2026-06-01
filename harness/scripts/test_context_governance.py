#!/usr/bin/env python
"""test_context_governance.py — single entry to run all layered tests.

Usage:
    --all                run unit + integration + smoke
    --layer unit|integration|smoke
    --junit <path>       JUnit XML output
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1] / "tests" / "context_governance"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--layer", choices=["unit", "integration", "smoke", "regression"])
    p.add_argument("--junit", default=None)
    p.add_argument("-q", "--quiet", action="store_true")
    args = p.parse_args(argv)

    targets: list[str] = []
    if args.all:
        targets = [
            str(TESTS_ROOT / "unit"),
            str(TESTS_ROOT / "integration"),
            str(TESTS_ROOT / "smoke"),
            str(TESTS_ROOT / "regression"),
        ]
    elif args.layer:
        targets = [str(TESTS_ROOT / args.layer)]
    else:
        targets = [str(TESTS_ROOT)]

    cmd = [sys.executable, "-m", "pytest"]
    if args.quiet:
        cmd.append("-q")
    else:
        cmd.append("-v")
    if args.junit:
        cmd.append(f"--junitxml={args.junit}")
    cmd.extend(targets)
    print(f"$ {' '.join(cmd)}")
    r = subprocess.run(cmd)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
