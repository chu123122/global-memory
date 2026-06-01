---
doc_type: guide
status: active
last_updated: 2026-05-26
trigger:
  keywords: [concept:getting-started, concept:install, concept:open-source-readiness]
  tags: [workflow, tooling]
---

# Getting Started

This guide is the external-entry path for evaluating the project without
adopting the author's full personal workflow.

Current boundary: this is a Claude Code harness plus global memory governance
system. It also exposes a stable generic CLI Context Brief contract. Full lifecycle governance is stable only for Claude Code; Codex CLI-specific lifecycle integration is still experimental.

## Prerequisites

- Windows or a Python environment that can run the harness scripts.
- Python 3.12 or compatible Python 3.
- Git.
- Claude Code if you want runtime hooks and `~/.claude/settings.json`
  integration.

No network access is required for the default readiness checks.

## Minimal Read-only Evaluation

From the repository root:

```powershell
python -m pip install -r requirements-dev.txt
python harness\scripts\client_context.py --client generic_cli --task unknown --query "test" --json
python harness\scripts\check_client_manifest.py --json
python harness\scripts\check_capability_manifest.py --json
python harness\maintain.py release-checkpoint --json
python harness\maintain.py release-checkpoint --strict --json
python harness\maintain.py release-gaps
python harness\maintain.py release-gaps --strict --json
python harness\maintain.py release-decisions --json
python harness\maintain.py release-decisions --strict --json
python harness\scripts\release_issue_ledger.py --json
python harness\scripts\release_issue_ledger.py --gap-table-only
python harness\scripts\release_issue_ledger.py --owner-decisions-only --json
python harness\maintain.py release-check --profile oss --json
python harness\maintain.py release-check --profile private-audit --json
```

Expected shape:

- `client_context.py` returns `kind=client_context` and `ok=true`.
- `check_client_manifest.py` reports supported clients, their status, and the
  distinction between full lifecycle integration and read-only Context Brief
  access. In the current tree, `readiness.context_cli` is `2/2` while
  `readiness.full_lifecycle_multi_client` is `1/2`.
  It also exposes `contracts.full_lifecycle_required_capabilities` and each
  client's `missing_full_lifecycle_capabilities`, so a second full lifecycle
  client requires concrete install, injection, write governance, audit,
  rollback, and health-check evidence.
- `check_capability_manifest.py` reports all harness scripts assigned to
  capabilities and all capabilities documented.
- `release-checkpoint --json` is the read-only checkpoint view for the current
  release state: external source safety, release verdict, issue ledger, gap
  table, owner decisions, owner-editable decision template, and manifest
  summaries are in one payload.
- `release-checkpoint --strict --json` returns non-zero while the checkpoint is
  blocked or warning-bearing, but still emits the same parseable JSON contract.
- `release-check` returns `verdict=ready` when there are no blocker/warning
  items in the OSS profile.
- `release-check --profile private-audit` keeps publication-only gaps as
  warnings when the owner decision is to keep the repo private; it is not a
  public release gate.
- In the current active checkout, `release-check` may intentionally return
  `verdict=blocked` while the project owner still has unresolved license and
  publish-scope decisions. See `docs/capability-map-and-oss-gap.md` for the
  current checkpoint table.
- `release-gaps --strict --json` returns non-zero for the same remaining
  blocker set, but still emits the parseable `release_gap_table` JSON payload.
- `release-gaps` / `release_issue_ledger.py --gap-table-only` are the primary
  current-gap views: owner rows include decision docs plus dry-run/write
  commands, and the `client_portability` row keeps `readiness` plus per-client
  evidence and `remediation_plan`.
- `release-decisions --json` emits the project-owner decision queue and the
  health of `harness/release_owner_decisions.json`. In that payload,
  `record_ready=true` only means the owner state file contains a valid decided
  record; `gate_ready=true` means the underlying release blocker has actually
  cleared. Use `gate_unblock_requirements` to see whether the next action is a
  required artifact, such as `LICENSE`, or a publish-scope condition, such as
  remaining tracked private paths.
- `release-decisions --strict --json` returns non-zero while owner decisions
  are not ready or their records are invalid, but still emits parseable JSON.
- `scan_orphan_scripts.py --strict --json` emits `kind=orphan_script_scan`;
  `verdict=ok` means every `harness/` Python script is represented in
  `docs/scripts-registry.md` and no removed script remains listed.

If `release-check` reports `project_metadata` as a blocker, resolve the listed
metadata item first. The project currently treats an absent `LICENSE` file as a
real external-release blocker rather than silently choosing a license. See
`docs/license-decision.md` for the decision checklist.

If `release-check` reports `publish_scope` as a blocker, the repo still tracks
personal memory, project, archive, or report paths. See `docs/publish-scope.md`
before treating this checkout as a public source distribution.

## Claude Code Runtime Install

If you want the full Claude Code hook chain:

```powershell
python bootstrap.py check
python bootstrap.py install
python bootstrap.py check
python harness\scripts\check_hook_alignment.py --strict --json
```

`bootstrap.py install` writes `~/.claude/settings.json` and creates runtime
junctions for agents, skills, and harness scripts. Use `CLAUDE_HOME` to test in
an isolated Claude home:

```powershell
$env:CLAUDE_HOME="C:\tmp\global-memory-claude-home"
python bootstrap.py install
python bootstrap.py check
```

## Generic CLI Context Brief

Clients that do not support Claude Code hooks can still request context:

```powershell
python harness\scripts\client_context.py --client generic_cli --task unknown --query "your task" --json
```

This is read-only by default. Add `--log` only if you want retrieve telemetry
written to the configured Claude logs directory.

## Product Boundaries

Read these before treating the project as an external dependency:

- `docs/capability-map-and-oss-gap.md` gives the current checkpoint and
  separates owner decisions from code remediation and docs/release-scope
  governance.
- `docs/capabilities.md` explains all 18 capability domains.
- `docs/publish-scope.md` explains which tracked paths are not part of the
  default external source scope.
- `harness/client_manifest.json` states which clients are stable,
  experimental, planned, or deprecated, and whether that stability covers full
  lifecycle governance or only Context Brief retrieval.
- `harness/capability_manifest.json` is the machine-readable capability source
  of truth.
- `harness/hook_manifest.json` is the machine-readable hook source of truth.

Default external MVP path:

1. Generic CLI Context Brief.
2. Claude Code hook runtime.
3. Read-only release readiness profile.
4. Optional diagnostics.

Not default MVP:

- Local GUI control panel.
- Personal memory repository maintenance.
- Task lifecycle workflow.
- Retrieve tuning experiments.
- Legacy route/audit utilities.

## Before Changing The System

Run:

```powershell
python -m pip install -r requirements-dev.txt
python harness\scripts\scan_orphan_scripts.py --strict --json
python harness\scripts\check_capability_manifest.py --json
python harness\generate_catalog.py --check --json
python harness\scripts\check_hook_alignment.py --strict --json
python harness\verify\verify_output_contracts.py --json
python harness\maintain.py release-check --profile oss --json
python harness\maintain.py release-check --profile private-audit --json
```

If you add a script, update `docs/scripts-registry.md` and assign the script to
a capability in `harness/capability_manifest.json`. If the script is a
maintainer, GUI, or AI-discoverable command, also update
`harness/maintenance_manifest.json`. If you add a capability, document it in
`docs/capabilities.md` with a `capability:<id>` marker. If you add or rename a
script, agent, or skill, run `python harness\generate_catalog.py`; release-check
blocks stale generated catalogs via `catalog_freshness`.
