"""retrieve_hitrate.py — retrieve_calls.jsonl 命中质量周期检查。

跑 7 天窗口，输出 zero_hit_rate / top noisy kw / namespace 偏斜。
zero_hit_rate ≥ 30% → warning（漏召回多，加 alias / 补 frontmatter）
noisy_kw share ≥ 0.5 → warning（单 kw 被推过半，候选剪枝）
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from ..registry import Signal, register

LOG_PATH = Path.home() / ".claude" / "logs" / "retrieve_calls.jsonl"
WINDOW_DAYS = 7
ZERO_HIT_WARN = 0.30
NOISY_KW_SHARE_WARN = 0.50
NOISY_KW_MIN_FREQ = 5


@register("retrieve_hitrate")
def check() -> list[Signal]:
    if not LOG_PATH.exists():
        return [Signal("retrieve_hitrate", "info", "retrieve_calls.jsonl 不存在（retrieve 未被调用）")]
    cutoff = datetime.now() - timedelta(days=WINDOW_DAYS)
    total = 0
    zero = 0
    why_freq: Counter[str] = Counter()
    with LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = datetime.fromisoformat(r.get("ts", ""))
                if ts < cutoff:
                    continue
            except ValueError:
                continue
            total += 1
            if r.get("hit_count", 0) == 0:
                zero += 1
            for hit in r.get("all_hits", []):
                for token in (hit.get("why") or "").split(","):
                    token = token.strip()
                    if token:
                        why_freq[token] += 1

    if total == 0:
        return [Signal("retrieve_hitrate", "info", f"近 {WINDOW_DAYS} 天 retrieve 调用 0 次")]

    signals: list[Signal] = []
    zero_rate = zero / total
    base_status = "ok" if zero_rate < ZERO_HIT_WARN else "warning"
    signals.append(Signal(
        check_id="retrieve_hitrate",
        status=base_status,
        headline=f"近 {WINDOW_DAYS} 天 retrieve 调用 {total} 次，空召回率 {zero_rate * 100:.1f}%",
        value=f"{total} calls / zero_hit={zero}",
        fix_hint="zero_hit ≥30% → 补 aliases 或文件 frontmatter keywords" if base_status == "warning" else "",
    ))

    noisy = []
    for tok, freq in why_freq.most_common(10):
        if freq < NOISY_KW_MIN_FREQ:
            continue
        share = freq / total
        if share >= NOISY_KW_SHARE_WARN:
            noisy.append(f"{tok} freq={freq} share={share:.2f}")
    if noisy:
        signals.append(Signal(
            check_id="retrieve_hitrate",
            status="warning",
            headline=f"{len(noisy)} 个 keyword 覆盖率过高（噪声候选）",
            evidence=noisy,
            fix_hint="跑 analyze_retrieve_log.py 看详情；考虑从泛覆盖文件 frontmatter 删该 kw",
        ))
    return signals
