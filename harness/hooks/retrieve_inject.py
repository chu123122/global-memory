#!/usr/bin/env python3
"""
retrieve_inject.py — UserPromptSubmit hook

Generates a Context Brief (top-N relevant memory pointers) from the user's
prompt and injects it as additional context. Pure read-only.

Fail-open: any exception or timeout returns silently (no brief, no error).
Disable via env HARNESS_RETRIEVE_INJECT=0.

Logs:
    - retrieve calls (one JSON line per call, with source=retrieve_inject):
        $env:CLAUDE_HOME/logs/retrieve_calls.jsonl
      File stays JSONL (one record per line) so analyze_retrieve_log.py and
      other line-by-line parsers keep working — do not pretty-print in place.

      Pretty viewer (human-readable, multi-line):
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py"
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py" -n 30
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py" --source retrieve_inject
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py" --miss

      Quick greps (raw JSONL):
        Select-String '"source": "retrieve_inject"' <log>
        Select-String '"hit_count": 0' <log>

      Analyzer:
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/analyze_retrieve_log.py" --days 7
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

if "pytest" not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HARNESS_SCRIPTS = Path(os.environ.get("GLOBAL_HARNESS_SCRIPTS", str(Path(__file__).resolve().parent.parent / "scripts")))
sys.path.insert(0, str(HARNESS_SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

TIMEOUT_SEC = 1.0
MIN_QUERY_LEN = 3
CLAUDE_DIR = Path.home() / ".claude"
CURRENT_TASK_FILE = CLAUDE_DIR / ".current_task"
SESSION_TASKS_DIR = CLAUDE_DIR / ".session_tasks"


def _parse_stdin() -> tuple[str, str]:
    try:
        raw_bytes = sys.stdin.buffer.read()
        raw = raw_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        raw = sys.stdin.read().strip()
    if not raw:
        return "", ""
    try:
        d = json.loads(raw)
        return d.get("prompt", "") or "", d.get("session_id", "") or ""
    except Exception:
        return raw, ""


def _read_session_task_file(session_id: str) -> str:
    if not session_id:
        return ""
    try:
        marker = SESSION_TASKS_DIR / session_id
        if marker.is_file():
            name = marker.read_text(encoding="utf-8").strip()
            if name:
                return name
    except Exception:
        pass
    return ""


def _read_current_task_file() -> str:
    try:
        if CURRENT_TASK_FILE.is_file():
            name = CURRENT_TASK_FILE.read_text(encoding="utf-8").strip()
            if name:
                return name
    except Exception:
        pass
    return ""


def _resolve_task(session_id: str = "") -> str:
    """Resolve current task name.

    Priority:
        1. ~/.claude/.session_tasks/<session_id> (multi-terminal task marker)
        2. ~/.claude/.current_task (legacy/global fallback)
        3. cwd → registry owner
        4. registry.active_tasks[0]
    """
    session_task = _read_session_task_file(session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    if session_task:
        return session_task
    current_task = _read_current_task_file()
    if current_task:
        return current_task
    try:
        from _task_resolver import load_registry, resolve_task_owner
        reg = load_registry()
        cwd = os.getcwd()
        t = resolve_task_owner(cwd, reg)
        if t:
            return t
        actives = reg.get("active_tasks", []) or []
        if actives:
            return actives[0]
    except Exception:
        pass
    return "unknown"


def _run_retrieve(task_name: str, user_msg: str) -> str | None:
    """Call harness_retrieve.retrieve() in-process. Returns brief yaml or None."""
    try:
        from harness_retrieve import retrieve, write_retrieve_log, resolve_project_memory
    except Exception:
        return None

    # 局部层：当前项目 CLI 自动记忆目录（cwd→projects/<slug>/memory）。无则 None，retrieve 跳过。
    try:
        project_mem = resolve_project_memory()
    except Exception:
        project_mem = None

    t0 = time.perf_counter()
    try:
        brief = retrieve(task_name=task_name, user_msg=user_msg, project_memory_root=project_mem)
    except Exception:
        return None
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    try:
        write_retrieve_log(
            task_name=task_name,
            user_msg=user_msg,
            brief=brief,
            elapsed_ms=elapsed_ms,
            extras={"source": "retrieve_inject"},
        )
    except Exception as e:
        try:
            import traceback
            dbg = Path.home() / ".claude" / "logs" / "retrieve_inject_debug.log"
            dbg.parent.mkdir(parents=True, exist_ok=True)
            with dbg.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} write_retrieve_log raised: {e!r}\n")
                f.write(traceback.format_exc())
                f.write("\n")
        except Exception:
            pass

    # 类型选择性注入（decision_retrieve_injector_feedback_failure 修订版）：
    # - feedback 排除：行为规则该常驻 CLAUDE.md，做成 JIT 指针 AI 系统性不读。
    # - fixes/knowledge/decisions 保留：参考型经验，跨 task 浮出是真价值；且现已
    #   带 summary(description)，AI 直接吃免再 Read，治了"裸路径不读"的投递洞。
    # write_retrieve_log 上方已记完整 brief，分析数据不丢；此处仅过滤实际注入。
    def _is_feedback(p: dict) -> bool:
        path = (p.get("path") or "").lower().replace("\\", "/")
        return "/feedback/" in path or "/feedback_" in path

    brief.relevant_pointers = [p for p in brief.relevant_pointers if not _is_feedback(p)]

    if not brief.relevant_pointers and not (brief.handoff_path or "").strip():
        return None

    return brief.to_yaml_like()


def _trace(stage: str, **extra) -> None:
    try:
        p = Path.home() / ".claude" / "logs" / "retrieve_inject_debug.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            kv = " ".join(f"{k}={v!r}" for k, v in extra.items())
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} HOOK {stage} {kv}\n")
    except Exception:
        pass


def main() -> None:
    _trace("entry", pid=os.getpid(), inject_env=os.environ.get("HARNESS_RETRIEVE_INJECT", "1"), log_env=os.environ.get("HARNESS_RETRIEVE_LOG", "1"))
    if os.environ.get("HARNESS_RETRIEVE_INJECT", "1") == "0":
        _trace("skip_disabled")
        return

    user_msg, session_id = _parse_stdin()
    _trace("parsed", msg_len=len(user_msg or ""), preview=(user_msg or "")[:60])
    if not user_msg or len(user_msg.strip()) < MIN_QUERY_LEN:
        _trace("skip_short")
        return

    t_start = time.perf_counter()
    task_name = _resolve_task(session_id)
    _trace("resolved", task=task_name)
    brief_yaml = _run_retrieve(task_name, user_msg)
    elapsed = time.perf_counter() - t_start
    _trace("after_retrieve", elapsed_ms=round(elapsed*1000,1), has_brief=bool(brief_yaml))

    if elapsed > TIMEOUT_SEC:
        return
    if not brief_yaml:
        return

    print("📎 Context Brief (auto-retrieved memory pointers):")
    print("```yaml")
    print(brief_yaml.rstrip())
    print("```")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
