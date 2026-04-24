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

HARNESS_DIR = Path(__file__).resolve().parent
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


def main() -> int:
    p = argparse.ArgumentParser(description="smoke_test_hooks Phase 3 MVP")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    all_cases = (
        smoke_dangerous_command_blocker()
        + smoke_memory_file_protector()
        + smoke_audit_logger()
        + smoke_subagent_logger()
    )

    summary = {"PASS": 0, "FAIL": 0}
    for c in all_cases:
        summary[c["result"]] += 1

    report = {
        "matrix_v": "v1",
        "total_cases": len(all_cases),
        "summary": summary,
        "cases": all_cases,
        "v2_pending_hooks": ["doc_gate", "diff_backup", "diff_show", "post_task_hook"],
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
        print(f"\n  结果:{summary['PASS']} PASS / {summary['FAIL']} FAIL  (covered 4/8 hooks; 4 pending v2)")

    return 0 if summary["FAIL"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
