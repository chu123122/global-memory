---
description: HANDOFF.md 多 Phase 推进无 gate → 全程不回写漂移
priority: medium
status: active
trigger:
  keywords:
    - concept:handoff
    - concept:drift
    - tool:harness
  tags:
    - workflow
    - tooling
  stages:
    - implementation
last_updated: 2026-05-21
---

# HANDOFF.md 多 Phase 不回写漂移

## 现象

任务跑完 N 个 Phase（N≥3）后，`core/HANDOFF.md` 仍停留在初始态（「下次起 P1」），「已完成」节空 / 与 `design/设计文档.md` Phase 拆分表脱节。归档前才发现。

## 根因

三层缺位：

1. **工具层缺 gate**：`update_phase_status.py` 三同步覆盖「Phase 卡 frontmatter + 设计文档表 + 验收清单」，HANDOFF 不在内
2. **规则层缺约束**：`task-lifecycle.md` § 2 写「每次 session 末尾更新 HANDOFF.md」但无 lint / hook 兜底
3. **执行层偷懒**：`changelog_inject.py` hook 每轮提醒 CHANGELOG，HANDOFF 无类似 hook → 自觉度归零

`harness-governance-followup` 跑完 P1-P8 全程未回写 HANDOFF，归档前才发现 → 暴露此 bug。

## 修复

短期：发现后手动 Edit HANDOFF.md 同步到当前 Phase 状态。

长期：开后继任务 `harness-handoff-sync-gate`，三选项：
- B1 扩 `update_phase_status.py` 加 `--sync-handoff` 子命令
- B2 新 hook `handoff_drift_check.py` PostToolUse:Edit
- B3 扩 `archive_task.py --extract` 加第 6 护栏「HANDOFF.md `last_updated` ≥ 最新 done Phase」

推荐 B3+B2 组合（兜底 + 提醒）。

## 验证

`archive_task.py --check <task>` 看 ready_to_archive 判定；HANDOFF 漂移肉眼可见。
