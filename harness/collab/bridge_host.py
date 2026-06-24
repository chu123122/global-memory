"""Local bridge host MVP over fake/manual runtime.

This module materializes the Phase 6 worker launch blueprint into an event-sourced
local host model. It does not spawn real workers; fake/manual sessions only prove
UI/state/router shape for Phase 7.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .errors import CollabError


class BridgeHostError(CollabError):
    """Raised when bridge host session/event input is invalid."""

    error_code = "COLLAB_BRIDGE_HOST_INVALID_INPUT"


_ALLOWED_RUNTIME_MODES = {"fake", "manual"}
_ALLOWED_WORKER_STATUSES = {"ready", "focused", "running", "done", "blocked", "error"}


def create_session_from_blueprint(
    blueprint: Mapping[str, Any],
    *,
    worker_limit: int | None = None,
    runtime_mode: str = "fake",
) -> dict[str, Any]:
    """Create an event-sourced local host session from a Phase 6 blueprint."""

    _validate_blueprint(blueprint)
    if runtime_mode not in _ALLOWED_RUNTIME_MODES:
        raise BridgeHostError(f"runtime_mode must be one of {sorted(_ALLOWED_RUNTIME_MODES)}")
    workers_raw = blueprint.get("workers", [])
    limit = len(workers_raw) if worker_limit is None else max(0, int(worker_limit))
    workers = [_worker_from_blueprint(item) for item in workers_raw[:limit]]
    events = [
        {
            "type": "session_created",
            "workflow": _text(blueprint.get("workflow")),
            "plan_id": _text(blueprint.get("plan_id")),
            "runtime_mode": runtime_mode,
            "spawns_process_now": False,
        }
    ]
    for worker in workers:
        events.append({"type": "worker_created", "worker": worker})
    focused = workers[0]["worker_id"] if workers else None
    if focused:
        events.append({"type": "worker_focused", "worker_id": focused})
    return _session_from_events(events)


def create_bridge_worker(
    session: Mapping[str, Any],
    *,
    worker_id: str,
    agent: str,
    initial_prompt: str,
    dispatch_id: str | None = None,
    role: str | None = None,
    runtime_adapter: str = "operator_command",
    focus: bool = False,
) -> dict[str, Any]:
    """Append a bridge-owned worker row without starting a process."""

    worker = {
        "worker_id": _required_value(worker_id, "worker_id"),
        "dispatch_id": _text(dispatch_id) or _required_value(worker_id, "worker_id"),
        "agent": _required_value(agent, "agent"),
        "role": _text(role),
        "runtime_adapter": _required_value(runtime_adapter, "runtime_adapter"),
        "status": "ready",
        "messages": [],
        "initial_prompt": _required_value(initial_prompt, "initial_prompt"),
        "spawns_process_now": False,
    }
    if worker["worker_id"] in {item.get("worker_id") for item in session.get("workers", []) if isinstance(item, Mapping)}:
        raise BridgeHostError(f"worker_id already exists: {worker['worker_id']}")
    events: list[Mapping[str, Any]] = _events(session) + [{"type": "worker_created", "worker": worker}]
    if focus:
        events.append({"type": "worker_focused", "worker_id": worker["worker_id"]})
    return _session_from_events(events)


def focus_worker(session: Mapping[str, Any], worker_id: str) -> dict[str, Any]:
    _require_worker(session, worker_id)
    return _session_from_events(_events(session) + [{"type": "worker_focused", "worker_id": worker_id}])


def send_worker_message(session: Mapping[str, Any], worker_id: str, message: str, *, now: str | None = None) -> dict[str, Any]:
    _require_worker(session, worker_id)
    text = _text(message)
    if not text:
        raise BridgeHostError("message is required")
    event: dict[str, Any] = {"type": "message_sent", "worker_id": worker_id, "message": text}
    if now:
        event["at"] = now
    return _session_from_events(_events(session) + [event])


def ingest_worker_report(
    session: Mapping[str, Any],
    worker_id: str,
    report: str,
    *,
    status: str = "done",
    now: str | None = None,
) -> dict[str, Any]:
    _require_worker(session, worker_id)
    if status not in _ALLOWED_WORKER_STATUSES:
        raise BridgeHostError(f"worker status must be one of {sorted(_ALLOWED_WORKER_STATUSES)}")
    pointer = _text(report)
    if not pointer:
        raise BridgeHostError("report is required")
    event: dict[str, Any] = {"type": "report_ingested", "worker_id": worker_id, "report": pointer, "status": status}
    if now:
        event["at"] = now
    return _session_from_events(_events(session) + [event])


def record_worker_runtime_result(
    session: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Append a Phase 9 bridge-owned worker runtime result event."""

    worker_id = _required_text(result, "worker_id")
    _require_worker(session, worker_id)
    status = _text(result.get("status")) or "error"
    if status not in _ALLOWED_WORKER_STATUSES:
        raise BridgeHostError(f"worker status must be one of {sorted(_ALLOWED_WORKER_STATUSES)}")
    event: dict[str, Any] = {
        "type": "worker_runtime_result",
        "worker_id": worker_id,
        "status": status,
        "exit_code": result.get("exit_code"),
        "timed_out": result.get("timed_out") is True,
        "spawns_process_now": result.get("spawns_process_now") is True,
        "runtime_mode": _text(result.get("runtime_mode")) or "operator_command",
        "command": _command_list(result.get("command")),
        "stdout": _text(result.get("stdout")),
        "stderr": _text(result.get("stderr")),
        "report": _text(result.get("report")) or _runtime_report_from_result(result),
    }
    if result.get("cwd") is not None:
        event["cwd"] = _text(result.get("cwd"))
    if now:
        event["at"] = now
    return _session_from_events(_events(session) + [event])


def materialize_bridge_host(session: Mapping[str, Any]) -> dict[str, Any]:
    """Build the stable local host UI/view model from session events."""

    normalized = _session_from_events(_events(session))
    workers = normalized["workers"]
    focused = normalized.get("focused_worker_id")
    has_real_runtime = normalized.get("real_worker_lifecycle") is True
    return {
        "schema_version": 1,
        "kind": "collab_bridge_host_model",
        "workflow": normalized["workflow"],
        "plan_id": normalized["plan_id"],
        "focused_worker_id": focused,
        "contract": {
            "phase": 9 if has_real_runtime else 7,
            "runtime_mode": normalized["runtime_mode"],
            "real_worker_lifecycle": has_real_runtime,
            "spawns_process_now": normalized.get("spawns_process_now") is True,
            "consumes_bridge_blueprint": True,
            "lead_cli_wrapped": False,
        },
        "summary": {
            "worker_count": len(workers),
            "event_count": len(normalized["events"]),
            "message_count": sum(len(item.get("messages", [])) for item in workers),
            "report_count": sum(1 for item in workers if item.get("report_pointer")),
            "runtime_run_count": sum(len(item.get("runtime_runs", [])) for item in workers),
            "router_message_count": sum(len(item.get("router_messages", [])) for item in workers),
            "router_failed_count": sum(1 for item in workers for msg in item.get("router_messages", []) if msg.get("status") == "failed"),
            "router_duplicate_count": sum(item.get("router_duplicate_count", 0) for item in workers),
        },
        "worker_rows": [
            {
                "worker_id": item["worker_id"],
                "dispatch_id": item["dispatch_id"],
                "agent": item["agent"],
                "role": item.get("role"),
                "runtime_adapter": item["runtime_adapter"],
                "status": item["status"],
                "focused": item["worker_id"] == focused,
                "message_count": len(item.get("messages", [])),
                "last_message": item.get("messages", [])[-1]["message"] if item.get("messages") else None,
                "report_pointer": item.get("report_pointer"),
                "runtime_run_count": len(item.get("runtime_runs", [])),
                "last_runtime_status": item.get("runtime_runs", [])[-1]["status"] if item.get("runtime_runs") else None,
                "router_outbox_count": sum(1 for msg in item.get("router_messages", []) if msg.get("status") in {"queued", "retried"}),
                "router_acked_count": sum(1 for msg in item.get("router_messages", []) if msg.get("status") == "acked"),
                "router_failed_count": sum(1 for msg in item.get("router_messages", []) if msg.get("status") == "failed"),
                "router_duplicate_count": item.get("router_duplicate_count", 0),
            }
            for item in workers
        ],
        "operator_actions": _operator_actions(normalized),
    }


def save_session_events(session: Mapping[str, Any], path: str | Path) -> None:
    event_path = Path(path)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event, ensure_ascii=False, sort_keys=True) for event in _events(session)]
    event_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_session_events(path: str | Path) -> dict[str, Any]:
    event_path = Path(path)
    try:
        text = event_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BridgeHostError(f"failed to read event log {event_path}: {exc}") from exc
    events = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BridgeHostError(f"event log line {index} is not valid JSON: {exc}") from exc
        if not isinstance(event, Mapping):
            raise BridgeHostError(f"event log line {index} must be an object")
        events.append(dict(event))
    return _session_from_events(events)


def dumps_bridge_host_json(model: Mapping[str, Any]) -> str:
    return json.dumps(dict(model), ensure_ascii=False, indent=2) + "\n"


def _session_from_events(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not events:
        raise BridgeHostError("event log is empty")
    workflow = ""
    plan_id = ""
    runtime_mode = "fake"
    spawns = False
    real_worker_lifecycle = False
    workers: dict[str, dict[str, Any]] = {}
    router_index: dict[str, tuple[str, dict[str, Any]]] = {}
    focused: str | None = None
    normalized_events: list[dict[str, Any]] = []
    for raw in events:
        event = copy.deepcopy(dict(raw))
        event_type = _text(event.get("type"))
        if not event_type:
            raise BridgeHostError("event.type is required")
        if event_type == "session_created":
            workflow = _required_text(event, "workflow")
            plan_id = _required_text(event, "plan_id")
            runtime_mode = _text(event.get("runtime_mode")) or "fake"
            spawns = event.get("spawns_process_now") is True
        elif event_type == "worker_created":
            worker = event.get("worker")
            if not isinstance(worker, Mapping):
                raise BridgeHostError("worker_created.worker must be an object")
            item = _static_worker(dict(worker))
            worker_id = _required_text(item, "worker_id")
            item.setdefault("status", "ready")
            item.setdefault("messages", [])
            item.setdefault("runtime_runs", [])
            item.setdefault("router_messages", [])
            item.setdefault("router_duplicate_count", 0)
            workers[worker_id] = item
            event["worker"] = _static_worker(dict(worker))
        elif event_type == "worker_focused":
            worker_id = _required_text(event, "worker_id")
            if worker_id not in workers:
                raise BridgeHostError(f"unknown worker_id: {worker_id}")
            focused = worker_id
        elif event_type == "message_sent":
            worker_id = _required_text(event, "worker_id")
            if worker_id not in workers:
                raise BridgeHostError(f"unknown worker_id: {worker_id}")
            workers[worker_id].setdefault("messages", []).append({"message": _required_text(event, "message"), **({"at": event["at"]} if event.get("at") else {})})
            workers[worker_id]["status"] = "running"
        elif event_type == "report_ingested":
            worker_id = _required_text(event, "worker_id")
            if worker_id not in workers:
                raise BridgeHostError(f"unknown worker_id: {worker_id}")
            workers[worker_id]["report_pointer"] = _required_text(event, "report")
            workers[worker_id]["status"] = _text(event.get("status")) or "done"
        elif event_type == "worker_runtime_result":
            worker_id = _required_text(event, "worker_id")
            if worker_id not in workers:
                raise BridgeHostError(f"unknown worker_id: {worker_id}")
            command = _command_list(event.get("command"))
            if not command:
                raise BridgeHostError("worker_runtime_result.command is required")
            status = _text(event.get("status")) or "error"
            if status not in _ALLOWED_WORKER_STATUSES:
                raise BridgeHostError(f"worker status must be one of {sorted(_ALLOWED_WORKER_STATUSES)}")
            runtime_run = {
                "status": status,
                "exit_code": event.get("exit_code"),
                "timed_out": event.get("timed_out") is True,
                "runtime_mode": _text(event.get("runtime_mode")) or "operator_command",
                "command": command,
            }
            if event.get("at"):
                runtime_run["at"] = event["at"]
            workers[worker_id].setdefault("runtime_runs", []).append(runtime_run)
            workers[worker_id]["status"] = status
            report = _text(event.get("report")) or _runtime_report_from_result(event)
            if report:
                workers[worker_id]["report_pointer"] = report
            if event.get("spawns_process_now") is True:
                spawns = True
                real_worker_lifecycle = True
        elif event_type == "router_message_queued":
            worker_id = _required_text(event, "worker_id")
            if worker_id not in workers:
                raise BridgeHostError(f"unknown worker_id: {worker_id}")
            message_id = _required_text(event, "message_id")
            if message_id in router_index:
                raise BridgeHostError(f"duplicate router message_id: {message_id}")
            msg = {"message_id": message_id, "correlation_id": _required_text(event, "correlation_id"), "dedupe_key": _required_text(event, "dedupe_key"), "message": _required_text(event, "message"), "status": _text(event.get("status")) or "queued", "attempt": int(event.get("attempt") or 1)}
            if event.get("at"):
                msg["at"] = event["at"]
            workers[worker_id].setdefault("router_messages", []).append(msg)
            router_index[message_id] = (worker_id, msg)
        elif event_type == "router_message_acknowledged":
            message_id = _required_text(event, "message_id")
            if message_id not in router_index:
                raise BridgeHostError(f"unknown message_id: {message_id}")
            worker_id, msg = router_index[message_id]
            msg["status"] = "acked"
            msg["ack_id"] = _text(event.get("ack_id")) or message_id
            workers[worker_id].setdefault("messages", []).append({"message": msg["message"], "correlation_id": msg["correlation_id"], **({"at": event["at"]} if event.get("at") else {})})
        elif event_type == "router_message_failed":
            message_id = _required_text(event, "message_id")
            if message_id not in router_index:
                raise BridgeHostError(f"unknown message_id: {message_id}")
            _worker_id, msg = router_index[message_id]
            msg["status"] = "failed"
            msg["error"] = _required_text(event, "error")
            msg["retryable"] = event.get("retryable") is not False
        elif event_type == "router_message_retried":
            original_id = _required_text(event, "original_message_id")
            if original_id not in router_index:
                raise BridgeHostError(f"unknown message_id: {original_id}")
            worker_id, original = router_index[original_id]
            new_id = _required_text(event, "message_id")
            original["status"] = "retried"
            msg = {"message_id": new_id, "correlation_id": _required_text(event, "correlation_id"), "dedupe_key": _required_text(event, "dedupe_key"), "message": _required_text(event, "message"), "status": "queued", "attempt": int(event.get("attempt") or 1), "retry_of": original_id}
            workers[worker_id].setdefault("router_messages", []).append(msg)
            router_index[new_id] = (worker_id, msg)
        elif event_type == "router_duplicate_detected":
            worker_id = _required_text(event, "worker_id")
            if worker_id not in workers:
                raise BridgeHostError(f"unknown worker_id: {worker_id}")
            workers[worker_id]["router_duplicate_count"] = workers[worker_id].get("router_duplicate_count", 0) + 1
        else:
            raise BridgeHostError(f"unknown event type: {event_type}")
        normalized_events.append(event)
    if not workflow or not plan_id:
        raise BridgeHostError("session_created event is required")
    return {
        "schema_version": 1,
        "kind": "collab_bridge_host_session",
        "workflow": workflow,
        "plan_id": plan_id,
        "runtime_mode": runtime_mode,
        "spawns_process_now": spawns,
        "real_worker_lifecycle": real_worker_lifecycle,
        "focused_worker_id": focused,
        "workers": list(workers.values()),
        "events": normalized_events,
    }


def _static_worker(item: dict[str, Any]) -> dict[str, Any]:
    """Return immutable event-log fields for worker_created events."""

    allowed = {
        "worker_id",
        "dispatch_id",
        "agent",
        "role",
        "runtime_adapter",
        "status",
        "initial_prompt",
        "spawns_process_now",
    }
    return {key: value for key, value in item.items() if key in allowed}


def _worker_from_blueprint(item: Mapping[str, Any]) -> dict[str, Any]:
    dispatch_id = _required_text(item, "dispatch_id")
    return {
        "worker_id": f"worker-{dispatch_id}",
        "dispatch_id": dispatch_id,
        "agent": _required_text(item, "agent"),
        "role": _text(item.get("role")),
        "runtime_adapter": _required_text(item, "runtime_adapter"),
        "status": "ready",
        "messages": [],
        "initial_prompt": _required_text(item, "initial_prompt"),
        "spawns_process_now": False,
    }


def _operator_actions(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    actions = [
        {"action": "focus_worker", "description": "Switch the selected worker row in the local bridge UI.", "writes_event_log": True},
        {"action": "send_worker_message", "description": "Append a fake/manual message event; does not contact a real runtime in Phase 7.", "writes_event_log": True},
        {"action": "ingest_worker_report", "description": "Attach a report pointer or pasted report to a worker.", "writes_event_log": True},
        {"action": "run_worker_command", "description": "Phase 9: explicitly run an operator-configured worker command; requires allow-spawn and writes a runtime result event.", "writes_event_log": True},
    ]
    if session.get("runtime_mode") in {"fake", "manual"}:
        actions.append({"action": "phase7_boundary", "description": "Fake/manual proves UI/state only; real worker lifecycle starts in Phase 9/10.", "writes_event_log": False})
    return actions


def _validate_blueprint(blueprint: Mapping[str, Any]) -> None:
    if blueprint.get("kind") != "collab_worker_launch_blueprint":
        raise BridgeHostError("blueprint.kind must be collab_worker_launch_blueprint")
    if blueprint.get("spawns_process_now") is not False:
        raise BridgeHostError("blueprint.spawns_process_now must be false")
    if not isinstance(blueprint.get("workers"), list):
        raise BridgeHostError("blueprint.workers must be a list")
    _required_text(blueprint, "workflow")
    _required_text(blueprint, "plan_id")


def _require_worker(session: Mapping[str, Any], worker_id: str) -> None:
    if _text(worker_id) not in {item.get("worker_id") for item in session.get("workers", []) if isinstance(item, Mapping)}:
        raise BridgeHostError(f"unknown worker_id: {worker_id}")


def _events(session: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    events = session.get("events")
    if not isinstance(events, list):
        raise BridgeHostError("session.events must be a list")
    return [event if isinstance(event, Mapping) else _bad_event() for event in events]


def _bad_event() -> Mapping[str, Any]:
    raise BridgeHostError("session.events items must be objects")


def _required_text(mapping: Mapping[str, Any], field: str) -> str:
    value = _text(mapping.get(field))
    if not value:
        raise BridgeHostError(f"{field} is required")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _command_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise BridgeHostError("command must be a list")
    return [_required_command_part(item) for item in value]


def _required_command_part(value: Any) -> str:
    text = _text(value)
    if not text:
        raise BridgeHostError("command items must be non-empty strings")
    return text


def _runtime_report_from_result(result: Mapping[str, Any]) -> str:
    stdout = _text(result.get("stdout"))
    stderr = _text(result.get("stderr"))
    status = _text(result.get("status")) or "error"
    exit_code = result.get("exit_code")
    if stdout:
        return stdout[:4000]
    if stderr:
        return stderr[:4000]
    return f"runtime status={status} exit_code={exit_code}"


def _required_value(value: Any, field: str) -> str:
    text = _text(value)
    if not text:
        raise BridgeHostError(f"{field} is required")
    return text
