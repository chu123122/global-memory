"""Tests for gm_mcp server CLI and MCP exposure policy."""
from __future__ import annotations

import json
import sys
import types

import pytest

from harness.gm_mcp import server


def test_direct_rule_cli_uses_backend_and_source(monkeypatch, capsys):
    calls = []

    def fake_rule(query, *, top, source):
        calls.append((query, top, source))
        return {"tool": "gm.rule", "query": query, "source": source}

    monkeypatch.setattr(server, "gm_rule", fake_rule)

    assert server.main(["--rule", "审查只报告不改代码", "--top", "1", "--source", "work_step3_rule"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "gm.rule"
    assert calls == [("审查只报告不改代码", 1, "work_step3_rule")]


def test_direct_search_cli_uses_backend_and_source(monkeypatch, capsys):
    calls = []

    def fake_search(query, *, top, intent_top, max_delivered_unique_paths, source):
        calls.append((query, top, intent_top, max_delivered_unique_paths, source))
        return {"tool": "gm.search", "query": query, "source": source}

    monkeypatch.setattr(server, "gm_search_tool", fake_search)

    assert server.main([
        "--search",
        "UE RAG 模板怎么处理去噪",
        "--top",
        "7",
        "--intent-top",
        "2",
        "--max-delivered-unique-paths",
        "3",
        "--source",
        "work_step0_search",
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "gm.search"
    assert calls == [("UE RAG 模板怎么处理去噪", 7, 2, 3, "work_step0_search")]


def test_direct_locate_cli_uses_backend_and_source(monkeypatch, capsys):
    calls = []

    def fake_locate(query, *, kind, max_reads, source):
        calls.append((query, kind, max_reads, source))
        return {"tool": "gm.locate", "query": query, "source": source}

    monkeypatch.setattr(server, "gm_locate_tool", fake_locate)

    assert server.main(["--locate", "work 继续任务要读什么", "--max-reads", "2", "--kind", "skill", "--source", "work_step0_locate"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "gm.locate"
    assert calls == [("work 继续任务要读什么", "skill", 2, "work_step0_locate")]


def test_direct_symbol_cli_uses_backend_and_source(monkeypatch, capsys):
    calls = []

    def fake_symbol(name, *, kind, module, source):
        calls.append((name, kind, module, source))
        return {"tool": "gm.symbol", "query": name, "source": source}

    monkeypatch.setattr(server, "gm_symbol_tool", fake_symbol)

    assert server.main(["--symbol", "gm_search_tool", "--kind", "function", "--module", "gm_mcp", "--source", "work_step3_symbol"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "gm.symbol"
    assert calls == [("gm_search_tool", "function", "gm_mcp", "work_step3_symbol")]


def test_direct_inspect_map_answer_cli(monkeypatch, capsys):
    monkeypatch.setattr(server, "gm_inspect_tool", lambda type, *, name, id, source: {"tool": "gm.inspect", "type": type, "name": name, "id": id, "source": source})
    monkeypatch.setattr(server, "gm_map_tool", lambda *, source: {"tool": "gm.map", "source": source})
    monkeypatch.setattr(server, "gm_answer", lambda query, *, top, source: {"tool": "gm.answer", "query": query, "top": top, "source": source})

    assert server.main(["--inspect", "skill", "--id", "work", "--source", "inspect_test"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"tool": "gm.inspect", "type": "skill", "name": None, "id": "work", "source": "inspect_test"}

    assert server.main(["--map", "--source", "map_test"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"tool": "gm.map", "source": "map_test"}

    assert server.main(["--answer", "审查模式能不能改代码", "--top", "1", "--source", "answer_test"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"tool": "gm.answer", "query": "审查模式能不能改代码", "top": 1, "source": "answer_test"}


def test_direct_cli_rejects_conflicting_direct_modes():
    with pytest.raises(SystemExit) as excinfo:
        server.main(["--rule", "r", "--search", "s"])

    assert excinfo.value.code == 2


def _install_fake_mcp(monkeypatch):
    instances = []

    class FakeMCP:
        def __init__(self, name):
            self.name = name
            self.tools = []
            self.transport = None
            instances.append(self)

        def tool(self, *, name):
            def decorator(func):
                self.tools.append(name)
                return func

            return decorator

        def run(self, *, transport):
            self.transport = transport

    mcp_mod = types.ModuleType("mcp")
    server_mod = types.ModuleType("mcp.server")
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = FakeMCP
    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.server", server_mod)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)
    monkeypatch.setattr(server, "warmup", lambda: {"rules": {"ok": True, "count": 1}, "catalog": {"ok": True}, "search": {"ok": True}})
    return instances


def test_stdio_server_hides_gm_rule_tool_by_default(monkeypatch):
    instances = _install_fake_mcp(monkeypatch)
    monkeypatch.delenv(server.EXPOSE_RULE_TOOL_ENV, raising=False)

    server.run_stdio_server()

    assert instances[0].tools == ["gm.search", "gm.locate", "gm.symbol", "gm.inspect", "gm.map", "gm.answer"]
    assert instances[0].transport == "stdio"


def test_stdio_server_can_opt_in_to_gm_rule_tool(monkeypatch):
    instances = _install_fake_mcp(monkeypatch)
    monkeypatch.setenv(server.EXPOSE_RULE_TOOL_ENV, "1")

    server.run_stdio_server()

    assert instances[0].tools == ["gm.search", "gm.locate", "gm.symbol", "gm.inspect", "gm.map", "gm.answer", "gm.rule"]
    assert instances[0].transport == "stdio"
