---
description: 多agent自动调度用混合模型：静态角色目录+AI从目录挑+代码绑定模型并orca派生
priority: high
status: active
trigger:
  keywords:
    - concept:multi-agent
    - concept:agent-dispatch
    - tool:orca
  tags:
    - design
    - workflow
    - tooling
  stages:
    - discussion
    - implementation
last_updated: 2026-06-17
---

# 决策：多 agent 自动调度用混合模型

> 日期：2026-06-17
> 背景：是 `knowledge/knowledge_loop_engineering_harness_mapping.md` 的直接延伸——给单 agent loop 长出多 agent 层。需求：自动划分 agent，按需派生 budget tier（骨折 GPT-5.5 / codex）worker。
> 状态：方向已定，**实现待走 `/work` 立任务**。

## 决定

把"自动划分 agent"拆成两个常被混淆的子问题，分别用不同钉法：

1. **有哪些角色（roster / WHAT）→ 静态**：固定角色目录，每个角色预绑 `model / effort / agent-kind`。这是确定性映射表，落 config/Script 层。
2. **某任务派谁、派几个（WHETHER & how many）→ 薄 AI 判断**：lead 拆解任务后**只能从固定目录里挑**角色 + 定数量，不凭空造角色。
3. **绑定模型 + 派生（HOW）→ 代码**：role→model 查表 + orca `create_worker` 派生 + loop，全确定性。

即「**固定角色目录(静态) → AI 从目录挑(判断) → 代码绑定+派生(确定)**」。

## 备选方案

| 方案 | 优点 | 缺点 | 取舍 |
|------|------|------|------|
| A 纯静态（用户每次指定 roster） | 最可控、可复现 | 每次要人点名，"auto" 没了 | 弃 |
| B 纯动态（AI 每次自由拆角色+定模型+定数量） | 最灵活、任何任务形状 | 不可复现、成本不可控（1 文件改动可能派 8 worker）、难调试、违背 DORMANT 克制 | 弃 |
| **C 混合**（静态目录 + AI 挑 + 代码派生） | 可复现、成本可控、保留自动性 | 需维护目录 | **选** |

## 理由

- **对齐铁律 8**（AI 只做判断活，路由/确定性变换用代码）：角色目录与"role→model"是确定性表（代码答），"派谁"才是判断（AI 答）。纯动态把路由也塞给 AI，违背此律。
- **复用现成种子**：`agents/` 已有 ~10 个静态角色定义（work-agent / code-reviewer / design-reviewer / guardian-agent / sidecar-explorer / log-triage ...），是现成目录种子。
- **对齐 DORMANT 克制**：接入索引 §0 把 Subagent 层标 DORMANT 以防过早分层；混合让目录小步扩，而非动态膨胀。

## 适用范围

- **适用**：需要并行子任务、独立审查、大范围调研，且愿意用 budget worker 控成本的场景。
- **v1 起手式（遵循铁律 2 最小化，先 2-3 角色不铺开）**：

  | 角色 | agent / 模型 | 职责 |
  |------|-------------|------|
  | `dev` | codex / 骨折 gpt-5.5 / effort high | 按 spec 实现 |
  | `reviewer` | codex / 骨折 gpt-5.5 | 只报告不改（对齐铁律 18） |
  | `explorer`（可选） | codex / 骨折 gpt-5.5 / effort low | 大范围调研、call chain |

- **三条护栏**：
  1. 骨折 gpt-5.5 = budget tier，**仅 Codex API key 模式可开**，OAuth 模式会被 `BUDGET_MODEL_REQUIRES_API_MODE` 拒——派生前确认模式。
  2. worker 数量设**硬上限**（orca 自带 soft/hard cap），防 agent sprawl。
  3. 派生计划先过人一眼再执行（铁律 16：架构取舍要人确认）；稳定后再考虑预算阈值内自动放行。
- **不适用**：单文件小改、快速问答——直接单 agent 做，别起 worker。

## 复审条件

- 角色目录涨到 >5 且频繁误派 → 重审是否该引入更细的目录或轻量动态。
- orca budget worker 行为/限额变更，或 Codex 模式策略变化 → 重审护栏 1/2。
- v1 跑一段后若"派谁"判断稳定度低 → 考虑把判断也半固化成任务类型→角色集的查表。

## 实现入口

- 本文件只记**决策**；dispatcher 实现（角色目录 config 落点、派生编排、护栏脚本）走 `/work` 立任务文档。
