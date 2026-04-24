#!/usr/bin/env python3
"""Unit tests for the control panel data model."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from control_panel_model import (  # noqa: E402
    event_key,
    summarize_doctor,
    summarize_event,
    summarize_groups,
    summarize_log,
    summarize_status,
    summarize_sync_preview,
)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label}: expected {needle!r} in {text!r}")


def test_status_dirty_recommends_preview() -> None:
    data = {
        "mode": "status",
        "git": {
            "dirty": True,
            "ahead": 0,
            "behind": 0,
            "change_count": 3,
            "groups": {"harness": ["a.py"], "docs": ["README.md", "CONTROL_PANEL.md"]},
            "changes": [{"code": "M", "path": "README.md"}],
        },
        "daemon": {"running": False, "process_count": 0},
        "recent_commits": {"summary": {"semantic": 2, "checkpoint": 5, "total": 7}},
        "logs": {"maintain_tail": []},
    }
    summary = summarize_status(data)
    assert_equal(summary["decision"]["level"], "warning", "dirty level")
    assert_contains(summary["decision"]["next_action"], "生成同步预览", "dirty next action")
    assert_equal(len(summary["changes"]), 1, "dirty changes")


def test_status_clean_recommends_doctor() -> None:
    data = {
        "git": {"dirty": False, "ahead": 0, "behind": 0, "change_count": 0, "groups": {}, "changes": []},
        "daemon": {"running": True, "process_count": 1},
        "recent_commits": {"summary": {"semantic": 1, "checkpoint": 1, "total": 2}},
        "logs": {"maintain_tail": []},
    }
    summary = summarize_status(data)
    assert_equal(summary["decision"]["level"], "ok", "clean level")
    assert_contains(summary["decision"]["next_action"], "完整体检", "clean next action")


def test_status_sync_failure_is_visible() -> None:
    data = {
        "git": {"dirty": True, "ahead": 0, "behind": 0, "change_count": 1, "groups": {"docs": ["README.md"]}},
        "daemon": {"running": False, "process_count": 0},
        "recent_commits": {"summary": {}},
        "logs": {"maintain_tail": [{"type": "sync", "summary": "pull --rebase failed; aborting push"}]},
    }
    summary = summarize_status(data)
    assert_equal(summary["last_sync_failed"], True, "sync failure flag")
    assert_contains(summary["decision"]["why"], "自动同步失败", "sync failure message")


def test_doctor_summary_levels() -> None:
    data = {
        "mode": "doctor",
        "summary": {"PASS": 5, "WARNING": 1, "ERROR": 0},
        "results": [{"id": "git_status", "level": "WARNING", "summary": "dirty=True"}],
    }
    summary = summarize_doctor(data)
    assert_equal(summary["decision"]["level"], "warning", "doctor warning")
    assert_equal(summary["checks"][0]["id"], "git_status", "doctor checks")


def test_sync_preview_summary() -> None:
    data = {
        "mode": "sync-preview",
        "file_count": 2,
        "commit": "checkpoint: test",
        "groups": {"harness": ["a.py"], "docs": ["README.md"]},
        "changes": [{"code": "M", "path": "a.py"}, {"code": "??", "path": "README.md"}],
    }
    summary = summarize_sync_preview(data)
    assert_equal(summary["decision"]["level"], "warning", "preview level")
    assert_equal(summary["groups_text"], "harness 1 / docs 1", "preview groups")
    assert_equal(len(summary["changes"]), 2, "preview changes")


def test_log_summary() -> None:
    data = {"summary": {"semantic": 3, "checkpoint": 9, "total": 12}, "entries": [{"sha": "abc"}]}
    summary = summarize_log(data)
    assert_equal(summary["semantic"], 3, "log semantic")
    assert_equal(summary["checkpoint"], 9, "log checkpoint")
    assert_equal(len(summary["entries"]), 1, "log entries")


def test_event_summary_and_key() -> None:
    event = {
        "timestamp": "2026-04-24T14:30:00",
        "source": "ai",
        "level": "warning",
        "title": "同步失败",
        "message": "pull failed",
    }
    summary = summarize_event(event)
    assert_equal(summary["time"], "04-24 14:30:00", "event time")
    assert_equal(summary["level"], "warning", "event level")
    assert_equal(event_key(event), summary["key"], "event key")


def test_group_text_empty() -> None:
    assert_equal(summarize_groups({}), "无变更", "empty groups")


def main() -> int:
    tests = [
        test_status_dirty_recommends_preview,
        test_status_clean_recommends_doctor,
        test_status_sync_failure_is_visible,
        test_doctor_summary_levels,
        test_sync_preview_summary,
        test_log_summary,
        test_event_summary_and_key,
        test_group_text_empty,
    ]
    for test in tests:
        test()
    print(f"control_panel_model tests passed: {len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

