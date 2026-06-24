"""Phase 9 standalone worker runtime alpha for the collab bridge.

This module runs only operator-configured commands and only when the caller
passes an explicit allow-spawn flag. It is intentionally not a wrapper around
the lead Codex/Claude CLI: the bridge owns worker runtime events, while the
lead CLI remains an optional caller in later phases.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .bridge_host import BridgeHostError, materialize_bridge_host, record_worker_runtime_result
from .errors import CollabError


class WorkerRuntimeError(CollabError):
    """Raised when a Phase 9 worker runtime request is invalid."""

    error_code = "COLLAB_WORKER_RUNTIME_INVALID_INPUT"


def build_worker_runtime_request(
    session: Mapping[str, Any],
    worker_id: str,
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Return a non-spawning request object for a bridge-owned worker command."""

    _require_worker(session, worker_id)
    command_list = _validate_command(command)
    timeout = _validate_timeout(timeout_seconds)
    return {
        "schema_version": 1,
        "kind": "collab_worker_runtime_request",
        "phase": 9,
        "worker_id": _text(worker_id),
        "runtime_mode": "operator_command",
        "command": command_list,
        "cwd": str(cwd) if cwd is not None else None,
        "timeout_seconds": timeout,
        "spawns_process_now": False,
        "allow_spawn_required": True,
        "lead_cli_wrapped": False,
        "codex_claude_e2e_verified": False,
        "notes": [
            "This request is a blueprint only; it does not spawn until allow_spawn is true.",
            "A generic command-worker run proves the bridge-owned process path, not a Codex/Claude E2E unless the operator command is Codex/Claude and is verified separately.",
        ],
    }


def run_worker_command(
    session: Mapping[str, Any],
    worker_id: str,
    command: Sequence[str],
    *,
    allow_spawn: bool = False,
    timeout_seconds: float = 30.0,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Run an operator-configured worker command and capture a stable result."""

    request = build_worker_runtime_request(session, worker_id, command, cwd=cwd, timeout_seconds=timeout_seconds)
    if not allow_spawn:
        raise WorkerRuntimeError("allow_spawn=true is required before starting a worker process")
    timeout = request["timeout_seconds"]
    command_list = list(request["command"])
    cwd_text = _validate_cwd(cwd)
    try:
        completed = subprocess.run(
            command_list,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            cwd=cwd_text,
            check=False,
        )
        exit_code: int | None = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = _decode_timeout_stream(exc.stdout)
        stderr = _decode_timeout_stream(exc.stderr) or f"command timed out after {timeout} seconds"
        timed_out = True
    except OSError as exc:
        exit_code = None
        stdout = ""
        stderr = str(exc)
        timed_out = False
    status = "done" if exit_code == 0 and not timed_out else "error"
    report = _report_from_streams(status=status, exit_code=exit_code, stdout=stdout, stderr=stderr)
    return {
        "schema_version": 1,
        "kind": "collab_worker_runtime_result",
        "phase": 9,
        "worker_id": _text(worker_id),
        "runtime_mode": "operator_command",
        "command": command_list,
        "cwd": cwd_text,
        "timeout_seconds": timeout,
        "exit_code": exit_code,
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "spawns_process_now": True,
        "real_worker_lifecycle": True,
        "lead_cli_wrapped": False,
        "codex_claude_e2e_verified": False,
        "report": report,
    }


def apply_runtime_result(
    session: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Append a runtime result event to a bridge host session and replay it."""

    if result.get("kind") != "collab_worker_runtime_result":
        raise WorkerRuntimeError("result.kind must be collab_worker_runtime_result")
    try:
        return record_worker_runtime_result(session, result, now=now)
    except BridgeHostError as exc:
        raise WorkerRuntimeError(f"failed to apply worker runtime result: {exc}") from exc


def build_runtime_run_payload(session: Mapping[str, Any], result: Mapping[str, Any], *, event_log_updated: bool) -> dict[str, Any]:
    """Build the CLI JSON payload after a worker command run."""

    return {
        "schema_version": 1,
        "kind": "collab_worker_runtime_run",
        "phase": 9,
        "event_log_updated": event_log_updated,
        "result": dict(result),
        "materialized": materialize_bridge_host(session),
    }


def dumps_worker_runtime_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _require_worker(session: Mapping[str, Any], worker_id: str) -> None:
    worker = _text(worker_id)
    if not worker:
        raise WorkerRuntimeError("worker_id is required")
    try:
        model = materialize_bridge_host(session)
    except BridgeHostError as exc:
        raise WorkerRuntimeError(f"invalid bridge host session: {exc}") from exc
    workers = {str(item.get("worker_id") or "") for item in model.get("worker_rows", []) if isinstance(item, Mapping)}
    if worker not in workers:
        raise WorkerRuntimeError(f"unknown worker_id: {worker}")


def _validate_command(command: Sequence[str]) -> list[str]:
    if isinstance(command, (str, bytes)):
        raise WorkerRuntimeError("command must be a list of arguments, not a shell string")
    try:
        command_list = [_text(item) for item in command]
    except TypeError as exc:
        raise WorkerRuntimeError("command must be a sequence of arguments") from exc
    if not command_list or any(not item for item in command_list):
        raise WorkerRuntimeError("command must contain at least one non-empty argument")
    return command_list


def _validate_timeout(timeout_seconds: float) -> float:
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError) as exc:
        raise WorkerRuntimeError("timeout_seconds must be a positive number") from exc
    if timeout <= 0:
        raise WorkerRuntimeError("timeout_seconds must be positive")
    return timeout


def _validate_cwd(cwd: str | Path | None) -> str | None:
    if cwd is None:
        return None
    path = Path(cwd)
    if not path.exists():
        raise WorkerRuntimeError(f"cwd does not exist: {path}")
    if not path.is_dir():
        raise WorkerRuntimeError(f"cwd is not a directory: {path}")
    return str(path)


def _decode_timeout_stream(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _report_from_streams(*, status: str, exit_code: int | None, stdout: str, stderr: str) -> str:
    if stdout.strip():
        return stdout.strip()[:4000]
    if stderr.strip():
        return stderr.strip()[:4000]
    return f"runtime status={status} exit_code={exit_code}"


def _text(value: Any) -> str:
    return str(value or "").strip()
