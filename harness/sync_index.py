#!/usr/bin/env python3
"""
sync_index.py — 重建 MEMORY.md 自动索引区

只重写 <!-- AUTO-INDEX:BEGIN --> ... <!-- AUTO-INDEX:END --> 之间的内容。
区块外的自定义章节（📌 系统规则 / 🏗️ 项目文档 / 📜 复盘记录 等）不会被触动。

首次运行时若文件中无 markers：从第一个 CATEGORY 标题（## Feedback...）
找到 ## 记忆统计 区块结束，整段替换为带 markers 的新版（legacy-migrate）。

用法：
    python sync_index.py              # 执行重建
    python sync_index.py --dry-run    # 只看会做什么
"""

import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _lib import *

AUTO_BEGIN = "<!-- AUTO-INDEX:BEGIN — 由 sync_index.py 维护，勿手动编辑 -->"
AUTO_END = "<!-- AUTO-INDEX:END -->"


def build_block(categories, file_count):
    lines = [AUTO_BEGIN, ""]
    for cat_name, files in categories.items():
        display = CATEGORY_NAMES.get(cat_name, cat_name)
        lines.append(f"## {display}")
        lines.append("| 文件 | 描述 | 更新时间 |")
        lines.append("|------|------|---------|")
        for f in files:
            lines.append(
                f"| [{f['name']}]({f['rel_path']}) | {f['description']} | {f['updated']} |"
            )
        lines.append("")
    lines.append("## 记忆统计")
    lines.append(f"- 总文件数：{file_count} / {MAX_FILES}（上限）")
    lines.append(f"- 最后维护时间：{today_str()}")
    lines.append("- 下次清理时间：（30 天后自动提醒）")
    lines.append(AUTO_END)
    return "\n".join(lines)


def find_legacy_span(content):
    """无 markers 时定位 legacy 自动区。
    起点 = 第一个匹配 CATEGORY_NAMES 的 ## 标题。
    终点 = ## 记忆统计 块之后的下一个 H1/H2，否则文件末尾。
    返回 (start_idx, end_idx) 或 None
    """
    lines = content.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            for cat_display in CATEGORY_NAMES.values():
                if cat_display in line:
                    start_idx = i
                    break
            if start_idx is not None:
                break
    if start_idx is None:
        return None

    stats_idx = None
    for i in range(start_idx, len(lines)):
        if lines[i].startswith("## 记忆统计"):
            stats_idx = i
            break

    if stats_idx is not None:
        end_idx = len(lines)
        for j in range(stats_idx + 1, len(lines)):
            if lines[j].startswith("## ") or lines[j].startswith("# "):
                end_idx = j
                break
    else:
        end_idx = len(lines)
        for j in range(start_idx + 1, len(lines)):
            if lines[j].startswith("## "):
                if not any(cd in lines[j] for cd in CATEGORY_NAMES.values()):
                    end_idx = j
                    break
    return (start_idx, end_idx)


def sync_index(dry_run=False):
    print("=== sync_index: 重建 MEMORY.md 索引（marker 模式）===\n")

    if not MEMORY_MD.exists():
        print("  ❌ MEMORY.md 不存在")
        return False

    content = MEMORY_MD.read_text(encoding="utf-8", errors="replace")
    categories = scan_topic_files()
    file_count = count_all_memory_files()
    new_block = build_block(categories, file_count)

    if AUTO_BEGIN in content and AUTO_END in content:
        mode = "marker"
        pattern = re.compile(
            re.escape(AUTO_BEGIN) + r".*?" + re.escape(AUTO_END),
            re.DOTALL,
        )
        new_content = pattern.sub(new_block, content)
    else:
        span = find_legacy_span(content)
        if span is None:
            print("  ⚠️ 未找到 markers 也未找到 legacy 区块，跳过")
            return False
        mode = "legacy-migrate"
        lines = content.splitlines()
        start_idx, end_idx = span
        # 防御：strip 任何残留的孤儿 marker（防止 update_stats 吃掉 END 后
        # 这里反复累积 BEGIN）
        def _is_stray_marker(line):
            return AUTO_BEGIN in line or AUTO_END in line
        before_lines = [l for l in lines[:start_idx] if not _is_stray_marker(l)]
        after_lines_raw = [l for l in lines[end_idx:] if not _is_stray_marker(l)]
        before = "\n".join(before_lines).rstrip() + "\n\n"
        after = "\n".join(after_lines_raw).lstrip("\n")
        new_content = before + new_block + (("\n\n" + after) if after else "\n")

    if not new_content.endswith("\n"):
        new_content += "\n"

    if dry_run:
        for cat, files in categories.items():
            print(f"  [DRY] {cat}: {len(files)} 个文件")
        print(f"  [DRY] 统计: {file_count} / {MAX_FILES}")
        print(f"  [DRY] 模式: {mode}")
        return True

    MEMORY_MD.write_text(new_content, encoding="utf-8")
    total = sum(len(f) for f in categories.values())
    print(f"  ✅ 索引已重建（{mode}）：{total} 个 topic 文件")
    print(f"  ✅ 统计已更新：{file_count} / {MAX_FILES}")
    write_log(
        "sync_index",
        f"PASS 索引重建({mode}): {total} topics, {file_count} total files",
    )
    return True


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sync_index(dry)
