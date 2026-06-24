Verdict: PASS

Blocking:
- none

Warnings:
- The work-skill action-point text is verified by inspection and task evidence rather than an executable parser; this is acceptable because the behavior change is a workflow contract plus direct CLI/backend tests, not a hook runtime change.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Red-Evidence:
- `test_stdio_server_hides_gm_rule_tool_by_default` would fail on the previous implementation because `run_stdio_server()` unconditionally registered `gm.rule`.
- `test_stdio_server_can_opt_in_to_gm_rule_tool` would fail if the compatibility path did not honor `GM_MCP_EXPOSE_RULE_TOOL=1`.
- `test_direct_rule_cli_uses_backend_and_source` and `test_direct_search_cli_uses_backend_and_source` would fail before the new direct `--rule` / `--search` CLI probes existed.
- `test_direct_cli_rejects_rule_and_search_together` proves the direct probe mode has an unambiguous command contract.

Mutation:
- Removing the env guard around MCP `gm.rule` registration is killed by `test_stdio_server_hides_gm_rule_tool_by_default`.
- Ignoring the `--source` CLI argument is killed by the direct rule/search CLI tests, which assert the exact source passed to the backend.
- Allowing `--rule` and `--search` simultaneously is killed by `test_direct_cli_rejects_rule_and_search_together`.
- Changing the direct search defaults for `top`, `intent_top`, or `max_delivered_unique_paths` is covered by the direct search CLI test's captured backend call.
