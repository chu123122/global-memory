#!/usr/bin/env python3
"""governance_pulse.py — 周期性治理巡检 daemon

复用 `auto_sync_daemon.py` 框架结构（轮询 + 单次模式 + 静默失败），但目标不同：
- auto_sync_daemon：监 mtime，IDLE 后 git sync
- governance_pulse：固定周期跑治理检查，写 jsonl，供 statusline 红点消费

跑什么（一次 pulse）：
  1) gate_check.check_prereqs() → 取 fail/warn 数（套 warn_sunset）
  2) scan_orphan_scripts --json → 取 UNREGISTERED/STALE 计数
  3) scan_dual_storage → 取 dual_count

为什么不上 hook：D3 — Stop hook 已挤，PostToolUse Edit md 跑 gate_check 不可接受。
失败不破业务：D4 — pulse 自身异常吞掉只写 error 行。

输出：
  ~/.claude/logs/governance_pulse.jsonl  (每次 pulse 1 行)
  schema: {ts, ok, gate_fail, gate_overdue, orphans, stale_registry, dual_storage, error?}

用法：
  python governance_pulse.py --once        # 单次跑后退出（cron / 手工）
  python governance_pulse.py --daemon      # 每 30 min 一次（默认）
  python governance_pulse.py --interval 5  # 调试用，5 min 一次
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = HARNESS_DIR / "scripts"
PULSE_LOG = Path.home() / ".claude" / "logs" / "governance_pulse.jsonl"
DEFAULT_INTERVAL_MIN = 30

sys.path.insert(0, str(HARNESS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import run_utf8  # noqa: E402


def _parse_orphan_scan_summary(stdout: str) -> tuple[int, int]:
    data = json.loads(stdout)
    if data.get("kind") != "orphan_script_scan":
        raise ValueError("unexpected scan_orphan_scripts payload")
    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("scan_orphan_scripts summary missing")
    unregistered = summary.get("unregistered")
    stale = summary.get("stale_in_registry")
    if not isinstance(unregistered, int) or not isinstance(stale, int):
        raise ValueError("scan_orphan_scripts summary counts invalid")
    return unregistered, stale


def _parse_dual_storage_summary(stdout: str) -> int:
    data = json.loads(stdout)
    if data.get("kind") != "dual_storage_scan":
        raise ValueError("unexpected scan_dual_storage payload")
    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("scan_dual_storage summary missing")
    dual_count = summary.get("dual_count")
    if not isinstance(dual_count, int):
        raise ValueError("scan_dual_storage dual_count invalid")
    return dual_count


def run_one_pulse() -> dict:
    """跑一次治理体检。返回 jsonl-ready dict。"""
    rec: dict = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "ok": True,
        "gate_fail": 0,
        "gate_overdue": 0,
        "orphans": 0,
        "stale_registry": 0,
        "dual_storage": 0,
    }
    # 1) gate_check：导入而非 subprocess，省启动开销 + 拿结构化结果
    try:
        from gate_check import check_prereqs  # type: ignore
        prereqs = check_prereqs(strict_sunset=False)
        rec["gate_fail"] = sum(1 for r in prereqs if not r["pass"])
        rec["gate_overdue"] = sum(1 for r in prereqs if "[OVERDUE" in (r.get("detail") or ""))
    except Exception as e:
        rec["ok"] = False
        rec["error"] = f"gate_check: {e!r}"
    # 2) scan_orphan_scripts：消费 release profile 使用的 JSON 契约
    try:
        r = run_utf8([sys.executable, str(SCRIPTS_DIR / "scan_orphan_scripts.py"), "--json"], timeout=30)
        rec["orphans"], rec["stale_registry"] = _parse_orphan_scan_summary(r.stdout or "")
        if r.returncode != 0:
            raise RuntimeError(f"scan_orphan_scripts exited {r.returncode}")
    except Exception as e:
        rec["ok"] = False
        rec["error"] = (rec.get("error") or "") + f"; scan_orphan: {e!r}"
    # 3) scan_dual_storage：消费 JSON 契约，保留旧文本输出给 gate_check G1
    try:
        r = run_utf8([sys.executable, str(SCRIPTS_DIR / "scan_dual_storage.py"), "--json"], timeout=30)
        rec["dual_storage"] = _parse_dual_storage_summary(r.stdout or "")
        if r.returncode != 0:
            raise RuntimeError(f"scan_dual_storage exited {r.returncode}")
    except Exception as e:
        rec["ok"] = False
        rec["error"] = (rec.get("error") or "") + f"; dual_storage: {e!r}"
    return rec


def write_pulse(rec: dict, path: Path = PULSE_LOG) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass  # D4：失败不破业务


def latest_pulse(path: Path = PULSE_LOG) -> dict | None:
    """statusline 用：取最后一行 pulse 记录。"""
    if not path.exists():
        return None
    try:
        last = ""
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = line
        if not last:
            return None
        return json.loads(last)
    except (OSError, json.JSONDecodeError):
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="governance pulse daemon")
    p.add_argument("--once", action="store_true", help="单次跑后退出")
    p.add_argument("--daemon", action="store_true", help="周期循环（默认行为）")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_MIN,
                   help=f"轮询间隔分钟（默认 {DEFAULT_INTERVAL_MIN}）")
    p.add_argument("--show-latest", action="store_true", help="读最后一行 pulse 并打印（debug）")
    args = p.parse_args(argv)

    if args.show_latest:
        rec = latest_pulse()
        sys.stdout.write(json.dumps(rec, ensure_ascii=False, indent=2, default=str) + "\n")
        return 0

    if args.once or not args.daemon:
        rec = run_one_pulse()
        write_pulse(rec)
        sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return 0 if rec.get("ok") else 1

    interval_sec = max(60, args.interval * 60)
    sys.stderr.write(f"[governance_pulse] daemon start, interval={args.interval}min, log={PULSE_LOG}\n")
    try:
        while True:
            rec = run_one_pulse()
            write_pulse(rec)
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        sys.stderr.write("[governance_pulse] stopped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
