"""Phase 11 interactive router and report loop hardening."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .bridge_host import BridgeHostError, ingest_worker_report, materialize_bridge_host
from .errors import CollabError


class RouterError(CollabError):
    """Raised when Phase 11 router input is invalid."""

    error_code = "COLLAB_ROUTER_INVALID_INPUT"


def build_router_snapshot(session: Mapping[str, Any]) -> dict[str, Any]:
    try:
        model = materialize_bridge_host(session)
    except BridgeHostError as exc:
        raise RouterError(f"invalid bridge host session: {exc}") from exc
    messages = _router_messages(session)
    return {
        "schema_version": 1,
        "kind": "collab_router_snapshot",
        "phase": 11,
        "summary": {
            "message_count": len(messages),
            "queued": sum(1 for item in messages if item["status"] == "queued"),
            "acked": sum(1 for item in messages if item["status"] == "acked"),
            "failed": sum(1 for item in messages if item["status"] == "failed"),
            "retried": sum(1 for item in messages if item["status"] == "retried"),
            "duplicates": sum(1 for event in _events(session) if event.get("type") == "router_duplicate_detected"),
        },
        "messages": messages,
        "materialized": model,
    }


def enqueue_message(session: Mapping[str, Any], worker_id: str, message: str, *, correlation_id: str | None = None, dedupe_key: str | None = None, now: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    worker = _require_worker(session, worker_id)
    text = _required_value(message, "message")
    correlation = _text(correlation_id) or _stable_id("corr", worker, text)
    dedupe = _text(dedupe_key) or _stable_id("dedupe", worker, text)
    existing = _find_by_dedupe(session, worker, dedupe)
    if existing:
        duplicate_id = _stable_id("dup", worker, dedupe, str(_duplicate_count(session, worker, dedupe) + 1))
        event = {"type": "router_duplicate_detected", "worker_id": worker, "duplicate_message_id": duplicate_id, "existing_message_id": existing["message_id"], "correlation_id": correlation, "dedupe_key": dedupe}
        if now:
            event["at"] = now
        return _session_from_event(session, event), _result("duplicate_detected", worker_id=worker, message_id=existing["message_id"], duplicate=True, event=event)
    message_id = _stable_id("msg", worker, correlation, dedupe)
    event = {"type": "router_message_queued", "worker_id": worker, "message_id": message_id, "correlation_id": correlation, "dedupe_key": dedupe, "message": text, "status": "queued", "attempt": 1}
    if now:
        event["at"] = now
    return _session_from_event(session, event), _result("queued", worker_id=worker, message_id=message_id, correlation_id=correlation, dedupe_key=dedupe, event=event)


def acknowledge_message(session: Mapping[str, Any], message_id: str, *, ack_id: str | None = None, now: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    msg = _require_message(session, message_id)
    event = {"type": "router_message_acknowledged", "message_id": msg["message_id"], "ack_id": _text(ack_id) or msg["message_id"]}
    if now:
        event["at"] = now
    return _session_from_event(session, event), _result("acked", worker_id=msg["worker_id"], message_id=msg["message_id"], event=event)


def fail_message(session: Mapping[str, Any], message_id: str, error: str, *, retryable: bool = True, now: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    msg = _require_message(session, message_id)
    event = {"type": "router_message_failed", "message_id": msg["message_id"], "error": _required_value(error, "error"), "retryable": retryable}
    if now:
        event["at"] = now
    return _session_from_event(session, event), _result("failed", worker_id=msg["worker_id"], message_id=msg["message_id"], retryable=retryable, event=event)


def retry_message(session: Mapping[str, Any], message_id: str, *, now: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    msg = _require_message(session, message_id)
    if msg["status"] != "failed":
        raise RouterError("only failed messages can be retried")
    if msg.get("retryable") is False:
        raise RouterError("message is not retryable")
    attempt = int(msg.get("attempt") or 1) + 1
    new_id = _stable_id("msg", msg["worker_id"], msg["correlation_id"], msg["dedupe_key"], str(attempt))
    event = {"type": "router_message_retried", "original_message_id": msg["message_id"], "message_id": new_id, "correlation_id": msg["correlation_id"], "dedupe_key": f"{msg['dedupe_key']}#retry-{attempt}", "message": msg["message"], "attempt": attempt}
    if now:
        event["at"] = now
    return _session_from_event(session, event), _result("retried", worker_id=msg["worker_id"], message_id=new_id, retry_of=msg["message_id"], event=event)


def ingest_router_report(session: Mapping[str, Any], worker_id: str, report: str, *, status: str = "done", now: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        updated = ingest_worker_report(session, worker_id, report, status=status, now=now)
    except BridgeHostError as exc:
        raise RouterError(str(exc)) from exc
    return updated, _result("report_ingested", worker_id=worker_id, report=report, worker_status=status)


def dumps_router_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _session_from_event(session: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from .bridge_host import _session_from_events as reduce_events  # type: ignore[attr-defined]
        return reduce_events(_events(session) + [dict(event)])
    except BridgeHostError as exc:
        raise RouterError(str(exc)) from exc


def _router_messages(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    messages: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for event in _events(session):
        typ = event.get("type")
        if typ == "router_message_queued":
            msg = {"worker_id": _required_value(event.get("worker_id"), "worker_id"), "message_id": _required_value(event.get("message_id"), "message_id"), "correlation_id": _required_value(event.get("correlation_id"), "correlation_id"), "dedupe_key": _required_value(event.get("dedupe_key"), "dedupe_key"), "message": _required_value(event.get("message"), "message"), "status": _text(event.get("status")) or "queued", "attempt": int(event.get("attempt") or 1), "retryable": True}
            messages[msg["message_id"]] = msg
            order.append(msg["message_id"])
        elif typ == "router_message_acknowledged":
            msg = messages.get(_text(event.get("message_id")))
            if msg:
                msg["status"] = "acked"
                msg["ack_id"] = _text(event.get("ack_id")) or msg["message_id"]
        elif typ == "router_message_failed":
            msg = messages.get(_text(event.get("message_id")))
            if msg:
                msg["status"] = "failed"
                msg["error"] = _text(event.get("error"))
                msg["retryable"] = event.get("retryable") is not False
        elif typ == "router_message_retried":
            original = messages.get(_text(event.get("original_message_id")))
            if original:
                original["status"] = "retried"
            msg = {"worker_id": original["worker_id"] if original else "", "message_id": _required_value(event.get("message_id"), "message_id"), "correlation_id": _required_value(event.get("correlation_id"), "correlation_id"), "dedupe_key": _required_value(event.get("dedupe_key"), "dedupe_key"), "message": _required_value(event.get("message"), "message"), "status": "queued", "attempt": int(event.get("attempt") or 1), "retry_of": _required_value(event.get("original_message_id"), "original_message_id"), "retryable": True}
            messages[msg["message_id"]] = msg
            order.append(msg["message_id"])
    return [messages[key] for key in order if key in messages]


def _find_by_dedupe(session: Mapping[str, Any], worker_id: str, dedupe_key: str) -> dict[str, Any] | None:
    for msg in _router_messages(session):
        if msg["worker_id"] == worker_id and msg["dedupe_key"] == dedupe_key and msg["status"] in {"queued", "acked", "failed"}:
            return msg
    return None


def _duplicate_count(session: Mapping[str, Any], worker_id: str, dedupe_key: str) -> int:
    return sum(1 for event in _events(session) if event.get("type") == "router_duplicate_detected" and event.get("worker_id") == worker_id and event.get("dedupe_key") == dedupe_key)


def _require_message(session: Mapping[str, Any], message_id: str) -> dict[str, Any]:
    wanted = _required_value(message_id, "message_id")
    for msg in _router_messages(session):
        if msg["message_id"] == wanted:
            return msg
    raise RouterError(f"unknown message_id: {wanted}")


def _require_worker(session: Mapping[str, Any], worker_id: str) -> str:
    worker = _required_value(worker_id, "worker_id")
    try:
        model = materialize_bridge_host(session)
    except BridgeHostError as exc:
        raise RouterError(f"invalid bridge host session: {exc}") from exc
    if worker not in {row.get("worker_id") for row in model.get("worker_rows", []) if isinstance(row, Mapping)}:
        raise RouterError(f"unknown worker_id: {worker}")
    return worker


def _events(session: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    events = session.get("events")
    if not isinstance(events, list):
        raise RouterError("session.events must be a list")
    return [event for event in events if isinstance(event, Mapping)]


def _result(result_status: str, **extra: Any) -> dict[str, Any]:
    payload = {"schema_version": 1, "kind": "collab_router_result", "phase": 11, "status": result_status}
    payload.update(extra)
    return payload


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _required_value(value: Any, field: str) -> str:
    text = _text(value)
    if not text:
        raise RouterError(f"{field} is required")
    return text


def _text(value: Any) -> str:
    return str(value or "").strip()
