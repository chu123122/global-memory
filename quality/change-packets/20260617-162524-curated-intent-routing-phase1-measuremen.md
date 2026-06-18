---
packet_id: 20260617-162524-curated-intent-routing-phase1-measuremen
author: codex-worker-b3egw1exug37enty0du8jpje
created: 2026-06-17T16:25:24
risk_tier: 2
status: draft
---

# Change Packet: curated intent routing phase1 measurement

## Motivation (WHY)

- Phase 1 needs data to decide whether curated intent bank + Q2Q routing is separable before investing in full curation or production retrieval changes.
- Without this measurement, the task would repeat the archived PoC failure mode: implementing a route/gate before proving recall and abstain distributions separate.

## Scope (WHAT)

Files to modify:
- `harness/semantic/fixtures/intent_bank.json`
- `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/measure_intent_bank.py`
- `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/测试.md`
- `D:/ClaudeTasks/active/global-memory-curated-intent-routing/ops/CHANGELOG.md`

Files NOT touched:
- `harness/scripts/harness_retrieve.py`
- `harness/hooks/**`
- `harness/scripts/client_context.py`
- production retrieval or hook wiring

New files to create:
- `harness/semantic/fixtures/intent_bank.json`
- `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/measure_intent_bank.py`
- `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/phase1_measurement.json`

## Approach (HOW)

- Build a small curated intent bank with train paraphrases and held-out positives separated per high-frequency intent; reuse existing fixture intent semantics and true answer_ref paths.
- Measure Q2doc by embedding the exact same evaluation queries against the rebuilt SQLite chunk-vector index; measure Q2Q by embedding the bank train paraphrases and taking top cosine over case vectors.
- Report held-out positives as the go/no-go basis, and report in-bank exclude-self positives only as an optimistic upper bound to expose overfitting gap.

## Evidence & Verification

- Pre-implementation: Phase card and lead approval require held-out positives, same query set, same bge-m3 model, Q2doc/Q2Q cosine parity, and forbidden-file boundaries.
- Post-implementation: run JSON validation for the bank, rebuild semantic index with loopback bge-m3, run measurement script, inspect distributions in `test/测试.md`, and run scoped quality gate over this task's changed files.

## Risks & Rollback

- Risk: curated train/held-out wording may still be style-correlated with developer wording; mitigated by separating held-out and by tester's unseen held-out set.
- Risk: Q2doc baseline changes after rebuilding the index because corpus changed; this is accepted by lead and recorded.
- Rollback: delete the new bank/script and task output files or revert the exact changed paths; no production retrieval files are modified.

## Intent Alignment

- Parent task: global-memory-curated-intent-routing
- Does this serve the task's stated goal? yes; it only measures Phase 1 H1/H2 and avoids production routing, full curation, hooks, and commits.
