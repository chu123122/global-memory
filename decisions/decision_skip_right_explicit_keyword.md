---
description: 5 护栏「跳过权」用显式关键词声明而非文件缺省，避免「不写=跳过」逃避路径
priority: high
status: active
trigger:
  keywords:
    - concept:retro
    - concept:skip
    - tool:harness
  tags:
    - workflow
    - design
    - tooling
  stages:
    - discussion
    - implementation
last_updated: 2026-05-21
---

# 5 护栏跳过权用显式关键词声明

## 决定

`core/复盘.md` 5 护栏 lint 中，「跳过复盘权」必须通过文件内**显式关键词**声明，不接受「文件不存在 = 跳过」。

合法跳过关键词：`本任务无重大踩点` / `跳过复盘`。

## 备选方案

- **A 文件不存在 = 跳过**：写复盘 = 选择题
- **B 文件必存在 + 显式关键词 = 跳过**（选）：写复盘 = 必答题，跳过也要写一行表态
- C 强制写复盘不允许跳过：过严，纯流水任务无内容可写

## 理由

A 留逃避路径：偷懒不写 = 跳过，AI 跑完任务自动符合「跳过」条件 → 5 护栏失效。
B 强制显式表态，跳过也要承担书写成本（认知摩擦），用人来过滤「真没踩点」vs「偷懒不写」。

实测：`harness-governance-followup` 自身归档时 lint 拦住 → 强制写出复盘 → 暴露 P2/P5 伪需求 + HANDOFF 漂移等真实问题。A 方案下这些都会被埋。

## 适用范围

适用：任务归档前复盘 / 任何「质量门要求显式输出」场景。

不适用：纯流水任务（无 Phase 拆分 / 无设计文档）的 commit message 类。

## 复审条件

- 假写复盘比例 >30%（关键词出现但内容空）→ 需加内容质量 lint
- 实际归档拦截率 <10%（绝大多数任务都能 PASS）→ 5 护栏可能偏宽
