#!/usr/bin/env python3
"""
load_context.py — Work Mode Step 0 上下文加载

输出：
1. ~/.claude/global-memory/MEMORY.md「🔥 当前活跃项目」表格
2. cwd 下 CLAUDE.md（如有）前 50 行

供 Claude Step 1 区分新/老任务时引用。
"""

import io
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CLAUDE_DIR = Path.home() / ".claude"
GLOBAL_MEMORY = CLAUDE_DIR / "global-memory" / "MEMORY.md"

ACTIVE_SECTION_RE = re.compile(
    r"##\s*🔥\s*当前活跃项目.*?(?=\n##\s|\Z)",
    re.DOTALL,
)


def extract_active_projects(memory_path: Path) -> str:
    if not memory_path.exists():
        return "(MEMORY.md 不存在)"
    try:
        content = memory_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"(MEMORY.md 读取失败：{e})"
    m = ACTIVE_SECTION_RE.search(content)
    if not m:
        return "(MEMORY.md 中未找到「🔥 当前活跃项目」章节)"
    return m.group(0).strip()


def read_cwd_claude_md(cwd: Path, max_lines: int = 50) -> str:
    target = cwd / "CLAUDE.md"
    if not target.exists():
        return ""
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        head = lines[:max_lines]
        more = f"\n... ({len(lines) - max_lines} 行未显示)" if len(lines) > max_lines else ""
        return "\n".join(head) + more
    except Exception as e:
        return f"(读取失败：{e})"


def main():
    print("[上下文加载]\n")

    print("--- 全局记忆活跃项目 ---")
    print(extract_active_projects(GLOBAL_MEMORY))
    print()

    cwd = Path(os.getcwd())
    print(f"--- cwd 项目说明（{cwd}） ---")
    claude_md = read_cwd_claude_md(cwd)
    if claude_md:
        print(claude_md)
    else:
        print("(cwd 下无 CLAUDE.md)")


if __name__ == "__main__":
    main()
