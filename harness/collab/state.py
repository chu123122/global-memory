"""Lightweight JSON state for collaboration dispatch replay/checkpoints."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


ALLOWED_DISPATCH_STATUSES = {"pending", "dispatched", "running", "done", "blocked", "error"}


class StateError(ValueError):
    """Raised when a collaboration state artifact is invalid."""


@dataclass(frozen=True)
class DispatchState:
    """State for one planned dispatch."""

    dispatch_id: str
    agent: str
    status: str = "pending"
    worker_id: str | None = None
    session_id: str | None = None
    report: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "dispatch_id": self.dispatch_id,
            "agent": self.agent,
            "status": self.status,
        }
        if self.worker_id:
            data["worker_id"] = self.worker_id
        if self.session_id:
            data["session_id"] = self.session_id
        if self.report:
            data["report"] = self.report
        if self.updated_at:
            data["updated_at"] = self.updated_at
        return data

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "DispatchState":
        dispatch_id = _required_text(raw, "dispatch_id")
        agent = _required_text(raw, "agent")
        status = _required_text(raw, "status")
        _validate_status(status)
        return cls(
            dispatch_id=dispatch_id,
            agent=agent,
            status=status,
            worker_id=_optional_text(raw.get("worker_id")),
            session_id=_optional_text(raw.get("session_id")),
            report=_optional_text(raw.get("report")),
            updated_at=_optional_text(raw.get("updated_at")),
        )


@dataclass(frozen=True)
class CollabState:
    """Serializable collab workflow state."""

    schema_version: int
    workflow: str
    plan_id: str
    dispatches: tuple[DispatchState, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "workflow": self.workflow,
            "plan_id": self.plan_id,
            "dispatches": [item.to_dict() for item in self.dispatches],
        }
        if self.notes:
            data["notes"] = list(self.notes)
        return data

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CollabState":
        schema_version = raw.get("schema_version")
        if schema_version != 1:
            raise StateError("state.schema_version must be 1")
        workflow = _required_text(raw, "workflow")
        plan_id = _required_text(raw, "plan_id")
        dispatches_raw = raw.get("dispatches")
        if not isinstance(dispatches_raw, list):
            raise StateError("state.dispatches must be a list")
        dispatches = tuple(
            DispatchState.from_mapping(item) if isinstance(item, Mapping) else _bad_dispatch(index)
            for index, item in enumerate(dispatches_raw)
        )
        notes_raw = raw.get("notes", [])
        if not isinstance(notes_raw, list):
            raise StateError("state.notes must be a list")
        notes = tuple(str(note).strip() for note in notes_raw if str(note).strip())
        return cls(
            schema_version=1,
            workflow=workflow,
            plan_id=plan_id,
            dispatches=dispatches,
            notes=notes,
        )


def state_from_plan(plan: Mapping[str, Any], *, notes: list[str] | None = None) -> CollabState:
    """Create an initial pending state from a dispatch plan."""

    dispatches_raw = plan.get("dispatches")
    if not isinstance(dispatches_raw, list):
        raise StateError("plan.dispatches must be a list")
    dispatches = []
    for index, dispatch in enumerate(dispatches_raw):
        if not isinstance(dispatch, Mapping):
            raise StateError(f"plan.dispatches[{index}] must be an object")
        dispatches.append(
            DispatchState(
                dispatch_id=_required_text(dispatch, "id"),
                agent=_required_text(dispatch, "agent"),
            )
        )
    return CollabState(
        schema_version=1,
        workflow=_required_text(plan, "workflow"),
        plan_id=_required_text(plan, "plan_id"),
        dispatches=tuple(dispatches),
        notes=tuple(notes or ()),
    )


def update_dispatch(
    state: CollabState,
    dispatch_id: str,
    *,
    status: str,
    worker_id: str | None = None,
    session_id: str | None = None,
    report: str | None = None,
    updated_at: str | None = None,
) -> CollabState:
    """Return a copy of state with one dispatch updated."""

    _validate_status(status)
    found = False
    updated: list[DispatchState] = []
    for item in state.dispatches:
        if item.dispatch_id != dispatch_id:
            updated.append(item)
            continue
        found = True
        updated.append(
            DispatchState(
                dispatch_id=item.dispatch_id,
                agent=item.agent,
                status=status,
                worker_id=worker_id if worker_id is not None else item.worker_id,
                session_id=session_id if session_id is not None else item.session_id,
                report=report if report is not None else item.report,
                updated_at=updated_at if updated_at is not None else item.updated_at,
            )
        )
    if not found:
        raise StateError(f"unknown dispatch_id: {dispatch_id}")
    return CollabState(
        schema_version=state.schema_version,
        workflow=state.workflow,
        plan_id=state.plan_id,
        dispatches=tuple(updated),
        notes=state.notes,
    )


def summarize_state(state: CollabState) -> dict[str, Any]:
    """Return deterministic status counts and completion facts for a state."""

    counts = {status: 0 for status in sorted(ALLOWED_DISPATCH_STATUSES)}
    for item in state.dispatches:
        counts[item.status] = counts.get(item.status, 0) + 1
    return {
        "workflow": state.workflow,
        "plan_id": state.plan_id,
        "dispatch_count": len(state.dispatches),
        "status_counts": counts,
        "all_done": bool(state.dispatches) and all(item.status == "done" for item in state.dispatches),
        "has_blockers": any(item.status in {"blocked", "error"} for item in state.dispatches),
    }


def load_state(path: str | Path) -> CollabState:
    """Load a state JSON file."""

    state_path = Path(path)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StateError(f"failed to read state {state_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise StateError(f"state {state_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise StateError("state root must be an object")
    return CollabState.from_mapping(payload)


def save_state(state: CollabState, path: str | Path) -> None:
    """Write state as stable UTF-8 JSON."""

    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(dumps_state_json(state), encoding="utf-8")


def dumps_state_json(state: CollabState) -> str:
    """Serialize state with stable formatting."""

    return json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n"


def _bad_dispatch(index: int) -> DispatchState:
    raise StateError(f"state.dispatches[{index}] must be an object")


def _validate_status(status: str) -> None:
    if status not in ALLOWED_DISPATCH_STATUSES:
        raise StateError(f"dispatch status must be one of {sorted(ALLOWED_DISPATCH_STATUSES)}")


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = str(mapping.get(field, "")).strip()
    if not value:
        raise StateError(f"{field} is required")
    return value


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
