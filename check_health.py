#!/usr/bin/env python3
"""
check_health.py — 全局记忆仓库健康检查

检查项：
  1. 索引一致性 — MEMORY.md 引用的文件是否存在（死链）
  2. 孤儿文件   — topic 目录下未被 MEMORY.md 收录的文件
  3. 文件计数   — MEMORY.md 底部统计与实际是否一致
  4. YAML 规范  — topic 文件是否有合规的 frontmatter
  5. 跨层重复   — 项目级 memory 与全局 memory 同名文件
  6. Git 同步   — 未提交变更、远程同步状态

用法：
  python check_health.py           # 只检查
  python check_health.py --fix     # 检查 + 自动修复
  python check_health.py --json    # JSON 输出

退出码：0 = 全部通过，1 = WARNING，2 = ERROR
"""

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Windows UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 复用 _lib
sys.path.insert(0, str(Path.home() / ".claude" / "scripts"))
try:
    from _lib import (
        MEMORY_DIR, TOPIC_DIRS, MEMORY_MD, CHANGELOG_MD, DOCS_DIR,
        CATEGORY_NAMES, count_all_memory_files, extract_yaml_field,
        scan_topic_files, write_log, now_str, today_str,
    )
except ImportError:
    # 回退：内联关键常量
    MEMORY_DIR = Path.home() / ".claude" / "global-memory"
    TOPIC_DIRS = ["feedback", "knowledge", "fixes", "decisions", "interview"]
    MEMORY_MD = MEMORY_DIR / "MEMORY.md"
    CHANGELOG_MD = MEMORY_DIR / "CHANGELOG.md"
    DOCS_DIR = MEMORY_DIR / "knowledge" / "docs"
    CATEGORY_NAMES = {
        "feedback": "Feedback（行为纠正）",
        "knowledge": "Knowledge（知识积累）",
        "fixes": "Fixes（修复经验）",
        "interview": "Interview（面试专用）",
        "decisions": "Decisions（架构决策）",
    }

    def count_all_memory_files():
        count = 0
        for d in TOPIC_DIRS:
            dp = MEMORY_DIR / d
            if dp.is_dir():
                count += sum(1 for f in dp.glob("*.md") if f.name != ".gitkeep")
        if DOCS_DIR.is_dir():
            count += sum(1 for f in DOCS_DIR.glob("*.md"))
        return count

    def extract_yaml_field(filepath, field):
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
        m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not m:
            return None
        for line in m.group(1).splitlines():
            line = line.strip()
            if line.startswith(f"{field}:"):
                val = line[len(f"{field}:"):].strip()
                if val and val[0] in ('"', "'") and len(val) > 1 and val[-1] == val[0]:
                    val = val[1:-1]
                return val if val else None
        return None

    def write_log(name, msg):
        pass

    def now_str():
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def today_str():
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

PROJECT_MEMORY_DIR = Path.home() / ".claude" / "projects"
YAML_REQUIRED_FIELDS = ["name", "type", "description"]


class HealthReport:
    """收集检查结果"""

    def __init__(self):
        self.errors = []    # (check_name, message)
        self.warnings = []
        self.infos = []
        self.fixes = []     # 已执行的修复

    def error(self, check, msg):
        self.errors.append((check, msg))

    def warning(self, check, msg):
        self.warnings.append((check, msg))

    def info(self, check, msg):
        self.infos.append((check, msg))

    def fixed(self, msg):
        self.fixes.append(msg)

    @property
    def exit_code(self):
        if self.errors:
            return 2
        if self.warnings:
            return 1
        return 0

    def to_dict(self):
        return {
            "errors": [{"check": c, "message": m} for c, m in self.errors],
            "warnings": [{"check": c, "message": m} for c, m in self.warnings],
            "infos": [{"check": c, "message": m} for c, m in self.infos],
            "fixes": self.fixes,
            "exit_code": self.exit_code,
        }


# ────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────

def parse_index_links(content: str) -> list[tuple[str, str]]:
    """从 MEMORY.md 表格行中提取 [name](path) 链接，返回 [(display, rel_path)]"""
    links = []
    for line in content.splitlines():
        if not line.strip().startswith("|"):
            continue
        for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
            display, rel_path = m.group(1), m.group(2)
            # 排除外部链接
            if rel_path.startswith("http"):
                continue
            links.append((display, rel_path))
    return links


def collect_actual_files(include_deep_docs: bool = False) -> set[str]:
    """收集 topic 目录下的 .md 文件，返回相对路径集合。
    include_deep_docs=False 时排除 knowledge/docs/ 和 knowledge/references/
    （深度参考文档按需读取，不要求逐个索引）
    """
    files = set()
    for d in TOPIC_DIRS:
        dp = MEMORY_DIR / d
        if not dp.is_dir():
            continue
        for f in dp.glob("*.md"):
            if f.name == ".gitkeep":
                continue
            files.add(f"{d}/{f.name}")
    if include_deep_docs:
        if DOCS_DIR.is_dir():
            for f in DOCS_DIR.glob("*.md"):
                files.add(f"knowledge/docs/{f.name}")
        ref_dir = MEMORY_DIR / "knowledge" / "references"
        if ref_dir.is_dir():
            for f in ref_dir.glob("*.md"):
                files.add(f"knowledge/references/{f.name}")
    return files


def git_run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args),
        cwd=str(MEMORY_DIR),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


# ────────────────────────────────────────────
# 检查函数
# ────────────────────────────────────────────

def check_index_consistency(report: HealthReport, do_fix: bool):
    """检查 1: MEMORY.md 引用的文件是否存在"""
    if not MEMORY_MD.is_file():
        report.error("索引一致性", "MEMORY.md 不存在")
        return

    content = MEMORY_MD.read_text(encoding="utf-8", errors="replace")
    links = parse_index_links(content)
    dead_links = []

    for display, rel_path in links:
        full = MEMORY_DIR / rel_path
        if not full.is_file():
            dead_links.append((display, rel_path))
            report.error("索引一致性", f"死链: [{display}]({rel_path})")

    if dead_links and do_fix:
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            remove = False
            for display, rel_path in dead_links:
                if rel_path in line and display in line:
                    remove = True
                    break
            if not remove:
                new_lines.append(line)
        MEMORY_MD.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        report.fixed(f"删除 {len(dead_links)} 条死链")


def check_orphan_files(report: HealthReport, do_fix: bool):
    """检查 2: topic 目录下未被索引的文件"""
    if not MEMORY_MD.is_file():
        return

    content = MEMORY_MD.read_text(encoding="utf-8", errors="replace")
    indexed_paths = {rel for _, rel in parse_index_links(content)}
    actual_files = collect_actual_files()

    orphans = actual_files - indexed_paths
    if not orphans:
        return

    for orphan in sorted(orphans):
        report.warning("孤儿文件", f"未收录: {orphan}")

    if do_fix:
        lines = content.splitlines()
        # 按分类分组孤儿
        by_category: dict[str, list[str]] = {}
        for orphan in orphans:
            cat = orphan.split("/")[0]
            by_category.setdefault(cat, []).append(orphan)

        for cat, files in sorted(by_category.items()):
            cat_header = CATEGORY_NAMES.get(cat, cat)
            # 找到该分类表格的最后一行
            insert_idx = None
            in_section = False
            for i, line in enumerate(lines):
                if cat_header in line:
                    in_section = True
                    continue
                if in_section:
                    if line.strip().startswith("##") and cat_header not in line:
                        insert_idx = i
                        break
                    if line.strip().startswith("|") and not line.strip().startswith("| 文件"):
                        insert_idx = i + 1

            if insert_idx is None:
                insert_idx = len(lines)

            for fp in sorted(files):
                fname = fp.split("/")[-1]
                fpath = MEMORY_DIR / fp
                desc = extract_yaml_field(fpath, "description") if fpath.is_file() else None
                desc = desc or fname.replace(".md", "").replace("_", " ")
                updated = today_str()
                new_row = f"| [{fname}]({fp}) | {desc} | {updated} |"
                lines.insert(insert_idx, new_row)
                insert_idx += 1

        MEMORY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report.fixed(f"追加 {len(orphans)} 个孤儿文件到索引")


def check_file_count(report: HealthReport, do_fix: bool):
    """检查 3: MEMORY.md 底部文件计数"""
    if not MEMORY_MD.is_file():
        return

    content = MEMORY_MD.read_text(encoding="utf-8", errors="replace")
    actual = count_all_memory_files()

    m = re.search(r"总文件数[：:]\s*(\d+)", content)
    if not m:
        report.warning("文件计数", f"MEMORY.md 中未找到文件计数字段（实际: {actual}）")
        return

    claimed = int(m.group(1))
    if claimed != actual:
        report.warning("文件计数", f"声称 {claimed}，实际 {actual}")
        if do_fix:
            new_content = content.replace(m.group(0), f"总文件数：{actual}")
            # 同时更新维护时间
            new_content = re.sub(
                r"最后维护时间[：:]\s*[\d-]+",
                f"最后维护时间：{today_str()}",
                new_content,
            )
            MEMORY_MD.write_text(new_content, encoding="utf-8")
            report.fixed(f"文件计数 {claimed} → {actual}")


def check_yaml_frontmatter(report: HealthReport, do_fix: bool):
    """检查 4: topic 文件的 YAML frontmatter"""
    for d in TOPIC_DIRS:
        dp = MEMORY_DIR / d
        if not dp.is_dir():
            continue
        for f in sorted(dp.glob("*.md")):
            if f.name == ".gitkeep":
                continue
            content = f.read_text(encoding="utf-8", errors="replace")
            has_yaml = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if not has_yaml:
                report.warning("YAML规范", f"缺少 frontmatter: {d}/{f.name}")
                continue
            for field in YAML_REQUIRED_FIELDS:
                val = extract_yaml_field(f, field)
                if not val:
                    report.warning("YAML规范", f"缺少字段 {field}: {d}/{f.name}")


def check_cross_layer_duplicates(report: HealthReport, do_fix: bool):
    """检查 5: 项目级 memory 与全局 memory 的同名文件"""
    if not PROJECT_MEMORY_DIR.is_dir():
        return

    global_names = set()
    for d in TOPIC_DIRS:
        dp = MEMORY_DIR / d
        if dp.is_dir():
            for f in dp.glob("*.md"):
                global_names.add(f.name)

    for proj_mem in PROJECT_MEMORY_DIR.rglob("memory"):
        if not proj_mem.is_dir():
            continue
        for f in proj_mem.glob("*.md"):
            if f.name == "MEMORY.md":
                continue
            if f.name in global_names:
                report.info("跨层重复", f"{f.name} 同时存在于项目级和全局")


def check_git_status(report: HealthReport, do_fix: bool):
    """检查 6: Git 同步状态"""
    # 未提交变更
    r = git_run("status", "--porcelain")
    if r.returncode != 0:
        report.info("Git同步", "非 Git 仓库或 git 不可用")
        return

    uncommitted = [l for l in r.stdout.strip().splitlines() if l.strip()]
    if uncommitted:
        report.info("Git同步", f"{len(uncommitted)} 个未提交变更")
        for line in uncommitted[:5]:
            report.info("Git同步", f"  {line.strip()}")

    # 远程同步
    git_run("fetch", "--quiet")
    r = git_run("status", "--branch", "--porcelain")
    if "ahead" in r.stdout:
        m = re.search(r"ahead (\d+)", r.stdout)
        n = m.group(1) if m else "?"
        report.info("Git同步", f"领先远程 {n} 个提交")
    if "behind" in r.stdout:
        m = re.search(r"behind (\d+)", r.stdout)
        n = m.group(1) if m else "?"
        report.info("Git同步", f"落后远程 {n} 个提交")

    if do_fix and uncommitted:
        git_run("add", "-A")
        git_run("commit", "-m", f"auto-fix: health check {today_str()}")
        r = git_run("push")
        if r.returncode == 0:
            report.fixed("已自动提交并推送")
        else:
            report.warning("Git同步", f"push 失败: {r.stderr.strip()}")


# ────────────────────────────────────────────
# 主函数
# ────────────────────────────────────────────

ALL_CHECKS = [
    ("1. 索引一致性", check_index_consistency),
    ("2. 孤儿文件", check_orphan_files),
    ("3. 文件计数", check_file_count),
    ("4. YAML 规范", check_yaml_frontmatter),
    ("5. 跨层重复", check_cross_layer_duplicates),
    ("6. Git 同步", check_git_status),
]


def main():
    do_fix = "--fix" in sys.argv
    do_json = "--json" in sys.argv

    report = HealthReport()

    if not do_json:
        print("=" * 55)
        print("  check_health.py — 全局记忆仓库健康检查")
        print(f"  时间: {now_str()}")
        if do_fix:
            print("  模式: 检查 + 自动修复")
        print("=" * 55)

    for label, fn in ALL_CHECKS:
        if not do_json:
            print(f"\n{'─'*45}")
            print(f"  {label}")
            print(f"{'─'*45}")

        before_e = len(report.errors)
        before_w = len(report.warnings)
        before_i = len(report.infos)

        fn(report, do_fix)

        if not do_json:
            new_e = report.errors[before_e:]
            new_w = report.warnings[before_w:]
            new_i = report.infos[before_i:]
            if not new_e and not new_w and not new_i:
                print("  ✅ 通过")
            for _, msg in new_e:
                print(f"  ❌ {msg}")
            for _, msg in new_w:
                print(f"  ⚠️  {msg}")
            for _, msg in new_i:
                print(f"  ℹ️  {msg}")

    # 汇总
    if do_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*55}")
        print("  📊 汇总")
        print(f"{'='*55}")
        print(f"  ERROR:   {len(report.errors)}")
        print(f"  WARNING: {len(report.warnings)}")
        print(f"  INFO:    {len(report.infos)}")
        if report.fixes:
            print(f"  FIXED:   {len(report.fixes)}")
            for f in report.fixes:
                print(f"    🔧 {f}")
        print()
        if report.exit_code == 0:
            print("  ✅ 全部通过")
        elif report.exit_code == 1:
            print("  ⚠️  存在 WARNING，建议检查")
        else:
            print("  ❌ 存在 ERROR，需要修复")

    write_log("check_health", f"E={len(report.errors)} W={len(report.warnings)} I={len(report.infos)} F={len(report.fixes)}")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
