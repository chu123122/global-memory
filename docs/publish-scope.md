---
doc_type: decision_guide
status: active
last_updated: 2026-05-25
trigger:
  keywords: [concept:publish-scope, concept:privacy, concept:open-source-readiness]
  tags: [workflow, governance]
---

# Publish Scope

This repository is currently a personal active workspace, not a clean source
distribution. A public release must not assume that every tracked path is safe
to publish.

`release-check --profile oss` intentionally blocks when personal memory,
project, experiment, archive, or report data is tracked in the same tree as the
harness code.

If the selected owner decision is `keep_private_maturity_audit`, use
`release-check --profile private-audit` for local governance. That profile
preserves publish-scope and clean-export gaps as warnings; it is not evidence
that the repository is safe to publish.

The release profile also runs `scan_external_safety.py` against the planned
clean source export, not the full private workspace. High-confidence secrets are
blockers. Local machine paths in external docs, prompts, or runtime source are
warnings and are grouped by rule, top file, and remediation group so cleanup can
start from the highest-noise public files. The default external scope uses
`PUBLIC_CHANGELOG.md` as the public history surface; the local `CHANGELOG.md`
is treated as a private audit log because it preserves local provenance.

If `public_history` warnings reappear, they usually mean a public history file
contains local task paths. The current default has already chosen the
`generate_public_changelog` policy: `PUBLIC_CHANGELOG.md` is published, while
`CHANGELOG.md` remains private.

## Default External Scope

The machine-readable source of truth is
`harness/publish_scope_manifest.json`; this document explains the intent.

For a source-only external MVP, include:

- `.gitignore`
- `PUBLIC_CHANGELOG.md`
- `README.md`
- `docs/guide/CONTRIBUTING.md`
- `docs/guide/MAINTENANCE.md`
- `docs/spec/RULE_ENFORCEMENT_MATRIX.md`
- `VERSION`
- `requirements-dev.txt`
- `bootstrap.py`
- `docs/spec/MEMORY-RULES.md`
- `harness/`
- `agents/`
- `skills/`
- `templates/`
- `docs/`
- `.github/workflows/`

These paths describe and run the harness.

## Not Default External Scope

These paths are personal data, local workflow data, historical reports, or
experiment artifacts. They need export, redaction, fixture conversion, or
explicit owner approval before publication:

- `.meta/`
- `archives/`
- `CHANGELOG_archive/`
- `decisions/`
- `feedback/`
- `fixes/`
- `interview/`
- `knowledge/`
- `projects/`
- `retrospectives/`
- `tasks/`
- `test-reports/`
- `MEMORY.md`
- `MEMORY.md.proposed`
- `MEMORY-LEGACY.md`
- `docs/reference/OBSERVATIONS.md`
- `docs/guide/CONTROL_PANEL.md`

Some of these may later become examples or fixtures, but they should not be
published by default just because they are tracked locally.

## Required Resolution

Choose one path before public release:

1. Split a clean source repository containing only the external scope.
2. Move personal data into a private repo or private release artifact.
3. Convert selected data into anonymized fixtures and document that choice.
4. Keep the repository private and use the private-audit profile as a maturity audit.

## Verification

Run:

```powershell
python harness\maintain.py release-check --profile oss --json
python harness\maintain.py release-check --profile private-audit --json
python harness\scripts\check_publish_scope.py --strict --json
python harness\scripts\export_source_scope.py --strict --json
python harness\scripts\scan_external_safety.py --strict --json
python harness\scripts\release_issue_ledger.py --json
python harness\maintain.py release-decisions --json
python harness\maintain.py release-decisions --strict --json
python harness\maintain.py release-decisions --template --json
python harness\maintain.py release-record-decision --dry-run --decision publish_scope_boundary --selected-option <option> --decided-by <owner> --decided-at YYYY-MM-DD --json
python harness\scripts\release_issue_ledger.py --gap-table-only
python harness\scripts\release_issue_ledger.py --owner-decisions-only --json
python harness\scripts\release_issue_ledger.py --decision-template --json
```

`publish_scope` blockers include `private_tracked_summary`, grouped by manifest
reason, top-level path group, and match type. Use that summary to decide whether
the remaining work is a repo split, a private-path exclusion, or a fixture/docs
replacement.
`verify_output_contracts.py` treats this as a stable machine contract: the
tracked/external/private/unclassified counts, manifest finding count, grouped
summaries, sorted scope lists, blocker verdict, and
`decision_plan.required_when` must stay internally consistent.
The same blocker includes `decision_plan.decision=publish_scope_boundary`, with
the four owner choices from Required Resolution encoded as machine-readable
options.

`source_export_plan` warnings include `untracked_included_summary`, grouped by
manifest reason and top-level path group. Use that summary to decide whether the
remaining work is simply staging external files, or whether the external scope
manifest is too broad.
The same JSON includes a read-only `tracking_plan` with the exact
`git add -- ...` argument vector for external-scope untracked files; it does not
modify the Git index.
`verify_output_contracts.py` also treats this as a stable contract: source-export
counts, untracked grouping, `tracking_plan.command`, `tracking_plan.safety`, and
the `ready | ready_with_warnings | invalid` verdict must stay internally
consistent.

`release_issue_ledger.py --json` also adds `summary.open_by_gap_type`,
`summary.open_by_owner`, `summary.owner_decisions`, top-level
`owner_decisions`, `remaining_gap_table`, and per-issue `gap` metadata. Use
those fields as the current machine-readable gap table instead of relying on a
one-off human summary. Owner-decision rows in `remaining_gap_table` also carry
`required_artifacts`, `required_when`, `selected_option`, and the command that
produced the blocker, so a recorded owner choice is not mistaken for actual gate
resolution.
The gap table also exposes `summary.open_by_gap_type`; for example, a
publish-scope blocker can be routed through the owner decision queue while still
counting as `publish_scope_governance` in the gap-type summary.
They also include `allowed_options`, `record_dry_run_command`, and
`record_write_command`, so the same gap table is enough to validate or record
the owner choice without hand-writing JSON.
`summary.owner_decision_records` gives a compact health summary for the owner
decision state file: valid, invalid, missing, stale, and status counts.
`release-decisions --template --json` gives the owner-editable patch skeleton
for `harness/release_owner_decisions.json`, including `allowed_options`,
`required_update_fields`, `required_artifacts`, and `required_when`; it remains
read-only and does not choose a boundary.
`release-record-decision --dry-run ...` validates the exact selected option,
owner, and date against the current open owner queue before writing. Use
`--write` only when the publication boundary has been intentionally selected.
The dry-run/write report includes
`record_gate_effect.effect=records_owner_choice_only` and
`record_gate_effect.clears_release_blocker=false`; the record captures owner
intent but does not resolve tracked private paths.
In `release-decisions`, `record_ready=true` only means the state file contains a
valid decided record; `gate_ready=true` requires the tracked private path
condition to be resolved.
The same JSON includes `gate_unblock_requirements` with
`kind=required_conditions`, currently `private_tracked_paths` and
`unclassified_tracked_paths`, so agents can distinguish publish-scope cleanup
from license artifact work.
Record the selected publication boundary in `harness/release_owner_decisions.json`
under `decisions.publish_scope_boundary`; this records the owner choice but does
not clear the blocker until the private tracked paths are actually resolved.
For `status=decided`, `selected_option` must be one of the current
`owner_decisions[].options[].id`, and `decided_by` / `decided_at` must be filled
or the ledger reports `record_valid=false`.
Do not remove the `publish_scope_boundary` record while the blocker is open;
missing owner records fail the output contract.

Expected blocker until publication scope is resolved:

```text
id=publish_scope
tracked_private_paths>0
```

Resolved policy for public history:

```text
id=external_source_safety
verdict=ok
warnings=0
```

If the warning returns and is limited to `public_history`,
`scan_external_safety.py` emits `policy_plan.decision=public_history_policy`
with three explicit options: sanitize the public changelog, publish a sanitized
replacement changelog, or exclude the changelog from the default external source
scope.
