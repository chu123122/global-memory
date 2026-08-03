---
packet_id: 20260626-182740-gm-r3-work-runner-repair-limit
author: Codex
created: 2026-06-26T18:27:40
risk_tier: 2
status: draft
---

# Change Packet: GM-R3 work runner repair limit

## Motivation (WHY)

- Add a bounded repair loop after `/work check` so verifier feedback can drive codex-exec fixes without unbounded automatic retries.
- If this is not added, repeated verifier failures can either require manual orchestration every time or risk ambiguous retry semantics where initial checks consume the same budget as real worker repairs.

## Scope (WHAT)

Files to modify:
- `harness/work_runner.py`
- `harness/scripts/work_runner.py`
- `harness/tests/test_work_runner.py`
- `harness/tests/test_work_skill_tdd_rules.py`
- `skills/work/SKILL.md`
- `skills/work/codex-adapter.md`
- `docs/scripts-registry.md`

Generated/runtime artifacts:
- `C:\Users\XINDONG\.codex\skills\codex-work\SKILL.md` regenerated from source + adapter.

Files NOT touched:
- `agents/CLAUDE.md`
- hook manifests/bootstrap behavior
- verifier command implementations

New files to create:
- this Change Packet only

## Approach (HOW)

- Add `repair_loop(..., worker="codex-exec")` as a separate entrypoint requiring existing `gate-feedback.json` with `gate=process-fail`.
- Track `repair_attempt` / `max_repair_attempts` independently from verifier-only checks; `/work check` remains diagnostic and keeps `repair_attempt=0`.
- On the third failed repair verifier result, overwrite feedback with `WORK_RUNNER_REPAIR_LIMIT_REACHED`, `failure_kind=repair-limit`, and block the run state.

## Evidence & Verification

- Pre-implementation: inspected current `harness/work_runner.py`, CLI wrapper, work skill, Codex adapter, and existing runner tests.
- Post-implementation:
  - `python -m pytest harness\tests\test_work_runner.py harness\tests\test_work_skill_tdd_rules.py -q` -> 43 passed
  - `python D:\global-memory\harness\scripts\render_codex_work_skill.py --check` -> up to date
  - `python D:\global-memory\harness\scripts\check_hook_alignment.py --strict --json` -> verdict aligned
  - `python D:\global-memory\harness\scripts\check_capability_manifest.py --json` -> verdict ok
  - `python D:\global-memory\harness\scripts\scan_orphan_scripts.py --strict --json` -> verdict ok
  - `python D:\global-memory\harness\scripts\change_packet.py validate D:\global-memory\quality\change-packets\20260626-182740-gm-r3-work-runner-repair-limit.md --json` -> PASS
  - `python D:\global-memory\harness\scripts\quality_gate.py verify --path ... --json` -> PASS

## Risks & Rollback

- Risk: repair loop semantics may diverge from legacy `attempt` / `failure_streak` expectations. Mitigation: tests cover check-not-counted, pass-on-first-repair, three verifier failures, fourth no-start, infra fail stop, and invalid feedback rejection.
- Rollback: revert the listed source/test/doc files plus regenerate `C:\Users\XINDONG\.codex\skills\codex-work\SKILL.md` from the previous source state.

## Intent Alignment

- Parent task: gm-r3-work-runner-repair-limit
- Does this serve the task's stated goal? yes; it implements the explicit `/work repair --worker codex-exec` bounded repair loop with max 3 real worker starts and blocked state on limit.
