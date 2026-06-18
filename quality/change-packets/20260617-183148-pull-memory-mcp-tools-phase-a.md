---
packet_id: 20260617-183148-pull-memory-mcp-tools-phase-a
author: Codex worker b3egw1exug37enty0du8jpje
created: 2026-06-17T18:31:48
risk_tier: 2
status: draft
---

# Change Packet: pull memory mcp tools phase a

## Motivation (WHY)

- Phase A needs a local pull-mode MCP surface so Claude Code can explicitly call global-memory search/rule tools instead of relying only on automatic context injection.
- Without this MVP, the task cannot measure the key risk: whether the AI naturally invokes memory tools when they are visible as tools.

## Scope (WHAT)

Files to modify:
- `harness/gm_mcp/**`
- `harness/tests/test_gm_mcp_*.py`
- `harness/capability_manifest.json`
- `docs/scripts-registry.md`
- `docs/capabilities.md`
- `CHANGELOG.md`
- `D:/ClaudeTasks/active/global-memory-pull-architecture/test/测试.md`
- `D:/ClaudeTasks/active/global-memory-pull-architecture/ops/CHANGELOG.md`

Files NOT touched:
- `harness/scripts/harness_retrieve.py`
- `harness/hooks/**`
- `harness/scripts/client_context.py`
- Claude Code MCP global settings/config files

New files to create:
- `harness/gm_mcp/rules.yaml`
- `harness/gm_mcp/rules.py`
- `harness/gm_mcp/search.py`
- `harness/gm_mcp/server.py`
- `harness/gm_mcp/README.md`
- `harness/tests/test_gm_mcp_logging.py`
- `harness/tests/test_gm_mcp_rules.py`
- `harness/tests/test_gm_mcp_search.py`

## Approach (HOW)

- Implement an official Python MCP SDK `FastMCP` stdio server as a thin wrapper only; the lead will handle Claude Code registration.
- `gm.search` directly imports existing `harness.semantic` modules and uses `AcceptanceConfig.default_open()` with `debug=True` so vector-only results are visible and low confidence is only annotated, never hard-filtered.
- `gm.rule` loads a small hand-curated in-repo rule registry into memory at process startup and returns only anchored source snippets/verdicts that are directly supported by rule text.
- Every tool call appends one JSONL record with `source`, `mode`, `latency_ms`, status/error, result refs/ids, confidence, and summary. Test/self-test calls set explicit non-natural source values.

## Evidence & Verification

- Pre-implementation: design/Phase card and lead approvals specify MCP tools, logging schema, prohibited files, and capability registration requirements.
- Post-implementation commands:
  - `python -m pytest harness/tests/test_gm_mcp_logging.py harness/tests/test_gm_mcp_rules.py harness/tests/test_gm_mcp_search.py -q`
  - `python -m harness.gm_mcp.server --self-test`
  - `python harness/scripts/scan_orphan_scripts.py --strict --json`
  - `python harness/scripts/check_capability_manifest.py --json`
  - `git diff --name-only -- harness/scripts/harness_retrieve.py harness/hooks harness/scripts/client_context.py`
  - `python harness/scripts/quality_gate.py verify --path harness/gm_mcp --path harness/tests/test_gm_mcp_logging.py --path harness/tests/test_gm_mcp_rules.py --path harness/tests/test_gm_mcp_search.py --json`

## Risks & Rollback

- Risk: MCP SDK may be absent locally. Mitigation: backend self-test avoids requiring SDK import; MCP run fails loudly with install guidance.
- Risk: semantic index/Ollama may be unavailable. Mitigation: search returns explicit backend errors in tests/self-test rather than silently succeeding.
- Rollback: remove `harness/gm_mcp/**`, related tests, and the `pull_memory_tools` registry/capability/doc entries; forbidden automatic-injection files remain untouched.

## Intent Alignment

- Parent task: global-memory-pull-architecture
- Does this serve the task's stated goal? Yes. It creates the minimal pull-mode MCP tools and tool-call evidence needed to test whether AI will naturally invoke global-memory tools.
