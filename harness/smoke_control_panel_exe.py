#!/usr/bin/env python3
"""smoke_control_panel_exe.py — 打包后主控台 exe 的递归自启冒烟测试

The PyInstaller onefile build normally leaves 2 processes for a short time
(launcher parent + extracted child). More than that usually means the frozen
GUI is using sys.executable to run harness scripts and recursively starting
itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from io import StringIO
from pathlib import Path


def tasklist() -> list[dict]:
    if not sys.platform.startswith("win"):
        return []
    proc = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq control_panel_pyside.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    rows = []
    for row in csv.reader(StringIO(proc.stdout)):
        if not row or row[0].startswith("INFO:"):
            continue
        rows.append({"image": row[0], "pid": int(row[1]), "session": row[2], "mem": row[4]})
    return rows


def kill_existing() -> None:
    subprocess.run(
        ["taskkill", "/F", "/IM", "control_panel_pyside.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def start_hidden(exe: Path) -> subprocess.Popen:
    startupinfo = None
    creationflags = 0
    if sys.platform.startswith("win"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [str(exe)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(exe.parent),
        startupinfo=startupinfo,
        creationflags=creationflags,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="smoke packaged control panel exe")
    parser.add_argument("--exe", default=str(Path(__file__).resolve().parent / "dist" / "control_panel_pyside.exe"))
    parser.add_argument("--wait", type=float, default=6.0)
    parser.add_argument("--max-processes", type=int, default=2)
    parser.add_argument("--kill-existing", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not sys.platform.startswith("win"):
        print("SKIP: control panel exe smoke is Windows-only")
        return 0

    exe = Path(args.exe).resolve()
    if not exe.exists():
        print(f"FAIL: exe not found: {exe}", file=sys.stderr)
        return 1

    before = tasklist()
    if before and not args.kill_existing:
        print("FAIL: control_panel_pyside.exe already running; use --kill-existing for smoke", file=sys.stderr)
        return 1
    if before:
        kill_existing()
        time.sleep(0.5)

    started = start_hidden(exe)
    time.sleep(args.wait)
    after = tasklist()
    ok = 1 <= len(after) <= args.max_processes
    kill_existing()
    report = {
        "exe": str(exe),
        "started_pid": started.pid,
        "wait_sec": args.wait,
        "process_count": len(after),
        "max_processes": args.max_processes,
        "processes": after,
        "ok": ok,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if ok else "FAIL"
        print(f"{status}: process_count={len(after)} max={args.max_processes}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
