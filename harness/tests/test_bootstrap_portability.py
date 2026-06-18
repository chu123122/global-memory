"""Tests for bootstrap portability helpers."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import bootstrap


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_codex_mcp_registration_writes_expected_block_and_is_idempotent(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex"
    config = codex_home / "config.toml"
    codex_home.mkdir()
    config.write_text("model = 'gpt-5.5'\n\n[mcp_servers.other]\ncommand = 'other'\n", encoding="utf-8")

    monkeypatch.setattr(bootstrap, "CODEX_HOME", codex_home)
    monkeypatch.setattr(bootstrap, "CODEX_CONFIG", config)
    monkeypatch.setattr(bootstrap, "REPO", tmp_path / "repo")

    bootstrap.ensure_codex_mcp_registration()
    first = config.read_text(encoding="utf-8")

    assert "[mcp_servers.other]" in first
    assert "[mcp_servers.global-memory]" in first
    assert f"command = '{bootstrap.sys.executable}'" in first
    assert 'args = ["-m", "harness.gm_mcp.server"]' in first
    assert "[mcp_servers.global-memory.env]" in first
    assert f"PYTHONPATH = '{tmp_path / 'repo'}'" in first
    assert len(list((codex_home / "_backups").glob("config.toml.*"))) == 1

    bootstrap.ensure_codex_mcp_registration()

    assert config.read_text(encoding="utf-8") == first
    assert len(list((codex_home / "_backups").glob("config.toml.*"))) == 1
    failed: list[str] = []
    bootstrap.check_codex_mcp_registration(failed)
    assert failed == []


def test_codex_model_instructions_file_is_created_for_fresh_home(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex"
    config = codex_home / "config.toml"
    codex_home.mkdir()
    monkeypatch.setattr(bootstrap, "CODEX_HOME", codex_home)
    monkeypatch.setattr(bootstrap, "CODEX_CONFIG", config)

    bootstrap.ensure_codex_model_instructions_file()

    assert config.read_text(encoding="utf-8") == 'model_instructions_file = "./ctf.md"\n'


def test_claude_mcp_registration_adds_missing_server_with_runtime_paths(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text('{"mcpServers": {}}', encoding="utf-8")

    monkeypatch.setattr(bootstrap, "HOME", tmp_path / ".claude")
    monkeypatch.setattr(bootstrap, "CLAUDE_JSON", claude_json)
    monkeypatch.setattr(bootstrap, "REPO", tmp_path / "repo")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *args, **kwargs: _Completed(1, stderr="not found"))
    monkeypatch.setattr(bootstrap.subprocess, "check_call", lambda cmd, **kwargs: calls.append(list(cmd)))

    bootstrap.ensure_claude_mcp_registration()

    assert calls == [[
        "claude", "mcp", "add", "-s", "user", "global-memory",
        "-e", f"PYTHONPATH={tmp_path / 'repo'}",
        "--", bootstrap.sys.executable, "-m", "harness.gm_mcp.server",
    ]]
    assert list((tmp_path / ".claude" / "_backups").glob(".claude.json.*"))


def test_runtime_install_and_index_build_use_current_interpreter(tmp_path, monkeypatch):
    calls: list[tuple[list[str], str | None]] = []
    req = tmp_path / "requirements.txt"
    req.write_text("mcp\nPyYAML\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "REQUIREMENTS", req)
    monkeypatch.setattr(bootstrap, "REPO", tmp_path)
    monkeypatch.setattr(bootstrap.subprocess, "check_call", lambda cmd, cwd=None, **kwargs: calls.append((list(cmd), cwd)))

    bootstrap.install_runtime_dependencies()
    bootstrap.build_semantic_index()

    assert calls[0] == ([bootstrap.sys.executable, "-m", "pip", "install", "-r", str(req)], str(tmp_path))
    assert calls[1] == ([bootstrap.sys.executable, "-m", "harness.semantic.cli", "build"], str(tmp_path))


def test_check_helpers_report_missing_dependencies_and_registrations(tmp_path, monkeypatch):
    failed: list[str] = []
    monkeypatch.setattr(bootstrap, "_module_available", lambda module: False)
    monkeypatch.setattr(bootstrap, "_ollama_tags", lambda: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(bootstrap, "SEMANTIC_INDEX", tmp_path / "missing.sqlite")
    monkeypatch.setattr(bootstrap, "CODEX_CONFIG", tmp_path / "missing-config.toml")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: None)

    bootstrap.check_runtime_dependencies(failed)
    bootstrap.check_ollama_model(failed)
    bootstrap.check_semantic_index(failed)
    bootstrap.check_codex_mcp_registration(failed)
    bootstrap.check_claude_mcp_registration(failed)

    joined = "\n".join(failed)
    assert "Python 依赖缺失: mcp" in joined
    assert "Python 依赖缺失: PyYAML" in joined
    assert "Ollama API 不可用" in joined
    assert "语义索引缺失" in joined
    assert "Codex config.toml 不存在" in joined
    assert "Claude Code CLI 未找到" in joined


def test_claude_mcp_registration_replaces_inconsistent_existing_server(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text('{"mcpServers": {"global-memory": {}}}', encoding="utf-8")

    monkeypatch.setattr(bootstrap, "HOME", tmp_path / ".claude")
    monkeypatch.setattr(bootstrap, "CLAUDE_JSON", claude_json)
    monkeypatch.setattr(bootstrap, "REPO", tmp_path / "repo")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)
    monkeypatch.setattr(
        bootstrap.subprocess,
        "run",
        lambda *args, **kwargs: _Completed(0, stdout="global-memory:\n  Command: C:/old/python.exe\n"),
    )
    monkeypatch.setattr(bootstrap.subprocess, "check_call", lambda cmd, **kwargs: calls.append(list(cmd)))

    bootstrap.ensure_claude_mcp_registration()

    assert calls[0] == ["claude", "mcp", "remove", "global-memory", "-s", "user"]
    assert calls[1][:6] == ["claude", "mcp", "add", "-s", "user", "global-memory"]
    assert list((tmp_path / ".claude" / "_backups").glob(".claude.json.*"))


def test_settings_sync_is_idempotent_for_bootstrap_managed_keys(tmp_path, monkeypatch):
    home = tmp_path / "claude"
    home.mkdir()
    settings = home / "settings.json"
    hooks = {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python hook.py"}]}]}
    status_line = {"type": "command", "command": "python status.py"}
    settings.write_text(
        json.dumps({"userSetting": True, "hooks": hooks, "statusLine": status_line}, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(bootstrap, "HOME", home)
    monkeypatch.setattr(bootstrap, "hooks_json", lambda: hooks)
    monkeypatch.setattr(bootstrap, "status_line_json", lambda: status_line)

    first = settings.read_text(encoding="utf-8")
    bootstrap.sync_claude_settings()
    bootstrap.sync_claude_settings()

    assert settings.read_text(encoding="utf-8") == first
    assert not list((home / "_backups").glob("settings.json.*"))

    drifted_hooks = {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python new_hook.py"}]}]}
    monkeypatch.setattr(bootstrap, "hooks_json", lambda: drifted_hooks)
    bootstrap.sync_claude_settings()

    updated = json.loads(settings.read_text(encoding="utf-8"))
    assert updated["userSetting"] is True
    assert updated["hooks"] == drifted_hooks
    assert updated["statusLine"] == status_line
    assert len(list((home / "_backups").glob("settings.json.*"))) == 1


def test_replace_junction_skips_when_target_already_points_to_source(tmp_path, monkeypatch):
    target = tmp_path / "target"
    source = tmp_path / "source"
    calls: list[str] = []
    monkeypatch.setattr(bootstrap, "path_points_to", lambda p, expected: True)
    monkeypatch.setattr(bootstrap, "remove_path", lambda p: calls.append(f"remove:{p}"))
    monkeypatch.setattr(bootstrap, "make_junction", lambda t, s: calls.append(f"mklink:{t}->{s}"))

    bootstrap.replace_junction(target, source, "skill:test")

    assert calls == []


def test_replace_junction_rebuilds_when_target_does_not_point_to_source(tmp_path, monkeypatch):
    target = tmp_path / "target"
    source = tmp_path / "source"
    calls: list[str] = []
    monkeypatch.setattr(bootstrap, "path_points_to", lambda p, expected: False)
    monkeypatch.setattr(bootstrap, "remove_path", lambda p: calls.append(f"remove:{p.name}"))
    monkeypatch.setattr(bootstrap, "make_junction", lambda t, s: calls.append(f"mklink:{t.name}->{s.name}"))

    bootstrap.replace_junction(target, source, "skill:test")

    assert calls == ["remove:target", "mklink:target->source"]
