"""Stable collaboration error codes and CLI JSON error helpers."""
from __future__ import annotations

import json
from typing import Any

DEFAULT_ERROR_CODE = "COLLAB_ERROR"
_CLASS_ERROR_CODES = {
    "ConfigError": "COLLAB_CONFIG_INVALID",
    "StateError": "COLLAB_STATE_INVALID",
    "ReplayError": "COLLAB_REPLAY_INVALID",
    "DispatchError": "COLLAB_DISPATCH_INVALID",
    "QueueError": "COLLAB_QUEUE_INVALID",
    "RecoverError": "COLLAB_RECOVER_INVALID_INPUT",
}
_MESSAGE_ERROR_CODES = {
    "concurrency": "COLLAB_QUEUE_CONCURRENCY_LIMIT",
    "no queued item": "COLLAB_QUEUE_EMPTY",
    "lease not found": "COLLAB_QUEUE_LEASE_NOT_FOUND",
    "unknown lease_id": "COLLAB_QUEUE_LEASE_NOT_FOUND",
}


class CollabError(ValueError):
    """Base collaboration error carrying a stable machine-readable code."""

    error_code = DEFAULT_ERROR_CODE

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        if error_code:
            self.error_code = error_code

    def to_dict(self) -> dict[str, Any]:
        message = str(self)
        return {
            "ok": False,
            "error": message,
            "error_code": code_for_exception(self),
            "message": message,
            "details": {},
        }


def code_for_exception(exc: BaseException) -> str:
    """Return a stable error code for known collab exceptions."""

    explicit = getattr(exc, "error_code", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    name = exc.__class__.__name__
    if name in _CLASS_ERROR_CODES:
        text = str(exc).lower()
        if name == "QueueError":
            for needle, code in _MESSAGE_ERROR_CODES.items():
                if needle in text:
                    return code
        return _CLASS_ERROR_CODES[name]
    return DEFAULT_ERROR_CODE


def error_payload(kind: str, exc: BaseException, **extra: Any) -> dict[str, Any]:
    """Build the additive JSON CLI error contract.

    The compatibility fields ``kind``, ``error``, and ``error_code`` are kept,
    while the stronger contract adds ``ok:false``, ``message``, and object
    ``details`` for downstream tooling.
    """

    message = str(exc)
    details = extra.pop("details", {})
    if details is None:
        details = {}
    if not isinstance(details, dict):
        details = {"value": details}
    payload: dict[str, Any] = {
        "ok": False,
        "kind": kind,
        "error": message,
        "error_code": code_for_exception(exc),
        "message": message,
        "details": details,
    }
    payload.update(extra)
    return payload


def dumps_json(payload: dict[str, Any]) -> str:
    """Serialize stable UTF-8 JSON for collab CLIs."""

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
