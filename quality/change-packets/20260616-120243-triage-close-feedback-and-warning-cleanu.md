---
packet_id: 20260616-120243-triage-close-feedback-and-warning-cleanu
author: codex
created: 2026-06-16T12:02:43
risk_tier: 2
status: submitted
---

# Change Packet: triage close feedback and warning cleanup

## Motivation (WHY)

- 用户在 `/triage` 中选择 A：优先处理两条可闭环 feedback 与两个 doctor warning。
- 不处理会导致已被新流程取代的 feedback 长期 active，且 `maintain.py doctor` 持续带可修 warning，降低 inbox/health 信噪比。

## Scope (WHAT)

Files to modify:
- `feedback/feedback_archive_feedback_loop.md`
- `feedback/feedback_harness_maintenance_flow.md`
- `agents/CLAUDE.md`
- `harness/scripts/task_experience_index.py`
- `harness/tests/test_warning_cleanup.py`
- `CHANGELOG.md`
- Path-canonicalization files touched by `fix_hardcoded_paths.py --fix`: `AGENTS.md`, `decisions/decision_quality_gate_evidence_antifake.md`, `quality/change-packets/20260615-100000-change-packet-gate.md`, `skills/work/v1/SKILL.md`

Files NOT touched:
- hooks / retrieve / statusline
- `harness/maintain.py` doctor aggregation logic
- full `registry-single-source-autoindex` issue design

New files to create:
- this Change Packet only

## Approach (HOW)

- Close the two feedback sources as `superseded`, not `drop`, because their core principles remain but are now implemented through `/triage` and `register_script.py` rather than the old prose workflows.
- Resolve prompt-system warning by adding only a compact priority/Agent-extension sentence to `agents/CLAUDE.md`; no large legacy prompt restoration.
- Resolve smoke hardcoded-path warning by replacing the one production hardcoded `D:\ClaudeTasks` with shared `CLAUDE_TASKS_ROOT`, and by running the existing path fixer for canonical `~/.claude/global-memory` doc references.

## Justification for modifying agents/CLAUDE.md

- The selected warning is emitted because the global behavior contract itself lacks a machine-visible priority / Agent extension marker. Updating only downstream verifier logic would hide the mismatch rather than document the contract.
- The change is deliberately one sentence in the preamble and does not alter the numbered hard boundaries; it clarifies precedence and that Agent extensions cannot relax hard boundaries.

## Evidence & Verification

- Pre-implementation: `triage_inbox.py --json` identified both feedback as active; `verify_prompt_system.py --json` showed warning(s); `smoke_test.py --json` pointed at `fix_hardcoded_paths.py` warning.
- Post-implementation:
  - `python harness/scripts/triage_inbox.py --verify-close feedback/feedback_archive_feedback_loop.md --json`
  - `python harness/scripts/triage_inbox.py --verify-close feedback/feedback_harness_maintenance_flow.md --json`
  - `python harness/verify/verify_prompt_system.py --json`
  - `python harness/verify/smoke_test.py --json`
  - `pytest harness/tests/test_warning_cleanup.py -q`
  - `python harness/maintain.py doctor --json`
  - limited `quality_gate.py verify --path ... --json`

## Risks & Rollback

- Risk: feedback closure could hide a still-useful rule. Mitigation: use `superseded` with explicit reason and keep the file searchable.
- Risk: canonical path replacement could make local D: path less visible. Mitigation: `~/.claude/global-memory` is a junction to the live repo and is the intended portable path.
- Rollback: revert this packet plus the listed file changes; feedback can be set back to `status: active` if the supersession is rejected.

## Intent Alignment

- Parent task: triage-warning-cleanup
- Does this serve the task's stated goal? yes — it closes two confirmed triage sources with mechanical verification and clears the selected doctor warning path without broad architecture changes.
