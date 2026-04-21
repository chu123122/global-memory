#!/usr/bin/env python3
"""
diff_backup.py — PreToolUse(Write|Edit) hook：编辑前备份原文件，供后续 diff_show.py 弹窗对比。

仅对 WHITELIST 内的目录生效。备份覆盖式存储（每文件只保留最近一次），
键名用 文件名 + 路径 sha1[:8] 命名以避免不同目录同名文件冲突。

新建文件无原内容可备份 → 跳过（diff_show.py 也会跳过）。
"""

import hashlib
import shutil
import sys
from pathlib import Path

# 复用项目 hook 共享库
sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, allow

# ── 白名单目录前缀（只对这些目录下的文件生效，扩展直接加路径）──
WHITELIST = [
    r"D:\ClaudeTasks\active",
    r"C:\Perforce\tl_gaoxinag_01\frontend\trunk\Editor\UE_game\Plugins\XDAdaptivePerformance",
]

BACKUP_DIR = Path(r"D:\ClaudeTasks\.diff_backup")


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


def main():
    data = read_hook_input()
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path or not in_whitelist(file_path):
        allow()

    src = Path(file_path)
    if not src.exists():
        # 新建文件没东西可备份
        allow()

    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, backup_path(file_path))
    except Exception:
        # 备份失败不阻塞编辑
        pass
    allow()


if __name__ == "__main__":
    main()
