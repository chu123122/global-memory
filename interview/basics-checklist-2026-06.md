---
name: basics-checklist-2026-06
description: 秋招基础/八股分级清单（S/A/B 三档，按 出现频率×简历关联度 排序），与 interview_question_bank 互补——bank 记真题与答题状态，本文件管学习范围与进度
type: interview
created: 2026-06-12
updated: 2026-06-12
source: 秋招顾问对话整理
access_count: 0
---

# 秋招基础/八股分级清单（2026-06 冲刺版）

> 前提共识：项目已够，瓶颈在基础。本清单吃"并发20%+渲染10%+部分表达"的时间，**算法 50% 不动摇**——八股决定面试上限，算法决定有没有面试。
> 每项统一验收标准：**合上材料，口头 90 秒讲清 + 接得住一层追问**。读懂≠会答，每项整理成 90 秒答题卡（格式参照 knowledge/docs/cpp-weak-token-async-lifetime.md 的 30 秒讲法）。
> 真题与答题状态记在 [interview_question_bank.md](interview_question_bank.md)，本清单只追学习进度。

## S 级——几乎必问，6 月内做完

- [ ] C++ 对象模型：构造/析构/拷贝/移动（Rule of Five）、vtable 与多态实现、虚析构、内存对齐与对象布局（bank 中多条 🔴必背 对应此项）
- [ ] 智能指针：control block、weak_ptr 解决什么（用 weak token 实战做答案）、RAII 第一性
- [ ] STL 底层：vector 扩容/迭代器失效、map vs unordered_map、rehash
- [ ] 网络八股：TCP/UDP 全套（三次握手/四次挥手/TIME_WAIT/可靠传输/拥塞概念）+ **自制"我的可靠 UDP vs TCP"对照表**——帧同步项目的标准追问，全清单 ROI 最高项
- [ ] 多线程全套 = knowledge_cpp_multithreading.md 的 3 周计划（线程池→SPSC），不在此重复
- [ ] UE 四种多线程方式：FRunnable / TaskGraph / AsyncTask / ParallelFor 各自适用场景（Phase 1c 实战过，半天整理；连带补 bank 中 TaskGraph/三线程模型两个 ❌）
- [ ] hello world 从编译到运行：预处理→编译→汇编→链接→装载，串起静态/动态库与符号
- [ ] 手撕 S 档：线程池（计划内）、shared_ptr、单例 DCLP 版（手撕×内存序二合一）、LRU（手撕题频率天花板，算共享算法时间）

## A 级——高频，7 月面试季前过完

- [ ] 内存：虚拟内存/页表/TLB、堆 vs 栈、new 底层（malloc/碎片）、碎片→池化（对象池手撕放此，讲述连到天美资源管理）
- [ ] 游戏概念：网络同步术语体系（事件流/状态流/输入流）、物理三阶段（broad→narrow→solve）、ECS 四优点 + vs MVC、状态机/行为树、AOI/九宫格
- [ ] 手撕 A 档：观察者、计时器（小顶堆实现，顺带复习堆）、对象池
- [ ] 场景题：圆内均匀随机（半径 sqrt(rand)，能解释为什么）、Fisher-Yates 洗牌、抽卡保底概率

## B 级——防守即可，不许深挖

- [ ] 反射：锚定 UE UHT（UCLASS 宏→generated.h→运行时类型信息 = C++ 无原生反射的人工补丁），对比 C# 原生反射。2 小时收工
- [ ] 渲染防守包：光栅化管线、shadow map、前向 vs 延迟、移动端 TBDR（连心动自适应性能插件）
- [ ] 稀疏集：定位是聊 ECS 的加分谈资，非考点
- [ ] OS 杂项：进程 vs 线程、死锁四条件（多线程计划顺带）

## 明确不做（防镀金）

- select/epoll 等服务端网络编程（客户端岗不考）
- 读写锁手撕（概念即可）、无锁结构 SPSC 以外不外扩
- MPMC / hazard pointer / 自定义 allocator

---
## 更新日志
- 2026-06-12: 初始创建。来源：用户自列基础清单 + 顾问补洞（网络八股/vtable/STL 底层三大遗漏）+ 分层排序
