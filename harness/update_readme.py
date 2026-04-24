#!/usr/bin/env python3
"""
update_readme.py — 自动更新仓库 README 的统计数据和更新日志

扫描仓库实际内容，更新 README 中的数字和清单，并在底部追加更新日志条目。

用法：
    python update_readme.py                    # 更新 global-memory README
    python update_readme.py --skills           # 只更新 Skill/脚本统计
    python update_readme.py --memory           # 只更新 global-memory
    python update_readme.py --message "描述"   # 自定义更新日志条目
    python update_readme.py --dry-run          # 只看会做什么
"""

import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _lib import *


def count_skills():
    """统计 skills-repo 中的 Skill 数量"""
    count = 0
    if SKILLS_DIR.is_dir():
        for d in SKILLS_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("_") and (d / "v1" / "SKILL.md").exists():
                count += 1
    return count


def count_scripts():
    """统计 harness/ 中的脚本数量"""
    if not SCRIPTS_DIR.is_dir():
        return 0
    return sum(1 for f in SCRIPTS_DIR.iterdir() if f.suffix in (".py", ".sh", ".bat", ".vbs"))


def count_templates():
    """统计 templates/ 中的模板数量"""
    if not TEMPLATES_DIR.is_dir():
        return 0
    return sum(1 for f in TEMPLATES_DIR.glob("*.md"))


def count_memory_docs():
    """统计 knowledge/docs/ 中的文档数量"""
    if not DOCS_DIR.is_dir():
        return 0
    return sum(1 for f in DOCS_DIR.glob("*.md"))


def get_conventions_count():
    """统计 conventions.md 中的规范条数"""
    conv_file = MEMORY_DIR / "decisions" / "conventions.md"
    if not conv_file.exists():
        return 0, 0
    content = conv_file.read_text(encoding="utf-8", errors="replace")
    total = len(re.findall(r"^### \w+-\d+", content, re.MULTILINE))
    hard = len(re.findall(r"🔒", content))
    return total, hard


def update_skills_readme(message, dry_run=False):
    """更新 global-memory/README.md 中的 Skill/脚本统计。"""
    readme = MEMORY_DIR / "README.md"
    if not readme.exists():
        print("  ⚠️ global-memory/README.md 不存在")
        return False

    content = readme.read_text(encoding="utf-8", errors="replace")
    skill_count = count_skills()
    script_count = count_scripts()
    template_count = count_templates()

    # 更新 Skill 数量
    content = re.sub(
        r"## Skill 清单（\d+ 个）",
        f"## Skill 清单（{skill_count} 个）",
        content
    )

    # 更新 Harness 模板数量
    content = re.sub(
        r"## Harness 工程模板（\d+ 个）",
        f"## Harness 工程模板（{template_count} 个）",
        content
    )

    # 更新脚本数量
    content = re.sub(
        r"# 全局脚本（\d+ 个）",
        f"# 全局脚本（{script_count} 个）",
        content
    )

    # 追加更新日志
    log_entry = f"\n- **{today_str()}**: {message}\n"

    if "## 更新日志" not in content:
        content += f"\n## 更新日志\n{log_entry}"
    else:
        content = content.replace(
            "## 更新日志\n",
            f"## 更新日志\n{log_entry}",
        )

    if dry_run:
        print(f"  [DRY] runtime: {skill_count} skills, {script_count} scripts, {template_count} templates")
        return True

    readme.write_text(content, encoding="utf-8")
    print(f"  ✅ runtime README 统计已更新: {skill_count} skills, {script_count} scripts, {template_count} templates")
    write_log("update_readme", f"runtime: {skill_count}S/{script_count}sc/{template_count}T - {message}")
    return True


def update_memory_readme(message, dry_run=False):
    """更新 global-memory/README.md"""
    readme = MEMORY_DIR / "README.md"
    if not readme.exists():
        print("  ⚠️ global-memory/README.md 不存在")
        return False

    content = readme.read_text(encoding="utf-8", errors="replace")
    file_count = count_all_memory_files()
    doc_count = count_memory_docs()
    conv_total, conv_hard = get_conventions_count()

    # 更新 docs 数量
    content = re.sub(
        r"\| \*\*knowledge/docs/\*\* \|.*?\| \d+ \|",
        f"| **knowledge/docs/** | 深度知识文档（UE 全景图/多线程/面试追问链等） | {doc_count} |",
        content
    )

    # 更新规范数量
    content = re.sub(
        r"当前 \d+ 条规范，\d+ 条有硬检查。",
        f"当前 {conv_total} 条规范，{conv_hard} 条有硬检查。",
        content
    )

    # 更新容量统计
    content = re.sub(
        r"Topic 文件总数 \| ≤ 50 个（当前.*?\）",
        f"Topic 文件总数 | ≤ 50 个（当前 {file_count}）",
        content
    )

    # 追加更新日志
    log_entry = f"\n- **{today_str()}**: {message}\n"

    if "## 更新日志" not in content:
        content += f"\n## 更新日志\n{log_entry}"
    else:
        content = content.replace(
            "## 更新日志\n",
            f"## 更新日志\n{log_entry}",
        )

    if dry_run:
        print(f"  [DRY] global-memory: {file_count} files, {doc_count} docs, {conv_total} conventions")
        return True

    readme.write_text(content, encoding="utf-8")
    print(f"  ✅ global-memory README 已更新: {file_count} files, {doc_count} docs, {conv_total} conventions")
    write_log("update_readme", f"global-memory: {file_count}F/{doc_count}D/{conv_total}C - {message}")
    return True


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    do_skills = "--skills" in sys.argv
    do_memory = "--memory" in sys.argv
    do_all = not do_skills and not do_memory

    # 提取 --message
    message = "常规更新"
    for i, arg in enumerate(sys.argv):
        if arg == "--message" and i + 1 < len(sys.argv):
            message = sys.argv[i + 1]
            break

    if do_all or do_skills:
        update_skills_readme(message, dry)
    if do_all or do_memory:
        update_memory_readme(message, dry)
