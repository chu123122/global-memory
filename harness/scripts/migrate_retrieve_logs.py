#!/usr/bin/env python3
"""Migrate legacy Claude retrieve_calls.jsonl into the shared runtime log.

Only migrates retrieve_calls.jsonl. Other Claude logs remain in CLAUDE_LOGS_DIR.
The migration is idempotent: exact duplicate lines are skipped.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (  # noqa: E402
    GLOBAL_MEMORY_LOGS_DIR,
    is_runtime_logs_dir_in_repo,
    runtime_logs_repo_warning,
)

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_SOURCE = Path.home() / ".claude" / "logs" / "retrieve_calls.jsonl"
DEFAULT_TARGET = GLOBAL_MEMORY_LOGS_DIR / "retrieve_calls.jsonl"


def _load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if line:
                lines.append(line)
    return lines


def migrate(source: Path = DEFAULT_SOURCE, target: Path = DEFAULT_TARGET, dry_run: bool = False) -> dict:
    if is_runtime_logs_dir_in_repo(target.parent):
        raise RuntimeError(runtime_logs_repo_warning(target.parent))

    source_lines = _load_lines(source)
    target_lines = _load_lines(target)
    seen = set(target_lines)
    to_append = [line for line in source_lines if line not in seen]

    if not dry_run and to_append:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8", newline="\n") as fh:
            for line in to_append:
                fh.write(line + "\n")

    return {
        "source": str(source),
        "target": str(target),
        "source_lines": len(source_lines),
        "target_existing_lines": len(target_lines),
        "appended_lines": len(to_append),
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy Claude retrieve_calls.jsonl to shared runtime logs")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = migrate(Path(args.source), Path(args.target), dry_run=args.dry_run)
    except Exception as exc:
        if args.json:
            sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stderr.write(f"ERROR: {exc}\n")
        return 1

    if args.json:
        out = {"ok": True, **result}
        sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(
            "migrate_retrieve_logs: "
            f"source_lines={result['source_lines']} "
            f"existing={result['target_existing_lines']} "
            f"appended={result['appended_lines']} "
            f"target={result['target']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
