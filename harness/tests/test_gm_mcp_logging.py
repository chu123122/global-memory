"""Tests for gm_mcp JSONL logging."""
from __future__ import annotations

import json

from harness.gm_mcp import logging as gm_logging


def test_run_logged_records_source_mode_and_latency(tmp_path, monkeypatch):
    log_path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("GM_MCP_LOG_PATH", str(log_path))
    monkeypatch.delenv("GM_MCP_CALL_SOURCE", raising=False)

    result = gm_logging.run_logged(
        tool="gm.rule",
        query="审查能不能改代码",
        args={"top": 1},
        backend={"kind": "unit"},
        source=None,
        mode="backend_direct",
        call=lambda: (
            {"ok": True},
            {
                "hit": True,
                "count": 1,
                "top_refs": ["agents/CLAUDE.md"],
                "top_ids": ["R18_REVIEW_READONLY"],
                "confidence": 1.0,
                "low_confidence": False,
                "returned_summary": "R18",
            },
            {"backend_ms": 0.1},
        ),
    )

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["source"] == "natural"
    assert record["mode"] == "backend_direct"
    assert record["latency_ms"] >= 0
    assert record["elapsed_ms"] == record["latency_ms"]
    assert record["tool"] == "gm.rule"
    assert record["top_ids"] == ["R18_REVIEW_READONLY"]
    assert result["diagnostics"]["latency_ms"] >= 0


def test_run_logged_honors_test_source_env(tmp_path, monkeypatch):
    log_path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("GM_MCP_LOG_PATH", str(log_path))
    monkeypatch.setenv("GM_MCP_CALL_SOURCE", "test")

    gm_logging.run_logged(
        tool="gm.search",
        query="q",
        args={},
        backend={},
        source=None,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: (
            {},
            {
                "hit": False,
                "count": 0,
                "top_refs": [],
                "top_ids": [],
                "confidence": 0.0,
                "low_confidence": True,
                "returned_summary": "",
            },
            {},
        ),
    )

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["source"] == "test"
    assert record["mode"] == "mcp_tool_call"
