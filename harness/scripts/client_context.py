#!/usr/bin/env python3
"""Stable context-brief CLI for non-hook clients.

This is the generic client contract: any CLI client can call it to get the same
Context Brief payload that Claude Code receives through retrieve_inject.py,
without requiring Claude Code hooks or settings.json.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from harness_retrieve import (  # noqa: E402
    DEFAULT_MEMORY_ROOT,
    DEFAULT_TASK_ROOT,
    MIN_SCORE_DEFAULT,
    _cache_path_for,
    retrieve,
    write_retrieve_log,
)


def read_query(args: argparse.Namespace) -> str:
    if args.query:
        return args.query
    if args.query_file:
        return Path(args.query_file).read_text(encoding="utf-8", errors="replace")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    query = read_query(args).strip()
    if not query:
        return {
            "schema_version": 1,
            "kind": "client_context",
            "client_id": args.client,
            "contract": "global-memory.context-brief.v1",
            "task": args.task,
            "stage": args.stage,
            "ok": False,
            "error": "empty_query",
            "brief": None,
            "brief_text": "",
            "elapsed_ms": 0.0,
        }, 1

    memory_root = Path(args.memory_root)
    task_root = Path(args.task_root)
    cache_path = Path(args.cache) if args.cache else _cache_path_for(memory_root)
    t0 = time.perf_counter()
    brief = retrieve(
        task_name=args.task,
        user_msg=query,
        stage=args.stage,
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
        task_tags=[tag.strip() for tag in args.tags.split(",") if tag.strip()],
        top_n=args.top,
        min_score=args.min_score,
        task_level_fallback_enabled=not args.disable_task_level_fallback,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if args.log:
        write_retrieve_log(
            task_name=args.task,
            user_msg=query,
            brief=brief,
            elapsed_ms=elapsed_ms,
            extras={"source": "client_context", "client_id": args.client},
        )

    payload = {
        "schema_version": 1,
        "kind": "client_context",
        "client_id": args.client,
        "contract": "global-memory.context-brief.v1",
        "task": brief.task,
        "stage": brief.stage,
        "ok": True,
        "error": "",
        "brief": asdict(brief),
        "brief_text": brief.to_yaml_like(),
        "elapsed_ms": round(elapsed_ms, 1),
    }
    return payload, 0


def emit_text(payload: dict[str, Any]) -> None:
    if not payload.get("ok"):
        print(f"error: {payload.get('error', 'unknown')}")
        return
    print(payload.get("brief_text", "").rstrip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", default="generic_cli", help="client id for audit/provenance")
    parser.add_argument("--task", default="unknown", help="task name used for handoff and task-scoped fallback")
    parser.add_argument("--query", default="", help="query text; stdin is used when omitted")
    parser.add_argument("--query-file", default="", help="read query text from file")
    parser.add_argument("--stage", default=None)
    parser.add_argument("--memory-root", default=str(DEFAULT_MEMORY_ROOT))
    parser.add_argument("--task-root", default=str(DEFAULT_TASK_ROOT))
    parser.add_argument("--cache", default="")
    parser.add_argument("--tags", default="", help="comma-separated task tags")
    parser.add_argument("--top", type=int, default=2)
    parser.add_argument("--min-score", type=float, default=MIN_SCORE_DEFAULT)
    parser.add_argument("--disable-task-level-fallback", action="store_true")
    parser.add_argument("--log", action="store_true", help="write retrieve log; default is read-only/no log")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    payload, rc = build_payload(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        emit_text(payload)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
