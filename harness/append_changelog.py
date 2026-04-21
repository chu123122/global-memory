#!/usr/bin/env python3
"""
append_changelog.py — 追加 CHANGELOG.md 审计记录

用法：
    python append_changelog.py CREATE "文件路径" "来源项目" "变更内容" "原因"
    python append_changelog.py UPDATE "decisions/conventions.md" "帧同步v2" "新增DOC-05" "开发文档规范"
    python append_changelog.py PROMOTE "conventions" "博客项目" "新增规范" "跨项目复用"

操作类型：CREATE | UPDATE | DELETE | PROMOTE
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _lib import *


def append_changelog(op_type, filepath, source, content_desc, reason):
    print(f"=== append_changelog: {op_type} {filepath} ===\n")

    if not CHANGELOG_MD.exists():
        print("  ❌ CHANGELOG.md 不存在")
        return False

    entry = (
        f"\n### {now_str()} {op_type} {filepath}\n"
        f"- **来源项目**：{source}\n"
        f"- **变更内容**：{content_desc}\n"
        f"- **原因/案例**：{reason}\n"
        f"- **影响范围**：{'所有项目' if source == '通用' else source + ' 项目'}\n"
    )

    with open(CHANGELOG_MD, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"  ✅ 已追加 CHANGELOG 记录")
    write_log("append_changelog", f"{op_type} {filepath} (from {source})")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print('用法: python append_changelog.py TYPE "文件" "来源" "内容" "原因"')
        print('TYPE: CREATE | UPDATE | DELETE | PROMOTE')
        sys.exit(1)
    append_changelog(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
