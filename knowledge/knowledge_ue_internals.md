---
name: knowledge-ue-internals
description: UE 引擎底层知识，包括 TaskGraph/线程模型/UObject/Pak VFS
summary: "实习经验(Pak/模块依赖/资源管线/Git工具链)已记录；源码/线程模型/UObject待学"
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

### TaskGraph 三核心类（2026-04-14 自测T17写入）
- FBaseGraphTask：任务基类，含执行线程需求(ENamedThreads)和依赖列表
- FGraphEvent：任务完成的事件令牌，下游任务可依赖它（类似future）
- TGraphTask<T>：模板包装，通过 CreateTask().ConstructAndDispatchWhenReady() 启动
- 关系：TGraphTask执行完 → 触发FGraphEvent → 解锁依赖它的下游任务

## UObject 系统
- 反射 / GC / 序列化

### FArchive 序列化（2026-04-14 自测T18写入，知识盲区）
- UE 所有序列化的基类（存档/网络/资产加载都用它）
- 同一个 `<<` 操作符，IsLoading()==true 时读，false 时写
- 同一份 Serialize 函数可同时处理读写逻辑（对称设计）
- 常见子类：FMemoryReader/FMemoryWriter（内存）、FArchiveFileReaderGeneric（文件）

## 和面试的关联
- FPakPlatformFile → VFS 设计 → 面试聊引擎底层的入口
- 模块依赖 → UBT 编译系统 → 面试聊工程架构

---
## 更新日志
- 2026-04-01: 初始创建，迁移 my-learning-agent 中的实习经验
