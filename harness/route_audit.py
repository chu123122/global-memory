#!/usr/bin/env python3
"""route_audit.py — 路由行为审计 v2。从真实日志统计 subagent 使用、missed opportunities。

用法：
  python route_audit.py                    # 全量审计
  python route_audit.py --days 7           # 最近 N 天
  python route_audit.py --session <id>     # 单 session
  python route_audit.py --json             # JSON 输出
  python route_audit.py --agents           # 只看 subagent 统计
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CLAUDE_DIR = Path.home() / ".claude"
LOG_DIR = CLAUDE_DIR / "logs"
TOOL_AUDIT = LOG_DIR / "tool_audit.jsonl"
SUBAGENT_AUDIT = LOG_DIR / "subagent_audit.jsonl"


def parse_ts(ts_str: str) -> float:
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts_str[:19]).timestamp()
    except Exception:
        return 0.0


def load_jsonl(path: Path, session: str | None, days: int | None) -> list[dict]:
    if not path.exists():
        return []
    cutoff = time.time() - days * 86400 if days else 0
    entries = []
    try:
        for line in path.read_text(encoding="utf-8").strip().splitlines():
            try:
                entry = json.loads(line)
                if session and entry.get("session", "") != session:
                    continue
                if cutoff and parse_ts(entry.get("ts", "")) < cutoff:
                    continue
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return entries


def group_by_turn(entries: list[dict]) -> dict[str, list[dict]]:
    turns = defaultdict(list)
    for e in entries:
        tid = e.get("turn_id", "")
        if tid:
            turns[tid].append(e)
    return dict(turns)


def subagent_stats(subagent_entries: list[dict]) -> dict:
    starts = [e for e in subagent_entries if e.get("event", "start") == "start"]
    stops = [e for e in subagent_entries if e.get("event") == "stop"]

    type_counts = Counter(e.get("agent_type", "unknown") for e in starts)
    type_durations = defaultdict(list)
    for s in stops:
        at = s.get("agent_type", "unknown")
        dur = s.get("duration_s")
        if dur is not None:
            type_durations[at].append(dur)

    type_limits = defaultdict(int)
    limit_details = []
    for s in stops:
        if s.get("hit_limit"):
            at = s.get("agent_type", "unknown")
            type_limits[at] += 1
            limit_details.append({
                "agent_type": at,
                "agent_id": s.get("agent_id", ""),
                "exit_reason": s.get("exit_reason"),
                "error": s.get("error", "")[:100],
                "was_killed": s.get("was_killed"),
                "output_truncated": s.get("output_truncated"),
                "duration_s": s.get("duration_s"),
            })

    stats = {}
    for at, count in type_counts.most_common():
        durations = type_durations.get(at, [])
        stats[at] = {
            "calls": count,
            "avg_duration_s": round(sum(durations) / len(durations), 1) if durations else None,
            "stops": len([s for s in stops if s.get("agent_type") == at]),
            "hit_limits": type_limits.get(at, 0),
        }
    return stats, limit_details


def missed_opportunities(tool_entries: list[dict], subagent_entries: list[dict]) -> list[dict]:
    tool_turns = group_by_turn(tool_entries)
    agent_turn_ids = {e.get("turn_id") for e in subagent_entries if e.get("turn_id")}
    missed = []
    for tid, events in tool_turns.items():
        edits = [e for e in events if e.get("tool") in ("Edit", "Write")]
        if len(edits) >= 5 and tid not in agent_turn_ids:
            missed.append({
                "turn_id": tid,
                "edit_count": len(edits),
                "files": list({e.get("input_summary", "") for e in edits})[:10],
            })
    return missed


def build_report(session: str | None, days: int | None) -> dict:
    tool_entries = load_jsonl(TOOL_AUDIT, session, days)
    subagent_entries = load_jsonl(SUBAGENT_AUDIT, session, days)

    sessions = {e.get("session", "") for e in tool_entries + subagent_entries} - {""}
    tool_counts = Counter(e.get("tool", "") for e in tool_entries)
    agent_stats, limit_details = subagent_stats(subagent_entries)
    missed = missed_opportunities(tool_entries, subagent_entries)
    turns_with_agents = len({e.get("turn_id") for e in subagent_entries if e.get("turn_id")})
    total_turns = len(group_by_turn(tool_entries))

    return {
        "period": f"last {days} days" if days else "all time",
        "sessions": len(sessions),
        "total_tool_calls": len(tool_entries),
        "total_turns": total_turns,
        "tool_distribution": dict(tool_counts.most_common(10)),
        "subagent_starts": len([e for e in subagent_entries if e.get("event", "start") == "start"]),
        "subagent_stops": len([e for e in subagent_entries if e.get("event") == "stop"]),
        "turns_with_agents": turns_with_agents,
        "agent_stats": agent_stats,
        "limit_hits": limit_details,
        "limit_count": len(limit_details),
        "missed_opportunities": missed,
        "missed_count": len(missed),
    }


def render_text(report: dict) -> str:
    lines = [
        f"=== 路由行为审计 ({report['period']}) ===",
        f"会话数：{report['sessions']}  总工具调用：{report['total_tool_calls']}  总 turn：{report['total_turns']}",
        f"subagent 启动：{report['subagent_starts']}  含 agent 的 turn：{report['turns_with_agents']}",
        "",
    ]

    if report["agent_stats"]:
        lines.append("Subagent 调用统计：")
        for at, s in report["agent_stats"].items():
            dur = f"  平均 {s['avg_duration_s']}s" if s["avg_duration_s"] else ""
            limits = f"  ⚠️{s['hit_limits']}次撞上限" if s.get("hit_limits") else ""
            lines.append(f"  {at}: {s['calls']}次{dur}{limits}")
    else:
        lines.append("Subagent 调用：无")

    lines.append("")
    lines.append("工具分布（前10）：")
    for tool, count in report.get("tool_distribution", {}).items():
        lines.append(f"  {tool}: {count}")

    if report.get("limit_hits"):
        lines.append("")
        lines.append(f"🚫 撞上限（{report['limit_count']} 次）：")
        for lh in report["limit_hits"][:5]:
            reason = lh.get("exit_reason") or ""
            killed = " [killed]" if lh.get("was_killed") else ""
            truncated = " [truncated]" if lh.get("output_truncated") else ""
            err = f" err={lh['error']}" if lh.get("error") else ""
            lines.append(f"  {lh['agent_type']}: {reason}{killed}{truncated}{err}")

    if report["missed_opportunities"]:
        lines.append("")
        lines.append(f"⚠️ Missed opportunities（{report['missed_count']} 轮）：")
        for m in report["missed_opportunities"][:5]:
            lines.append(f"  turn {m['turn_id']}: {m['edit_count']} files edited, no subagent")
    else:
        lines.append("")
        lines.append("Missed opportunities：无（或 turn_id 未关联）")

    return "\n".join(lines)


def render_agents_only(report: dict) -> str:
    if not report["agent_stats"]:
        return "Subagent 调用：无记录"
    lines = ["Subagent 调用统计："]
    for at, s in report["agent_stats"].items():
        dur = f"  平均 {s['avg_duration_s']}s" if s["avg_duration_s"] else ""
        limits = f"  ⚠️{s['hit_limits']}次撞上限" if s.get("hit_limits") else ""
        lines.append(f"  {at}: {s['calls']}次, {s['stops']}次完成{dur}{limits}")
    if report.get("limit_hits"):
        lines.append(f"\n🚫 撞上限详情（{report['limit_count']} 次）：")
        for lh in report["limit_hits"][:10]:
            reason = lh.get("exit_reason") or "unknown"
            lines.append(f"  {lh['agent_type']}: {reason} dur={lh.get('duration_s')}s")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="路由行为审计 v2")
    parser.add_argument("--session", help="只审计指定 session")
    parser.add_argument("--days", type=int, help="只审计最近 N 天")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--agents", action="store_true", help="只看 subagent 统计")
    args = parser.parse_args()

    report = build_report(args.session, args.days)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.agents:
        print(render_agents_only(report))
    else:
        print(render_text(report))


if __name__ == "__main__":
    main()
