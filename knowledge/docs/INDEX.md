# Knowledge Docs 总索引

> 30+ 篇深度文档分组索引。MEMORY.md 顶层只放本文件链接，避免索引爆炸。
> 按需读取——不要在每次对话开始就加载这些文件。

## C++ 语言与底层
- [cpp-multithreading-guide.md](cpp-multithreading-guide.md) — C++ 多线程完整指南（当前最高优先级短板）
- [cpp-memory-model-lockfree.md](cpp-memory-model-lockfree.md) — 内存模型 + 无锁编程
- [cpp-template-metaprogramming.md](cpp-template-metaprogramming.md) — 模板元编程
- [cpp-weak-token-async-lifetime.md](cpp-weak-token-async-lifetime.md) — 异步任务 lifetime / weak token 模式

## UE 引擎
- [ue-engine-internals-guide.md](ue-engine-internals-guide.md) — UE 引擎底层综述
- [ue-source-deep-dive.md](ue-source-deep-dive.md) — UE 源码深度剖析
- [ue5-engine-startup-modules.md](ue5-engine-startup-modules.md) — 引擎启动 + Module 系统
- [ue5-uobject-reflection.md](ue5-uobject-reflection.md) — UObject 反射机制
- [ue5-memory-allocator.md](ue5-memory-allocator.md) — 内存分配器
- [ue5-smart-pointers-vs-std.md](ue5-smart-pointers-vs-std.md) — UE 智能指针 vs std
- [ue5-async-loading-reference.md](ue5-async-loading-reference.md) — 异步资源加载（入职任务直接相关）
- [async-resource-loading-preresearch.md](async-resource-loading-preresearch.md) — 多线程资源加载插件预研
- [ue5-rendering-pipeline.md](ue5-rendering-pipeline.md) — 渲染管线
- [ue5-network-replication.md](ue5-network-replication.md) — 网络同步/Replication
- [ue5-gas-ability-system.md](ue5-gas-ability-system.md) — GAS 技能系统
- [ue5-animation-motion-matching.md](ue5-animation-motion-matching.md) — 动画 + Motion Matching

## 游戏引擎通用
- [ecs-archetype-vs-sparseset.md](ecs-archetype-vs-sparseset.md) — ECS 架构对比
- [game-physics-reference.md](game-physics-reference.md) — 游戏物理 reference
- [game-networking-reference.md](game-networking-reference.md) — 游戏网络 reference

## 面试与求职
- [interview-cheatsheet.md](interview-cheatsheet.md) — 面试速查
- [interview-deep-dive-chains.md](interview-deep-dive-chains.md) — 面试深挖链
- [interview-trends-2025-2026.md](interview-trends-2025-2026.md) — 2025-2026 面试趋势
- [project-interview-scripts.md](project-interview-scripts.md) — 项目讲解话术
- [xindong-tech-intel.md](xindong-tech-intel.md) — 心动技术情报

## 工程方法 / 系统
- [harness-engineering-2026.md](harness-engineering-2026.md) — Harness Engineering 2026
- [prompt-engineering-system.md](prompt-engineering-system.md) — Prompt 工程系统
- [code-review-and-blog-templates.md](code-review-and-blog-templates.md) — Code Review + 博客模板
- [learning-methodology.md](learning-methodology.md) — 学习方法论
- [ai-impact-game-dev.md](ai-impact-game-dev.md) — AI 对游戏开发的影响
- [ai-system-audit-2026-04-16.md](ai-system-audit-2026-04-16.md) — 2026-04-16 系统审计

## 资源 / 链接
- [resource-links.md](resource-links.md) — 资源链接汇总
- [gdc-must-watch.md](gdc-must-watch.md) — GDC 必看演讲

---

> 维护规则：新增 docs/*.md 时**必须**在本索引追加一行，否则 verify_memory.py MEM-11 报 ERROR。
