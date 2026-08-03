from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

from harness.gm_mcp import sidecar


def _reset_state(*, warm: bool = True, degraded: bool = False, fallback_reason: str | None = None) -> None:
    sidecar._STATE.clear()
    sidecar._STATE.update({
        "warming": False,
        "warm": warm,
        "degraded": degraded,
        "warmup_error": None,
        "warmup": {"vectors": 1, "intent_paraphrases": 1},
        "reranker": {"enabled": not degraded, "backend": "mock", "model": "mock-model", "fallback_reason": fallback_reason},
        "reranker_fallback_count": 1 if fallback_reason else 0,
        "request_count": 0,
        "last_request_error": None,
    })


def test_health_endpoint_reports_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(sidecar, "GLOBAL_MEMORY_LOGS_DIR", tmp_path)
    _reset_state(warm=True, degraded=False)
    server = sidecar.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2.0) as response:  # noqa: S310 - loopback test
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)

    assert payload["status"] == "ready"
    assert payload["ready"] is True
    assert payload["reranker_fallback_count"] == 0


def test_hook_search_uses_interactive_hook_profile(monkeypatch):
    _reset_state(warm=True, degraded=False)
    calls: list[dict[str, object]] = []

    def fake_search(query: str, **kwargs):
        calls.append({"query": query, **kwargs})
        return {
            "tool": "gm.search",
            "query": query,
            "hit": True,
            "count": 1,
            "confidence": 0.9,
            "abstained": False,
            "delivery_profile": sidecar.gm_search.HOOK_DELIVERY_PROFILE,
            "pointers": [{"path": "rules/接入索引.md", "signals": {"raw_cosine": 0.9, "evidence_class": "semantic_only"}}],
            "diagnostics": {"reranker": {"enabled": True, "fallback_reason": None}},
        }

    monkeypatch.setattr(sidecar.gm_search, "search", fake_search)

    result = sidecar.hook_search({"query": "代码审查规则在哪", "session_id": "s1", "client": "pytest", "task_name": "t"})

    assert result["hit"] is True
    assert result["abstained"] is False
    assert calls[0]["delivery_profile"] == sidecar.gm_search.HOOK_DELIVERY_PROFILE
    assert calls[0]["top"] == 2
    assert result["diagnostics"]["sidecar"]["status"] == "ready"


def test_hook_search_abstains_when_reranker_degraded(monkeypatch):
    _reset_state(warm=True, degraded=True, fallback_reason="dependency missing")

    def explode(*_args, **_kwargs):
        raise AssertionError("degraded sidecar must not call gm.search")

    monkeypatch.setattr(sidecar.gm_search, "search", explode)

    result = sidecar.hook_search({"query": "代码审查规则在哪"})

    assert result["hit"] is False
    assert result["abstained"] is True
    assert result["abstain_reason"].startswith("sidecar_degraded:")
