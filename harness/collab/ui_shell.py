"""Deterministic optional UI-shell view model for collab artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .errors import CollabError
from .queue import CollabQueue, load_queue, summarize_queue
from .recover import load_json_object
from .replay import load_plan
from .state import CollabState, load_state, summarize_state


class UiShellError(CollabError):
    """Raised when UI shell input artifacts are invalid."""

    error_code = "COLLAB_UI_SHELL_INVALID_INPUT"


INFORMATION_ARCHITECTURE = (
    {
        "id": "plan",
        "title": "Plan overview",
        "shows": ("workflow", "plan_id", "intent", "agents", "dispatch order"),
        "source": "plan.json",
    },
    {
        "id": "state",
        "title": "State timeline",
        "shows": ("dispatch status", "worker_id", "session_id", "updated_at", "report pointer"),
        "source": "state.json",
    },
    {
        "id": "queue",
        "title": "Queue and leases",
        "shows": ("queue status", "lease_owner", "lease_id", "attempts", "labels"),
        "source": "queue.json",
    },
    {
        "id": "recover",
        "title": "Recovery and errors",
        "shows": ("verdict", "error_code", "issue severity", "advisory actions"),
        "source": "recover.json or computed recovery report",
    },
    {
        "id": "dispatch",
        "title": "Selected dispatch packet",
        "shows": ("runtime payload", "worker prompt", "state update commands", "spawns_process flag"),
        "source": "dispatch.json",
    },
    {
        "id": "report",
        "title": "Worker reports",
        "shows": ("evidence pointers", "operator notes", "done/blocked/error summaries"),
        "source": "state.report and optional report map",
    },
)

XDMAKER_BOUNDARY = {
    "reuse_concepts": [
        {
            "name": "CollaborationModeToggle",
            "reuse": "concept only",
            "reason": "Useful as a first-screen switch between solo and collaboration views; do not copy product wiring or branding.",
        },
        {
            "name": "OrcaSplitView",
            "reuse": "layout pattern only",
            "reason": "Plan/list on the left and selected dispatch/recover details on the right maps well to Phase 4 artifacts.",
        },
    ],
    "replace_or_avoid": [
        "Electron shell, login/update/brand surfaces, localDb schema, process spawning, and XDMaker-specific runtime adapters.",
        "Any UI action that mutates state without calling the explicit state/queue CLI or equivalent reviewed adapter.",
    ],
}


def build_ui_shell_model(
    *,
    plan: Mapping[str, Any],
    state: CollabState | None = None,
    queue: CollabQueue | None = None,
    recovery: Mapping[str, Any] | None = None,
    dispatch_packet: Mapping[str, Any] | None = None,
    report_pointers: Mapping[str, str] | None = None,
    artifact_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a stable UI view model without starting workers or mutating artifacts."""

    _validate_plan(plan)
    _validate_dispatch_packet(dispatch_packet)
    report_pointers = {str(k): str(v) for k, v in (report_pointers or {}).items() if str(k).strip() and str(v).strip()}
    artifact_paths = {str(k): str(v) for k, v in (artifact_paths or {}).items() if str(v).strip()}
    dispatch_rows = _dispatch_rows(plan, state, queue, report_pointers)
    recovery_issues = list(recovery.get("issues", [])) if isinstance(recovery, Mapping) else []
    recovery_actions = list(recovery.get("actions", [])) if isinstance(recovery, Mapping) else []

    return {
        "schema_version": 1,
        "kind": "collab_ui_shell_model",
        "contract": {
            "headless": True,
            "optional_ui_shell": True,
            "spawns_process": False,
            "readiness": "experimental",
            "mutation_policy": "UI must call collab_state.py / collab_queue.py or an equivalent reviewed adapter; this model is read-only.",
            "client_manifest_readiness_changed": False,
        },
        "workflow": _text(plan.get("workflow")),
        "plan_id": _text(plan.get("plan_id")),
        "artifact_paths": artifact_paths,
        "artifact_presence": {
            "plan": True,
            "state": state is not None,
            "queue": queue is not None,
            "recover": recovery is not None,
            "dispatch": dispatch_packet is not None,
            "reports": bool(report_pointers),
        },
        "information_architecture": [_section(section) for section in INFORMATION_ARCHITECTURE],
        "xdmaker_boundary": XDMAKER_BOUNDARY,
        "summary": _summary(plan, state, queue, recovery, dispatch_rows),
        "dispatch_rows": dispatch_rows,
        "recovery_panel": {
            "verdict": _text(recovery.get("verdict")) if isinstance(recovery, Mapping) else "not_loaded",
            "issue_count": len(recovery_issues),
            "issues": recovery_issues,
            "actions": recovery_actions,
        },
        "selected_dispatch": _selected_dispatch(dispatch_packet),
        "operator_actions": _operator_actions(dispatch_packet, recovery_actions),
    }


def load_ui_shell_inputs(
    *,
    plan_path: str | Path,
    state_path: str | Path | None = None,
    queue_path: str | Path | None = None,
    recover_path: str | Path | None = None,
    dispatch_path: str | Path | None = None,
) -> tuple[dict[str, Any], CollabState | None, CollabQueue | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Load UI shell artifacts with UI-specific stable errors."""

    try:
        plan = load_plan(plan_path)
        state = load_state(state_path) if state_path else None
        queue = load_queue(queue_path) if queue_path else None
        recovery = load_json_object(recover_path, label="recover") if recover_path else None
        dispatch = load_json_object(dispatch_path, label="dispatch") if dispatch_path else None
    except Exception as exc:
        if isinstance(exc, UiShellError):
            raise
        raise UiShellError(str(exc)) from exc
    return plan, state, queue, recovery, dispatch


def render_ui_shell_markdown(model: Mapping[str, Any]) -> str:
    """Render a deterministic Markdown dashboard from a UI shell model."""

    summary = model.get("summary", {}) if isinstance(model.get("summary"), Mapping) else {}
    contract = model.get("contract", {}) if isinstance(model.get("contract"), Mapping) else {}
    lines = [
        "# Collaboration UI Shell Dashboard",
        "",
        f"Workflow: `{model.get('workflow')}`",
        f"Plan ID: `{model.get('plan_id')}`",
        f"Readiness: `{contract.get('readiness')}`",
        f"headless: `{str(contract.get('headless')).lower()}`",
        f"spawns_process: `{str(contract.get('spawns_process')).lower()}`",
        "",
        "## Summary",
        f"- dispatches: {summary.get('dispatch_count')}",
        f"- loaded artifacts: {', '.join(summary.get('loaded_artifacts', [])) or 'none'}",
        f"- recovery verdict: {summary.get('recovery_verdict')}",
        "",
        "## Information Architecture",
    ]
    for section in model.get("information_architecture", []):
        lines.append(f"- `{section['id']}` {section['title']} - {', '.join(section['shows'])}")
    lines.extend(["", "## Dispatch Board", "", "| dispatch | agent | state | queue | report |", "|---|---|---|---|---|"])
    for row in model.get("dispatch_rows", []):
        lines.append(
            f"| `{row['dispatch_id']}` | {row['agent']} | {row['state_status']} | {row['queue_status']} | {row.get('report_pointer') or ''} |"
        )
    lines.extend(["", "## Recovery Panel"])
    recovery = model.get("recovery_panel", {}) if isinstance(model.get("recovery_panel"), Mapping) else {}
    if not recovery.get("issues"):
        lines.append("- no loaded issues")
    for issue in recovery.get("issues", []):
        lines.append(f"- `{issue.get('error_code')}` {issue.get('message')}")
    lines.extend(["", "## Operator Actions"])
    for action in model.get("operator_actions", []):
        lines.append(f"- `{action['action']}`: {action['description']}")
    lines.extend(["", "## XDMaker Reuse / Replace Boundary"])
    boundary = model.get("xdmaker_boundary", {}) if isinstance(model.get("xdmaker_boundary"), Mapping) else {}
    lines.append("### Reuse concepts")
    for item in boundary.get("reuse_concepts", []):
        lines.append(f"- `{item['name']}`: {item['reuse']} - {item['reason']}")
    lines.append("### Replace or avoid")
    for item in boundary.get("replace_or_avoid", []):
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def dumps_ui_shell_json(model: Mapping[str, Any]) -> str:
    return json.dumps(dict(model), ensure_ascii=False, indent=2) + "\n"


def _validate_plan(plan: Mapping[str, Any]) -> None:
    if not _text(plan.get("plan_id")):
        raise UiShellError("plan.plan_id is required")
    if not isinstance(plan.get("dispatches"), list):
        raise UiShellError("plan.dispatches must be a list")


def _validate_dispatch_packet(packet: Mapping[str, Any] | None) -> None:
    if packet is None:
        return
    payload = packet.get("runtime_payload")
    if isinstance(payload, Mapping) and payload.get("spawns_process") is not False:
        raise UiShellError("dispatch runtime_payload.spawns_process must be false for UI shell")
    if packet.get("spawns_process") not in (None, False):
        raise UiShellError("dispatch spawns_process must be false for UI shell")


def _dispatch_rows(
    plan: Mapping[str, Any],
    state: CollabState | None,
    queue: CollabQueue | None,
    report_pointers: Mapping[str, str],
) -> list[dict[str, Any]]:
    state_by_id = {item.dispatch_id: item for item in state.dispatches} if state else {}
    queue_by_id = {item.dispatch_id: item for item in queue.items} if queue else {}
    rows = []
    for raw in plan.get("dispatches", []):
        if not isinstance(raw, Mapping):
            raise UiShellError("plan dispatch must be an object")
        dispatch_id = _required_text(raw, "id")
        state_item = state_by_id.get(dispatch_id)
        queue_item = queue_by_id.get(dispatch_id)
        report = report_pointers.get(dispatch_id) or (state_item.report if state_item else None) or (queue_item.report if queue_item else None)
        rows.append(
            {
                "dispatch_id": dispatch_id,
                "agent": _required_text(raw, "agent"),
                "adapter": _adapter_name(raw),
                "state_status": state_item.status if state_item else "unknown",
                "queue_status": queue_item.status if queue_item else "unknown",
                "worker_id": state_item.worker_id if state_item else None,
                "session_id": state_item.session_id if state_item else None,
                "lease_owner": queue_item.lease_owner if queue_item else None,
                "lease_id": queue_item.lease_id if queue_item else None,
                "attempts": queue_item.attempts if queue_item else None,
                "labels": list(queue_item.labels) if queue_item else [],
                "report_pointer": report,
                "next_ui_action": _next_ui_action(state_item.status if state_item else "unknown", queue_item.status if queue_item else "unknown"),
            }
        )
    return rows


def _summary(
    plan: Mapping[str, Any],
    state: CollabState | None,
    queue: CollabQueue | None,
    recovery: Mapping[str, Any] | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    loaded = [name for name, present in (("plan", True), ("state", state is not None), ("queue", queue is not None), ("recover", recovery is not None)) if present]
    return {
        "intent": _text(plan.get("intent")),
        "dispatch_count": len(rows),
        "loaded_artifacts": loaded,
        "state_summary": summarize_state(state) if state else None,
        "queue_summary": summarize_queue(queue) if queue else None,
        "recovery_verdict": _text(recovery.get("verdict")) if isinstance(recovery, Mapping) else "not_loaded",
        "blocked_or_error_rows": [row["dispatch_id"] for row in rows if row["state_status"] in {"blocked", "error"} or row["queue_status"] == "error"],
    }


def _selected_dispatch(packet: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if packet is None:
        return None
    return {
        "dispatch_id": _text(packet.get("dispatch_id")),
        "agent": _text(packet.get("agent")),
        "status": _text(packet.get("status")),
        "adapter": _text(packet.get("adapter")),
        "dry_run": packet.get("dry_run") is True,
        "spawns_process": False,
        "state_update_commands": dict(packet.get("state_update_commands", {})) if isinstance(packet.get("state_update_commands"), Mapping) else {},
    }


def _operator_actions(packet: Mapping[str, Any] | None, recovery_actions: list[Any]) -> list[dict[str, Any]]:
    actions = [
        {
            "action": "inspect_artifacts",
            "description": "Review plan/state/queue/recover panels before using any runtime tool.",
            "writes_artifact": False,
        },
        {
            "action": "record_state_or_queue_update",
            "description": "Use collab_state.py or collab_queue.py after manual worker progress; the UI shell model is read-only.",
            "writes_artifact": True,
        },
    ]
    if packet is not None:
        actions.append(
            {
                "action": "copy_dry_run_dispatch_packet",
                "description": "Copy the selected packet into an already-authorized runtime tool; do not spawn from this UI shell.",
                "writes_artifact": False,
            }
        )
    for action in recovery_actions:
        if isinstance(action, Mapping):
            actions.append(
                {
                    "action": f"recover:{_text(action.get('action'))}",
                    "description": f"Advisory recovery action for {action.get('dispatch_id') or action.get('target')}; operator must apply explicitly.",
                    "writes_artifact": False,
                }
            )
    return actions


def _next_ui_action(state_status: str, queue_status: str) -> str:
    if state_status == "done" or queue_status == "done":
        return "review_report"
    if state_status in {"blocked", "error"} or queue_status == "error":
        return "inspect_recovery"
    if queue_status == "leased" or state_status == "running":
        return "monitor_or_recover_if_stale"
    if queue_status == "queued" or state_status in {"pending", "unknown"}:
        return "lease_or_dispatch_manually"
    return "inspect"


def _section(section: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(section.get("id")),
        "title": _text(section.get("title")),
        "shows": list(section.get("shows", [])),
        "source": _text(section.get("source")),
    }


def _adapter_name(dispatch: Mapping[str, Any]) -> str:
    adapter = dispatch.get("adapter")
    if isinstance(adapter, Mapping):
        return _text(adapter.get("name"))
    return "unknown"


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = _text(mapping.get(field))
    if not value:
        raise UiShellError(f"{field} is required")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()
