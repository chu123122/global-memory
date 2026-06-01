#!/usr/bin/env python
"""context_meter.py — Estimate fixed-context token cost per turn.

Sources:
  - C:/Users/<user>/.claude/CLAUDE.md           (user constitution)
  - $env:GLOBAL_MEMORY_DIR/agents/CLAUDE.md     (global agent rules)
  - $env:GLOBAL_MEMORY_DIR/MEMORY.md            (memory index)
  - settings.json hooks injected text (best-effort static estimate)
  - Enabled plugins (token estimate from tool schemas, static)

Output: JSON with bytes / approx tokens / breakdown.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_USER = Path.home() / ".claude"
GLOBAL_MEM = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2])))
BYTES_PER_TOKEN = 4  # rough CJK-mixed avg


def size_or_zero(p: Path) -> int:
    try:
        return p.stat().st_size if p.exists() else 0
    except Exception:
        return 0


def gather(user_dir: Path) -> dict:
    items = {
        "user_claude_md": size_or_zero(user_dir / "CLAUDE.md"),
        "agent_claude_md": size_or_zero(GLOBAL_MEM / "agents" / "CLAUDE.md"),
        "memory_md": size_or_zero(GLOBAL_MEM / "MEMORY.md"),
        "user_memory_index": size_or_zero(user_dir / "projects" / "C--Users-XINDONG" / "memory" / "MEMORY.md"),
    }
    total_bytes = sum(items.values())
    return {
        "items_bytes": items,
        "total_bytes": total_bytes,
        "approx_tokens": total_bytes // BYTES_PER_TOKEN,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--user-dir", default=str(DEFAULT_USER))
    p.add_argument("--baseline-out", default=None,
                   help="Write report to this path as baseline snapshot")
    args = p.parse_args(argv)

    report = gather(Path(args.user_dir))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.baseline_out:
        Path(args.baseline_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.baseline_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
