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
MAX_FILES = 80  # Phase 1-A: 50→80 实测当前 60 全活跃,旧阈值 50 制造假污染。memory_gc.py 工具铺好,实际归档由用户决定
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


def is_windows() -> bool:
    """Phase 4-A: 平台判断,用于 _file_lock 选锁实现"""
    import platform
    return platform.system() == "Windows"


def _file_lock(fp, exclusive: bool = True):
    """Phase 4-A: 跨平台文件锁 context manager。Windows 用 msvcrt,POSIX 用 fcntl。

    用法:
        with open(path, 'a', encoding='utf-8') as f:
            with _file_lock(f):
                f.write(...)

    Windows 使用 msvcrt.locking(LK_LOCK) 阻塞获取;POSIX 使用 fcntl.flock(LOCK_EX)。
    锁的范围是文件起始 1 字节(POSIX flock 是文件级,msvcrt 是字节范围;1 字节足够互斥)。
    """
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        if is_windows():
            import msvcrt
            try:
                # Windows: 锁文件起始 1 字节,LK_LOCK 阻塞模式
                fp.seek(0)
                msvcrt.locking(fp.fileno(), msvcrt.LK_LOCK, 1)
                fp.seek(0, 2)  # 锁定后回到文件尾,append 模式
                yield
            finally:
                try:
                    fp.seek(0)
                    msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
                fp.seek(0, 2)
        else:
            import fcntl
            try:
                lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(fp.fileno(), lock_type)
                yield
            finally:
                try:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass

    return _ctx()


def _atomic_append_jsonl(path: Path, record: dict) -> None:
    """Phase 4-A: 跨平台原子 append 一行 JSON 到 jsonl 文件。

    内部用 _file_lock 互斥;失败抛 IOError。
    """
    import json
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    # 注意:Windows msvcrt.locking 要求文件用 'r+b' 或类似可读可写模式
    # 我们用 'a+' (读写 + append),写完后 seek 回 end
    with open(path, "a", encoding="utf-8") as f:
        with _file_lock(f):
            f.write(line)
            f.flush()


def rotate_log(path: Path, max_size_bytes: int = 5 * 1024 * 1024,
               max_lines: int = 10000, keep: int = 3) -> bool:
    """Phase 4-A: 按大小/行数轮转 jsonl 文件。

    任一阈值超限即触发滚动:
      <path>.{keep-1} 删除
      <path>.{i} → <path>.{i+1}  (i 从 keep-2 到 0)
      <path>     → <path>.0
      新建空 <path>

    返回 True 表示发生轮转,False 表示未触发。
    """
    path = Path(path)
    if not path.exists():
        return False
    size = path.stat().st_size
    if size < max_size_bytes:
        # 大小未超,再看行数
        try:
            with open(path, "rb") as f:
                line_count = sum(1 for _ in f)
        except Exception:
            return False
        if line_count < max_lines:
            return False
    # 触发轮转:.{keep-1} 删除,.{i} → .{i+1}
    oldest = path.with_suffix(path.suffix + f".{keep - 1}")
    if oldest.exists():
        oldest.unlink()
    for i in range(keep - 2, -1, -1):
        src = path.with_suffix(path.suffix + f".{i}")
        dst = path.with_suffix(path.suffix + f".{i + 1}")
        if src.exists():
            src.rename(dst)
    # path → path.0
    path.rename(path.with_suffix(path.suffix + ".0"))
    # 新空文件
    path.touch()
    return True


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
