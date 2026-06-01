---
doc_type: decision_guide
status: active
last_updated: 2026-05-25
trigger:
  keywords: [concept:license, concept:open-source-readiness]
  tags: [workflow, governance]
---

# License Decision

`release-check --profile oss` intentionally blocks when `LICENSE`,
`LICENSE.md`, or `COPYING` is missing. The license is a project-owner decision,
not something automation should choose.

This page records the decision surface so the blocker is actionable.
`release_issue_ledger.py --json` also carries this as
`oss-project_metadata.evidence.decision_plan` and as a top-level
`owner_decisions[]` entry, so the owner choice is visible in the
machine-readable issue ledger without traversing every issue.
Use `python harness\maintain.py release-decisions --json` when the only
question is which project-owner choices remain. Use
`python harness\maintain.py release-decisions --strict --json` when automation
should fail until the owner queue is ready while still receiving parseable JSON.
Use `python harness\maintain.py release-decisions --template --json` to get a
machine-readable patch template with allowed option IDs and required fields for
the owner-editable state file.
Use `python harness\maintain.py release-record-decision --dry-run --decision
license_policy --selected-option <option> --decided-by <owner> --decided-at
YYYY-MM-DD --json` to validate the exact state-file update before writing it.
Use the same command with `--write` only after the owner choice is intentional.
The dry-run/write report includes
`record_gate_effect.effect=records_owner_choice_only` and
`record_gate_effect.clears_release_blocker=false`; recording the owner choice is
necessary bookkeeping, not proof that `release-check` will pass.
In `release-decisions`, `record_ready=true` only means the state file contains a
valid decided record; `gate_ready=true` requires the release blocker itself to
be resolved.
The same JSON includes `gate_unblock_requirements` with
`kind=required_artifacts` for `LICENSE`, `LICENSE.md`, and `COPYING`; at least
one of those artifacts must exist for the metadata blocker to clear.
Record the chosen option in `harness/release_owner_decisions.json` under
`decisions.license_policy`; then add the required license artifact so the gate
can actually resolve.
Do not remove the `license_policy` record while the blocker is open; missing
owner records fail the output contract.

## Current State

Status: undecided.

Current blocker:

```powershell
python harness\maintain.py release-check --profile oss --json
```

Expected blocker until a license is chosen:

```text
id=project_metadata
missing=LICENSE / LICENSE.md / COPYING
```

## Common Options

| Option | Typical meaning | Tradeoff |
|---|---|---|
| MIT | Permissive reuse with minimal obligations. | Very simple, but offers little patent language. |
| Apache-2.0 | Permissive reuse plus explicit patent grant. | Longer license text; often preferred for tooling. |
| BSD-3-Clause | Permissive reuse with attribution and no endorsement. | Similar permissive posture, no Apache-style patent terms. |
| AGPL-3.0 | Strong copyleft including network use. | Stronger reciprocity, much heavier adoption constraint. |
| No public license | Source visible but not open-source reusable. | Honest if the project is not ready for external reuse. |

This is not legal advice. The owner should choose based on intended reuse,
company/IP constraints, and whether external users may copy, modify, and
redistribute the code.

## Decision Checklist

1. Decide whether the repository should permit external reuse at all.
2. If yes, choose a license family.
3. Update `harness/release_owner_decisions.json` with `status=decided`,
   `selected_option`, `decided_by`, and `decided_at`. `selected_option` must be
   one of the current `owner_decisions[].options[].id`; otherwise the ledger
   reports `record_valid=false`.
   Generate the current editable skeleton with
   `python harness\maintain.py release-decisions --template --json`.
   Validate the exact record first with
   `python harness\maintain.py release-record-decision --dry-run --decision license_policy --selected-option <option> --decided-by <owner> --decided-at YYYY-MM-DD --json`.
   Replace `--dry-run` with `--write` only after the owner choice is intentional.
4. Add one of `LICENSE`, `LICENSE.md`, or `COPYING` at the repository root.
5. Mention the license in `README.md`.
6. Run:

```powershell
python harness\maintain.py release-check --profile oss --json
```

## Do Not

- Do not add a license just to make the gate green.
- Do not let scripts generate a license text without an explicit owner choice.
- Do not call the project open-source while this blocker remains unresolved.
