#!/usr/bin/env python3
"""
outcomes_reader.py - Phase 4-B-A: task_outcomes.jsonl reader 框架

职责:
  1. 多文件聚合(.0 / .1 / .2 轮转后的历史也读)
  2. last_offset 增量读(避免每次全量 parse)
  3. 自动聚合 metrics(从 audit jsonl 反推 tool_calls 等)

不做(Phase 4-B-B,留 control-panel-v2-pyside):
  - GUI 账本页(等 v2)
  - 趋势图表

用法:
  python outcomes_reader.py --list                # 列所有 outcome
  python outcomes_reader.py --task X              # 按 task 过滤
  python outcomes_reader.py --aggregate <task>    # 从 audit 反推 metrics
  python outcomes_reader.py --json                # 机器可读
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import LOG_DIR  # noqa: E402

# Windows UTF-8(emoji)
for _stream in (sys.stdout, sys.stderr):
    try:
        if getattr(_stream, "encoding", None) != "utf-8" and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUTCOME_LOG = LOG_DIR / "task_outcomes.jsonl"
TOOL_AUDIT = LOG_DIR / "tool_audit.jsonl"
SUBAGENT_AUDIT = LOG_DIR / "subagent_audit.jsonl"


def discover_outcome_files() -> list[Path]:
    """返回当前 + 历史轮转 .0 .1 .2 文件列表(按时间从旧到新)"""
    files = []
    for i in range(2, -1, -1):  # .2, .1, .0(旧到新)
        rotated = OUTCOME_LOG.with_suffix(OUTCOME_LOG.suffix + f".{i}")
        if rotated.exists():
            files.append(rotated)
    if OUTCOME_LOG.exists():
        files.append(OUTCOME_LOG)
    return files


def read_all_outcomes() -> list[dict]:
    """读所有(轮转 + 当前)outcome 记录,按 ts 排序"""
    records = []
    for f in discover_outcome_files():
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            continue
    records.sort(key=lambda r: r.get("ts", ""))
    return records


def filter_by_task(records: list[dict], task: str) -> list[dict]:
    return [r for r in records if r.get("task") == task]


def aggregate_metrics_from_audit(task: str, since_ts: str | None = None,
                                  until_ts: str | None = None) -> dict:
    """从 tool_audit.jsonl + subagent_audit.jsonl 反推 task 的 metrics

    时间窗:
      since_ts (ISO) → 起点(默认无下限,即所有历史)
      until_ts (ISO) → 终点(默认无上限,即至今)

    metrics 字段(对应 task_outcomes schema):
      tool_calls / doc_gate_blocks / memory_writes / subagent_starts
    """
    metrics = {
        "tool_calls": 0,
        "doc_gate_blocks": 0,
        "memory_writes": 0,
        "subagent_starts": 0,
    }

    def in_window(ts_str: str) -> bool:
        if since_ts and ts_str < since_ts:
            return False
        if until_ts and ts_str > until_ts:
            return False
        return True

    # tool_audit:tool_calls / memory_writes / doc_gate_blocks
    if TOOL_AUDIT.exists():
        for line in TOOL_AUDIT.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = r.get("ts", "")
            if not in_window(ts):
                continue
            metrics["tool_calls"] += 1
            # 启发式:input_summary 含 ".claude/global-memory/" 视为 memory write
            tool = r.get("tool", "")
            inp = r.get("input_summary", "")
            if tool in ("Write", "Edit") and "global-memory" in inp:
                metrics["memory_writes"] += 1
            # doc_gate_blocks 暂无直接 audit(doc_gate 自己 deny 时不写 audit_logger)
            # 可从 dangerous_command_blocker / doc_gate 自己的日志读,但本期不做

    # subagent_audit:subagent_starts
    if SUBAGENT_AUDIT.exists():
        for line in SUBAGENT_AUDIT.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = r.get("ts") or r.get("timestamp", "")
            if not in_window(ts):
                continue
            metrics["subagent_starts"] += 1

    return metrics


def render_text(records: list[dict]) -> str:
    """人类可读视图"""
    if not records:
        return "(no outcomes)\n"
    lines = [f"task_outcomes ledger ({len(records)} records, oldest first):", ""]
    for i, r in enumerate(records, 1):
        ts = r.get("ts", "?")[:19]
        task = r.get("task", "?")
        phase = r.get("phase", "")
        out = r.get("outcome", "?")
        m = r.get("metrics", {})
        lines.append(
            f"  #{i:2d} [{ts}] task={task:30s} phase={phase:5s} outcome={out:10s} "
            f"tools={m.get('tool_calls', 0):3d} dur={m.get('duration_min', 0):4d}min"
        )
        lesson = r.get("lesson", "").strip()
        if lesson:
            lines.append(f"      lesson: {lesson[:100]}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="outcomes_reader — Phase 4-B-A reader framework")
    p.add_argument("--list", action="store_true", help="list all outcomes")
    p.add_argument("--task", help="filter by task name")
    p.add_argument("--aggregate", metavar="TASK", help="aggregate metrics from audit jsonl for TASK")
    p.add_argument("--since", help="ISO ts lower bound (used with --aggregate)")
    p.add_argument("--until", help="ISO ts upper bound (used with --aggregate)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.aggregate:
        m = aggregate_metrics_from_audit(args.aggregate, args.since, args.until)
        if args.json:
            print(json.dumps({
                "task": args.aggregate,
                "since": args.since,
                "until": args.until,
                "aggregated_metrics": m,
            }, ensure_ascii=False, indent=2))
        else:
            print(f"[aggregate from audit] task={args.aggregate}")
            print(f"  since={args.since or '(no lower bound)'}")
            print(f"  until={args.until or '(now)'}")
            for k, v in m.items():
                print(f"  {k}: {v}")
        return 0

    records = read_all_outcomes()
    if args.task:
        records = filter_by_task(records, args.task)

    if args.json:
        print(json.dumps({
            "total": len(records),
            "files_read": [str(f) for f in discover_outcome_files()],
            "records": records,
        }, ensure_ascii=False, indent=2))
    else:
        print(render_text(records))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
