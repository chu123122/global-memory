---
description: 归档复盘抽取候选必须进入 triage 到关闭的反馈闭环
priority: high
status: superseded
trigger:
  keywords:
    - concept:archive-feedback-loop
    - concept:retrospective
    - concept:triage
    - tool:archive_task
  tags:
    - workflow
    - memory
  stages:
    - delivery
    - review
last_updated: 2026-06-16
---

# 归档复盘反馈闭环

## 规则

归档任务不能只生成 `_archive/extract_candidates.md` 就结束；复盘候选必须被 triage，并进入 issue / knowledge / decision / follow-up task / drop-with-reason 之一，后续修复或采纳后要有可关闭状态。

## Why

2026-06-15 `global-memory-entry-pr-gate` 归档时，`archive_task.py --extract` 生成了 3 条候选，但默认只停在“人工判定是否入库”。用户指出这只完成了“新建任务 → 完成 → 复盘”的前半段；后半段“复盘反馈分析 → 改正 → 验证 → close”仍是空的。

## How to apply

触发：归档 task、读 `_archive/extract_candidates.md`、讨论复盘/反馈闭环时。

执行要求：

1. 每条候选给稳定 `candidate_id`。
2. triage 结果必须是 `promote_to_issue` / `promote_to_knowledge` / `promote_to_decision` / `promote_to_task` / `drop_with_reason`。
3. 被提升的候选必须记录 `target_path` 或 `task_id`。
4. 修复或采纳后回写 `verification` 和 `closed_at`。
5. 如果本轮只生成候选、没有消费候选，最终答复必须明说“反馈闭环未完成”。

## 关闭记录

2026-06-16 triage 关闭原因：本条原先要求把归档候选消费成可关闭反馈闭环；已由 `/triage` skill 取代为更轻的 inbox triage loop，归档候选不再作为引擎，只作为可选输入源。当前已落地 `skills/triage/v1/SKILL.md` 与 `harness/scripts/triage_inbox.py`，并新增关闭机械门 `triage_inbox.py --verify-close`，防止口头 closed。

验证命令：

```powershell
python harness/scripts/triage_inbox.py --json
python harness/scripts/triage_inbox.py --verify-close feedback/feedback_archive_feedback_loop.md --json
```

superseded reason：旧的 per-candidate archive 状态机设计被无状态 inbox triage 流程取代，保留“候选必须被消费”的原则，不再保留旧 `candidate_id -> target -> verification` 强 ledger 要求。
