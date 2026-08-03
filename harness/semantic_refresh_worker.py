#!/usr/bin/env python3
"""Queue-backed one-shot semantic index refresh worker.

Compatibility/manual path:
  maintain.py semantic-sync --check-only can still write harness/data/semantic_sync_queue.json when stale.
  This worker drains one queued request after a short debounce and delegates
  all index writes to maintain.py semantic-sync.
  Stop hook no longer launches this worker fire-and-forget; it runs check+sync in the foreground.

This process is intentionally short-lived. It never commits, pushes, or edits
source documents; it only refreshes the derived semantic index through the
maintain.py semantic-sync entrypoint.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

try:
    from harness import maintain  # type: ignore  # noqa: E402
except ModuleNotFoundError:  # direct script execution from copied harness dir
    if str(HARNESS_DIR) not in sys.path:
        sys.path.insert(0, str(HARNESS_DIR))
    import maintain  # type: ignore  # noqa: E402

DEFAULT_DEBOUNCE_SECONDS = float(os.environ.get("SEMANTIC_WORKER_DEBOUNCE_SECONDS", "90"))
DEFAULT_CHECK_TIMEOUT_SECONDS = int(os.environ.get("SEMANTIC_WORKER_CHECK_TIMEOUT_SECONDS", "60"))
DEFAULT_SYNC_TIMEOUT_SECONDS = int(os.environ.get("SEMANTIC_WORKER_SYNC_TIMEOUT_SECONDS", "900"))


def _emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload.get("summary") or payload.get("skipped_reason") or payload.get("error") or payload
        print(summary)


def _queue_exists() -> bool:
    try:
        return maintain.SEMANTIC_SYNC_QUEUE_FILE.exists()
    except OSError:
        return False


def _clear_queue() -> None:
    try:
        maintain.SEMANTIC_SYNC_QUEUE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _lock_exists() -> bool:
    try:
        return maintain.SEMANTIC_SYNC_LOCK_FILE.exists()
    except OSError:
        return False


def _base_report(*, skipped: bool = False, skipped_reason: str | None = None) -> dict[str, Any]:
    return {
        "trigger": "worker",
        "mode": "sync",
        "started_at": maintain.now_iso(),
        "ended_at": maintain.now_iso(),
        "duration_ms": 0,
        "ok": True,
        "skipped": skipped,
        "skipped_reason": skipped_reason,
        "index": str(maintain.HARNESS_DIR / "data" / "semantic_index.sqlite"),
        "filesSeen": 0,
        "filesIndexed": 0,
        "reusedFiles": 0,
        "staleRemoved": 0,
        "chunks": None,
        "vectors": None,
        "missing_count": 0,
        "dirty_count": 0,
        "stale_count": 0,
        "missingFiles": [],
        "dirtyFiles": [],
        "stalePaths": [],
        "needsSync": False,
        "error": None,
    }


def _write_worker_skip(reason: str) -> dict[str, Any]:
    report = _base_report(skipped=True, skipped_reason=reason)
    maintain.write_semantic_sync_artifacts(report)
    return report


def semantic_report_needs_sync(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    return bool(data.get("needsSync") or data.get("missing_count") or data.get("dirty_count") or data.get("stale_count"))


def run_semantic_command(args: list[str], *, timeout: int) -> tuple[int, dict[str, Any] | None, str]:
    cmd = [sys.executable, str(HARNESS_DIR / "maintain.py"), "semantic-sync", *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, None, f"timeout after {exc.timeout}s"
    except Exception as exc:  # noqa: BLE001
        return 1, None, f"{type(exc).__name__}: {exc}"

    stdout = (proc.stdout or "").strip()
    if not stdout:
        return proc.returncode, None, (proc.stderr or "").strip()
    try:
        return proc.returncode, json.loads(stdout), (proc.stderr or "").strip()
    except json.JSONDecodeError:
        tail = " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-3:])
        return proc.returncode, None, tail


def _write_worker_failure(message: str) -> dict[str, Any]:
    report = _base_report()
    report.update({"ok": False, "error": message})
    maintain.write_semantic_sync_artifacts(report)
    return report


def drain_once(
    *,
    debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS,
    check_timeout_seconds: int = DEFAULT_CHECK_TIMEOUT_SECONDS,
    sync_timeout_seconds: int = DEFAULT_SYNC_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any]]:
    if not _queue_exists():
        return 0, _base_report(skipped=True, skipped_reason="no_queue")

    if _lock_exists():
        return 0, _write_worker_skip("lock_exists")

    if debounce_seconds > 0:
        time.sleep(debounce_seconds)

    code, check_report, check_error = run_semantic_command(
        ["--check-only", "--trigger", "worker", "--json"],
        timeout=check_timeout_seconds,
    )
    if check_report is None:
        report = _write_worker_failure(f"check_failed:{check_error or code}")
        return 1, report

    if not semantic_report_needs_sync(check_report):
        _clear_queue()
        report = _base_report(skipped=True, skipped_reason="no_stale_after_debounce")
        report["check"] = check_report
        return 0, report

    code, sync_report, sync_error = run_semantic_command(
        ["--trigger", "worker", "--json"],
        timeout=sync_timeout_seconds,
    )
    if sync_report is None:
        report = _write_worker_failure(f"sync_failed:{sync_error or code}")
        return 1, report
    if sync_report.get("ok") and not sync_report.get("skipped") and not semantic_report_needs_sync(sync_report):
        _clear_queue()
    return (0 if code == 0 and sync_report.get("ok") else 1), sync_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drain semantic refresh queue once.")
    parser.add_argument("--drain-once", action="store_true", help="drain at most one queued refresh request")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--debounce-seconds", type=float, default=DEFAULT_DEBOUNCE_SECONDS)
    parser.add_argument("--check-timeout-seconds", type=int, default=DEFAULT_CHECK_TIMEOUT_SECONDS)
    parser.add_argument("--sync-timeout-seconds", type=int, default=DEFAULT_SYNC_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    # The worker is one-shot by design; --drain-once is accepted for readability
    # and compatibility with docs/tests.
    code, report = drain_once(
        debounce_seconds=args.debounce_seconds,
        check_timeout_seconds=args.check_timeout_seconds,
        sync_timeout_seconds=args.sync_timeout_seconds,
    )
    _emit(report, as_json=args.json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
