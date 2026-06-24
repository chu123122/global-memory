"""CLI for semantic retrieval."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness.config import MEMORY_ROOT
from harness.semantic.engine import query_index
from harness.semantic.errors import SemanticError
from harness.semantic.eval import run_eval
from harness.semantic.index import DEFAULT_INDEX_PATH, build_index, check_stale, status_path
from harness.semantic.sources import DEFAULT_SOURCE_MANIFEST, add_source_to_manifest, load_source_registry, validate_source_registry


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.semantic.cli")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--memory-root", type=Path, default=MEMORY_ROOT)
    parser.add_argument("--manifest", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_index_arg(command: argparse.ArgumentParser) -> None:
        command.add_argument("--index", type=Path, default=argparse.SUPPRESS)

    build_p = sub.add_parser("build")
    add_index_arg(build_p)
    build_p.add_argument("--json", action="store_true")

    sync_p = sub.add_parser("sync")
    add_index_arg(sync_p)
    sync_p.add_argument("--json", action="store_true")

    stale_p = sub.add_parser("check-stale")
    add_index_arg(stale_p)
    stale_p.add_argument("--json", action="store_true")

    sources_p = sub.add_parser("sources")
    sources_sub = sources_p.add_subparsers(dest="sources_command", required=True)
    sources_list = sources_sub.add_parser("list")
    sources_list.add_argument("--json", action="store_true")
    sources_check = sources_sub.add_parser("check")
    sources_check.add_argument("--json", action="store_true")
    sources_add = sources_sub.add_parser("add")
    sources_add.add_argument("--id", required=True)
    sources_add.add_argument("--root", type=Path, required=True)
    sources_add.add_argument("--include", action="append", required=True)
    sources_add.add_argument("--exclude", action="append", default=[])
    sources_add.add_argument("--source-type", default="external_docs")
    sources_add.add_argument("--priority", type=int, default=50)
    sources_add.add_argument("--disabled", action="store_true")
    sources_add.add_argument("--json", action="store_true")

    status_p = sub.add_parser("status")
    add_index_arg(status_p)
    status_p.add_argument("--json", action="store_true")

    query_p = sub.add_parser("query")
    add_index_arg(query_p)
    query_p.add_argument("query")
    query_p.add_argument("--top", type=int, default=5)
    query_p.add_argument("--debug", action="store_true")

    eval_p = sub.add_parser("eval")
    add_index_arg(eval_p)
    eval_p.add_argument("--fixture", type=Path)
    eval_p.add_argument("--golden", type=Path)
    eval_p.add_argument("--negative", type=Path)
    eval_p.add_argument("--with-baseline", action="store_true")
    eval_p.add_argument("--save-policy", action="store_true")

    args = parser.parse_args(argv)
    manifest = args.manifest
    try:
        if args.command in {"build", "sync"}:
            stats = build_index(index_path=args.index, memory_root=args.memory_root, manifest_path=manifest)
            data = {
                "index": str(stats.index_path),
                "filesSeen": stats.files_seen,
                "filesIndexed": stats.files_indexed,
                "chunks": stats.chunks_indexed,
                "vectors": stats.vectors_indexed,
                "reusedFiles": stats.reused_files,
                "staleRemoved": stats.stale_removed,
            }
            _print_json(data)
            return 0
        if args.command == "check-stale":
            _print_json(check_stale(index_path=args.index, memory_root=args.memory_root, manifest_path=manifest).to_dict())
            return 0
        if args.command == "sources":
            manifest_path = manifest or DEFAULT_SOURCE_MANIFEST
            if args.sources_command == "list":
                sources = load_source_registry(memory_root=args.memory_root, manifest_path=manifest)
                _print_json({"sources": [source.to_dict() for source in sources]})
                return 0
            if args.sources_command == "check":
                sources = load_source_registry(memory_root=args.memory_root, manifest_path=manifest)
                _print_json(validate_source_registry(sources))
                return 0
            if args.sources_command == "add":
                sources = add_source_to_manifest(
                    source_id=args.id,
                    root=args.root,
                    include=args.include,
                    exclude=args.exclude,
                    enabled=not args.disabled,
                    source_type=args.source_type,
                    priority=args.priority,
                    manifest_path=manifest_path,
                )
                _print_json({"ok": True, "manifest": str(manifest_path), "sources": [source.to_dict() for source in sources]})
                return 0
        if args.command == "status":
            _print_json(status_path(args.index))
            return 0
        if args.command == "query":
            _print_json(query_index(args.query, index_path=args.index, top_n=args.top, debug=args.debug))
            return 0
        if args.command == "eval":
            _print_json(run_eval(index_path=args.index, fixture=args.fixture, golden_path=args.golden, negative_path=args.negative, with_baseline=args.with_baseline, save_policy=args.save_policy))
            return 0
    except (SemanticError, ValueError) as exc:
        if isinstance(exc, SemanticError):
            _print_json(exc.to_dict())
        else:
            _print_json({"error_code": "SEMANTIC_CLI_ERROR", "message": str(exc)})
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
