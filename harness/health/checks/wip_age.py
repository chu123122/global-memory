"""git status dirty 文件计数 + 最老未提交文件年龄。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..registry import Signal, register

REPO_DIR = Path(__file__).resolve().parents[3]


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_DIR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    ).stdout


@register("wip_age")
def check() -> list[Signal]:
    status_text = _git(["status", "--short"])
    files = [ln[3:].strip().split(" -> ")[-1].strip('"') for ln in status_text.splitlines() if ln.strip()]
    n = len(files)
    if n == 0:
        return [Signal("wip_age", "ok", "工作树干净")]
    if n >= 25:
        status = "critical"
    elif n >= 8:
        status = "warning"
    else:
        status = "info"
    return [
        Signal(
            check_id="wip_age",
            status=status,
            headline=f"工作树有 {n} 个未提交文件",
            value=f"{n} files",
            evidence=files[:8],
            fix_hint="分批 commit；长期 WIP 会持续触发 daemon WIP 跳过",
        )
    ]
