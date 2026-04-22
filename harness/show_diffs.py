#!/usr/bin/env python3
"""
show_diffs.py — 手动 diff 入口（/diff skill 调用）

按 active_task 隔离的 diff 备份，扫每个 <task>/.diff/now/，
对每个 (bak, original) 对拉 VS Code Code.exe --diff 视图，然后归档 now/ → history/<ts>/。

入口：
    python show_diffs.py            # 所有 active_tasks
    python show_diffs.py all        # 同上
    python show_diffs.py <task>     # 单个 task（支持前缀模糊）

设计参见 D:/ClaudeTasks/active/diff-workflow-redesign/{REQUIREMENTS,DESIGN,SPEC}.md

退出码：
    0 = 成功（包括 opened=0）
    1 = 致命错误（registry 无法解析 / Code.exe 找不到 / task 名歧义无匹配）
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 复用 hooks/_task_resolver
sys.path.insert(0, str(Path(__file__).parent / "hooks"))
from _task_resolver import load_registry  # noqa: E402


def find_code_exe() -> Optional[str]:
    """code.cmd → parent.parent / Code.exe；找不到返回 None。"""
    code_cmd = shutil.which("code")
    if not code_cmd:
        return None
    if code_cmd.lower().endswith(".cmd"):
        candidate = Path(code_cmd).parent.parent / "Code.exe"
        if candidate.exists():
            return str(candidate)
    elif code_cmd.lower().endswith(".exe"):
        return code_cmd
    return None


def list_target_tasks(args: List[str], registry: dict) -> List[str]:
    """
    解析参数返回要处理的 task 名列表。
    无参数 / "all" → active_tasks 全集
    单 task → 精确 / 前缀模糊匹配
    歧义 / 无匹配 → 空列表 + stderr 提示
    """
    active_tasks = registry.get("active_tasks", []) or []
    if not args or (len(args) == 1 and args[0].lower() == "all"):
        return active_tasks

    target = args[0]
    if target in active_tasks:
        return [target]
    matches = [t for t in active_tasks if t.startswith(target)]
    if len(matches) == 1:
        return matches
    if len(matches) > 1:
        print(f"[diff] ambiguous task prefix '{target}': {matches}", file=sys.stderr)
        return []
    print(f"[diff] no task matched '{target}'. Active tasks: {active_tasks}", file=sys.stderr)
    return []


def open_diffs_for_task(task: str, code_exe: str, tasks_root: Path) -> int:
    """
    扫 <task>/.diff/now/_paths.json，对每对 (bak, original) 拉 Code.exe --diff。
    返回打开的 diff 数量（now/ 不存在或为空返回 0）。
    """
    now_dir = tasks_root / task / ".diff" / "now"
    pmap = now_dir / "_paths.json"
    if not pmap.exists():
        return 0
    try:
        paths = json.loads(pmap.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[diff] task={task} _paths.json parse failed: {e}", file=sys.stderr)
        return 0

    opened = 0
    for bak_name, orig_path in paths.items():
        bak = now_dir / bak_name
        if not bak.exists():
            continue
        if not Path(orig_path).exists():
            print(f"[diff] task={task} skip: original missing {orig_path}", file=sys.stderr)
            continue
        try:
            subprocess.Popen(
                [code_exe, "--diff", str(bak), orig_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            opened += 1
        except Exception as e:
            print(f"[diff] task={task} Popen failed for {orig_path}: {e}", file=sys.stderr)
    return opened


def archive_now(task: str, tasks_root: Path) -> Optional[Path]:
    """
    把 <task>/.diff/now/ 整体 mv 到 <task>/.diff/history/<YYYYMMDD-HHMMSS>/
    now/ 不存在或目录空 → 返回 None
    history/<ts>/ 已存在 → 加 -1/-2 后缀
    """
    now_dir = tasks_root / task / ".diff" / "now"
    if not now_dir.exists():
        return None
    if not any(now_dir.iterdir()):
        return None

    history_root = tasks_root / task / ".diff" / "history"
    history_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = history_root / ts
    suffix = 0
    while target.exists():
        suffix += 1
        target = history_root / f"{ts}-{suffix}"

    shutil.move(str(now_dir), str(target))
    return target


def main() -> int:
    registry = load_registry()
    if not registry:
        print("[diff] failed to load project_registry.json", file=sys.stderr)
        return 1

    code_exe = find_code_exe()
    if not code_exe:
        print(
            "[diff] Code.exe not found via 'code' CLI. "
            "Aborting (no archive). Check that VS Code 'code' is in PATH.",
            file=sys.stderr,
        )
        return 1

    tasks_root_raw = registry.get("tasks_root", "")
    tasks_root = Path(tasks_root_raw) if tasks_root_raw else Path.home() / ".claude" / "projects"

    targets = list_target_tasks(sys.argv[1:], registry)
    if not targets:
        return 1

    total_opened = 0
    for task in targets:
        opened = open_diffs_for_task(task, code_exe, tasks_root)
        if opened == 0:
            print(f"[diff] task={task} opened=0 (now/ empty or not found)")
            continue
        archive = archive_now(task, tasks_root)
        archive_str = (
            str(archive.relative_to(tasks_root)) if archive else "<not archived>"
        )
        print(f"[diff] task={task} opened={opened} → archived to {archive_str}")
        total_opened += opened

    print(f"[diff] total opened={total_opened}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
