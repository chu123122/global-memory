#!/usr/bin/env python3
"""UserPromptSubmit hook: 高置信低耦合场景 nudge + turn_id 生成。

默认静默。仅命中已知低耦合模式时注入短提示（≤120 token）。
每轮写 .current_turn.json 供 PostToolUse hooks 关联 turn_id。
"""

import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CLAUDE_HOME  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

CLAUDE_DIR = CLAUDE_HOME
TURN_FILE = CLAUDE_DIR / ".current_turn.json"
STATS_FILE = CLAUDE_DIR / ".turn_stats.json"
TOPIC_WINDOW_FILE = CLAUDE_DIR / ".topic_window.json"

# P7 compact-nudge 参数
TOPIC_WINDOW_SIZE = 5          # 留最近 5 轮 prompt 词袋
TOPIC_MIN_TURNS = 10           # 至少累计 10 轮才考虑 /compact nudge
TOPIC_JACCARD_THRESHOLD = 0.08 # 当前 prompt 与窗口聚合 jaccard 低于此 = 话题切换

# (regex, nudge_text, agent)
NUDGE_RULES_STDIN = [
    (r"(查|搜索|搜一下|梳理.*调用链|阅读.*代码|grep.*所有|全局.*查找)",
     "💡 大范围搜索 → 考虑用 sidecar-explorer", "sidecar-explorer"),
    (r"(编译.*报错|日志|报错链|crash.*log|build.*error)",
     "💡 长日志/错误链 → 考虑用 log-triage", "log-triage"),
    (r"(批量.*(替换|修改|添加|改名)|迁移|格式化|文档同步|翻译|i18n|国际化)",
     "💡 批量机械改动 → 考虑用 bounded-worker（给明确 write-set）", "bounded-worker"),
    (r"(写测试|补测试|加测试|test.*cover)",
     "💡 补测试 → 考虑用 bounded-worker（给测试文件范围）", "bounded-worker"),
    (r"(生成.*文档|写.*readme|生成.*readme)",
     "💡 独立文档生成 → 考虑用 bounded-worker", "bounded-worker"),
    (r"(commit\s*message|提交信息)",
     "💡 commit message → 考虑派 haiku subagent", "haiku"),
]


def load_prev_stats() -> dict:
    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def tokenize_topic(text: str) -> set[str]:
    """提 prompt 词袋：ASCII 单词 + CJK 2-gram。用于轻量话题相似度。"""
    text = text.lower()
    words = set(re.findall(r"[a-z_][a-z0-9_]{2,}", text))
    cjk = re.sub(r"[\s\W\d_]+", "", text)
    grams = {cjk[i:i + 2] for i in range(len(cjk) - 1)} if len(cjk) >= 2 else set()
    return words | grams


def load_topic_window() -> tuple[list, int]:
    """返回 (prompts 列表, cumulative turn 计数)。"""
    try:
        data = json.loads(TOPIC_WINDOW_FILE.read_text(encoding="utf-8"))
        return data.get("prompts", []), int(data.get("total", 0))
    except Exception:
        return [], 0


def save_topic_window(prompts: list, total: int) -> None:
    try:
        TOPIC_WINDOW_FILE.write_text(
            json.dumps({"prompts": prompts[-TOPIC_WINDOW_SIZE:], "total": total}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def check_compact_nudge(current_tokens: set, window: list, total_turns: int) -> str | None:
    """累计轮数 ≥ TOPIC_MIN_TURNS 且当前 prompt 与窗口聚合 jaccard 极低 → /compact 提示。"""
    if total_turns < TOPIC_MIN_TURNS:
        return None
    agg: set[str] = set()
    for p in window:
        agg.update(p.get("tokens", []))
    if not agg or not current_tokens:
        return None
    sim = jaccard(current_tokens, agg)
    if sim < TOPIC_JACCARD_THRESHOLD:
        return f"💡 话题与最近 {total_turns} 轮重合度仅 {sim:.2f} → 考虑 /compact 清理上下文"
    return None


def update_topic_window(current_tokens: set, window: list) -> list:
    """把当前 prompt 加入窗口；同话题（jaccard ≥ 阈值）合并为同一项扩词。"""
    if window:
        last = window[-1]
        if jaccard(current_tokens, set(last.get("tokens", []))) >= TOPIC_JACCARD_THRESHOLD:
            last["tokens"] = sorted(set(last.get("tokens", [])) | current_tokens)
            return window[-TOPIC_WINDOW_SIZE:]
    window.append({"tokens": sorted(current_tokens)})
    return window[-TOPIC_WINDOW_SIZE:]


def check_stats_nudge(stats: dict) -> str | None:
    """基于前轮 turn_stats 判断是否 nudge。"""
    if stats.get("edit_count", 0) >= 3:
        return "💡 前轮改了 %d 个文件 → 考虑派 code-reviewer 检查 diff 质量" % stats["edit_count"]
    if stats.get("bash_output_lines", 0) > 2000:
        return "💡 前轮 Bash 输出 %d 行 → 考虑用 log-triage 提取错误链" % stats["bash_output_lines"]
    return None


def parse_stdin() -> tuple[str, str]:
    """解析 stdin。UserPromptSubmit 传 JSON（含 session_id + prompt），兼容纯文本。"""
    raw = sys.stdin.read().strip()
    if not raw:
        return "", ""
    try:
        data = json.loads(raw)
        return data.get("prompt", ""), data.get("session_id", os.environ.get("CLAUDE_CODE_SESSION_ID", "unknown"))
    except (json.JSONDecodeError, ValueError):
        return raw, os.environ.get("CLAUDE_CODE_SESSION_ID", "unknown")


def main():
    msg, session = parse_stdin()
    if not msg:
        return

    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    turn_id = f"{session[:8]}_{ts.replace(':', '-')}"

    # 写 turn_id（PostToolUse hooks 读取）
    TURN_FILE.write_text(
        json.dumps({"turn_id": turn_id, "ts": ts, "session": session}, ensure_ascii=False),
        encoding="utf-8",
    )

    # 维护话题窗口（无论是否 nudge 都要更新）
    current_tokens = tokenize_topic(msg)
    window, total_turns = load_topic_window()
    compact_msg = check_compact_nudge(current_tokens, window, total_turns)
    save_topic_window(update_topic_window(current_tokens, window), total_turns + 1)

    # 检查 stdin 关键词 nudge
    lower = msg.lower()
    for pat, nudge, agent in NUDGE_RULES_STDIN:
        if re.search(pat, lower):
            print(nudge)
            return

    # 检查前轮 stats nudge
    stats = load_prev_stats()
    stats_nudge = check_stats_nudge(stats)
    if stats_nudge:
        print(stats_nudge)
        return

    # 检查话题切换 → /compact nudge（优先级最低，仅默认无其它 nudge 时触发）
    if compact_msg:
        print(compact_msg)
        return

    # 默认静默


if __name__ == "__main__":
    main()
