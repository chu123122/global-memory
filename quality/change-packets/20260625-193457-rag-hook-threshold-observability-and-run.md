---
packet_id: 20260625-193457-rag-hook-threshold-observability-and-run
author: Codex
created: 2026-06-25T19:34:57
risk_tier: 3
status: draft
---

# Change Packet: rag-hook-threshold-observability-and-runtime-brief

## Motivation (WHY)

- Current hook logs show hit/abstain/elapsed/top refs, but do not expose enough threshold evidence to tune pre-rerank and reranker gates safely.
- Current runtime/config questions (hook list, MCP exposure, RAG refresh state, why the hook did not inject) should be answered from live deterministic files/logs, not by semantic recall thresholds.

## Scope (WHAT)

Files to modify:
- `harness/hooks/retrieve_inject.py`
- `harness/gm_mcp/search.py`
- `harness/scripts/retrieve_threshold_report.py`
- `harness/tests/test_policy_fact_inject.py`
- `harness/tests/test_retrieve_threshold_report.py`
- `harness/capability_manifest.json`
- `docs/scripts-registry.md`
- `docs/hook-chain.md`
- `docs/主循环与日志地图.md`
- `rules/接入索引.md`

Files NOT touched:
- Production threshold constants (`0.622`, `4.625`) are not changed.
- Runtime log files under `~/.global-memory/logs/` are not migrated or rewritten.
- `agents/CLAUDE.md` behavior semantics are not edited.

New files to create:
- `harness/scripts/retrieve_threshold_report.py`
- `harness/tests/test_retrieve_threshold_report.py`

## Approach (HOW)

- Add gm.search debug fields for top candidates, raw cosine and active thresholds, then mirror them into retrieve JSONL records while keeping the existing one-line JSONL schema backward compatible.
- Add a deterministic runtime/config short-circuit in `retrieve_inject.py` for current hook/MCP/RAG status questions so those prompts do not call `gm.search`.
- Add a read-only report script with optional local JSONL labels (`query_id -> useful|noise|unclear`) to summarize abstain/injection behavior and suggest observation windows without editing thresholds.

## Evidence & Verification

- Pre-implementation: repo entrance docs, hook-chain docs, registry, current `retrieve_inject.py`, `gm_mcp/search.py`, sidecar and existing tests were inspected; dirty tree was noted before changes.
- Post-implementation: run targeted pytest for policy/runtime hook behavior, sidecar, threshold report, policy fact, hook alignment, smoke hooks and quality gate path-scoped verification.

## Risks & Rollback

- Risk: hook hot path grows too slow or noisy. Mitigation: runtime brief uses bounded log tails and RAG still calls the warm sidecar with timeout/fail-open behavior.
- Risk: report interpretation is mistaken as automatic tuning. Mitigation: script and docs state read-only/advisory; production thresholds are unchanged.
- Rollback: revert the listed source/test/doc files; no runtime logs or production thresholds require migration rollback.

## Intent Alignment

- Parent task: rag-hook-threshold-observability
- Does this serve the task's stated goal? Yes: it adds threshold observability first, keeps thresholds unchanged, introduces lightweight labels, and separates current runtime facts from semantic RAG decisions.
