"""Tests for semantic-sync maintenance artifacts and guardrails."""
from __future__ import annotations

import json

from harness import maintain


def test_semantic_sync_artifacts_write_status_log_and_queue(tmp_path, monkeypatch):
    log_path = tmp_path / "semantic_sync.jsonl"
    status_path = tmp_path / "semantic_sync_status.json"
    queue_path = tmp_path / "semantic_sync_queue.json"
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_LOG_FILE", log_path)
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_STATUS_FILE", status_path)
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_QUEUE_FILE", queue_path)

    stale_report = {
        "ok": False,
        "mode": "check",
        "trigger": "stop-hook",
        "needsSync": True,
        "missing_count": 1,
        "dirty_count": 0,
        "stale_count": 0,
    }
    maintain.write_semantic_sync_artifacts(stale_report)

    assert json.loads(status_path.read_text(encoding="utf-8"))["trigger"] == "stop-hook"
    assert json.loads(queue_path.read_text(encoding="utf-8"))["needsSync"] is True
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1

    synced_report = {
        "ok": True,
        "mode": "sync",
        "trigger": "daemon",
        "needsSync": False,
        "ended_at": "2026-06-24T01:02:03",
    }
    maintain.write_semantic_sync_artifacts(synced_report)

    assert not queue_path.exists()
    synced_status = json.loads(status_path.read_text(encoding="utf-8"))
    assert synced_status["mode"] == "sync"
    assert synced_status["last_successful_sync_at"] == "2026-06-24T01:02:03"

    clean_check_report = {
        "ok": True,
        "mode": "check",
        "trigger": "test",
        "needsSync": False,
    }
    maintain.write_semantic_sync_artifacts(clean_check_report)

    checked_status = json.loads(status_path.read_text(encoding="utf-8"))
    assert checked_status["mode"] == "check"
    assert checked_status["last_successful_sync_at"] == "2026-06-24T01:02:03"
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3


def test_semantic_sync_lock_skips_concurrent_run(tmp_path, monkeypatch):
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_LOCK_FILE", tmp_path / "semantic_index.lock")

    locked, reason, release = maintain.acquire_semantic_sync_lock("test")
    assert locked is True
    assert reason is None
    assert release is not None

    locked_again, reason_again, release_again = maintain.acquire_semantic_sync_lock("test")
    assert locked_again is False
    assert reason_again == "lock_exists"
    assert release_again is None

    release()
    locked_after_release, reason_after_release, release_after_release = maintain.acquire_semantic_sync_lock("test")
    assert locked_after_release is True
    assert reason_after_release is None
    assert release_after_release is not None
    release_after_release()


def test_semantic_sync_throttle_only_applies_to_auto_triggers(tmp_path, monkeypatch):
    status_path = tmp_path / "semantic_sync_status.json"
    status_path.write_text(
        json.dumps({"ok": True, "mode": "sync", "skipped": False, "ended_at": maintain.now_iso()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_STATUS_FILE", status_path)

    skip, reason = maintain.semantic_sync_should_skip_for_throttle("daemon", min_interval_seconds=600)
    assert skip is True
    assert reason == "last_success_within_600s"

    manual_skip, manual_reason = maintain.semantic_sync_should_skip_for_throttle("manual", min_interval_seconds=600)
    assert manual_skip is False
    assert manual_reason is None

    forced_skip, forced_reason = maintain.semantic_sync_should_skip_for_throttle("daemon", force=True, min_interval_seconds=600)
    assert forced_skip is False
    assert forced_reason is None



def test_semantic_sync_lock_skip_keeps_queue(tmp_path, monkeypatch):
    log_path = tmp_path / "semantic_sync.jsonl"
    status_path = tmp_path / "semantic_sync_status.json"
    queue_path = tmp_path / "semantic_sync_queue.json"
    queue_path.write_text(json.dumps({"needsSync": True}), encoding="utf-8")
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_LOG_FILE", log_path)
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_STATUS_FILE", status_path)
    monkeypatch.setattr(maintain, "SEMANTIC_SYNC_QUEUE_FILE", queue_path)

    skipped_report = {
        "ok": True,
        "mode": "sync",
        "trigger": "worker",
        "skipped": True,
        "skipped_reason": "lock_exists",
        "needsSync": False,
    }
    maintain.write_semantic_sync_artifacts(skipped_report)

    assert queue_path.exists()
    assert json.loads(status_path.read_text(encoding="utf-8"))["skipped_reason"] == "lock_exists"
