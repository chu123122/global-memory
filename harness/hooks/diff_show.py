#!/usr/bin/env python3
"""
diff_show.py — PostToolUse(Write|Edit) hook：编辑后异步弹 VS Code 三栏 diff 视图。

只在归属 active_task 的文件上生效；同文件 5 秒内重复编辑只弹一次（debounce）；
新建文件无备份则不弹（弹也无对比意义）。

VS Code 通过 `code --diff <bak> <file>` 启动；Popen 异步、不阻塞 hook 退出。
"""

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, allow
from _task_resolver import load_registry, resolve_task_owner

DEBOUNCE_SECONDS = 5


def get_tasks_root(registry: dict) -> Path:
    tasks_root_raw = registry.get("tasks_root", "")
    return Path(tasks_root_raw) if tasks_root_raw else Path.home() / ".claude" / "projects"


def backup_path(file_path: str, task: str, tasks_root: Path) -> Path:
    h = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:8]
    name = Path(file_path).name
    return tasks_root / task / ".diff" / "now" / f"{name}.{h}.bak"


def debounce_file(tasks_root: Path) -> Path:
    return tasks_root / ".diff" / "_lastshow.json"


def is_debounced(file_path: str, tasks_root: Path) -> bool:
    state_file = debounce_file(tasks_root)
    if not state_file.exists():
        return False
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (time.time() - data.get(file_path, 0)) < DEBOUNCE_SECONDS


def update_debounce(file_path: str, tasks_root: Path):
    state_file = debounce_file(tasks_root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[file_path] = time.time()
    state_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def launch_code_diff_hidden(bak: Path, file_path: str) -> None:
    """Launch VS Code diff without flashing a transient cmd window on Windows."""
    if sys.platform == "win32":
        code_cmd = shutil.which("code") or shutil.which("code.cmd")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if code_cmd:
            subprocess.Popen(
                ["cmd", "/d", "/c", code_cmd, "--diff", str(bak), file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
                close_fds=True,
            )
            return
        # Last-resort fallback keeps the shell hidden even if only shell lookup works.
        subprocess.Popen(
            f'start "" code --diff "{bak}" "{file_path}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        return

    subprocess.Popen(
        ["code", "--diff", str(bak), file_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )


def main():
    data = read_hook_input()
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        allow()

    registry = load_registry()
    if not registry:
        allow()

    task = resolve_task_owner(file_path, registry)
    if not task:
        allow()

    tasks_root = get_tasks_root(registry)
    if is_debounced(file_path, tasks_root):
        allow()

    bak = backup_path(file_path, task, tasks_root)
    if not bak.exists():
        allow()

    try:
        launch_code_diff_hidden(bak, file_path)
        update_debounce(file_path, tasks_root)
        print(f"[diff_show] opened diff for {file_path.name}", file=sys.stderr)
    except Exception as e:
        print(f"[diff_show] failed: {e}", file=sys.stderr)
    allow()


if __name__ == "__main__":
    main()
