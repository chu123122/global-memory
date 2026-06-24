"""Phase 8 event-sourced store helpers for the local collab bridge host."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .bridge_host import BridgeHostError, load_session_events, materialize_bridge_host
from .errors import CollabError


class BridgeStoreError(CollabError):
    """Raised when bridge store input or snapshot data is invalid."""

    error_code = "COLLAB_BRIDGE_STORE_INVALID_INPUT"


def build_store_summary(session: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic store metadata plus materialized view-model."""

    try:
        model = materialize_bridge_host(session)
    except BridgeHostError as exc:
        raise BridgeStoreError(str(exc)) from exc
    events = _events(session)
    return {
        "schema_version": 1,
        "kind": "collab_bridge_store_summary",
        "workflow": _text(model.get("workflow")),
        "plan_id": _text(model.get("plan_id")),
        "event_count": len(events),
        "event_types": _event_type_counts(events),
        "replay": {
            "deterministic": materialize_bridge_host(session) == model,
            "source": "events",
        },
        "materialized": model,
        "migration": {
            "current_schema_version": 1,
            "supported_schema_versions": [1],
        },
    }


def write_materialized_snapshot(session: Mapping[str, Any], path: str | Path) -> dict[str, Any]:
    """Atomically write materialized session JSON and return write metadata."""

    snapshot_path = Path(path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_store_summary(session)
    tmp_path = snapshot_path.with_name(snapshot_path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload["materialized"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, snapshot_path)
    return {
        "schema_version": 1,
        "kind": "collab_bridge_snapshot_written",
        "path": str(snapshot_path),
        "event_count": payload["event_count"],
        "worker_count": payload["materialized"]["summary"]["worker_count"],
    }


def replay_store(path: str | Path) -> dict[str, Any]:
    """Read a materialized snapshot and validate its stable view-model shape."""

    snapshot_path = Path(path)
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BridgeStoreError(f"failed to read snapshot {snapshot_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BridgeStoreError(f"snapshot {snapshot_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise BridgeStoreError("snapshot root must be an object")
    if payload.get("kind") != "collab_bridge_host_model":
        raise BridgeStoreError("snapshot.kind must be collab_bridge_host_model")
    if not isinstance(payload.get("worker_rows"), list):
        raise BridgeStoreError("snapshot.worker_rows must be a list")
    return dict(payload)


def migrate_event_log(events: Sequence[Mapping[str, Any]], *, from_version: int, to_version: int) -> dict[str, Any]:
    """Return a migration report. Phase 8 only supports no-op v1 -> v1."""

    if from_version != 1 or to_version != 1:
        raise BridgeStoreError("only schema migration 1 -> 1 is supported in Phase 8")
    return {
        "schema_version": 1,
        "kind": "collab_bridge_event_migration",
        "from_version": from_version,
        "to_version": to_version,
        "changed": False,
        "event_count": len(list(events)),
        "notes": ["Phase 8 migration stub: event schema v1 is already current."],
    }


def load_store_events(path: str | Path) -> dict[str, Any]:
    """Load event JSONL with store-specific stable error wrapping."""

    try:
        return load_session_events(path)
    except BridgeHostError as exc:
        raise BridgeStoreError(str(exc)) from exc


def dumps_bridge_store_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _events(session: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    events = session.get("events")
    if not isinstance(events, list):
        raise BridgeStoreError("session.events must be a list")
    return [event if isinstance(event, Mapping) else _bad_event() for event in events]


def _bad_event() -> Mapping[str, Any]:
    raise BridgeStoreError("session.events items must be objects")


def _event_type_counts(events: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        key = _text(event.get("type")) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _text(value: Any) -> str:
    return str(value or "").strip()
