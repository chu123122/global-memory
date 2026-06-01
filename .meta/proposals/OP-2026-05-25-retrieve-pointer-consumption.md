---
proposal_id: OP-2026-05-25-retrieve-pointer-consumption
status: proposed
created: 2026-05-25
target: retrieve
auto_apply: false
---

# Proposal: Improve Retrieve Pointer Consumption

## Decision

Do not auto-apply. This proposal is ready for review only.

## User-Visible Problem

`maintain.py report` now surfaces a clear first-screen decision:

- Verdict: `READY_FOR_PROPOSAL`
- Current top issue: retrieve pointer consumption is low
- Current first action: create a read-only proposal, not an automatic fix

The user-visible problem is not merely that an internal metric is bad. It is that memory appears to exist, but retrieved pointers are rarely consumed, so the user cannot reliably feel that memory is helping the agent make decisions.

## Evidence

From `~/.claude/logs/health_checks.jsonl` latest health signal:

- Near 7 days retrieve: 249 calls with hits
- Call consumption rate: 1.2%
- Pointer consumption rate: 0.6%
- Frequently recalled but unread pointers:
  - `feedback_ai_summary_drift.md` recalled 97 times, 0 read
  - `feedback_code_style.md` recalled 72 times, 0 read
  - `feedback_compile_after_module_change.md` recalled 62 times, 0 read
  - `fixes_shader_code_library_missing.md` recalled 48 times, 0 read
  - `feedback_diff_workflow.md` recalled 20 times, 0 read

From `meta_optimize.py` direct analysis:

- Retrieve zero-hit rate: 33.5% across 376 retrieve calls in 7 days
- High zero-hit tasks include:
  - `harness-governance-followup`
  - `android-cook-shadermap-dangling`
  - `aik-refactor-ui-provider`
  - `harness-context-governance`
  - `xd-adaptive-performance-refactor`

## Hypothesis

The retrieve system is likely over-returning generic behavioral feedback pointers and under-serving task-specific context. This creates two visible failure modes:

1. The agent gets memory pointers that it does not actually read.
2. The report repeatedly says memory/retrieve is problematic, but does not yet tell the user which safe change should be tried.

This is still a hypothesis, not proof. Do not edit retrieve ranking or frontmatter until this proposal is reviewed.

## Proposed Change

First safe change should be diagnostic, not behavioral:

1. Add a `retrieve_candidate_quality` report that groups recalled-but-unread pointers by namespace and file family.
2. Mark generic feedback files as `candidate_downrank`, not immediately changing runtime ranking.
3. Generate a before/after simulation report showing which top pointers would change if generic feedback files were downranked.
4. Only after simulation, decide whether to adjust runtime ranking or frontmatter.

## Primary Metric

- `pointer_consumption_rate`

Expected direction: increase after a reviewed ranking/frontmatter change.

## Guardrail Metrics

- `retrieve_zero_hit_rate` must not get worse by more than 5 percentage points.
- `user_visible_report_clarity` must remain high: report first screen keeps one recommendation and at most 3 candidates.
- `handoff_ready` for active work task must remain PASS.

## Rollback

If runtime ranking is later changed and results regress:

1. Revert the ranking/frontmatter change.
2. Keep this proposal and evaluation artifact as evidence.
3. Mark proposal status as `reverted` with the metric delta.

## Verification Plan

Before any apply:

```powershell
python ~/.claude/global-memory/harness/maintain.py report --json | ConvertFrom-Json
python ~/.claude/global-memory/harness/maintain.py report --markdown
python ~/.claude/global-memory/harness/scripts/assurance_gate.py --gate task-handoff-ready --task harness-meta-optimize-assurance
```

After a future simulation script exists:

```powershell
python ~/.claude/global-memory/harness/scripts/retrieve_candidate_quality.py --days 7 --format json
```

## Apply Status

Not applied. The next implementation should create a read-only candidate-quality or simulation report before any retrieve behavior changes.

## Candidate Quality Report Implemented

Implemented read-only script:

```powershell
python ~/.claude/global-memory/harness/scripts/retrieve_candidate_quality.py --format json
python ~/.claude/global-memory/harness/scripts/retrieve_candidate_quality.py --format markdown
```

Current sample output:

- retrieve_calls: 376
- unique_pointers: 57
- candidate_downrank_count: 11
- top_candidate_family: feedback
- family quality:
  - feedback: recalled 326, consumed 0, consumption_rate 0.0
  - fixes: recalled 72, consumed 1, consumption_rate 0.0139
  - docs: recalled 43, consumed 2, consumption_rate 0.0465
  - decisions: recalled 32, consumed 0, consumption_rate 0.0
  - knowledge: recalled 23, consumed 0, consumption_rate 0.0

This strengthens the hypothesis that generic feedback pointers dominate recall but are not consumed. Still no runtime behavior has been changed.

## Downrank Simulation Implemented

Implemented read-only script:

```powershell
python ~/.claude/global-memory/harness/scripts/retrieve_downrank_simulation.py --format json
python ~/.claude/global-memory/harness/scripts/retrieve_downrank_simulation.py --penalty-factor 0.5 --format markdown
```

Simulation results:

| penalty | evaluated_queries | top1_changed | top2_changed | zero_hit_delta | guardrail |
|---:|---:|---:|---:|---:|---|
| 0.2 | 376 | 204 | 216 | +41 | WARN |
| 0.5 | 376 | 136 | 152 | 0 | PASS |
| 0.8 | 376 | 124 | 136 | 0 | PASS |

Interpretation:

- Candidate downrank direction is plausible: feedback family would drop substantially in top2.
- Strong penalty `0.2` is unsafe because it increases zero-hit by 41 queries.
- Mild penalty `0.5` passes the zero-hit guardrail in simulation and changes 152/376 top2 results.
- Still do not apply. The next step is human review or a smaller scoped reversible experiment.

Current `maintain.py report` external verdict has advanced to `READY_FOR_REVIEW`.

## Opt-In Experiment Implemented

Runtime retrieve behavior is still unchanged by default.

Implemented opt-in support in `~/.claude/global-memory/harness/scripts/harness_retrieve.py`:

```powershell
python ~/.claude/global-memory/harness/scripts/harness_retrieve.py `
  --task puerts-ai-prototype `
  --query "ue 编辑器扩展怎么写" `
  --downrank-config ~/.claude/global-memory/.meta/experiments/retrieve_downrank_0_5.json `
  --json
```

Experiment config:

```text
~/.claude/global-memory/.meta/experiments/retrieve_downrank_0_5.json
```

Observed single-query before/after:

- Default top2:
  - `feedback_code_style.md`
  - `feedback_compile_after_module_change.md`
- Opt-in top2:
  - `feedback_learning_path.md`
  - `knowledge_lua_patterns.md`

Validation:

- `python -m py_compile ~/.claude/global-memory/harness/scripts/harness_retrieve.py`
- `python -m pytest ~/.claude/global-memory/harness/tests/context_governance/unit/test_retrieve.py -q` -> 12 passed
- `maintain.py report` external verdict advanced to `READY_FOR_OPT_IN_EXPERIMENT`

Safety constraints:

- Do not set `HARNESS_RETRIEVE_DOWNRANK_CONFIG` globally yet.
- Do not enable by default.
- Use only explicit `--downrank-config` for single-run or small task-level experiments.

## Side-by-Side Trial Helper Implemented

Implemented read-only helper:

```powershell
python ~/.claude/global-memory/harness/scripts/retrieve_optin_compare.py `
  --task puerts-ai-prototype `
  --query "ue 编辑器扩展怎么写" `
  --format markdown
```

Single-query observed result:

- Default top2:
  - `feedback_code_style.md`
  - `feedback_compile_after_module_change.md`
- Opt-in top2:
  - `feedback_learning_path.md`
  - `knowledge_lua_patterns.md`

Recent-query batch check:

```powershell
python ~/.claude/global-memory/harness/scripts/retrieve_optin_compare.py --recent 5 --format json
```

Result:

- compared: 5
- changed: 2
- unchanged: 3

This gives the user a direct external view of the optimization effect without enabling it globally.

## Human-Visible Evaluation

Created evaluation artifacts:

```text
~/.claude/global-memory/.meta/evaluations/EV-2026-05-25-retrieve-downrank-human-visible.json
~/.claude/global-memory/.meta/evaluations/EV-2026-05-25-retrieve-downrank-human-visible.md
```

Human-only recent-query result:

- compared: 10
- changed: 2
- unchanged: 8
- both default and opt-in empty: 8
- external verdict: `LIMITED_BY_ZERO_HIT`

Decision:

- Do not default-enable downrank.
- Keep explicit opt-in available for single-run or task-scoped trials.
- Next optimization should target human-query zero-hit, because most sampled real user queries still show no memory pointer before or after downrank.

This is the first hard example of the external-evidence rule: internal `top2_changed` can prove that ranking moves, but it does not prove that the user can feel the system is smarter.
