#!/usr/bin/env python
"""scan_dual_storage.py — Detect task docs duplicated across
$env:CLAUDE_TASKS_ACTIVE and $env:GLOBAL_MEMORY_DIR/projects.

Default output: dual_count=<N> and a list of duplicate dirs.
JSON output: schema_version=1, kind=dual_storage_scan.
Exit 0 always (informational). Use --strict to exit 1 if any duplicates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_TASKS_ROOT = Path(os.environ.get("CLAUDE_TASKS_ROOT", str(Path.home() / ".claude" / "tasks")))
ACTIVE = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(DEFAULT_TASKS_ROOT / "active")))
ARCHIVED = Path(os.environ.get("CLAUDE_TASKS_ARCHIVED", str(DEFAULT_TASKS_ROOT / "archived")))
PROJECTS = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2]))) / "projects"


def list_dirs(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {d.name for d in root.iterdir() if d.is_dir()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    a = list_dirs(ACTIVE)
    ar = list_dirs(ARCHIVED)
    pr = list_dirs(PROJECTS)

    dual = sorted((a | ar) & pr)
    duplicates = [
        {
            "name": d,
            "active": d in a,
            "archived": d in ar,
            "projects": True,
        }
        for d in dual
    ]
    result = {
        "schema_version": 1,
        "kind": "dual_storage_scan",
        "verdict": "dual_storage_found" if dual else "ok",
        "roots": {
            "active": str(ACTIVE),
            "archived": str(ARCHIVED),
            "projects": str(PROJECTS),
        },
        "summary": {
            "active_dirs": len(a),
            "archived_dirs": len(ar),
            "project_dirs": len(pr),
            "dual_count": len(dual),
        },
        "duplicates": duplicates,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"dual_count={len(dual)}")
        for row in duplicates:
            print(
                f"  - {row['name']} "
                f"(active={row['active']}, archived={row['archived']}, projects=True)"
            )

    if args.strict and dual:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
