"""Adapter contract metadata and declarative runtime payloads.

This module deliberately returns data only. It never imports runtime tool
modules, spawns clients, or sends worker messages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AdapterContract:
    """Declarative adapter contract; it never launches a client process."""

    name: str
    payload_kind: str
    tool_hint: str
    spawns_process: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "payload_kind": self.payload_kind,
            "tool_hint": self.tool_hint,
            "spawns_process": self.spawns_process,
            "notes": list(self.notes),
        }


ADAPTER_CONTRACTS: dict[str, AdapterContract] = {
    "codex": AdapterContract(
        name="codex",
        payload_kind="dispatch_plan.codex",
        tool_hint="Use the current Codex/orchestration tool only when the runtime already exposes one.",
        spawns_process=False,
        notes=(
            "Produces deterministic worker prompts and metadata for a Codex lead.",
            "Does not start Codex CLI, alter permissions, or bypass quality gates.",
        ),
    ),
    "claude-code": AdapterContract(
        name="claude-code",
        payload_kind="dispatch_plan.claude_code",
        tool_hint="Use Claude Code Task/Orca tools if the active session provides them.",
        spawns_process=False,
        notes=(
            "Keeps work/quality-gate governance in the prompt payload.",
            "Does not modify hooks, settings, or client lifecycle readiness flags.",
        ),
    ),
    "orca": AdapterContract(
        name="orca",
        payload_kind="dispatch_plan.orca",
        tool_hint="Map each dispatch item to create_worker/send_to_worker style calls when available.",
        spawns_process=False,
        notes=(
            "Uses host-neutral workflow and worker identifiers.",
            "Does not depend on a host UI session id or local database.",
        ),
    ),
    "manual": AdapterContract(
        name="manual",
        payload_kind="dispatch_plan.manual",
        tool_hint="Copy the dispatch prompt to a human-selected worker/runtime.",
        spawns_process=False,
        notes=("Fallback for clients without a delegation tool.",),
    ),
}


def get_adapter_contract(name: str) -> AdapterContract:
    """Return the declarative contract for an adapter name."""

    try:
        return ADAPTER_CONTRACTS[name]
    except KeyError as exc:
        raise KeyError(f"unknown adapter: {name}") from exc


def build_adapter_payload(dispatch: Mapping[str, Any]) -> dict[str, Any]:
    """Build a declarative runtime-shaped payload for one dispatch item.

    The payload can be inspected or copied into a runtime-specific tool call by
    a lead agent. It is not executable by itself and always keeps
    ``spawns_process`` false.
    """

    adapter = _text(dispatch.get("adapter", {}).get("name") if isinstance(dispatch.get("adapter"), Mapping) else "")
    if not adapter:
        adapter = _text(dispatch.get("client", "")) or "manual"
    contract = get_adapter_contract(adapter)
    prompt = _text(dispatch.get("prompt"))
    agent = _text(dispatch.get("agent"))
    role = _text(dispatch.get("role"))
    model = _text(dispatch.get("model"))
    effort = _text(dispatch.get("reasoning_effort"))
    label = _safe_label(agent or role or "worker")

    return {
        "schema_version": 1,
        "kind": "collab_adapter_payload",
        "dispatch_id": _text(dispatch.get("id")),
        "adapter": adapter,
        "agent": agent,
        "role": role,
        "payload_kind": contract.payload_kind,
        "spawns_process": False,
        "requires_runtime_tool": adapter != "manual",
        "tool": _tool_payload(
            adapter=adapter,
            agent=agent,
            role=role,
            model=model,
            effort=effort,
            label=label,
            prompt=prompt,
        ),
        "manual_fallback": {
            "instruction": "Copy this prompt into the chosen worker/runtime if no adapter tool is available.",
            "prompt": prompt,
        },
    }


def build_adapter_payloads(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build runtime-shaped payloads for all dispatches in a plan."""

    dispatches = plan.get("dispatches", [])
    if not isinstance(dispatches, list):
        raise TypeError("plan.dispatches must be a list")
    return [build_adapter_payload(dispatch) for dispatch in dispatches]


def _tool_payload(
    *,
    adapter: str,
    agent: str,
    role: str,
    model: str,
    effort: str,
    label: str,
    prompt: str,
) -> dict[str, Any] | None:
    if adapter == "manual":
        return None
    if adapter == "codex":
        return {
            "name": "spawn_agent",
            "arguments": {
                "agent_type": "worker",
                "message": prompt,
                "reasoning_effort": effort,
                "model": model,
            },
        }
    if adapter == "claude-code":
        return {
            "name": "Task",
            "arguments": {
                "description": f"{agent}: {role}"[:80],
                "prompt": prompt,
                "subagent_type": "general-purpose",
            },
        }
    if adapter == "orca":
        return {
            "name": "create_worker",
            "arguments": {
                "role": agent or role or "worker",
                "agent": _agent_kind_for_model(model),
                "model": model,
                "effort": effort,
                "label": label,
                "initial_task": prompt,
            },
        }
    raise KeyError(f"unknown adapter: {adapter}")


def _agent_kind_for_model(model: str) -> str:
    lowered = model.lower()
    if "claude" in lowered:
        return "claude-code"
    return "codex"


def _safe_label(value: str) -> str:
    chars = [
        ch if ch.isascii() and (ch.isalnum() or ch in {"-", "_"}) else "-"
        for ch in value.strip()
    ]
    label = "".join(chars).strip("-_")
    return (label or "worker")[:32]


def _text(value: Any) -> str:
    return str(value or "").strip()
