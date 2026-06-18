"""MCP server entrypoint for pull-mode global-memory tools."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from typing import Any

from harness.gm_mcp import logging as gm_logging
from harness.gm_mcp import rules as gm_rules
from harness.gm_mcp import search as gm_search


def gm_rule(query: str, top: int = 3, source: str | None = None) -> dict[str, Any]:
    return gm_logging.run_logged(
        tool="gm.rule",
        query=query,
        args={"top": top},
        backend={"kind": "rules_yaml_in_memory", "registry": str(gm_rules.RULES_PATH)},
        source=source,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: _rule_call(query, top=top),
    )


def _rule_call(query: str, *, top: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    start = time.perf_counter()
    result = gm_rules.lookup_rule(query, top=top)
    timings = {"backend_ms": round((time.perf_counter() - start) * 1000.0, 3)}
    return result, gm_rules.log_summary(result), timings


def gm_search_tool(
    query: str,
    top: int = 5,
    intent_top: int = 3,
    max_delivered_unique_paths: int = gm_search.DEFAULT_DELIVERED_UNIQUE_PATHS,
    source: str | None = None,
) -> dict[str, Any]:
    return gm_logging.run_logged(
        tool="gm.search",
        query=query,
        args={"top": top, "intent_top": intent_top, "max_delivered_unique_paths": max_delivered_unique_paths},
        backend={"kind": "semantic_q2doc_plus_intent_q2q", "index": str(gm_search.DEFAULT_INDEX_PATH)},
        source=source,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: _search_call(
            query,
            top=top,
            intent_top=intent_top,
            max_delivered_unique_paths=max_delivered_unique_paths,
        ),
    )


def _search_call(
    query: str,
    *,
    top: int,
    intent_top: int,
    max_delivered_unique_paths: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    start = time.perf_counter()
    result = gm_search.search(
        query,
        top=top,
        intent_top=intent_top,
        max_delivered_unique_paths=max_delivered_unique_paths,
    )
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    timings = diagnostics.get("timings") if isinstance(diagnostics.get("timings"), dict) else {}
    out_timings = {str(k): float(v) for k, v in timings.items() if isinstance(v, (int, float))}
    out_timings["backend_ms"] = round((time.perf_counter() - start) * 1000.0, 3)
    return result, gm_search.log_summary(result), out_timings


def warmup() -> dict[str, Any]:
    rule_start = time.perf_counter()
    rule_count = len(gm_rules.load_rules())
    rule_ms = (time.perf_counter() - rule_start) * 1000.0
    search_status: dict[str, Any]
    try:
        search_status = {"ok": True, **gm_search.warmup()}
    except Exception as exc:  # explicit status for local setup gaps
        search_status = {"ok": False, "error": gm_logging.summarize_error(exc)}
    return {
        "rules": {"ok": True, "count": rule_count, "elapsed_ms": round(rule_ms, 3)},
        "search": search_status,
    }


def self_test() -> dict[str, Any]:
    previous_source = os.environ.get("GM_MCP_CALL_SOURCE")
    os.environ["GM_MCP_CALL_SOURCE"] = "self_test"
    try:
        payload: dict[str, Any] = {"warmup": warmup()}
        payload["rule"] = gm_rule("审查模式能不能改代码", source="self_test")
        try:
            payload["search"] = gm_search_tool("代码审查时能不能顺手改", source="self_test")
        except Exception as exc:
            payload["search"] = {"status": "error", "error": gm_logging.summarize_error(exc)}
        payload["log_path"] = str(gm_logging.log_path())
        return payload
    finally:
        if previous_source is None:
            os.environ.pop("GM_MCP_CALL_SOURCE", None)
        else:
            os.environ["GM_MCP_CALL_SOURCE"] = previous_source


def bench(repeat: int) -> dict[str, Any]:
    os.environ["GM_MCP_CALL_SOURCE"] = "self_test"
    warmup()
    rule_latencies = []
    search_latencies = []
    for _ in range(max(1, repeat)):
        t0 = time.perf_counter(); gm_rule("同一个错误反复出现该停吗", source="self_test"); rule_latencies.append((time.perf_counter() - t0) * 1000.0)
        try:
            t1 = time.perf_counter(); gm_search_tool("记忆应该存在哪里", source="self_test"); search_latencies.append((time.perf_counter() - t1) * 1000.0)
        except Exception:
            pass
    def stats(items: list[float]) -> dict[str, float | int]:
        if not items:
            return {"count": 0}
        ordered = sorted(items)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        return {"count": len(items), "p50_ms": round(statistics.median(items), 3), "p95_ms": round(p95, 3)}
    return {"gm.rule": stats(rule_latencies), "gm.search": stats(search_latencies)}


def run_stdio_server() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing MCP SDK. Install with: python -m pip install mcp") from exc

    status = warmup()
    if not status["rules"]["ok"]:
        raise SystemExit("gm.rule warmup failed")

    mcp = FastMCP("global-memory-pull-tools")

    @mcp.tool(name="gm.rule")
    def _gm_rule(query: str, top: int = 3, source: str | None = None) -> dict[str, Any]:
        """Look up anchored global-memory rules for a question or action, with source paths and conservative verdicts."""
        return gm_rule(query=query, top=top, source=source)

    @mcp.tool(name="gm.search")
    def _gm_search(
        query: str,
        top: int = 5,
        intent_top: int = 3,
        max_delivered_unique_paths: int = gm_search.DEFAULT_DELIVERED_UNIQUE_PATHS,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Recall global-memory decisions, pitfalls, and knowledge across projects/sessions or paraphrased wording when grep cannot reach them. Do not use for current-repo file search; grep is more precise."""
        return gm_search_tool(
            query=query,
            top=top,
            intent_top=intent_top,
            max_delivered_unique_paths=max_delivered_unique_paths,
            source=source,
        )

    mcp.run(transport="stdio")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.gm_mcp.server")
    parser.add_argument("--self-test", action="store_true", help="run backend self-test without requiring MCP SDK")
    parser.add_argument("--bench", action="store_true", help="run a small warm latency benchmark")
    parser.add_argument("--repeat", type=int, default=20)
    args = parser.parse_args(argv)
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if args.bench:
        print(json.dumps(bench(args.repeat), ensure_ascii=False, indent=2))
        return 0
    run_stdio_server()
    return 0


if __name__ == "__main__":
    sys.exit(main())
