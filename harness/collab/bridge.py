"""Standalone collaboration bridge contracts.

The bridge is a control plane for collaboration. It may own worker runtime
processes once an operator or MCP call explicitly asks for a worker, but it
must not wrap or replace the user's lead Codex/Claude CLI thread.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import CollabError
from .replay import load_plan


class BridgeError(CollabError):
    """Raised when standalone bridge inputs are invalid."""

    error_code = "COLLAB_BRIDGE_INVALID_INPUT"


@dataclass(frozen=True)
class BridgeTool:
    """Stable MCP-style tool surface exposed by the standalone bridge."""

    name: str
    purpose: str
    mutates: str
    requires_approval: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "mutates": self.mutates,
            "requires_approval": self.requires_approval,
        }


BRIDGE_MCP_TOOLS: tuple[BridgeTool, ...] = (
    BridgeTool(
        name="create_worker",
        purpose="Create a bridge-owned worker session from an explicit dispatch prompt.",
        mutates="worker_runtime,event_store",
        requires_approval=True,
    ),
    BridgeTool(
        name="send_to_worker",
        purpose="Append a user/lead message to an existing worker and enqueue delivery.",
        mutates="message_outbox,event_store",
        requires_approval=True,
    ),
    BridgeTool(
        name="worker_status",
        purpose="Read worker lifecycle, queue, and last-seen report state.",
        mutates="none",
        requires_approval=False,
    ),
    BridgeTool(
        name="read_worker",
        purpose="Read worker transcript/report artifacts without changing runtime state.",
        mutates="none",
        requires_approval=False,
    ),
    BridgeTool(
        name="ingest_worker_report",
        purpose="Record a worker report pointer or pasted report into the event store.",
        mutates="event_store,materialized_state",
        requires_approval=False,
    ),
)


def build_standalone_bridge_spec() -> dict[str, Any]:
    """Return the machine-readable standalone bridge boundary/spec."""

    return {
        "schema_version": 1,
        "kind": "collab_standalone_bridge_spec",
        "goal": "Provide a standalone collab bridge + UI without degrading or replacing the lead Codex/Claude CLI runtime.",
        "lead_cli_boundary": {
            "wraps_or_replaces_lead_cli": False,
            "mutates_lead_thread_goal_or_tools": False,
            "mutates_lead_prompt_or_sandbox": False,
            "allowed_integration": "optional MCP/tools or manual action cards; the lead CLI remains authoritative for its own thread.",
        },
        "control_plane": {
            "owns_worker_runtime": True,
            "owns_event_store": True,
            "owns_message_router": True,
            "owns_ui_projection": True,
            "owns_lead_agent_loop": False,
            "owns_lead_thread_lifecycle": False,
        },
        "runtime_policy": {
            "worker_processes_may_be_spawned": True,
            "spawns_process_during_spec_or_blueprint_generation": False,
            "spawn_requires": [
                "explicit operator action or MCP create_worker call",
                "configured worker command adapter",
                "recorded event log entry",
            ],
            "manual_fallback_is_not_real_lifecycle": True,
        },
        "mcp_tool_surface": [tool.to_dict() for tool in BRIDGE_MCP_TOOLS],
        "capability_matrix": _capability_matrix(),
        "state_contract": {
            "event_log": "append-only JSONL",
            "materialized_state": "deterministic reducer output",
            "correlation_keys": ["workflow_id", "worker_id", "dispatch_id", "message_id"],
            "recovery": "replay event log, then surface stale/retry/requeue actions",
        },
        "xdmaker_boundary": {
            "copy": ["worker focus UX", "create/send/read/report semantics", "split-view information architecture"],
            "adapter": ["Orca bridge tool semantics", "worker report loop"],
            "replace": ["Electron/localDb/session host", "Codex app-server ownership", "product login/update shell"],
            "exclude": ["lead Codex/Claude thread management", "goal/tool mutation in the lead CLI", "XDMaker branding/account dependencies"],
        },
    }


def build_worker_launch_blueprint(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Build deferred worker launch specs from a dispatch plan.

    This is executable *shape*, not execution: it never starts a process. The
    future bridge host can consume this blueprint from create_worker or UI flows.
    """

    _validate_plan(plan)
    workers = []
    for dispatch in plan["dispatches"]:
        if not isinstance(dispatch, Mapping):
            raise BridgeError("plan.dispatches items must be objects")
        workers.append(_worker_spec(dispatch))
    return {
        "schema_version": 1,
        "kind": "collab_worker_launch_blueprint",
        "workflow": _text(plan.get("workflow")),
        "plan_id": _text(plan.get("plan_id")),
        "spawns_process_now": False,
        "launch_policy": "deferred_explicit_operator_or_mcp_call",
        "workers": workers,
    }


def build_standalone_bridge_bundle(plan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return spec plus optional worker launch blueprint."""

    bundle: dict[str, Any] = {
        "schema_version": 1,
        "kind": "collab_standalone_bridge_bundle",
        "spec": build_standalone_bridge_spec(),
    }
    if plan is not None:
        bundle["worker_launch_blueprint"] = build_worker_launch_blueprint(plan)
    return bundle


def load_bridge_plan(path: str | Path) -> dict[str, Any]:
    """Load a plan with bridge-specific stable error wrapping."""

    try:
        return load_plan(path)
    except Exception as exc:  # noqa: BLE001 - stable CLI contract wraps all load errors
        raise BridgeError(str(exc)) from exc


def dumps_bridge_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def render_bridge_markdown(bundle: Mapping[str, Any]) -> str:
    """Render deterministic Markdown for operator review."""

    spec = bundle.get("spec", {}) if isinstance(bundle.get("spec"), Mapping) else {}
    lead = spec.get("lead_cli_boundary", {}) if isinstance(spec.get("lead_cli_boundary"), Mapping) else {}
    control = spec.get("control_plane", {}) if isinstance(spec.get("control_plane"), Mapping) else {}
    runtime = spec.get("runtime_policy", {}) if isinstance(spec.get("runtime_policy"), Mapping) else {}
    lines = [
        "# Standalone Collaboration Bridge",
        "",
        f"wraps_or_replaces_lead_cli: `{str(lead.get('wraps_or_replaces_lead_cli')).lower()}`",
        f"mutates_lead_thread_goal_or_tools: `{str(lead.get('mutates_lead_thread_goal_or_tools')).lower()}`",
        f"owns_worker_runtime: `{str(control.get('owns_worker_runtime')).lower()}`",
        f"spawns_process_during_spec_or_blueprint_generation: `{str(runtime.get('spawns_process_during_spec_or_blueprint_generation')).lower()}`",
        "",
        "## MCP Tool Surface",
    ]
    for tool in spec.get("mcp_tool_surface", []):
        lines.append(f"- `{tool['name']}`: {tool['purpose']} (mutates: {tool['mutates']})")
    lines.extend(["", "## Capability Matrix"])
    for entry in spec.get("capability_matrix", []):
        lines.append(f"- `{entry['adapter']}` -> `{entry['capability_level']}`: {entry['meaning']}")
    blueprint = bundle.get("worker_launch_blueprint")
    if isinstance(blueprint, Mapping):
        lines.extend(["", "## Worker Launch Blueprint"])
        lines.append(f"plan_id: `{blueprint.get('plan_id')}`")
        lines.append(f"spawns_process_now: `{str(blueprint.get('spawns_process_now')).lower()}`")
        for worker in blueprint.get("workers", []):
            lines.append(f"- `{worker['dispatch_id']}` {worker['agent']} via `{worker['runtime_adapter']}`")
    return "\n".join(lines).rstrip() + "\n"


def _capability_matrix() -> list[dict[str, Any]]:
    return [
        {
            "adapter": "manual",
            "capability_level": "action_card_only",
            "meaning": "Human copies prompts/reports; useful as fallback only, not a real worker lifecycle.",
            "real_worker_lifecycle": False,
        },
        {
            "adapter": "orca",
            "capability_level": "real_worker_api",
            "meaning": "Existing Orca/XDMaker-style bridge exposes create/send/status/read worker APIs.",
            "real_worker_lifecycle": True,
        },
        {
            "adapter": "standalone-codex-worker",
            "capability_level": "standalone_worker_runtime",
            "meaning": "Bridge-owned worker process may run Codex as a worker; the lead Codex CLI is not wrapped.",
            "real_worker_lifecycle": True,
        },
        {
            "adapter": "standalone-claude-worker",
            "capability_level": "standalone_worker_runtime",
            "meaning": "Bridge-owned worker process may run Claude Code as a worker; the lead Claude CLI is not wrapped.",
            "real_worker_lifecycle": True,
        },
        {
            "adapter": "lead-cli-mcp",
            "capability_level": "bridge_available",
            "meaning": "Lead CLI can call bridge MCP tools if configured; otherwise UI/manual action cards remain available.",
            "real_worker_lifecycle": True,
        },
    ]


def _worker_spec(dispatch: Mapping[str, Any]) -> dict[str, Any]:
    model = _text(dispatch.get("model"))
    return {
        "dispatch_id": _required_text(dispatch, "id"),
        "agent": _required_text(dispatch, "agent"),
        "role": _text(dispatch.get("role")),
        "model": model,
        "reasoning_effort": _text(dispatch.get("reasoning_effort")),
        "runtime_adapter": _standalone_adapter_for_model(model),
        "initial_prompt": _required_text(dispatch, "prompt"),
        "spawn_command": "operator_configured",
        "spawns_process_now": False,
    }


def _standalone_adapter_for_model(model: str) -> str:
    return "standalone-claude-worker" if "claude" in model.lower() else "standalone-codex-worker"


def _validate_plan(plan: Mapping[str, Any]) -> None:
    if not _text(plan.get("plan_id")):
        raise BridgeError("plan.plan_id is required")
    if not isinstance(plan.get("dispatches"), list):
        raise BridgeError("plan.dispatches must be a list")


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = _text(mapping.get(field))
    if not value:
        raise BridgeError(f"{field} is required")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()
