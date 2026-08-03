"""Optional query rewrite layer for gm.search.

The rewrite layer is intentionally best-effort.  It may expand one user query
into a small retrieval plan, but it must never answer the user question and must
never make gm.search fail.  Any invalid backend output, unavailable model, or
slow response returns a single-query fallback plan that preserves the original
query.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

DEFAULT_REWRITE_BACKEND = "off"
DEFAULT_REWRITE_MODEL = "qwen3:4b"
DEFAULT_REWRITE_TIMEOUT_MS = 3000
DEFAULT_REWRITE_MAX_QUERIES = 5
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_VALID_BACKENDS = {"off", "mock", "ollama-json", "deepseek-json"}
_FORBIDDEN_FIELDS = {"answer", "final", "response", "body"}
_BASE_ALLOWED_SOURCE_HINTS = {"agents", "rules", "docs", "knowledge", "fixes", "claude-tasks"}
_REPO_ROOT = Path(__file__).resolve().parents[2]


class RewriteError(RuntimeError):
    """Raised when a rewrite backend response violates the retrieval-plan schema."""


@dataclass(frozen=True)
class RewriteConfig:
    backend: str = DEFAULT_REWRITE_BACKEND
    model: str = DEFAULT_REWRITE_MODEL
    timeout_ms: int = DEFAULT_REWRITE_TIMEOUT_MS
    max_queries: int = DEFAULT_REWRITE_MAX_QUERIES

    @property
    def enabled(self) -> bool:
        return self.backend != "off"


@dataclass(frozen=True)
class RewritePlan:
    intent: str
    queries: tuple[str, ...]
    must_include: tuple[str, ...]
    avoid: tuple[str, ...]
    source_hints: tuple[str, ...]
    confidence: float
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "queries": list(self.queries),
            "must_include": list(self.must_include),
            "avoid": list(self.avoid),
            "source_hints": list(self.source_hints),
            "confidence": self.confidence,
        }


class RewriteBackend(Protocol):
    name: str

    def generate(self, query: str, *, config: RewriteConfig) -> str:
        """Return a JSON string containing a retrieval-only rewrite plan."""


class MockRewriteBackend:
    """Deterministic backend for tests and local plumbing validation."""

    name = "mock"

    def __init__(self, response: str | Mapping[str, Any] | None = None) -> None:
        self._response = response

    def generate(self, query: str, *, config: RewriteConfig) -> str:
        if self._response is not None:
            if isinstance(self._response, str):
                return self._response
            return json.dumps(dict(self._response), ensure_ascii=False)
        plan = {
            "intent": "mock_retrieval_plan",
            "queries": [query, f"{query} 规则", f"{query} global-memory"],
            "must_include": [],
            "avoid": [],
            "source_hints": [],
            "confidence": 0.5,
        }
        return json.dumps(plan, ensure_ascii=False)


def _rewrite_messages(query: str, *, max_queries: int) -> list[dict[str, str]]:
    example = {
        "intent": "find rule for repeated failures",
        "queries": ["同一个错误反复出现该停吗", "同错 3 次 停 汇报", "repeated same error stop after 3 attempts"],
        "must_include": ["同错", "3 次", "停"],
        "avoid": ["general debugging advice"],
        "source_hints": ["agents", "rules", "docs"],
        "confidence": 0.8,
    }
    return [
        {
            "role": "system",
            "content": (
                "You generate retrieval plans for a local repository search tool. "
                "Return only JSON. Do not answer the user's question. Do not include answer, final, response, or body fields. "
                "Do not invent file paths. Use exactly these keys: intent, queries, must_include, avoid, source_hints, confidence. "
                f"Generate at most {max_queries} queries and include the original query exactly as the first query. "
                "source_hints may only be broad existing scopes such as agents, rules, docs, knowledge, fixes, claude-tasks. "
                "All list fields must be JSON arrays of strings. intent must be a string. confidence must be a number between 0 and 1. "
                f"Example JSON: {json.dumps(example, ensure_ascii=False)}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"original_query": query, "max_queries": max_queries}, ensure_ascii=False),
        },
    ]


class OllamaJsonBackend:
    """Loopback-only Ollama chat backend using strict JSON mode."""

    name = "ollama-json"

    def generate(self, query: str, *, config: RewriteConfig) -> str:
        payload = {
            "model": config.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": _rewrite_messages(query, max_queries=config.max_queries),
        }
        request = urllib.request.Request(
            OLLAMA_CHAT_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(config.timeout_ms / 1000.0, 0.001)) as response:  # nosec B310 - loopback constant URL only
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:  # pragma: no cover - depends on local Ollama state
            raise RewriteError(f"ollama unavailable: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - Ollama normally returns JSON envelope
            raise RewriteError(f"ollama envelope invalid_json: {exc}") from exc
        message = data.get("message") if isinstance(data, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RewriteError("ollama response missing message.content")
        return content


class DeepSeekJsonBackend:
    """DeepSeek OpenAI-compatible chat backend using JSON Output mode."""

    name = "deepseek-json"

    def generate(self, query: str, *, config: RewriteConfig) -> str:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RewriteError("DEEPSEEK_API_KEY missing")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).strip().rstrip("/") or DEFAULT_DEEPSEEK_BASE_URL
        payload = {
            "model": config.model,
            "stream": False,
            "temperature": 0,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "messages": _rewrite_messages(query, max_queries=config.max_queries),
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(config.timeout_ms / 1000.0, 0.001)) as response:  # nosec B310 - user-configured DeepSeek API base URL
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover - depends on remote API state
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RewriteError(f"deepseek http_error:{exc.code}:{detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - depends on remote API state
            raise RewriteError(f"deepseek unavailable: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - remote envelope should be JSON
            raise RewriteError(f"deepseek envelope invalid_json: {exc}") from exc
        choices = data.get("choices") if isinstance(data, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RewriteError("deepseek response missing choices[0].message.content")
        return content


def _env_int(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = max(minimum, int(raw))
    except ValueError:
        return default
    if maximum is not None:
        value = min(value, maximum)
    return value


def config_from_env() -> RewriteConfig:
    backend = os.environ.get("GM_SEARCH_REWRITE", DEFAULT_REWRITE_BACKEND).strip().lower() or DEFAULT_REWRITE_BACKEND
    if backend not in _VALID_BACKENDS:
        backend = "off"
    return RewriteConfig(
        backend=backend,
        model=os.environ.get("GM_SEARCH_REWRITE_MODEL", DEFAULT_REWRITE_MODEL).strip() or DEFAULT_REWRITE_MODEL,
        timeout_ms=_env_int("GM_SEARCH_REWRITE_TIMEOUT_MS", DEFAULT_REWRITE_TIMEOUT_MS, minimum=1),
        max_queries=_env_int("GM_SEARCH_REWRITE_MAX_QUERIES", DEFAULT_REWRITE_MAX_QUERIES, minimum=1, maximum=5),
    )


def _allowed_source_hints() -> set[str]:
    hints = set(_BASE_ALLOWED_SOURCE_HINTS)
    try:
        for child in _REPO_ROOT.iterdir():
            if child.is_dir() and child.name not in {".git", "__pycache__"}:
                hints.add(child.name)
    except OSError:
        pass
    return hints


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise RewriteError(f"{field} must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise RewriteError(f"{field} items must be strings")
        text = item.strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _has_forbidden_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if key_text in _FORBIDDEN_FIELDS:
                return key_text
            nested = _has_forbidden_key(child)
            if nested:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _has_forbidden_key(child)
            if nested:
                return nested
    return None


def _normalize_queries(queries: list[str], original_query: str | None, max_queries: int) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    if original_query is not None:
        clean = original_query.strip()
        if not clean:
            raise RewriteError("original query must not be empty")
        normalized.append(clean)
        seen.add(clean)
    for query in queries:
        clean = query.strip()
        if not clean or clean in seen:
            continue
        normalized.append(clean)
        seen.add(clean)
        if len(normalized) >= max_queries:
            break
    if not normalized:
        raise RewriteError("queries must not be empty")
    return tuple(normalized[:max_queries])


def parse_rewrite_json(text: str, *, query: str | None = None, config: RewriteConfig | None = None) -> RewritePlan:
    """Parse and validate a backend JSON response as a retrieval-only plan."""
    config = config or RewriteConfig()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RewriteError(f"invalid_json: {exc}") from exc
    if not isinstance(data, dict):
        raise RewriteError("rewrite JSON must be an object")
    forbidden = _has_forbidden_key(data)
    if forbidden:
        raise RewriteError(f"forbidden_field:{forbidden}")
    required = {"intent", "queries", "must_include", "avoid", "source_hints", "confidence"}
    missing = sorted(required - set(data))
    if missing:
        raise RewriteError(f"missing_fields:{','.join(missing)}")
    if not isinstance(data.get("intent"), str):
        raise RewriteError("intent must be a string")
    confidence_raw = data.get("confidence")
    if not isinstance(confidence_raw, (int, float)) or not math.isfinite(float(confidence_raw)):
        raise RewriteError("confidence must be a finite number")
    queries = _normalize_queries(_string_list(data.get("queries"), "queries"), query, max(1, min(config.max_queries, 5)))
    allowed_hints = _allowed_source_hints()
    source_hints = tuple(hint for hint in _string_list(data.get("source_hints"), "source_hints") if hint in allowed_hints)
    return RewritePlan(
        intent=str(data.get("intent") or "").strip(),
        queries=queries,
        must_include=tuple(_string_list(data.get("must_include"), "must_include")),
        avoid=tuple(_string_list(data.get("avoid"), "avoid")),
        source_hints=source_hints,
        confidence=max(0.0, min(1.0, float(confidence_raw))),
        fallback_reason=None,
    )


def fallback_plan(query: str, reason: str) -> RewritePlan:
    clean = query.strip()
    if not clean:
        raise ValueError("query must not be empty")
    return RewritePlan(
        intent="",
        queries=(clean,),
        must_include=(),
        avoid=(),
        source_hints=(),
        confidence=0.0,
        fallback_reason=reason,
    )


def _backend_from_config(config: RewriteConfig) -> RewriteBackend:
    if config.backend == "mock":
        return MockRewriteBackend()
    if config.backend == "ollama-json":
        return OllamaJsonBackend()
    if config.backend == "deepseek-json":
        return DeepSeekJsonBackend()
    raise RewriteError(f"unsupported rewrite backend: {config.backend}")


def rewrite_query(query: str, config: RewriteConfig | None = None, backend_impl: RewriteBackend | None = None) -> RewritePlan:
    """Return a validated rewrite plan or a single-query fallback plan."""
    clean = query.strip()
    if not clean:
        raise ValueError("query must not be empty")
    config = config or config_from_env()
    if not config.enabled:
        return fallback_plan(clean, "backend_off")
    start = time.perf_counter()
    try:
        backend = backend_impl or _backend_from_config(config)
        raw = backend.generate(clean, config=config)
        latency_ms = (time.perf_counter() - start) * 1000.0
        if latency_ms > config.timeout_ms:
            raise RewriteError(f"timeout_ms_exceeded:{round(latency_ms, 3)}>{config.timeout_ms}")
        return parse_rewrite_json(raw, query=clean, config=config)
    except Exception as exc:
        return fallback_plan(clean, str(exc))
