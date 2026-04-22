---
name: knowledge-cpp-multithreading
description: C++ 多线程/并发编程知识积累（当前最高优先级短板）
summary: "⚡最高优先级短板；UE关联(FCriticalSection/FEvent/TAtomic/TaskGraph)已记录；已掌握部分待填"
type: knowledge
created: 2026-04-01
updated: 2026-04-01
source: 学习 Agent
access_count: 0
---

# C++ 多线程/并发编程

> 从面试短板到项目实践的积累

## 已掌握的知识点
（随学习进度更新）

## 和 UE 的关联
- UE 的 FCriticalSection = 平台抽象的 mutex
- UE 的 FEvent = 平台抽象的 condition_variable
- UE 的 TAtomic = std::atomic 的 UE 封装
- UE 的 TaskGraph = 基于 DAG 的任务调度（比 std::async 更复杂）

## 常见面试题 & 话术
（随学习进度更新）

## 踩坑记录
（随练习进度更新）

## 模式与文档
- **weak token / lifetime witness**（异步任务 lifetime 管理）：[docs/cpp-weak-token-async-lifetime.md](docs/cpp-weak-token-async-lifetime.md)
  - 起源：XDAdaptivePerformance Phase 1c 子线程化实战
  - 核心：智能指针 control block 是免费 alive flag；token 是为非 TSharedPtr 管理对象（IModuleInterface / Actor）补一个"挂靠"的生命周期信号
  - 跨语言对照：UE Slate / iOS [weak self] / Java WeakReference / Rust Weak<T>
  - 已附 30 秒面试讲法 + 4 类踩坑，可作博客草稿

## 学习路线
```
Week 1：std::thread / mutex / lock_guard / unique_lock
Week 2：condition_variable / atomic
Week 3：future / promise / async / 线程池
Week 4：无锁队列 / memory_order / False Sharing
```

---
## 更新日志
- 2026-04-01: 初始创建，迁移 my-learning-agent 中的 UE 关联知识
