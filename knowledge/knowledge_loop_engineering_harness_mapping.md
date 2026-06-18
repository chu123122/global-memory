---
description: loop engineering(Cherny)映射到本harness双轴；单agent已满配，缺口=多agent loop
priority: medium
status: active
trigger:
  keywords:
    - concept:loop-engineering
    - concept:harness
    - concept:agent-loop
  tags:
    - design
    - workflow
    - tooling
  stages:
    - discussion
    - implementation
last_updated: 2026-06-17
---

# loop engineering 映射到本 harness

> 来源：Boris Cherny（Claude Code 创造者）在红杉 AI Ascent 2026 访谈提出的 "loop engineering / harness engineering"——「别 prompt Claude，搭一个自己 prompt 自己的系统」。核心循环 `Observe → Plan → Act → Reflect → Repeat`。

## 核心要点

- **本 harness 本身就是一个 loop engineering 产物**，且在单 agent 层面基本满配：
  - 设计轴闭环 `执行→沉淀→反馈→(回)执行` = Cherny 说的"自我 prompt 系统"。
  - Observe = 反馈层 `retrieve_inject.py` 每轮自动召回 + Context Brief。
  - Reflect = 沉淀层（写 decisions/knowledge/retro）。
  - harness engineering（脚手架）= 运转轴 `Rules→Skills→Script + hook 旁挂`。
  - "Claude.md tax"（上下文文件省轮次）= CLAUDE.md 铁律 + 接入索引 just-in-time 加载。
  - 带检查点/审批门的多天循环 = `/work` Step0-4 + 三层文档防线 + done 打回规则。
  - 循环原语 = 内置 `/loop` skill。
- **唯一缺口**：Cherny 那套和本 harness 都是 **1 个 agent 在 loop**。下一阶 = **loop 里派生 loop**（多 agent 编排）。
- 这对应接入索引 §0 里标 **DORMANT 的 Subagent 层**——多 agent 调度 = 唤醒该层 + 用 orca budget worker 落地。
- 流传数字（8x 产出 / 80%+ 合入代码 / 76% 成功率）是二手博客归因，无一手出处，**当谈资不当硬数据**。

## 常见误区

- 把 loop engineering 当"新功能"去追——实际单 agent 层你已建好，真正未做的只有多 agent。
- 把"自我 prompt 系统"理解成让 AI 自由发挥——Cherny 的 loop 同样有检查点、错误恢复分支、危险操作的人工审批门，与本 harness 的确定性下沉一致。

## 参考

- 决策落点：`decisions/decision_multi_agent_dispatch.md`（多 agent 调度，本知识的直接延伸）。
- The New Stack《loop engineering》；explainx.ai harness engineering 拆解；YouTube 红杉 AI Ascent 2026 Boris Cherny 原访谈。
