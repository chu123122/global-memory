---
packet_id: 20260615-111501-work-user-confirmation-after-design-review
author: codex
created: 2026-06-15T11:15:01
risk_tier: 2
status: draft
---

# Change Packet: 设计审查后用户确认门

## Motivation (WHY)

- Solves the `/work` workflow gap where a design review result can be treated as implementation authorization.
- If we do not fix this, workers can start implementation after review without the user seeing the plan, trade-offs, scope, and remaining decisions.

## Scope (WHAT)

Files to modify:
- skills/work/v1/SKILL.md
- skills/work/v1/codex-adapter.md
- harness/tests/test_work_skill_tdd_rules.py
- quality/reviews/correctness.md and quality/reviews/test-quality.md as quality-gate evidence.

Files NOT touched:
- agents/CLAUDE.md semantic behavior.
- hook installation, bootstrap, settings, memory data, or sync chain.
- unrelated dirty files already present in the worktree.
- harness/scripts/render_codex_work_skill.py implementation.

New files to create:
- Task docs under D:/ClaudeTasks/active/work-user-confirmation-after-design-review.
- Quality-gate review evidence if Tier 2 gate requires it.

## Approach (HOW)

- First get a read-only Claude design proposal for where the confirmation gate belongs and what deterministic checks should prove it.
- Implement the smallest durable workflow change: the Work Mode contract must say design review is input, not authorization; implementation dispatch requires an explicit user confirmation gate.
- Prefer deterministic tests around the rendered Codex work skill or source skill text so the rule cannot silently disappear from generated Codex instructions.

## Evidence & Verification

- Pre-implementation: Claude design proposal reviewed by Codex and then summarized to the user before implementation.
- Post-implementation:
  - `python -m pytest harness/tests/test_work_skill_tdd_rules.py -k confirmation` -> FAIL before implementation, PASS after implementation.
  - `python -m pytest harness/tests/test_work_skill_tdd_rules.py` -> PASS, 15 passed.
  - `python harness\scripts\render_codex_work_skill.py --check` -> FAIL before regenerating Codex skill, PASS after `python harness\scripts\render_codex_work_skill.py`.
  - `python C:\Users\XINDONG\.claude\scripts\work_context_pack.py --task work-user-confirmation-after-design-review --json --write-status` -> PASS.
  - `python harness\scripts\change_packet.py validate quality\change-packets\20260615-111501-work-user-confirmation-after-design-review.md --json` -> PASS.
  - `python harness\scripts\quality_gate.py verify --path skills\work\v1\SKILL.md --path skills\work\v1\codex-adapter.md --path harness\tests\test_work_skill_tdd_rules.py --path quality\change-packets\20260615-111501-work-user-confirmation-after-design-review.md --json` -> PASS after adding required review evidence.

## Risks & Rollback

- Risk: adding only prompt text without a test would regress later when the Codex skill is regenerated.
- Risk: over-tightening the flow could block explicitly authorized implementation requests.
- Rollback: revert the touched skill/test/doc paths and keep the issue open; no data migration is planned.

## Intent Alignment

- Parent task: work-user-confirmation-after-design-review
- Does this serve the task's stated goal? yes; it directly implements the recorded issue that design review must be followed by user-facing plan confirmation before implementation.
