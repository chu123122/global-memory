"""统一健康检测入口。

  python harness/health/runner.py            # 文本表
  python harness/health/runner.py --json     # 给面板
  python harness/health/runner.py --check sync_failures  # 单个

每跑一次 append 一条聚合到 ~/.claude/logs/health_checks.jsonl 供后续趋势查询。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .registry import Signal, all_checks, run_check
from .checks import (  # noqa: F401  触发注册
    changelog_drift,
    ghost_refs,
    invocation_freq,
    knowledge_unread,
    log_liveness,
    memory_usage,
    sync_failures,
    traffic_imbalance,
    wip_age,
)

LOG_OUT = Path.home() / ".claude" / "logs" / "health_checks.jsonl"

STATUS_ORDER = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
STATUS_GLYPH = {"critical": "[X]", "warning": "[!]", "info": "[i]", "ok": "[v]"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def collect(only: str | None = None) -> list[Signal]:
    out: list[Signal] = []
    targets = {only: all_checks()[only]} if only else all_checks()
    for cid in targets:
        try:
            out.extend(run_check(cid))
        except Exception as exc:  # noqa: BLE001
            out.append(
                Signal(
                    check_id=cid,
                    status="critical",
                    headline=f"检测器自身异常：{type(exc).__name__}: {exc}",
                )
            )
    out.sort(key=lambda s: (STATUS_ORDER.get(s.status, 9), s.check_id))
    return out


def render_text(signals: list[Signal]) -> str:
    counts = {k: 0 for k in STATUS_ORDER}
    for s in signals:
        counts[s.status] = counts.get(s.status, 0) + 1
    head = " ".join(
        f"{STATUS_GLYPH[k]}{counts[k]}" for k in ("critical", "warning", "info", "ok")
    )
    lines = [f"=== Health Check ===  {head}", ""]
    for s in signals:
        lines.append(f"{STATUS_GLYPH.get(s.status,'?')} [{s.status:<8}] {s.check_id}")
        lines.append(f"   {s.headline}")
        if s.value:
            lines.append(f"   value: {s.value}")
        for ev in s.evidence[:6]:
            lines.append(f"     · {ev}")
        if s.fix_hint:
            lines.append(f"   ↳ {s.fix_hint}")
        lines.append("")
    return "\n".join(lines)


def append_log(signals: list[Signal]) -> None:
    LOG_OUT.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signals": [s.to_dict() for s in signals],
    }
    with LOG_OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--check", help="只跑指定 check_id")
    p.add_argument("--no-log", action="store_true", help="不 append 到 health_checks.jsonl")
    args = p.parse_args()

    try:
        signals = collect(args.check)
    except KeyError as exc:
        print(f"unknown check: {exc.args[0]}", file=sys.stderr)
        return 2

    if not args.no_log:
        append_log(signals)

    if args.json:
        json.dump(
            {"signals": [s.to_dict() for s in signals]},
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    else:
        print(render_text(signals))

    worst = min((STATUS_ORDER.get(s.status, 9) for s in signals), default=3)
    return 0 if worst >= 2 else 1  # critical/warning → exit 1


if __name__ == "__main__":
    sys.exit(main())
