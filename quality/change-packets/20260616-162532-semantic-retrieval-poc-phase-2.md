---
packet_id: 20260616-162532-semantic-retrieval-poc-phase-2
author: codex-worker-gt29259zqt6o6y5cy75wihah
created: 2026-06-16T16:25:32
risk_tier: 3
status: submitted
---

# Change Packet: semantic retrieval PoC (Phase 2 + Phase 3 negative result + archival README)

## Motivation (WHY)

- Implement and preserve a local, read-only, auditable hybrid semantic retrieval PoC for global-memory.
- Evaluate whether FTS5 + local bge-m3 vectors + RRF + authority/pointer output can improve recall over the current keyword-only baseline.
- Record the final product decision honestly: the PoC is useful as evidence, but is not deployed because non-LLM abstention could not recover semantic/paraphrase recall without precision risk on the current small mixed corpus.

## Scope (WHAT)

Files modified:
- `.gitignore` to exclude generated semantic SQLite artifacts.
- This Change Packet to reflect final scope and validation evidence.

No new runtime dependencies were added.

Files NOT touched:
- `harness/scripts/harness_retrieve.py`
- `hooks/`
- `harness/scripts/client_context.py`
- `agents/CLAUDE.md`
- Existing injection/retrieve runtime paths

New files to create:
- `harness/semantic/__init__.py`
- `harness/semantic/corpus.py`
- `harness/semantic/embed.py`
- `harness/semantic/index.py`
- `harness/semantic/query.py`
- `harness/semantic/eval.py`
- `harness/semantic/calibration.py`
- `harness/semantic/tokens.py`
- `harness/semantic/errors.py`
- `harness/semantic/cli.py`
- `harness/semantic/README.md`
- `harness/semantic/fixtures/golden.json`
- `harness/semantic/fixtures/negative.json`
- `harness/semantic/fixtures/semantic_positives.json`
- `harness/tests/test_semantic_query.py`
- `harness/tests/test_semantic_corpus.py`
- `harness/tests/test_semantic_eval.py`
- `harness/tests/test_semantic_engine.py`
- `harness/tests/test_semantic_errors.py`

## Approach (HOW)

- Build an isolated `harness.semantic` package with CLI entry `python -m harness.semantic.cli`; imports use `harness/config.py` for `MEMORY_ROOT` and default index path under `harness/data/semantic_index.sqlite`.
- Use SQLite FTS5 plus local Ollama `bge-m3` embeddings from loopback only; store normalized float32 vector blobs and query via in-process dot product, with explicit error codes for local embed failures.
- Keep ranking relevance-led: BM25 and vector channels feed weighted RRF, then apply capped additive authority bonus (`epsilon=0.05`) to fused relevance.
- Use pointer-only output and debug/eval raw signals (`raw_rrf`, channel ranks, raw BM25, raw cosine, evidence class, accept/reject reason).
- Calibrate a v1 heuristic acceptance policy using absolute signals and content-token filtering; explicitly disable `vector_only` rather than hiding rejection behind impossible cosine thresholds.
- Preserve Phase 3 negative results in `harness/semantic/README.md`: non-LLM abstention via global cosine and free directory facets did not separate in-domain from off-topic queries well enough for deployment.

## Evidence & Verification

- `python -m unittest discover -s harness/tests -p "test_semantic_*.py"` passes.
- `python -m harness.semantic.cli build` produced 132 files / 1628 chunks / 1628 vectors.
- `python -m harness.semantic.cli eval --with-baseline --save-policy` measured golden Recall@5=0.75, Recall@10=1.0, negative FPR=0.0, baseline Recall@10=0.0 on in-baseline fixture slice.
- Tester held-out negative verification blocked 13/13 off-topic questions.
- Phase 3 read-only measurements showed global cosine and governance-facet cosine distributions overlap, so the PoC is not deployed.
- Path-limited quality gate passes; forbidden paths (`harness/scripts/harness_retrieve.py`, `hooks/`, `harness/scripts/client_context.py`) have no diff.

## Risks & Rollback

- Ollama unavailable or embedding dimension mismatch can block build/query; the implementation fails loudly with explicit `errorCode` instead of silently falling back.
- SQLite FTS5 availability may vary by Python build; tests and status/build commands expose this early.
- The current acceptance policy is heuristic and disables vector-only acceptance, so semantic/paraphrase recall is intentionally limited.
- Rollback is deleting the new `harness/semantic/` package, new `harness/tests/test_semantic_*.py` tests, generated `harness/data/semantic_index.sqlite`, and this Change Packet; no existing runtime retrieval/hook file is modified.

## Intent Alignment

- Parent task: global-memory-semantic-retrieval-survey
- Final alignment: preserve a self-contained PoC artifact and evidence trail, while clearly marking it as not deployed and not connected to hot-path retrieve. The implementation preserves explicit no-touch boundaries and gives future work a reproducible starting point if corpus size or hot-path needs change.

