"""MCP server entrypoint for pull-mode global-memory tools."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from typing import Any

from harness.gm_mcp import catalog as gm_catalog
from harness.gm_mcp import logging as gm_logging
from harness.gm_mcp import rules as gm_rules
from harness.gm_mcp import search as gm_search

EXPOSE_RULE_TOOL_ENV = "GM_MCP_EXPOSE_RULE_TOOL"


def _env_truthy(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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


def gm_answer(query: str, top: int = 3, source: str | None = None) -> dict[str, Any]:
    return gm_logging.run_logged(
        tool="gm.answer",
        query=query,
        args={"top": top},
        backend={"kind": "rules_yaml_answer", "registry": str(gm_rules.RULES_PATH)},
        source=source,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: _answer_call(query, top=top),
    )


def _answer_call(query: str, *, top: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    start = time.perf_counter()
    rule_result = gm_rules.lookup_rule(query, top=top)
    results = rule_result.get("results") if isinstance(rule_result.get("results"), list) else []
    top_result = results[0] if results and isinstance(results[0], dict) else {}
    anchored = bool(rule_result.get("hit")) and str(top_result.get("verdict_basis")) != "informational"
    sources = top_result.get("sources") if isinstance(top_result.get("sources"), list) else []
    answer = {
        "tool": "gm.answer",
        "query": query.strip(),
        "hit": anchored,
        "abstain": not anchored,
        "verdict": top_result.get("verdict") if anchored else "abstain",
        "rule_id": top_result.get("rule_id") if anchored else None,
        "summary": top_result.get("summary") if anchored else "No anchored rule verdict found; abstain instead of using RAG as authority.",
        "sources": sources if anchored else [],
        "authority": "rules_yaml" if anchored else "none",
        "fallback_used": False,
        "rule_result": rule_result,
        "count": 1 if anchored else 0,
        "confidence": rule_result.get("confidence") if anchored else 0.0,
        "low_confidence": not anchored,
        "diagnostics": {
            "backend": "rules_yaml_answer",
            "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
        },
    }
    return answer, _answer_log_summary(answer), {"backend_ms": answer["diagnostics"]["elapsed_ms"]}


def _answer_log_summary(result: dict[str, Any]) -> dict[str, Any]:
    top_refs = []
    for source in result.get("sources") or []:
        if isinstance(source, dict):
            top_refs.append(str(source.get("source_path")))
    return {
        "hit": bool(result.get("hit")),
        "count": int(result.get("count") or 0),
        "top_refs": top_refs[:3],
        "top_ids": [str(result.get("rule_id"))] if result.get("rule_id") else [],
        "confidence": float(result.get("confidence") or 0.0),
        "low_confidence": bool(result.get("low_confidence")),
        "returned_summary": str(result.get("summary") or "")[:500],
    }


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


def gm_locate_tool(query: str, kind: str | None = None, max_reads: int = 3, source: str | None = None) -> dict[str, Any]:
    return gm_logging.run_logged(
        tool="gm.locate",
        query=query,
        args={"kind": kind, "max_reads": max_reads},
        backend={"kind": "structured_catalog", "catalog": str(gm_catalog.CATALOG_PATH)},
        source=source,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: _catalog_call(lambda: gm_catalog.locate(query, kind=kind, max_reads=max_reads)),
    )


def gm_symbol_tool(name: str, kind: str | None = None, module: str | None = None, source: str | None = None) -> dict[str, Any]:
    return gm_logging.run_logged(
        tool="gm.symbol",
        query=name,
        args={"kind": kind, "module": module},
        backend={"kind": "python_ast_symbol_index", "symbols": str(gm_catalog.SYMBOLS_PATH)},
        source=source,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: _catalog_call(lambda: gm_catalog.symbol(name, kind=kind, module=module)),
    )


def gm_inspect_tool(type: str, name: str | None = None, id: str | None = None, source: str | None = None) -> dict[str, Any]:
    query = f"{type}:{id or name}" if (id or name) else type
    return gm_logging.run_logged(
        tool="gm.inspect",
        query=query,
        args={"type": type, "name": name, "id": id},
        backend={"kind": "structured_catalog", "catalog": str(gm_catalog.CATALOG_PATH)},
        source=source,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: _catalog_call(lambda: gm_catalog.inspect_object(type, name=name, id_=id)),
    )


def gm_map_tool(source: str | None = None) -> dict[str, Any]:
    return gm_logging.run_logged(
        tool="gm.map",
        query="global-memory modules",
        args={},
        backend={"kind": "structured_catalog", "catalog": str(gm_catalog.CATALOG_PATH)},
        source=source,
        mode=gm_logging.DEFAULT_MODE,
        call=lambda: _catalog_call(gm_catalog.map_modules),
    )


def _catalog_call(func) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    start = time.perf_counter()
    result = func()
    timings = {"backend_ms": round((time.perf_counter() - start) * 1000.0, 3)}
    return result, gm_catalog.catalog_summary(result), timings


def warmup() -> dict[str, Any]:
    rule_start = time.perf_counter()
    rule_count = len(gm_rules.load_rules())
    rule_ms = (time.perf_counter() - rule_start) * 1000.0
    catalog_status: dict[str, Any]
    try:
        catalog_payload = gm_catalog.load_catalog()
        symbol_payload = gm_catalog.load_symbols()
        catalog_status = {
            "ok": True,
            "entries": len(catalog_payload.get("entries", [])),
            "symbols": len(symbol_payload.get("symbols", [])),
        }
    except Exception as exc:
        catalog_status = {"ok": False, "error": gm_logging.summarize_error(exc)}
    search_status: dict[str, Any]
    try:
        search_status = {"ok": True, **gm_search.warmup()}
    except Exception as exc:  # explicit status for local setup gaps
        search_status = {"ok": False, "error": gm_logging.summarize_error(exc)}
    return {
        "rules": {"ok": True, "count": rule_count, "elapsed_ms": round(rule_ms, 3)},
        "catalog": catalog_status,
        "search": search_status,
    }


def self_test() -> dict[str, Any]:
    previous_source = os.environ.get("GM_MCP_CALL_SOURCE")
    os.environ["GM_MCP_CALL_SOURCE"] = "self_test"
    try:
        payload: dict[str, Any] = {"warmup": warmup()}
        payload["rule"] = gm_rule("审查模式能不能改代码", source="self_test")
        payload["answer"] = gm_answer("审查模式能不能改代码", source="self_test")
        payload["locate"] = gm_locate_tool("work 继续任务要读什么", source="self_test")
        payload["symbol"] = gm_symbol_tool("gm_search_tool", source="self_test")
        payload["map"] = gm_map_tool(source="self_test")
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
    if not status.get("catalog", {}).get("ok"):
        raise SystemExit("gm catalog warmup failed")

    mcp = FastMCP("global-memory-pull-tools")

    @mcp.tool(name="gm.search")
    def _gm_search(
        query: str,
        top: int = 5,
        intent_top: int = 3,
        max_delivered_unique_paths: int = gm_search.DEFAULT_DELIVERED_UNIQUE_PATHS,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Recall old cross-project/cross-session memory, prior decisions, pitfalls, or paraphrased conclusions. Do not use for current-repo navigation, function lookup, or rule verdicts."""
        return gm_search_tool(
            query=query,
            top=top,
            intent_top=intent_top,
            max_delivered_unique_paths=max_delivered_unique_paths,
            source=source,
        )

    @mcp.tool(name="gm.locate")
    def _gm_locate(query: str, kind: str | None = None, max_reads: int = 3, source: str | None = None) -> dict[str, Any]:
        """Locate the smallest authoritative global-memory entry files for an internal question. Use before broad rg/read when asking what module, rule, script, or work entry to read."""
        return gm_locate_tool(query=query, kind=kind, max_reads=max_reads, source=source)

    @mcp.tool(name="gm.symbol")
    def _gm_symbol(name: str, kind: str | None = None, module: str | None = None, source: str | None = None) -> dict[str, Any]:
        """Find Python function/class/method definitions by AST and return exact path:start-end line locations. Use before reading whole files for implementation lookup."""
        return gm_symbol_tool(name=name, kind=kind, module=module, source=source)

    @mcp.tool(name="gm.inspect")
    def _gm_inspect(type: str, name: str | None = None, id: str | None = None, source: str | None = None) -> dict[str, Any]:
        """Inspect a known catalog object such as skill, script, rule, capability, task, module, rule_doc, agent, doc, or memory; returns summary and authoritative source path."""
        return gm_inspect_tool(type=type, name=name, id=id, source=source)

    @mcp.tool(name="gm.map")
    def _gm_map(source: str | None = None) -> dict[str, Any]:
        """Return the global-memory module map: top-level directory responsibilities and authoritative entrypoints."""
        return gm_map_tool(source=source)

    @mcp.tool(name="gm.answer")
    def _gm_answer(query: str, top: int = 3, source: str | None = None) -> dict[str, Any]:
        """Answer questions that have an anchored global-memory rule verdict. Abstains when no rule anchor exists; never uses RAG as authority."""
        return gm_answer(query=query, top=top, source=source)

    if _env_truthy(EXPOSE_RULE_TOOL_ENV, default=False):
        @mcp.tool(name="gm.rule")
        def _gm_rule(query: str, top: int = 3, source: str | None = None) -> dict[str, Any]:
            """Look up anchored global-memory rules for a question or action, with source paths and conservative verdicts. Usually prefer gm.answer for direct answers."""
            return gm_rule(query=query, top=top, source=source)

    mcp.run(transport="stdio")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(prog="python -m harness.gm_mcp.server")
    parser.add_argument("--self-test", action="store_true", help="run backend self-test without requiring MCP SDK")
    parser.add_argument("--bench", action="store_true", help="run a small warm latency benchmark")
    parser.add_argument("--repeat", type=int, default=20)
    direct = parser.add_mutually_exclusive_group()
    direct.add_argument("--rule", metavar="QUERY", help="direct gm.rule backend probe for gates/workflows")
    direct.add_argument("--search", metavar="QUERY", help="direct gm.search backend probe for fuzzy recall")
    direct.add_argument("--locate", metavar="QUERY", help="direct gm.locate structured catalog probe")
    direct.add_argument("--symbol", metavar="NAME", help="direct gm.symbol Python AST lookup")
    direct.add_argument("--inspect", metavar="TYPE", help="direct gm.inspect catalog object probe")
    direct.add_argument("--answer", metavar="QUERY", help="direct gm.answer anchored rule answer")
    direct.add_argument("--map", action="store_true", help="direct gm.map module map")
    parser.add_argument("--source", help="call-log source label, e.g. work_step3_rule")
    parser.add_argument("--top", type=int, help="result count for direct --rule/--search/--answer")
    parser.add_argument("--intent-top", type=int, default=3, help="intent match count for direct --search")
    parser.add_argument("--max-reads", type=int, default=3, help="max minimal reads for direct --locate")
    parser.add_argument("--kind", help="kind filter for direct --locate/--symbol")
    parser.add_argument("--module", help="module/path filter for direct --symbol")
    parser.add_argument("--name", help="name filter for direct --inspect")
    parser.add_argument("--id", help="id filter for direct --inspect")
    parser.add_argument(
        "--max-delivered-unique-paths",
        type=int,
        default=gm_search.DEFAULT_DELIVERED_UNIQUE_PATHS,
        help="deliver-gate cap for direct --search",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return 0
    if args.bench:
        print(json.dumps(bench(args.repeat), ensure_ascii=False, indent=2))
        return 0
    if args.rule:
        print(json.dumps(gm_rule(args.rule, top=args.top or 3, source=args.source), ensure_ascii=False, indent=2))
        return 0
    if args.search:
        print(json.dumps(
            gm_search_tool(
                args.search,
                top=args.top or 5,
                intent_top=args.intent_top,
                max_delivered_unique_paths=args.max_delivered_unique_paths,
                source=args.source,
            ),
            ensure_ascii=False,
            indent=2,
        ))
        return 0
    if args.locate:
        print(json.dumps(gm_locate_tool(args.locate, kind=args.kind, max_reads=args.max_reads, source=args.source), ensure_ascii=False, indent=2))
        return 0
    if args.symbol:
        print(json.dumps(gm_symbol_tool(args.symbol, kind=args.kind, module=args.module, source=args.source), ensure_ascii=False, indent=2))
        return 0
    if args.inspect:
        print(json.dumps(gm_inspect_tool(args.inspect, name=args.name, id=args.id, source=args.source), ensure_ascii=False, indent=2))
        return 0
    if args.answer:
        print(json.dumps(gm_answer(args.answer, top=args.top or 3, source=args.source), ensure_ascii=False, indent=2))
        return 0
    if args.map:
        print(json.dumps(gm_map_tool(source=args.source), ensure_ascii=False, indent=2))
        return 0
    run_stdio_server()
    return 0


if __name__ == "__main__":
    sys.exit(main())
