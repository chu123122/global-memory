"""Build deterministic collaboration replay/runbook action cards."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .adapters import build_adapter_payload
from .state import CollabState


class ReplayError(ValueError):
    """Raised when a collab replay input is invalid."""


def load_plan(path: str | Path) -> dict[str, Any]:
    """Load a plan JSON file emitted by collab_plan.py."""

    plan_path = Path(path)
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReplayError(f"failed to read plan {plan_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReplayError(f"plan {plan_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReplayError("plan root must be an object")
    if not isinstance(payload.get("dispatches"), list):
        raise ReplayError("plan.dispatches must be a list")
    if not str(payload.get("plan_id", "")).strip():
        raise ReplayError("plan.plan_id is required")
    return payload


def build_replay_runbook(
    plan: Mapping[str, Any],
    *,
    state: CollabState | None = None,
    state_path: str | Path | None = None,
    include_done: bool = False,
    adapter: str | None = None,
) -> dict[str, Any]:
    """Return ordered action cards for pending/non-done dispatches."""

    dispatches = plan.get("dispatches")
    if not isinstance(dispatches, list):
        raise ReplayError("plan.dispatches must be a list")
    plan_id = _text(plan.get("plan_id"))
    if not plan_id:
        raise ReplayError("plan.plan_id is required")
    state_by_id = {
        item.dispatch_id: item
        for item in state.dispatches
    } if state else {}
    if state and state.plan_id != plan_id:
        raise ReplayError(f"state plan_id {state.plan_id!r} does not match plan {plan_id!r}")

    cards: list[dict[str, Any]] = []
    skipped_done = 0
    for raw in dispatches:
        if not isinstance(raw, Mapping):
            raise ReplayError("each dispatch must be an object")
        dispatch_id = _required_text(raw, "id")
        status = state_by_id.get(dispatch_id).status if dispatch_id in state_by_id else "pending"
        if status == "done" and not include_done:
            skipped_done += 1
            continue
        payload = build_adapter_payload(raw)
        if adapter and payload["adapter"] != adapter:
            continue
        cards.append(_action_card(raw, payload, status, state_path))

    return {
        "schema_version": 1,
        "kind": "collab_replay_runbook",
        "workflow": _required_text(plan, "workflow"),
        "plan_id": plan_id,
        "state_path": str(state_path) if state_path else None,
        "include_done": include_done,
        "adapter_filter": adapter,
        "skipped_done": skipped_done,
        "action_count": len(cards),
        "actions": cards,
    }


def render_runbook_markdown(runbook: Mapping[str, Any]) -> str:
    """Render a replay runbook as Markdown for lead inspection."""

    lines = [
        "# Collaboration Replay Runbook",
        "",
        f"Workflow: `{runbook['workflow']}`",
        f"Plan ID: `{runbook['plan_id']}`",
        f"State: `{runbook.get('state_path') or 'none'}`",
        f"Actions: {runbook['action_count']}",
        "",
    ]
    for action in runbook.get("actions", []):
        tool = action.get("tool") or {}
        tool_name = tool.get("name") if isinstance(tool, Mapping) else "manual"
        lines.extend(
            [
                f"## {action['dispatch_id']} · {action['agent']} · {action['status']}",
                "",
                f"- adapter: `{action['adapter']}`",
                f"- runtime tool: `{tool_name}`",
                f"- spawns_process: `{str(action['spawns_process']).lower()}`",
                "",
                "### Runtime payload",
                "",
                "```json",
                json.dumps(action["adapter_payload"], ensure_ascii=False, indent=2),
                "```",
                "",
                "### State update examples",
            ]
        )
        for label, command in action.get("state_update_commands", {}).items():
            lines.extend(["", f"- {label}:", "", "```powershell", command, "```"])
        lines.extend(["", "### Worker prompt", "", "```text", action["prompt"], "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def dumps_runbook_json(runbook: Mapping[str, Any]) -> str:
    """Serialize a runbook with stable formatting."""

    return json.dumps(runbook, ensure_ascii=False, indent=2) + "\n"


def _action_card(
    dispatch: Mapping[str, Any],
    payload: Mapping[str, Any],
    status: str,
    state_path: str | Path | None,
) -> dict[str, Any]:
    dispatch_id = _required_text(dispatch, "id")
    agent = _required_text(dispatch, "agent")
    prompt = _required_text(dispatch, "prompt")
    return {
        "dispatch_id": dispatch_id,
        "agent": agent,
        "status": status,
        "adapter": payload["adapter"],
        "spawns_process": False,
        "tool": payload.get("tool"),
        "adapter_payload": dict(payload),
        "prompt": prompt,
        "state_update_commands": _state_update_commands(state_path, dispatch_id),
    }


def _state_update_commands(state_path: str | Path | None, dispatch_id: str) -> dict[str, str]:
    path = str(state_path) if state_path else "<state.json>"
    base = f"python harness\\scripts\\collab_state.py --state {path} --dispatch-id {dispatch_id}"
    return {
        "mark running": f"{base} --status running --worker-id <worker-id> --session-id <session-id> --json",
        "mark done": f"{base} --status done --report <evidence-pointer> --json",
        "mark blocked": f"{base} --status blocked --report <blocker-summary> --json",
    }


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = _text(mapping.get(field))
    if not value:
        raise ReplayError(f"{field} is required")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()
