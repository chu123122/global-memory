---
packet_id: 20260618-212346-global-memory-collab-plugin-skeleton
author: codex-lead
created: 2026-06-18T21:23:46
risk_tier: 2
status: submitted
---

# Change Packet: global-memory collab plugin skeleton

## Motivation (WHY)

- XDMaker 的 Orca 协同能力已经具备 lead/worker prompt、MCP bridge、worker model/effort 配置、分屏 UI 和 workflow 状态，但这些实现深绑 XDMaker Electron host。
- 用户目标是把协同能力拆成可加入 global-memory 的独立插件/能力包，并能融入 Codex、Claude Code 等客户端使用。
- 如果不先落一个 host-neutral core + config schema + adapter contract，后续会把 XDMaker 主体、Electron localDb、路由和 UI 外壳一起复制进 global-memory，偏离插件化目标。

## Scope (WHAT)

Files to modify:
- `harness/capability_manifest.json`
- `docs/capabilities.md`
- `docs/scripts-registry.md`
- `quality/verification.md` or task-level `D:/ClaudeTasks/active/xd-maker-agent-collab-standalone/test/测试.md`

Files NOT touched:
- `agents/CLAUDE.md` (no global behavior semantic change in this patch)
- `harness/client_manifest.json` (do not claim Codex full lifecycle or set `multi_client_ready=true` in the first patch)
- `harness/hooks/**` (no automatic hook behavior in the first patch)
- `D:/xdt-maker-main/**` (source reference only, never modified)

New files to create:
- `skills/collab/v1/SKILL.md`
- `harness/collab/__init__.py`
- `harness/collab/config.py`
- `harness/collab/plan.py`
- `harness/collab/adapters.py`
- `harness/scripts/collab_plan.py`
- `harness/tests/test_collab_config.py`
- `harness/tests/test_collab_plan.py`

## Approach (HOW)

- Build a small host-neutral collaboration core first: deterministic Python schema validation and dispatch-plan generation. This keeps routing/retry/config transforms in code, and leaves actual worker spawning to the active client runtime tools.
- Package the user-facing workflow as `skills/collab/v1/SKILL.md`, so Claude Code and Codex can both receive the same procedure and call their available delegation tools (Orca, Codex subagents, Claude Code Task) when present.
- Add adapter contracts as data, not runtime process launchers. The first patch must not spawn Codex/Claude Code processes directly or bypass client permission/governance.
- Register the new script/capability as experimental. This advances the plugin goal without overclaiming global-memory as full lifecycle multi-client ready.

## Evidence & Verification

- Pre-implementation: `D:/ClaudeTasks/active/xd-maker-agent-collab-standalone/design/Phase2-插件化边界设计.md` documents copy/adapter/replace/exclude boundaries from XDMaker evidence.
- Pre-implementation: XDMaker evidence paths include `D:/xdt-maker-main/packages/orca-workflow/src/orca-bridge-mcp.ts`, `D:/xdt-maker-main/packages/orca-workflow/src/orca-bridge-prompt.ts`, `D:/xdt-maker-main/packages/lizi-mcps/src/collab/server.ts`, and Electron UI/state files.
- Post-implementation: `pytest harness/tests/test_collab_config.py harness/tests/test_collab_plan.py`
- Post-implementation: `python harness/scripts/collab_plan.py --json`
- Post-implementation: `python harness/scripts/check_capability_manifest.py --json`
- Post-implementation: `python harness/scripts/quality_gate.py verify --path skills/collab/v1/SKILL.md --path harness/collab --path harness/scripts/collab_plan.py --path harness/tests/test_collab_config.py --path harness/tests/test_collab_plan.py --path harness/capability_manifest.json --path docs/capabilities.md --path docs/scripts-registry.md --json`

## Risks & Rollback

- Risk: The patch overclaims multi-client readiness. Mitigation: mark capability experimental and do not edit `harness/client_manifest.json` readiness flags in the first patch.
- Risk: The script becomes an orphan. Mitigation: register `harness/scripts/collab_plan.py` in `docs/scripts-registry.md` and `harness/capability_manifest.json`.
- Risk: Adapter contract duplicates XDMaker assumptions. Mitigation: tests assert host-neutral dispatch payloads and no Electron/localDb dependency.
- Rollback: delete `skills/collab`, `harness/collab`, `harness/scripts/collab_plan.py`, related tests, and remove the capability/docs registry entries. No persistent user data or hooks are modified in this patch.

## Intent Alignment

- Parent task: `xd-maker-agent-collab-standalone`
- Yes. This is the first code-bearing slice toward making XDMaker-style collaboration an independent global-memory plugin/ability package that can be used from Codex and Claude Code without depending on the XDMaker Electron host.
- This patch intentionally preserves the broader final scope: UI shell and true client-runtime spawning remain later phases, while the first slice establishes the shared schema, dispatch contract, and governance registration needed for safe implementation.
