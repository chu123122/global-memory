#!/usr/bin/env python3
"""
_lib.py — 记忆维护脚本的共享工具库

所有小脚本共用的函数放这里，避免重复代码。
不要直接运行此文件。
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Windows UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        if getattr(_stream, "encoding", None) != "utf-8" and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 路径常量 ──
HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
CLAUDE_DIR = Path(os.environ.get("CLAUDE_DIR", Path.home() / ".claude"))
MEMORY_DIR = Path(os.environ.get("GLOBAL_MEMORY_DIR", REPO_DIR))
SKILLS_DIR = Path(os.environ.get("GLOBAL_SKILLS_DIR", MEMORY_DIR / "skills"))
SCRIPTS_DIR = Path(os.environ.get("GLOBAL_HARNESS_DIR", HARNESS_DIR))
TEMPLATES_DIR = Path(os.environ.get("GLOBAL_TEMPLATES_DIR", MEMORY_DIR / "templates"))
AGENTS_DIR = Path(os.environ.get("GLOBAL_AGENTS_DIR", MEMORY_DIR / "agents"))
MEMORY_MD = MEMORY_DIR / "MEMORY.md"
CHANGELOG_MD = MEMORY_DIR / "CHANGELOG.md"
LOG_DIR = CLAUDE_DIR / "logs"
TOPIC_DIRS = ["feedback", "knowledge", "fixes", "decisions", "interview"]
DOCS_DIR = MEMORY_DIR / "knowledge" / "docs"
MAX_FILES = 50
MAX_LOG_LINES = 500  # 日志最大行数，超过自动轮转

CATEGORY_NAMES = {
    "feedback": "Feedback（行为纠正）",
    "knowledge": "Knowledge（知识积累）",
    "fixes": "Fixes（修复经验）",
    "interview": "Interview（面试专用）",
    "decisions": "Decisions（架构决策）",
}


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def git_last_modified(filepath):
    """从 git log 获取文件最后修改日期（使用相对路径精确匹配）"""
    try:
        # 获取相对于仓库根目录的路径
        repo_root = MEMORY_DIR
        try:
            rel_path = filepath.resolve().relative_to(repo_root.resolve())
        except ValueError:
            rel_path = filepath.name

        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(rel_path)],
            cwd=str(repo_root),
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:10]
    except Exception:
        pass
    try:
        mtime = filepath.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except Exception:
        return "未知"


def extract_yaml_field(filepath, field):
    """从 YAML 头提取指定字段"""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith(f"{field}:"):
            val = line[len(f"{field}:"):].strip()
            if val and val[0] in ('"', "'") and len(val) > 1 and val[-1] == val[0]:
                val = val[1:-1]
            return val if val else None
    return None


def scan_topic_files():
    """扫描所有 topic 文件，返回 {category: [{name, rel_path, description, updated}]}"""
    from collections import OrderedDict
    categories = OrderedDict()
    for dir_name in TOPIC_DIRS:
        dir_path = MEMORY_DIR / dir_name
        if not dir_path.is_dir():
            continue
        files = []
        for f in sorted(dir_path.glob("*.md")):
            if f.name == ".gitkeep":
                continue
            desc = extract_yaml_field(f, "description") or f.stem.replace("_", " ")
            updated = git_last_modified(f)
            files.append({
                "name": f.name,
                "rel_path": f"{dir_name}/{f.name}",
                "description": desc,
                "updated": updated,
            })
        if files:
            categories[dir_name] = files
    return categories


def count_all_memory_files():
    """统计所有记忆文件数"""
    count = 0
    for dir_name in TOPIC_DIRS:
        dir_path = MEMORY_DIR / dir_name
        if dir_path.is_dir():
            count += sum(1 for f in dir_path.glob("*.md") if f.name != ".gitkeep")
    if DOCS_DIR.is_dir():
        count += sum(1 for f in DOCS_DIR.glob("*.md"))
    return count


def write_log(script_name, message):
    """写运行日志到 ~/.claude/logs/{script_name}.log，自动轮转"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{script_name}.log"
    entry = f"[{now_str()}] {message}\n"

    # 追加
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)

    # 轮转：超过 MAX_LOG_LINES 则只保留后半部分
    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_LOG_LINES:
            keep = lines[-(MAX_LOG_LINES // 2):]
            log_file.write_text(
                f"[{now_str()}] --- 日志轮转：保留最近 {len(keep)} 条 ---\n"
                + "\n".join(keep) + "\n",
                encoding="utf-8"
            )
    except Exception:
        pass
