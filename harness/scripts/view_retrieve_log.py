#!/usr/bin/env python3
"""
view_retrieve_log.py — pretty-print recent retrieve_calls.jsonl entries.

JSONL stays one-line-per-record on disk (so analyze_retrieve_log.py and other
parsers keep working). This tool only reformats for human reading.

Usage:
    python view_retrieve_log.py                # last 10 entries
    python view_retrieve_log.py -n 30          # last 30
    python view_retrieve_log.py --source retrieve_inject   # hook calls only
    python view_retrieve_log.py --miss          # hit_count == 0 only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_LOG = Path.home() / ".claude" / "logs" / "retrieve_calls.jsonl"


def load_lines(path: Path) -> list[dict]:
    out = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("-n", "--num", type=int, default=10, help="show last N entries")
    p.add_argument("--source", help="filter by source field")
    p.add_argument("--miss", action="store_true", help="only entries with hit_count==0")
    p.add_argument("--path", default=str(DEFAULT_LOG))
    args = p.parse_args()

    records = load_lines(Path(args.path))
    if args.source:
        records = [r for r in records if r.get("source") == args.source]
    if args.miss:
        records = [r for r in records if r.get("hit_count", 0) == 0]
    records = records[-args.num :]

    if not records:
        print("(no matching entries)")
        return 0

    for i, r in enumerate(records, 1):
        print(f"\n--- #{i}  {r.get('ts','?')}  source={r.get('source','-')}  hits={r.get('hit_count','?')}  {r.get('elapsed_ms','?')}ms ---")
        print(json.dumps(r, ensure_ascii=False, indent=2))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
