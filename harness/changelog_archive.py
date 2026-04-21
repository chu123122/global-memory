#!/usr/bin/env python3
"""
changelog_archive.py — CHANGELOG 周归档脚本

功能：
  - 将 CHANGELOG.md 中超过 7 天的记录移入 CHANGELOG_archive/YYYY-WNN.md
  - CHANGELOG.md 只保留最近 7 天的记录 + 格式头部
  - 建议每周一自动运行（可集成到 auto_sync_daemon 或 cron）

用法：
  python changelog_archive.py                # 归档 7 天前的记录
  python changelog_archive.py --days 14      # 归档 14 天前的记录
  python changelog_archive.py --dry-run      # 只显示会归档什么，不实际操作
"""

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", os.path.expanduser("~/.claude/global-memory")))
CHANGELOG = MEMORY_DIR / "CHANGELOG.md"
ARCHIVE_DIR = MEMORY_DIR / "CHANGELOG_archive"


def parse_entries(content: str):
    """解析 CHANGELOG.md，分离头部和条目"""
    lines = content.split("\n")
    header_lines = []
    entries = []
    current_entry = []
    in_header = True

    for line in lines:
        if in_header:
            if re.match(r"^### \d{4}-\d{2}-\d{2}", line):
                in_header = False
                current_entry = [line]
            else:
                header_lines.append(line)
        else:
            if re.match(r"^### \d{4}-\d{2}-\d{2}", line):
                if current_entry:
                    entries.append("\n".join(current_entry))
                current_entry = [line]
            else:
                current_entry.append(line)

    if current_entry:
        entries.append("\n".join(current_entry))

    return "\n".join(header_lines), entries


def get_entry_date(entry: str) -> datetime | None:
    """从条目中提取日期"""
    match = re.match(r"^### (\d{4}-\d{2}-\d{2})", entry)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            return None
    return None


def get_week_key(dt: datetime) -> str:
    """获取 ISO 周标识 YYYY-WNN"""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def main():
    days = 7
    dry_run = False

    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--days":
            idx = sys.argv.index("--days")
            days = int(sys.argv[idx + 1])

    if not CHANGELOG.exists():
        print(f"  ❌ {CHANGELOG} 不存在")
        return 1

    content = CHANGELOG.read_text(encoding="utf-8")
    header, entries = parse_entries(content)

    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    archive_groups = {}  # week_key -> [entries]

    for entry in entries:
        entry_date = get_entry_date(entry)
        if entry_date is None:
            recent.append(entry)  # 无法解析日期的保留
            continue

        if entry_date >= cutoff:
            recent.append(entry)
        else:
            week_key = get_week_key(entry_date)
            archive_groups.setdefault(week_key, []).append(entry)

    archive_count = sum(len(v) for v in archive_groups.values())

    if archive_count == 0:
        print(f"  ✅ 没有超过 {days} 天的记录需要归档")
        return 0

    print(f"  📦 将归档 {archive_count} 条记录（{len(archive_groups)} 个周文件）")
    print(f"  📋 保留 {len(recent)} 条近期记录")

    if dry_run:
        for week, ents in sorted(archive_groups.items()):
            print(f"     → {week}: {len(ents)} 条")
        print("  (--dry-run 模式，未实际操作)")
        return 0

    # 创建归档目录
    ARCHIVE_DIR.mkdir(exist_ok=True)

    # 写入归档文件
    for week_key, week_entries in sorted(archive_groups.items()):
        archive_file = ARCHIVE_DIR / f"{week_key}.md"
        archive_header = f"# CHANGELOG 归档 — {week_key}\n\n"

        if archive_file.exists():
            existing = archive_file.read_text(encoding="utf-8")
            new_content = existing.rstrip() + "\n\n" + "\n\n".join(week_entries) + "\n"
        else:
            new_content = archive_header + "\n\n".join(week_entries) + "\n"

        archive_file.write_text(new_content, encoding="utf-8")
        print(f"  ✅ {archive_file.name}: {len(week_entries)} 条")

    # 重写 CHANGELOG.md（只保留头部 + 近期记录）
    new_changelog = header.rstrip() + "\n\n" + "\n\n".join(recent) + "\n"
    CHANGELOG.write_text(new_changelog, encoding="utf-8")
    print(f"  ✅ CHANGELOG.md 更新完成（保留 {len(recent)} 条）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
