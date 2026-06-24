---
packet_id: 20260619-221803-collab-replay-runbook-helper
author: codex-lead
created: 2026-06-19T22:18:03
risk_tier: 2
status: submitted
---

# Change Packet: collab replay runbook helper

## Motivation (WHY)

- The collab plugin can now generate plans/payloads and update state, but the lead still has to manually inspect raw JSON to decide which dispatch is next and which runtime command/state-update command to run.
- A replay/runbook helper makes the migration materially more usable without crossing into automatic process spawning: it turns plan + state into ordered action cards.
- Without this, the feature is technically valid but still awkward for real work because the bridge between payload and state is implicit.

## Scope (WHAT)

Files to modify:
- `harness/collab/__init__.py`
- `harness/collab/adapters.py`
- `harness/capability_manifest.json`
- `docs/capabilities.md`
- `docs/scripts-registry.md`
- `harness/README.md`
- `README.md`
- `skills/collab/v1/SKILL.md`
- `quality/verification.md`

Files NOT touched:
- `harness/client_manifest.json`
- hooks / bootstrap / runtime settings
- `agents/CLAUDE.md`
- `D:/xdt-maker-main/**`
- real worker/session process spawning or tool invocation

New files to create:
- `harness/collab/replay.py`
- `harness/scripts/collab_replay.py`
- `harness/tests/test_collab_replay.py`
- `harness/tests/test_collab_replay_cli.py`
- `quality/reviews/collab-replay-runbook/{correctness,test-quality,risk-security,maintainability}.md`

## Approach (HOW)

- Add a deterministic runbook builder that reads a plan and optional state, skips done dispatches by default, and emits action cards with adapter payload, worker prompt, and exact `collab_state.py` update command examples.
- Keep runtime action cards as data/Markdown only. The helper names possible runtime tools but does not call them.
- Support `--include-done` for audit/replay and `--adapter` filtering for focused runtime use.

## Evidence & Verification

- Pre-implementation: collab plan/state/state-update tests are PASS; task docs identify runtime replay helper as the next useful non-spawning step.
- Post-implementation: `python -m pytest harness/tests/test_collab_config.py harness/tests/test_collab_plan.py harness/tests/test_collab_adapters.py harness/tests/test_collab_state.py harness/tests/test_collab_state_cli.py harness/tests/test_collab_replay.py harness/tests/test_collab_replay_cli.py -q`
- Post-implementation: `python harness/scripts/collab_replay.py --plan <plan.json> --state <state.json> --json`
- Post-implementation: `python harness/scripts/check_capability_manifest.py --json`
- Post-implementation: path-limited `quality_gate.py verify --review-dir quality/reviews/collab-replay-runbook ... --json`

## Risks & Rollback

- Risk: Runbook text could be mistaken for automatic dispatch. Mitigation: every payload keeps `spawns_process=false`; docs say it is copy/execute guidance for the lead.
- Risk: Plan/state mismatch could hide work. Mitigation: tests cover done filtering and state status merge; missing state falls back to pending view.
- Risk: CLI surface becomes too broad. Mitigation: only read plan/state and emit runbook; state mutation remains in `collab_state.py`.
- Rollback: remove replay module/script/tests/reviews and registry/docs references. Existing plan/state/update functionality remains.

## Intent Alignment

- Parent task: xd-maker-agent-collab-standalone
- Yes. It turns the already verified plugin skeleton into a more complete usable workflow by connecting dispatch payloads to state-update evidence without overclaiming full lifecycle runtime automation.
