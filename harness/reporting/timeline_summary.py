#!/usr/bin/env python3
"""Summarize AI timeline evidence for the control panel.

This is intentionally read-only. It answers two practical questions:
- What did the last audited AI session actually do?
- Did the token-saver / timeline tools get called in real conversations?
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import LOG_DIR  # noqa: E402


TRACKED_TOOLS = OrderedDict(
    [
        ("work_context_pack.py", "work context pack"),
        ("audit_skill.py", "skill audit"),
        ("check_prepare.py", "check preflight"),
        ("session_report.py", "session timeline"),
        ("outcomes_reader.py", "outcome ledger"),
    ]
)
DEFAULT_WINDOW_DAYS = 7


def parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


def tool_audit_records(log_dir: Path) -> list[dict]:
    records = read_jsonl(log_dir / "tool_audit.jsonl")
    records.sort(key=lambda r: str(r.get("ts", "")))
    return records


def outcome_records(log_dir: Path) -> list[dict]:
    base = log_dir / "task_outcomes.jsonl"
    paths: list[Path] = []
    for i in range(2, -1, -1):
        rotated = base.with_suffix(base.suffix + f".{i}")
        if rotated.exists():
            paths.append(rotated)
    if base.exists():
        paths.append(base)
    records: list[dict] = []
    for path in paths:
        records.extend(read_jsonl(path))
    records.sort(key=lambda r: str(r.get("ts", "")))
    return records


def invocation_records(log_dir: Path) -> list[dict]:
    base = log_dir / "harness_tool_invocations.jsonl"
    paths: list[Path] = []
    for i in range(2, -1, -1):
        rotated = base.with_suffix(base.suffix + f".{i}")
        if rotated.exists():
            paths.append(rotated)
    if base.exists():
        paths.append(base)
    records: list[dict] = []
    for path in paths:
        records.extend(read_jsonl(path))
    records.sort(key=lambda r: str(r.get("ts", "")))
    return records


def latest_session(records: list[dict], max_events: int = 12) -> dict | None:
    sessions: OrderedDict[str, list[dict]] = OrderedDict()
    for record in records:
        sid = str(record.get("session") or "").strip()
        if not sid:
            continue
        sessions.setdefault(sid, []).append(record)
    if not sessions:
        return None

    sid, items = next(reversed(sessions.items()))
    start = parse_ts(str(items[0].get("ts", "")))
    end = parse_ts(str(items[-1].get("ts", "")))
    duration_sec = int((end - start).total_seconds()) if start and end else None
    tool_counts = Counter(str(r.get("tool") or "?") for r in items)
    events = []
    for r in items[-max_events:]:
        summary = str(r.get("input_summary") or "")
        if len(summary) > 150:
            summary = summary[:147] + "..."
        events.append(
            {
                "ts": r.get("ts", ""),
                "tool": r.get("tool", ""),
                "summary": summary,
            }
        )
    return {
        "session": sid,
        "start": items[0].get("ts", ""),
        "end": items[-1].get("ts", ""),
        "duration_sec": duration_sec,
        "tool_calls": len(items),
        "tool_counts": dict(tool_counts.most_common()),
        "events": events,
    }


def tracked_tool_usage(records: list[dict], invocations: list[dict], days: int) -> dict:
    cutoff = datetime.now() - timedelta(days=days)
    usage: dict[str, dict] = {}
    recent_calls: list[dict] = []
    for script, label in TRACKED_TOOLS.items():
        audit_total = 0
        audit_recent = 0
        invoke_total = 0
        invoke_recent = 0
        last_audit_ts = ""
        last_invoke_ts = ""
        for record in records:
            summary = str(record.get("input_summary") or "")
            if script not in summary:
                continue
            audit_total += 1
            ts = str(record.get("ts") or "")
            if ts > last_audit_ts:
                last_audit_ts = ts
            parsed = parse_ts(ts)
            if parsed and parsed >= cutoff:
                audit_recent += 1
                recent_calls.append(
                    {
                        "ts": ts,
                        "script": script,
                        "label": label,
                        "source": "ai-tool-audit",
                        "tool": record.get("tool", ""),
                        "session": record.get("session", ""),
                        "summary": summary[:180],
                    }
                )
        for record in invocations:
            if str(record.get("script") or "") != script:
                continue
            invoke_total += 1
            ts = str(record.get("ts") or "")
            if ts > last_invoke_ts:
                last_invoke_ts = ts
            parsed = parse_ts(ts)
            if parsed and parsed >= cutoff:
                invoke_recent += 1
                recent_calls.append(
                    {
                        "ts": ts,
                        "script": script,
                        "label": label,
                        "source": record.get("source", "script-invocation"),
                        "tool": "script",
                        "session": "",
                        "summary": " ".join(str(x) for x in record.get("argv", []))[:180],
                    }
                )
        last_ts = max(last_audit_ts, last_invoke_ts)
        if audit_recent:
            status = "recent"
        elif invoke_recent:
            status = "self-recent"
        elif audit_total or invoke_total:
            status = "stale"
        else:
            status = "unused"
        usage[script] = {
            "label": label,
            "total_count": audit_total,
            "recent_count": audit_recent,
            "audit_total_count": audit_total,
            "audit_recent_count": audit_recent,
            "invocation_total_count": invoke_total,
            "invocation_recent_count": invoke_recent,
            "last_audit_ts": last_audit_ts,
            "last_invocation_ts": last_invoke_ts,
            "last_ts": last_ts,
            "status": status,
        }
    recent_calls.sort(key=lambda r: str(r.get("ts", "")), reverse=True)
    return {"tools": usage, "recent_calls": recent_calls[:20], "window_days": days}


def latest_outcomes(records: list[dict], limit: int = 5) -> list[dict]:
    out = []
    for record in records[-limit:]:
        metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
        out.append(
            {
                "ts": record.get("ts", ""),
                "task": record.get("task", ""),
                "phase": record.get("phase", ""),
                "outcome": record.get("outcome", ""),
                "tool_calls": metrics.get("tool_calls", 0),
                "duration_min": metrics.get("duration_min", 0),
                "lesson": str(record.get("lesson", ""))[:180],
            }
        )
    out.reverse()
    return out


def build_report(log_dir: Path, days: int, max_events: int) -> dict:
    audit = tool_audit_records(log_dir)
    invocations = invocation_records(log_dir)
    outcomes = outcome_records(log_dir)
    usage = tracked_tool_usage(audit, invocations, days)
    recommendations = []
    if usage["tools"]["work_context_pack.py"]["audit_recent_count"] == 0:
        recommendations.append("/work context pack has no recent AI direct audit calls.")
    if usage["tools"]["audit_skill.py"]["audit_recent_count"] == 0:
        recommendations.append("skill audit has no recent AI direct audit calls.")
    if usage["tools"]["session_report.py"]["audit_recent_count"] == 0:
        recommendations.append("session timeline exists but is not a recent AI-facing habit.")

    return {
        "schema_version": 1,
        "kind": "timeline_summary",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source_note": "AI counts come from direct tool_audit calls. Script counts come from harness_tool_invocations.jsonl and prove execution, not AI workflow adoption.",
        "log_dir": str(log_dir),
        "latest_session": latest_session(audit, max_events=max_events),
        "tracked_tool_usage": usage,
        "latest_outcomes": latest_outcomes(outcomes),
        "recommendations": recommendations,
    }


def render_text(report: dict) -> str:
    lines = ["timeline summary", f"timestamp: {report['timestamp']}", ""]
    session = report.get("latest_session")
    if session:
        lines.append(
            f"latest session: {session['session'][:12]} "
            f"{session['start']} -> {session['end']} "
            f"calls={session['tool_calls']}"
        )
        lines.append("top tools: " + ", ".join(f"{k}:{v}" for k, v in list(session["tool_counts"].items())[:5]))
    else:
        lines.append("latest session: none")
    lines.append("")
    lines.append("tracked tools:")
    for script, item in report["tracked_tool_usage"]["tools"].items():
        lines.append(
            f"- {script}: {item['status']} "
            f"ai_recent={item['audit_recent_count']} ai_total={item['audit_total_count']} "
            f"script_recent={item['invocation_recent_count']} script_total={item['invocation_total_count']} "
            f"last={item['last_ts'] or '-'}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="summarize AI audit timeline for control panel")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--log-dir", default=str(LOG_DIR))
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--max-events", type=int, default=12)
    args = parser.parse_args()

    report = build_report(Path(args.log_dir), days=args.days, max_events=args.max_events)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
