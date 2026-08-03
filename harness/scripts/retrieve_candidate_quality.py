#!/usr/bin/env python3
"""retrieve_candidate_quality.py — read-only quality report for retrieve pointers.

This script does not change ranking or frontmatter. It correlates RAG-delivered
or recalled pointers with subsequent Read calls from tool_audit.jsonl and flags
frequently recalled candidates that were not consumed.
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

try:
    from harness.config import GLOBAL_MEMORY_LOGS_DIR
except Exception:
    GLOBAL_MEMORY_LOGS_DIR = Path.home() / ".global-memory" / "logs"

SCHEMA_VERSION = 2
DEFAULT_LOGS = GLOBAL_MEMORY_LOGS_DIR
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
    s = str(path or "").replace("\\", "/").strip().strip('"').lower()
    while "//" in s:
        s = s.replace("//", "/")
    if s.endswith(".proposed"):
        s = s[: -len(".proposed")]
    return s


def path_matches(read_path: str, pointer_path: str) -> bool:
    read = norm_path(read_path)
    pointer = norm_path(pointer_path)
    if not read or not pointer:
        return False
    return read == pointer or read.endswith("/" + pointer) or pointer.endswith("/" + read)


def family_for(path: str) -> str:
    s = norm_path(path)
    for family in ["feedback", "knowledge", "fixes", "decisions", "docs", "projects", "skills", "agents", "harness", "rules"]:
        if f"/{family}/" in s or s.endswith(f"/{family}") or f"global-memory/{family}/" in s:
            return family
    if "global-memory" in s:
        return "global-memory-other"
    return "external"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def retrieve_paths(row: dict[str, Any]) -> list[str]:
    """Return pointer paths from new fields first, then legacy all_hits[].path."""
    paths: list[str] = []
    for key in ("top_refs", "top_candidate_paths"):
        for path in _string_list(row.get(key)):
            if path not in paths:
                paths.append(path)
    if paths:
        return paths
    for hit in row.get("all_hits") or []:
        if isinstance(hit, dict):
            path = str(hit.get("path") or "")
            if path and path not in paths:
                paths.append(path)
    return paths


def build_read_events(tool_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in tool_rows:
        if row.get("tool") != "Read":
            continue
        ts = parse_ts(row.get("ts") or row.get("timestamp"))
        path = str(row.get("input_summary") or row.get("path") or "")
        if not ts or not path.strip():
            continue
        events.append({
            "ts": ts,
            "session": str(row.get("session") or row.get("hook_session_id") or ""),
            "turn_id": str(row.get("turn_id") or ""),
            "path": path,
        })
    events.sort(key=lambda item: item["ts"])
    return events


def find_consuming_read(
    hit_path: str,
    retrieve_ts: datetime | None,
    session: str,
    read_events: list[dict[str, Any]],
    *,
    turn_id: str = "",
) -> dict[str, Any] | None:
    if not retrieve_ts or not norm_path(hit_path):
        return None
    window_end = retrieve_ts + timedelta(minutes=CONSUMPTION_WINDOW_MIN)

    def eligible(event: dict[str, Any], *, require_session: bool, require_turn: bool) -> bool:
        ts = event["ts"]
        if not (retrieve_ts <= ts <= window_end):
            return False
        if require_session and session and event.get("session") != session:
            return False
        if require_turn and turn_id and event.get("turn_id") != turn_id:
            return False
        return path_matches(str(event.get("path") or ""), hit_path)

    # Prefer exact turn+session, then same session, then cross-session fallback.
    passes = [
        (True, True),
        (True, False),
        (False, False),
    ]
    for require_session, require_turn in passes:
        for event in read_events:
            if eligible(event, require_session=require_session, require_turn=require_turn):
                return event
    return None


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    logs = Path(args.logs_root)
    retrieve_rows = load_jsonl(logs / "retrieve_calls.jsonl", args.days)
    tool_rows = load_jsonl(logs / "tool_audit.jsonl", args.days)
    read_events = build_read_events(tool_rows)

    pointer_recalled: Counter[str] = Counter()
    pointer_consumed: Counter[str] = Counter()
    family_recalled: Counter[str] = Counter()
    family_consumed: Counter[str] = Counter()
    turn_stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"delivered": 0, "consumed": 0, "paths": Counter()})
    consumed_examples: list[dict[str, Any]] = []

    delivered_pointer_count = 0
    consumed_pointer_count = 0

    for row in retrieve_rows:
        ts = parse_ts(row.get("ts") or row.get("timestamp"))
        session = str(row.get("hook_session_id") or row.get("session") or "")
        turn_id = str(row.get("turn_id") or "")
        query_id = str(row.get("query_id") or "")
        paths = retrieve_paths(row)
        if not paths:
            continue
        for path in paths:
            fam = family_for(path)
            delivered_pointer_count += 1
            pointer_recalled[path] += 1
            family_recalled[fam] += 1
            if turn_id:
                key = (session, turn_id)
                turn_stats[key]["delivered"] += 1
                turn_stats[key]["paths"][path] += 1
            event = find_consuming_read(path, ts, session, read_events, turn_id=turn_id)
            if event:
                consumed_pointer_count += 1
                pointer_consumed[path] += 1
                family_consumed[fam] += 1
                if turn_id:
                    turn_stats[(session, turn_id)]["consumed"] += 1
                if len(consumed_examples) < args.limit:
                    consumed_examples.append({
                        "path": path,
                        "query_id": query_id,
                        "retrieve_ts": ts.isoformat(timespec="seconds") if ts else "",
                        "read_ts": event["ts"].isoformat(timespec="seconds"),
                        "session": event.get("session") or session,
                        "turn_id": event.get("turn_id") or turn_id,
                    })

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

    turn_quality = []
    for (session, turn_id), data in sorted(turn_stats.items()):
        delivered = int(data["delivered"])
        consumed = int(data["consumed"])
        turn_quality.append({
            "session": session,
            "turn_id": turn_id,
            "delivered_pointer_count": delivered,
            "consumed_pointer_count": consumed,
            "consumption_rate": round(consumed / delivered, 4) if delivered else 0.0,
            "top_paths": [path for path, _count in data["paths"].most_common(5)],
        })

    candidates = [p for p in pointer_rows if p["candidate_downrank"]]
    unconsumed = [p for p in pointer_rows if p["consumed"] == 0]
    consumption_rate = consumed_pointer_count / delivered_pointer_count if delivered_pointer_count else 0.0
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
            "read_calls": len(read_events),
            "unique_pointers": len(pointer_rows),
            "delivered_pointer_count": delivered_pointer_count,
            "consumed_pointer_count": consumed_pointer_count,
            "consumption_rate": round(consumption_rate, 4),
            "candidate_downrank_count": len(candidates),
            "top_candidate_family": candidates[0]["family"] if candidates else None,
        },
        "delivered_pointer_count": delivered_pointer_count,
        "consumed_pointer_count": consumed_pointer_count,
        "consumption_rate": round(consumption_rate, 4),
        "unconsumed_top_paths": unconsumed[: args.limit],
        "consumed_examples": consumed_examples,
        "family_quality": families,
        "turn_quality": turn_quality[: args.limit],
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
        f"- read_calls: `{report['summary']['read_calls']}`",
        f"- delivered_pointer_count: `{report['delivered_pointer_count']}`",
        f"- consumed_pointer_count: `{report['consumed_pointer_count']}`",
        f"- consumption_rate: `{report['consumption_rate']}`",
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
