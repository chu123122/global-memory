#!/usr/bin/env python3
"""
read_large_file_guard.py — PreToolUse Read hook

拦截已知大文件的全文读取。命中白名单且未带 offset/limit 时 exit 2，
注入 hook-prompts.md 中的结构导航提示。带 offset 或 limit 的分段读直接放行。

白名单键：文件名（basename）匹配——任意目录下同名文件都拦截。
新增条目：① 改 LARGE_FILES dict ② 在 hook-prompts.md 加对应段落。
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_lib import read_hook_input, deny, allow
from _prompt_loader import get_prompt

LARGE_FILES = {
    "CHANGELOG.md": "large-file/CHANGELOG.md",
}


def main():
    data = read_hook_input()
    if not data:
        allow()

    tool_input = data.get("tool_input", {})
    file_path = str(tool_input.get("file_path", ""))
    if not file_path:
        allow()

    if tool_input.get("offset") is not None or tool_input.get("limit") is not None:
        allow()

    basename = os.path.basename(file_path.replace("\\", "/"))
    section_id = LARGE_FILES.get(basename)
    if section_id is None:
        allow()

    msg = get_prompt(section_id)
    if not msg:
        msg = (
            f"⚠️ {basename} 已列入大文件白名单但未在 hook-prompts.md 配置导航提示。"
            f"请用 Read 带 offset/limit，或先 Grep 定位。"
        )
    deny(msg)


if __name__ == "__main__":
    main()
