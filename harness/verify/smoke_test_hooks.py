#!/usr/bin/env python3
"""
smoke_test_hooks.py - Phase 3 MVP: harness hooks 端到端冒烟测试

通过 subprocess 调用每个 hook 脚本 + 模拟 stdin JSON,
验证 exit code 符合预期。

MVP 覆盖 4 个 simpler hooks(8 用例):
  SMK-001 dangerous_command_blocker  (happy + fail)
  SMK-002 memory_file_protector       (happy + fail-protected)
  SMK-003 audit_logger                 (happy + robust-no-input)
  SMK-004 subagent_logger              (happy + robust-no-input)

未覆盖(Phase 3 v2):
  doc_gate(需 fake task dir / registry mock)
  diff_backup / diff_show(fs 操作 + GUI subprocess)
  post_task_hook(git 副作用大)

输出:
  --json 机器可读;默认人类可读
  退出码:0 全 PASS;2 有 FAIL
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Windows UTF-8(支持 emoji)
for _stream in (sys.stdout, sys.stderr):
    try:
        if getattr(_stream, "encoding", None) != "utf-8" and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HARNESS_DIR = Path(__file__).resolve().parent.parent  # 本文件在 harness/verify/，上溯到 harness/
HOOKS_DIR = HARNESS_DIR / "hooks"
POST_TASK = HARNESS_DIR / "post_task_hook.py"  # not in hooks/, sits at harness/


def run_hook(script: Path, stdin_json: dict | str | None) -> tuple[int, str, str]:
    """跑 hook 脚本 + stdin。返回 (exit_code, stdout, stderr)"""
    if stdin_json is None:
        stdin_data = ""
    elif isinstance(stdin_json, str):
        stdin_data = stdin_json
    else:
        stdin_data = json.dumps(stdin_json)
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=stdin_data,
        capture_output=True, text=True, encoding="utf-8",
        timeout=10,
    )
    return proc.returncode, proc.stdout, proc.stderr


def case(smk_id: str, hook_name: str, scenario: str,
         script: Path, stdin: dict | str | None,
         expected_exit: int | list[int],
         expected_stdout_contains: str | None = None) -> dict:
    """运行一个 smoke case,返回结果字典。
    可选 expected_stdout_contains 用于检查 ask 等"exit 0 + 特殊输出"模式。
    """
    code, stdout, stderr = run_hook(script, stdin)
    expected = expected_exit if isinstance(expected_exit, list) else [expected_exit]
    exit_ok = code in expected
    stdout_ok = (expected_stdout_contains is None) or (expected_stdout_contains in stdout)
    passed = exit_ok and stdout_ok
    return {
        "smk_id": smk_id,
        "hook": hook_name,
        "scenario": scenario,
        "expected_exit": expected,
        "actual_exit": code,
        "expected_stdout_contains": expected_stdout_contains,
        "stdout_snippet": stdout[:200] if stdout else "",
        "result": "PASS" if passed else "FAIL",
        "stderr_snippet": stderr[:200] if stderr else "",
    }


def smoke_dangerous_command_blocker() -> list[dict]:
    """SMK-001: dangerous_command_blocker"""
    script = HOOKS_DIR / "dangerous_command_blocker.py"
    return [
        case("SMK-001H", "dangerous_command_blocker", "happy: safe ls",
             script, {"tool": "Bash", "tool_input": {"command": "ls"}},
             expected_exit=0),
        case("SMK-001F", "dangerous_command_blocker", "fail: rm -rf / (must deny)",
             script, {"tool": "Bash", "tool_input": {"command": "rm -rf /"}},
             expected_exit=2),
    ]


def smoke_memory_file_protector() -> list[dict]:
    """SMK-002: memory_file_protector"""
    script = HOOKS_DIR / "memory_file_protector.py"
    return [
        case("SMK-002H", "memory_file_protector", "happy: edit /tmp/foo.md",
             script, {"tool": "Edit", "tool_input": {"file_path": "/tmp/foo.md"}},
             expected_exit=0),
        case("SMK-002F", "memory_file_protector", "fail: edit CLAUDE.md (must ask: exit 0 + permissionDecision=ask)",
             script, {"tool": "Edit", "tool_input": {"file_path": str(Path.home() / ".claude" / "CLAUDE.md")}},
             expected_exit=0,
             expected_stdout_contains="permissionDecision"),
    ]


def smoke_audit_logger() -> list[dict]:
    """SMK-003: audit_logger (PostToolUse, only logs, never blocks)"""
    script = HOOKS_DIR / "audit_logger.py"
    return [
        case("SMK-003H", "audit_logger", "happy: any tool call appended to jsonl",
             script, {"tool": "Bash", "tool_input": {"command": "ls"}, "tool_response": "..."},
             expected_exit=0),
        case("SMK-003R", "audit_logger", "robust: empty stdin still exits 0",
             script, "",
             expected_exit=0),
    ]


def smoke_subagent_logger() -> list[dict]:
    """SMK-004: subagent_logger"""
    script = HOOKS_DIR / "subagent_logger.py"
    return [
        case("SMK-004H", "subagent_logger", "happy: subagent_start event",
             script, {"event_name": "SubagentStart", "subagent_type": "design-reviewer"},
             expected_exit=0),
        case("SMK-004R", "subagent_logger", "robust: empty stdin still exits 0",
             script, "",
             expected_exit=0),
    ]


def smoke_read_large_file_guard() -> list[dict]:
    """SMK-005: read_large_file_guard (PreToolUse Read; 小文件放行 + 空 stdin fail-open)"""
    script = HOOKS_DIR / "read_large_file_guard.py"
    return [
        case("SMK-005H", "read_large_file_guard", "happy: read small/normal path 放行",
             script, {"tool": "Read", "tool_input": {"file_path": "/tmp/small.txt"}},
             expected_exit=0),
        case("SMK-005R", "read_large_file_guard", "robust: empty stdin fail-open 退 0",
             script, "", expected_exit=0),
    ]


def smoke_agent_prompt_gate() -> list[dict]:
    """SMK-006: agent_prompt_gate (PreToolUse Agent; 空输入 fail-open)"""
    script = HOOKS_DIR / "agent_prompt_gate.py"
    return [
        case("SMK-006R", "agent_prompt_gate", "robust: empty stdin 不崩(退 0)",
             script, "", expected_exit=0),
    ]


def smoke_memory_lint_gate() -> list[dict]:
    """SMK-007: memory_lint_gate (PreToolUse Write; 非记忆文件放行 + 空 fail-open)"""
    script = HOOKS_DIR / "memory_lint_gate.py"
    return [
        case("SMK-007H", "memory_lint_gate", "happy: 非记忆目录文件放行",
             script, {"tool": "Edit", "tool_input": {"file_path": "/tmp/foo.py"}},
             expected_exit=0),
        case("SMK-007R", "memory_lint_gate", "robust: empty stdin 退 0",
             script, "", expected_exit=0),
    ]


def smoke_subagent_stop_logger() -> list[dict]:
    """SMK-008: subagent_stop_logger (SubagentStop; 只记日志)"""
    script = HOOKS_DIR / "subagent_stop_logger.py"
    return [
        case("SMK-008H", "subagent_stop_logger", "happy: stop event 记日志",
             script, {"event_name": "SubagentStop", "subagent_type": "Explore"},
             expected_exit=0),
        case("SMK-008R", "subagent_stop_logger", "robust: empty stdin 退 0",
             script, "", expected_exit=0),
    ]


def smoke_diff_backup_show() -> list[dict]:
    """SMK-009: diff_backup / diff_show (白名单外/空输入应放行不崩)"""
    backup = HOOKS_DIR / "diff_backup.py"
    show = HOOKS_DIR / "diff_show.py"
    return [
        case("SMK-009BH", "diff_backup", "happy: 白名单外 /tmp 文件放行",
             backup, {"tool": "Edit", "tool_input": {"file_path": "/tmp/foo.txt"}},
             expected_exit=0),
        case("SMK-009BR", "diff_backup", "robust: empty stdin 退 0",
             backup, "", expected_exit=0),
        case("SMK-009SR", "diff_show", "robust: empty stdin 退 0",
             show, "", expected_exit=0),
    ]


def smoke_userprompt_injectors() -> list[dict]:
    """SMK-010: UserPromptSubmit 注入链 fail-open(空 stdin 静默退 0,绝不阻断)"""
    cases = []
    for name in ("changelog_inject", "sync_inject", "route_check", "retrieve_inject"):
        script = HOOKS_DIR / f"{name}.py"
        cases.append(
            case(f"SMK-010-{name}", name, "robust: empty stdin fail-open 退 0",
                 script, "", expected_exit=0)
        )
    return cases


def smoke_learning_opportunity_nudge() -> list[dict]:
    """SMK-011: learning_opportunity_nudge (PostToolUse Bash; 空输入退 0)"""
    script = HOOKS_DIR / "learning_opportunity_nudge.py"
    return [
        case("SMK-011R", "learning_opportunity_nudge", "robust: empty stdin 退 0",
             script, "", expected_exit=0),
    ]


def smoke_doc_gate() -> list[dict]:
    """SMK-012: doc_gate (PreToolUse Write; 不匹配任何 task 的文件 → 放行)"""
    script = HOOKS_DIR / "doc_gate.py"
    return [
        case("SMK-012H", "doc_gate", "happy: 不在任何 task 内的文件放行",
             script, {"tool": "Edit", "tool_input": {"file_path": "/tmp/unrelated.txt"}},
             expected_exit=0),
        case("SMK-012R", "doc_gate", "robust: empty stdin 退 0",
             script, "", expected_exit=0),
    ]


def main() -> int:
    p = argparse.ArgumentParser(description="smoke_test_hooks (matrix v2)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    all_cases = (
        smoke_dangerous_command_blocker()
        + smoke_memory_file_protector()
        + smoke_audit_logger()
        + smoke_subagent_logger()
        + smoke_read_large_file_guard()
        + smoke_agent_prompt_gate()
        + smoke_memory_lint_gate()
        + smoke_subagent_stop_logger()
        + smoke_diff_backup_show()
        + smoke_userprompt_injectors()
        + smoke_learning_opportunity_nudge()
        + smoke_doc_gate()
    )

    summary = {"PASS": 0, "FAIL": 0}
    for c in all_cases:
        summary[c["result"]] += 1

    report = {
        "matrix_v": "v2",
        "total_cases": len(all_cases),
        "summary": summary,
        "cases": all_cases,
        "v2_pending_hooks": ["post_task_hook (git push 副作用,不在 smoke 跑)", "doc_gate deny-path (需 fake task+registry fixture)"],
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[smoke_test_hooks MVP] {len(all_cases)} cases\n")
        for c in all_cases:
            icon = "✅" if c["result"] == "PASS" else "❌"
            print(f"{icon} [{c['smk_id']}] {c['hook']}: {c['scenario']}")
            print(f"     expected_exit={c['expected_exit']} actual_exit={c['actual_exit']}")
            if c["result"] == "FAIL" and c["stderr_snippet"]:
                print(f"     stderr: {c['stderr_snippet']}")
        print(f"\n  结果:{summary['PASS']} PASS / {summary['FAIL']} FAIL  (matrix v2: 12 hooks 覆盖; post_task_hook + doc_gate deny-path 待 fixture)")

    return 0 if summary["FAIL"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
