#!/usr/bin/env python3
"""retrieve_candidate_quality.py — read-only quality report for retrieve pointers.

This script does not change ranking or frontmatter. It groups recalled pointers by
file family and flags candidates that are recalled frequently but not consumed by
subsequent Read calls.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCHEMA_VERSION = 1
DEFAULT_LOGS = Path.home() / ".claude" / "logs"
CONSUMPTION_WINDOW_MIN = 30


def parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def load_jsonl(path: Path, days: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days) if days else None
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            ts = parse_ts(row.get("ts") or row.get("timestamp"))
            if cutoff and ts and ts < cutoff:
                continue
            out.append(row)
    return out


def norm_path(path: str) -> str:
    s = str(path or "").replace("\\", "/").strip().lower()
    if s.endswith(".proposed"):
        s = s[: -len(".proposed")]
    return s


def family_for(path: str) -> str:
    s = norm_path(path)
    for family in ["feedback", "knowledge", "fixes", "decisions", "docs", "projects", "skills", "agents", "harness"]:
        if f"/{family}/" in s or s.endswith(f"/{family}") or f"global-memory/{family}/" in s:
            return family
    if "global-memory" in s:
        return "global-memory-other"
    return "external"


def build_read_index(tool_rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[datetime]]:
    read_index: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for row in tool_rows:
        if row.get("tool") != "Read":
            continue
        ts = parse_ts(row.get("ts"))
        if not ts:
            continue
        sess = str(row.get("session") or "")
        path = norm_path(str(row.get("input_summary") or ""))
        if path:
            read_index[(sess, path)].append(ts)
    return read_index


def was_consumed(hit_path: str, retrieve_ts: datetime | None, session: str, read_index: dict[tuple[str, str], list[datetime]]) -> bool:
    if not retrieve_ts:
        return False
    target = norm_path(hit_path)
    if not target:
        return False
    window = timedelta(minutes=CONSUMPTION_WINDOW_MIN)
    candidates: list[datetime] = []
    if session:
        candidates.extend(read_index.get((session, target), []))
    if not candidates:
        for (_, path), times in read_index.items():
            if path == target:
                candidates.extend(times)
    return any(retrieve_ts <= ts <= retrieve_ts + window for ts in candidates)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    logs = Path(args.logs_root)
    retrieve_rows = load_jsonl(logs / "retrieve_calls.jsonl", args.days)
    tool_rows = load_jsonl(logs / "tool_audit.jsonl", args.days)
    read_index = build_read_index(tool_rows)

    pointer_recalled: Counter[str] = Counter()
    pointer_consumed: Counter[str] = Counter()
    family_recalled: Counter[str] = Counter()
    family_consumed: Counter[str] = Counter()

    for row in retrieve_rows:
        ts = parse_ts(row.get("ts"))
        session = str(row.get("session") or "")
        for hit in row.get("all_hits") or []:
            path = str(hit.get("path") or "")
            if not path:
                continue
            fam = family_for(path)
            pointer_recalled[path] += 1
            family_recalled[fam] += 1
            if was_consumed(path, ts, session, read_index):
                pointer_consumed[path] += 1
                family_consumed[fam] += 1

    pointer_rows = []
    for path, recalled in pointer_recalled.most_common():
        consumed = pointer_consumed.get(path, 0)
        rate = consumed / recalled if recalled else 0.0
        family = family_for(path)
        candidate = recalled >= args.min_recalled and consumed == 0
        pointer_rows.append({
            "path": path,
            "family": family,
            "recalled": recalled,
            "consumed": consumed,
            "consumption_rate": round(rate, 4),
            "candidate_downrank": candidate,
            "reason": "frequently recalled but not read" if candidate else "",
        })

    families = []
    for family, recalled in family_recalled.most_common():
        consumed = family_consumed.get(family, 0)
        families.append({
            "family": family,
            "recalled": recalled,
            "consumed": consumed,
            "consumption_rate": round(consumed / recalled, 4) if recalled else 0.0,
        })

    candidates = [p for p in pointer_rows if p["candidate_downrank"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "read-only",
        "inputs": {
            "logs_root": str(logs),
            "days": args.days,
            "window_minutes": CONSUMPTION_WINDOW_MIN,
            "min_recalled": args.min_recalled,
        },
        "summary": {
            "retrieve_calls": len(retrieve_rows),
            "unique_pointers": len(pointer_rows),
            "candidate_downrank_count": len(candidates),
            "top_candidate_family": candidates[0]["family"] if candidates else None,
        },
        "family_quality": families,
        "candidate_downrank": candidates[: args.limit],
        "top_pointers": pointer_rows[: args.limit],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Retrieve Candidate Quality",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- mode: `{report['mode']}`",
        f"- retrieve_calls: `{report['summary']['retrieve_calls']}`",
        f"- unique_pointers: `{report['summary']['unique_pointers']}`",
        f"- candidate_downrank_count: `{report['summary']['candidate_downrank_count']}`",
        "",
        "## Family Quality",
        "",
        "| family | recalled | consumed | consumption_rate |",
        "|---|---:|---:|---:|",
    ]
    for row in report["family_quality"]:
        lines.append(f"| {row['family']} | {row['recalled']} | {row['consumed']} | {row['consumption_rate']} |")
    lines.extend(["", "## Candidate Downrank", ""])
    if not report["candidate_downrank"]:
        lines.append("- No candidates above threshold.")
    else:
        for row in report["candidate_downrank"]:
            lines.append(f"- `{row['path']}` — recalled={row['recalled']}, consumed={row['consumed']}, family={row['family']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only retrieve candidate quality report.")
    parser.add_argument("--logs-root", default=str(DEFAULT_LOGS))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--min-recalled", type=int, default=10)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
