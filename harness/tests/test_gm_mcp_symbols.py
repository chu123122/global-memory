"""Golden tests for gm_mcp Python symbol index."""
from __future__ import annotations

from pathlib import Path

from harness.config import REPO_DIR
from harness.gm_mcp import catalog


def _assert_valid_location(item):
    path = REPO_DIR / item["path"]
    assert path.is_file()
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    assert 1 <= item["start_line"] <= item["end_line"] <= len(lines)


def test_symbol_finds_gm_search_tool_precise_location():
    result = catalog.symbol("gm_search_tool")

    assert result["tool"] == "gm.symbol"
    assert result["hit"] is True
    first = result["results"][0]
    assert first["path"] == "harness/gm_mcp/server.py"
    assert first["kind"] == "function"
    assert first["signature"].startswith("def gm_search_tool(")
    assert first["location"].startswith("harness/gm_mcp/server.py:")
    _assert_valid_location(first)


def test_symbol_finds_class_and_method_names():
    class_result = catalog.symbol("RuleEntry", kind="class")
    assert class_result["hit"] is True
    assert class_result["results"][0]["path"] == "harness/gm_mcp/rules.py"
    _assert_valid_location(class_result["results"][0])

    method_result = catalog.symbol("_SymbolVisitor.visit_FunctionDef", kind="method")
    assert method_result["hit"] is True
    assert method_result["results"][0]["path"] == "harness/gm_mcp/catalog.py"
    _assert_valid_location(method_result["results"][0])
