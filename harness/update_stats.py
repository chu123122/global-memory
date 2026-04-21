#!/usr/bin/env python3
"""
update_stats.py — 更新 MEMORY.md 的记忆统计区块

只改统计数字，不动索引表。

用法：
    python update_stats.py
    python update_stats.py --dry-run
"""

import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _lib import *


def update_stats(dry_run=False):
    print("=== update_stats: 更新记忆统计 ===\n")

    if not MEMORY_MD.exists():
        print("  ❌ MEMORY.md 不存在")
        return False

    content = MEMORY_MD.read_text(encoding="utf-8", errors="replace")
    file_count = count_all_memory_files()

    new_stats = (
        f"## 记忆统计\n"
        f"- 总文件数：{file_count} / {MAX_FILES}（上限）\n"
        f"- 最后维护时间：{today_str()}\n"
        f"- 下次清理时间：（30 天后自动提醒）"
    )

    # 必须在 AUTO-INDEX:END / 下一个 H2 / EOF 之前停下，
    # 否则会把 sync_index 维护的 marker 一并吃掉，导致 marker 累积 bug
    pattern = r"## 记忆统计\n.*?(?=\n## |\n<!-- AUTO-INDEX:END|\Z)"
    if not re.search(pattern, content, re.DOTALL):
        print("  ⚠️ 未找到'记忆统计'区块")
        return False

    if dry_run:
        print(f"  [DRY] 文件数: {file_count} / {MAX_FILES}")
        return True

    new_content = re.sub(pattern, new_stats, content, flags=re.DOTALL)
    MEMORY_MD.write_text(new_content, encoding="utf-8")
    print(f"  ✅ 统计已更新：{file_count} / {MAX_FILES}")
    write_log("update_stats", f"PASS 文件数: {file_count}/{MAX_FILES}")
    return True


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    update_stats(dry)
