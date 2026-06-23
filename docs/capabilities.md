---
doc_type: guide
status: active
last_updated: 2026-05-26
trigger:
  keywords: [concept:capabilities, concept:open-source-readiness, tool:harness]
  tags: [workflow, tooling]
---

# Capabilities

This page is the human-readable companion to `harness/capability_manifest.json`.
The manifest is the machine source of truth; this document explains what each
capability is for, who should use it, and whether it belongs to the external
MVP.

Current product boundary: this project is a Claude Code harness plus global
memory governance system. It is not yet a generic multi-client memory platform.
`client_context.py` provides a stable generic CLI Context Brief contract, but
full lifecycle governance is stable only for Claude Code.

Quick checks:

```powershell
python harness\scripts\check_capability_manifest.py --json
python harness\maintain.py release-check --profile oss --json
```

## External MVP Path

Use these capabilities first when judging the project as an installable,
documented, externally testable system:

| Capability | Status | Release | External value |
|---|---|---:|---|
| `core_memory_retrieval` | core | yes | Retrieve a compact, auditable Context Brief. |
| `runtime_hook_governance` | core | yes | Reproduce and verify the Claude Code hook chain. |
| `client_portability` | core | yes | State exactly which clients are stable. |
| `release_readiness` | core | yes | Run one read-only OSS-readiness verdict. |
| `maintenance_control_plane` | core | yes | Operate the system from one CLI surface. |
| `shared_runtime_libraries` | core | yes | Keep root/path/hook helpers centralized. |

Optional diagnostics can support the MVP, but should not be required for first
install success. Experimental and legacy capabilities must not be treated as
default product promises.

## Capability Details

### Long-term Memory Retrieval And Injection

`capability:core_memory_retrieval`

Status: core. Release scope: yes.

External story: a client can opt into auditable, low-noise memory context
injection.

Boundary: retrieve scoped memory pointers and inject a compact Context Brief.
The stable non-hook contract is:

```powershell
python harness\scripts\client_context.py --client generic_cli --task unknown --query "your question" --json
```

Primary scripts: `scripts/harness_retrieve.py`, `scripts/client_context.py`,
`hooks/retrieve_inject.py`, `scripts/harness_memory_lint.py`.

### Runtime Hook Governance

`capability:runtime_hook_governance`

Status: core. Release scope: yes.

External story: a fresh install can reproduce the expected Claude Code hook
chain and detect drift.

Boundary: hook registration, ordering, runtime drift checks, and
fail-open/fail-block behavior. `harness/hook_manifest.json` is the source of
truth.

Primary check:

```powershell
python harness\scripts\check_hook_alignment.py --strict --json
```

### Client Support Boundary

`capability:client_portability`

Status: core. Release scope: yes.

External story: users can see whether this is a Claude Code harness, a stable
Context Brief CLI contract, or a generic multi-client memory system.

Boundary: `claude_code` is the only full-lifecycle stable client. `generic_cli`
is stable for read-only Context Brief retrieval only. Codex CLI is experimental
until it has its own installation and injection path.

Machine-readable distinction:

- `multi_client_ready=false`: full lifecycle multi-client integration is not
  established.
- `context_cli_ready=true`: the generic CLI Context Brief contract is stable.
- `readiness.full_lifecycle_multi_client`: stable clients `1/2`.
- `readiness.context_cli`: stable clients `2/2`.
- `clients[]`: per-client `status`, `integration`, `support_level`, and entry
  count, checked against the summary by `verify_output_contracts.py`. The
  release-check and release ledger contracts also require `readiness` and
  `clients[]` to survive aggregation.
- `contracts.full_lifecycle_required_capabilities`: the machine-readable
  checklist for promoting another client to full lifecycle support:
  install/bootstrap, automatic context injection, write governance, audit
  logging, rollback/disable, and release health checks.
- `clients[].missing_full_lifecycle_capabilities`: the concrete gap list for
  each client. Today `claude_code` has none, `codex_cli` is still missing
  install/bootstrap, automatic injection, write governance, audit logging, and
  rollback/disable, and `generic_cli` is intentionally context-brief only.
- `remediation_plan`: the required machine-readable next step for the current
  warning, with `keep_narrow_claim` and `add_second_full_lifecycle_client` as
  explicit options.
- `claim_policy.checked`: external entrypoint docs checked for the narrow
  product boundary.
- `claim_policy.forbidden_checked`: external entrypoint docs checked for
  forbidden overclaims, so README/getting-started/capabilities cannot silently
  claim generic full-lifecycle multi-client readiness.

Primary check:

```powershell
python harness\scripts\check_client_manifest.py --json
```

### Open-source Readiness Profile

`capability:release_readiness`

Status: core. Release scope: yes.

External story: a maintainer can run one read-only command to see current
blockers before externalizing the project.

Boundary: release-check aggregates registry coverage, capability coverage,
maintenance manifest coverage, generated catalog freshness, client scope,
external docs entrypoints, CI workflow coverage, hook alignment, bootstrap,
publish-scope, source-export plan, path config, hardcoded paths,
external-source safety, output contracts, gate checks, and smoke tests.
`release_issue_ledger.py` derives an issue ledger from that current
release-check result.
Registry coverage is the `scan_orphan_scripts.py --strict --json` check: it
only answers whether every `harness/` Python script is present in
`docs/scripts-registry.md` and whether the registry still names removed scripts.
It does not decide external product scope; `check_capability_manifest.py`
separately verifies that every script belongs to a capability domain.

Primary check:

```powershell
python harness\maintain.py release-check --profile oss --json
python harness\maintain.py release-checkpoint --json
python harness\maintain.py release-checkpoint --strict --json
python harness\maintain.py release-gaps
python harness\maintain.py release-gaps --strict --json
python harness\maintain.py release-decisions --json
python harness\maintain.py release-decisions --strict --json
python harness\maintain.py release-decisions --template --json
python harness\maintain.py release-record-decision --dry-run --decision license_policy --selected-option <option> --decided-by <owner> --decided-at YYYY-MM-DD --json
python harness\scripts\release_issue_ledger.py --json
python harness\scripts\release_issue_ledger.py --gap-table-only
python harness\scripts\release_issue_ledger.py --owner-decisions-only --json
```

`maintain.py release-checkpoint --json` is the current checkpoint shortcut when
you need one payload for external source safety, release verdict, issue ledger,
gap table, owner decisions, owner-editable decision template, and manifest
summaries. It is read-only and keeps the full release gate separate: use
`release-check --profile oss --json` as the authoritative gate when deciding
whether the OSS profile passes.
Use `maintain.py release-checkpoint --strict --json` when automation should fail
on the current blocked/warning checkpoint while still receiving the same
parseable `release_checkpoint` payload.

The derived ledger keeps every check as `open`, `resolved`, or `deferred`, and
adds a `gap` classification so remaining work is separated into owner decisions,
code remediation, and publish-scope/document governance.
It also exposes `remaining_gap_table` as the current machine-readable gap table,
grouped into `owner_decisions`, `code_remediation`,
`docs_publish_scope_governance`, and `deferred`, so reports do not have to
reconstruct the release state from free-form text. Owner-decision rows include
the decision id, current recorded status, selected option, required artifacts,
required conditions, decision document, and command evidence needed to move from
"owner selected" to "gate actually resolved".
The gap-table summary keeps bucket counts for ownership routing and also exposes
`open_by_gap_type`, so a publish-scope blocker that is owner-governed is still
visible as `publish_scope_governance` instead of being hidden inside the owner
queue count.
Use `release_issue_ledger.py --gap-table-only` when the user or a follow-up
agent only needs the categorized remaining work instead of the full evidence
ledger. Use `maintain.py release-gaps` as the primary control-plane shortcut for
that same table.
Non-owner rows keep compact evidence when that evidence is needed to understand
the remaining gap; for example, the `client_portability` row carries
`evidence.readiness`, `evidence.clients[]`, and `evidence.remediation_plan`
directly in the gap table.
It also carries `client_lifecycle_gaps`, so the gap-table view directly shows
the full-lifecycle required capabilities and each client's missing
full-lifecycle items without requiring a separate full ledger lookup.
Owner-decision rows can also carry operational evidence when the owner needs it
to choose a path; for example, `publish_scope` carries
`publish_scope_breakdown` with private tracked path groups and reasons, so the
owner can see whether the blocker is mostly personal knowledge, project/task
context, feedback memory, or self-loop evidence.
Use `maintain.py release-gaps --strict --json` when automation should fail on
the current remaining blocker set while still receiving the same parseable
`release_gap_table` payload.
It also exposes `owner_decisions` as the top-level queue for unresolved
project-owner choices, including the decision id, owner, decision document, and
machine-readable options.
Use `maintain.py release-decisions --json` as the primary control-plane shortcut
when only that owner queue is needed.
Owner decision templates, gap rows, and dry-run/write reports expose
`record_gate_effect.effect=records_owner_choice_only` and
`record_gate_effect.clears_release_blocker=false`, so automation cannot confuse
a valid owner record with a resolved release gate.
In the owner queue, `ready` is kept for compatibility and mirrors `gate_ready`;
`record_ready` separately reports whether the owner state file already has a
valid `decided` record.
The same owner surfaces expose `gate_unblock_requirements`, a normalized list of
remaining gate conditions such as `required_artifacts` or
`required_conditions`, so agents do not have to infer the unblock work from
free-form `next_action` text.
Use `maintain.py release-decisions --template --json` to get the current
owner-editable patch skeleton. Use `maintain.py release-record-decision
--dry-run ...` to validate a selected option before writing; replace `--dry-run`
with `--write` only after the project owner has intentionally chosen that
license or publication boundary.

`check_prepare.py --json` is the deterministic `/check` input contract: it
resolves the target task, enumerates review docs, scans placeholders/empty
headings/long docs, emits review warnings, and produces the prompt inputs used
by the read-only review pass.
Use `maintain.py release-decisions --strict --json` when automation should fail
until those owner decisions are ready and their records are valid/current while
still receiving the same parseable owner queue payload.
The owner-editable record is `harness/release_owner_decisions.json`; updating
that file records the choice but does not by itself make release gates pass.
The ledger validates recorded decisions against current option ids and exposes
`record_valid` / `record_findings` in both full and owner-only output.
Every open owner decision must have a matching record in that file; missing
records are reported as `record_present=false` and fail the output contract.
Records with no matching open owner decision are reported in
`decision_state_findings` and also fail the output contract.
`summary.owner_decision_records` aggregates valid, invalid, missing, stale, and
per-status counts so reports can show record health without scanning every item.
For the full ledger and gap-table views, `release_issue_ledger.py --strict`
and the primary shortcut `maintain.py release-gaps --strict --json` return
non-zero for either open release blockers or invalid/missing/stale owner
decision records. For the owner-only view, `release_issue_ledger.py
--owner-decisions-only --strict --json` and `maintain.py release-decisions
--strict --json` return non-zero only when the owner queue is not ready or its
records are invalid/missing/stale.
`verify_output_contracts.py` enforces that `gate_check.py` keeps G1-G9,
summary, failures, verdict, and G9 WARN labeling internally consistent; that
`check_hook_alignment.py` emits a stable hook alignment contract with
manifest/bootstrap/runtime/registry counts and drift verdict; that
`scan_dual_storage.py --json` emits a stable `dual_storage_scan` contract while
the default text output remains available for G1; that
`scan_orphan_scripts.py` emits a stable `orphan_script_scan` JSON contract; that
capability/client manifest checks keep internally consistent boundary counts;
that `check_publish_scope.py` keeps tracked/external/private/unclassified
counts, grouped private/unclassified summaries, scope lists, verdict, and
`decision_plan.required_when` internally consistent;
that `export_source_scope.py` keeps source-export counts, untracked grouping,
tracking command, tracking safety, and verdict internally consistent;
that `scan_external_safety.py` keeps its summary, verdict, `by_code`,
`top_paths`, `remediation_groups`, visible findings, skipped rows, and
public-history policy plan internally consistent;
that `smoke_test.py` keeps summary counts aligned with per-script result rows,
status values, skip explanations, and zero-failure release semantics;
that `client_context.py` keeps the generic client `context-brief.v1` payload
shape stable across `ok/error`, `brief`, `brief_text`, pointer rows, and
just-in-time load strategy;
that `generate_catalog.py --check --json` keeps generated component catalog
freshness machine-readable across targets, summary counts, findings, and
verdict;
that `audit_skill.py --all --json` keeps skill summary counts aligned with
per-skill levels, issue rows, issue-code groups, and deployed-extra warnings;
that `analyze_retrieve_log.py --json` keeps retrieve log totals, zero-hit
rates, hit distribution, top path rows, noisy keyword candidates, namespace
distribution, and miss-query samples internally consistent;
that `work_context_pack.py --json` keeps the read-only `work_context` task
summary shape stable and does not need STATUS.md writes;
that `check_prepare.py --json` keeps unresolved-task, missing-task, and
resolved review-prep payloads stable across candidates, review docs, doc scans,
warnings, level semantics, and prompt inputs;
that `harness_status.py --tasks --json` keeps task lifecycle summary counts
aligned with active/archived task rows, stage groups, and missing/unknown active
task counts;
that `self_loop_report.py --json` keeps self-loop overview, optimization
ledger, fallback cost, fallback candidates, and assurance payloads
machine-readable;
that `meta_optimize.py --json` keeps the read-only optimization finding ledger,
user-visible decision, severity counts, and priority rows internally
consistent;
that release-check still carries the external docs entrypoint check, that at
least six entrypoint docs are covered, and that `docs/` entrypoint docs keep
frontmatter with `status` and `last_updated`,
that the maintenance manifest check is present and reports zero findings for
command groups, script paths, required commands, and JSON entrypoints,
that the generated catalog freshness check covers the three automatic component
README files and reports zero stale/missing catalogs,
that the OSS workflow is parseable YAML with readiness steps and exposes the
catalog freshness, output-contract, release-checkpoint, gap-table, owner-queue, and final
release-check commands, and
that owner-governed blockers expose `decision_plan` values for `license_policy`
and `publish_scope_boundary`, and that `client_portability` keeps its
`readiness`, per-client evidence, and remediation plan through release-check
aggregation. It also enforces that release ledger issues keep `gap` metadata,
that `client_portability` ledger issues keep `readiness`, `clients[]`, and
`remediation_plan`, that open owner-governed issues appear in `owner_decisions`,
that `remaining_gap_table` matches the issue list and carries owner follow-up
requirements, that the gap-table `open_by_gap_type` summary matches row
`gap_type` values, that owner decision records are valid, and that the open
issue gap summaries match the issue list.

### Maintenance Control Plane

`capability:maintenance_control_plane`

Status: core. Release scope: yes.

External story: humans, GUI, and AI clients have one discoverable CLI surface
for maintenance.

Boundary: read-only status, doctor, release-check, release-checkpoint, release-gaps,
release-decisions, safe-fix, sync preview, and report commands; explicit owner
state writes go through `release-record-decision`. `maintain.py` is the
preferred entrypoint.

### Shared Runtime Libraries

`capability:shared_runtime_libraries`

Status: core. Release scope: yes.

External story: maintainers can update runtime helper behavior in one place
instead of each hook or script carrying private path and parsing logic.

Boundary: centralized path config, hook helpers, prompt loading, task resolver,
and stage helpers. New release-facing path defaults should go through
`harness/config.py`.

### Documentation And Prompt Integrity

`capability:documentation_prompt_integrity`

Status: optional. Release scope: yes.

External story: users can trust that documented hook, skill, agent, and
maintenance surfaces match the checkout.

Boundary: README/docs/prompt-system consistency checks and catalog generation.
This supports release readiness but is not the runtime memory engine.
`audit_skill.py --all --json` emits a skill quality ledger with summary counts
by skill level, issue level, issue code, and deployed-extra skills.

### Memory Repository Maintenance

`capability:memory_repository_maintenance`

Status: optional. Release scope: no.

External story: useful for this personal memory repository; not required for
the external Context Brief MVP.

Boundary: memory file extraction, changelog archive, stats, garbage collection,
notes, and trigger metadata migration.

### Deployment And Sync Utilities

`capability:deployment_and_sync`

Status: optional. Release scope: no.

External story: a local maintainer can keep the personal runtime wired and
synchronized.

Boundary: hook deployment, background sync, baseline comparison, task/session
sync helpers, and diff display. These are local workflow utilities, not a
generic install contract.

### Project Context Tools

`capability:project_context_tools`

Status: optional. Release scope: no.

External story: external adopters can ignore this unless they adopt the same
project-doc workflow.

Boundary: creates, closes, and summarizes local project/task context documents.

### Health Diagnostics

`capability:health_diagnostics`

Status: optional. Release scope: yes.

External story: maintainers can inspect why a system is unhealthy without
making personal-memory signals mandatory for OSS readiness.

Boundary: deeper repository, retrieval, lint, sync, and WIP diagnostics. These
checks explain problems; they are not all default blockers.

### Self-loop Evidence Pipeline

`capability:self_loop_evidence`

Status: optional. Release scope: yes.

External story: the project can explain optimization decisions without enabling
automatic behavior changes by default.

Boundary: proposal, evaluation, trial, candidate, optimization ledger, and
self-loop overview reporting. This is evidence and governance, not autonomous
runtime mutation.
`self_loop_report.py --json` and `meta_optimize.py --json` are stable read-only
machine contracts and are checked by `verify_output_contracts.py`.

### Pull-mode Memory MCP Tools

`capability:pull_memory_tools`

Status: experimental. Release scope: no.

External story: local operator experiment for pull-mode memory recall,
structured internal navigation, Python symbol lookup, and anchored rule
backends. It lets Claude Code call `gm.search` for fuzzy memory pointers,
`gm.locate` for minimal internal entrypoints, `gm.symbol` for exact Python
symbol locations, `gm.inspect` / `gm.map` for catalog navigation, and
`gm.answer` for anchored rule answers. It is not a default external runtime
promise.

Boundary: stdio MCP server and direct backend probes; it runs alongside the
existing automatic Context Brief injection and does not replace it. `gm.search`
is fuzzy recall for old cross-project/cross-session memory; structured internal
navigation goes through `gm.locate`, `gm.symbol`, `gm.inspect`, and `gm.map`.
`gm.answer` gives anchored rule verdicts and abstains without a rule source.
`gm.rule` is kept as a forced-gate backend by default rather than a default
optional MCP tool.

Primary local commands:

```powershell
python -m harness.gm_mcp.server --self-test
python -m harness.gm_mcp.server
python -m harness.gm_mcp.server --rule "审查只报告不改代码" --source work_step3_rule
python -m harness.gm_mcp.server --search "UE RAG 模板怎么处理去噪" --source work_step0_search
python -m harness.gm_mcp.server --locate "work 继续任务要读什么" --source self_test
python -m harness.gm_mcp.server --symbol gm_search_tool --source self_test
```

### Retrieve Experiments And Trial Packs

`capability:retrieve_experiments`

Status: experimental. Release scope: no.

External story: local tuning and evidence gathering for retrieve behavior.

Boundary: downrank simulations, task-context fallback trials, fallback cost,
candidate quality, trace, and zero-hit analysis. These scripts should remain
opt-in until promoted.

### Task Lifecycle Tooling

`capability:task_lifecycle`

Status: optional. Release scope: no.

External story: useful for this personal workflow; not required for the memory
retrieval MVP.

Boundary: archive tasks, synchronize phase status, and check completion
readiness.
`harness_status.py --tasks --json` is the read-only task lifecycle overview; it
emits `kind=harness_tasks`, summary counts, active/archived task rows, stage
groups, and explicit missing/unknown active counts.

### Local GUI Control Panel

`capability:control_panel`

Status: optional. Release scope: no.

External story: diagnostics UI for this machine; external users can operate the
CLI without it.

Boundary: local PySide control panel and reporting views over the maintenance
CLI.

### Markdown Rendering Utilities

`capability:markdown_rendering`

Status: optional. Release scope: no.

External story: report rendering is useful for this local workflow but not
required for the core memory retrieval contract.

Boundary: markdown-to-HTML rendering and classification helpers.

### Legacy Routing And AI Runner Utilities

`capability:legacy_routing_and_ai_runner`

Status: legacy. Release scope: no.

External story: maintainers can inspect or retire these scripts explicitly;
external users should not treat them as the primary routing interface.

Boundary: older route gate/audit and AI runner scripts retained for visibility
while current hooks and route-system-v2 replace the default path.

### Legacy Deep Content Checks

`capability:legacy_deep_checks`

Status: legacy. Release scope: no.

External story: run explicitly for repository cleanup; do not treat as external
install readiness.

Boundary: personal memory index, conventions, and deep content hygiene checks.

## Promotion Rules

To promote an experimental or optional capability into the external MVP:

1. Give it a stable external story in `harness/capability_manifest.json`.
2. Add or update the `capability:<id>` section on this page.
3. Ensure every referenced script is registered in `docs/scripts-registry.md`.
4. Add a machine-readable check or explain why an existing release check covers
   it.
5. Run `python harness\maintain.py release-check --profile oss --json`.
