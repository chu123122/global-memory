#!/usr/bin/env python3
"""
retrieve_inject.py — UserPromptSubmit hook

Generates a Context Brief (top-N relevant memory pointers) from the user's
prompt and injects it as additional context. Pure read-only.

Fail-open: any exception or timeout returns silently (no brief, no error).
Disable via env HARNESS_RETRIEVE_INJECT=0.

Logs:
    - retrieve calls (one JSON line per call, with source=retrieve_inject):
        $env:GLOBAL_MEMORY_LOGS_DIR/retrieve_calls.jsonl
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

HARNESS_ROOT = Path(__file__).resolve().parent.parent
HARNESS_SCRIPTS = Path(os.environ.get("GLOBAL_HARNESS_SCRIPTS", str(HARNESS_ROOT / "scripts")))
sys.path.insert(0, str(HARNESS_ROOT))
sys.path.insert(0, str(HARNESS_SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config import GLOBAL_MEMORY_LOGS_DIR, is_runtime_logs_dir_in_repo, runtime_logs_repo_warning
except Exception:  # fail-open fallback for standalone hook invocation
    GLOBAL_MEMORY_LOGS_DIR = Path.home() / ".global-memory" / "logs"

    def is_runtime_logs_dir_in_repo(_logs_dir: Path | None = None) -> bool:
        return False

    def runtime_logs_repo_warning(_logs_dir: Path | None = None) -> str:
        return "WARNING: runtime logs dir is inside the global-memory repository"

TIMEOUT_SEC = 1.0
MIN_QUERY_LEN = 3
CLAUDE_DIR = Path.home() / ".claude"
SESSION_TASKS_DIR = CLAUDE_DIR / ".session_tasks"


def _parse_stdin() -> tuple[str, str, str]:
    try:
        raw_bytes = sys.stdin.buffer.read()
        raw = raw_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        raw = sys.stdin.read().strip()
    if not raw:
        return "", "", ""
    try:
        d = json.loads(raw)
        prompt = d.get("prompt") or d.get("user_prompt") or d.get("message") or ""
        session_id = d.get("session_id") or d.get("hook_session_id") or d.get("conversation_id") or ""
        client = d.get("client") or d.get("source") or ""
        return prompt, session_id, client
    except Exception:
        return raw, "", ""


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


def _resolve_task(session_id: str = "") -> str:
    """Resolve the task name for THIS session's brief.

    All signals are per-terminal, so one terminal cannot pollute another's brief:
        1. ~/.claude/.session_tasks/<session_id>  (this session's marker)
        2. cwd → registry owner                   (cwd is terminal-specific)
    The global ~/.claude/.current_task is an informational marker only and is
    NOT consulted; nor do we blindly fall back to active_tasks[0] (a global guess
    unrelated to this terminal). No per-terminal match → "unknown".
    """
    session_task = _read_session_task_file(session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    if session_task:
        return session_task
    try:
        from _task_resolver import load_registry, resolve_task_owner
        t = resolve_task_owner(os.getcwd(), load_registry())
        if t:
            return t
    except Exception:
        pass
    return "unknown"


def _run_retrieve(task_name: str, user_msg: str, session_id: str = "", client: str = "") -> str | None:
    """Call harness_retrieve.retrieve() in-process. Returns brief yaml or None."""
    try:
        from harness_retrieve import retrieve, write_retrieve_log, DEFAULT_TASK_INDEX_PATH
    except Exception:
        return None

    # 局部层：ClaudeTasks 跨任务经验索引（不存在 retrieve 内部跳过）。
    t0 = time.perf_counter()
    try:
        brief = retrieve(task_name=task_name, user_msg=user_msg, task_index_path=DEFAULT_TASK_INDEX_PATH)
    except Exception:
        return None
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    try:
        write_retrieve_log(
            task_name=task_name,
            user_msg=user_msg,
            brief=brief,
            elapsed_ms=elapsed_ms,
            extras={
                "source": "retrieve_inject",
                "client": client,
                "hook_session_id": session_id,
            },
        )
    except Exception as e:
        try:
            import traceback
            dbg = GLOBAL_MEMORY_LOGS_DIR / "retrieve_inject_debug.log"
            if is_runtime_logs_dir_in_repo(dbg.parent):
                raise RuntimeError(runtime_logs_repo_warning(dbg.parent))
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
        p = GLOBAL_MEMORY_LOGS_DIR / "retrieve_inject_debug.log"
        if is_runtime_logs_dir_in_repo(p.parent):
            return
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

    user_msg, session_id, client = _parse_stdin()
    _trace("parsed", msg_len=len(user_msg or ""), preview=(user_msg or "")[:60], client=client, session_id=session_id)
    if not user_msg or len(user_msg.strip()) < MIN_QUERY_LEN:
        _trace("skip_short")
        return

    t_start = time.perf_counter()
    task_name = _resolve_task(session_id)
    _trace("resolved", task=task_name)
    brief_yaml = _run_retrieve(task_name, user_msg, session_id=session_id, client=client)
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
