#!/usr/bin/env python3
"""Run deterministic work-runner checks, attempts, and bounded repairs.

Gate failures are emitted as JSON data and return exit code 0; invalid CLI/input
errors return non-zero.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shlex
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from work_runner import WorkRunnerError, check_once, dumps_json, repair_loop, run_once  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one worker attempt")
    _add_common_gate_args(run, repo_help="Repository root passed to codex exec --cd and verifier cwd.")
    run.add_argument("--worker", required=True, choices=["fake", "codex-exec"], help="Worker adapter.")
    run.add_argument("--fake-result", choices=["pass", "fail", "touch-forbidden"], help="Fake worker result fixture; required only for --worker fake.")
    run.add_argument("--codex-command", default="codex", help="Codex executable or script path; tests may pass a fake command.")

    check = sub.add_parser("check", help="run verifier-only checks without starting a worker")
    _add_common_gate_args(check, repo_help="Repository root used as verifier cwd.")

    repair = sub.add_parser("repair", help="run bounded codex-exec repair attempts from gate-feedback.json")
    _add_common_gate_args(repair, repo_help="Repository root passed to codex exec --cd and verifier cwd.")
    repair.add_argument("--worker", required=True, choices=["codex-exec"], help="Repair worker adapter; only codex-exec is allowed.")
    repair.add_argument("--codex-command", default="codex", help="Codex executable or script path; tests may pass a fake command.")
    return parser


def _add_common_gate_args(parser: argparse.ArgumentParser, *, repo_help: str) -> None:
    parser.add_argument("--run-root", required=True, type=Path, help="Directory holding run-state and runner feedback.")
    parser.add_argument("--task-id", required=True, help="Task id, for example global-memory-work-runner.")
    parser.add_argument("--step", required=True, help="Current step/phase id, for example GM-R3.")
    parser.add_argument("--repo-root", type=Path, default=Path(r"D:\global-memory"), help=repo_help)
    parser.add_argument("--timeout-sec", type=int, default=300, help="Worker/verifier timeout in seconds.")
    parser.add_argument("--allowed-next-step", help="Step adopted only after verifier pass.")
    parser.add_argument("--verifier-command", action="append", help="Verifier command. Prefer a JSON argv list; may be repeated.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and args.worker == "fake" and not args.fake_result:
        parser.error("--fake-result is required when --worker fake")
    try:
        verifier_commands = _parse_verifier_commands(args.verifier_command)
        if args.command == "check":
            payload = check_once(
                run_root=args.run_root,
                task_id=args.task_id,
                step=args.step,
                repo_root=args.repo_root,
                timeout_sec=args.timeout_sec,
                allowed_next_step=args.allowed_next_step,
                verifier_commands=verifier_commands,
            )
        elif args.command == "repair":
            payload = repair_loop(
                run_root=args.run_root,
                task_id=args.task_id,
                step=args.step,
                worker=args.worker,
                repo_root=args.repo_root,
                timeout_sec=args.timeout_sec,
                allowed_next_step=args.allowed_next_step,
                codex_command=args.codex_command,
                verifier_commands=verifier_commands,
            )
        else:
            payload = run_once(
                run_root=args.run_root,
                task_id=args.task_id,
                step=args.step,
                worker=args.worker,
                fake_result=args.fake_result,
                repo_root=args.repo_root,
                timeout_sec=args.timeout_sec,
                allowed_next_step=args.allowed_next_step,
                codex_command=args.codex_command,
                verifier_commands=verifier_commands,
            )
    except WorkRunnerError as exc:
        if args.json:
            print(dumps_json({"schema_version": 1, "kind": "work_runner_error", "error": str(exc)}), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(dumps_json(payload), end="")
    else:
        state = payload["state"]
        feedback = payload["feedback"]
        print(
            f"work_runner {payload['verdict']} task={payload['task_id']} step={payload['step']} "
            f"attempt={state.get('attempt')} repair_attempt={state.get('repair_attempt')}/"
            f"{state.get('max_repair_attempts')} status={state.get('status')} current_step={state.get('current_step')}"
        )
        if payload["verdict"] != "process-pass":
            print(f"failure_code={feedback.get('failure_code')} failure_kind={feedback.get('failure_kind')}")
    return 0


def _parse_verifier_commands(values: list[str] | None) -> list[list[str]] | None:
    if values is None:
        return None
    commands: list[list[str]] = []
    for value in values:
        text = value.strip()
        if not text:
            continue
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise WorkRunnerError("--verifier-command JSON must be a list")
            commands.append([str(part) for part in parsed])
        else:
            commands.append(shlex.split(text, posix=os.name != "nt"))
    return commands


if __name__ == "__main__":
    raise SystemExit(main())
