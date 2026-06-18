# gm_mcp — pull-mode global-memory MCP tools

Phase A MVP exposes two local MCP tools in parallel with the existing automatic injection path:

- `gm.search(query, top=5, intent_top=3, source=None)` — wraps `harness.semantic` Q2doc retrieval plus curated `intent_bank.json` Q2Q matches. It runs with open acceptance/debug output and marks `low_confidence`; it does not hard-filter low-confidence results.
- `gm.rule(query, top=3, source=None)` — in-memory lookup over `rules.yaml`, returning anchored rule snippets with `rule_id`, `verdict`, and `source_path`.

## Install dependency

```powershell
python -m pip install mcp
```

Backend self-test does not require the MCP SDK, but running the stdio MCP server does.

## Run

```powershell
python -m harness.gm_mcp.server
```

Transport: stdio. Claude Code MCP configuration is intentionally not modified by this package; the lead/operator registers it.

Example registration shape for the operator:

```json
{
  "mcpServers": {
    "global-memory": {
      "command": "python",
      "args": ["-m", "harness.gm_mcp.server"],
      "cwd": "D:/global-memory"
    }
  }
}
```

## Warm model strategy

`gm.search` uses the existing loopback bge-m3/Ollama embedding service from `harness.semantic`; the MCP process never spawns a per-call Python child or reloads a model. Server startup calls `warmup()` once, which sends a tiny embedding request and caches intent-bank paraphrase embeddings in-process.

Expected warm latency target:

- `gm.rule`: single-digit ms p50/p95 on warm process; pure in-memory match after startup anchor validation.
- `gm.search`: tens of ms when the local bge-m3 endpoint is warm; SQLite retrieval and Q2Q scoring are small, embedding is the main cost.

## Logs

Each call appends one JSONL line. Default path:

```text
~/.claude/logs/gm_mcp_tool_calls.jsonl
```

Override for tests:

```powershell
$env:GM_MCP_LOG_PATH = "D:/tmp/gm_mcp_test.jsonl"
$env:GM_MCP_CALL_SOURCE = "self_test"
```

Important fields include `source` (`natural` by default; tests should set `test` or `self_test`), `mode`, `latency_ms`, `tool`, `query`, `hit`, `count`, `top_refs`, `top_ids`, `confidence`, `low_confidence`, `returned_summary`, `status`, `error`, `session_id`, and `task_id`.

## Self-test

```powershell
$env:GM_MCP_CALL_SOURCE = "self_test"
python -m harness.gm_mcp.server --self-test
python -m harness.gm_mcp.server --bench --repeat 20
```
