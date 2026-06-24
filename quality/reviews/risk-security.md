Verdict: PASS

Blocking:
- none

Warnings:
- Direct `gm.search` probes call the existing local embedding backend and can append to `~/.claude/logs/gm_mcp_tool_calls.jsonl`; this is intended evidence logging, but should not be confused with natural adoption.
- Hiding `gm.rule` by default changes the optional MCP affordance surface; compatibility remains via `GM_MCP_EXPOSE_RULE_TOOL=1`, and no bootstrap/settings/user config is changed.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Risk notes:
- No new network target, credential handling, destructive command, hook registration, or runtime settings mutation is introduced.
- The retrieve hot path (`retrieve_inject.py` / `harness_retrieve.py`) is untouched, so a bug in direct probes cannot break every prompt injection path.
- `gm.rule` source anchors are still validated by existing rule tests; direct CLI source labels make workflow/test calls auditable.
