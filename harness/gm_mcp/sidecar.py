"""Loopback HTTP sidecar for warm gm.search hook delivery.

The Claude/Codex prompt hook should be a lightweight HTTP client.  This
process owns the expensive Python/CUDA/reranker lifetime and fails closed for
RAG injection when the reranker is degraded.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from harness.config import GLOBAL_MEMORY_LOGS_DIR, is_runtime_logs_dir_in_repo
from harness.gm_mcp import search as gm_search
from harness.semantic import reranker as semantic_reranker

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
DEFAULT_WARMUP_TIMEOUT_MS = 120_000
STARTED_MONOTONIC = time.monotonic()

_STATE: dict[str, Any] = {
    "warming": False,
    "warm": False,
    "degraded": False,
    "warmup_error": None,
    "warmup": {},
    "reranker": {},
    "reranker_fallback_count": 0,
    "request_count": 0,
    "last_request_error": None,
}


def _runtime_log_path(name: str) -> Path | None:
    try:
        path = GLOBAL_MEMORY_LOGS_DIR / name
        if is_runtime_logs_dir_in_repo(path.parent):
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return None


def _log(event: str, **fields: Any) -> None:
    path = _runtime_log_path("gm_search_sidecar.log")
    if path is None:
        return
    try:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": event,
            **fields,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _write_pid_file(host: str, port: int) -> None:
    path = _runtime_log_path("gm_search_sidecar.pid.json")
    if path is None:
        return
    try:
        payload = {
            "pid": os.getpid(),
            "host": host,
            "port": port,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def _warmup_reranker() -> dict[str, Any]:
    config = semantic_reranker.config_from_env()
    warmup_timeout = int(os.environ.get("GM_SEARCH_SIDECAR_WARMUP_TIMEOUT_MS", str(DEFAULT_WARMUP_TIMEOUT_MS)))
    if warmup_timeout > config.timeout_ms:
        config = replace(config, timeout_ms=warmup_timeout)
    candidates = [
        {
            "path": "__sidecar_warmup__/reranker.md",
            "summary": "Warm the gm.search reranker backend for hook delivery.",
            "why": "sidecar startup warmup",
            "chunk_text": "global memory gm.search hook reranker warmup document",
            "retrieval_score": 1.0,
            "signals": {"raw_cosine": 1.0, "evidence_class": "semantic_only"},
        }
    ]
    _rows, diagnostics = semantic_reranker.rerank_candidates(
        "gm.search sidecar reranker warmup",
        candidates,
        top_n=1,
        config=config,
    )
    return dict(diagnostics)


def warmup() -> dict[str, Any]:
    """Warm embeddings/index/intent cache and load the configured reranker."""
    if _STATE.get("warm") or _STATE.get("warming"):
        return health_payload()
    _STATE.update({"warming": True, "warmup_error": None})
    _log("warmup_start", pid=os.getpid())
    started = time.perf_counter()
    try:
        memory_warmup = gm_search.warmup()
        reranker_diag = _warmup_reranker()
        fallback_reason = reranker_diag.get("fallback_reason")
        degraded = bool(fallback_reason) or not bool(reranker_diag.get("enabled"))
        _STATE.update({
            "warm": True,
            "warming": False,
            "degraded": degraded,
            "warmup": memory_warmup,
            "reranker": reranker_diag,
            "reranker_fallback_count": 1 if fallback_reason else 0,
            "warmup_error": None,
        })
    except Exception as exc:  # fail closed for hook delivery
        _STATE.update({
            "warm": False,
            "warming": False,
            "degraded": True,
            "warmup_error": str(exc),
            "reranker_fallback_count": 1,
        })
    _STATE["warmup_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    _log("warmup_done", status=health_payload().get("status"), elapsed_ms=_STATE["warmup_elapsed_ms"], error=_STATE.get("warmup_error"))
    return health_payload()


def health_payload() -> dict[str, Any]:
    if _STATE.get("warming"):
        status = "warming"
    elif _STATE.get("warm") and not _STATE.get("degraded"):
        status = "ready"
    elif _STATE.get("degraded"):
        status = "degraded"
    else:
        status = "cold"
    reranker = dict(_STATE.get("reranker") or {})
    return {
        "service": "gm.search.sidecar",
        "status": status,
        "ready": status == "ready",
        "warm": bool(_STATE.get("warm")),
        "degraded": bool(_STATE.get("degraded")),
        "pid": os.getpid(),
        "uptime_s": round(time.monotonic() - STARTED_MONOTONIC, 3),
        "warmup": dict(_STATE.get("warmup") or {}),
        "warmup_elapsed_ms": _STATE.get("warmup_elapsed_ms"),
        "warmup_error": _STATE.get("warmup_error"),
        "reranker": reranker,
        "reranker_fallback_count": int(_STATE.get("reranker_fallback_count") or 0),
        "reranker_fallback_reason": reranker.get("fallback_reason"),
        "request_count": int(_STATE.get("request_count") or 0),
        "last_request_error": _STATE.get("last_request_error"),
    }


def _abstain(reason: str, *, query: str = "") -> dict[str, Any]:
    return {
        "tool": "gm.search",
        "query": query,
        "hit": False,
        "count": 0,
        "pointers": [],
        "abstained": True,
        "abstain_reason": reason,
        "low_confidence": True,
        "delivery_profile": gm_search.HOOK_DELIVERY_PROFILE,
        "diagnostics": {"sidecar": health_payload()},
    }


def hook_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or payload.get("prompt") or "").strip()
    if not query:
        return _abstain("empty_query", query=query)
    health = health_payload()
    if health["status"] == "warming":
        return _abstain("sidecar_warming", query=query)
    if not health["warm"]:
        return _abstain("sidecar_not_warm", query=query)
    if health["degraded"] or health["reranker_fallback_count"] > 0:
        reason = health.get("reranker_fallback_reason") or health.get("warmup_error") or "reranker_degraded"
        return _abstain(f"sidecar_degraded:{reason}", query=query)

    _STATE["request_count"] = int(_STATE.get("request_count") or 0) + 1
    try:
        result = gm_search.search(
            query,
            top=2,
            intent_top=1,
            max_delivered_unique_paths=2,
            delivery_profile=gm_search.HOOK_DELIVERY_PROFILE,
        )
        reranker_diag = (result.get("diagnostics") or {}).get("reranker") if isinstance(result.get("diagnostics"), dict) else {}
        fallback_reason = reranker_diag.get("fallback_reason") if isinstance(reranker_diag, dict) else None
        if fallback_reason:
            _STATE["degraded"] = True
            _STATE["reranker"] = dict(reranker_diag)
            _STATE["reranker_fallback_count"] = int(_STATE.get("reranker_fallback_count") or 0) + 1
            result = _abstain(f"sidecar_degraded:{fallback_reason}", query=query)
        result.setdefault("diagnostics", {})
        if isinstance(result["diagnostics"], dict):
            result["diagnostics"]["sidecar"] = health_payload()
        _STATE["last_request_error"] = None
        return result
    except Exception as exc:
        _STATE["last_request_error"] = str(exc)
        _log("request_error", error=str(exc), query_preview=query[:80])
        return _abstain(f"search_error:{exc}", query=query)


class SidecarHandler(BaseHTTPRequestHandler):
    server_version = "gm-search-sidecar/1"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.split("?", 1)[0] != "/health":
            self._send_json(404, {"error": "not_found"})
            return
        self._send_json(200, health_payload())

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.split("?", 1)[0] != "/v1/hook/search":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(min(length, 1_000_000)) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
        except Exception as exc:
            self._send_json(400, {"error": "bad_request", "message": str(exc)})
            return
        self._send_json(200, hook_search(payload))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited name
        _log("http", message=format % args)


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, int(port)), SidecarHandler)


def _client_json(method: str, url: str, payload: dict[str, Any] | None = None, *, timeout: float = 2.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback operator CLI
        body = response.read().decode("utf-8")
    loaded = json.loads(body)
    return loaded if isinstance(loaded, dict) else {"value": loaded}


def _health_url(host: str, port: int) -> str:
    return f"http://{host}:{int(port)}/health"


def _search_url(host: str, port: int) -> str:
    return f"http://{host}:{int(port)}/v1/hook/search"


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Warm loopback gm.search sidecar for prompt hooks.")
    parser.add_argument("--host", default=os.environ.get("GM_SEARCH_SIDECAR_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GM_SEARCH_SIDECAR_PORT", DEFAULT_PORT)))
    parser.add_argument("--health", action="store_true", help="Query a running sidecar /health and exit.")
    parser.add_argument("--self-test", action="store_true", help="Warm this process and run one hook search without serving forever.")
    args = parser.parse_args(argv)

    if args.health:
        try:
            payload = _client_json("GET", _health_url(args.host, args.port), timeout=2.0)
            _print_json(payload)
            return 0 if payload.get("ready") else 2
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            _print_json({"status": "unreachable", "ready": False, "error": str(exc)})
            return 2

    if args.self_test:
        warm = warmup()
        result = hook_search({"query": "审查只报告不改代码", "client": "self_test"})
        payload = {"health": warm, "search": {"hit": result.get("hit"), "abstained": result.get("abstained"), "abstain_reason": result.get("abstain_reason")}}
        _print_json(payload)
        return 0 if warm.get("ready") else 2

    _write_pid_file(args.host, args.port)
    warmup()
    server = create_server(args.host, args.port)
    _log("serve_start", host=args.host, port=args.port, pid=os.getpid(), status=health_payload().get("status"))
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        _log("serve_stop", reason="keyboard_interrupt")
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
