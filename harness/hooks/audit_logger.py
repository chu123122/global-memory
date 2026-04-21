#!/usr/bin/env python3
"""
audit_logger.py — PostToolUse hook（异步）

每次工具调用后追加一行 JSON 到 tool_audit.jsonl。
按工具类型提取关键字段作为 input_summary。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, append_jsonl, now_iso, truncate, LOG_DIR

AUDIT_FILE = LOG_DIR / "tool_audit.jsonl"


def summarize_input(tool_name: str, tool_input: dict) -> str:
    """按工具类型提取可读摘要。"""
    if tool_name == "Bash":
        return tool_input.get("command", "")
    elif tool_name in ("Write", "Edit", "Read"):
        return tool_input.get("file_path", "")
    elif tool_name == "Glob":
        return tool_input.get("pattern", "")
    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", ".")
        return f"{pattern} in {path}"
    elif tool_name == "WebFetch":
        return tool_input.get("url", "")
    elif tool_name == "WebSearch":
        return tool_input.get("query", "")
    elif tool_name == "Agent":
        return tool_input.get("description", "") or tool_input.get("prompt", "")[:100]
    else:
        for v in tool_input.values():
            if isinstance(v, str) and len(v) > 3:
                return v
        return ""


def main():
    data = read_hook_input()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})

    record = {
        "ts": now_iso(),
        "session": data.get("session_id", ""),
        "tool": tool_name,
        "input_summary": truncate(summarize_input(tool_name, tool_input)),
        "cwd": data.get("cwd", ""),
    }

    try:
        append_jsonl(AUDIT_FILE, record)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
