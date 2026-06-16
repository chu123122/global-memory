---
packet_id: 20260616-150351-triage-issue-and-feedback-batch-cleanup
author: codex
created: 2026-06-16T15:03:51
risk_tier: 2
status: submitted
---

# Change Packet: triage issue and feedback batch cleanup

## Motivation (WHY)

- User chose the previously proposed issue-cleanup and full feedback digestion path after reviewing every current inbox item.
- Without this, resolved/routed issues and obsolete feedback stay in `/triage` forever, hiding genuinely actionable items behind known backlog/noise.

## Scope (WHAT)

Files to modify:
- `issues/ISSUE-2026-06-03-registry-single-source-autoindex.md`
- `issues/ISSUE-2026-06-03-rules-layer-minor-backlog.md`
- `feedback/feedback_diff_workflow.md`
- `feedback/feedback_skill_deployment_layout.md`
- `CHANGELOG.md`
- `quality/verification.md`
- `quality/reviews/correctness.md`
- `quality/reviews/test-quality.md`

Files NOT touched:
- hooks / retrieve / statusline
- `harness/scripts/triage_inbox.py` scan semantics
- active long-term preference feedback files that are still valid

New files to create:
- this Change Packet only

## Approach (HOW)

- Mark `registry-single-source-autoindex` as `routed`, not `closed`, because the partial fix is real but full single-source SoT remains future `/work` scope.
- Mark `rules-layer-minor-backlog` as `deferred`, because it is a low-priority bundle of independent minor follow-ups and should not stay as an open inbox blocker.
- Mark obsolete automatic VS Code diff feedback as `superseded`; update skill deployment wording in place while keeping it `active`.

## Evidence & Verification

- Pre-implementation: `triage_inbox.py --json` reported 2 open issues and 15 active feedback items; user approved the proposed handling.
- Post-implementation:
  - `python harness/scripts/triage_inbox.py --verify-close <path> --json` for the two issues and superseded feedback.
  - `python harness/scripts/triage_inbox.py --json` to confirm inbox shrink.
  - `python bootstrap.py check` for updated skill deployment guidance.
  - `python harness/maintain.py doctor --json` and limited `quality_gate.py verify --path ... --json`.

## Risks & Rollback

- Risk: routed/deferred issue status may hide remaining work. Mitigation: closure records include explicit target / future trigger and preserve the original content.
- Risk: obsolete diff feedback might still be useful historically. Mitigation: mark `superseded`, not delete.
- Rollback: set the two issue statuses back to `open`, set `feedback_diff_workflow.md` back to `active`, and revert the skill deployment wording update.

## Intent Alignment

- Parent task: triage-batch-cleanup
- Does this serve the task's stated goal? yes — it applies the user-approved triage decisions while preserving traceability and machine-verifiable close evidence.
