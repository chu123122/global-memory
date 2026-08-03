"""Tests for queue-backed one-shot semantic refresh worker."""
from __future__ import annotations

import json

from harness import maintain
from harness import semantic_refresh_worker as worker


def _patch_artifacts(tmp_path, monkeypatch):
    queue = tmp_path / "semantic_sync_queue.json"
    lock = tmp_path / "semantic_index.lock"
    status = tmp_path / "semantic_sync_status.json"
    log = tmp_path / "semantic_sync.jsonl"
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_QUEUE_FILE", queue)
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_LOCK_FILE", lock)
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_STATUS_FILE", status)
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_LOG_FILE", log)
    return queue, lock, status, log


def test_worker_no_queue_exits_without_sync(tmp_path, monkeypatch):
    _patch_artifacts(tmp_path, monkeypatch)

    calls = []
    monkeypatch.setattr(worker, "run_semantic_command", lambda *args, **kwargs: calls.append(args))

    code, report = worker.drain_once(debounce_seconds=0)

    assert code == 0
    assert report["skipped_reason"] == "no_queue"
    assert calls == []


def test_worker_lock_skip_records_status_and_keeps_queue(tmp_path, monkeypatch):
    queue, lock, status, log = _patch_artifacts(tmp_path, monkeypatch)
    queue.write_text(json.dumps({"needsSync": True}), encoding="utf-8")
    lock.write_text("locked", encoding="utf-8")

    code, report = worker.drain_once(debounce_seconds=0)

    assert code == 0
    assert report["skipped_reason"] == "lock_exists"
    assert queue.exists()
    assert json.loads(status.read_text(encoding="utf-8"))["skipped_reason"] == "lock_exists"
    assert log.read_text(encoding="utf-8").strip()


def test_worker_clears_queue_when_recheck_is_clean(tmp_path, monkeypatch):
    queue, _lock, _status, _log = _patch_artifacts(tmp_path, monkeypatch)
    queue.write_text(json.dumps({"needsSync": True}), encoding="utf-8")

    calls = []

    def fake_run(args, *, timeout):
        calls.append(args)
        return 0, {"ok": True, "needsSync": False, "missing_count": 0, "dirty_count": 0, "stale_count": 0}, ""

    monkeypatch.setattr(worker, "run_semantic_command", fake_run)

    code, report = worker.drain_once(debounce_seconds=0)

    assert code == 0
    assert report["skipped_reason"] == "no_stale_after_debounce"
    assert not queue.exists()
    assert calls == [["--check-only", "--trigger", "worker", "--json"]]


def test_worker_runs_sync_for_stale_queue_and_clears_queue(tmp_path, monkeypatch):
    queue, _lock, _status, _log = _patch_artifacts(tmp_path, monkeypatch)
    queue.write_text(json.dumps({"needsSync": True}), encoding="utf-8")

    calls = []

    def fake_run(args, *, timeout):
        calls.append(args)
        if "--check-only" in args:
            return 1, {"ok": False, "needsSync": True, "missing_count": 1, "dirty_count": 0, "stale_count": 0}, ""
        return 0, {"ok": True, "skipped": False, "needsSync": False, "filesIndexed": 1}, ""

    monkeypatch.setattr(worker, "run_semantic_command", fake_run)

    code, report = worker.drain_once(debounce_seconds=0)

    assert code == 0
    assert report["ok"] is True
    assert not queue.exists()
    assert calls == [
        ["--check-only", "--trigger", "worker", "--json"],
        ["--trigger", "worker", "--json"],
    ]
