#!/usr/bin/env python3
"""readback_audit.py — 文档回读率审计

复用 ~/.claude/logs/tool_audit.jsonl(已记每次 Read, input_summary=被读文件绝对路径)，
无需新埋点。回答："任务文档(HANDOFF/STATUS/design...)写了之后到底有没有被读回？"

核心指标(仅统计"正式任务会话"——会话内 Edit/Write 过 ClaudeTasks 文档，或写过
.current_task。快速提问会话不计入，否则分母被稀释)：
  - HANDOFF 开头回读率：会话前 N(默认5)个工具调用内 Read 过 HANDOFF.md 的会话占比
  - HANDOFF 整会话回读率：会话内任意位置 Read 过 HANDOFF.md 的会话占比

用法：
  python readback_audit.py                 # 近30天，人类可读汇总
  python readback_audit.py --days 7
  python readback_audit.py --json          # 机器可读
  python readback_audit.py --opening-n 3   # 调整"开头"窗口

注：tool_audit 不记 SessionStart，"开头"用"前 N 个工具调用"近似。
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LOG = Path.home() / ".claude" / "logs" / "tool_audit.jsonl"

# 关注的文档子串(大小写无关，匹配 input_summary 路径)
DOC_PATTERNS = {
    "HANDOFF": "handoff.md",
    "STATUS": "status.md",
    "MEMORY": "memory.md",
    "design": "设计文档",
    "REQUIREMENTS": "需求分析",
    "Phase": "phase",
    "CHANGELOG": "changelog.md",
    "REVIEW": "review",
    "背景": "背景.md",
}


def _is_taskdoc(path: str) -> bool:
    return "claudetasks" in path.lower().replace("\\", "/")


def _load_sessions(days: int) -> dict[str, list[dict]]:
    """读 tool_audit，按 cutoff 过滤，按 session 分组(保留时序)。"""
    if not LOG.is_file():
        raise SystemExit(f"日志不存在: {LOG}")
    # cutoff 基于日志里最新 ts 往回推(避免依赖系统时钟/Date)
    rows: list[dict] = []
    latest = ""
    with LOG.open(encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            ts = d.get("ts", "")
            if ts > latest:
                latest = ts
            rows.append(d)
    if not latest:
        raise SystemExit("日志为空或无 ts 字段")
    try:
        cut_dt = datetime.fromisoformat(latest[:19]) - timedelta(days=days)
        cutoff = cut_dt.isoformat()
    except Exception:
        cutoff = ""

    sess: dict[str, list[dict]] = defaultdict(list)
    for d in rows:
        if cutoff and d.get("ts", "") < cutoff:
            continue
        sess[d.get("session", "?")].append(d)
    return sess


def _is_formal(evs: list[dict]) -> bool:
    """会话是否为正式任务：Edit/Write 过 ClaudeTasks 文档，或写过 .current_task。"""
    for e in evs:
        summ = e.get("input_summary", "")
        if e.get("tool") in ("Edit", "Write") and _is_taskdoc(summ):
            return True
        if "current_task" in summ.lower():
            return True
    return False


def _read_hit(evs: list[dict], needle: str, opening_n: int | None) -> bool:
    """会话内是否 Read 过路径含 needle 的文件；opening_n 限定前 N 个工具调用内。"""
    for i, e in enumerate(evs):
        if opening_n is not None and i >= opening_n:
            break
        if e.get("tool") == "Read" and needle in e.get("input_summary", "").lower():
            return True
    return False


def audit(days: int, opening_n: int) -> dict:
    sess = _load_sessions(days)
    all_sessions = [s for s, evs in sess.items() if len(evs) >= 3]
    formal = [s for s in all_sessions if _is_formal(sess[s])]
    n_formal = len(formal)

    def rate(needle: str, opening: bool) -> dict:
        on = opening_n if opening else None
        hit = sum(_read_hit(sess[s], needle, on) for s in formal)
        return {"hit": hit, "total": n_formal,
                "pct": round(100 * hit / n_formal, 1) if n_formal else 0.0}

    # 全文档读频次(全部会话，非仅正式)
    doc_reads = {name: 0 for name in DOC_PATTERNS}
    for evs in sess.values():
        for e in evs:
            if e.get("tool") != "Read":
                continue
            s = e.get("input_summary", "").lower()
            for name, pat in DOC_PATTERNS.items():
                if pat in s:
                    doc_reads[name] += 1

    return {
        "days": days,
        "opening_n": opening_n,
        "sessions_total": len(sess),
        "sessions_active": len(all_sessions),
        "sessions_formal": n_formal,
        "handoff_opening": rate("handoff.md", True),
        "handoff_anywhere": rate("handoff.md", False),
        "status_anywhere": rate("status.md", False),
        "doc_read_counts": doc_reads,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="文档回读率审计(复用 tool_audit.jsonl)")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--opening-n", type=int, default=5, help="'开头'窗口=前 N 个工具调用")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    r = audit(args.days, args.opening_n)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print(f"  文档回读率审计 — 近 {r['days']} 天")
    print("=" * 56)
    print(f"  会话总数 {r['sessions_total']} | 活跃(≥3调用) {r['sessions_active']} | 正式任务 {r['sessions_formal']}")
    print()
    ho, ha = r["handoff_opening"], r["handoff_anywhere"]
    print(f"  HANDOFF 开头回读(前{r['opening_n']}调用): {ho['hit']}/{ho['total']} = {ho['pct']}%")
    print(f"  HANDOFF 整会话回读           : {ha['hit']}/{ha['total']} = {ha['pct']}%")
    st = r["status_anywhere"]
    print(f"  STATUS  整会话回读           : {st['hit']}/{st['total']} = {st['pct']}%")
    print()
    print("  各文档被 Read 频次(全部会话):")
    for name, n in sorted(r["doc_read_counts"].items(), key=lambda x: -x[1]):
        print(f"    {name:14}{n}")
    print()
    print("  解读：整会话回读=文档真实价值；开头回读=启动协议执行度。")
    print("  两者差距大 → 文档有用但'先读'协议没被遵守。")


if __name__ == "__main__":
    main()
