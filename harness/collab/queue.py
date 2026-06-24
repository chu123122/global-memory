"""Host-neutral multi-worker queue for collaboration dispatches."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import CollabError

QUEUE_STATUSES = {"queued", "leased", "done", "error"}


class QueueError(CollabError):
    """Raised when a collaboration queue operation is invalid."""

    error_code = "COLLAB_QUEUE_INVALID"


@dataclass(frozen=True)
class QueueItem:
    dispatch_id: str
    agent: str
    status: str = "queued"
    labels: tuple[str, ...] = field(default_factory=tuple)
    attempts: int = 0
    max_attempts: int = 3
    lease_owner: str | None = None
    lease_id: str | None = None
    leased_at: str | None = None
    last_error: str | None = None
    report: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "dispatch_id": self.dispatch_id,
            "agent": self.agent,
            "status": self.status,
            "labels": list(self.labels),
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
        }
        for key in ("lease_owner", "lease_id", "leased_at", "last_error", "report"):
            value = getattr(self, key)
            if value:
                data[key] = value
        return data

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "QueueItem":
        status = _required_text(raw, "status")
        if status not in QUEUE_STATUSES:
            raise QueueError(f"queue item status must be one of {sorted(QUEUE_STATUSES)}")
        labels_raw = raw.get("labels", [])
        if not isinstance(labels_raw, list):
            raise QueueError("queue item labels must be a list")
        return cls(
            dispatch_id=_required_text(raw, "dispatch_id"),
            agent=_required_text(raw, "agent"),
            status=status,
            labels=tuple(_normalize_labels(labels_raw)),
            attempts=_nonnegative_int(raw.get("attempts", 0), "attempts"),
            max_attempts=max(1, _nonnegative_int(raw.get("max_attempts", 3), "max_attempts")),
            lease_owner=_optional_text(raw.get("lease_owner")),
            lease_id=_optional_text(raw.get("lease_id")),
            leased_at=_optional_text(raw.get("leased_at")),
            last_error=_optional_text(raw.get("last_error")),
            report=_optional_text(raw.get("report")),
        )


@dataclass(frozen=True)
class CollabQueue:
    schema_version: int
    workflow: str
    plan_id: str
    items: tuple[QueueItem, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "kind": "collab_queue",
            "workflow": self.workflow,
            "plan_id": self.plan_id,
            "items": [item.to_dict() for item in self.items],
        }
        if self.notes:
            data["notes"] = list(self.notes)
        return data

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CollabQueue":
        if raw.get("schema_version") != 1:
            raise QueueError("queue.schema_version must be 1")
        items_raw = raw.get("items")
        if not isinstance(items_raw, list):
            raise QueueError("queue.items must be a list")
        notes_raw = raw.get("notes", [])
        if not isinstance(notes_raw, list):
            raise QueueError("queue.notes must be a list")
        return cls(
            schema_version=1,
            workflow=_required_text(raw, "workflow"),
            plan_id=_required_text(raw, "plan_id"),
            items=tuple(QueueItem.from_mapping(item) if isinstance(item, Mapping) else _bad_item(index) for index, item in enumerate(items_raw)),
            notes=tuple(str(note).strip() for note in notes_raw if str(note).strip()),
        )


def queue_from_plan(
    plan: Mapping[str, Any],
    *,
    labels_by_dispatch: Mapping[str, Sequence[str]] | None = None,
    max_attempts: int = 3,
    notes: Sequence[str] | None = None,
) -> CollabQueue:
    dispatches = plan.get("dispatches")
    if not isinstance(dispatches, list):
        raise QueueError("plan.dispatches must be a list")
    labels_by_dispatch = labels_by_dispatch or {}
    items = []
    for index, raw in enumerate(dispatches):
        if not isinstance(raw, Mapping):
            raise QueueError(f"plan.dispatches[{index}] must be an object")
        dispatch_id = _required_text(raw, "id")
        items.append(
            QueueItem(
                dispatch_id=dispatch_id,
                agent=_required_text(raw, "agent"),
                labels=tuple(_normalize_labels(labels_by_dispatch.get(dispatch_id, []))),
                max_attempts=max(1, int(max_attempts)),
            )
        )
    return CollabQueue(
        schema_version=1,
        workflow=_required_text(plan, "workflow"),
        plan_id=_required_text(plan, "plan_id"),
        items=tuple(items),
        notes=tuple(str(note).strip() for note in notes or [] if str(note).strip()),
    )


def lease_next(
    queue: CollabQueue,
    *,
    worker_id: str,
    labels: Sequence[str] | None = None,
    max_concurrent: int = 1,
    now: str | None = None,
) -> tuple[CollabQueue, QueueItem]:
    worker_id = _normalize_required(worker_id, "worker_id")
    if max_concurrent < 1:
        raise QueueError("max_concurrent must be >= 1")
    active = sum(1 for item in queue.items if item.status == "leased" and item.lease_owner == worker_id)
    if active >= max_concurrent:
        raise QueueError("worker concurrency limit reached", error_code="COLLAB_QUEUE_CONCURRENCY_LIMIT")
    desired_labels = set(_normalize_labels(labels or []))
    for item in queue.items:
        if item.status != "queued":
            continue
        if desired_labels and not desired_labels.issubset(set(item.labels)):
            continue
        leased = _replace_item(
            item,
            status="leased",
            lease_owner=worker_id,
            lease_id=_lease_id(queue.plan_id, item.dispatch_id, item.attempts + 1, worker_id),
            leased_at=now or _utc_now(),
            last_error=item.last_error,
        )
        return _update_item(queue, leased), leased
    raise QueueError("no queued item matches the requested labels", error_code="COLLAB_QUEUE_EMPTY")


def requeue_lease(queue: CollabQueue, lease_id: str, *, reason: str | None = None) -> CollabQueue:
    item = _find_lease(queue, lease_id)
    attempts = item.attempts + 1
    status = "queued" if attempts < item.max_attempts else "error"
    updated = _replace_item(
        item,
        status=status,
        attempts=attempts,
        lease_owner=None,
        lease_id=None,
        leased_at=None,
        last_error=_optional_text(reason),
    )
    return _update_item(queue, updated)


def complete_lease(queue: CollabQueue, lease_id: str, *, report: str | None = None) -> CollabQueue:
    item = _find_lease(queue, lease_id)
    updated = _replace_item(
        item,
        status="done",
        lease_owner=None,
        lease_id=None,
        leased_at=None,
        report=_optional_text(report),
    )
    return _update_item(queue, updated)


def fail_lease(queue: CollabQueue, lease_id: str, *, reason: str | None = None) -> CollabQueue:
    item = _find_lease(queue, lease_id)
    updated = _replace_item(
        item,
        status="error",
        lease_owner=None,
        lease_id=None,
        leased_at=None,
        last_error=_optional_text(reason),
    )
    return _update_item(queue, updated)


def summarize_queue(queue: CollabQueue) -> dict[str, Any]:
    counts = {status: 0 for status in sorted(QUEUE_STATUSES)}
    for item in queue.items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return {
        "workflow": queue.workflow,
        "plan_id": queue.plan_id,
        "item_count": len(queue.items),
        "status_counts": counts,
        "all_done": bool(queue.items) and all(item.status == "done" for item in queue.items),
        "has_errors": any(item.status == "error" for item in queue.items),
    }


def load_queue(path: str | Path) -> CollabQueue:
    queue_path = Path(path)
    try:
        payload = json.loads(queue_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise QueueError(f"failed to read queue {queue_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise QueueError(f"queue {queue_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise QueueError("queue root must be an object")
    return CollabQueue.from_mapping(payload)


def save_queue(queue: CollabQueue, path: str | Path) -> None:
    queue_path = Path(path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(dumps_queue_json(queue), encoding="utf-8")


def dumps_queue_json(queue: CollabQueue | Mapping[str, Any]) -> str:
    payload = queue.to_dict() if isinstance(queue, CollabQueue) else dict(queue)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise QueueError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _find_lease(queue: CollabQueue, lease_id: str) -> QueueItem:
    wanted = _normalize_required(lease_id, "lease_id")
    for item in queue.items:
        if item.lease_id == wanted and item.status == "leased":
            return item
    raise QueueError(f"lease not found: {wanted}", error_code="COLLAB_QUEUE_LEASE_NOT_FOUND")


def _update_item(queue: CollabQueue, updated: QueueItem) -> CollabQueue:
    return CollabQueue(
        schema_version=queue.schema_version,
        workflow=queue.workflow,
        plan_id=queue.plan_id,
        items=tuple(updated if item.dispatch_id == updated.dispatch_id else item for item in queue.items),
        notes=queue.notes,
    )


def _replace_item(item: QueueItem, **changes: Any) -> QueueItem:
    data = item.to_dict()
    data.update(changes)
    return QueueItem.from_mapping(data)


def _lease_id(plan_id: str, dispatch_id: str, attempt: int, worker_id: str) -> str:
    safe_worker = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in worker_id)
    return f"{plan_id}:{dispatch_id}:attempt-{attempt}:{safe_worker}"


def _bad_item(index: int) -> QueueItem:
    raise QueueError(f"queue.items[{index}] must be an object")


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    return _normalize_required(mapping.get(field), field)


def _normalize_required(value: Any, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise QueueError(f"{field} is required")
    return normalized


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_labels(labels: Sequence[Any]) -> list[str]:
    return sorted({str(label).strip() for label in labels if str(label).strip()})


def _nonnegative_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise QueueError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise QueueError(f"{field} must be >= 0")
    return parsed


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
