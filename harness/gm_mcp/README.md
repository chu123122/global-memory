# gm_mcp — pull-mode global-memory MCP tools

Phase A MVP exposes pull-mode backends in parallel with the existing automatic injection path:

- `gm.search(query, top=5, intent_top=3, source=None)` — fuzzy recall for old cross-project/cross-session memory and paraphrased prior conclusions. It is not an internal navigation tool.
- `gm.locate(query, kind=None, max_reads=3, source=None)` — returns the smallest authoritative global-memory entry files to read for an internal question.
- `gm.symbol(name, kind=None, module=None, source=None)` — Python AST symbol lookup returning exact `path:start_line-end_line` locations and signatures.
- `gm.inspect(type, name=None, id=None, source=None)` — object detail lookup for skill/script/rule/capability/task/module/doc entries.
- `gm.map(source=None)` — top-level module map and authoritative entrypoints.
- `gm.answer(query, top=3, source=None)` — direct anchored rule answer; abstains instead of using RAG when no rule source exists.
- `gm.rule(query, top=3, source=None)` — in-memory lookup over `rules.yaml`, returning anchored rule snippets with `rule_id`, `verdict`, and `source_path`. It is kept as a forced-gate/backend probe by default, not as a default optional MCP affordance.

## Install dependency

```powershell
python -m pip install mcp
```

Backend self-test does not require the MCP SDK, but running the stdio MCP server does.

## Run

```powershell
python -m harness.gm_mcp.server
```

Transport: stdio. Claude Code MCP configuration is intentionally not modified by this package; the lead/operator registers it. By default the stdio server exposes `gm.search`, `gm.locate`, `gm.symbol`, `gm.inspect`, `gm.map`, and `gm.answer`; `gm.rule` remains available as a backend/CLI probe and can be exposed as an opt-in MCP tool with `GM_MCP_EXPOSE_RULE_TOOL=1`.

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

## Direct workflow probes

Workflows and gates should call the backend directly with explicit source labels instead of relying on natural MCP tool selection:

```powershell
python -m harness.gm_mcp.server --rule "审查只报告不改代码" --source work_step3_rule
python -m harness.gm_mcp.server --search "UE RAG 模板怎么处理去噪" --source work_step0_search
python -m harness.gm_mcp.server --answer "审查模式能不能改代码" --source work_step3_rule
python -m harness.gm_mcp.server --locate "work 继续任务要读什么" --source work_step0_locate
python -m harness.gm_mcp.server --symbol gm_search_tool --source work_step3_symbol
python -m harness.gm_mcp.server --inspect skill --id work --source work_step1_inspect
python -m harness.gm_mcp.server --map --source self_test
```

Use `gm.search` only for cross-project/cross-session/paraphrased memory recall. Use `gm.rule` as anchored rule evidence for gates/review/implementation decisions.

## Self-test

```powershell
$env:GM_MCP_CALL_SOURCE = "self_test"
python -m harness.gm_mcp.server --self-test
python -m harness.gm_mcp.server --bench --repeat 20
```
