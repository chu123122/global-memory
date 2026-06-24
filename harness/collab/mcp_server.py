"""Phase 15 stdio MCP server for the standalone collab bridge.

The Phase 10 module exposed an MCP-style surface. This module is a real
line-delimited JSON-RPC stdio server implementing the MCP initialize,
tools/list, and tools/call methods over that surface.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, TextIO

from .bridge_host import BridgeHostError, load_session_events, save_session_events
from .errors import CollabError
from .mcp_bridge import LeadCliMcpError, build_lead_cli_mcp_schema, call_bridge_tool, probe_lead_cli_mcp


class RealMcpServerError(CollabError):
    """Raised when the Phase 15 MCP server receives invalid input."""

    error_code = "COLLAB_REAL_MCP_SERVER_INVALID_INPUT"


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "global-memory-collab-bridge"


def build_mcp_server_config(events_path: str | Path, *, python_executable: str | None = None) -> dict[str, Any]:
    """Return non-persistent config snippets for Codex/Claude MCP registration."""

    py = python_executable or sys.executable
    script = str(Path(__file__).resolve().parents[1] / "scripts" / "collab_mcp_server.py")
    events = str(events_path)
    return {
        "schema_version": 1,
        "kind": "collab_real_mcp_server_config",
        "phase": 15,
        "server_name": SERVER_NAME,
        "transport": "stdio",
        "command": py,
        "args": [script, "serve", "--events", events],
        "codex_config_toml": f'[mcp_servers.{SERVER_NAME}]\ncommand = {json.dumps(py)}\nargs = {json.dumps([script, "serve", "--events", events])}\n',
        "claude_mcp_add_json": {"type": "stdio", "command": py, "args": [script, "serve", "--events", events]},
        "codex_exec_probe_prompt": "Use the worker_status MCP tool from global-memory-collab-bridge. If it returns workers, reply exactly MCP_TOOL_OK.",
        "does_not_persist_config_by_itself": True,
    }


def handle_mcp_request(request: Mapping[str, Any], *, events_path: str | Path | None = None) -> dict[str, Any] | None:
    """Handle a single JSON-RPC MCP request."""

    method = str(request.get("method") or "")
    req_id = request.get("id")
    if method.startswith("notifications/"):
        return None
    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
            }
        elif method == "tools/list":
            result = {"tools": _mcp_tools()}
        elif method == "tools/call":
            params = request.get("params") or {}
            if not isinstance(params, Mapping):
                raise RealMcpServerError("params must be an object")
            result = _call_tool(params, events_path=events_path)
        else:
            return _error(req_id, -32601, f"method not found: {method}")
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    except Exception as exc:
        return _error(req_id, -32000, str(exc))


def run_stdio_server(events_path: str | Path, *, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> int:
    """Run the line-delimited JSON-RPC stdio server."""

    instream = input_stream or sys.stdin
    outstream = output_stream or sys.stdout
    for line in instream:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, Mapping):
                raise RealMcpServerError("request must be an object")
            response = handle_mcp_request(request, events_path=events_path)
        except Exception as exc:
            response = _error(None, -32700, str(exc))
        if response is not None:
            outstream.write(json.dumps(response, ensure_ascii=False) + "\n")
            outstream.flush()
    return 0


def run_mcp_self_test(events_path: str | Path) -> dict[str, Any]:
    """Exercise initialize/tools/list/tools/call against the real server handler."""

    init = handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "self-test"}}}, events_path=events_path)
    tools = handle_mcp_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, events_path=events_path)
    call = handle_mcp_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "worker_status", "arguments": {}}}, events_path=events_path)
    mutating = handle_mcp_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "send_to_worker", "arguments": {"worker_id": "worker-01-find", "message": "phase15 self-test"}}}, events_path=events_path)
    ok = all(item and "result" in item for item in [init, tools, call, mutating])
    return {
        "schema_version": 1,
        "kind": "collab_real_mcp_server_probe",
        "phase": 15,
        "real_mcp_server_verified": ok,
        "transport": "stdio_jsonrpc",
        "server_name": SERVER_NAME,
        "initialize_ok": bool(init and "result" in init),
        "tools_list_ok": bool(tools and "result" in tools),
        "tool_call_ok": bool(call and "result" in call),
        "mutating_tool_call_ok": bool(mutating and "result" in mutating),
        "tool_names": [tool["name"] for tool in _mcp_tools()],
        "sample_call": call,
        "sample_mutating_call": mutating,
    }



def build_codex_mcp_exec_probe_command(
    events_path: str | Path,
    *,
    workdir: str | Path,
    output_file: str | Path,
    python_executable: str | None = None,
    prompt: str | None = None,
    approval_policy: str = "never",
) -> dict[str, Any]:
    """Return a reproducible Codex exec command for a read-only MCP approval probe."""

    config = build_mcp_server_config(events_path, python_executable=python_executable)
    py = config["command"]
    args = config["args"]
    prompt_text = prompt or config["codex_exec_probe_prompt"]
    command = [
        "codex",
        "-a",
        approval_policy,
        "exec",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--ephemeral",
        "-C",
        str(workdir),
        "-s",
        "read-only",
        "-o",
        str(output_file),
        "-c",
        f"mcp_servers.{SERVER_NAME}.command='{py}'",
        "-c",
        f"mcp_servers.{SERVER_NAME}.args={json.dumps(args)}",
        prompt_text,
    ]
    return {
        "schema_version": 1,
        "kind": "collab_codex_mcp_exec_probe_command",
        "phase": 19,
        "server_name": SERVER_NAME,
        "tool": "worker_status",
        "approval_policy": approval_policy,
        "command": command,
        "prompt": prompt_text,
        "expected_marker": "MCP_TOOL_OK",
        "does_not_persist_config": True,
    }


def classify_codex_mcp_exec_probe(*, stdout: str = "", stderr: str = "", output_text: str = "") -> dict[str, Any]:
    """Classify Codex exec MCP tool-call probe output."""

    merged = "\n".join([stdout or "", stderr or "", output_text or ""])
    marker = "MCP_TOOL_OK" in merged
    cancelled = "user cancelled MCP tool call" in merged or "MCP 工具调用被取消" in merged
    started = "mcp: global-memory-collab-bridge/worker_status started" in merged or "worker_status started" in merged
    failed = "mcp: global-memory-collab-bridge/worker_status (failed)" in merged or "worker_status (failed)" in merged
    if marker:
        status = "ok"
        reason = "Codex exec called read-only MCP tool and returned expected marker"
    elif cancelled:
        status = "approval_cancelled"
        reason = "Codex exec attempted the MCP tool call, but noninteractive approval cancelled it"
    elif started and failed:
        status = "tool_failed"
        reason = "Codex exec started the MCP tool but it failed before returning marker"
    elif started:
        status = "tool_started_no_marker"
        reason = "Codex exec started the MCP tool but final marker was absent"
    else:
        status = "not_called"
        reason = "No evidence that Codex exec called worker_status"
    return {
        "schema_version": 1,
        "kind": "collab_codex_mcp_exec_probe_classification",
        "phase": 19,
        "server_name": SERVER_NAME,
        "tool": "worker_status",
        "status": status,
        "reason": reason,
        "expected_marker_found": marker,
        "tool_started": started,
        "approval_cancelled": cancelled,
        "stdout_excerpt": (stdout or "").strip()[:500],
        "stderr_excerpt": (stderr or "").strip()[:500],
        "output_excerpt": (output_text or "").strip()[:500],
    }

def dumps_mcp_server_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _mcp_tools() -> list[dict[str, Any]]:
    schema = build_lead_cli_mcp_schema()
    tools = []
    for tool in schema["tools"]:
        name = tool["name"]
        tools.append({
            "name": name,
            "description": tool["description"],
            "inputSchema": tool["input_schema"],
            "annotations": _tool_annotations(name),
        })
    return tools


def _tool_annotations(name: str) -> dict[str, Any]:
    read_only = name in {"worker_status", "read_worker"}
    mutating = name in {"create_worker", "send_to_worker", "ingest_worker_report"}
    return {
        "title": name.replace("_", " ").title(),
        "readOnlyHint": read_only,
        "destructiveHint": False,
        "idempotentHint": read_only,
        "openWorldHint": False,
        "requiresApprovalHint": mutating,
    }


def _call_tool(params: Mapping[str, Any], *, events_path: str | Path | None) -> dict[str, Any]:
    tool = str(params.get("name") or "").strip()
    args = params.get("arguments") or {}
    if not isinstance(args, Mapping):
        raise RealMcpServerError("arguments must be an object")
    if tool == "collab_probe":
        payload = probe_lead_cli_mcp(_load_session(events_path) if events_path else None)
        return _text_result(payload)
    if not events_path:
        raise RealMcpServerError("events path is required for bridge tool calls")
    session = _load_session(events_path)
    try:
        payload, session, updated = call_bridge_tool(session, tool, args)
    except LeadCliMcpError as exc:
        raise RealMcpServerError(str(exc)) from exc
    if updated:
        save_session_events(session, events_path)
    payload = dict(payload)
    payload["real_mcp_server_verified"] = True
    payload["mcp_transport"] = "stdio_jsonrpc"
    return _text_result(payload)


def _text_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(dict(payload), ensure_ascii=False, indent=2)}], "isError": False}


def _load_session(events_path: str | Path | None) -> dict[str, Any]:
    if not events_path:
        raise RealMcpServerError("events path is required")
    try:
        return load_session_events(events_path)
    except BridgeHostError as exc:
        raise RealMcpServerError(str(exc)) from exc


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
