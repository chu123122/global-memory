"""检测「改记忆当场记 CHANGELOG」铁律是否生效。

原理：
  - memory_writes.jsonl 记录所有 Edit/Write 落在 global-memory 内的时间
  - CHANGELOG.md 自身被 Edit 也算 memory_write，需排除
  - 找近 24h 内非 CHANGELOG 的 memory_write 时间 t_mem
  - 找 CHANGELOG.md 末尾日期戳 t_changelog
  - 如果存在 t_mem > t_changelog 且 > 30 分钟 → 漂移
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..registry import Signal, register

REPO_DIR = Path(__file__).resolve().parents[3]
LOG_PATH = Path.home() / ".claude" / "logs" / "memory_writes.jsonl"
CHANGELOG_PATH = REPO_DIR / "CHANGELOG.md"

WINDOW_HOURS = 24
GRACE_MIN = 30
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


@register("changelog_drift")
def check() -> list[Signal]:
    if not LOG_PATH.exists() or not CHANGELOG_PATH.exists():
        return [Signal("changelog_drift", "info", "memory_writes.jsonl 或 CHANGELOG.md 不存在")]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    recent_writes: list[tuple[datetime, str]] = []
    with LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_raw = obj.get("ts", "")
            try:
                t = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if t < cutoff:
                continue
            f = (obj.get("file") or "").replace("\\", "/")
            if f.endswith("CHANGELOG.md"):
                continue
            recent_writes.append((t, f))
    if not recent_writes:
        return [Signal("changelog_drift", "ok", f"近 {WINDOW_HOURS}h 无非 CHANGELOG 记忆写入")]

    text = CHANGELOG_PATH.read_text(encoding="utf-8", errors="replace")
    dates = DATE_RE.findall(text)
    if not dates:
        return [Signal("changelog_drift", "warning", "CHANGELOG.md 解析不到日期戳")]
    last_date = max(dates)
    try:
        t_changelog = datetime.fromisoformat(last_date).replace(tzinfo=timezone.utc) + timedelta(hours=24)
    except ValueError:
        return [Signal("changelog_drift", "warning", f"CHANGELOG.md 末尾日期 {last_date} 解析失败")]

    threshold = t_changelog + timedelta(minutes=GRACE_MIN)
    drifts = [(t, f) for t, f in recent_writes if t > threshold]
    if not drifts:
        return [
            Signal(
                check_id="changelog_drift",
                status="ok",
                headline=f"CHANGELOG 与近 {WINDOW_HOURS}h 记忆写入对齐",
                value=f"last CHANGELOG date={last_date}",
            )
        ]
    files_unique = sorted({f for _, f in drifts})
    status = "critical" if len(files_unique) >= 5 else "warning"
    return [
        Signal(
            check_id="changelog_drift",
            status=status,
            headline=f"{len(files_unique)} 个记忆文件在 CHANGELOG {last_date} 之后被改且无新条目",
            value=f"{len(drifts)} 次写入未记 CHANGELOG",
            evidence=[f"{t.isoformat(timespec='minutes')} {f}" for t, f in drifts[-6:]],
            fix_hint="在 CHANGELOG.md 末尾追加今天的 ## 日期 段，描述这些改动",
        )
    ]
