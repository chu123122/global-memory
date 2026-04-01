---
name: knowledge-ue-internals
description: UE 引擎底层知识，包括 TaskGraph/线程模型/UObject/Pak VFS
type: knowledge
created: 2026-04-01
updated: 2026-04-01
source: 学习 Agent
access_count: 0
---

# UE 引擎底层

> 源码阅读笔记 + 实习经验 + InsideUE4 学习

## 源码阅读记录
（随 InsideUE4 学习进度更新）

## 实习中学到的
- Pak 加载：上万 Pak 卡死 → 拓扑图 + 多线程调度解决
- 模块依赖：三级权限管理
- 资源管线：双轨隔离 + 路径软加载
- Git 工具链：减少 43% 耗时

## 线程模型
- GameThread / RenderThread / RHI Thread 三线程
- TaskGraph 基于 DAG 的任务调度
（待深入学习）

## UObject 系统
- 反射 / GC / 序列化
（待学习）

## 和面试的关联
- FPakPlatformFile → VFS 设计 → 面试聊引擎底层的入口
- 模块依赖 → UBT 编译系统 → 面试聊工程架构

---
## 更新日志
- 2026-04-01: 初始创建，迁移 my-learning-agent 中的实习经验
