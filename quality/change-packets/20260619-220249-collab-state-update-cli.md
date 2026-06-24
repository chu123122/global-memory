---
packet_id: 20260619-220249-collab-state-update-cli
author: codex-lead
created: 2026-06-19T22:02:49
risk_tier: 2
status: submitted
---

# Change Packet: collab state update cli

## Motivation (WHY)

- The current collab state artifact can be generated, but there is no deterministic command to update it after a lead manually dispatches a runtime-shaped payload or receives a worker report.
- Without a state update CLI, the migration remains a static planning tool; users would hand-edit JSON, making replay, evidence capture, and later runtime adapters inconsistent.
- This slice creates the smallest usable lifecycle loop: generate plan/state -> dispatch with an available runtime tool or manually -> record worker/session/report/status in state.

## Scope (WHAT)

Files to modify:
- `harness/collab/state.py`
- `harness/collab/__init__.py`
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
- real worker/session process spawning

New files to create:
- `harness/scripts/collab_state.py`
- `harness/tests/test_collab_state_cli.py`
- `quality/reviews/collab-state-cli/{correctness,test-quality,risk-security,maintainability}.md`

## Approach (HOW)

- Add a narrow CLI around the existing `CollabState` model: validate/show state, update one dispatch by ID, and write either in-place or to a separate output path.
- Keep the state file as explicit user-selected JSON. The command will not discover tasks, write hidden files, or call worker tools.
- Make update operations immutable in the library and deterministic in the CLI so tests can assert exact status/worker/report outcomes.

## Evidence & Verification

- Pre-implementation: `harness/collab/state.py` already validates state shape and supports immutable `update_dispatch`; adapter/state quality gate is PASS.
- Post-implementation: `python -m pytest harness/tests/test_collab_config.py harness/tests/test_collab_plan.py harness/tests/test_collab_adapters.py harness/tests/test_collab_state.py harness/tests/test_collab_state_cli.py -q`
- Post-implementation: `python harness/scripts/collab_state.py --state <tmp> --validate --json`
- Post-implementation: `python harness/scripts/collab_state.py --state <tmp> --dispatch-id 01-find --status running --worker-id worker-1 --json`
- Post-implementation: `python harness/scripts/check_capability_manifest.py --json`
- Post-implementation: path-limited `quality_gate.py verify --review-dir quality/reviews/collab-state-cli ... --json`

## Risks & Rollback

- Risk: The CLI could silently overwrite the wrong file. Mitigation: require explicit `--state`; default output is the same explicit file, and tests cover `--out` copy behavior.
- Risk: Report text could be confused with authoritative verification. Mitigation: state stores report strings as evidence pointers only; lead still verifies tests/runtime behavior.
- Risk: Scope creep toward real dispatching. Mitigation: no tool invocation, no process spawn, no client readiness claim.
- Rollback: remove `harness/scripts/collab_state.py`, `harness/tests/test_collab_state_cli.py`, review evidence, and revert docs/manifest/state exports. Existing plan/state generation remains usable.

## Intent Alignment

- Parent task: xd-maker-agent-collab-standalone
- Yes. It makes the host-neutral collab plugin materially more useful by allowing a lead to track real or manual dispatch progress without depending on XDMaker's localDb/session store.
