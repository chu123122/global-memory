#!/usr/bin/env python3
"""PreToolUse hook (Write|Edit): 阻断未完成路由计划的实现动作。

检查 .route_pending.json 中 plan_path 指向的计划文件：
- 存在 + JSON 合法 + 格式校验通过 → 删 pending，放行
- 否则 → exit 2 阻断
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, allow, deny  # noqa: E402

CLAUDE_DIR = Path.home() / ".claude"

VALID_EXECUTORS = {"主模型", "sonnet", "haiku", "Explore"}
VALID_OVERALL = {"主模型", "派 sonnet", "派 haiku", "派 Explore", "混合"}

MIN_ACTION_LEN = 5
MIN_REASON_LEN = 8

# 黑名单：明显敷衍的 action/reason 模式
LAZY_ACTION_PATTERNS = [
    r"^.{0,4}$",
    r"^(做|改|写|跑|看|查|处理|实现|完成|执行|操作)$",
    r"^(实现|处理|完成|执行|操作).{0,3}$",
]
LAZY_REASON_PATTERNS = [
    r"^.{0,7}$",
    r"^(需要|高耦合|低耦合|因为|所以|必须|要求|直接)$",
    r"^(高耦合|低耦合).{0,3}$",
    r"^需要.{0,4}$",
]


def pending_file_for_session() -> Path | None:
    """找到当前 session 的 pending 文件。"""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if session_id:
        p = CLAUDE_DIR / f".route_pending_{session_id}.json"
        if p.exists():
            return p
    # fallback: 扫描所有 pending 文件，取最新的（单终端场景兼容）
    candidates = list(CLAUDE_DIR.glob(".route_pending_*.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)


def load_pending() -> tuple[dict | None, Path | None]:
    pf = pending_file_for_session()
    if not pf:
        return None, None
    try:
        return json.loads(pf.read_text(encoding="utf-8")), pf
    except Exception:
        return None, None


def validate_plan(plan_path: str, expected_ts: str) -> tuple[bool, str]:
    """校验计划文件格式。返回 (pass, error_msg)。"""
    p = Path(plan_path)
    if not p.exists():
        return False, f"计划文件不存在：{plan_path}"

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception) as e:
        return False, f"计划文件 JSON 解析失败：{e}"

    # 根字段检查
    for field in ("ts", "session", "input_preview", "overall", "steps"):
        if field not in data:
            return False, f"缺少必填字段：{field}"

    if not isinstance(data.get("input_preview", ""), str) or len(data["input_preview"]) < 4:
        return False, "input_preview 过短（≥4字符）"

    if data.get("overall") not in VALID_OVERALL:
        return False, f"overall 值非法：{data.get('overall')}，合法值：{VALID_OVERALL}"

    # ts 匹配检查
    if data.get("ts") != expected_ts:
        return False, f"ts 不匹配：计划={data.get('ts')}，期望={expected_ts}"

    # steps 检查
    steps = data.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        return False, "steps 必须是非空数组"

    all_main = True
    for i, step in enumerate(steps):
        prefix = f"steps[{i}]"

        for field in ("id", "action", "executor", "reason"):
            if field not in step or not isinstance(step[field], str) or not step[field].strip():
                return False, f"{prefix} 缺少或为空：{field}"

        action = step["action"].strip()
        reason = step["reason"].strip()
        executor = step["executor"].strip()

        if executor not in VALID_EXECUTORS:
            return False, f"{prefix}.executor 非法：{executor}"

        if executor != "主模型":
            all_main = False

        if len(action) < MIN_ACTION_LEN:
            return False, f"{prefix}.action 过短（{len(action)}<{MIN_ACTION_LEN}）：'{action}'"

        if len(reason) < MIN_REASON_LEN:
            return False, f"{prefix}.reason 过短（{len(reason)}<{MIN_REASON_LEN}）：'{reason}'"

        for pat in LAZY_ACTION_PATTERNS:
            if re.match(pat, action):
                return False, f"{prefix}.action 疑似敷衍：'{action}'"

        for pat in LAZY_REASON_PATTERNS:
            if re.match(pat, reason):
                return False, f"{prefix}.reason 疑似敷衍：'{reason}'"

    # 全主模型警告（不阻断，注入提示）
    if all_main and len(steps) > 1:
        print(
            f"⚠️ 计划中 {len(steps)} 步全为主模型，确认无可派遣段？",
            file=sys.stderr,
        )

    return True, ""


def main():
    read_hook_input()

    pending, pending_file = load_pending()
    if not pending:
        allow()

    plan_path = pending.get("plan_path", "")
    expected_ts = pending.get("ts", "")

    if not plan_path or not expected_ts:
        allow()

    ok, err = validate_plan(plan_path, expected_ts)
    if ok:
        try:
            if pending_file:
                pending_file.unlink(missing_ok=True)
        except Exception:
            pass
        allow()

    deny(
        f"🚫 路由计划校验失败：{err}\n"
        f"写计划文件到：{plan_path}\n"
        f"ts 必须为：{expected_ts}"
    )


if __name__ == "__main__":
    main()
