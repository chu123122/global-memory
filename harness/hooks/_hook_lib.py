#!/usr/bin/env python3
"""
_hook_lib.py — Claude Code hooks 共享工具库

所有 hook 脚本共用的 stdin/stdout 协议、日志、路径常量。
"""

import io
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Windows UTF-8 fix
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 路径常量 ──
CLAUDE_DIR = Path.home() / ".claude"
LOG_DIR = CLAUDE_DIR / "logs"
MEMORY_DIR = CLAUDE_DIR / "global-memory"
SKILLS_BOOTSTRAP = CLAUDE_DIR / "skills-repo" / "_bootstrap"


def read_hook_input() -> dict:
    """从 stdin 读取 hook 输入 JSON。失败返回空 dict。"""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def write_hook_output(output: dict):
    """向 stdout 写入 hook 输出 JSON。"""
    json.dump(output, sys.stdout, ensure_ascii=False)
    sys.stdout.flush()


def deny(reason: str):
    """阻止工具调用：stderr 输出原因，exit 2。"""
    print(reason, file=sys.stderr)
    sys.exit(2)


def ask(reason: str):
    """升级为用户确认：输出 ask 决策 JSON，exit 0。"""
    write_hook_output({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason
        }
    })
    sys.exit(0)


def allow():
    """放行工具调用，exit 0。"""
    sys.exit(0)


def now_iso() -> str:
    """当前时间 ISO 格式。"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def append_jsonl(filepath: Path, record: dict):
    """追加一行 JSON 到 .jsonl 文件。自动创建目录。"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def truncate(s: str, maxlen: int = 200) -> str:
    """截断字符串到指定长度。"""
    if len(s) <= maxlen:
        return s
    return s[:maxlen - 3] + "..."
