---
packet_id: 20260619-214615-collab-adapter-payload-and-state-skeleto
author: codex-lead
created: 2026-06-19T21:46:15
risk_tier: 2
status: submitted
---

# Change Packet: collab adapter payload and state skeleton

## Motivation (WHY)

- The first collab skeleton can validate agent config and render worker prompts, but it stops before the two pieces that make a migration practically usable: runtime-shaped adapter payloads and replayable workflow state.
- XDMaker's Orca value is not only prompt text; it also has session links, worker status, and lead/worker message routing. If global-memory keeps only a static plan, later Codex/Claude/Orca integration will re-invent incompatible payload and state shapes.
- This slice still avoids launching clients. It adds deterministic adapter payload metadata and a lightweight state artifact so future runtime adapters can consume the same contract.

## Scope (WHAT)

Files to modify:
- `harness/collab/__init__.py`
- `harness/collab/adapters.py`
- `harness/collab/plan.py`
- `harness/scripts/collab_plan.py`
- `harness/capability_manifest.json`
- `docs/capabilities.md`
- `docs/scripts-registry.md`
- `harness/README.md`
- `quality/verification.md`

Files NOT touched:
- `harness/client_manifest.json` (do not claim full lifecycle readiness)
- hooks / bootstrap / runtime settings
- `agents/CLAUDE.md`
- `D:/xdt-maker-main/**`
- real worker/session process spawning

New files to create:
- `harness/collab/state.py`
- `harness/tests/test_collab_adapters.py`
- `harness/tests/test_collab_state.py`
- `quality/reviews/collab-adapter-state/{correctness,test-quality,risk-security,maintainability}.md`

## Approach (HOW)

- Add adapter payload builders as declarative dictionaries: they describe which runtime tool could consume the dispatch and with what arguments, but keep `spawns_process=false` and never call tools from Python.
- Add a minimal JSON state model with stable `plan_id`, dispatch statuses, optional worker/session IDs, and reports. This gives a replay/checkpoint artifact without introducing a database or tying state to XDMaker localDb.
- Extend `collab_plan.py` with optional payload/state output flags while preserving the existing default Markdown/JSON behavior.

## Evidence & Verification

- Pre-implementation: first collab skeleton tests and quality gate PASS; Phase 2 boundary says state and adapter contracts are next migration layer, while UI/runtime spawning stay deferred.
- Post-implementation: `python -m pytest harness/tests/test_collab_config.py harness/tests/test_collab_plan.py harness/tests/test_collab_adapters.py harness/tests/test_collab_state.py -q`
- Post-implementation: `python harness/scripts/collab_plan.py --intent "adapter smoke" --adapter-payloads --json`
- Post-implementation: `python harness/scripts/collab_plan.py --intent "state smoke" --state-out <tmp-file> --json`
- Post-implementation: `python harness/scripts/check_capability_manifest.py --json`
- Post-implementation: path-limited `quality_gate.py verify --review-dir quality/reviews/collab-adapter-state ... --json`

## Risks & Rollback

- Risk: Adapter payloads look executable and overclaim runtime support. Mitigation: docs and payloads explicitly mark them as declarative and non-spawning.
- Risk: State schema becomes a second task database. Mitigation: keep it as optional JSON artifact scoped to collab replay/checkpoints only.
- Risk: CLI grows too much. Mitigation: only add opt-in flags; existing default outputs and tests remain stable.
- Rollback: revert `harness/collab/adapters.py`, `harness/collab/plan.py`, `harness/scripts/collab_plan.py`, remove `harness/collab/state.py`, new tests, registry/docs entries, verification/review evidence. No persistent user data or hooks are changed.

## Intent Alignment

- Parent task: xd-maker-agent-collab-standalone
- Yes. It advances the task from a static plugin skeleton toward a practical XDMaker-style collaboration migration by preserving worker dispatch and state concepts in a host-neutral form.
