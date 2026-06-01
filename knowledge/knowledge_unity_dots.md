---
description: Unity DOTS/ECS 架构经验
priority: medium
status: active
trigger:
  keywords:
    - concept:build
    - concept:thread
    - tool:ue
  tags:
    - ue
    - unity
    - interview
  stages:
    - implementation
last_updated: 2026-05-20
---

---
name: knowledge-unity-dots
description: Unity DOTS/ECS 架构经验，Archetype/Chunk/SOA/Burst+JobSystem
summary: "Archetype/Burst/四维性能分析已掌握；PBD+FlowField+Boids项目实践已记录"
type: knowledge
created: 2026-04-01
updated: 2026-04-01
source: 学习 Agent
access_count: 0
---

# Unity DOTS/ECS 架构经验

## 核心概念（已掌握）
- Archetype → Chunk(16KB) → SOA 布局
- Burst 编译器原理（消除托管对象/装箱 + SIMD 向量化）
- 四维性能分析（D-Cache/I-Cache/SIMD/多线程）

## 项目实践
- PBD 物理求解器 + Flow Field + Boids
- 200+ 单位碰撞避障，逻辑帧 0.2ms
- 空间哈希 Broad Phase，Gauss-Seidel 迭代

## 面试话术
（参见 interview_question_bank.md）

---
## 更新日志
- 2026-04-01: 初始创建，基于已有项目经验整理
