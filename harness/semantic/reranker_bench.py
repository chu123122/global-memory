"""Benchmark optional semantic reranker backends.

This command is read-only.  It measures backend cold load plus warm rerank latency
against candidates from the local semantic index.  vLLM is intentionally treated
as an optional experimental backend; dependency or platform failures are reported
as fallback diagnostics instead of changing the MCP hot path.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from harness.semantic import reranker
from harness.semantic.engine import query_index
from harness.semantic.index import DEFAULT_INDEX_PATH
from harness.semantic.query import AcceptanceConfig

DEFAULT_QUERY = "审查模式能不能改代码"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[idx]


def run_bench(
    *,
    backend: str,
    top_k: int,
    repeats: int,
    query: str,
    index_path: Path,
    model: str,
    timeout_ms: int,
    max_chars: int,
    synthetic: bool = False,
) -> dict[str, Any]:
    fetch_start = time.perf_counter()
    if synthetic:
        candidates = [
            {
                "path": f"synthetic/{idx}.md",
                "heading_path": "Benchmark",
                "summary": f"Synthetic reranker benchmark candidate {idx}",
                "why": "synthetic fixture",
                "chunk_text": f"This is a synthetic candidate {idx} for query {query}.",
                "score": 1.0 - idx * 0.01,
                "signals": {"raw_cosine": 0.9 - idx * 0.01, "evidence_class": "vector_only"},
            }
            for idx in range(top_k)
        ]
    else:
        candidates = query_index(
            query,
            index_path=index_path,
            top_n=top_k,
            debug=True,
            acceptance_config=AcceptanceConfig.default_open(),
        )
    fetch_ms = (time.perf_counter() - fetch_start) * 1000.0
    config = reranker.RerankerConfig(
        backend=backend,
        model=model,
        top_k=top_k,
        timeout_ms=timeout_ms,
        max_chars=max_chars,
    )

    cold_start = time.perf_counter()
    cold_rows, cold_diag = reranker.rerank_candidates(query, candidates, top_n=min(5, top_k), config=config)
    cold_ms = (time.perf_counter() - cold_start) * 1000.0

    warm_latencies: list[float] = []
    warm_diags: list[dict[str, Any]] = []
    for _ in range(max(0, repeats)):
        start = time.perf_counter()
        _rows, diag = reranker.rerank_candidates(query, candidates, top_n=min(5, top_k), config=config)
        warm_latencies.append((time.perf_counter() - start) * 1000.0)
        warm_diags.append(diag)

    scores = [row.get("reranker_score") for row in cold_rows if isinstance(row.get("reranker_score"), (int, float))]
    return {
        "backend": backend,
        "model": model,
        "query": query,
        "top_k": top_k,
        "candidate_count": len(candidates),
        "candidate_fetch_ms": round(fetch_ms, 3),
        "cold_ms": round(cold_ms, 3),
        "warm_repeats": repeats,
        "warm_p50_ms": round(statistics.median(warm_latencies), 3) if warm_latencies else 0.0,
        "warm_p95_ms": round(_percentile(warm_latencies, 0.95), 3) if warm_latencies else 0.0,
        "warm_latencies_ms": [round(value, 3) for value in warm_latencies],
        "cold_diagnostics": cold_diag,
        "last_warm_diagnostics": warm_diags[-1] if warm_diags else None,
        "score_distribution": {
            "count": len(scores),
            "min": round(min(scores), 6) if scores else None,
            "max": round(max(scores), 6) if scores else None,
        },
        "notes": [
            "scores_are_uncalibrated_backend_raw_scores",
            "vllm_backend_uses_generate_yes_no_logprobs_when_available_not_stock_rerank_api",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.semantic.reranker_bench")
    parser.add_argument("--backend", choices=["sentence-transformers", "transformers", "vllm", "off"], default="sentence-transformers")
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--model", default=reranker.DEFAULT_RERANK_MODEL)
    parser.add_argument("--timeout-ms", type=int, default=reranker.DEFAULT_RERANK_TIMEOUT_MS)
    parser.add_argument("--max-chars", type=int, default=reranker.DEFAULT_RERANK_MAX_CHARS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--synthetic", action="store_true", help="use synthetic candidates instead of querying the local semantic index")
    args = parser.parse_args()
    result = run_bench(
        backend=args.backend,
        top_k=max(1, args.top_k),
        repeats=max(0, args.repeats),
        query=args.query,
        index_path=args.index,
        model=args.model,
        timeout_ms=max(1, args.timeout_ms),
        max_chars=max(200, args.max_chars),
        synthetic=bool(args.synthetic),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"backend={result['backend']} top_k={result['top_k']} candidates={result['candidate_count']}")
        print(f"cold_ms={result['cold_ms']} warm_p50_ms={result['warm_p50_ms']} warm_p95_ms={result['warm_p95_ms']}")
        print(f"fallback={result['cold_diagnostics'].get('fallback_reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
