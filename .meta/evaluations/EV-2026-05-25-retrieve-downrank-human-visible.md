---
evaluation_id: EV-2026-05-25-retrieve-downrank-human-visible
target: retrieve_downrank_0_5
created: 2026-05-25
mode: human-visible-before-after
default_enable: reject_for_now
---

# Evaluation: Retrieve Downrank Human-Visible Effect

## Decision

Do not default-enable retrieve downrank.

Keep it as explicit opt-in only. The next optimization should target human-query zero-hit, because most sampled human queries still show no memory pointer before or after downrank.

## Why

Command:

```powershell
python D:/global-memory/harness/scripts/retrieve_optin_compare.py --recent 10 --human-only --format json
```

Observed summary:

- compared: 10
- changed: 2
- unchanged: 8
- human queries: 10
- both default and opt-in empty: 8

External assessment:

- verdict: `LIMITED_BY_ZERO_HIT`
- conclusion: 2/10 human queries changed first-screen memory pointers, but 8/10 still returned no memory pointers in both modes.
- recommended decision: keep opt-in; fix zero-hit before doing more penalty tuning.

## What The User Can Feel

Visible improvements exist, but only in a small subset.

Changed example:

- query: `ue 编辑器扩展怎么写`
- default: `feedback_code_style.md`, `feedback_compile_after_module_change.md`
- opt-in: `feedback_learning_path.md`, `knowledge_lua_patterns.md`

Another changed example:

- query: `这是什么问题？意思是我现在本地跑的版本就有问题？把插件开了编译就过不了，PIE进不去？`
- default: `feedback_compile_after_module_change.md`, `feedback_learning_path.md`
- opt-in: `feedback_learning_path.md`, `knowledge_ue_internals.md`

But most sampled queries still have no visible memory effect:

- `目前情况？`
- `e2e测试呢？`
- `为啥没加载？`
- `这个删除在EngineTeamOPT上没有？这是我回来后新添加上去导致的问题？`

## Guardrail

Internal simulation was not enough to declare success. `top2_changed` proved that the algorithm can move scores, but this human-only comparison shows the user-visible improvement is not broad enough.

The optimization is not failed; it is simply not the next default behavior.

