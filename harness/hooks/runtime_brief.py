#!/usr/bin/env python3
"""Deterministic runtime config brief for hook/MCP/RAG status questions.

This module is read-only and intentionally independent from retrieve_inject's
RAG path: it never calls policy matching or gm.search.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

try:
    from config import GLOBAL_MEMORY_LOGS_DIR as DEFAULT_LOGS_DIR
except Exception:  # standalone hook fallback
    DEFAULT_LOGS_DIR = Path.home() / ".global-memory" / "logs"

HARNESS_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_BRIEF_TAIL_BYTES = 64 * 1024
RUNTIME_BRIEF_DEBUG_LINES = 8
COOLDOWN_FILE = "gm_search_sidecar_cooldown.json"
RUNTIME_BRIEF_INTENT_WINDOW_CHARS = 500


def _lower_for_match(text: str) -> str:
    return (text or "").casefold()


def _looks_like_forwarded_runtime_brief(text: str) -> bool:
    """Return True for already-injected hook context pasted back by the client.

    A Runtime Config Brief is itself full of trigger words (hook/mcp/rag/status).
    If we classify the forwarded brief as a fresh user question, the hook will
    recursively inject another Runtime Brief into meta-discussions about the
    previous injection.
    """
    lowered = _lower_for_match(text)
    if "userpromptsubmit hook (completed)" in lowered and "runtime config brief" in lowered:
        return True
    if "hook context:" in lowered and "deterministic_runtime_config" in lowered:
        return True
    return False


def _looks_like_task_execution_prompt(text: str) -> bool:
    lowered = _lower_for_match(text.lstrip())
    return lowered.startswith("a previous agent produced the plan below") or lowered.startswith("implement the plan")


def _intent_window(text: str) -> str:
    """Return only the leading user-intent window used for classification.

    Runtime Brief is for explicit current-state questions.  Full prompts often
    contain quoted plans, logs, or previous hook output with words like
    mcp/status/runtime; scanning the whole prompt causes false positives.
    """
    stripped = text.strip()
    first_fence = stripped.find("```")
    if first_fence >= 0:
        stripped = stripped[:first_fence]
    return stripped[:RUNTIME_BRIEF_INTENT_WINDOW_CHARS]


def runtime_brief_topic(user_msg: str) -> str | None:
    """Classify current runtime/config questions that should not use RAG."""
    if _looks_like_forwarded_runtime_brief(user_msg) or _looks_like_task_execution_prompt(user_msg):
        return None
    text = _lower_for_match(_intent_window(user_msg))
    if not text.strip():
        return None
    currentish = any(token in text for token in ["当前", "现在", "目前", "刚才", "本轮", "运行状态", "配置", "status", "runtime", "current"])
    if ("hook" in text or "钩子" in text or "注入" in text) and any(token in text for token in ["没注入", "未注入", "不注入", "为什么刚才", "没出来", "no inject", "not inject"]):
        return "why_hook_no_inject"
    if "mcp" in text and (currentish or any(token in text for token in ["启动", "暴露", "注册", "状态", "起来", "expose", "started"])):
        return "mcp_status"
    if "rag" in text and any(token in text for token in ["自动更新", "还在", "是否", "状态", "当前", "现在", "更新"]):
        return "rag_auto_update"
    if ("hook" in text or "钩子" in text or "主循环" in text) and (currentish or any(token in text for token in ["列表", "有哪些", "有什么", "链路"])):
        return "hook_list"
    if any(token in text for token in ["当前配置", "运行状态", "runtime config", "runtime status"]) and any(token in text for token in ["hook", "mcp", "rag", "召回", "注入"]):
        return "runtime_config"
    return None


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _tail_text(path: Path, *, max_bytes: int = RUNTIME_BRIEF_TAIL_BYTES) -> str:
    try:
        if not path.is_file():
            return ""
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
            raw = handle.read()
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _last_jsonl_record(path: Path) -> dict[str, Any]:
    tail = _tail_text(path)
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            return data if isinstance(data, dict) else {}
        except Exception:
            continue
    return {}


def _grep_recent_debug_lines(path: Path) -> list[str]:
    tail = _tail_text(path)
    wanted = []
    keywords = ("skip_", "sidecar_", "after_gm_search", "parsed", "resolved", "runtime_brief")
    for line in tail.splitlines():
        if any(keyword in line for keyword in keywords):
            wanted.append(line[-240:])
    return wanted[-RUNTIME_BRIEF_DEBUG_LINES:]


def _hook_manifest_summary(harness_root: Path) -> list[dict[str, object]]:
    manifest = _read_json_file(harness_root / "hook_manifest.json")
    rows: list[dict[str, object]] = []
    for event, groups in (manifest.get("hooks") or {}).items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            matcher = group.get("matcher", "*") if isinstance(group, dict) else "*"
            hooks = group.get("hooks", []) if isinstance(group, dict) else []
            for spec in hooks if isinstance(hooks, list) else []:
                if isinstance(spec, dict):
                    rows.append({
                        "event": event,
                        "matcher": matcher,
                        "path": spec.get("path"),
                        "failure_action": spec.get("failure_action"),
                    })
    status = manifest.get("statusLine") if isinstance(manifest.get("statusLine"), dict) else None
    if status:
        rows.append({"event": "statusLine", "matcher": "*", "path": status.get("path"), "failure_action": status.get("failure_action")})
    return rows


def _config_contains(path: Path, needle: str) -> bool:
    try:
        if path.is_file():
            return needle in path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return False


def sidecar_cooldown_snapshot(logs_dir: Path | None = None, *, now: float | None = None) -> dict[str, object]:
    """Return a safe, display-ready view of sidecar cooldown state."""
    root = logs_dir or DEFAULT_LOGS_DIR
    data = _read_json_file(root / COOLDOWN_FILE)
    until_epoch = data.get("cooldown_until_epoch")
    now_epoch = time.time() if now is None else now
    cooling_down = False
    try:
        cooling_down = float(until_epoch) > now_epoch
    except Exception:
        cooling_down = False
    return {
        "cooling_down": cooling_down,
        "cooldown_until": data.get("cooldown_until") or "",
        "failure_count": int(data.get("failure_count") or 0),
        "last_reason": data.get("last_reason") or "",
    }


def runtime_status_payload(topic: str, *, logs_dir: Path | None = None, harness_root: Path | None = None) -> dict[str, object]:
    root = logs_dir or DEFAULT_LOGS_DIR
    hroot = harness_root or HARNESS_ROOT
    retrieve_log = root / "retrieve_calls.jsonl"
    debug_log = root / "retrieve_inject_debug.log"
    sidecar_pid = _read_json_file(root / "gm_search_sidecar.pid.json")
    sidecar_start = _read_json_file(root / "gm_search_sidecar_start_attempt.json")
    sidecar_last = _last_jsonl_record(root / "gm_search_sidecar.log")
    last_retrieve = _last_jsonl_record(retrieve_log)
    codex_config = Path.home() / ".codex" / "config.toml"
    claude_json = Path.home() / ".claude.json"
    post_task_text = ""
    daemon_text = ""
    try:
        post_task_text = (hroot / "post_task_hook.py").read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        daemon_text = (hroot / "auto_sync_daemon.py").read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return {
        "topic": topic,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "deterministic_runtime_config",
        "logs_dir": str(root),
        "hook_manifest_path": str(hroot / "hook_manifest.json"),
        "hooks": _hook_manifest_summary(hroot),
        "mcp": {
            "codex_config_path": str(codex_config),
            "codex_global_memory_present": _config_contains(codex_config, "global-memory"),
            "claude_json_path": str(claude_json),
            "claude_global_memory_present": _config_contains(claude_json, "global-memory"),
            "rule_tool_env_present_in_codex": _config_contains(codex_config, "GM_MCP_EXPOSE_RULE_TOOL"),
        },
        "rag_runtime": {
            "retrieve_calls_exists": retrieve_log.is_file(),
            "last_retrieve_call": {k: last_retrieve.get(k) for k in ["ts", "source", "hit", "hit_count", "abstained", "abstain_reason", "decision_reason", "sidecar_status"] if k in last_retrieve},
            "sidecar_cooldown": sidecar_cooldown_snapshot(root),
            "debug_tail": _grep_recent_debug_lines(debug_log),
            "sidecar_pid": sidecar_pid,
            "sidecar_start_attempt": sidecar_start,
            "sidecar_last_event": sidecar_last,
        },
        "semantic_refresh": {
            "worker_exists": (hroot / "semantic_refresh_worker.py").is_file(),
            "post_task_hook_mentions_worker": "semantic_refresh_worker" in post_task_text,
            "post_task_hook_uses_check_only": "--check-only" in post_task_text,
            "auto_sync_daemon_mentions_semantic_refresh": "semantic_refresh_worker" in daemon_text or "semantic-sync" in daemon_text,
        },
    }


def _yaml_scalar(value: object) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", "\n", "'", '"']):
        return json.dumps(text, ensure_ascii=False)
    return text


def _append_yaml_value(lines: list[str], key: str, value: object, indent: int = 0) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        lines.append(f"{prefix}{key}:")
        for child_key, child_value in value.items():
            _append_yaml_value(lines, str(child_key), child_value, indent + 2)
    elif isinstance(value, list):
        lines.append(f"{prefix}{key}:")
        if not value:
            lines.append(f"{prefix}  []")
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}  -")
                for child_key, child_value in item.items():
                    _append_yaml_value(lines, str(child_key), child_value, indent + 4)
            else:
                lines.append(f"{prefix}  - {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")


def format_runtime_brief(payload: dict[str, object]) -> str:
    lines: list[str] = []
    for key, value in payload.items():
        if key == "hooks" and isinstance(value, list):
            # Keep hook list compact for prompt injection.
            lines.append("hooks:")
            for item in value:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "  - "
                    f"event: {_yaml_scalar(item.get('event'))}; "
                    f"matcher: {_yaml_scalar(item.get('matcher'))}; "
                    f"path: {_yaml_scalar(item.get('path'))}; "
                    f"failure_action: {_yaml_scalar(item.get('failure_action'))}"
                )
            continue
        _append_yaml_value(lines, key, value)
    return "\n".join(lines) + "\n"


def build_runtime_brief(user_msg: str, *, logs_dir: Path | None = None, harness_root: Path | None = None) -> str | None:
    topic = runtime_brief_topic(user_msg)
    if topic is None:
        return None
    return format_runtime_brief(runtime_status_payload(topic, logs_dir=logs_dir, harness_root=harness_root))
