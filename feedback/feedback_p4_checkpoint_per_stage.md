---
description: feedback_p4_checkpoint_per_stage
priority: medium
status: active
trigger:
  keywords:
    - workflow
  tags:
    - workflow
  stages:
    - implementation
last_updated: 2026-05-20
---

---
name: 阶段完成用新 CL 存档保留多 checkpoint
description: P4 工作流偏好 — 每个重构阶段完成后用新的 changelist shelve, 不要覆盖同一 CL, 保留可回滚到任意阶段的 checkpoint 链
type: feedback
created: 2026-04-23
updated: 2026-04-24
source: XDAdaptivePerformance 阶段 2c-1 p4 revert 复盘
access_count: 0
---

每个阶段完成后用**新的 P4 changelist** 单独 shelve, 不要 `p4 shelve -f` 覆盖同一 CL。

**Why:** 用户 2026-04-23 在 XDAdaptivePerformance 阶段 2c-1 目录重组失败 + p4 revert 撤过头事件后明确要求。事件复盘:
- 之前一直用 CL 5156891 反复 `shelve -f` 覆盖, 每次 shelve 只保留"当下最新状态"
- 当 2c-1 失败 revert 撤过头时, 只能 unshelve 回到 2b 完成态(那是最近一次 shelve 的状态)
- **2a 完成 / 2b 完成 / 2c-1 完成的中间 checkpoint 全部丢失** — 只能回到最近的一次 shelve 点
- 如果用多 CL 保留: 5156891 = 2b 完成 / 5156892 = 2c-1 完成 / 5156893 = 2c-2 完成 ..., 任何阶段失败都能 unshelve 到上一阶段的稳定 checkpoint

**How to apply:**

阶段完成后的 P4 流程:
1. 跑测试不回归 ✅
2. 创建新 CL: `p4 change -t restricted` (或直接 `p4 change`, 编辑器写描述)
3. 把当前 opened 文件 reopen 到新 CL: `p4 reopen -c <new_cl> //...` (相对当前 pending CL)
4. shelve 到新 CL: `p4 shelve -c <new_cl>`
5. **不删旧 CL** — 旧 CL 保留作为前一阶段的 checkpoint

CL 描述模板(写清是哪个阶段的 checkpoint):
```
<task-name> · 阶段 <X> · <段名> 完成
- 累计含: 2a 测试基建 + 2b 低风险清理 + 2c-1 精简版
- 测试: 12 PASS / 0 FAIL
- 下一段: 2c-2 行为改动
```

**适用场景:**
- 重构任务的阶段切分(阶段 1a / 1b / 1c / 2a / 2b / 2c / ...)
- 任何"完成一段, 跑测试, 锁 checkpoint, 进下一段"的工作流

**不适用:**
- 单点 bug 修复(没必要分 CL)
- 调试中间态(随时改, 不算阶段完成)
- 文档纯改动(不需 P4 shelve checkpoint)

**注意:**
- shelve 是 P4 server 端独立存储, **多 CL 多 shelve = server 多份存储**, 可能占空间但 KB 级不算事
- 任务结束后(submit 一个 CL) 其他 CL 可 `p4 change -d <CL>` 删
- 用户偏好: 多 checkpoint > server 空间
