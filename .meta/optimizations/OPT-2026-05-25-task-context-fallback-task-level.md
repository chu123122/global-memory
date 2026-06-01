---
optimization_id: OPT-2026-05-25-task-context-fallback-task-level
status: applied
applied_at: 2026-05-25
scope: task-scoped
default_enable: false
---

# Optimization: Task-Level Task-Context Fallback

## Decision

Enable task-context fallback only for `android-cook-shadermap-dangling` through the task-local config:

`D:/ClaudeTasks/active/android-cook-shadermap-dangling/core/CONFIG.json`

Do not enable fallback globally.

## Evidence

- Source proposal: `~/.claude/global-memory/.meta/proposals/OP-2026-05-25-human-query-zero-hit.md`
- Simulation: `~/.claude/global-memory/.meta/evaluations/EV-2026-05-25-task-context-simulation.json`
- Relevance review: `~/.claude/global-memory/.meta/evaluations/EV-2026-05-25-task-context-relevance-review.json`
- Trial pack: `~/.claude/global-memory/.meta/trials/TR-2026-05-25-task-context-android-cook.json`

## Why This Is Safe Enough For Task Scope

- The accepted task has direct HANDOFF references to Android cook ShaderMap work.
- Fallback only triggers when literal-query retrieve has no scored pointer.
- Runtime enablement is task-local, not global.
- `xdap-plugin-mount-missing` remains rejected and is not configured.

## Rollback

Set `retrieve.task_context_fallback.enabled` to `false` in:

`D:/ClaudeTasks/active/android-cook-shadermap-dangling/core/CONFIG.json`

or remove the file.
