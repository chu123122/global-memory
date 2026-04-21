#!/usr/bin/env python3
"""
close_project.py — 从 MEMORY.md 活跃项目表中移除

用法：
    python close_project.py "博客重设计"
    python close_project.py --dry-run "博客重设计"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _lib import *


def close_project(name, dry_run=False):
    print(f"=== close_project: {name} ===\n")

    if not MEMORY_MD.exists():
        print("  ❌ MEMORY.md 不存在")
        return False

    content = MEMORY_MD.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    new_lines = []
    removed = False

    for line in lines:
        if line.startswith("|") and name in line and "仓库" not in line and "---" not in line:
            if dry_run:
                print(f"  [DRY] 会移除: {line.strip()}")
            else:
                print(f"  ✅ 已移除: {name}")
            removed = True
            continue
        new_lines.append(line)

    if not removed:
        print(f"  ⚠️ 未找到项目 '{name}'")
        return False

    if not dry_run:
        MEMORY_MD.write_text("\n".join(new_lines), encoding="utf-8")
        write_log("close_project", f"REMOVE {name}")
    return True


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if len(args) != 1:
        print('用法: python close_project.py "项目名"')
        sys.exit(1)
    close_project(args[0], dry_run=dry)
