# Verification Summary - work gm pull/gate integration

Scope: integrate `gm.search` and `gm.rule` into the `work` skill flow with explicit workflow probes and channel boundaries. This change does **not** modify the retrieve injection hook chain, bootstrap, runtime settings, or user MCP configuration.

## Deterministic Checks

- `python harness\scripts\change_packet.py validate quality\change-packets\20260618-212344-work-gm-pull-integration.md --json` -> PASS.
- `python -m pytest harness\tests\test_gm_mcp_server.py harness\tests\test_gm_mcp_logging.py harness\tests\test_gm_mcp_rules.py harness\tests\test_gm_mcp_search.py -q` -> PASS, 27 tests.
- `python -m harness.gm_mcp.server --self-test` -> PASS; rules and search warmup OK.
- `python -m harness.gm_mcp.server --rule "审查只报告不改代码" --source work_step3_rule` -> PASS; direct `gm.rule` backend returns `R18_REVIEW_READONLY` with anchored sources.
- `python -m harness.gm_mcp.server --search "记忆应该存在哪里" --source work_step0_search --top 5 --intent-top 3` -> PASS; direct `gm.search` backend returns delivered pointers after deliver-gate.
- `python harness\scripts\render_codex_work_skill.py --check` -> PASS; generated Codex work skill is up to date.
- `python harness\scripts\scan_orphan_scripts.py --strict --json` -> PASS; no unregistered scripts.
- `python harness\scripts\check_capability_manifest.py --json` -> PASS; all harness scripts assigned.
- `git diff --name-only -- harness/hooks/retrieve_inject.py harness/scripts/harness_retrieve.py bootstrap.py harness/hook_manifest.json` -> empty.

## Test Evidence

- `harness/tests/test_gm_mcp_server.py` covers direct CLI probes and default/opt-in MCP exposure policy for `gm.rule`.
- Existing gm_mcp tests still cover logging source behavior, rule registry anchors/verdicts, search deliver-gate, abstain behavior, and Q2Q demotion.
- Task-level evidence is recorded in `D:/ClaudeTasks/active/global-memory-pull-architecture/test/work_gm_integration.md`.

## Human decision

human decision: user explicitly decided that `gm_rule` should be kept as a forced-gate backend and should not remain a default optional MCP tool used to claim natural adoption. The implementation follows that by keeping direct backend/CLI access and hiding the MCP `gm.rule` affordance by default, with `GM_MCP_EXPOSE_RULE_TOOL=1` as opt-in compatibility.

## Rollback / Recovery

- Rollback: revert `harness/gm_mcp/server.py`, `harness/gm_mcp/README.md`, `harness/tests/test_gm_mcp_server.py`, `skills/work/v1/SKILL.md`, `rules/接入索引.md`, `docs/scripts-registry.md`, `docs/capabilities.md`, and the task Phase3 docs.
- Recovery: if direct probes fail, run `python -m harness.gm_mcp.server --self-test` first, then use `gm.rule` injected rule text / required `/work` docs as fallback; do not change hooks/settings to recover.
- The retrieve hook chain and bootstrap/settings are untouched, so rollback does not require runtime redeployment beyond regenerating the Codex work skill if `skills/work/v1/SKILL.md` changes.

---

# Verification Summary - collab plugin skeleton

Scope: first code-bearing slice for `xd-maker-agent-collab-standalone`: `skills/collab/v1`, `harness/collab`, `harness/scripts/collab_plan.py`, collab tests, capability/docs registry, and generated catalogs. This change does **not** modify hooks, bootstrap behavior, `harness/client_manifest.json`, or XDMaker source.

## Deterministic Checks

- `python harness\scripts\change_packet.py validate quality\change-packets\20260618-212346-global-memory-collab-plugin-skeleton.md --json` -> PASS.
- Initial Red: `python -m pytest harness\tests\test_collab_config.py harness\tests\test_collab_plan.py -q` -> FAIL with `ModuleNotFoundError: No module named 'collab'` before implementation.
- Mid-loop Red: `test_plan_payload_is_host_neutral` failed when adapter metadata still mentioned `Electron`; fixed by removing host-specific wording.
- `python -m pytest harness\tests\test_collab_config.py harness\tests\test_collab_plan.py -q` -> PASS, 10 tests.
- `python harness\scripts\collab_plan.py --intent "CLI smoke" --json` -> PASS; parsed output was `global-memory-collab 5 find`.
- `python harness\scripts\check_capability_manifest.py --json` -> PASS; `ERROR=0`, `unassigned_scripts=0`, `actual_scripts=161`.
- `python harness\scripts\scan_orphan_scripts.py --strict --json` -> PASS; `unregistered=0`, `stale_in_registry=0`.
- `python harness\generate_catalog.py --check --json` -> PASS; all 3 generated catalogs fresh.
- `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-plugin-skeleton --path ... --json` -> PASS; auto tier=3, `files=20`, `changed_lines=1059`, `missing=[]`.

## Test Evidence

- `harness/tests/test_collab_config.py` covers required five-agent config, defaults, JSON loading, invalid reasoning rejection, and missing-agent rejection.
- `harness/tests/test_collab_plan.py` covers stable dispatch order, required prompt sections, host-neutral payload constraints, adapter process-spawn contract, Markdown render uniqueness, and CLI JSON smoke.

## Human decision

human decision: user/lead explicitly preauthorized continuing the formal `/work` task and landing this Change Packet without stopping at a second implementation confirmation gate.

## Rollback / Recovery

Rollback: delete `skills/collab`, `harness/collab`, `harness/scripts/collab_plan.py`, `harness/tests/test_collab_config.py`, `harness/tests/test_collab_plan.py`, and remove the `collaboration_orchestration` capability/docs/registry/catalog entries plus this verification/review evidence. No persistent user data, hooks, bootstrap links, or client lifecycle flags are modified.

Recovery: if `collab_plan.py` fails, run `python harness\scripts\collab_plan.py --validate --json` first to isolate config errors, then rerun the two collab pytest files; do not change hooks/settings to recover this feature.

---

# Verification Summary - collab adapter payload and state skeleton

Scope: second collab migration slice for `xd-maker-agent-collab-standalone`: declarative adapter payloads, stable plan IDs, optional JSON state artifacts, extra tests, and updated capability/docs registry. This change still does **not** launch worker clients, change hooks/bootstrap, edit `harness/client_manifest.json`, or touch XDMaker source.

## Deterministic Checks

- `python harness\scripts\change_packet.py validate quality\change-packets\20260619-214615-collab-adapter-payload-and-state-skeleto.md --json` -> PASS.
- `python -m pytest harness\tests\test_collab_config.py harness\tests\test_collab_plan.py harness\tests\test_collab_adapters.py harness\tests\test_collab_state.py -q` -> PASS, 19 tests.
- `python harness\scripts\collab_plan.py --intent "adapter smoke" --adapter-payloads --state-out <tmp-file> --json` -> PASS; output contained 5 adapter payloads, first tool `spawn_agent`, and state JSON had 5 pending dispatches.
- `python harness\scripts\check_capability_manifest.py --json` -> PASS; `ERROR=0`, `unassigned_scripts=0`, `actual_scripts=162`.
- `python harness\scripts\scan_orphan_scripts.py --strict --json` -> PASS; `unregistered=0`, `stale_in_registry=0`.
- `python harness\generate_catalog.py --check --json` -> PASS; all 3 generated catalogs fresh.
- `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-adapter-state --path ... --json` -> PASS; auto tier=3, `files=20`, `changed_lines=1620`, `missing=[]`.

## Test Evidence

- `harness/tests/test_collab_adapters.py` covers Codex, Orca, manual fallback, non-spawning payloads, and host-neutral payload text.
- `harness/tests/test_collab_state.py` covers pending state creation from a plan, immutable dispatch updates, invalid status/ID rejection, and JSON roundtrip.
- Existing collab config/plan tests now also cover stable `plan_id` generation.

## Human decision

human decision: user set an active lead-only goal with a 400k token budget to progressively improve the XDMaker collaboration migration effect. This slice follows that direction while preserving the earlier boundary that runtime spawning/UI shell remain later phases.

## Rollback / Recovery

Rollback: revert `harness/collab/adapters.py`, `harness/collab/plan.py`, `harness/scripts/collab_plan.py`, docs/manifest updates, remove `harness/collab/state.py`, `harness/tests/test_collab_adapters.py`, `harness/tests/test_collab_state.py`, this Change Packet, and `quality/reviews/collab-adapter-state/`.

Recovery: if adapter payload output fails, rerun `python harness\scripts\collab_plan.py --validate --json` first, then rerun the four collab pytest files. If `--state-out` fails, use plan JSON without state and do not change hooks/settings to recover.

---

# Verification Summary - collab state update CLI

Scope: third collab migration slice for `xd-maker-agent-collab-standalone`: deterministic state validation/update CLI, state summary helper, CLI tests, and docs/manifest registry updates. This change still does **not** call worker tools, launch clients, mutate hooks/bootstrap, edit `harness/client_manifest.json`, or touch XDMaker source.

## Deterministic Checks

- `python harness\scripts\change_packet.py validate quality\change-packets\20260619-220249-collab-state-update-cli.md --json` -> PASS.
- `python -m pytest harness\tests\test_collab_config.py harness\tests\test_collab_plan.py harness\tests\test_collab_adapters.py harness\tests\test_collab_state.py harness\tests\test_collab_state_cli.py -q` -> PASS, 23 tests.
- `python harness\scripts\collab_state.py --state <tmp> --validate --json` -> PASS; summary reported 5 pending dispatches.
- `python harness\scripts\collab_state.py --state <tmp> --dispatch-id 01-find --status running --worker-id worker-1 --json` -> PASS; state JSON updated `01-find` to `running`.
- `python harness\scripts\check_capability_manifest.py --json` -> PASS; `ERROR=0`, `unassigned_scripts=0`, `actual_scripts=163`.
- `python harness\generate_catalog.py --check --json` -> PASS; all 3 generated catalogs fresh.
- `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-state-cli --path ... --json` -> PASS; auto tier=3, `files=21`, `changed_lines=1623`, `missing=[]`.

## Test Evidence

- `harness/tests/test_collab_state_cli.py` covers state validation summary, in-place update, `--out` copy update, and rejection of partial ambiguous updates.
- Existing state tests still cover invalid status/ID rejection and JSON roundtrip.

## Human decision

human decision: user set an active lead-only goal with a 400k token budget to progressively complete a useful XDMaker collaboration plugin migration. This slice improves usefulness by adding a deterministic manual/replay state update loop while keeping runtime spawning and UI shell deferred.

## Rollback / Recovery

Rollback: remove `harness/scripts/collab_state.py`, `harness/tests/test_collab_state_cli.py`, `quality/reviews/collab-state-cli/`, this Change Packet, and revert docs/manifest/README/skill updates plus the `summarize_state` export.

Recovery: if state updates fail, validate the state first with `python harness\scripts\collab_state.py --state <path> --validate --json`; if invalid, regenerate state via `collab_plan.py --state-out`. Do not change hooks/settings to recover this feature.

---

# Verification Summary - collab replay runbook helper

Scope: fourth collab migration slice for `xd-maker-agent-collab-standalone`: deterministic replay/runbook helper that reads plan + optional state, emits next action cards, runtime-shaped payloads, worker prompts, and `collab_state.py` update examples. This change still does **not** call worker tools, launch clients, mutate hooks/bootstrap, edit `harness/client_manifest.json`, or touch XDMaker source.

## Deterministic Checks

- `python harness\scripts\change_packet.py validate quality\change-packets\20260619-221803-collab-replay-runbook-helper.md --json` -> PASS.
- `python -m pytest harness\tests\test_collab_config.py harness\tests\test_collab_plan.py harness\tests\test_collab_adapters.py harness\tests\test_collab_state.py harness\tests\test_collab_state_cli.py harness\tests\test_collab_replay.py harness\tests\test_collab_replay_cli.py -q` -> PASS, 31 tests.
- `python harness\scripts\collab_replay.py --plan <plan.json> --state <state.json> --json` -> PASS; after marking `01-find` done, runbook emitted 4 actions and skipped 1 done dispatch.
- `python harness\scripts\check_capability_manifest.py --json` -> PASS; `ERROR=0`, `unassigned_scripts=0`, `actual_scripts=165`.
- `python harness\scripts\scan_orphan_scripts.py --strict --json` -> PASS; `unregistered=0`, `stale_in_registry=0`.
- `python harness\generate_catalog.py --check --json` -> PASS; all 3 generated catalogs fresh.
- `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-replay-runbook --path ... --json` -> PASS; auto tier=3, `files=22`, `changed_lines=1772`, `missing=[]`.

## Test Evidence

- `harness/tests/test_collab_replay.py` covers default done filtering, include-done audit mode, adapter filtering, plan/state mismatch rejection, and Markdown rendering.
- `harness/tests/test_collab_replay_cli.py` covers subprocess JSON runbook output, adapter filter behavior, and missing-plan error reporting.

## Human decision

human decision: user explicitly asked to continue beyond the first completed goal toward a more complete effect and requested an 800k goal budget target; the goal tool cannot resize a completed goal in-place, so this slice continues the same migration direction without redefining full lifecycle/UI as complete.

## Rollback / Recovery

Rollback: remove `harness/collab/replay.py`, `harness/scripts/collab_replay.py`, `harness/tests/test_collab_replay.py`, `harness/tests/test_collab_replay_cli.py`, `quality/reviews/collab-replay-runbook/`, this Change Packet, and revert docs/manifest/README/skill updates plus replay exports.

Recovery: if replay output fails, validate the plan with `collab_plan.py --validate --json` when config-based, validate state with `collab_state.py --validate --json`, then rerun replay. Do not change hooks/settings to recover this feature.

---

# Verification Summary - collab dispatch dry-run packet

Scope: fifth collab migration slice for `xd-maker-agent-collab-standalone`: deterministic dry-run dispatch packet helper that selects one replay action and renders runtime payload, worker prompt, and paired `collab_state.py` update commands. This change still does **not** execute worker tools, launch clients, mutate hooks/bootstrap, edit `harness/client_manifest.json`, or touch XDMaker source.

## Deterministic Checks

- `python harness\scripts\change_packet.py validate quality\change-packets\20260619-224031-collab-dispatch-dry-run-packet.md --json` -> PASS.
- `python -m pytest harness\tests\test_collab_config.py harness\tests\test_collab_plan.py harness\tests\test_collab_adapters.py harness\tests\test_collab_state.py harness\tests\test_collab_state_cli.py harness\tests\test_collab_replay.py harness\tests\test_collab_replay_cli.py harness\tests\test_collab_dispatch.py harness\tests\test_collab_dispatch_cli.py -q` -> PASS, 39 tests.
- `python harness\scripts\collab_dispatch.py --plan <plan.json> --state <state.json> --json` -> PASS; after marking `01-find` done, packet selected `02-designer` and kept `dry_run=true`.
- `python harness\scripts\check_capability_manifest.py --json` -> PASS; `ERROR=0`, `unassigned_scripts=0`, `actual_scripts=167`.
- `python harness\scripts\scan_orphan_scripts.py --strict --json` -> PASS; `unregistered=0`, `stale_in_registry=0`.
- `python harness\generate_catalog.py --check --json` -> PASS; all 3 generated catalogs fresh.
- `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-dispatch-dry-run --path ... --json` -> PASS; auto tier=3, `files=23`, `changed_lines=1950`, `missing=[]`.

## Test Evidence

- `harness/tests/test_collab_dispatch.py` covers first-available selection, specific dispatch selection, unavailable dispatch rejection, manual fallback, and Markdown rendering.
- `harness/tests/test_collab_dispatch_cli.py` covers subprocess JSON packet output, `--dispatch-id`, and empty adapter-filter error handling.

## Human decision

human decision: user asked to continue toward a more complete effect after the first completed goal; this slice improves lead-operated dispatch usability while preserving the no-auto-spawn boundary.

## Rollback / Recovery

Rollback: remove `harness/collab/dispatch.py`, `harness/scripts/collab_dispatch.py`, `harness/tests/test_collab_dispatch.py`, `harness/tests/test_collab_dispatch_cli.py`, `quality/reviews/collab-dispatch-dry-run/`, this Change Packet, and revert docs/manifest/README/skill updates plus dispatch exports.

Recovery: if dispatch packet output fails, run `collab_replay.py --plan <plan> --state <state> --json` first to check available actions, then rerun `collab_dispatch.py`. Do not change hooks/settings to recover this feature.
