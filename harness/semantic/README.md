# Semantic Retrieval PoC

Status: **PoC only; not deployed; not connected to hot-path retrieve**.

This package is a local, read-only, auditable semantic retrieval experiment for `global-memory`.  It intentionally leaves the existing hot-path retrieval stack untouched: it does **not** modify or call into `harness/scripts/harness_retrieve.py`, hooks, or `client_context.py` runtime injection.

## How to run

From repository root (`~/.claude/global-memory`):

```powershell
python -m harness.semantic.cli build
python -m harness.semantic.cli status
python -m harness.semantic.cli query "审查模式能不能改代码" --top 10
python -m harness.semantic.cli query "审查模式能不能改代码" --top 10 --debug
python -m harness.semantic.cli eval --with-baseline
python -m harness.semantic.cli eval --with-baseline --save-policy
python -m harness.semantic.reranker_bench --backend sentence-transformers --top-k 30 --json
python -m harness.semantic.phase7_eval preflight --timeout-ms 20000 | Set-Content -Encoding utf8 .tmp/phase7-preflight.json
python -m harness.semantic.phase7_eval calibrate --top-k 10 --max-chars 800 --timeout-ms 20000 | Set-Content -Encoding utf8 .tmp/phase7-calibration.json
```

Notes:
- `build` requires local Ollama embedding endpoint only (`bge-m3`, loopback `http://127.0.0.1:11434/api/embed` by default).
- `--save-policy` persists the calibrated acceptance policy into `harness/data/semantic_index.sqlite` metadata.
- The SQLite index is a generated artifact and is ignored by git via `harness/data/semantic_index.sqlite*`.

## Architecture

- `corpus.py` — scans the B-scope markdown corpus recursively, parses frontmatter, chunks by headings, maps authority tiers, skips deprecated docs.
- `embed.py` — calls local Ollama `bge-m3`, validates loopback-only endpoints and 1024-dim embeddings, normalizes vectors, stores float32 blobs.
- `index.py` — builds and validates SQLite schema (`meta/chunks/fts5/fts/vectors/token_df`), stores chunks, FTS5 text, vectors, and acceptance policy metadata.
- `query.py` — pure ranking/gating logic: RRF fusion, capped authority bonus, evidence classes, pointer-only output, accepted/reject debug signals.
- `reranker.py` — optional Phase 5 reranker layer for `gm.search`: default `sentence-transformers`, optional official `transformers` yes/no scoring path, experimental vLLM backend for benchmarks, and explicit fallback diagnostics.
- `reranker_bench.py` — read-only benchmark command for cold load, warm p50/p95, TopK latency, and score distribution.
- `phase7_eval.py` — original Phase 7 report command: stable-config preflight first, then threshold/abstain/must-not-return calibration; it never writes production thresholds.
- `engine.py` — read-only query orchestration: lexical/metadata/vector recall, token filtering, policy loading, pointer ranking.
- `tokens.py` — v1 heuristic low-information token filter plus content-token helpers; build-time `token_df` provides the data-derived high-DF guardrail.
- `calibration.py` — v1 heuristic acceptance-policy calibration over golden/negative fixtures using absolute raw signals, not normalized RRF confidence.
- `eval.py` — fixture metrics: Recall@5, Recall@10, MRR, Hit@1, negative false-positive rate, optional baseline comparison.
- `errors.py` — stable `SemanticError(errorCode, message)` contract for fail-loud behavior.
- `cli.py` — CLI entry point for `build/status/query/eval`.

## What worked

Independent verification showed this PoC can build and evaluate a local semantic index:

- Build corpus: **132 files / 1628 chunks / 1628 vectors**.
- Golden fixture: **Recall@10 = 1.0**, **Recall@5 = 0.75**.
- Baseline on in-scope golden cases: **Recall@10 = 0.0** for the existing keyword retrieve baseline in the measured fixture slice.
- Negative control: **13/13 held-out negative questions blocked** in tester verification after Phase 2 gating fixes.
- Fully local: only loopback Ollama is allowed; no remote LLM, no sqlite-vec, no Chroma/Qdrant/LlamaIndex/LangChain.


## Phase 5 local reranker selection

`gm.search` now has an optional in-process reranker stage after hybrid recall and before delivery gating.  Default configuration is:

```text
GM_SEARCH_RERANKER=sentence-transformers
GM_SEARCH_RERANK_MODEL=Qwen/Qwen3-Reranker-0.6B
GM_SEARCH_RERANK_TOPK=30
GM_SEARCH_RERANK_TIMEOUT_MS=5000
GM_SEARCH_RERANK_MAX_CHARS=2000
```

Operational notes:

- `GM_SEARCH_RERANKER=off` preserves the pre-reranker retrieval order.
- `sentence-transformers` uses `CrossEncoder(...).predict([(query, doc), ...])` and is the MVP default.
- `transformers` follows Qwen's yes/no log-prob scoring shape and keeps scores explicitly uncalibrated.
- `vllm` is benchmark-only / experimental for now; it uses generate-time yes/no logprobs, not an assumed stock `/rerank` compatibility path.
- Any dependency load failure, backend exception, or timeout returns the original candidate order with `fallback_reason`; it must not be reported as successful reranking.

Benchmark commands:

```powershell
python -m harness.semantic.reranker_bench --backend sentence-transformers --top-k 30 --json
python -m harness.semantic.reranker_bench --backend transformers --top-k 30 --json
python -m harness.semantic.reranker_bench --backend vllm --top-k 30 --json
python -m harness.semantic.reranker_bench --backend off --top-k 5 --synthetic --json  # script smoke without Ollama/index
```

Do not promote vLLM into the MCP stdio process unless measurements show warm Top30 latency is unacceptable for the in-process backends and a sidecar with health checks, timeout, and fallback is justified.


## Phase 6 expanded-set checkpoint (2026-06-25)

Expanded fixtures were exercised on `golden_expanded_100.json` and `negative_expanded_50.json` after switching the default Python environment to CUDA PyTorch (`torch 2.10.0+cu130`, RTX 5060 Ti).  The checkpoint result is directional only, not a valid final benchmark:

- No-rerank baseline: `Recall@5=0.49`, `Recall@10=0.54`, `MRR=0.3562`, `Hit@1=0.27`, negative FPR `0.08`.
- Qwen reranker directionally improved retrieval: observed `Recall@5=0.72`, `Recall@10=0.77`, `MRR=0.5453`, `Hit@1=0.44`, negative FPR `0.04`.
- The reranker run is **invalid as a strict benchmark** because `reranker_fallback_count=25/150`; every fallback was `timeout_ms_exceeded` under `GM_SEARCH_RERANK_TOPK=30`, `GM_SEARCH_RERANK_MAX_CHARS=2000`, and `GM_SEARCH_RERANK_TIMEOUT_MS=20000`.
- Local rewrite bakeoff is paused/removed from the current path.  The partial `qwen3:4b` rewrite run produced heavy timeout fallback (`rewrite_fallback_count=122/150`) and did not justify continuing `qwen2.5:7b` / `phi4-mini` tests.
- Current conclusion: reranker is promising enough to keep as the next optimization target, but rewrite should not be pursued until the reranker latency/fallback profile is controlled.

Artifacts: `D:\global-memory\.tmp\phase6_rerank_rewrite_bakeoff\`.

## Honest limitations

This is not a production replacement for current retrieval.

- The working system is essentially **content-token anchored hybrid retrieval + vector reranking**.  It is not a robust semantic abstention system.
- `vector_only` is explicitly disabled in the saved acceptance policy.  This keeps precision high but means **English-only or pure paraphrase semantic recall is not recovered** unless lexical/content-token evidence also supports it.
- Abstention is based on absolute thresholds and heuristic token filtering.  The current policy is a **v1 heuristic calibrated on a small fixture set** (golden + negative + held-out checks, roughly dozens not hundreds of cases).  Statistical strength is limited.
- Phase 3 tested two non-LLM abstain ideas and found them insufficient for this small mixed corpus:
  - global top1 vector cosine could not separate in-domain from off-topic queries;
  - free directory/facet partitioning still had overlapping governance-positive vs off-topic distributions.
- The package is **not deployed** and **not wired into hot-path retrieve**.
- For the current small and heterogeneous repository, grep / existing retrieval remains a reasonable ROI choice; semantic RAG becomes more attractive only if the corpus grows or hot-path automatic prevention becomes necessary.

## When to revisit

Reopen this PoC if one of these becomes true:

- The memory corpus grows large enough that grep/keyword retrieval no longer gives acceptable operator latency or recall.
- Hot-path automatic rule-prevention requires semantic matching across paraphrases and English/Chinese queries.
- There is budget to add the missing query-understanding layer locally.

Likely next steps then:

1. Return to the original **Phase 7: Eval + Threshold Calibration** path, but run the reranker stable-config preflight first.  This is a prerequisite for Phase 7 calibration, not a newly invented phase.
2. Preflight the fixed Qwen/sentence-transformers/20s setup with `topK/max_chars` = `10/800`, `15/1000`, `20/1000`, and `30/2000` as the failure control.  Any config with `reranker_fallback_count > 0` is invalid for threshold calibration.
3. Use only a valid preflight config for `phase7_eval calibrate`; output threshold/abstain/must-not-return recommendations as a report, and do not auto-apply production thresholds.
4. Keep local LLM rewrite/domain-classifier work paused unless a later task has a concrete abstention/query-normalization need and a latency budget.
5. Add HyDE or explicit query expansion only after reranker latency is stable.
6. Re-evaluate deployment only after independent held-out tests show both precision and semantic recall improve over the current baseline.
