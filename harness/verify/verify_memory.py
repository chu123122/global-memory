#!/usr/bin/env python3
"""
verify_memory.py — 记忆仓库健康检查脚本

检查 global-memory 仓库的完整性、一致性和格式规范。
这个脚本替代人工/AI审查，所有能自动化的检查都在这里。

用法：
    python verify_memory.py [memory_dir]
    python verify_memory.py                          # 默认 ~/.claude/global-memory
    python verify_memory.py --fix                    # 自动修复可修复的问题
    python verify_memory.py --report                 # 输出详细报告

检查项（13 项）：
    MEM-01: MEMORY.md 索引完整性（所有 topic 文件都在索引中）
    MEM-02: MEMORY.md 索引无死链（索引中的文件都存在）
    MEM-03: Topic 文件 YAML 头格式（必须字段：name, description, type, created, updated, source）
    MEM-04: Topic 文件更新日志区块存在
    MEM-05: docs/ 文件格式（大文件豁免 YAML，但必须有标题和来源标注）
    MEM-06: CHANGELOG.md 存在且非空
    MEM-07: CHANGELOG 最新条目日期不超过 7 天（防止忘记记录）
    MEM-08: 活跃项目表中的项目都有交接文档路径
    MEM-09: 记忆文件总数不超过上限（50）
    MEM-10: 文件内容非空（排除 .gitkeep）
    MEM-11: 无孤儿文件（存在于目录中但不在索引中的 topic 文件）
    MEM-12: conventions.md 中 🔒 条目统计（覆盖率需人工确认）
    MEM-13: 章节标题重复检测（topic 文件之间的 ## 标题重叠）
"""

import os
import sys
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib import MAX_FILES as MAX_MEMORY_FILES, TOPIC_DIRS as _TOPIC_LIST  # noqa: E402


# ============================================================
# 配置
# ============================================================

REQUIRED_YAML_FIELDS = {"name", "description", "type", "created", "updated", "source"}
VALID_TYPES = {"knowledge", "feedback", "fixes", "decision", "interview"}
CHANGELOG_STALE_DAYS = 7

TOPIC_DIRS = set(_TOPIC_LIST)
# 豁免 YAML 头的目录/文件
YAML_EXEMPT = {"docs", "projects", "archives"}
# 系统文件（不检查 YAML）
SYSTEM_FILES = {"MEMORY.md", "CHANGELOG.md", "README.md", "CONTROL_PANEL.md", "MAINTENANCE.md"}
RUNTIME_DIRS = {"agents", "skills", "templates", "harness"}


class CheckResult:
    def __init__(self, check_id, name):
        self.check_id = check_id
        self.name = name
        self.status = "PASS"  # PASS / WARNING / ERROR
        self.details = []

    def warn(self, msg):
        if self.status == "PASS":
            self.status = "WARNING"
        self.details.append(f"⚠️  {msg}")

    def error(self, msg):
        self.status = "ERROR"
        self.details.append(f"❌ {msg}")

    def info(self, msg):
        self.details.append(f"ℹ️  {msg}")

    def __str__(self):
        icon = {"PASS": "✅", "WARNING": "⚠️", "ERROR": "❌"}[self.status]
        lines = [f"{icon} [{self.check_id}] {self.name}: {self.status}"]
        for d in self.details:
            lines.append(f"    {d}")
        return "\n".join(lines)


def parse_yaml_header(filepath):
    """解析文件的 YAML 头部，返回字典。无 YAML 头返回 None。"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None

    if not lines or lines[0].strip() != "---":
        return None

    yaml_lines = []
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            break
        yaml_lines.append(line)
    else:
        return None  # 没有找到结束的 ---

    result = {}
    for line in yaml_lines:
        match = re.match(r'^(\w+):\s*(.+)$', line.strip())
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def get_all_md_files(memory_dir):
    """获取所有 .md 文件（排除 .gitkeep 和 README.md）。"""
    files = []
    for root, dirs, filenames in os.walk(memory_dir):
        # 跳过 .git
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in filenames:
            if f.endswith(".md") and f != "README.md":
                files.append(os.path.join(root, f))
    return files


def get_counted_memory_files(memory_dir):
    """获取记忆容量统计口径内的 .md 文件：topic + knowledge/docs。"""
    files = []
    for td in TOPIC_DIRS:
        td_path = os.path.join(memory_dir, td)
        if not os.path.isdir(td_path):
            continue
        for f in os.listdir(td_path):
            if f.endswith(".md") and f != ".gitkeep":
                files.append(os.path.join(td_path, f))

    docs_dir = os.path.join(memory_dir, "knowledge", "docs")
    if os.path.isdir(docs_dir):
        for f in os.listdir(docs_dir):
            if f.endswith(".md") and f != ".gitkeep":
                files.append(os.path.join(docs_dir, f))
    return files


def get_relative(filepath, base):
    return os.path.relpath(filepath, base).replace("\\", "/")


def read_file_content(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


# ============================================================
# 检查函数
# ============================================================

def check_mem01_index_completeness(memory_dir, memory_content):
    """MEM-01: 所有 topic 文件都在 MEMORY.md 索引中"""
    r = CheckResult("MEM-01", "索引完整性（topic→索引）")

    # 找所有 topic 目录下的 .md 文件
    topic_files = []
    for td in TOPIC_DIRS:
        td_path = os.path.join(memory_dir, td)
        if not os.path.isdir(td_path):
            continue
        for f in os.listdir(td_path):
            if f.endswith(".md") and f != ".gitkeep":
                topic_files.append(f"{td}/{f}")

    # 检查每个 topic 文件是否出现在 MEMORY.md 中
    for tf in topic_files:
        filename = os.path.basename(tf)
        if filename not in memory_content and tf not in memory_content:
            r.warn(f"文件 {tf} 不在 MEMORY.md 索引中")

    if not r.details:
        r.info(f"全部 {len(topic_files)} 个 topic 文件已索引")
    return r


def check_mem02_no_dead_links(memory_dir, memory_content):
    """MEM-02: 索引中的文件都存在"""
    r = CheckResult("MEM-02", "索引无死链（索引→文件）")

    # 提取 MEMORY.md 中的 markdown 链接
    links = re.findall(r'\[.*?\]\((.*?\.md)\)', memory_content)
    dead = []
    for link in links:
        # 处理相对路径
        full_path = os.path.join(memory_dir, link.replace("/", os.sep))
        if not os.path.exists(full_path):
            dead.append(link)

    for d in dead:
        r.error(f"索引中的链接 {d} 指向不存在的文件")

    if not dead:
        r.info(f"全部 {len(links)} 个索引链接有效")
    return r


def check_mem03_yaml_format(memory_dir):
    """MEM-03: Topic 文件 YAML 头格式检查"""
    r = CheckResult("MEM-03", "Topic 文件 YAML 头格式")

    issues = 0
    checked = 0
    for td in TOPIC_DIRS:
        td_path = os.path.join(memory_dir, td)
        if not os.path.isdir(td_path):
            continue
        for f in os.listdir(td_path):
            if not f.endswith(".md") or f == ".gitkeep":
                continue
            filepath = os.path.join(td_path, f)
            checked += 1
            yaml = parse_yaml_header(filepath)
            rel = f"{td}/{f}"

            if yaml is None:
                r.error(f"{rel}: 缺少 YAML 头部")
                issues += 1
                continue

            missing = REQUIRED_YAML_FIELDS - set(yaml.keys())
            if missing:
                r.warn(f"{rel}: YAML 缺少字段 {missing}")
                issues += 1

            if "type" in yaml and yaml["type"] not in VALID_TYPES:
                r.warn(f"{rel}: type '{yaml['type']}' 不在有效范围 {VALID_TYPES}")
                issues += 1

            if "updated" in yaml and yaml["updated"] == "待填":
                r.warn(f"{rel}: updated 字段仍为 '待填'")
                issues += 1

    if issues == 0:
        r.info(f"全部 {checked} 个 topic 文件 YAML 格式正确")
    return r


def check_mem04_changelog_section(memory_dir):
    """MEM-04: Topic 文件必须有更新日志区块"""
    r = CheckResult("MEM-04", "Topic 文件更新日志区块")
    r.info("单仓库当前以 CHANGELOG.md 作为权威变更审计；Topic 内更新日志为可选")
    return r

    issues = 0
    checked = 0
    for td in TOPIC_DIRS:
        td_path = os.path.join(memory_dir, td)
        if not os.path.isdir(td_path):
            continue
        for f in os.listdir(td_path):
            if not f.endswith(".md") or f == ".gitkeep":
                continue
            filepath = os.path.join(td_path, f)
            content = read_file_content(filepath)
            checked += 1

            if "更新日志" not in content and "Changelog" not in content:
                r.warn(f"{td}/{f}: 缺少更新日志区块")
                issues += 1

    if issues == 0:
        r.info(f"全部 {checked} 个 topic 文件有更新日志")
    return r


def check_mem05_docs_format(memory_dir):
    """MEM-05: docs/ 文件格式（大文件豁免 YAML，但必须有标题）"""
    r = CheckResult("MEM-05", "docs/ 文件格式")

    docs_dir = os.path.join(memory_dir, "knowledge", "docs")
    if not os.path.isdir(docs_dir):
        r.info("docs/ 目录不存在，跳过")
        return r

    issues = 0
    for f in os.listdir(docs_dir):
        if not f.endswith(".md"):
            continue
        filepath = os.path.join(docs_dir, f)
        content = read_file_content(filepath)
        lines = content.split("\n")
        if lines and lines[0].strip() == "---":
            for idx, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    lines = lines[idx + 1:]
                    break

        # 必须有标题（# 开头）
        has_title = any(line.startswith("# ") for line in lines[:10])
        if not has_title:
            r.warn(f"docs/{f}: 前 10 行没有标题（# ...）")
            issues += 1

    if issues == 0:
        r.info(f"docs/ 下 {len(os.listdir(docs_dir))} 个文件格式正常")
    return r


def check_mem06_changelog_exists(memory_dir):
    """MEM-06: CHANGELOG.md 存在且非空"""
    r = CheckResult("MEM-06", "CHANGELOG.md 存在性")

    cl_path = os.path.join(memory_dir, "CHANGELOG.md")
    if not os.path.exists(cl_path):
        r.error("CHANGELOG.md 不存在")
        return r

    content = read_file_content(cl_path)
    if len(content.strip()) < 50:
        r.error("CHANGELOG.md 内容过少（<50字符）")
        return r

    # 统计变更条目数
    entries = re.findall(r'### \d{4}-\d{2}-\d{2}', content)
    r.info(f"CHANGELOG.md 存在，包含 {len(entries)} 条变更记录")
    return r


def check_mem07_changelog_freshness(memory_dir):
    """MEM-07: CHANGELOG 最新条目不超过 N 天"""
    r = CheckResult("MEM-07", f"CHANGELOG 时效性（{CHANGELOG_STALE_DAYS}天内有更新）")

    cl_path = os.path.join(memory_dir, "CHANGELOG.md")
    if not os.path.exists(cl_path):
        r.warn("CHANGELOG.md 不存在，无法检查时效")
        return r

    content = read_file_content(cl_path)
    dates = re.findall(r'### (\d{4}-\d{2}-\d{2})', content)
    if not dates:
        r.warn("CHANGELOG.md 中没有找到日期格式的条目")
        return r

    latest = max(dates)
    try:
        latest_date = datetime.strptime(latest, "%Y-%m-%d")
        days_ago = (datetime.now() - latest_date).days
        if days_ago > CHANGELOG_STALE_DAYS:
            r.warn(f"最新条目 {latest}（{days_ago} 天前），可能有未记录的变更")
        else:
            r.info(f"最新条目 {latest}（{days_ago} 天前）")
    except ValueError:
        r.warn(f"日期解析失败：{latest}")

    return r


def check_mem08_active_projects(memory_content):
    """MEM-08: 活跃项目表中的项目有交接文档"""
    r = CheckResult("MEM-08", "活跃项目交接文档")

    # 找活跃项目表（只扫描"当前活跃项目"到下一个 ## 之间的区块）
    if "当前活跃项目" not in memory_content:
        r.warn("MEMORY.md 中没有'当前活跃项目'区块")
        return r

    # 提取活跃项目区块
    lines = memory_content.split("\n")
    in_section = False
    section_lines = []
    for line in lines:
        if "当前活跃项目" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break  # 下一个区块开始，停止
        if in_section:
            section_lines.append(line)

    # 只检查表格数据行（排除表头和分隔线）
    projects = 0
    has_handoff = 0
    for line in section_lines:
        if not line.startswith("|"):
            continue
        if "---" in line or "项目" in line or "仓库" in line:
            continue  # 表头或分隔线
        if line.strip() == "|" or len(line.strip()) < 10:
            continue
        projects += 1
        if "HANDOFF" in line or "PROGRESS" in line or "交接" in line:
            has_handoff += 1
        else:
            r.warn(f"项目行缺少交接文档引用：{line.strip()[:80]}...")

    if projects > 0 and has_handoff == projects:
        r.info(f"全部 {projects} 个活跃项目有交接文档")
    elif projects == 0:
        r.info("当前无活跃项目")
    return r


def check_mem09_file_count(memory_dir):
    """MEM-09: 文件总数不超过上限"""
    r = CheckResult("MEM-09", f"文件总数（上限 {MAX_MEMORY_FILES}）")

    all_files = get_counted_memory_files(memory_dir)
    count = len(all_files)

    if count > MAX_MEMORY_FILES:
        r.warn(f"文件数 {count} 超过上限 {MAX_MEMORY_FILES}，建议后续归档清理（不阻断运行）")
    elif count > MAX_MEMORY_FILES * 0.8:
        r.warn(f"文件数 {count}，接近上限 {MAX_MEMORY_FILES}（>80%）")
    else:
        r.info(f"文件数 {count} / {MAX_MEMORY_FILES}")

    return r


def check_mem10_non_empty(memory_dir):
    """MEM-10: 文件内容非空"""
    r = CheckResult("MEM-10", "文件内容非空")

    empty = []
    all_files = get_counted_memory_files(memory_dir)
    for f in all_files:
        content = read_file_content(f)
        if len(content.strip()) < 10:
            rel = get_relative(f, memory_dir)
            empty.append(rel)

    for e in empty:
        r.warn(f"{e} 内容为空或极少（<10字符）")

    if not empty:
        r.info(f"全部 {len(all_files)} 个文件有内容")
    return r


def check_mem11_orphan_files(memory_dir, memory_content):
    """MEM-11: 无孤儿文件 — 递归白名单制（v2 2026-04-20）

    所有 global-memory/**/*.md 必须出现在某个索引里：
    - knowledge/docs/*.md → 必须在 knowledge/docs/INDEX.md
    - 其它 .md → 必须在 MEMORY.md（按文件名或相对路径匹配）

    黑名单（不需索引）：
    - 系统文件：MEMORY.md / CHANGELOG.md / README.md / CONTROL_PANEL.md / MAINTENANCE.md / FIXLIST.md / docs/INDEX.md
    - 子目录：CHANGELOG_archive/ / test-reports/ / archives/ / runtime dirs
    - 任务文档：projects/*/{HANDOFF,WORKFLOW,HARNESS_REVIEW}.md（白名单只校验 SPEC 与命名档）
    """
    r = CheckResult("MEM-11", "孤儿文件检测（递归白名单 v2）")

    # 系统/运维黑名单文件名
    BLACKLIST_NAMES = {"MEMORY.md", "CHANGELOG.md", "README.md", "CONTROL_PANEL.md", "MAINTENANCE.md", "FIXLIST.md", "INDEX.md", ".gitkeep"}
    # 黑名单子目录（相对 memory_dir 的首段路径）
    BLACKLIST_DIRS = {"CHANGELOG_archive", "test-reports", "archives", "retrospectives", "projects", *RUNTIME_DIRS}

    # 加载 docs/INDEX.md 内容（用于检查 docs/*.md 是否被索引）
    docs_index_path = os.path.join(memory_dir, "knowledge", "docs", "INDEX.md")
    docs_index_content = read_file_content(docs_index_path) if os.path.exists(docs_index_path) else ""

    if not docs_index_content:
        r.warn("knowledge/docs/INDEX.md 不存在 — docs/ 下文件无法走子索引校验")

    orphans = []
    docs_orphans = []

    for filepath in get_all_md_files(memory_dir):
        rel = get_relative(filepath, memory_dir)
        filename = os.path.basename(rel)

        # 黑名单文件
        if filename in BLACKLIST_NAMES:
            continue
        # 黑名单子目录
        first_seg = rel.split("/", 1)[0]
        if first_seg in BLACKLIST_DIRS:
            continue

        # docs/ 子目录：走 INDEX.md 校验
        if rel.startswith("knowledge/docs/"):
            if filename not in docs_index_content:
                docs_orphans.append(rel)
            continue

        # 其它：走 MEMORY.md 校验（按文件名或相对路径）
        if filename not in memory_content and rel not in memory_content:
            orphans.append(rel)

    for o in orphans:
        r.error(f"{o} 不在 MEMORY.md 索引中")
    for o in docs_orphans:
        r.error(f"{o} 不在 knowledge/docs/INDEX.md 索引中")

    if not orphans and not docs_orphans:
        r.info("无孤儿文件（全部 .md 已被索引）")
    return r


def check_mem12_conventions_coverage(memory_dir):
    """MEM-12: 统计 conventions.md 中 🔒 条目数量（覆盖率需人工确认）"""
    r = CheckResult("MEM-12", "🔒 规范条目统计")

    conv_path = os.path.join(memory_dir, "decisions", "conventions.md")
    if not os.path.exists(conv_path):
        r.info("conventions.md 不存在，跳过")
        return r

    content = read_file_content(conv_path)
    locked = re.findall(r'🔒.*?(?=\n(?:###|\Z))', content, re.DOTALL)
    r.info(f"conventions.md 中有 {len(locked)} 条 🔒 标注规范（覆盖率验证需人工确认）")
    return r


def check_mem13_duplicate_detection(memory_dir):
    """MEM-13: 检测 topic 文件之间的章节标题重叠（非内容级去重）"""
    r = CheckResult("MEM-13", "章节标题重复检测")

    # 取 topic 文件的标题
    topic_titles = {}
    for td in TOPIC_DIRS:
        td_path = os.path.join(memory_dir, td)
        if not os.path.isdir(td_path):
            continue
        for f in os.listdir(td_path):
            if not f.endswith(".md") or f == ".gitkeep":
                continue
            filepath = os.path.join(td_path, f)
            content = read_file_content(filepath)
            # 提取二级标题
            titles = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)
            topic_titles[f"{td}/{f}"] = set(t.strip() for t in titles)

    # topic 之间的标题重叠检测
    files = list(topic_titles.keys())
    overlaps = 0
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            common = topic_titles[files[i]] & topic_titles[files[j]]
            # 过滤通用标题
            common = {t for t in common if t not in {"更新日志", "待积累", "参考资料"}}
            if len(common) >= 3:
                r.warn(f"{files[i]} 和 {files[j]} 有 {len(common)} 个相同章节标题：{common}")
                overlaps += 1

    if overlaps == 0:
        r.info("未发现明显的内容重复")
    return r


# ============================================================
# 主函数
# ============================================================

def main():
    # 确定 memory 目录
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        memory_dir = sys.argv[1]
    else:
        memory_dir = os.path.expanduser("~/.claude/global-memory")

    if not os.path.isdir(memory_dir):
        print(f"❌ 目录不存在：{memory_dir}")
        sys.exit(1)

    # 读取 MEMORY.md
    memory_path = os.path.join(memory_dir, "MEMORY.md")
    memory_content = read_file_content(memory_path) if os.path.exists(memory_path) else ""

    print(f"{'='*60}")
    print(f"  记忆仓库健康检查")
    print(f"  目录：{memory_dir}")
    print(f"  时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print()

    # 运行所有检查
    results = [
        check_mem01_index_completeness(memory_dir, memory_content),
        check_mem02_no_dead_links(memory_dir, memory_content),
        check_mem03_yaml_format(memory_dir),
        check_mem04_changelog_section(memory_dir),
        check_mem05_docs_format(memory_dir),
        check_mem06_changelog_exists(memory_dir),
        check_mem07_changelog_freshness(memory_dir),
        check_mem08_active_projects(memory_content),
        check_mem09_file_count(memory_dir),
        check_mem10_non_empty(memory_dir),
        check_mem11_orphan_files(memory_dir, memory_content),
        check_mem12_conventions_coverage(memory_dir),
        check_mem13_duplicate_detection(memory_dir),
    ]

    # 输出结果
    pass_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARNING")
    error_count = sum(1 for r in results if r.status == "ERROR")

    for r in results:
        print(r)
        print()

    print(f"{'='*60}")
    print(f"  结果：{pass_count} PASS / {warn_count} WARNING / {error_count} ERROR")
    print(f"{'='*60}")

    # 详细报告模式
    if "--report" in sys.argv:
        print("\n--- 文件清单 ---")
        all_files = get_all_md_files(memory_dir)
        for f in sorted(all_files):
            rel = get_relative(f, memory_dir)
            size = os.path.getsize(f)
            lines = len(read_file_content(f).split("\n"))
            yaml = parse_yaml_header(f)
            yaml_status = "YAML✅" if yaml else "YAML❌"
            print(f"  {rel:50s} {lines:4d} lines  {size:6d}B  {yaml_status}")

    if error_count > 0:
        sys.exit(1)
    elif warn_count > 0:
        sys.exit(0)  # WARNING 不阻断
    else:
        sys.exit(0)


if __name__ == "__main__":
    # Windows GBK 编码兼容
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    main()
