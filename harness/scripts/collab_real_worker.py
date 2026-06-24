#!/usr/bin/env python3
"""Run Phase 13 real Codex/Claude worker probes."""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge_host import load_session_events, save_session_events  # noqa: E402
from collab.errors import dumps_json, error_payload  # noqa: E402
from collab.real_worker import (  # noqa: E402
    RealWorkerError,
    apply_real_worker_result,
    build_real_worker_command,
    build_real_worker_probe_payload,
    build_real_worker_result,
    classify_real_worker_result,
    dumps_real_worker_json,
    run_real_worker_probe,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)

    request = sub.add_parser("request", help="Build a non-spawning real CLI worker request.")
    request.add_argument("--runtime", required=True, choices=["codex", "claude"])
    request.add_argument("--prompt", required=True)
    request.add_argument("--cwd", type=Path)
    request.add_argument("--output-file", type=Path)
    request.add_argument("--debug-log", type=Path)
    request.add_argument("--timeout-seconds", type=float, default=180.0)
    request.add_argument("--json", action="store_true")

    classify = sub.add_parser("classify", help="Classify saved/fake real worker streams.")
    classify.add_argument("--runtime", required=True, choices=["codex", "claude"])
    classify.add_argument("--result-json", type=Path)
    classify.add_argument("--stdout", default="")
    classify.add_argument("--stderr", default="")
    classify.add_argument("--exit-code", type=int)
    classify.add_argument("--timed-out", action="store_true")
    classify.add_argument("--expected-text")
    classify.add_argument("--output-file", type=Path)
    classify.add_argument("--debug-log", type=Path)
    classify.add_argument("--json", action="store_true")

    probe = sub.add_parser("probe", help="Run a real CLI worker probe and optionally update events.")
    probe.add_argument("--events", required=True, type=Path)
    probe.add_argument("--worker-id", required=True)
    probe.add_argument("--runtime", required=True, choices=["codex", "claude"])
    probe.add_argument("--prompt", required=True)
    probe.add_argument("--expected-text")
    probe.add_argument("--allow-spawn", action="store_true")
    probe.add_argument("--timeout-seconds", type=float, default=180.0)
    probe.add_argument("--cwd", type=Path)
    probe.add_argument("--output-file", type=Path)
    probe.add_argument("--debug-log", type=Path)
    probe.add_argument("--no-update-events", action="store_true")
    probe.add_argument("--now")
    probe.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command_name == "request":
            payload = build_real_worker_command(
                args.runtime,
                args.prompt,
                cwd=args.cwd,
                output_file=args.output_file,
                debug_log=args.debug_log,
                timeout_seconds=args.timeout_seconds,
            )
        elif args.command_name == "classify":
            result = _load_result(args)
            payload = {
                "schema_version": 1,
                "kind": "collab_real_worker_classification",
                "phase": 13,
                "classification": classify_real_worker_result(
                    args.runtime,
                    result,
                    expected_text=args.expected_text,
                    output_file_text=_read_optional(args.output_file),
                    debug_log_text=_read_optional(args.debug_log),
                ),
            }
        elif args.command_name == "probe":
            session = load_session_events(args.events)
            result = run_real_worker_probe(
                session,
                args.worker_id,
                args.runtime,
                args.prompt,
                allow_spawn=args.allow_spawn,
                cwd=args.cwd,
                timeout_seconds=args.timeout_seconds,
                expected_text=args.expected_text,
                output_file=args.output_file,
                debug_log=args.debug_log,
            )
            updated = not args.no_update_events
            if updated:
                session = apply_real_worker_result(session, result, now=args.now)
                save_session_events(session, args.events)
            payload = build_real_worker_probe_payload(session, result, event_log_updated=updated)
        else:  # pragma: no cover
            raise RealWorkerError(f"unknown command: {args.command_name}")
    except Exception as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_real_worker_error", _coerce_error(exc))), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(dumps_real_worker_json(payload), end="")
    return 0


def _load_result(args: argparse.Namespace) -> dict[str, object]:
    if args.result_json:
        try:
            payload = json.loads(args.result_json.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RealWorkerError(f"failed to read result JSON: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RealWorkerError(f"result JSON is invalid: {exc}") from exc
        if not isinstance(payload, dict):
            raise RealWorkerError("result JSON root must be an object")
        if payload.get("kind") == "collab_real_worker_probe":
            payload = payload.get("result") or {}
        if payload.get("kind") == "collab_worker_runtime_run":
            payload = payload.get("result") or {}
        if not isinstance(payload, dict):
            raise RealWorkerError("result payload must be an object")
        return dict(payload)
    return {"stdout": args.stdout, "stderr": args.stderr, "exit_code": args.exit_code, "timed_out": args.timed_out}


def _read_optional(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


def _coerce_error(exc: BaseException) -> BaseException:
    if isinstance(exc, RealWorkerError):
        return exc
    return RealWorkerError(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
