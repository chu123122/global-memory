"""Phase 10 lead CLI MCP-style bridge beta.

This module exposes the standalone bridge worker tool surface as schema/probe
and deterministic tool-call helpers. It does not mutate the lead Codex/Claude
thread, goal, tool list, prompt, or sandbox. A real Codex/Claude MCP server
registration remains operator setup and is reported separately by probe output.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .bridge import BRIDGE_MCP_TOOLS
from .bridge_host import (
    BridgeHostError,
    create_bridge_worker,
    ingest_worker_report,
    materialize_bridge_host,
    send_worker_message,
)
from .errors import CollabError


class LeadCliMcpError(CollabError):
    """Raised when a Phase 10 MCP-style bridge request is invalid."""

    error_code = "COLLAB_LEAD_CLI_MCP_INVALID_INPUT"


_TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "create_worker": {
        "type": "object",
        "required": ["worker_id", "agent", "initial_prompt"],
        "properties": {
            "worker_id": {"type": "string"},
            "agent": {"type": "string"},
            "initial_prompt": {"type": "string"},
            "dispatch_id": {"type": "string"},
            "role": {"type": "string"},
            "runtime_adapter": {"type": "string", "default": "operator_command"},
            "focus": {"type": "boolean", "default": False},
        },
    },
    "send_to_worker": {
        "type": "object",
        "required": ["worker_id", "message"],
        "properties": {"worker_id": {"type": "string"}, "message": {"type": "string"}, "now": {"type": "string"}},
    },
    "worker_status": {
        "type": "object",
        "properties": {"worker_id": {"type": "string"}},
    },
    "read_worker": {
        "type": "object",
        "required": ["worker_id"],
        "properties": {"worker_id": {"type": "string"}},
    },
    "ingest_worker_report": {
        "type": "object",
        "required": ["worker_id", "report"],
        "properties": {
            "worker_id": {"type": "string"},
            "report": {"type": "string"},
            "status": {"type": "string", "default": "done"},
            "now": {"type": "string"},
        },
    },
}
_MUTATING_TOOLS = {"create_worker", "send_to_worker", "ingest_worker_report"}


def build_lead_cli_mcp_schema() -> dict[str, Any]:
    """Return MCP-style tool declarations for the lead CLI bridge."""

    return {
        "schema_version": 1,
        "kind": "collab_lead_cli_mcp_schema",
        "phase": 10,
        "lead_cli_boundary": {
            "wraps_or_replaces_lead_cli": False,
            "mutates_lead_thread_goal_or_tools": False,
            "mutates_lead_prompt_or_sandbox": False,
        },
        "server": {
            "name": "global-memory-collab-bridge",
            "transport": "operator_configured_mcp_or_cli_probe",
            "real_mcp_server_verified": False,
        },
        "tools": [
            {
                "name": tool.name,
                "description": tool.purpose,
                "input_schema": _TOOL_INPUT_SCHEMAS[tool.name],
                "mutates": tool.mutates,
                "requires_approval": tool.requires_approval,
            }
            for tool in BRIDGE_MCP_TOOLS
        ],
    }


def probe_lead_cli_mcp(session: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Probe the bridge-side MCP surface without claiming Codex/Claude registration."""

    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "collab_lead_cli_mcp_probe",
        "phase": 10,
        "bridge_tools_available": True,
        "tool_names": [tool.name for tool in BRIDGE_MCP_TOOLS],
        "lead_cli_wrapped": False,
        "mutates_lead_thread_goal_or_tools": False,
        "real_mcp_server_verified": False,
        "fallback": "action_card_or_cli_call",
    }
    if session is not None:
        try:
            model = materialize_bridge_host(session)
        except BridgeHostError as exc:
            raise LeadCliMcpError(f"invalid bridge host session: {exc}") from exc
        payload["events_loadable"] = True
        payload["materialized_summary"] = model.get("summary", {})
    return payload


def call_bridge_tool(session: Mapping[str, Any], tool_name: str, arguments: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Apply a bridge tool call to a session and return result/session/update flag."""

    tool = _require_tool(tool_name)
    args = _require_args(arguments)
    event_log_updated = tool in _MUTATING_TOOLS
    try:
        if tool == "create_worker":
            session = create_bridge_worker(
                session,
                worker_id=_required_text(args, "worker_id"),
                agent=_required_text(args, "agent"),
                initial_prompt=_required_text(args, "initial_prompt"),
                dispatch_id=_optional_text(args, "dispatch_id"),
                role=_optional_text(args, "role"),
                runtime_adapter=_optional_text(args, "runtime_adapter") or "operator_command",
                focus=bool(args.get("focus", False)),
            )
            result = {"worker_id": _required_text(args, "worker_id"), "status": "created"}
        elif tool == "send_to_worker":
            session = send_worker_message(session, _required_text(args, "worker_id"), _required_text(args, "message"), now=_optional_text(args, "now"))
            result = {"worker_id": _required_text(args, "worker_id"), "status": "message_sent"}
        elif tool == "ingest_worker_report":
            session = ingest_worker_report(
                session,
                _required_text(args, "worker_id"),
                _required_text(args, "report"),
                status=_optional_text(args, "status") or "done",
                now=_optional_text(args, "now"),
            )
            result = {"worker_id": _required_text(args, "worker_id"), "status": "report_ingested"}
        elif tool == "worker_status":
            result = _worker_status(materialize_bridge_host(session), _optional_text(args, "worker_id"))
        elif tool == "read_worker":
            result = _read_worker(session, _required_text(args, "worker_id"))
        else:  # pragma: no cover - _require_tool guards this
            raise LeadCliMcpError(f"unsupported bridge tool: {tool}")
    except BridgeHostError as exc:
        raise LeadCliMcpError(str(exc)) from exc
    return _call_payload(tool, result, session, event_log_updated), dict(session), event_log_updated


def load_args_json(value: str | Path) -> dict[str, Any]:
    """Load tool arguments from an inline JSON object or a file path."""

    raw = str(value)
    if raw.strip().startswith("{"):
        text = raw
    else:
        try:
            text = Path(raw).read_text(encoding="utf-8")
        except OSError as exc:
            raise LeadCliMcpError(f"failed to read args JSON {raw}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LeadCliMcpError(f"args JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise LeadCliMcpError("args JSON root must be an object")
    return payload


def dumps_lead_cli_mcp_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _call_payload(tool: str, result: Mapping[str, Any], session: Mapping[str, Any], event_log_updated: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "collab_lead_cli_mcp_call_result",
        "phase": 10,
        "tool": tool,
        "ok": True,
        "event_log_updated": event_log_updated,
        "lead_cli_wrapped": False,
        "real_mcp_server_verified": False,
        "result": dict(result),
        "materialized": materialize_bridge_host(session),
    }


def _worker_status(model: Mapping[str, Any], worker_id: str | None) -> dict[str, Any]:
    rows = model.get("worker_rows", [])
    if worker_id:
        for row in rows:
            if isinstance(row, Mapping) and row.get("worker_id") == worker_id:
                return {"worker": dict(row)}
        raise LeadCliMcpError(f"unknown worker_id: {worker_id}")
    return {"workers": [dict(row) for row in rows if isinstance(row, Mapping)], "summary": dict(model.get("summary", {}))}


def _read_worker(session: Mapping[str, Any], worker_id: str) -> dict[str, Any]:
    for worker in session.get("workers", []):
        if isinstance(worker, Mapping) and worker.get("worker_id") == worker_id:
            return {"worker": dict(worker)}
    raise LeadCliMcpError(f"unknown worker_id: {worker_id}")


def _require_tool(tool_name: str) -> str:
    tool = str(tool_name or "").strip()
    valid = {item.name for item in BRIDGE_MCP_TOOLS}
    if tool not in valid:
        raise LeadCliMcpError(f"tool must be one of {sorted(valid)}")
    return tool


def _require_args(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(arguments, Mapping):
        raise LeadCliMcpError("arguments must be an object")
    return arguments


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = _optional_text(mapping, field)
    if not value:
        raise LeadCliMcpError(f"{field} is required")
    return value


def _optional_text(mapping: Mapping[str, Any], field: str) -> str | None:
    value = mapping.get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
