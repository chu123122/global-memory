#!/usr/bin/env python3
"""
init_project.py — 在 MEMORY.md 活跃项目表中添加一行

用法：
    python init_project.py "博客重设计" "https://github.com/xxx/blog.git" "redesign-astro" "SPEC已完成"
    python init_project.py --dry-run "测试" "url" "main" "进度"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _lib import *


def init_project(name, repo, branch, progress, dry_run=False):
    print(f"=== init_project: {name} ===\n")

    if not MEMORY_MD.exists():
        print("  ❌ MEMORY.md 不存在")
        return False

    content = MEMORY_MD.read_text(encoding="utf-8", errors="replace")

    if name in content:
        print(f"  ⚠️ 项目 '{name}' 已存在，跳过")
        return False

    new_row = f"| **{name}** | [{name}]({repo}) | `{branch}` | {progress} | `docs/HANDOFF.md` |"
    anchor = "> 接手任何项目前"

    if anchor not in content:
        print("  ⚠️ 未找到活跃项目表锚点")
        return False

    if dry_run:
        print(f"  [DRY] 会添加: {name} ({repo} @ {branch})")
        return True

    new_content = content.replace(anchor, new_row + "\n\n" + anchor)
    MEMORY_MD.write_text(new_content, encoding="utf-8")
    print(f"  ✅ 已添加项目: {name}")
    write_log("init_project", f"ADD {name} @ {branch} ({repo})")
    return True


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if len(args) != 4:
        print('用法: python init_project.py "名称" "仓库URL" "分支" "进度"')
        sys.exit(1)
    init_project(*args, dry_run=dry)
