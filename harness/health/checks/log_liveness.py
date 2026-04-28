"""复用 log_health.scan() 输出，把 STALE/DEAD 提为 signal。

任何 DEAD = critical；STALE 数量 > 0 = warning；EMPTY 不报。
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..registry import Signal, register

HARNESS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HARNESS_DIR))


@register("log_liveness")
def check() -> list[Signal]:
    from log_health import scan  # type: ignore[import-not-found]

    rows = scan()
    if not rows:
        return [Signal("log_liveness", "info", "logs 目录空")]
    dead = [r for r in rows if r["status"] == "DEAD"]
    stale = [r for r in rows if r["status"] == "STALE"]
    alive = [r for r in rows if r["status"] == "ALIVE"]
    if dead:
        status = "critical"
    elif stale:
        status = "warning"
    else:
        status = "ok"
    headline = (
        f"jsonl 日志 {len(alive)} 活 / {len(stale)} 久未写 / {len(dead)} 死"
    )
    evidence = [f"{r['status']:<5} {r['name']}（{r['age_days']:.1f} 天）" for r in stale + dead]
    return [
        Signal(
            check_id="log_liveness",
            status=status,
            headline=headline,
            value=f"alive={len(alive)} stale={len(stale)} dead={len(dead)}",
            evidence=evidence,
            fix_hint="DEAD 文件长期 0 写入 → 弃用或删脚本；STALE > 14 天将转 DEAD",
        )
    ]
