"""Phase 14 worker supervisor for bridge-owned worker processes.

The supervisor owns worker child processes inside the bridge process. It is not a
wrapper around the lead CLI. CLI tests use short Python fixtures; real Codex or
Claude workers remain Phase 13/P15 explicit probes.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import CollabError


class WorkerSupervisorError(CollabError):
    """Raised when a Phase 14 supervisor request is invalid."""

    error_code = "COLLAB_WORKER_SUPERVISOR_INVALID_INPUT"


class WorkerSupervisor:
    """Small in-process supervisor with stdout/stderr capture and stop/timeout."""

    def __init__(self) -> None:
        self._workers: dict[str, dict[str, Any]] = {}

    def start_worker(
        self,
        worker_id: str,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        worker = _required_text(worker_id, "worker_id")
        if worker in self._workers and self._workers[worker]["process"].poll() is None:
            raise WorkerSupervisorError(f"worker already running: {worker}")
        command_list = _command_list(command)
        cwd_text = _validate_cwd(cwd)
        timeout = _optional_timeout(timeout_seconds)
        try:
            process = subprocess.Popen(
                command_list,
                cwd=cwd_text,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise WorkerSupervisorError(str(exc)) from exc
        stdout_q: queue.Queue[str] = queue.Queue()
        stderr_q: queue.Queue[str] = queue.Queue()
        threads = [
            _start_reader(process.stdout, stdout_q),
            _start_reader(process.stderr, stderr_q),
        ]
        self._workers[worker] = {
            "worker_id": worker,
            "command": command_list,
            "cwd": cwd_text,
            "timeout_seconds": timeout,
            "started_at": time.monotonic(),
            "process": process,
            "stdout": stdout_q,
            "stderr": stderr_q,
            "threads": threads,
            "last_status": "running",
        }
        return _event("supervisor_worker_started", worker, command=command_list, cwd=cwd_text, pid=process.pid, timeout_seconds=timeout, status="running")

    def send_to_worker(self, worker_id: str, message: str) -> dict[str, Any]:
        item = self._item(worker_id)
        process: subprocess.Popen[str] = item["process"]
        if process.poll() is not None:
            raise WorkerSupervisorError(f"worker is not running: {worker_id}")
        text = str(message)
        if process.stdin is None:
            raise WorkerSupervisorError("worker stdin is not available")
        process.stdin.write(text + "\n")
        process.stdin.flush()
        return _event("supervisor_message_sent", item["worker_id"], message=text, status="running")

    def read_worker(self, worker_id: str) -> dict[str, Any]:
        item = self._item(worker_id)
        stdout = _drain(item["stdout"])
        stderr = _drain(item["stderr"])
        status = self._status_for(item)
        return _event("supervisor_worker_read", item["worker_id"], stdout=stdout, stderr=stderr, status=status, returncode=item["process"].poll())

    def worker_status(self, worker_id: str) -> dict[str, Any]:
        item = self._item(worker_id)
        status = self._status_for(item)
        return _event("supervisor_worker_status", item["worker_id"], status=status, returncode=item["process"].poll(), pid=item["process"].pid)

    def stop_worker(self, worker_id: str, *, grace_seconds: float = 2.0) -> dict[str, Any]:
        item = self._item(worker_id)
        process: subprocess.Popen[str] = item["process"]
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=max(0.1, grace_seconds))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        status = "stopped" if process.returncode == 0 or process.returncode is not None else "error"
        item["last_status"] = status
        return _event("supervisor_worker_stopped", item["worker_id"], status=status, returncode=process.returncode)

    def enforce_timeout(self, worker_id: str) -> dict[str, Any] | None:
        item = self._item(worker_id)
        timeout = item.get("timeout_seconds")
        if timeout is None or item["process"].poll() is not None:
            return None
        elapsed = time.monotonic() - float(item["started_at"])
        if elapsed <= float(timeout):
            return None
        item["process"].kill()
        item["process"].wait(timeout=2)
        item["last_status"] = "timeout"
        return _event("supervisor_worker_timeout", item["worker_id"], status="timeout", elapsed_seconds=round(elapsed, 3), returncode=item["process"].returncode)

    def _item(self, worker_id: str) -> dict[str, Any]:
        worker = _required_text(worker_id, "worker_id")
        if worker not in self._workers:
            raise WorkerSupervisorError(f"unknown worker_id: {worker}")
        return self._workers[worker]

    def _status_for(self, item: Mapping[str, Any]) -> str:
        if item.get("last_status") == "timeout":
            return "timeout"
        code = item["process"].poll()
        if code is None:
            return "running"
        if code == 0:
            return "exited"
        return "crashed"


def build_supervisor_snapshot(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    workers: dict[str, dict[str, Any]] = {}
    for raw in events:
        event = dict(raw)
        worker_id = str(event.get("worker_id") or "")
        if not worker_id:
            continue
        row = workers.setdefault(worker_id, {"worker_id": worker_id, "status": "unknown", "stdout": [], "stderr": [], "messages": 0, "events": 0})
        row["events"] += 1
        typ = str(event.get("type") or "")
        if typ == "supervisor_worker_started":
            row["status"] = "running"
            row["command"] = list(event.get("command") or [])
            row["pid"] = event.get("pid")
        elif typ == "supervisor_message_sent":
            row["messages"] += 1
        elif typ == "supervisor_worker_read":
            row["stdout"].extend(list(event.get("stdout") or []))
            row["stderr"].extend(list(event.get("stderr") or []))
            row["status"] = str(event.get("status") or row["status"])
        elif typ in {"supervisor_worker_status", "supervisor_worker_stopped", "supervisor_worker_timeout"}:
            row["status"] = str(event.get("status") or row["status"])
            row["returncode"] = event.get("returncode")
    rows = list(workers.values())
    return {
        "schema_version": 1,
        "kind": "collab_worker_supervisor_snapshot",
        "phase": 14,
        "summary": {"worker_count": len(rows), "event_count": len(list(events)), "running": sum(1 for row in rows if row.get("status") == "running"), "crashed": sum(1 for row in rows if row.get("status") == "crashed"), "timeout": sum(1 for row in rows if row.get("status") == "timeout")},
        "worker_rows": rows,
    }


def append_supervisor_events(path: str | Path, events: Sequence[Mapping[str, Any]]) -> None:
    event_path = Path(path)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(dict(event), ensure_ascii=False, sort_keys=True) + "\n")


def load_supervisor_events(path: str | Path) -> list[dict[str, Any]]:
    event_path = Path(path)
    if not event_path.exists():
        return []
    out: list[dict[str, Any]] = []
    for index, line in enumerate(event_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkerSupervisorError(f"event log line {index} is invalid JSON: {exc}") from exc
        if isinstance(payload, Mapping):
            out.append(dict(payload))
    return out


def dumps_supervisor_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _start_reader(stream: Any, out: queue.Queue[str]) -> threading.Thread:
    def run() -> None:
        if stream is None:
            return
        try:
            for line in stream:
                out.put(line.rstrip("\n"))
        finally:
            try:
                stream.close()
            except Exception:
                pass
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _drain(q: queue.Queue[str]) -> list[str]:
    lines: list[str] = []
    while True:
        try:
            lines.append(q.get_nowait())
        except queue.Empty:
            return lines


def _event(event_type: str, worker_id: str, **fields: Any) -> dict[str, Any]:
    return {"schema_version": 1, "phase": 14, "type": event_type, "worker_id": worker_id, **fields}


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkerSupervisorError(f"{field} is required")
    return text


def _command_list(command: Sequence[str]) -> list[str]:
    if isinstance(command, (str, bytes)):
        raise WorkerSupervisorError("command must be a list of arguments, not a shell string")
    items = [str(item) for item in command]
    if not items or any(not item for item in items):
        raise WorkerSupervisorError("command must contain at least one non-empty argument")
    return items


def _validate_cwd(cwd: str | Path | None) -> str | None:
    if cwd is None:
        return None
    path = Path(cwd)
    if not path.exists() or not path.is_dir():
        raise WorkerSupervisorError(f"cwd must be an existing directory: {path}")
    return str(path)


def _optional_timeout(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise WorkerSupervisorError("timeout_seconds must be a positive number") from exc
    if timeout <= 0:
        raise WorkerSupervisorError("timeout_seconds must be positive")
    return timeout
