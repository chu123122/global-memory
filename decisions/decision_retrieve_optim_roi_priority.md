---
description: retrieve 链优化 ROI 排序：frontmatter 修剪 > top_k 降参 > monitor > 补 aliases > 算法调权
priority: high
status: active
trigger:
  keywords:
    - concept:retrieve
    - concept:optimization
    - concept:roi
  tags:
    - tooling
    - design
  stages:
    - discussion
    - implementation
last_updated: 2026-05-22
---

# Retrieve 链优化 5 维 ROI 排序

## 决定

按 ROI 分 5 档，先做 (1)(2)(3)，留 (4)(5)。

1. **frontmatter 修剪噪声 keyword**（最高，0 代码改）
2. **top_k 降参**（次高，1 行 const 改）
3. **加 health monitor**（中，新 check 文件）
4. **补 aliases 治 zero_hit**（低，需先分析 fail query）
5. **why 排序调权**（最低，黑盒难回滚）

## 备选方案

- A 一次性全做：风险高，无法定位回归源
- B 只做 top_k 降参：治 pointer_rate 一半，zero_hit 不动
- **C 按 ROI 分批**（选）：每批可观察 7d 数据再决定下一档

## 理由

- frontmatter 修剪零代码风险，效果立竿见影（噪声 top3 文件直接除）
- top_k 降参可逆，A/B 7d 对比
- monitor 是观察工具，加了不变现状
- aliases 治 zero_hit 需大量分析 + 写记忆元数据，工作量大
- 算法调权改 embedding/排序，黑盒难调，长期最后做

## 适用范围

- 适用：retrieve / RAG / pointer-based memory injection 系统优化
- 不适用：算法本身有 bug 时（应先 fix bug 而非调参）

## 复审条件

- top_k 2 跑 7d 后 call_rate 仍 <10% → 重排优先级（可能算法本身有问题）
- 新增 aliases / 算法调权时回看 ROI 排序
