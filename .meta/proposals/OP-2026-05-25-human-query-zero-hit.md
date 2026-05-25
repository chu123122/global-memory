---
proposal_id: OP-2026-05-25-human-query-zero-hit
status: proposed
created: 2026-05-25
target: retrieve
auto_apply: false
depends_on: EV-2026-05-25-retrieve-downrank-human-visible
---

# Proposal: Reduce Human Query Zero-Hit

## Decision

Do not apply a behavior change yet.

The next optimization target should be human-query zero-hit, not more downrank tuning.

## User-Visible Problem

The previous downrank experiment changed some noisy top pointers, but the user-visible evaluation showed the larger problem:

- 10 recent human queries compared
- 2 changed
- 8 unchanged
- 8 had no memory pointer in both default and opt-in modes

From the user's perspective, this means the system often feels like it has no memory at all during natural task follow-ups.

## Evidence

Read-only analysis command:

```powershell
python D:/global-memory/harness/scripts/retrieve_zero_hit_analysis.py --format json
```

Observed result:

- human_calls: 209
- human_zero_hit: 118
- human_zero_hit_rate: 56.5%
- short_followup_zero_hit: 88
- short_followup_zero_hit_rate: 74.6%
- task_specific_zero_hit: 30

Top zero-hit tasks:

- `harness-governance-followup`: 26
- `android-cook-shadermap-dangling`: 25
- `aik-refactor-ui-provider`: 19
- `harness-context-governance`: 18
- `xd-adaptive-performance-refactor`: 18

Visible failure samples:

- `目前情况？`
- `e2e测试呢？`
- `为啥没加载？`
- `这个删除在EngineTeamOPT上没有？这是我回来后新添加上去导致的问题？`

## Hypothesis

Most human zero-hit cases are not standalone search queries. They are task-local follow-ups whose meaning depends on the current task, recent handoff, or task title.

The retrieve system appears to score the literal user message too narrowly, so short follow-ups do not inherit enough task context to retrieve useful memory.

## Proposed Direction

First safe change should still be diagnostic/simulation-first:

1. Build a read-only simulation that compares literal-query retrieve against task-context-expanded retrieve.
2. Expansion candidates should be limited to low-risk context:
   - task name
   - task display name
   - current task HANDOFF first paragraph
   - current task STATUS progress line
3. Evaluate on recent human zero-hit samples.
4. Only consider runtime behavior if before/after samples visibly improve without pointer spam.

## Primary Metric

- human_zero_hit_rate

Expected direction: decrease, especially for short follow-up queries.

## External Acceptance

The optimization can only advance if a before/after sample pack shows:

- at least 10 recent human zero-hit queries
- default result vs expanded-query result
- user-readable explanation of why new pointers are relevant
- no broad feedback-spam regression

If the before/after output is not visibly better, reject the change.

## Guardrails

- Do not lower `MIN_SCORE_DEFAULT` globally.
- Do not increase `MAX_POINTERS` globally.
- Do not re-enable noisy generic feedback files just to reduce zero-hit.
- Do not inject long task docs into every retrieve call.
- Do not default-enable any fallback before a human-visible evaluation artifact exists.

## Rollback

If a future runtime fallback is enabled and feels worse:

1. Disable the fallback flag/config.
2. Keep this proposal and evaluation as evidence.
3. Mark this proposal `reverted` with the specific query samples that regressed.

## Current Status

Task-context simulation has been implemented as read-only:

```powershell
python D:/global-memory/harness/scripts/retrieve_task_context_simulation.py --samples 10 --format json
```

Evaluation artifacts:

```text
D:/global-memory/.meta/evaluations/EV-2026-05-25-task-context-simulation.json
D:/global-memory/.meta/evaluations/EV-2026-05-25-task-context-simulation.md
```

Observed summary:

- compared: 10
- new_hits: 10
- changed: 10
- still_empty: 0
- verdict: `STRONG_VISIBLE_DELTA`

Decision remains conservative:

- Do not default-enable fallback.
- Human review is required because some new pointers may be generic or weakly related.
- If accepted, the next runtime implementation should be opt-in or task-scoped first.

## Opt-In Runtime Fallback Implemented

Runtime behavior remains unchanged by default.

Implemented explicit opt-in support in `D:/global-memory/harness/scripts/harness_retrieve.py`:

```powershell
python D:/global-memory/harness/scripts/harness_retrieve.py `
  --task android-cook-shadermap-dangling `
  --query "目前情况？" `
  --task-context-fallback-config D:/global-memory/.meta/experiments/retrieve_task_context_fallback_review.json `
  --json
```

Experiment config:

```text
D:/global-memory/.meta/experiments/retrieve_task_context_fallback_review.json
```

Observed before/after:

- Default for `目前情况？`: `[]`
- Opt-in fallback:
  - `fixes/fix_cook_av_dangling_shadermap.md`
  - `fixes/fix_uat_silent_cook_failure.md`

Validation:

- `python -m pytest D:/global-memory/harness/tests/context_governance/unit/test_retrieve.py -q` -> 15 passed
- `python -m py_compile D:/global-memory/harness/scripts/harness_retrieve.py`
- `maintain.py report` external verdict advanced to `TASK_CONTEXT_OPT_IN_READY`

Safety constraints:

- Do not set `HARNESS_RETRIEVE_TASK_CONTEXT_FALLBACK_CONFIG` globally.
- Do not enable by default.
- Keep runtime fallback single-run or task-scoped until changed samples are reviewed.

## Relevance Review Completed

Created relevance review artifacts:

```text
D:/global-memory/.meta/evaluations/EV-2026-05-25-task-context-relevance-review.json
D:/global-memory/.meta/evaluations/EV-2026-05-25-task-context-relevance-review.md
```

Review result:

- reviewed_tasks: 2
- accepted_tasks: 1
- rejected_tasks: 1
- decision: `task_scoped_opt_in_only`

Accepted:

- `android-cook-shadermap-dangling`
- reason: new pointers are exact cook/shadermap fixes referenced by the task HANDOFF.

Rejected for now:

- `xdap-plugin-mount-missing`
- reason: new pointers reduce empty output but risk pulling the agent toward shader/cook symptoms instead of the actual uproject/UHT conflict.

Runtime config was narrowed:

```json
["android-cook-shadermap-dangling"]
```

Current report verdict: `TASK_CONTEXT_TASK_SCOPED_READY`.
