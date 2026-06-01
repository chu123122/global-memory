---
description: 滑动窗口算法计数陷阱：item count vs cumulative total 必须分离
priority: medium
status: active
trigger:
  keywords:
    - concept:window
    - concept:algorithm
    - concept:jaccard
  tags:
    - design
    - tooling
    - python
  stages:
    - implementation
last_updated: 2026-05-21
---

# 滑动窗口计数陷阱：item count vs cumulative total

## 核心要点

1. **滑动窗口 + 同类合并** 容易踩计数陷阱：窗口元素 N 个，但「累计调用次数」 ≠ N。

2. **典型场景**：topic-shift 检测窗口存最近 5 条 user prompt。当新 prompt 与窗口末尾 jaccard ≥ threshold（同主题）→ 合并到末尾 item，窗口 item 数不增。

3. **错误实现**：用 item.count 字段记每个窗口元素的累计次数；total = sum(item.count)。合并时 count++ 但窗口 item 数仍 = N，total 增长正常 → 看似 OK，但**窗口溢出（>N）时旧 item 被淘汰，其 count 也丢**，total 跳变下降。

4. **正确实现**：顶层独立 `cumulative_total` 字段，每次调用 ++1（无关合并）；窗口 prompts 只存 token 列表 + 截 last N。`{"prompts": [...], "total": int}`。

5. **判定阈值用 total，不用 len(prompts)**：例 `if total ≥ 10 and jaccard < 0.08 → nudge`。total 单调递增，不受窗口淘汰影响。

6. **本质**：「最近 N 个唯一/合并后 item」与「累计调用次数」是两个数据，强行复用一个字段必踩坑。

7. **同类陷阱**：LRU cache 的 hit count、rate limiter 的窗口计数、token bucket 的 fill rate vs accumulated 都需分离。

## 常见误区

- 「窗口只存最近 5 个，再加 total 不冗余吗？」→ 不冗余。窗口为「相似性判定」服务，total 为「触发阈值」服务，语义不同。
- 「合并时不淘汰旧 item，永远累加」→ 内存爆。淘汰 + 顶层 total 才完整。

## 参考

- 实现：`~/.claude/global-memory/harness/hooks/route_check.py:update_topic_window` / `check_compact_nudge`
- 关联设计：`D:/ClaudeTasks/archived/harness-governance-followup/design/Phase7-compact-nudge.md`（归档后路径）
