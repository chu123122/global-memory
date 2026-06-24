from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from harness import config
from harness.scripts import analyze_retrieve_log, harness_retrieve


class _Brief:
    stage = "unit"
    warnings: list[str] = []
    relevant_pointers = [{"path": "knowledge/example.md", "why": "unit"}]


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_runtime_logs_dir_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("GLOBAL_MEMORY_LOGS_DIR", str(tmp_path / "global"))
    monkeypatch.setenv("HARNESS_LOGS_DIR", str(tmp_path / "harness"))
    assert config.resolve_runtime_logs_dir() == tmp_path / "global"

    monkeypatch.delenv("GLOBAL_MEMORY_LOGS_DIR")
    assert config.resolve_runtime_logs_dir() == tmp_path / "harness"


def test_write_retrieve_log_adds_shared_source_client_and_session(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    log_path = tmp_path / "logs" / "retrieve_calls.jsonl"

    harness_retrieve.write_retrieve_log(
        task_name="task-a",
        user_msg="hello shared logs",
        brief=_Brief(),
        elapsed_ms=12.34,
        log_path=log_path,
        extras={"source": "retrieve_inject", "client": "codex", "hook_session_id": "sess-1"},
    )

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["source"] == "retrieve_inject"
    assert record["client"] == "codex"
    assert record["hook_session_id"] == "sess-1"
    assert (tmp_path / "logs" / "retrieve_inject_debug.log").exists()


def test_analyzer_default_log_prefers_shared_then_legacy(tmp_path, monkeypatch):
    shared = tmp_path / "shared" / "retrieve_calls.jsonl"
    legacy = tmp_path / "legacy" / "retrieve_calls.jsonl"
    monkeypatch.setattr(analyze_retrieve_log, "DEFAULT_SHARED_LOG", shared)
    monkeypatch.setattr(analyze_retrieve_log, "LEGACY_LOG", legacy)

    assert analyze_retrieve_log.default_log_path() == legacy
    shared.parent.mkdir()
    shared.write_text("{}\n", encoding="utf-8")
    assert analyze_retrieve_log.default_log_path() == shared


def test_migrate_retrieve_logs_is_idempotent_and_refuses_repo_target(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts" / "migrate_retrieve_logs.py"
    migrate = _load_script(script, "migrate_retrieve_logs_for_test")

    source = tmp_path / "old" / "retrieve_calls.jsonl"
    target = tmp_path / "new" / "retrieve_calls.jsonl"
    source.parent.mkdir()
    source.write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
    target.parent.mkdir()
    target.write_text('{"a":1}\n', encoding="utf-8")

    first = migrate.migrate(source, target)
    second = migrate.migrate(source, target)

    assert first["appended_lines"] == 1
    assert second["appended_lines"] == 0
    assert target.read_text(encoding="utf-8").splitlines() == ['{"a":1}', '{"b":2}']

    monkeypatch.setattr(migrate, "is_runtime_logs_dir_in_repo", lambda _path: True)
    try:
        migrate.migrate(source, target)
    except RuntimeError as exc:
        assert "runtime logs dir" in str(exc)
    else:
        raise AssertionError("expected repo target guard to refuse migration")
