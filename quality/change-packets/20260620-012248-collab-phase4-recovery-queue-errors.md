---
packet_id: 20260620-012248-collab-phase4-recovery-queue-errors
author: codex-worker-sqt3yzub9jibk4obiqwdaq2r
created: 2026-06-20T01:22:48
risk_tier: 2
status: submitted
---

# Change Packet: collab phase4 recovery queue errors

## Motivation (WHY)

- Phase 4 currently has lead-operated plan/state/replay/dispatch, but lacks stable JSON error codes, deterministic multi-worker queue semantics, recovery advice for interrupted runs, and executable examples.
- Without this, long-running collaboration remains hard to resume, failures are not machine-diagnosable, and new collab scripts would be orphaned from manifest/registry checks.

## Scope (WHAT)

Files to modify:
- `harness/collab/__init__.py`
- `harness/collab/state.py`
- `harness/scripts/collab_plan.py`
- `harness/scripts/collab_state.py`
- `harness/scripts/collab_replay.py`
- `harness/scripts/collab_dispatch.py`
- `harness/capability_manifest.json`
- `docs/scripts-registry.md`
- `CHANGELOG.md`

Files NOT touched:
- `agents/CLAUDE.md`
- `harness/client_manifest.json`
- `harness/hooks/**`, `bootstrap.py`, runtime settings
- `D:\xdt-maker-main\**`
- `D:\ClaudeTasks\active\xd-maker-agent-collab-standalone\**`

New files to create:
- `harness/collab/errors.py`
- `harness/collab/queue.py`
- `harness/collab/recover.py`
- `harness/scripts/collab_queue.py`
- `harness/scripts/collab_recover.py`
- `harness/tests/test_collab_errors.py`
- `harness/tests/test_collab_queue.py`
- `harness/tests/test_collab_queue_cli.py`
- `harness/tests/test_collab_recover.py`
- `harness/tests/test_collab_recover_cli.py`
- `harness/tests/test_collab_error_contract_cli.py`
- `examples/collab/README.md`
- `examples/collab/run_minimal_flow.py`

## Approach (HOW)

- Introduce a small `CollabError` hierarchy with stable `error_code` values and shared CLI JSON helpers; update existing collab CLIs to add `error_code` while preserving existing `kind`/`error` fields.
- Add a host-neutral JSON queue model that supports enqueue, lease, retry/requeue, completion, labels, concurrency limits, and stale lease detection without spawning workers or writing a database.
- Add a recovery analyzer that reads plan/state/queue artifacts and emits deterministic warnings/actions for stale running items, plan/state mismatches, schema/version mismatches, and queue conflicts.

## Evidence & Verification

- Pre-implementation: Phase 4 handoff and design require P4-5..P4-8; existing collab modules establish JSON file + CLI pattern and non-spawning adapter boundary.
- Post-implementation: run `python -m pytest <collab tests> -q`; `python examples\collab\run_minimal_flow.py --out <tmp>`; `python harness\scripts\check_capability_manifest.py --json`; `python harness\scripts\scan_orphan_scripts.py --strict --json`; `python harness\generate_catalog.py --check --json`; path-limited `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-phase4 ... --json`.

## Risks & Rollback

- Risk: queue/recovery semantics drift from existing state/replay assumptions; mitigated by deterministic tests over plan/state/queue fixtures and backward-compatible CLI error JSON.
- Risk: new scripts become unregistered; mitigated by updating manifest and scripts registry and running scan checks.
- Rollback: remove the new collab modules/scripts/tests/examples and revert the listed edits; no hooks/bootstrap/client runtime state is modified.

## Intent Alignment

- Parent task: xd-maker-agent-collab-standalone
- Does this serve the task's stated goal? yes; it directly implements Phase 4 P4-5..P4-8 code-side acceptance without expanding into UI or automatic worker spawning.
