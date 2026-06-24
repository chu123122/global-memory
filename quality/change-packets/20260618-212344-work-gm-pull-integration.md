---
packet_id: 20260618-212344-work-gm-pull-integration
author: codex-lead
created: 2026-06-18T21:23:44
risk_tier: 2
status: submitted
---

# Change Packet: work gm pull integration

## Motivation (WHY)

- `gm.search` and `gm.rule` currently exist as experimental MCP affordances, but the work skill still describes a manual flow that does not say when they should be used, logged, or ignored.
- User decision on 2026-06-18: keep `gm_rule` as a forced-gate backend, but do not keep betting on it as a default optional natural MCP tool.
- Without a narrow integration, future `/work` runs will either forget the tools, overuse `gm.search` instead of grep, or keep exposing `gm.rule` as noisy optional affordance rather than deterministic rule evidence.

## Scope (WHAT)

Files to modify:
- `harness/gm_mcp/server.py`
- `harness/gm_mcp/README.md`
- `harness/tests/test_gm_mcp_server.py`
- `skills/work/v1/SKILL.md`
- `rules/接入索引.md`
- `docs/scripts-registry.md`
- `docs/capabilities.md`
- `D:/ClaudeTasks/active/global-memory-pull-architecture/*` task docs, as needed for design/verification state

Files NOT touched:
- Existing retrieve injection hook chain (`harness/hooks/retrieve_inject.py`, `harness/scripts/harness_retrieve.py`)
- Bootstrap/runtime settings and user MCP configuration
- `harness/gm_mcp/search.py` ranking/deliver-gate thresholds
- Unrelated issue file `issues/ISSUE-2026-06-18-check-doc-sync-global-noise.md`

New files to create:
- `harness/tests/test_gm_mcp_server.py`

## Approach (HOW)

- Keep integration deterministic and minimal: reuse `harness.gm_mcp.server` as the single backend/CLI surface instead of adding a new hook or orphan script.
- Add direct CLI probes for work-flow use (`--search` / `--rule` with explicit `source`) so `/work` can record evidence without relying on natural MCP tool selection.
- Hide `gm.rule` from the default stdio MCP tool list unless explicitly opted in by env; retain `gm_rule()` and `--rule` as the forced-gate backend.
- Update `work` skill instructions to call `gm.search` only at cross-project/cross-session/paraphrase recall points and `gm.rule` at rule-sensitive action points; repo-local file lookup remains grep/read.

## Evidence & Verification

- Pre-implementation: existing task evidence shows `gm.search` cross-project recall is useful, while `gm.rule` has no natural samples and overlaps injected rules; `rules/接入索引.md §0.1` already defines pull vs gate channel separation.
- Post-implementation:
  - `python -m pytest harness/tests/test_gm_mcp_server.py harness/tests/test_gm_mcp_logging.py harness/tests/test_gm_mcp_rules.py harness/tests/test_gm_mcp_search.py`
  - `python -m harness.gm_mcp.server --rule "审查只报告不改代码" --source work_step3_rule`
  - `python -m harness.gm_mcp.server --search "UE RAG 模板怎么处理去噪" --source work_step0_search`
  - `python harness/scripts/quality_gate.py verify --path harness/gm_mcp --path harness/tests/test_gm_mcp_server.py --path skills/work/v1/SKILL.md --path docs/scripts-registry.md --path docs/capabilities.md --json`

## Risks & Rollback

- Risk: hiding `gm.rule` by default may surprise manual MCP users. Mitigation: keep opt-in env and direct CLI/backend API; document the behavior.
- Risk: `/work` instructions over-trigger semantic search. Mitigation: explicitly say not to use it for repo-local lookup or injected rules.
- Rollback: revert the server CLI/default-exposure change and the work/doc edits; no data migration or hook/runtime settings are changed.

## Intent Alignment

- Parent task: global-memory-pull-architecture
- Does this serve the task's stated goal? Yes. It moves from optional pull affordance toward an explicit work-flow contract: `gm.search` supplies candidate memory pointers where grep cannot, while `gm.rule` becomes deterministic rule evidence for gates.
