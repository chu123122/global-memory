"""Phase 13 real Codex/Claude worker probe helpers.

This module is deliberately narrower than a general process runner. It builds
known-safe non-interactive Codex/Claude worker commands, classifies their real
CLI results, and can ingest the result into the bridge event log. Tests may use
fixture result objects for classification, but a Phase 13 acceptance claim must
come from an actual ``codex`` or ``claude`` command line probe.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from .bridge_host import BridgeHostError, materialize_bridge_host, record_worker_runtime_result
from .errors import CollabError
from .worker_runtime import WorkerRuntimeError, run_worker_command


class RealWorkerError(CollabError):
    """Raised when a Phase 13 real CLI worker probe is invalid."""

    error_code = "COLLAB_REAL_WORKER_INVALID_INPUT"


_ALLOWED_RUNTIMES = {"codex", "claude"}
_BUDGET_MARKERS = ["ExceededBudget", "Max budget limit reached", "over budget", "429"]
_AUTH_MARKERS = ["not logged in", "login", "unauthorized", "invalid api key", "invalid token"]
_MISSING_MARKERS = ["not recognized", "No such file", "cannot find", "not found", "WinError 2", "系统找不到指定的文件"]


def build_real_worker_command(
    runtime: str,
    prompt: str,
    *,
    cwd: str | Path | None = None,
    output_file: str | Path | None = None,
    debug_log: str | Path | None = None,
    timeout_seconds: float = 180.0,
) -> dict[str, Any]:
    """Return a non-spawning real Codex/Claude worker command request."""

    cli = _runtime(runtime)
    prompt_text = _required_text(prompt, "prompt")
    timeout = _positive_timeout(timeout_seconds)
    cwd_text = str(cwd) if cwd is not None else None
    artifacts: dict[str, str] = {}
    if cli == "codex":
        command = [_resolve_cli("codex"), "exec", "--ephemeral", "--skip-git-repo-check"]
        if cwd_text:
            command += ["-C", cwd_text]
        command += ["-s", "read-only"]
        if output_file is not None:
            artifacts["output_file"] = str(output_file)
            command += ["-o", str(output_file)]
        command.append(prompt_text)
    else:
        command = [
            _resolve_cli("claude"),
            "--print",
            "--output-format",
            "json",
            "--permission-mode",
            "acceptEdits",
            "--max-turns",
            "1",
        ]
        if debug_log is not None:
            artifacts["debug_log"] = str(debug_log)
            command += ["--debug-file", str(debug_log)]
        command.append(prompt_text)
    return {
        "schema_version": 1,
        "kind": "collab_real_worker_request",
        "phase": 13,
        "runtime": cli,
        "runtime_mode": f"{cli}_cli_worker",
        "prompt": prompt_text,
        "command": command,
        "cwd": cwd_text,
        "timeout_seconds": timeout,
        "artifacts": artifacts,
        "spawns_process_now": False,
        "allow_spawn_required": True,
        "lead_cli_wrapped": False,
        "real_cli_e2e_claimed": False,
    }


def build_real_worker_result(
    runtime: str,
    runtime_result: Mapping[str, Any],
    *,
    expected_text: str | None = None,
    output_file_text: str | None = None,
    debug_log_text: str | None = None,
    artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a generic worker runtime result into Phase 13 evidence."""

    cli = _runtime(runtime)
    classification = classify_real_worker_result(
        cli,
        runtime_result,
        expected_text=expected_text,
        output_file_text=output_file_text,
        debug_log_text=debug_log_text,
    )
    status = "done" if classification["status"] == "ok" else "error"
    report = _report_from_real_evidence(classification, runtime_result, output_file_text, debug_log_text)
    return {
        "schema_version": 1,
        "kind": "collab_real_worker_result",
        "phase": 13,
        "worker_id": _required_text(runtime_result.get("worker_id"), "worker_id"),
        "runtime": cli,
        "runtime_mode": f"{cli}_cli_worker",
        "command": list(runtime_result.get("command") or []),
        "cwd": runtime_result.get("cwd"),
        "timeout_seconds": runtime_result.get("timeout_seconds"),
        "exit_code": runtime_result.get("exit_code"),
        "status": status,
        "stdout": str(runtime_result.get("stdout") or ""),
        "stderr": str(runtime_result.get("stderr") or ""),
        "timed_out": runtime_result.get("timed_out") is True,
        "spawns_process_now": runtime_result.get("spawns_process_now") is True,
        "real_worker_lifecycle": True,
        "lead_cli_wrapped": False,
        "codex_claude_e2e_verified": classification["status"] == "ok",
        "real_cli_e2e_verified": classification["status"] == "ok",
        "classification": classification,
        "artifacts": dict(artifacts or {}),
        "report": report,
    }


def run_real_worker_probe(
    session: Mapping[str, Any],
    worker_id: str,
    runtime: str,
    prompt: str,
    *,
    allow_spawn: bool = False,
    cwd: str | Path | None = None,
    timeout_seconds: float = 180.0,
    expected_text: str | None = None,
    output_file: str | Path | None = None,
    debug_log: str | Path | None = None,
) -> dict[str, Any]:
    """Run a real Codex/Claude worker probe and return classified evidence."""

    request = build_real_worker_command(
        runtime,
        prompt,
        cwd=cwd,
        output_file=output_file,
        debug_log=debug_log,
        timeout_seconds=timeout_seconds,
    )
    if not allow_spawn:
        raise RealWorkerError("allow_spawn=true is required before starting a real Codex/Claude worker probe")
    try:
        runtime_result = run_worker_command(
            session,
            worker_id,
            request["command"],
            allow_spawn=True,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
        )
    except WorkerRuntimeError as exc:
        raise RealWorkerError(str(exc)) from exc
    output_text = _read_optional(output_file)
    debug_text = _read_optional(debug_log)
    result = build_real_worker_result(
        request["runtime"],
        runtime_result,
        expected_text=expected_text,
        output_file_text=output_text,
        debug_log_text=debug_text,
        artifacts=request.get("artifacts") or {},
    )
    result["request"] = request
    return result


def classify_real_worker_result(
    runtime: str,
    result: Mapping[str, Any],
    *,
    expected_text: str | None = None,
    output_file_text: str | None = None,
    debug_log_text: str | None = None,
) -> dict[str, Any]:
    """Classify a real CLI worker result without hiding blocked CLIs."""

    cli = _runtime(runtime)
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    debug = debug_log_text or ""
    output = output_file_text or ""
    merged = "\n".join([stdout, stderr, debug, output])
    lower = merged.lower()
    exit_code = result.get("exit_code")
    timed_out = result.get("timed_out") is True
    expected = str(expected_text or "").strip()
    expected_found = bool(expected and expected in merged)
    if any(marker.lower() in lower for marker in _BUDGET_MARKERS):
        status = "blocked_budget"
        reason = "provider budget or 429 limit reached"
    elif any(marker.lower() in lower for marker in _MISSING_MARKERS):
        status = "missing_cli"
        reason = "CLI executable or command was not available"
    elif any(marker.lower() in lower for marker in _AUTH_MARKERS):
        status = "auth_required"
        reason = "CLI authentication or token is required"
    elif timed_out:
        status = "timeout"
        reason = "real CLI probe timed out"
    elif exit_code == 0 and (not expected or expected_found):
        status = "ok"
        reason = "real CLI worker probe completed and expected marker matched" if expected else "real CLI worker probe completed"
    elif exit_code == 0 and expected and not expected_found:
        status = "unexpected_output"
        reason = "CLI exited successfully but expected marker was not found"
    else:
        status = "runtime_error"
        reason = "CLI exited non-zero or produced an unclassified failure"
    return {
        "runtime": cli,
        "status": status,
        "reason": reason,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "expected_text": expected or None,
        "expected_text_found": expected_found if expected else None,
        "stdout_excerpt": stdout.strip()[:500],
        "stderr_excerpt": stderr.strip()[:500],
        "debug_log_excerpt": debug.strip()[:500],
        "output_file_excerpt": output.strip()[:500],
    }


def apply_real_worker_result(
    session: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Append classified real CLI worker evidence to the bridge event log."""

    if result.get("kind") != "collab_real_worker_result":
        raise RealWorkerError("result.kind must be collab_real_worker_result")
    event_result = dict(result)
    event_result["kind"] = "collab_worker_runtime_result"
    event_result["report"] = str(result.get("report") or "")[:4000]
    try:
        return record_worker_runtime_result(session, event_result, now=now)
    except BridgeHostError as exc:
        raise RealWorkerError(f"failed to apply real worker result: {exc}") from exc


def build_real_worker_probe_payload(session: Mapping[str, Any], result: Mapping[str, Any], *, event_log_updated: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "collab_real_worker_probe",
        "phase": 13,
        "event_log_updated": event_log_updated,
        "result": dict(result),
        "materialized": materialize_bridge_host(session),
    }


def dumps_real_worker_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _resolve_cli(name: str) -> str:
    """Resolve Windows shim executables for subprocess(shell=False)."""

    if name == "codex":
        return shutil.which("codex.cmd") or shutil.which("codex.exe") or shutil.which("codex") or "codex"
    if name == "claude":
        return shutil.which("claude.exe") or shutil.which("claude.cmd") or shutil.which("claude") or "claude"
    return shutil.which(name) or name


def _runtime(runtime: str) -> str:
    cli = str(runtime or "").strip().lower()
    if cli not in _ALLOWED_RUNTIMES:
        raise RealWorkerError(f"runtime must be one of {sorted(_ALLOWED_RUNTIMES)}")
    return cli


def _positive_timeout(value: float) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise RealWorkerError("timeout_seconds must be a positive number") from exc
    if timeout <= 0:
        raise RealWorkerError("timeout_seconds must be positive")
    return timeout


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RealWorkerError(f"{field} is required")
    return text


def _read_optional(path: str | Path | None) -> str | None:
    if path is None:
        return None
    try:
        p = Path(path)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


def _report_from_real_evidence(
    classification: Mapping[str, Any],
    result: Mapping[str, Any],
    output_file_text: str | None,
    debug_log_text: str | None,
) -> str:
    if output_file_text and output_file_text.strip():
        return output_file_text.strip()[:4000]
    stdout = str(result.get("stdout") or "").strip()
    if stdout:
        return stdout[:4000]
    stderr = str(result.get("stderr") or "").strip()
    if stderr:
        return stderr[:4000]
    debug = str(debug_log_text or "").strip()
    if debug:
        return debug[:4000]
    return f"real worker {classification.get('runtime')} status={classification.get('status')}"
