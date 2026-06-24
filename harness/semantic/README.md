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
- `engine.py` — read-only query orchestration: lexical/metadata/vector recall, token filtering, policy loading, pointer ranking.
- `tokens.py` — v1 heuristic low-information token filter plus content-token helpers; build-time `token_df` provides the data-derived high-DF guardrail.
- `calibration.py` — v1 heuristic acceptance-policy calibration over golden/negative fixtures using absolute raw signals, not normalized RRF confidence.
- `eval.py` — fixture metrics: Recall@5, Recall@10, MRR, negative false-positive rate, optional baseline comparison.
- `errors.py` — stable `SemanticError(errorCode, message)` contract for fail-loud behavior.
- `cli.py` — CLI entry point for `build/status/query/eval`.

## What worked

Independent verification showed this PoC can build and evaluate a local semantic index:

- Build corpus: **132 files / 1628 chunks / 1628 vectors**.
- Golden fixture: **Recall@10 = 1.0**, **Recall@5 = 0.75**.
- Baseline on in-scope golden cases: **Recall@10 = 0.0** for the existing keyword retrieve baseline in the measured fixture slice.
- Negative control: **13/13 held-out negative questions blocked** in tester verification after Phase 2 gating fixes.
- Fully local: only loopback Ollama is allowed; no remote LLM, no sqlite-vec, no Chroma/Qdrant/LlamaIndex/LangChain.

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

1. Add a local LLM rewrite / domain classifier layer for abstention and query normalization.
2. Add HyDE or explicit query expansion for English/paraphrase governance questions.
3. Expand golden, semantic-positive, and negative fixtures substantially before tuning thresholds.
4. Re-evaluate deployment only after independent held-out tests show both precision and semantic recall improve over the current baseline.
