"""Build one dry-run dispatch packet from a collab replay runbook."""
from __future__ import annotations

import json
from typing import Any, Mapping

class DispatchError(ValueError):
    """Raised when a dry-run dispatch packet cannot be selected."""


def build_dispatch_packet(
    runbook: Mapping[str, Any],
    *,
    dispatch_id: str | None = None,
) -> dict[str, Any]:
    """Select one replay action and return a dry-run dispatch packet.

    The packet is data for the lead to inspect/copy. It never executes runtime
    tools and always keeps ``dry_run`` true.
    """

    actions = runbook.get("actions")
    if not isinstance(actions, list):
        raise DispatchError("runbook.actions must be a list")
    if not actions:
        raise DispatchError("runbook has no available actions")

    selected = None
    if dispatch_id:
        for action in actions:
            if isinstance(action, Mapping) and action.get("dispatch_id") == dispatch_id:
                selected = action
                break
        if selected is None:
            raise DispatchError(f"dispatch_id not available in runbook actions: {dispatch_id}")
    else:
        first = actions[0]
        if not isinstance(first, Mapping):
            raise DispatchError("runbook action must be an object")
        selected = first

    return _packet(runbook, selected)


def render_dispatch_packet_markdown(packet: Mapping[str, Any]) -> str:
    """Render a dry-run dispatch packet for lead use."""

    lines = [
        "# Collaboration Dispatch Packet",
        "",
        f"Workflow: `{packet['workflow']}`",
        f"Plan ID: `{packet['plan_id']}`",
        f"Dispatch: `{packet['dispatch_id']}`",
        f"Agent: `{packet['agent']}`",
        f"Adapter: `{packet['adapter']}`",
        f"Dry run: `{str(packet['dry_run']).lower()}`",
        "",
        "## Runtime payload",
        "",
        "```json",
        json.dumps(packet["runtime_payload"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## State update commands",
    ]
    for label, command in packet.get("state_update_commands", {}).items():
        lines.extend(["", f"- {label}:", "", "```powershell", command, "```"])
    lines.extend(["", "## Worker prompt", "", "```text", packet["prompt"], "```"])
    return "\n".join(lines).rstrip() + "\n"


def dumps_dispatch_packet_json(packet: Mapping[str, Any]) -> str:
    """Serialize a dispatch packet with stable formatting."""

    return json.dumps(packet, ensure_ascii=False, indent=2) + "\n"


def _packet(runbook: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
    runtime_payload = action.get("adapter_payload")
    if not isinstance(runtime_payload, Mapping):
        raise DispatchError("action.adapter_payload must be an object")
    if runtime_payload.get("spawns_process") is not False:
        raise DispatchError("dispatch packet requires non-spawning adapter payload")
    return {
        "schema_version": 1,
        "kind": "collab_dispatch_packet",
        "dry_run": True,
        "workflow": _required_text(runbook, "workflow"),
        "plan_id": _required_text(runbook, "plan_id"),
        "state_path": runbook.get("state_path"),
        "dispatch_id": _required_text(action, "dispatch_id"),
        "agent": _required_text(action, "agent"),
        "status": _required_text(action, "status"),
        "adapter": _required_text(action, "adapter"),
        "spawns_process": False,
        "runtime_tool": action.get("tool"),
        "runtime_payload": dict(runtime_payload),
        "state_update_commands": dict(action.get("state_update_commands", {})),
        "prompt": _required_text(action, "prompt"),
        "instructions": [
            "Inspect the runtime_payload and prompt before using any runtime tool.",
            "If you dispatch it manually, immediately record progress with the matching collab_state.py command.",
            "Do not treat worker output as verified until the lead checks decisive evidence.",
        ],
    }


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = str(mapping.get(field, "")).strip()
    if not value:
        raise DispatchError(f"{field} is required")
    return value
