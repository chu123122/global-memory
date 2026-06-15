---
description: C++ 多线程/并发编程
priority: medium
status: active
trigger:
  keywords:
    - concept:cpp
    - concept:thread
    - concept:tsan
    - concept:lock_guard
    - concept:mutex
  tags:
    - cpp
    - ue
    - interview
    - memory
  stages:
    - implementation
last_updated: 2026-06-12
---

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

## 学习路线（2026-06-12 重排：秋招冲刺版，3 周 × ~1h/天）

> 形式：独立纯 C++ 仓库（不在 UE 里练），WSL2 + `clang++ -std=c++17 -fsanitize=thread -O1 -g`。
> 每练习一个文件夹一个 main.cpp（自带压力测试），硬上限 200 行。
> 护栏：不做 MPMC / hazard pointer / 自定义 allocator；单题卡住 >1.5h 就带问题求助；Week 3 优先级高于 Week 2 做到完美（表达 ≥ 并发）。

### Week 1：mutex/CV → 线程池
- [ ] 1.1 有界阻塞队列（CV 谓词循环 / 虚假唤醒 / notify_one vs all）
- [ ] 1.2 线程池 v1：N worker + submit(function) + 优雅关闭
- [ ] 1.3 线程池 v2：submit 返回 std::future（packaged_task）
- 验收：①无忙等 ②关闭语义二选一且能说出区别（排空 vs 立即）③任务异常不杀 worker ④8 线程×10w 任务 TSan 干净且计数正确 ⑤合书 25min 默写

### Week 2：atomic + 内存序 → SPSC 验收
- [ ] 2.1 自旋锁（atomic_flag, TAS acquire / clear release）+ benchmark vs mutex（短/长临界区两组，记数字）
- [ ] 2.2 False sharing 演示：同 cache line vs alignas(64)，测出倍数
- [ ] 2.3 SPSC 环形队列（验收题，从"两索引各只有一个写者"自行推导，不照抄）
- 验收：①TSan 干净（1000w 递增整数序列校验）②吞吐 vs mutex+queue 有数字 ③故意破坏实验：release→relaxed 让 TSan 抓到，并能解释 x86 强内存模型为何掩盖、ARM 上为何真炸（连到心动 Android 工作）④每个 memory_order 能口头说"为什么是它、relaxed 会怎么死"

### Week 3：接回真实世界 + 转成嘴上的东西
- [ ] 3.1 集成：SPSC 塞进帧同步项目（收包线程→逻辑线程），变成简历句子
- [ ] 3.2 重述存量经历 ×3 个 30 秒版本（照 weak token 文档格式）：天美主线程卡死修复 / Phase 1c weak token / DOTS Job System 为何 cache 友好
- [ ] 3.3 模拟拷打（/learn → cpp-tutor）：线程池→任务窃取→唤醒丢失；SPSC→MPSC 要加什么→CAS→ABA。后两层答不上没关系，能说出边界即可

最终验收：线程池 + SPSC 两个工件均能 20-25min 白板默写，且每个 memory_order 选择讲得出理由。

---
## 更新日志
- 2026-06-12: 学习路线重排为秋招冲刺版（3 周：线程池→SPSC→集成+表达），含逐项验收标准与护栏；旧四周骨架删除
- 2026-04-01: 初始创建，迁移 my-learning-agent 中的 UE 关联知识
