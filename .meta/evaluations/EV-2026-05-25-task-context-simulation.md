---
evaluation_id: EV-2026-05-25-task-context-simulation
target: human-query-zero-hit
created: 2026-05-25
mode: read-only-task-context-simulation
default_enable: reject_for_now
---

# Evaluation: Task Context Simulation

## Decision

Do not default-enable task-context fallback yet.

The simulation is promising because it removes the empty first screen for sampled zero-hit follow-ups, but the new pointers still need relevance review.

## Command

```powershell
python D:/global-memory/harness/scripts/retrieve_task_context_simulation.py --samples 10 --format json
```

## Summary

- verdict: `STRONG_VISIBLE_DELTA`
- compared: 10
- new_hits: 10
- changed: 10
- still_empty: 0
- default_enable_ready: false

## What The User Can Feel

Before simulation, these natural follow-ups had no memory pointers:

- `目前情况？`
- `e2e测试呢？`
- `为啥没加载？`

With task context expansion, they show concrete memory pointers instead of an empty first screen.

Example that looks useful:

- task: `android-cook-shadermap-dangling`
- query: `目前情况？`
- literal: `[]`
- expanded:
  - `fixes/fix_cook_av_dangling_shadermap.md`
  - `fixes/fix_uat_silent_cook_failure.md`

Example needing review:

- task: `xdap-plugin-mount-missing`
- query: `为啥没加载？`
- literal: `[]`
- expanded:
  - `feedback/feedback_compile_after_module_change.md`
  - `fixes/fixes_shader_code_library_missing.md`

The second example proves why this still cannot be default-enabled: it reduces empty output, but may introduce generic or weakly related pointers.

## Next Gate

Human review must decide whether the new pointers are actually better for the sampled tasks. If accepted, the next implementation should still be opt-in or task-scoped first.

