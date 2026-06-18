"""JSONL logging for global-memory MCP tool calls."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness.config import CLAUDE_LOGS_DIR

DEFAULT_SOURCE = "natural"
DEFAULT_MODE = "mcp_tool_call"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def log_path() -> Path:
    override = os.environ.get("GM_MCP_LOG_PATH")
    if override:
        return Path(override).expanduser()
    return CLAUDE_LOGS_DIR / "gm_mcp_tool_calls.jsonl"


def call_source(default: str = DEFAULT_SOURCE) -> str:
    return os.environ.get("GM_MCP_CALL_SOURCE") or default


def session_id() -> str | None:
    return os.environ.get("GM_MCP_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")


def task_id() -> str | None:
    return os.environ.get("GM_MCP_TASK_ID") or os.environ.get("CLAUDE_TASK_ID")


def append_log(record: dict[str, Any], *, path: Path | None = None) -> float:
    start = time.perf_counter()
    target = path or log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return (time.perf_counter() - start) * 1000.0


def summarize_error(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def run_logged(
    *,
    tool: str,
    query: str,
    args: dict[str, Any],
    backend: dict[str, Any],
    source: str | None,
    mode: str,
    call: Callable[[], tuple[dict[str, Any], dict[str, Any], dict[str, float]]],
) -> dict[str, Any]:
    start = time.perf_counter()
    src = source or call_source(DEFAULT_SOURCE)
    base: dict[str, Any] = {
        "schema_version": 1,
        "ts": utc_now(),
        "source": src,
        "mode": mode,
        "tool": tool,
        "query": query,
        "action": query if tool == "gm.rule" else None,
        "args": args,
        "session_id": session_id(),
        "task_id": task_id(),
        "backend": backend,
    }
    try:
        result, result_summary, timings = call()
        latency_ms = (time.perf_counter() - start) * 1000.0
        record = {
            **base,
            "status": "ok",
            "error": None,
            "latency_ms": round(latency_ms, 3),
            "elapsed_ms": round(latency_ms, 3),
            "timings": timings,
            **result_summary,
        }
        log_ms = append_log(record)
        timings["log_ms"] = log_ms
        record["timings"] = timings
        # Append a second corrected timing line would pollute counts; return timing in result instead.
        result.setdefault("diagnostics", {})["latency_ms"] = round(latency_ms, 3)
        result.setdefault("diagnostics", {})["timings"] = timings
        return result
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        record = {
            **base,
            "status": "error",
            "error": summarize_error(exc),
            "latency_ms": round(latency_ms, 3),
            "elapsed_ms": round(latency_ms, 3),
            "timings": {},
            "hit": False,
            "count": 0,
            "top_refs": [],
            "top_ids": [],
            "confidence": 0.0,
            "low_confidence": True,
            "returned_summary": "",
        }
        append_log(record)
        raise
