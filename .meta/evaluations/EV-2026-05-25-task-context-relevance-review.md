---
evaluation_id: EV-2026-05-25-task-context-relevance-review
target: task-context-fallback-review
created: 2026-05-25
mode: human-visible-relevance-review
default_enable: false
decision: task_scoped_opt_in_only
---

# Evaluation: Task Context Relevance Review

## Decision

Keep task-context fallback opt-in only.

Narrow the runtime config to `android-cook-shadermap-dangling` only. Do not include `xdap-plugin-mount-missing` yet.

## Accepted

Task: `android-cook-shadermap-dangling`

Sample follow-ups:

- `目前进度`
- `目前？`
- `e2e测试呢？`
- `目前情况？`

New pointers:

- `fixes/fix_cook_av_dangling_shadermap.md`
- `fixes/fix_uat_silent_cook_failure.md`

Why accepted:

- The task HANDOFF directly names Android cook ShaderMap work and points to `fix_cook_av_dangling_shadermap.md` as the complete W6 context.
- `fix_cook_av_dangling_shadermap.md` documents the exact cook AV, ShaderMap Content null, W6 fix, and e2e validation.
- `fix_uat_silent_cook_failure.md` documents UAT swallowing cook failures and links back to the same cook AV memory.

This is a good example of the external improvement the user can feel: short follow-ups that previously returned no memory now return task-specific fixes.

## Rejected For Now

Task: `xdap-plugin-mount-missing`

Sample follow-ups:

- `为啥没加载？`
- `这个删除在EngineTeamOPT上没有？这是我回来后新添加上去导致的问题？`
- `但是为什么被这个commit给删掉了，是其他模块隐性调用问题，还是只是分支拉取那个版本的同步情况而已？`

New pointers:

- `feedback_compile_after_module_change.md`
- `fixes_shader_code_library_missing.md`

Why rejected:

- The task HANDOFF says the root cause is `XDAdaptivePerformance` disabled in `UE_game.uproject` plus duplicate USTRUCT conflict when enabling it.
- `feedback_compile_after_module_change.md` is a generic compile cadence preference.
- `fixes_shader_code_library_missing.md` is only indirectly related through Android package symptoms and may distract from the uproject/UHT conflict.

This is exactly the risk we wanted to catch: the fallback reduces empty output but can introduce plausible-looking weak pointers.

## Runtime Config Update

Update:

```text
D:/global-memory/.meta/experiments/retrieve_task_context_fallback_review.json
```

Allowed tasks should be:

```json
["android-cook-shadermap-dangling"]
```

Still do not set `HARNESS_RETRIEVE_TASK_CONTEXT_FALLBACK_CONFIG` globally.

