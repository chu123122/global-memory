#!/usr/bin/env python3
"""
learning_opportunity_nudge.py — PostToolUse hook（matcher: Bash）

learning-opportunities skill 的自动触发层（bash post-tool-use.sh 的 Python 移植版）。
每次 Bash 工具调用后跑：若命令是 `git commit`，注入一句提醒，让主模型考虑
是否提议 10-15min 学习练习。值不值得练由 skill 判，本 hook 只在对的时机戳。

限频：每 session 最多戳 2 次（状态文件 keyed on session_id）。
失败静默 exit 0，绝不破坏业务（对齐 hook-chain.md「失败不破业务」）。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, write_hook_output, LOG_DIR

MAX_OFFERS_PER_SESSION = 2
STATE_DIR = LOG_DIR / "lo_auto_state"

# git commit 检测：命令文本里同时出现 git 与 commit（git log/status 等不触发）
GIT_COMMIT_RE = re.compile(r"\bgit\b.*\bcommit\b", re.IGNORECASE | re.DOTALL)

NUDGE = (
    "[learning-opportunities-auto] The user just committed code. Per the "
    "learning-opportunities skill, consider whether this is a good moment to "
    "offer a learning exercise. If the committed work involved new files, schema "
    "changes, architectural decisions, refactors, or unfamiliar patterns, ask the "
    "user (one short sentence) if they'd like a 10-15 minute exercise. Do not start "
    "the exercise until they confirm. If they decline, note it — no more offers this session."
)


def main() -> None:
    data = read_hook_input()
    if not data:
        sys.exit(0)

    # 只认 Bash 工具的 git commit
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    command = (data.get("tool_input") or {}).get("command", "")
    if not command or not GIT_COMMIT_RE.search(command):
        sys.exit(0)

    session_id = data.get("session_id", "")
    if not session_id:
        sys.exit(0)

    # 限频：每 session 状态文件计数
    safe_sid = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)
    state_file = STATE_DIR / f"{safe_sid}.state"
    offers = 0
    try:
        offers = int(state_file.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        offers = 0

    if offers >= MAX_OFFERS_PER_SESSION:
        sys.exit(0)

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file.write_text(str(offers + 1), encoding="utf-8")
    except Exception:
        pass  # 写状态失败不阻断，最坏多戳几次

    write_hook_output({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": NUDGE,
        }
    })
    sys.exit(0)


if __name__ == "__main__":
    main()
