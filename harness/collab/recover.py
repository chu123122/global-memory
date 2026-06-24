"""Recovery analysis for collaboration plan/state/queue artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .errors import CollabError
from .queue import CollabQueue, parse_time
from .state import CollabState


class RecoverError(CollabError):
    """Raised when recovery inputs cannot be read or interpreted."""

    error_code = "COLLAB_RECOVER_INVALID_INPUT"


def load_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    artifact_path = Path(path)
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RecoverError(f"failed to read {label} {artifact_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RecoverError(f"{label} {artifact_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RecoverError(f"{label} root must be an object")
    return payload


def build_recovery_report(
    *,
    plan: Mapping[str, Any],
    state: CollabState | None = None,
    state_raw: Mapping[str, Any] | None = None,
    queue: CollabQueue | None = None,
    queue_raw: Mapping[str, Any] | None = None,
    now: str | None = None,
    stale_after_seconds: int = 3600,
) -> dict[str, Any]:
    """Return deterministic recovery warnings and operator actions."""

    now_dt = _parse_now(now)
    issues: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    plan_id = str(plan.get("plan_id", "")).strip()
    plan_dispatch_ids = _plan_dispatch_ids(plan, issues)

    if plan.get("schema_version") != 1:
        _issue(issues, "COLLAB_PLAN_SCHEMA_UNSUPPORTED", "plan schema_version is not 1", severity="block")

    state_dispatch_by_id: dict[str, Any] = {}
    if state_raw is not None and state_raw.get("schema_version") != 1:
        _issue(issues, "COLLAB_STATE_SCHEMA_UNSUPPORTED", "state schema_version is not 1", severity="block")
    if state is not None:
        state_dispatch_by_id = {item.dispatch_id: item for item in state.dispatches}
        if plan_id and state.plan_id != plan_id:
            _issue(
                issues,
                "COLLAB_PLAN_STATE_MISMATCH",
                f"state plan_id {state.plan_id!r} does not match plan {plan_id!r}",
                severity="block",
            )
        _compare_ids(plan_dispatch_ids, set(state_dispatch_by_id), issues, left="plan", right="state")
        for item in state.dispatches:
            if item.status == "running" and _is_stale(item.updated_at, now_dt, stale_after_seconds):
                _issue(
                    issues,
                    "COLLAB_RECOVER_STALE_RUNNING",
                    f"dispatch {item.dispatch_id} is running but stale",
                    dispatch_id=item.dispatch_id,
                )
                actions.append(
                    {
                        "action": "requeue_or_mark_blocked",
                        "target": "state",
                        "dispatch_id": item.dispatch_id,
                        "reason": "running dispatch exceeded stale_after_seconds",
                    }
                )

    queue_item_by_id: dict[str, Any] = {}
    if queue_raw is not None and queue_raw.get("schema_version") != 1:
        _issue(issues, "COLLAB_QUEUE_SCHEMA_UNSUPPORTED", "queue schema_version is not 1", severity="block")
    if queue is not None:
        queue_item_by_id = {item.dispatch_id: item for item in queue.items}
        if plan_id and queue.plan_id != plan_id:
            _issue(
                issues,
                "COLLAB_PLAN_QUEUE_MISMATCH",
                f"queue plan_id {queue.plan_id!r} does not match plan {plan_id!r}",
                severity="block",
            )
        _compare_ids(plan_dispatch_ids, set(queue_item_by_id), issues, left="plan", right="queue")
        for item in queue.items:
            if item.status == "leased" and _is_stale(item.leased_at, now_dt, stale_after_seconds):
                _issue(
                    issues,
                    "COLLAB_QUEUE_STALE_LEASE",
                    f"queue lease for {item.dispatch_id} is stale",
                    dispatch_id=item.dispatch_id,
                    lease_id=item.lease_id,
                )
                actions.append(
                    {
                        "action": "requeue_lease",
                        "target": "queue",
                        "dispatch_id": item.dispatch_id,
                        "lease_id": item.lease_id,
                        "reason": "lease exceeded stale_after_seconds",
                    }
                )

    if state_dispatch_by_id and queue_item_by_id:
        for dispatch_id in sorted(set(state_dispatch_by_id) & set(queue_item_by_id)):
            state_status = state_dispatch_by_id[dispatch_id].status
            queue_status = queue_item_by_id[dispatch_id].status
            if _conflict(state_status, queue_status):
                _issue(
                    issues,
                    "COLLAB_STATE_QUEUE_CONFLICT",
                    f"dispatch {dispatch_id} state={state_status} queue={queue_status}",
                    dispatch_id=dispatch_id,
                )
                actions.append(
                    {
                        "action": "reconcile_state_queue_status",
                        "target": "state+queue",
                        "dispatch_id": dispatch_id,
                        "state_status": state_status,
                        "queue_status": queue_status,
                    }
                )

    return {
        "schema_version": 1,
        "kind": "collab_recovery_report",
        "workflow": str(plan.get("workflow", "")).strip() or None,
        "plan_id": plan_id or None,
        "now": _format_time(now_dt),
        "stale_after_seconds": stale_after_seconds,
        "verdict": "ok" if not issues else "needs_attention",
        "issue_count": len(issues),
        "issues": issues,
        "actions": actions,
    }


def render_recovery_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Collaboration Recovery Report",
        "",
        f"Plan ID: `{report.get('plan_id') or 'unknown'}`",
        f"Verdict: `{report['verdict']}`",
        f"Issues: {report['issue_count']}",
        "",
        "## Issues",
    ]
    if not report.get("issues"):
        lines.append("- none")
    for issue in report.get("issues", []):
        lines.append(f"- `{issue['error_code']}` {issue['message']}")
    lines.extend(["", "## Actions"])
    if not report.get("actions"):
        lines.append("- none")
    for action in report.get("actions", []):
        lines.append(f"- `{action['action']}` target={action.get('target')} dispatch={action.get('dispatch_id')}")
    return "\n".join(lines).rstrip() + "\n"


def dumps_recovery_json(report: Mapping[str, Any]) -> str:
    return json.dumps(dict(report), ensure_ascii=False, indent=2) + "\n"


def _plan_dispatch_ids(plan: Mapping[str, Any], issues: list[dict[str, Any]]) -> set[str]:
    dispatches = plan.get("dispatches")
    if not isinstance(dispatches, list):
        _issue(issues, "COLLAB_PLAN_INVALID", "plan.dispatches must be a list", severity="block")
        return set()
    ids = set()
    for index, item in enumerate(dispatches):
        if not isinstance(item, Mapping):
            _issue(issues, "COLLAB_PLAN_INVALID", f"plan.dispatches[{index}] must be an object", severity="block")
            continue
        dispatch_id = str(item.get("id", "")).strip()
        if dispatch_id:
            ids.add(dispatch_id)
    return ids


def _compare_ids(plan_ids: set[str], other_ids: set[str], issues: list[dict[str, Any]], *, left: str, right: str) -> None:
    missing = sorted(plan_ids - other_ids)
    extra = sorted(other_ids - plan_ids)
    if missing or extra:
        code = "COLLAB_PLAN_STATE_MISMATCH" if right == "state" else "COLLAB_PLAN_QUEUE_MISMATCH"
        _issue(issues, code, f"{left}/{right} dispatch ids differ", severity="block", missing=missing, extra=extra)


def _conflict(state_status: str, queue_status: str) -> bool:
    if state_status == "done" and queue_status != "done":
        return True
    if queue_status == "done" and state_status != "done":
        return True
    if state_status in {"pending", "blocked", "error"} and queue_status == "leased":
        return True
    return False


def _issue(issues: list[dict[str, Any]], error_code: str, message: str, *, severity: str = "warn", **extra: Any) -> None:
    issue = {"error_code": error_code, "severity": severity, "message": message}
    issue.update({key: value for key, value in extra.items() if value is not None})
    issues.append(issue)


def _is_stale(value: str | None, now: datetime, stale_after_seconds: int) -> bool:
    if not value:
        return False
    try:
        then = parse_time(value)
    except Exception:
        return True
    return (now - then).total_seconds() >= stale_after_seconds


def _parse_now(value: str | None) -> datetime:
    if value:
        return parse_time(value)
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
