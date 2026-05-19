#!/usr/bin/env python3
"""PreToolUse Agent hook: subagent prompt 质量门。

5 选 3 通过：目标/读写范围/输出格式/不做什么/预算。
不足 → ask（补充信息），prompt <20 字符 → deny。
"""

import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, allow, deny, ask  # noqa: E402

MIN_PROMPT_LEN = 20
MIN_PASS_COUNT = 3

CHECKS = [
    ("任务目标", lambda p: len(p) >= 50),
    ("读写范围", lambda p: bool(re.search(r"(/|\\|\.\w{1,5}\b|src/|harness/|agents/)", p))),
    ("输出格式", lambda p: bool(re.search(r"(返回|报告|JSON|markdown|摘要|列表|summary|report|format)", p, re.I))),
    ("不做什么", lambda p: bool(re.search(r"(不要|禁止|不修改|只读|不写|never|don.t|do not|read.only)", p, re.I))),
    ("预算限制", lambda p: bool(re.search(r"(最多|≤|上限|简短|<\s*\d|under\s+\d|max\s+\d|limit)", p, re.I))),
]


def extract_prompt(hook_input: dict) -> str:
    """从 hook 输入提取 subagent prompt。"""
    inp = hook_input.get("input", {})
    if isinstance(inp, dict):
        return inp.get("prompt", "")
    return ""


def main():
    hook_input = read_hook_input()
    prompt = extract_prompt(hook_input)

    if not prompt:
        allow()

    if len(prompt) < MIN_PROMPT_LEN:
        deny(f"🚫 subagent prompt 过短（{len(prompt)}<{MIN_PROMPT_LEN}字符），无法有效执行。补充任务目标和范围。")

    passed = []
    failed = []
    for name, check in CHECKS:
        if check(prompt):
            passed.append(name)
        else:
            failed.append(name)

    if len(passed) >= MIN_PASS_COUNT:
        allow()

    ask(
        f"subagent prompt 质量检查：通过 {len(passed)}/{len(CHECKS)}（需 {MIN_PASS_COUNT}）。"
        f" 缺少：{', '.join(failed)}。建议补充后重试。"
    )


if __name__ == "__main__":
    main()
