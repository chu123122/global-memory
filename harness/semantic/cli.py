"""CLI for the semantic retrieval PoC."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness.semantic.engine import query_index
from harness.semantic.errors import SemanticError
from harness.semantic.eval import run_eval
from harness.semantic.index import DEFAULT_INDEX_PATH, build_index, status_path


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.semantic.cli")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build")
    build_p.add_argument("--json", action="store_true")

    status_p = sub.add_parser("status")
    status_p.add_argument("--json", action="store_true")

    query_p = sub.add_parser("query")
    query_p.add_argument("query")
    query_p.add_argument("--top", type=int, default=5)
    query_p.add_argument("--debug", action="store_true")

    eval_p = sub.add_parser("eval")
    eval_p.add_argument("--fixture", type=Path)
    eval_p.add_argument("--golden", type=Path)
    eval_p.add_argument("--negative", type=Path)
    eval_p.add_argument("--with-baseline", action="store_true")
    eval_p.add_argument("--save-policy", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            stats = build_index(index_path=args.index)
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
        if args.command == "status":
            _print_json(status_path(args.index))
            return 0
        if args.command == "query":
            _print_json(query_index(args.query, index_path=args.index, top_n=args.top, debug=args.debug))
            return 0
        if args.command == "eval":
            _print_json(run_eval(index_path=args.index, fixture=args.fixture, golden_path=args.golden, negative_path=args.negative, with_baseline=args.with_baseline, save_policy=args.save_policy))
            return 0
    except SemanticError as exc:
        _print_json(exc.to_dict())
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())


