"""Tests for Stop hook foreground semantic refresh and visible events."""
from __future__ import annotations

import json
from types import SimpleNamespace

from harness import post_task_hook


def _patch_events(tmp_path, monkeypatch):
    event_log = tmp_path / "semantic_refresh_events.jsonl"
    queue = tmp_path / "semantic_sync_queue.json"
    monkeypatch.setattr(post_task_hook, "SEMANTIC_REFRESH_EVENTS_FILE", event_log)
    monkeypatch.setattr(post_task_hook, "SEMANTIC_SYNC_QUEUE_FILE", queue)
    return event_log, queue


def _events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_semantic_check_clean_writes_final_no_update(tmp_path, monkeypatch):
    event_log, _queue = _patch_events(tmp_path, monkeypatch)
    calls = []

    def fake_run(args, *, timeout):
        calls.append(args)
        return 0, {"ok": True, "needsSync": False, "missing_count": 0, "dirty_count": 0, "stale_count": 0}, None, ["python", "maintain.py", *args], 7

    monkeypatch.setattr(post_task_hook, "run_semantic_maintain_command", fake_run)

    result = post_task_hook.HookResult()
    assert post_task_hook.check_semantic_index_stale(result, r"D:\ClaudeTasks\active\foo") is True

    assert calls == [["--check-only", "--trigger", "stop-hook", "--json"]]
    assert result.warnings == []
    assert any("当前fooRAG库无需更新" in msg for msg in result.passed)
    assert [e["phase"] for e in _events(event_log)] == ["check_start", "check_result", "final_message"]


def test_semantic_stale_sync_success_writes_events_and_clears_queue(tmp_path, monkeypatch):
    event_log, queue = _patch_events(tmp_path, monkeypatch)
    queue.write_text(json.dumps({"needsSync": True}), encoding="utf-8")
    calls = []

    def fake_run(args, *, timeout):
        calls.append(args)
        if "--check-only" in args:
            return 1, {"ok": False, "needsSync": True, "missing_count": 1, "dirty_count": 0, "stale_count": 0}, None, ["python", "maintain.py", *args], 11
        return 0, {"ok": True, "skipped": False, "needsSync": False, "missing_count": 0, "dirty_count": 0, "stale_count": 0}, None, ["python", "maintain.py", *args], 23

    monkeypatch.setattr(post_task_hook, "run_semantic_maintain_command", fake_run)

    result = post_task_hook.HookResult()
    assert post_task_hook.check_semantic_index_stale(result, r"D:\ClaudeTasks\active\foo") is True

    assert calls == [
        ["--check-only", "--trigger", "stop-hook", "--json"],
        ["--trigger", "stop-hook", "--force", "--json"],
    ]
    assert not queue.exists()
    assert result.warnings == []
    assert any("当前fooRAG库已更新" in msg for msg in result.passed)
    events = _events(event_log)
    assert [e["phase"] for e in events] == ["check_start", "check_result", "sync_start", "sync_result", "final_message"]
    assert events[1]["needsSync"] is True
    assert events[3]["ok"] is True


def test_semantic_sync_skipped_is_failure(tmp_path, monkeypatch):
    event_log, _queue = _patch_events(tmp_path, monkeypatch)

    def fake_run(args, *, timeout):
        if "--check-only" in args:
            return 1, {"ok": False, "needsSync": True, "missing_count": 1, "dirty_count": 0, "stale_count": 0}, None, ["python", "maintain.py", *args], 1
        return 0, {"ok": True, "skipped": True, "skipped_reason": "lock_exists", "needsSync": False, "missing_count": 0, "dirty_count": 0, "stale_count": 0}, None, ["python", "maintain.py", *args], 1

    monkeypatch.setattr(post_task_hook, "run_semantic_maintain_command", fake_run)

    result = post_task_hook.HookResult()
    assert post_task_hook.check_semantic_index_stale(result, r"D:\ClaudeTasks\active\foo") is False

    assert not any("RAG库已更新" in msg for msg in result.passed)
    assert any("当前fooRAG库更新失败：sync_skipped:lock_exists" in msg for msg in result.warnings)
    events = _events(event_log)
    assert events[-1]["phase"] == "final_message"
    assert events[-1]["ok"] is False


def test_semantic_sync_after_still_needs_sync_is_failure(tmp_path, monkeypatch):
    _event_log, _queue = _patch_events(tmp_path, monkeypatch)

    def fake_run(args, *, timeout):
        if "--check-only" in args:
            return 1, {"ok": False, "needsSync": True, "missing_count": 0, "dirty_count": 1, "stale_count": 0}, None, ["python", "maintain.py", *args], 1
        return 1, {"ok": False, "skipped": False, "needsSync": True, "missing_count": 0, "dirty_count": 1, "stale_count": 0}, None, ["python", "maintain.py", *args], 1

    monkeypatch.setattr(post_task_hook, "run_semantic_maintain_command", fake_run)

    result = post_task_hook.HookResult()
    assert post_task_hook.check_semantic_index_stale(result, r"D:\ClaudeTasks\active\foo") is False

    assert any("sync_after仍needsSync" in msg for msg in result.warnings)
    assert not any("RAG库已更新" in msg for msg in result.passed)


def test_semantic_sync_without_json_is_failure(tmp_path, monkeypatch):
    _event_log, _queue = _patch_events(tmp_path, monkeypatch)

    def fake_run(args, *, timeout):
        if "--check-only" in args:
            return 1, {"ok": False, "needsSync": True, "missing_count": 1, "dirty_count": 0, "stale_count": 0}, None, ["python", "maintain.py", *args], 1
        return 0, None, "invalid_json_stdout", ["python", "maintain.py", *args], 1

    monkeypatch.setattr(post_task_hook, "run_semantic_maintain_command", fake_run)

    result = post_task_hook.HookResult()
    assert post_task_hook.check_semantic_index_stale(result, r"D:\ClaudeTasks\active\foo") is False

    assert any("当前fooRAG库更新失败：sync_error:invalid_json_stdout" in msg for msg in result.warnings)
    assert not any("RAG库已更新" in msg for msg in result.passed)


def test_task_name_from_cwd_when_project_absent(tmp_path, monkeypatch):
    active = tmp_path / "active"
    workdir = active / "bar" / "subdir"
    workdir.mkdir(parents=True)
    monkeypatch.setattr(post_task_hook, "ACTIVE_TASKS_DIR", active)
    monkeypatch.chdir(workdir)

    assert post_task_hook.infer_task_name() == "bar"


def test_main_does_not_call_git_sync_repo(monkeypatch, capsys):
    monkeypatch.setattr(post_task_hook.sys, "argv", ["post_task_hook.py"])
    monkeypatch.setattr(post_task_hook, "check_index_sync", lambda result: result.passed.append("index") or True)
    monkeypatch.setattr(post_task_hook, "check_semantic_index_stale", lambda result, project_dir=None: result.passed.append("semantic") or True)
    monkeypatch.setattr(post_task_hook, "check_changelog_freshness", lambda result: result.passed.append("changelog"))
    monkeypatch.setattr(post_task_hook, "git_sync_repo", lambda repo: (_ for _ in ()).throw(AssertionError("git sync should not run")))

    def fake_run(cmd, **kwargs):
        if "harness.health.runner" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"signals": []}), stderr="")
        if "harness.issue_tracker" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"issues": [], "new_count": 0}), stderr="")
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(post_task_hook.subprocess, "run", fake_run)

    assert post_task_hook.main() == 0
    out = capsys.readouterr().out
    assert "已停用自动提交/推送" in out
    assert "sync --source manual" in out
