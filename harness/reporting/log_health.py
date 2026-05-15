"""扫 ~/.claude/logs/*.jsonl，按 mtime + 行数判定活/死。

用途：
  python harness/log_health.py            # 文本表格
  python harness/log_health.py --json     # 给 control panel 用

判定规则（mtime 距今）：
  < 3 天   = ALIVE
  3-14 天  = STALE
  > 14 天  = DEAD
  0 行     = EMPTY（覆盖以上判定）
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOGS_DIR = Path.home() / ".claude" / "logs"
ALIVE_DAYS = 3
STALE_DAYS = 14


def classify(line_count: int, age_days: float) -> str:
    if line_count == 0:
        return "EMPTY"
    if age_days < ALIVE_DAYS:
        return "ALIVE"
    if age_days < STALE_DAYS:
        return "STALE"
    return "DEAD"


def scan() -> list[dict]:
    if not LOGS_DIR.exists():
        return []
    now = datetime.now(timezone.utc).timestamp()
    rows: list[dict] = []
    for path in sorted(LOGS_DIR.glob("*.jsonl")):
        try:
            with path.open("rb") as fh:
                line_count = sum(1 for _ in fh)
        except OSError:
            line_count = -1
        try:
            stat = path.stat()
            age_days = (now - stat.st_mtime) / 86400
            size = stat.st_size
        except OSError:
            age_days = -1.0
            size = 0
        rows.append(
            {
                "name": path.name,
                "lines": line_count,
                "size_bytes": size,
                "age_days": round(age_days, 1),
                "status": classify(line_count, age_days),
            }
        )
    return rows


def fmt_size(n: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n //= 1024
    return f"{n}T"


def render_text(rows: list[dict]) -> str:
    if not rows:
        return f"(no jsonl files in {LOGS_DIR})"
    counts = {"ALIVE": 0, "STALE": 0, "DEAD": 0, "EMPTY": 0}
    for r in rows:
        counts[r["status"]] += 1
    lines = [
        f"=== {LOGS_DIR} ({len(rows)} jsonl files) ===",
        f"ALIVE={counts['ALIVE']}  STALE={counts['STALE']}  DEAD={counts['DEAD']}  EMPTY={counts['EMPTY']}",
        "",
        f"{'STATUS':<7} {'NAME':<38} {'LINES':>7} {'SIZE':>7} {'AGE(d)':>8}",
        "-" * 72,
    ]
    order = {"ALIVE": 0, "STALE": 1, "DEAD": 2, "EMPTY": 3}
    for r in sorted(rows, key=lambda x: (order[x["status"]], x["name"])):
        lines.append(
            f"{r['status']:<7} {r['name']:<38} {r['lines']:>7} "
            f"{fmt_size(r['size_bytes']):>7} {r['age_days']:>8.1f}"
        )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="emit JSON for panel")
    args = p.parse_args()
    rows = scan()
    if args.json:
        json.dump(
            {"logs_dir": str(LOGS_DIR), "rows": rows},
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    else:
        print(render_text(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
