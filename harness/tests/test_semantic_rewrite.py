"""Tests for optional gm.search query rewrite plans."""
from __future__ import annotations

import pytest

from harness.semantic import rewrite


class _ExplodingBackend:
    name = "mock"

    def generate(self, query: str, *, config: rewrite.RewriteConfig) -> str:
        raise RuntimeError("boom")


def _config(max_queries: int = 5) -> rewrite.RewriteConfig:
    return rewrite.RewriteConfig(backend="mock", model="mock", timeout_ms=3000, max_queries=max_queries)


def test_mock_backend_generates_valid_plan_with_original_query():
    plan = rewrite.rewrite_query("同一个错误反复出现该停吗", config=_config())

    assert plan.fallback_reason is None
    assert plan.queries[0] == "同一个错误反复出现该停吗"
    assert len(plan.queries) <= 5
    assert plan.intent == "mock_retrieval_plan"


def test_bad_json_falls_back_to_original_query():
    backend = rewrite.MockRewriteBackend("not-json")

    plan = rewrite.rewrite_query("q", config=_config(), backend_impl=backend)

    assert plan.queries == ("q",)
    assert "invalid_json" in str(plan.fallback_reason)


def test_missing_required_field_falls_back():
    backend = rewrite.MockRewriteBackend({"intent": "x", "queries": ["q"]})

    plan = rewrite.rewrite_query("q", config=_config(), backend_impl=backend)

    assert plan.queries == ("q",)
    assert "missing_fields" in str(plan.fallback_reason)


def test_invalid_source_hints_are_filtered():
    raw = {
        "intent": "x",
        "queries": ["q"],
        "must_include": [],
        "avoid": [],
        "source_hints": ["agents", "not-a-scope", "docs"],
        "confidence": 0.7,
    }

    plan = rewrite.parse_rewrite_json(__import__("json").dumps(raw), query="q", config=_config())

    assert plan.source_hints == ("agents", "docs")


def test_forbidden_answer_field_falls_back():
    backend = rewrite.MockRewriteBackend({
        "intent": "x",
        "queries": ["q"],
        "must_include": [],
        "avoid": [],
        "source_hints": [],
        "confidence": 0.7,
        "answer": "do not answer",
    })

    plan = rewrite.rewrite_query("q", config=_config(), backend_impl=backend)

    assert plan.queries == ("q",)
    assert "forbidden_field:answer" in str(plan.fallback_reason)


def test_original_query_is_always_retained_and_first():
    backend = rewrite.MockRewriteBackend({
        "intent": "x",
        "queries": ["expanded one", "expanded two"],
        "must_include": [],
        "avoid": [],
        "source_hints": [],
        "confidence": 0.7,
    })

    plan = rewrite.rewrite_query("original", config=_config(), backend_impl=backend)

    assert plan.queries[0] == "original"
    assert "expanded one" in plan.queries


def test_query_count_cap_is_enforced_after_adding_original_query():
    backend = rewrite.MockRewriteBackend({
        "intent": "x",
        "queries": ["a", "b", "c", "d", "e", "f"],
        "must_include": [],
        "avoid": [],
        "source_hints": [],
        "confidence": 0.7,
    })

    plan = rewrite.rewrite_query("original", config=_config(max_queries=3), backend_impl=backend)

    assert plan.queries == ("original", "a", "b")


def test_backend_exception_falls_back():
    plan = rewrite.rewrite_query("q", config=_config(), backend_impl=_ExplodingBackend())

    assert plan.queries == ("q",)
    assert "boom" in str(plan.fallback_reason)


def test_off_backend_returns_backend_off_fallback():
    plan = rewrite.rewrite_query("q", config=rewrite.RewriteConfig(backend="off"))

    assert plan.queries == ("q",)
    assert plan.fallback_reason == "backend_off"



def test_deepseek_backend_missing_api_key_falls_back(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = rewrite.RewriteConfig(backend="deepseek-json", model="deepseek-v4-flash", timeout_ms=3000, max_queries=5)

    plan = rewrite.rewrite_query("q", config=config)

    assert plan.queries == ("q",)
    assert plan.fallback_reason == "DEEPSEEK_API_KEY missing"


def test_config_from_env_accepts_deepseek_backend(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_REWRITE", "deepseek-json")
    monkeypatch.setenv("GM_SEARCH_REWRITE_MODEL", "deepseek-v4-flash")

    config = rewrite.config_from_env()

    assert config.backend == "deepseek-json"
    assert config.model == "deepseek-v4-flash"
