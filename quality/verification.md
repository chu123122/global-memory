# Verification Summary - global-memory curated intent routing Phase 1 measurement

Scope: Phase 1 read-only measurement for curated intent-bank Q2Q routing. Production retrieval, hooks, `harness/scripts/harness_retrieve.py`, and `harness/scripts/client_context.py` are not modified.

## Deterministic Checks

- `python harness/scripts/change_packet.py validate quality/change-packets/20260617-162524-curated-intent-routing-phase1-measuremen.md --json` -> PASS.
- `python -m py_compile D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/measure_intent_bank.py` -> PASS.
- JSON parse for `harness/semantic/fixtures/intent_bank.json` -> PASS.
- `python -m pytest D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/test_measure_intent_bank.py -q` -> PASS, 3 tests.
- `python -m harness.semantic.cli build` -> PASS, rebuilt current corpus index: filesSeen=143, chunks=1679, vectors=1679.
- `python D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/measure_intent_bank.py --json-out D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/phase1_measurement.json --markdown-out D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/测试.md` -> PASS.

## Test Evidence

- Unit tests cover the key deterministic measurement invariants: invalid duplicate bank ids fail, Q2Q optimistic mode excludes the exact same bank case, and threshold selection prefers the lowest zero-negative tau with best positive acceptance.
- Measurement output records held-out positives as the main basis, train exclude-self as an optimistic upper bound, Q2doc/Q2Q per-row cosines, intent-match, overfit gap, and tau scan.
- Task evidence is written to `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/测试.md` and raw JSON to `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/phase1_measurement.json`.

## Human decision

human decision: Orca lead approved the Phase 1 plan, required held-out positives as the GO/NO-GO basis, allowed local semantic index rebuild, and delegated final H1/H2 judgment to tester independent held-out plus reviewer口径审.

## Rollback / Recovery

- Rollback: remove `harness/semantic/fixtures/intent_bank.json`, `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/measure_intent_bank.py`, and `D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/test_measure_intent_bank.py`; restore task `test/测试.md` and `ops/CHANGELOG.md` from git or task archive.
- Recovery: if measurement output is stale, rerun `python -m harness.semantic.cli build` and then the measurement command above. The generated SQLite index is gitignored and can be deleted/rebuilt.
- No production route/hook state is changed, so rollback does not require deployment or environment changes.
