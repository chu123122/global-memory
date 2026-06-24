Verdict: PASS

Blocking:
- none

Warnings:
- `gm.search` direct probes can still be slow when the local embedding backend is cold; the work skill limits use to explicit cross-project/history recall points and forbids hot-path hook integration.
- `gm.rule` remains available as an opt-in MCP tool via `GM_MCP_EXPOSE_RULE_TOOL=1`; this is intentional compatibility, but natural adoption must not be counted as success for the work-flow gate design.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Review notes:
- `harness/gm_mcp/server.py` keeps backend functions intact, adds direct `--rule`/`--search` probes, and defaults stdio MCP exposure to `gm.search` only; this matches the user decision that `gm_rule` is a forced-gate backend rather than a default optional affordance.
- `skills/work/v1/SKILL.md` states concrete action points and non-use boundaries: `gm.search` for cross-project/cross-session/paraphrased memory pointers, `gm.rule` for anchored rule evidence, and repo-local lookup remains grep/read.
- `rules/接入索引.md` preserves the push/pull/gate separation and adds `gm.rule` as a backend probe rather than a new every-turn push path.
