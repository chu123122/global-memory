#!/usr/bin/env python3
"""retrieve_trace.py - explain retrieve scoring and task-context fallback.

This is read-only diagnostics. It imports harness_retrieve directly and does
not append retrieve_calls.jsonl.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

import harness_retrieve as retrieve_mod  # type: ignore

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _brief_size(brief: retrieve_mod.ContextBrief) -> dict[str, int]:
    text = brief.to_yaml_like()
    return {"chars": len(text), "bytes": len(text.encode("utf-8"))}


def _load_downrank(config_path: Path | None) -> tuple[set[str], float, str, str]:
    try:
        paths, factor, source = retrieve_mod.load_downrank_config(config_path)
        return paths, factor, source, ""
    except Exception as exc:
        return set(), 1.0, "", str(exc)


def _load_fallback(config_path: Path | None) -> tuple[bool, int, set[str], str, str]:
    try:
        enabled, limit, allow, source = retrieve_mod.load_task_context_fallback_config(config_path)
        return enabled, limit, allow, source, ""
    except Exception as exc:
        return False, 600, set(), "", str(exc)


def _resolve_fallback(args: argparse.Namespace, task_root: Path) -> tuple[bool, int, set[str], str, str, Path | None]:
    config_path = Path(args.task_context_fallback_config) if args.task_context_fallback_config else None
    if config_path:
        enabled, limit, allow, source, error = _load_fallback(config_path)
        return enabled, limit, allow, source, error, config_path
    try:
        enabled, limit, source = retrieve_mod.load_task_level_fallback_config(task_root, args.task)
        allow = {args.task} if enabled else set()
        return enabled, limit, allow, source, "", None
    except Exception as exc:
        return False, 600, set(), "", str(exc), None


def _trace_candidates(
    entries: list[dict[str, Any]],
    query: str,
    *,
    stage: str | None,
    task_tags: list[str],
    min_score: float,
    downrank_paths: set[str],
    downrank_factor: float,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        row = retrieve_mod.score_entry_trace(entry, query, stage, task_tags)
        raw_score = float(row["final_score"])
        final_score = raw_score
        downranked = False
        if raw_score >= min_score and downrank_paths and retrieve_mod.normalize_path_key(row["path"]) in downrank_paths:
            final_score = raw_score * downrank_factor
            downranked = True
        row.update({
            "raw_score": round(raw_score, 4),
            "final_score": round(final_score, 4),
            "passed_min_score": final_score >= min_score,
            "downrank_applied": downranked,
            "downrank_factor": downrank_factor if downranked else None,
        })
        rows.append(row)
    rows.sort(key=lambda r: (float(r["final_score"]), float(r["raw_score"])), reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    interesting = [r for r in rows if r["passed_min_score"] or r["contributions"]]
    return interesting[:limit]


def _top_paths(brief: retrieve_mod.ContextBrief) -> list[str]:
    return [str(p.get("path") or "") for p in brief.relevant_pointers]


def _phase(
    name: str,
    query: str,
    *,
    entries: list[dict[str, Any]],
    task_name: str,
    stage: str | None,
    memory_root: Path,
    task_root: Path,
    cache_path: Path,
    task_tags: list[str],
    top_n: int,
    min_score: float,
    downrank_config: Path | None,
    downrank_paths: set[str],
    downrank_factor: float,
    candidate_limit: int,
) -> dict[str, Any]:
    expanded_query, aliases = retrieve_mod.expand_query(query, retrieve_mod.load_aliases())
    candidates = _trace_candidates(
        entries,
        expanded_query,
        stage=stage,
        task_tags=task_tags,
        min_score=min_score,
        downrank_paths=downrank_paths,
        downrank_factor=downrank_factor,
        limit=candidate_limit,
    )
    brief = retrieve_mod.retrieve(
        task_name=task_name,
        user_msg=query,
        stage=stage,
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
        task_tags=task_tags,
        top_n=top_n,
        min_score=min_score,
        downrank_config=downrank_config,
        task_context_fallback_config=None,
        task_level_fallback_enabled=False,
    )
    return {
        "name": name,
        "query_chars": len(query),
        "expanded_query_chars": len(expanded_query),
        "alias_targets": aliases,
        "candidate_count_shown": len(candidates),
        "candidates": candidates,
        "brief": {
            "handoff_path": brief.handoff_path,
            "top_paths": _top_paths(brief),
            "pointers": brief.relevant_pointers,
            "warnings": brief.warnings,
            "size": _brief_size(brief),
        },
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    memory_root = Path(args.memory_root)
    task_root = Path(args.task_root)
    cache_path = Path(args.cache) if args.cache else retrieve_mod._cache_path_for(memory_root)
    task_tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    downrank_config = Path(args.downrank_config) if args.downrank_config else None

    entries = retrieve_mod.load_trigger_cache(cache_path, memory_root)
    downrank_paths, downrank_factor, downrank_source, downrank_error = _load_downrank(downrank_config)
    fallback_enabled, fallback_limit, fallback_allow, fallback_source, fallback_error, fallback_config = _resolve_fallback(args, task_root)

    default_phase = _phase(
        "default",
        args.query,
        entries=entries,
        task_name=args.task,
        stage=args.stage,
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
        task_tags=task_tags,
        top_n=args.top,
        min_score=args.min_score,
        downrank_config=downrank_config,
        downrank_paths=downrank_paths,
        downrank_factor=downrank_factor,
        candidate_limit=args.candidates,
    )

    fallback_triggered = False
    fallback_skipped_reason = ""
    context_query = args.query
    context_chars = 0
    context_sources: list[str] = []
    opt_in_phase: dict[str, Any] | None = None
    if not fallback_enabled and not fallback_config:
        fallback_skipped_reason = "no_fallback_config"
    elif not fallback_enabled:
        fallback_skipped_reason = "fallback_config_disabled"
    elif fallback_allow and args.task not in fallback_allow:
        fallback_skipped_reason = f"task_not_allowed:{args.task}"
    elif default_phase["brief"]["top_paths"]:
        fallback_skipped_reason = "baseline_has_hits"
    elif not args.query.strip():
        fallback_skipped_reason = "empty_query"
    else:
        context_query, context_chars, context_sources = retrieve_mod.build_task_context_query(
            args.query,
            args.task,
            task_root,
            context_limit=fallback_limit,
        )
        fallback_triggered = context_chars > 0
        if not fallback_triggered:
            fallback_skipped_reason = "no_task_context"

    if fallback_triggered:
        opt_in_phase = _phase(
            "task_context_fallback",
            context_query,
            entries=entries,
            task_name=args.task,
            stage=args.stage,
            memory_root=memory_root,
            task_root=task_root,
            cache_path=cache_path,
            task_tags=task_tags,
            top_n=args.top,
            min_score=args.min_score,
            downrank_config=downrank_config,
            downrank_paths=downrank_paths,
            downrank_factor=downrank_factor,
            candidate_limit=args.candidates,
        )
        actual = retrieve_mod.retrieve(
            task_name=args.task,
            user_msg=args.query,
            stage=args.stage,
            memory_root=memory_root,
            task_root=task_root,
            cache_path=cache_path,
            task_tags=task_tags,
            top_n=args.top,
            min_score=args.min_score,
            downrank_config=downrank_config,
            task_context_fallback_config=fallback_config,
            task_level_fallback_enabled=fallback_config is None,
        )
        opt_in_phase["brief"] = {
            "handoff_path": actual.handoff_path,
            "top_paths": _top_paths(actual),
            "pointers": actual.relevant_pointers,
            "warnings": actual.warnings,
            "size": _brief_size(actual),
        }

    return {
        "schema_version": 1,
        "mode": "read-only-retrieve-trace",
        "inputs": {
            "task": args.task,
            "query": args.query,
            "stage": args.stage,
            "memory_root": str(memory_root),
            "task_root": str(task_root),
            "cache": str(cache_path),
            "top": args.top,
            "min_score": args.min_score,
            "candidate_limit": args.candidates,
            "downrank_config": str(downrank_config) if downrank_config else None,
            "task_context_fallback_config": str(fallback_config) if fallback_config else None,
        },
        "index": {
            "entries": len(entries),
        },
        "downrank": {
            "enabled": bool(downrank_paths),
            "factor": downrank_factor,
            "paths": len(downrank_paths),
            "source": downrank_source,
            "error": downrank_error,
        },
        "fallback": {
            "config_enabled": fallback_enabled,
            "allowlist": sorted(fallback_allow),
            "source": fallback_source,
            "error": fallback_error,
            "triggered": fallback_triggered,
            "skipped_reason": fallback_skipped_reason,
            "context_chars": context_chars,
            "context_sources": context_sources,
        },
        "default": default_phase,
        "opt_in": opt_in_phase,
        "summary": {
            "default_hits": len(default_phase["brief"]["top_paths"]),
            "opt_in_hits": len(opt_in_phase["brief"]["top_paths"]) if opt_in_phase else None,
            "new_hits": (
                len(set(opt_in_phase["brief"]["top_paths"]) - set(default_phase["brief"]["top_paths"]))
                if opt_in_phase else 0
            ),
            "brief_bytes_default": default_phase["brief"]["size"]["bytes"],
            "brief_bytes_opt_in": opt_in_phase["brief"]["size"]["bytes"] if opt_in_phase else None,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Retrieve Trace / 检索追踪",
        "",
        "## Summary / 摘要",
        "",
        f"- task / 任务: `{report['inputs']['task']}`",
        f"- query / 原始查询: `{report['inputs']['query']}`",
        f"- entries / 可评分记忆条目数: `{report['index']['entries']}`",
        f"- default_hits / 默认命中数: `{report['summary']['default_hits']}`",
        f"- opt_in_hits / opt-in 命中数: `{report['summary']['opt_in_hits']}`",
        f"- new_hits / 新增命中数: `{report['summary']['new_hits']}`",
        f"- fallback_triggered / 是否触发 fallback: `{report['fallback']['triggered']}`",
        f"- fallback_context_chars / fallback 注入字符数: `{report['fallback']['context_chars']}`",
        f"- fallback_sources / fallback 上下文来源: `{', '.join(report['fallback']['context_sources']) or '-'}`",
        f"- brief_bytes_default / 默认 brief 字节数: `{report['summary']['brief_bytes_default']}`",
        f"- brief_bytes_opt_in / opt-in brief 字节数: `{report['summary']['brief_bytes_opt_in']}`",
        "",
    ]
    for key in ("default", "opt_in"):
        phase = report.get(key)
        if not phase:
            continue
        phase_label = "默认检索" if phase["name"] == "default" else "任务上下文 fallback"
        lines += [
            f"## {phase['name']} / {phase_label}",
            "",
            f"- query_chars / 当前查询字符数: `{phase['query_chars']}`",
            f"- expanded_query_chars / alias 后查询字符数: `{phase['expanded_query_chars']}`",
            f"- alias_targets / 命中的别名扩展: `{', '.join(phase['alias_targets']) or '-'}`",
            f"- top_paths / 最终进入 brief 的路径: `{', '.join(phase['brief']['top_paths']) or '-'}`",
            f"- warnings / 运行警告: `{'; '.join(phase['brief']['warnings']) or '-'}`",
            "",
            "### Candidates / 候选评分",
            "",
        ]
        if not phase["candidates"]:
            lines.append("- none above trace interest threshold / 没有候选产生有效贡献或通过阈值")
        for row in phase["candidates"]:
            contrib = ", ".join(_format_contribution(c) for c in row.get("contributions", [])) or "no contribution / 无贡献"
            lines.append(
                f"- rank / 排名 {row['rank']} score / 最终分={row['final_score']} "
                f"raw / 原始分={row['raw_score']} passed / 过阈值={row['passed_min_score']} `{row['path']}`"
            )
            lines.append(f"  - why / 命中原因: {row['why']}")
            lines.append(f"  - contributions / 分数贡献: {contrib}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_contribution(c: dict[str, Any]) -> str:
    kind = c.get("kind")
    if kind == "priority":
        return f"priority / 优先级:{c.get('match')} x{c.get('factor')} {c.get('before')}->{c.get('after')}"
    label = {
        "keyword": "关键词",
        "fuzzy": "模糊匹配",
        "tag": "任务标签",
        "stage": "阶段",
        "description": "描述兜底",
    }.get(str(kind), str(kind))
    return f"{kind} / {label}:{c.get('match')} +{c.get('delta')}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Trace retrieve scoring and fallback behavior.")
    p.add_argument("--task", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--stage", default=None)
    p.add_argument("--memory-root", default=str(retrieve_mod.DEFAULT_MEMORY_ROOT))
    p.add_argument("--task-root", default=str(retrieve_mod.DEFAULT_TASK_ROOT))
    p.add_argument("--cache", default=None)
    p.add_argument("--tags", default="")
    p.add_argument("--top", type=int, default=retrieve_mod.MAX_POINTERS)
    p.add_argument("--min-score", type=float, default=retrieve_mod.MIN_SCORE_DEFAULT)
    p.add_argument("--candidates", type=int, default=8, help="number of scored candidates to show per phase")
    p.add_argument("--downrank-config", default=None)
    p.add_argument("--task-context-fallback-config", default=None)
    p.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = p.parse_args(argv)

    report = build_report(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
