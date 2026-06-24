#!/usr/bin/env python
"""analyze_retrieve_log.py — 分析 retrieve_calls.jsonl 产出数据驱动 keyword 建议

默认读 ~/.global-memory/logs/retrieve_calls.jsonl；不存在时 fallback 到 ~/.claude/logs/retrieve_calls.jsonl。输出：
- noisy_kw：高频出现但被推到 top1 的 keyword（候选剪枝）
- miss_query：召回 0 的 query（候选加 alias / 补 frontmatter）
- namespace 分布：tool: vs concept: vs error: 占比
- 调用规模：总次数 / 平均延迟 / hit_count 分布

默认读共享 retrieve_calls.jsonl；共享日志不存在时读旧 Claude retrieve_calls.jsonl。
schema_version: v1
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import GLOBAL_MEMORY_LOGS_DIR  # noqa: E402

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_SHARED_LOG = GLOBAL_MEMORY_LOGS_DIR / "retrieve_calls.jsonl"
LEGACY_LOG = Path.home() / ".claude" / "logs" / "retrieve_calls.jsonl"
DEFAULT_TOOL_AUDIT = Path.home() / ".claude" / "logs" / "tool_audit.jsonl"


def default_log_path() -> Path:
    """Prefer shared local runtime log; fallback to legacy Claude retrieve log."""
    if DEFAULT_SHARED_LOG.exists():
        return DEFAULT_SHARED_LOG
    return LEGACY_LOG
SCHEMA_VERSION = "v2"

# 召回 → 真 Read 的关联窗口（同 session 内 N 分钟）
CONSUMPTION_WINDOW_MIN = 30


def load_records(log_path: Path, days: int | None = None) -> list[dict]:
    if not log_path.exists():
        return []
    out: list[dict] = []
    cutoff = None
    if days:
        cutoff = datetime.now() - timedelta(days=days)
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if cutoff:
                try:
                    ts = datetime.fromisoformat(r.get("ts", ""))
                    if ts < cutoff:
                        continue
                except Exception:
                    pass
            out.append(r)
    return out


def load_tool_audit(path: Path, days: int | None = None) -> list[dict]:
    """tool_audit.jsonl schema: {ts, session, tool, input_summary, cwd}"""
    if not path.exists():
        return []
    out: list[dict] = []
    cutoff = datetime.now() - timedelta(days=days) if days else None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if cutoff:
                try:
                    if datetime.fromisoformat(r.get("ts", "")) < cutoff:
                        continue
                except Exception:
                    pass
            out.append(r)
    return out


def _norm_path(p: str) -> str:
    """归一化路径用于 Read input_summary ↔ retrieve all_hits.path 对账。

    去 .proposed 后缀：dual-storage 期间，用户可能 Read 的是 `.proposed` 变体
    （diff 评审用），但 retrieve 召回主文件 path。算作同一文件被消费。
    """
    if not p:
        return ""
    s = p.replace("\\", "/").strip().lower()
    if s.endswith(".proposed"):
        s = s[: -len(".proposed")]
    return s


def compute_consumption(
    retrieve_records: list[dict],
    audit_records: list[dict],
    window_min: int = CONSUMPTION_WINDOW_MIN,
) -> dict:
    """真消费率：召回的 pointer 在同 session 后续窗口内是否被 Read 工具真访问。

    返回：
      - call_rate：≥1 个 pointer 被 Read 的 retrieve 调用 / 总 retrieve 调用
      - pointer_rate：被 Read 的 pointer 数 / 总召回 pointer 数
      - noisy_pointers：召回 >=3 次但从未被 Read 的 pointer top10
      - per_task_call_rate：按 task 拆分
    """
    if not retrieve_records:
        return {"note": "no retrieve records"}

    # 索引 Read 调用：(session, norm_path) → [ts...]
    read_index: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for a in audit_records:
        if a.get("tool") != "Read":
            continue
        sess = a.get("session", "")
        norm = _norm_path(a.get("input_summary", ""))
        if not norm:
            continue
        try:
            ts = datetime.fromisoformat(a["ts"])
        except Exception:
            continue
        read_index[(sess, norm)].append(ts)

    window = timedelta(minutes=window_min)
    calls_with_any_consumed = 0
    total_pointers = 0
    consumed_pointers = 0
    pointer_recall_freq: Counter = Counter()
    pointer_consumed_freq: Counter = Counter()
    per_task_total: Counter = Counter()
    per_task_consumed: Counter = Counter()

    for r in retrieve_records:
        sess = r.get("session", "")  # may be missing in older logs
        task = r.get("task") or "<no-task>"
        try:
            r_ts = datetime.fromisoformat(r["ts"])
        except Exception:
            continue
        hits = r.get("all_hits") or []
        if not hits:
            continue
        per_task_total[task] += 1
        any_consumed = False
        for h in hits:
            path = h.get("path", "")
            norm = _norm_path(path)
            if not norm:
                continue
            total_pointers += 1
            pointer_recall_freq[path] += 1
            # session 优先用 retrieve 自己记录的，没有的话退化为「全 session 内任意 Read」
            candidates: list[datetime] = []
            if sess:
                candidates = read_index.get((sess, norm), [])
            if not candidates:
                # fallback：扫所有 session 的同路径 Read（旧 retrieve 日志无 session 字段）
                for (s, n), ts_list in read_index.items():
                    if n == norm:
                        candidates.extend(ts_list)
            # 命中窗口内
            if any(r_ts <= rt <= r_ts + window for rt in candidates):
                consumed_pointers += 1
                pointer_consumed_freq[path] += 1
                any_consumed = True
        if any_consumed:
            calls_with_any_consumed += 1
            per_task_consumed[task] += 1

    total_calls = sum(per_task_total.values())
    noisy = [
        {"path": p, "recalled": n, "consumed": pointer_consumed_freq.get(p, 0)}
        for p, n in pointer_recall_freq.most_common(50)
        if n >= 3 and pointer_consumed_freq.get(p, 0) == 0
    ][:10]

    per_task = {}
    for task, total in per_task_total.most_common():
        c = per_task_consumed.get(task, 0)
        per_task[task] = {
            "total_calls": total,
            "consumed_calls": c,
            "call_rate": round(c / total, 3) if total else 0,
        }

    return {
        "window_minutes": window_min,
        "total_retrieve_calls_with_hits": total_calls,
        "calls_with_any_pointer_read": calls_with_any_consumed,
        "call_rate": round(calls_with_any_consumed / total_calls, 3) if total_calls else 0,
        "total_pointers_recalled": total_pointers,
        "pointers_actually_read": consumed_pointers,
        "pointer_rate": round(consumed_pointers / total_pointers, 3) if total_pointers else 0,
        "noisy_pointers_top10": noisy,
        "per_task_call_rate": per_task,
    }


def analyze(records: list[dict]) -> dict:
    if not records:
        return {
            "schema_version": SCHEMA_VERSION,
            "total_calls": 0,
            "note": "no records",
        }

    total = len(records)
    hit_counts = Counter(r.get("hit_count", 0) for r in records)
    zero_hit = hit_counts.get(0, 0)
    elapsed = [r.get("elapsed_ms", 0) for r in records if r.get("elapsed_ms")]
    avg_ms = sum(elapsed) / len(elapsed) if elapsed else 0.0

    top1_paths = Counter()
    why_freq = Counter()
    namespace_freq = Counter()
    miss_queries: list[dict] = []

    for r in records:
        if r.get("hit_count", 0) == 0:
            miss_queries.append({
                "ts": r.get("ts"),
                "task": r.get("task"),
                "query": r.get("query"),
            })
            continue
        if r.get("top1_path"):
            top1_paths[r["top1_path"]] += 1
        for hit in r.get("all_hits", []):
            why = hit.get("why", "")
            for token in why.split(","):
                token = token.strip()
                if not token:
                    continue
                why_freq[token] += 1
                parts = token.split(":")
                if len(parts) >= 3 and parts[0] in ("kw", "fuzzy"):
                    ns = parts[1]
                    namespace_freq[ns] += 1

    noisy_kw = []
    for token, freq in why_freq.most_common(20):
        share = freq / total if total else 0
        if share >= 0.15 and freq >= 3:
            noisy_kw.append({"why": token, "freq": freq, "share": round(share, 3)})

    return {
        "schema_version": SCHEMA_VERSION,
        "total_calls": total,
        "zero_hit_calls": zero_hit,
        "zero_hit_rate": round(zero_hit / total, 3) if total else 0,
        "avg_elapsed_ms": round(avg_ms, 1),
        "hit_count_distribution": dict(sorted(hit_counts.items())),
        "top1_path_top10": top1_paths.most_common(10),
        "noisy_kw_candidates": noisy_kw,
        "namespace_distribution": dict(namespace_freq),
        "miss_queries_sample": miss_queries[:20],
        "miss_queries_total": len(miss_queries),
    }


def format_report(result: dict) -> str:
    if result.get("total_calls", 0) == 0:
        return "# Retrieve Log Analysis\n\nNo records.\n"
    lines = [
        "# Retrieve Log Analysis",
        "",
        f"- 总调用：{result['total_calls']}",
        f"- 空召回：{result['zero_hit_calls']} ({result['zero_hit_rate'] * 100:.1f}%)",
        f"- 平均延迟：{result['avg_elapsed_ms']}ms",
        "",
        "## hit_count 分布",
        "",
    ]
    for cnt, n in result["hit_count_distribution"].items():
        lines.append(f"- {cnt} hits: {n}")
    lines += ["", "## 噪声 kw 候选（high freq + high share）", ""]
    if not result["noisy_kw_candidates"]:
        lines.append("- 无")
    else:
        for nk in result["noisy_kw_candidates"]:
            lines.append(f"- `{nk['why']}` freq={nk['freq']} share={nk['share']}")
    lines += ["", "## top1 命中文件 top10", ""]
    for path, cnt in result["top1_path_top10"]:
        lines.append(f"- {cnt}x {path}")
    lines += ["", "## namespace 分布", ""]
    for ns, cnt in sorted(result["namespace_distribution"].items(), key=lambda x: -x[1]):
        lines.append(f"- {ns}: {cnt}")
    lines += ["", f"## 空召回 query（共 {result['miss_queries_total']}，前 20）", ""]
    for mq in result["miss_queries_sample"]:
        lines.append(f"- [{mq.get('ts')}] task={mq.get('task')} query={mq.get('query')!r}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Analyze retrieve_calls.jsonl")
    p.add_argument("--log", default=None, help="retrieve_calls.jsonl path; default shared log, fallback legacy Claude log")
    p.add_argument("--audit", default=str(DEFAULT_TOOL_AUDIT),
                   help="tool_audit.jsonl path (用于 --consumption)")
    p.add_argument("--days", type=int, default=None, help="filter last N days")
    p.add_argument("--json", action="store_true")
    p.add_argument("--consumption", action="store_true",
                   help="只跑真消费率指标（交叉 tool_audit Read）")
    p.add_argument("--window-min", type=int, default=CONSUMPTION_WINDOW_MIN,
                   help=f"真消费率关联窗口分钟数（默认 {CONSUMPTION_WINDOW_MIN}）")
    args = p.parse_args(argv)

    log_path = Path(args.log) if args.log else default_log_path()
    records = load_records(log_path, days=args.days)

    if args.consumption:
        audits = load_tool_audit(Path(args.audit), days=args.days)
        result = compute_consumption(records, audits, window_min=args.window_min)
        if args.json:
            sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            sys.stdout.write("\n")
        else:
            if result.get("note"):
                sys.stdout.write(f"# Consumption Rate\n\n{result['note']}\n")
            else:
                sys.stdout.write(
                    f"# Retrieve 真消费率 (window={result['window_minutes']}min)\n\n"
                    f"- 总 retrieve 调用（含 hit）：{result['total_retrieve_calls_with_hits']}\n"
                    f"- ≥1 pointer 被 Read 的调用：{result['calls_with_any_pointer_read']}\n"
                    f"- **call_rate**：{result['call_rate'] * 100:.1f}%\n"
                    f"- 召回 pointer 总数：{result['total_pointers_recalled']}\n"
                    f"- 实际被 Read 的 pointer 数：{result['pointers_actually_read']}\n"
                    f"- **pointer_rate**：{result['pointer_rate'] * 100:.1f}%\n\n"
                    f"## 噪声 pointer top10（召回 ≥3 次从未被 Read）\n\n"
                )
                if not result["noisy_pointers_top10"]:
                    sys.stdout.write("- 无\n")
                else:
                    for np in result["noisy_pointers_top10"]:
                        sys.stdout.write(f"- {np['recalled']}× recalled, 0 read: {np['path']}\n")
                sys.stdout.write("\n## 按 task 拆分\n\n")
                for task, st in result["per_task_call_rate"].items():
                    sys.stdout.write(
                        f"- {task}: {st['consumed_calls']}/{st['total_calls']} "
                        f"({st['call_rate'] * 100:.1f}%)\n"
                    )
        return 0

    result = analyze(records)
    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
