#!/usr/bin/env python3
"""
diff_show.py — PostToolUse(Write|Edit) hook：编辑后异步弹 VS Code 三栏 diff 视图。

只在 WHITELIST 内目录生效；同文件 5 秒内重复编辑只弹一次（debounce）；
新建文件无备份则不弹（弹也无对比意义）。

VS Code 通过 `code --diff <bak> <file>` 启动；Popen 异步、不阻塞 hook 退出。
"""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, allow

# ── 与 diff_backup.py 保持同步（手动）──
WHITELIST = [
    r"D:\ClaudeTasks\active",
    r"C:\Perforce\tl_gaoxinag_01\frontend\trunk\Editor\UE_game\Plugins\XDAdaptivePerformance",
]

BACKUP_DIR = Path(r"D:\ClaudeTasks\.diff_backup")
DEBOUNCE_FILE = BACKUP_DIR / "_lastshow.json"
DEBOUNCE_SECONDS = 5


def in_whitelist(file_path: str) -> bool:
    try:
        fp = Path(file_path).resolve()
    except Exception:
        return False
    for w in WHITELIST:
        try:
            fp.relative_to(Path(w).resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def backup_path(file_path: str) -> Path:
    h = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:8]
    name = Path(file_path).name
    return BACKUP_DIR / f"{name}.{h}.bak"


def is_debounced(file_path: str) -> bool:
    if not DEBOUNCE_FILE.exists():
        return False
    try:
        data = json.loads(DEBOUNCE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (time.time() - data.get(file_path, 0)) < DEBOUNCE_SECONDS


def update_debounce(file_path: str):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if DEBOUNCE_FILE.exists():
        try:
            data = json.loads(DEBOUNCE_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[file_path] = time.time()
    DEBOUNCE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def main():
    data = read_hook_input()
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path or not in_whitelist(file_path):
        allow()

    if is_debounced(file_path):
        allow()

    bak = backup_path(file_path)
    if not bak.exists():
        allow()

    try:
        # shell=True + start "" 让 Windows 真正异步启动 code，不阻塞 hook
        subprocess.Popen(
            f'start "" code --diff "{bak}" "{file_path}"',
            shell=True,
        )
        update_debounce(file_path)
    except Exception:
        pass
    allow()


if __name__ == "__main__":
    main()
