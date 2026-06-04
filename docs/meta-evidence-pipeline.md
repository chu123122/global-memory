---
doc_type: reference
status: draft
last_updated: 2026-05-25
retrieve: true
retrieve_summary: ".meta evidence pipeline: proposals/evaluations/experiments/trials/candidates/optimizations form a read-only self-loop evidence chain; default behavior is not changed without explicit opt-in."
trigger:
  keywords: [concept:meta-evidence, concept:self-loop, tool:meta_optimize]
  tags: [workflow, tooling]
---

# `.meta` Evidence Pipeline

`.meta/` 是当前自循环体系的证据层。它不应该被理解成普通临时目录，也不应该默认改变运行时行为。

它的职责是把“系统哪里消耗了过多人工 steering、哪里召回无效、哪里完成信号弱”转成可审查证据，再决定是否做小范围、可回滚的 opt-in 优化。

## 原则

| 原则 | 含义 |
|---|---|
| 默认只读 | proposal / simulation / evaluation / trial 可以自动生成，但不能自动启用默认行为 |
| 证据先行 | 任何优化必须引用日志、评估产物、候选样本或任务交接证据 |
| 小范围启用 | 新行为优先 task-scoped opt-in，不做全局默认开启 |
| 可回滚 | `optimizations.jsonl` 必须写 rollback |
| 可审计 | 每个阶段都保留 JSON 或 Markdown 产物，避免只剩口头结论 |

## 目录含义

| 目录 | 内容 | 生产者 | 消费者 |
|---|---|---|---|
| `.meta/proposals/` | 优化提案，说明问题、假设、风险和验证窗口 | `meta_optimize.py`, 人工整理 | 人工评审、simulation 脚本 |
| `.meta/evaluations/` | 只读模拟和相关性评审结果（历史证据保留；产出脚本 P1 退役） | 人工整理 | `meta_optimize.py`, `self_loop_report.py` |
| `.meta/experiments/` | 显式 opt-in runtime config | 人工创建或候选工具生成 | `harness_retrieve.py`, trial/compare 脚本 |
| `.meta/trials/` | 小范围试用包，记录默认行为与 opt-in 行为对比（历史证据保留；产出脚本 P1 退役） | 人工整理 | 人工评审、`self_loop_report.py` |
| `.meta/candidates/` | fallback 候选任务和 ACCEPT/REVIEW/REJECT 证据 | `retrieve_fallback_candidates.py` | 人工决策、future admission gate |
| `.meta/optimizations/` | 已应用优化的 ledger 和决策说明 | 人工 apply 后记录 | `self_loop_report.py`, `maintain.py report` |

## 当前链路

```text
health/retrieve logs
  -> meta_optimize.py
  -> .meta/proposals/*.md
  -> retrieve simulation / evaluation
  -> .meta/evaluations/*.json|*.md
  -> opt-in config / trial pack
  -> .meta/experiments/*.json + .meta/trials/*.json|*.md
  -> fallback candidate admission
  -> .meta/candidates/*.json|*.md
  -> applied optimization ledger
  -> .meta/optimizations/optimizations.jsonl
  -> self_loop_report.py / maintain.py report
```

## 主要脚本

| 脚本 | 作用 | 默认副作用 |
|---|---|---|
| `harness/scripts/meta_optimize.py` | 读取 health/retrieve/sync/task 信号，给出当前最值得处理的优化方向 | 无 |
| `harness/scripts/retrieve_zero_hit_analysis.py` | 找 human query zero-hit 和短 follow-up zero-hit | 无 |
| `harness/scripts/retrieve_downrank_simulation.py` | 模拟 downrank 参数，不改默认 retrieve | 无 |
| `harness/scripts/retrieve_fallback_candidates.py` | 生成 fallback 候选和建议 | 默认无；显式参数可写 review artifact |
| `harness/scripts/retrieve_fallback_cost.py` | 统计 fallback 实际触发成本 | 无 |
| `harness/scripts/self_loop_report.py` | 汇总自循环当前状态 | 无 |

## 已应用优化记录

当前 ledger:

`~/.claude/global-memory/.meta/optimizations/optimizations.jsonl`

每条记录至少应包含：

| 字段 | 含义 |
|---|---|
| `optimization_id` | 唯一 ID |
| `status` | `proposed` / `applied` / `rolled_back` / `rejected` |
| `scope` | `task-scoped` / `repo-scoped` / `global` |
| `default_enable` | 是否改变默认行为 |
| `source_proposal` | 提案来源 |
| `source_review` | 评审或相关性证据 |
| `source_trial` | 试用包 |
| `changed_files` | 实际改动范围 |
| `rollback` | 回滚方式 |

## 不做

- 不把 `.meta` 产物直接注入模型上下文。
- 不让 `meta_optimize.py` 自动改文件。
- 不因为 simulation 变好就默认启用全局 fallback。
- 不把 rejected candidate 加入 allowlist。
- 不让 experimental pipeline 进入开源 MVP 默认路径。

## 开源倒逼要求

外部用户能接受 `.meta` 的前提不是“它很智能”，而是：

1. 它默认只读。
2. 它可以关闭或忽略。
3. 它的产物结构可解释。
4. 它不会悄悄改变默认 retrieve 行为。
5. 它能说清楚为什么某个优化被接受、拒绝或回滚。

因此 `.meta` 在开源 profile 中应标记为 `experimental evidence pipeline`，不应作为 core install 的必需路径。
