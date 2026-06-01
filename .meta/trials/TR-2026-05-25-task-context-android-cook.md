---
trial_id: TR-2026-05-25-task-context-android-cook
created: 2026-05-25
mode: read-only-task-context-trial-pack
task: android-cook-shadermap-dangling
default_enable: false
---

# Trial: Task-Context Fallback For Android Cook

## Decision

Keep task-context fallback as task-scoped opt-in only.

This trial is visibly useful for `android-cook-shadermap-dangling`, but it still does not justify global/default enablement.

## Command

```powershell
python ~/.claude/global-memory/harness/scripts/retrieve_task_context_trial_pack.py --task android-cook-shadermap-dangling --samples 5 --zero-hit-only --format json
```

## Result

- verdict: `VISIBLE_TASK_SCOPED_TRIAL`
- compared: 5
- new_hits: 5
- changed: 5
- still_empty: 0
- default_enable_ready: false

## What The User Can Feel

Before opt-in, these task follow-ups had no memory pointer:

- `ok，手机不在周围，可以全程自动吗`
- `e2e测试呢？`
- `目前情况？`

With task-scoped opt-in, all sampled follow-ups return:

- `fixes/fix_cook_av_dangling_shadermap.md`
- `fixes/fix_uat_silent_cook_failure.md`

This is the desired external effect: a natural short follow-up no longer feels like the system has no memory.

## Guardrail

Do not generalize from this one task. `xdap-plugin-mount-missing` was rejected in relevance review because it produced plausible but weak pointers.

