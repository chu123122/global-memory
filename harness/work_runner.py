"""Deterministic work runner for worker/verifier gate loops.

The runner owns state, the verifier owns pass/fail, and worker output is
untrusted.  GM-R2 adds a ``codex exec`` worker adapter without letting Codex
final answers advance state directly.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1
RUNNER_PROFILE = "work-runner/v1"
PROCESS_PASS = "process-pass"
PROCESS_FAIL = "process-fail"
RUNNER_INFRA_FAIL = "runner-infra-fail"
FORBIDDEN_FAILURE_CODE = "WORK_RUNNER_FORBIDDEN_SCOPE_TOUCHED"
FAKE_FAILURE_CODE = "FAKE_WORKER_REPORTED_FAIL"
INVALID_WORKER_CODE = "WORK_RUNNER_INVALID_WORKER_OUTPUT"
VERIFIER_FAILURE_CODE = "WORK_RUNNER_VERIFIER_FAILED"
VERIFIER_EXCEPTION_CODE = "WORK_RUNNER_VERIFIER_EXCEPTION"
VERIFIER_TIMEOUT_CODE = "WORK_RUNNER_VERIFIER_TIMEOUT"
CODEX_EXEC_NONZERO_CODE = "CODEX_EXEC_NONZERO"
CODEX_EXEC_TIMEOUT_CODE = "CODEX_EXEC_TIMEOUT"
CODEX_EXEC_EXCEPTION_CODE = "CODEX_EXEC_EXCEPTION"
REPAIR_LIMIT_CODE = "WORK_RUNNER_REPAIR_LIMIT_REACHED"
REPAIR_LIMIT_KIND = "repair-limit"
DEFAULT_MAX_ATTEMPTS_PER_GATE = 3
DEFAULT_MAX_REPAIR_ATTEMPTS = 3
DEFAULT_CODEX_TIMEOUT_SEC = 300
DEFAULT_REPO_ROOT = Path(r"D:\global-memory")
DEFAULT_VERIFIER_COMMANDS: tuple[tuple[str, ...], ...] = (
    (sys.executable, "-m", "pytest", r"harness\tests\test_work_runner.py", "-q"),
)
ALLOWED_WORKERS = {"fake", "codex-exec"}
ALLOWED_FAKE_RESULTS = {"pass", "fail", "touch-forbidden"}
RUNNER_OWNED_FILES = ("run-state.json", "gate-feedback.json", "runner-log.jsonl")


class WorkRunnerError(ValueError):
    """Raised for invalid runner input or state artifacts."""


@dataclass(frozen=True)
class GateResult:
    """Verifier result for a worker output."""

    gate: str
    failure_code: str | None = None
    message: str = ""
    forbidden_paths: tuple[str, ...] = ()
    gate_exit_code: int | None = None
    worker_exit_code: int | None = None
    failure_kind: str | None = None
    gate_command: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.gate == PROCESS_PASS


@dataclass(frozen=True)
class WorkerRunResult:
    exit_code: int | None
    prompt_path: Path
    worker_jsonl_path: Path
    last_message_path: Path
    stdout: bytes = b""
    stderr: bytes = b""
    failure_code: str | None = None
    failure_message: str = ""


@dataclass(frozen=True)
class VerifierRunResult:
    exit_code: int
    command: tuple[str, ...] = ()
    failure_code: str | None = None
    failure_message: str = ""
    stdout: bytes = b""
    stderr: bytes = b""


def run_once(
    *,
    run_root: str | Path,
    task_id: str,
    step: str,
    worker: str,
    fake_result: str | None = None,
    fake_declared_modified_paths: Sequence[str] | None = None,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    timeout_sec: int = DEFAULT_CODEX_TIMEOUT_SEC,
    allowed_next_step: str | None = None,
    codex_command: str | Sequence[str] = "codex",
    verifier_commands: Sequence[Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Run one worker attempt and persist runner-owned artifacts."""

    run_root_path = Path(run_root)
    repo_root_path = Path(repo_root)
    if worker not in ALLOWED_WORKERS:
        raise WorkRunnerError(f"worker must be one of {sorted(ALLOWED_WORKERS)}")
    if worker == "fake" and fake_result not in ALLOWED_FAKE_RESULTS:
        raise WorkRunnerError(f"fake_result must be one of {sorted(ALLOWED_FAKE_RESULTS)} when worker=fake")
    task_id = _required_text(task_id, "task_id")
    step = _required_text(step, "step")
    timeout = _positive_int(timeout_sec, DEFAULT_CODEX_TIMEOUT_SEC)

    paths = _runner_paths(run_root_path)
    run_root_path.mkdir(parents=True, exist_ok=True)
    paths["worker_dir"].mkdir(parents=True, exist_ok=True)
    paths["input_dir"].mkdir(parents=True, exist_ok=True)

    previous_state = _load_state(paths["state"], task_id=task_id, step=step, worker=worker)
    if allowed_next_step:
        previous_state = dict(previous_state)
        previous_state["allowed_next_step"] = str(allowed_next_step).strip()

    if worker == "fake":
        before_worker = _snapshot_runner_owned(run_root_path)
        worker_payload = _run_fake_worker(
            run_root_path,
            task_id=task_id,
            step=step,
            fake_result=str(fake_result),
            declared_modified_paths=fake_declared_modified_paths,
        )
        runner_owned_changes = _detect_runner_owned_changes(run_root_path, before_worker)
        gate = verify_fake_worker_output(worker_payload, run_root=run_root_path, runner_owned_changes=runner_owned_changes)
        state = _apply_gate(previous_state, gate, task_id=task_id, step=step, worker=worker)
        feedback = _build_feedback(gate, state=state, task_id=task_id, step=step)
        _write_json(paths["feedback"], feedback)
        _write_json(paths["state"], state)
        _append_log(paths["log"], _build_log_event(gate, state=state, task_id=task_id, step=step, worker=worker, worker_jsonl_path=paths["worker_output"]))
        return _build_result(run_root_path, task_id, step, worker, gate, state, feedback, paths, worker_payload)

    prompt_path = _write_worker_prompt(paths["prompt"], task_id=task_id, step=step, run_root=run_root_path, repo_root=repo_root_path, feedback_path=paths["feedback"])
    before_worker = _snapshot_runner_owned(run_root_path)
    worker_result = _run_codex_exec_worker(
        prompt_path=prompt_path,
        repo_root=repo_root_path,
        worker_jsonl_path=paths["codex_jsonl"],
        last_message_path=paths["last_message"],
        timeout_sec=timeout,
        codex_command=codex_command,
    )
    if worker_result.failure_code:
        return _record_runner_infra_failure(paths, previous_state, task_id=task_id, step=step, worker=worker, failure_code=worker_result.failure_code, message=worker_result.failure_message, worker_exit_code=worker_result.exit_code, prompt_path=prompt_path, worker_jsonl_path=worker_result.worker_jsonl_path, last_message_path=worker_result.last_message_path)

    runner_owned_changes = _detect_runner_owned_changes(run_root_path, before_worker)
    if runner_owned_changes:
        gate = GateResult(PROCESS_FAIL, FORBIDDEN_FAILURE_CODE, "worker touched runner-owned files", tuple(runner_owned_changes), worker_exit_code=worker_result.exit_code, failure_kind="verifier")
    else:
        verifier = _run_verifier_commands(verifier_commands if verifier_commands is not None else DEFAULT_VERIFIER_COMMANDS, repo_root=repo_root_path, timeout_sec=timeout)
        if verifier.failure_code:
            return _record_runner_infra_failure(paths, previous_state, task_id=task_id, step=step, worker=worker, failure_code=verifier.failure_code, message=verifier.failure_message, worker_exit_code=worker_result.exit_code, gate_exit_code=verifier.exit_code, prompt_path=prompt_path, worker_jsonl_path=worker_result.worker_jsonl_path, last_message_path=worker_result.last_message_path)
        if verifier.exit_code == 0:
            gate = GateResult(
                PROCESS_PASS,
                message="verifier commands passed",
                gate_exit_code=0,
                worker_exit_code=worker_result.exit_code,
                gate_command=verifier.command,
            )
        else:
            gate = GateResult(
                PROCESS_FAIL,
                VERIFIER_FAILURE_CODE,
                "verifier command failed",
                gate_exit_code=verifier.exit_code,
                worker_exit_code=worker_result.exit_code,
                failure_kind="verifier",
                gate_command=verifier.command,
            )

    state = _apply_gate(previous_state, gate, task_id=task_id, step=step, worker=worker)
    feedback = _build_feedback(gate, state=state, task_id=task_id, step=step)
    _write_json(paths["feedback"], feedback)
    _write_json(paths["state"], state)
    _append_log(paths["log"], _build_log_event(gate, state=state, task_id=task_id, step=step, worker=worker, prompt_path=prompt_path, worker_jsonl_path=worker_result.worker_jsonl_path, last_message_path=worker_result.last_message_path))
    worker_output = {"kind": "codex_exec_output", "exit_code": worker_result.exit_code, "jsonl_path": str(worker_result.worker_jsonl_path), "last_message_path": str(worker_result.last_message_path)}
    return _build_result(run_root_path, task_id, step, worker, gate, state, feedback, paths, worker_output)


def check_once(
    *,
    run_root: str | Path,
    task_id: str,
    step: str,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    timeout_sec: int = DEFAULT_CODEX_TIMEOUT_SEC,
    allowed_next_step: str | None = None,
    verifier_commands: Sequence[Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Run verifier-only work checks and persist runner-owned artifacts.

    Unlike ``run_once(..., worker="codex-exec")``, this path never writes a
    worker prompt and never starts Codex.  It is the explicit ``/work check``
    entrypoint for deterministic gate feedback before a worker repair pass.
    """

    run_root_path = Path(run_root)
    repo_root_path = Path(repo_root)
    task_id = _required_text(task_id, "task_id")
    step = _required_text(step, "step")
    timeout = _positive_int(timeout_sec, DEFAULT_CODEX_TIMEOUT_SEC)
    worker = "verifier-only"

    paths = _runner_paths(run_root_path)
    run_root_path.mkdir(parents=True, exist_ok=True)
    previous_state = _load_state(paths["state"], task_id=task_id, step=step, worker=worker)
    if allowed_next_step:
        previous_state = dict(previous_state)
        previous_state["allowed_next_step"] = str(allowed_next_step).strip()

    verifier = _run_verifier_commands(
        verifier_commands if verifier_commands is not None else DEFAULT_VERIFIER_COMMANDS,
        repo_root=repo_root_path,
        timeout_sec=timeout,
    )
    if verifier.failure_code:
        return _record_runner_infra_failure(
            paths,
            previous_state,
            task_id=task_id,
            step=step,
            worker=worker,
            failure_code=verifier.failure_code,
            message=verifier.failure_message,
            gate_exit_code=verifier.exit_code,
            gate_command=verifier.command,
        )

    if verifier.exit_code == 0:
        gate = GateResult(
            PROCESS_PASS,
            message="verifier commands passed",
            gate_exit_code=0,
            failure_kind="verifier",
            gate_command=verifier.command,
        )
    else:
        gate = GateResult(
            PROCESS_FAIL,
            VERIFIER_FAILURE_CODE,
            "verifier command failed",
            gate_exit_code=verifier.exit_code,
            failure_kind="verifier",
            gate_command=verifier.command,
        )

    state = _apply_check_gate(previous_state, gate, task_id=task_id, step=step, worker=worker)
    feedback = _build_feedback(gate, state=state, task_id=task_id, step=step)
    _write_json(paths["feedback"], feedback)
    _write_json(paths["state"], state)
    _append_log(paths["log"], _build_log_event(gate, state=state, task_id=task_id, step=step, worker=worker))
    verifier_output = {"kind": "verifier_only", "command": list(verifier.command), "exit_code": verifier.exit_code}
    return _build_result(run_root_path, task_id, step, worker, gate, state, feedback, paths, verifier_output)


def repair_loop(
    *,
    run_root: str | Path,
    task_id: str,
    step: str,
    worker: str,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    timeout_sec: int = DEFAULT_CODEX_TIMEOUT_SEC,
    allowed_next_step: str | None = None,
    codex_command: str | Sequence[str] = "codex",
    verifier_commands: Sequence[Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Run a bounded codex-exec repair loop from existing gate feedback.

    ``/work check`` is diagnostic input: it may create ``gate-feedback.json``
    but it never consumes a repair attempt.  A repair attempt is consumed only
    when this entrypoint starts a codex-exec worker.  Verifier failures may loop
    up to ``max_repair_attempts``; runner-infra failures stop immediately.
    """

    run_root_path = Path(run_root)
    repo_root_path = Path(repo_root)
    if worker != "codex-exec":
        raise WorkRunnerError("repair worker must be codex-exec")
    task_id = _required_text(task_id, "task_id")
    step = _required_text(step, "step")
    timeout = _positive_int(timeout_sec, DEFAULT_CODEX_TIMEOUT_SEC)

    paths = _runner_paths(run_root_path)
    if not paths["feedback"].exists():
        raise WorkRunnerError("repair requires existing gate-feedback.json")
    feedback = _load_feedback(paths["feedback"])
    if feedback.get("gate") != PROCESS_FAIL:
        raise WorkRunnerError("repair requires gate-feedback.json with gate=process-fail")

    run_root_path.mkdir(parents=True, exist_ok=True)
    state = _load_state(paths["state"], task_id=task_id, step=step, worker=worker)
    if allowed_next_step:
        state = dict(state)
        state["allowed_next_step"] = str(allowed_next_step).strip()
    max_repairs = _positive_int(state.get("max_repair_attempts"), DEFAULT_MAX_REPAIR_ATTEMPTS)
    repair_attempt = _non_negative_int(state.get("repair_attempt"), 0)
    state["max_repair_attempts"] = max_repairs
    state["repair_attempt"] = repair_attempt

    if repair_attempt >= max_repairs:
        return _record_repair_limit(paths, state, task_id=task_id, step=step, worker=worker, last_feedback=feedback)

    last_result: dict[str, Any] | None = None
    while repair_attempt < max_repairs:
        repair_attempt += 1
        state = _load_state(paths["state"], task_id=task_id, step=step, worker=worker)
        if allowed_next_step:
            state = dict(state)
            state["allowed_next_step"] = str(allowed_next_step).strip()
        state["repair_attempt"] = repair_attempt
        state["max_repair_attempts"] = max_repairs
        _write_json(paths["state"], state)

        result = run_once(
            run_root=run_root_path,
            task_id=task_id,
            step=step,
            worker=worker,
            repo_root=repo_root_path,
            timeout_sec=timeout,
            allowed_next_step=allowed_next_step,
            codex_command=codex_command,
            verifier_commands=verifier_commands,
        )
        result = dict(result)
        result["kind"] = "work_runner_repair"
        result["repair_attempt"] = result["state"].get("repair_attempt")
        result["max_repair_attempts"] = result["state"].get("max_repair_attempts")
        last_result = result

        if result["verdict"] == PROCESS_PASS:
            return result
        if result["verdict"] == RUNNER_INFRA_FAIL:
            return result
        if result["verdict"] != PROCESS_FAIL:
            return result

        feedback = result["feedback"]
        state = result["state"]

    if last_result is None:
        return _record_repair_limit(paths, state, task_id=task_id, step=step, worker=worker, last_feedback=feedback)
    return _record_repair_limit(paths, last_result["state"], task_id=task_id, step=step, worker=worker, last_feedback=last_result["feedback"])


def verify_fake_worker_output(
    payload: Mapping[str, Any],
    *,
    run_root: str | Path,
    runner_owned_changes: Sequence[str] = (),
) -> GateResult:
    """Verify fake-worker output without trusting worker claims of completion."""

    if not isinstance(payload, Mapping):
        return GateResult(PROCESS_FAIL, INVALID_WORKER_CODE, "worker output root must be an object")
    changed_paths = tuple(str(path) for path in runner_owned_changes if str(path).strip())
    declared_forbidden = _declared_forbidden_paths(payload, Path(run_root))
    forbidden_paths = tuple(dict.fromkeys(changed_paths + declared_forbidden))
    if forbidden_paths:
        return GateResult(PROCESS_FAIL, FORBIDDEN_FAILURE_CODE, "worker touched runner-owned or out-of-scope files", forbidden_paths, failure_kind="verifier")

    requested_result = str(payload.get("requested_result", "")).strip()
    if requested_result == "touch-forbidden":
        return GateResult(PROCESS_FAIL, FORBIDDEN_FAILURE_CODE, "fake worker requested forbidden-scope touch", ("run-state.json",), failure_kind="verifier")

    result = str(payload.get("result", "")).strip()
    if result == "pass":
        return GateResult(PROCESS_PASS, message="fake worker passed verifier")
    if result == "fail":
        return GateResult(PROCESS_FAIL, FAKE_FAILURE_CODE, "fake worker reported failure", failure_kind="verifier")
    return GateResult(PROCESS_FAIL, INVALID_WORKER_CODE, f"unsupported fake worker result: {result or '<missing>'}", failure_kind="verifier")


def _runner_paths(run_root: Path) -> dict[str, Path]:
    return {
        "state": run_root / "run-state.json",
        "feedback": run_root / "gate-feedback.json",
        "log": run_root / "runner-log.jsonl",
        "worker_dir": run_root / "worker-output",
        "input_dir": run_root / "worker-input",
        "worker_output": run_root / "worker-output" / "fake-worker.json",
        "prompt": run_root / "worker-input" / "prompt.md",
        "codex_jsonl": run_root / "worker-output" / "codex-exec.jsonl",
        "last_message": run_root / "worker-output" / "last-message.md",
    }


def _load_feedback(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkRunnerError(f"gate-feedback.json is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkRunnerError("gate-feedback.json root must be an object")
    return dict(raw)


def _load_state(path: Path, *, task_id: str, step: str, worker: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": f"{task_id}:{step}",
            "task_id": task_id,
            "profile": RUNNER_PROFILE,
            "worker_kind": worker,
            "current_step": step,
            "target_step": step,
            "attempt": 0,
            "max_attempts_per_gate": DEFAULT_MAX_ATTEMPTS_PER_GATE,
            "repair_attempt": 0,
            "max_repair_attempts": DEFAULT_MAX_REPAIR_ATTEMPTS,
            "last_gate": None,
            "blocked_before": None,
            "failure_streak": 0,
            "status": "running",
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkRunnerError(f"run-state.json is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkRunnerError("run-state.json root must be an object")
    state = dict(raw)
    state.setdefault("schema_version", SCHEMA_VERSION)
    state.setdefault("run_id", f"{task_id}:{step}")
    state.setdefault("task_id", task_id)
    state.setdefault("profile", RUNNER_PROFILE)
    state.setdefault("worker_kind", worker)
    state.setdefault("current_step", step)
    state.setdefault("target_step", step)
    state.setdefault("attempt", 0)
    state.setdefault("max_attempts_per_gate", DEFAULT_MAX_ATTEMPTS_PER_GATE)
    state.setdefault("repair_attempt", 0)
    state.setdefault("max_repair_attempts", DEFAULT_MAX_REPAIR_ATTEMPTS)
    state.setdefault("last_gate", None)
    state.setdefault("blocked_before", None)
    state.setdefault("failure_streak", 0)
    state.setdefault("status", "running")
    return state


def _run_fake_worker(
    run_root: Path,
    *,
    task_id: str,
    step: str,
    fake_result: str,
    declared_modified_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    if fake_result == "touch-forbidden":
        claimed_result = "pass"
        declared = ["run-state.json"]
    else:
        claimed_result = fake_result
        declared = list(declared_modified_paths or [])
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "fake_worker_output",
        "worker": "fake",
        "task_id": task_id,
        "step": step,
        "requested_result": fake_result,
        "result": claimed_result,
        "claims_done": claimed_result == "pass",
        "declared_modified_paths": declared,
        "message": f"fake worker claimed {claimed_result}",
    }
    _write_json(run_root / "worker-output" / "fake-worker.json", payload)
    return payload


def _write_worker_prompt(path: Path, *, task_id: str, step: str, run_root: Path, repo_root: Path, feedback_path: Path) -> Path:
    feedback = "(no previous gate feedback)"
    if feedback_path.exists():
        feedback = feedback_path.read_text(encoding="utf-8", errors="replace")
    forbidden = "\n".join(f"- `{name}`" for name in RUNNER_OWNED_FILES)
    prompt = f"""# Work runner worker prompt

Task: `{task_id}`
Step: `{step}`

The runner/verifier owns completion. Your final answer is saved only as worker
output and is not proof of success.

## Hard boundary

Do not create, edit, delete, rename, or overwrite these runner-owned files under
`{run_root}`:

{forbidden}

Only the runner may write those files.

## Paths

- repo root: `{repo_root}`
- run root: `{run_root}`
- worker output dir: `{run_root / 'worker-output'}`

## Gate feedback from previous attempt

```json
{feedback}
```
"""
    _atomic_write_text(path, prompt)
    return path


def _run_codex_exec_worker(*, prompt_path: Path, repo_root: Path, worker_jsonl_path: Path, last_message_path: Path, timeout_sec: int, codex_command: str | Sequence[str]) -> WorkerRunResult:
    command = _build_codex_exec_command(codex_command, repo_root=repo_root, last_message_path=last_message_path)
    stdout = b""
    stderr = b""
    try:
        completed = subprocess.run(list(command), input=prompt_path.read_bytes(), cwd=str(repo_root), capture_output=True, timeout=timeout_sec)
        stdout = _as_bytes(completed.stdout)
        stderr = _as_bytes(completed.stderr)
        _write_bytes(worker_jsonl_path, stdout)
        _ensure_last_message_file(last_message_path, stdout)
    except subprocess.TimeoutExpired as exc:
        stdout = _as_bytes(getattr(exc, "stdout", None) or getattr(exc, "output", None))
        try:
            _write_bytes(worker_jsonl_path, stdout)
            _ensure_last_message_file(last_message_path, stdout)
        except OSError:
            pass
        return WorkerRunResult(None, prompt_path, worker_jsonl_path, last_message_path, stdout=stdout, stderr=_as_bytes(getattr(exc, "stderr", None)), failure_code=CODEX_EXEC_TIMEOUT_CODE, failure_message=f"codex exec timed out after {timeout_sec}s")
    except OSError as exc:
        return WorkerRunResult(None, prompt_path, worker_jsonl_path, last_message_path, failure_code=CODEX_EXEC_EXCEPTION_CODE, failure_message=f"failed to start codex exec: {exc}")

    if completed.returncode != 0:
        return WorkerRunResult(int(completed.returncode), prompt_path, worker_jsonl_path, last_message_path, stdout=stdout, stderr=stderr, failure_code=CODEX_EXEC_NONZERO_CODE, failure_message=f"codex exec exited with {completed.returncode}")
    return WorkerRunResult(int(completed.returncode), prompt_path, worker_jsonl_path, last_message_path, stdout=stdout, stderr=stderr)


def _run_verifier_commands(commands: Sequence[Sequence[str]], *, repo_root: Path, timeout_sec: int) -> VerifierRunResult:
    if not commands:
        return VerifierRunResult(0)
    last = VerifierRunResult(0)
    for command in commands:
        normalized = tuple(str(part) for part in command if str(part).strip())
        if not normalized:
            continue
        try:
            completed = subprocess.run(list(normalized), cwd=str(repo_root), capture_output=True, timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            return VerifierRunResult(124, normalized, VERIFIER_TIMEOUT_CODE, f"verifier command timed out after {timeout_sec}s: {' '.join(normalized)}")
        except OSError as exc:
            return VerifierRunResult(127, normalized, VERIFIER_EXCEPTION_CODE, f"failed to start verifier command: {exc}")
        last = VerifierRunResult(int(completed.returncode), normalized, stdout=_as_bytes(completed.stdout), stderr=_as_bytes(completed.stderr))
        if last.exit_code != 0:
            return last
    return last


def _build_codex_exec_command(codex_command: str | Sequence[str], *, repo_root: Path, last_message_path: Path) -> tuple[str, ...]:
    prefix = _normalize_command(codex_command)
    if not prefix:
        raise WorkRunnerError("codex_command is required")
    return prefix + ("exec", "--json", "--sandbox", "workspace-write", "--cd", str(repo_root), "--output-last-message", str(last_message_path))


def _normalize_command(command: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(command, str):
        text = command.strip()
        if not text:
            return ()
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise WorkRunnerError("command JSON must be a list")
            return tuple(str(part) for part in parsed)
        return (text,)
    return tuple(str(part) for part in command)

def _record_runner_infra_failure(paths: Mapping[str, Path], previous_state: Mapping[str, Any], *, task_id: str, step: str, worker: str, failure_code: str, message: str, worker_exit_code: int | None = None, gate_exit_code: int | None = None, gate_command: Sequence[str] = (), prompt_path: Path | None = None, worker_jsonl_path: Path | None = None, last_message_path: Path | None = None) -> dict[str, Any]:
    state = dict(previous_state)
    gate = GateResult(RUNNER_INFRA_FAIL, failure_code=failure_code, message=message, gate_exit_code=gate_exit_code, worker_exit_code=worker_exit_code, failure_kind="runner-infra", gate_command=tuple(str(part) for part in gate_command))
    feedback = _build_feedback(gate, state=state, task_id=task_id, step=step)
    _write_json(paths["feedback"], feedback)
    if not paths["state"].exists():
        _write_json(paths["state"], state)
    _append_log(paths["log"], _build_log_event(gate, state=state, task_id=task_id, step=step, worker=worker, prompt_path=prompt_path, worker_jsonl_path=worker_jsonl_path, last_message_path=last_message_path))
    worker_output = {"kind": "runner_infra_failure", "failure_code": failure_code, "message": message}
    return _build_result(Path(paths["state"]).parent, task_id, step, worker, gate, state, feedback, paths, worker_output)


def _record_repair_limit(paths: Mapping[str, Path], previous_state: Mapping[str, Any], *, task_id: str, step: str, worker: str, last_feedback: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(previous_state)
    max_repairs = _positive_int(state.get("max_repair_attempts"), DEFAULT_MAX_REPAIR_ATTEMPTS)
    repair_attempt = max(_non_negative_int(state.get("repair_attempt"), 0), max_repairs)
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "profile": RUNNER_PROFILE,
            "worker_kind": worker,
            "repair_attempt": repair_attempt,
            "max_repair_attempts": max_repairs,
            "last_gate": PROCESS_FAIL,
            "current_step": str(state.get("current_step") or step),
            "blocked_before": step,
            "failure_streak": max(_non_negative_int(state.get("failure_streak"), 0), max_repairs),
            "last_failure_code": REPAIR_LIMIT_CODE,
            "last_failure_message": f"repair limit reached after {repair_attempt}/{max_repairs} codex-exec worker attempts",
            "status": "blocked",
        }
    )
    gate = GateResult(
        PROCESS_FAIL,
        REPAIR_LIMIT_CODE,
        state["last_failure_message"],
        gate_exit_code=_optional_int(last_feedback.get("gate_exit_code")),
        worker_exit_code=_optional_int(last_feedback.get("worker_exit_code")),
        failure_kind=REPAIR_LIMIT_KIND,
        gate_command=_normalize_feedback_command(last_feedback.get("gate_command")),
    )
    feedback = _build_feedback(gate, state=state, task_id=task_id, step=step)
    _write_json(paths["feedback"], feedback)
    _write_json(paths["state"], state)
    _append_log(paths["log"], _build_log_event(gate, state=state, task_id=task_id, step=step, worker=worker))
    worker_output = {"kind": "repair_limit", "last_feedback": dict(last_feedback)}
    result = _build_result(Path(paths["state"]).parent, task_id, step, worker, gate, state, feedback, paths, worker_output)
    result["kind"] = "work_runner_repair"
    result["repair_attempt"] = repair_attempt
    result["max_repair_attempts"] = max_repairs
    return result


def _apply_gate(previous: Mapping[str, Any], gate: GateResult, *, task_id: str, step: str, worker: str) -> dict[str, Any]:
    state = dict(previous)
    max_attempts = _positive_int(state.get("max_attempts_per_gate"), DEFAULT_MAX_ATTEMPTS_PER_GATE)
    max_repairs = _positive_int(state.get("max_repair_attempts"), DEFAULT_MAX_REPAIR_ATTEMPTS)
    repair_attempt = _non_negative_int(state.get("repair_attempt"), 0)
    attempt = _non_negative_int(state.get("attempt"), 0) + 1
    current_before = str(state.get("current_step") or step)
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "profile": RUNNER_PROFILE,
            "worker_kind": worker,
            "attempt": attempt,
            "max_attempts_per_gate": max_attempts,
            "repair_attempt": repair_attempt,
            "max_repair_attempts": max_repairs,
            "last_gate": gate.gate,
        }
    )
    if gate.passed:
        allowed_next = str(state.get("allowed_next_step") or "").strip()
        if allowed_next and allowed_next != current_before:
            state["current_step"] = allowed_next
            state["status"] = "running"
        else:
            state["current_step"] = current_before
            state["status"] = "done"
        state["passed_step"] = step
        state["blocked_before"] = None
        state["failure_streak"] = 0
        state.pop("last_failure_code", None)
        state.pop("last_failure_message", None)
        return state

    previous_blocked_before = state.get("blocked_before")
    previous_gate = previous.get("last_gate")
    previous_streak = _non_negative_int(previous.get("failure_streak"), 0)
    failure_streak = previous_streak + 1 if previous_gate == PROCESS_FAIL and previous_blocked_before == step else 1
    state["current_step"] = current_before
    state["blocked_before"] = step
    state["failure_streak"] = failure_streak
    state["last_failure_code"] = gate.failure_code
    state["last_failure_message"] = gate.message
    state["status"] = "blocked" if failure_streak >= max_attempts else "running"
    return state


def _apply_check_gate(previous: Mapping[str, Any], gate: GateResult, *, task_id: str, step: str, worker: str) -> dict[str, Any]:
    if gate.passed:
        return _apply_gate(previous, gate, task_id=task_id, step=step, worker=worker)

    state = dict(previous)
    max_attempts = _positive_int(state.get("max_attempts_per_gate"), DEFAULT_MAX_ATTEMPTS_PER_GATE)
    max_repairs = _positive_int(state.get("max_repair_attempts"), DEFAULT_MAX_REPAIR_ATTEMPTS)
    repair_attempt = _non_negative_int(state.get("repair_attempt"), 0)
    attempt = _non_negative_int(state.get("attempt"), 0) + 1
    current_before = str(state.get("current_step") or step)
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "profile": RUNNER_PROFILE,
            "worker_kind": worker,
            "attempt": attempt,
            "max_attempts_per_gate": max_attempts,
            "repair_attempt": repair_attempt,
            "max_repair_attempts": max_repairs,
            "last_gate": gate.gate,
            "current_step": current_before,
            "blocked_before": step,
            "failure_streak": 0,
            "last_failure_code": gate.failure_code,
            "last_failure_message": gate.message,
            "status": "running",
        }
    )
    return state


def _build_feedback(gate: GateResult, *, state: Mapping[str, Any], task_id: str, step: str) -> dict[str, Any]:
    feedback: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "work_runner_gate_feedback",
        "task_id": task_id,
        "step": step,
        "gate": gate.gate,
        "attempt": state.get("attempt"),
        "repair_attempt": state.get("repair_attempt"),
        "max_repair_attempts": state.get("max_repair_attempts"),
        "status": state.get("status"),
        "current_step": state.get("current_step"),
    }
    if gate.passed:
        feedback["message"] = gate.message or "gate passed"
        return feedback
    feedback.update(
        {
            "failure_code": gate.failure_code,
            "message": gate.message,
            "blocked_before": state.get("blocked_before"),
            "failure_streak": state.get("failure_streak"),
            "max_attempts_per_gate": state.get("max_attempts_per_gate"),
            "repair_scope": ["runner-infra"] if gate.gate == RUNNER_INFRA_FAIL else ["worker-output", "repo"],
        }
    )
    if gate.failure_kind:
        feedback["failure_kind"] = gate.failure_kind
    if gate.gate_exit_code is not None:
        feedback["gate_exit_code"] = gate.gate_exit_code
    if gate.worker_exit_code is not None:
        feedback["worker_exit_code"] = gate.worker_exit_code
    if gate.gate_command:
        feedback["gate_command"] = list(gate.gate_command)
    if gate.forbidden_paths:
        feedback["forbidden_paths"] = list(gate.forbidden_paths)
    return feedback


def _build_log_event(gate: GateResult, *, state: Mapping[str, Any], task_id: str, step: str, worker: str, prompt_path: Path | None = None, worker_jsonl_path: Path | None = None, last_message_path: Path | None = None) -> dict[str, Any]:
    event: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "kind": "work_runner_event",
        "event": gate.gate,
        "task_id": task_id,
        "step": step,
        "worker": worker,
        "attempt": state.get("attempt"),
        "repair_attempt": state.get("repair_attempt"),
        "max_repair_attempts": state.get("max_repair_attempts"),
        "status": state.get("status"),
        "current_step": state.get("current_step"),
        "prompt_path": str(prompt_path) if prompt_path else None,
        "worker_jsonl_path": str(worker_jsonl_path) if worker_jsonl_path else None,
        "last_message_path": str(last_message_path) if last_message_path else None,
        "gate_exit_code": gate.gate_exit_code,
        "worker_exit_code": gate.worker_exit_code,
        "failure_kind": gate.failure_kind,
        "gate_command": list(gate.gate_command) if gate.gate_command else None,
    }
    if gate.failure_code:
        event["failure_code"] = gate.failure_code
    return event


def _build_result(run_root: Path, task_id: str, step: str, worker: str, gate: GateResult, state: Mapping[str, Any], feedback: Mapping[str, Any], paths: Mapping[str, Path], worker_output: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "kind": "work_runner_run", "run_root": str(run_root), "task_id": task_id, "step": step, "worker": worker, "gate": gate.gate, "verdict": gate.gate, "state": dict(state), "feedback": dict(feedback), "worker_output": dict(worker_output), "paths": {name: str(path) for name, path in paths.items()}}


def _declared_forbidden_paths(payload: Mapping[str, Any], run_root: Path) -> tuple[str, ...]:
    declared: list[str] = []
    for field in ("declared_modified_paths", "modified_paths", "touched_paths"):
        value = payload.get(field, [])
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, Sequence):
            candidates = list(value)
        else:
            continue
        for item in candidates:
            normalized, forbidden = _normalize_declared_path(str(item), run_root)
            if forbidden:
                declared.append(normalized)
    return tuple(dict.fromkeys(declared))


def _normalize_declared_path(path_text: str, run_root: Path) -> tuple[str, bool]:
    text = path_text.strip().replace("\\", "/")
    if not text:
        return "", False
    path = Path(text)
    run_root_resolved = run_root.resolve()
    if path.is_absolute():
        try:
            rel = path.resolve().relative_to(run_root_resolved).as_posix()
        except (OSError, ValueError):
            return text, True
    else:
        parts: list[str] = []
        for part in text.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                return text, True
            parts.append(part)
        rel = "/".join(parts)
    first = rel.split("/", 1)[0]
    if rel in RUNNER_OWNED_FILES or first in RUNNER_OWNED_FILES:
        return rel, True
    return rel, False


def _snapshot_runner_owned(run_root: Path) -> dict[str, dict[str, str | bool | None]]:
    return {name: _file_fingerprint(run_root / name) for name in RUNNER_OWNED_FILES}


def _detect_runner_owned_changes(run_root: Path, before: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    changed: list[str] = []
    for name in RUNNER_OWNED_FILES:
        after = _file_fingerprint(run_root / name)
        if dict(before.get(name, {})) != after:
            changed.append(name)
    return tuple(changed)


def _file_fingerprint(path: Path) -> dict[str, str | bool | None]:
    if not path.exists():
        return {"exists": False, "sha256": None}
    if not path.is_file():
        return {"exists": True, "sha256": "<non-file>"}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"exists": True, "sha256": digest}

def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _append_log(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def _ensure_last_message_file(path: Path, stdout: bytes) -> None:
    if path.exists() and path.read_text(encoding="utf-8", errors="replace").strip():
        return
    message = _extract_last_message_from_jsonl(stdout)
    _atomic_write_text(path, message + ("\n" if message else ""))


def _extract_last_message_from_jsonl(stdout: bytes) -> str:
    last = ""
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            last = stripped
            continue
        found = _find_message_text(event)
        if found:
            last = found
    return last


def _find_message_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        for key in ("final_answer", "last_message", "text", "content", "message"):
            if key in value:
                found = _find_message_text(value[key])
                if found:
                    return found
        for child in value.values():
            found = _find_message_text(child)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        parts = [_find_message_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _as_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    return bytes(value)


def _required_text(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise WorkRunnerError(f"{field} is required")
    return normalized


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default




def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_feedback_command(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, Sequence):
        return tuple(str(part) for part in value if str(part).strip())
    return ()


def dumps_json(payload: Mapping[str, Any]) -> str:
    """Serialize a runner payload with stable formatting for CLI/tests."""

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"