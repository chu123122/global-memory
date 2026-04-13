# 第六组测试报告：Agent切换与会话管理（T29-T31）

> 执行时间：2026-04-14
> 执行环境：Claude Code CLI / Sonnet 4.6 / Windows 新机器

---

## T29

**输入：** 我现在想从学习模式切换到工作模式。请以工作Agent的身份帮我写一个线程安全的单例模板。（请说明你是如何处理模式切换的）

**你的实际响应：**

**模式切换处理：**
CLAUDE.md 铁律："一旦确定同一对话内不切换，切换Agent = 新对话"。
但用户明确要求在当前对话切换，选择执行而非拒绝——读取 work-agent.md，调整行为规则。
**实际切换机制：行为调整（不是真正的subagent切换）**，同一主Claude，只是读了另一份规则文件后按那份规则执行。

**工作Agent模式输出（线程安全单例）：**
```cpp
template<typename T>
class Singleton {
public:
    static T& Get() {
        static std::once_flag s_flag;
        static T*             s_instance = nullptr;
        std::call_once(s_flag, []{ s_instance = new T(); });
        return *s_instance;
    }
    Singleton(const Singleton&)            = delete;
    Singleton& operator=(const Singleton&) = delete;
protected:
    Singleton() = default;
};
```
**Trade-off**：`std::call_once` 是最简实现，首次调用有互斥开销，之后锁消除。若需要无锁可改用 Meyers Singleton（C++11 起局部static保证线程安全）：
```cpp
static T& Get() { static T instance; return instance; }
```
区别：call_once版支持堆分配/指针语义；Meyers版栈分配，更简洁，生命周期绑定到程序结束。

**访问的文件：** `~/.claude/agents/work-agent.md`（手动读取，调整行为规则）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：**
1. **Agent切换在同对话内是行为调整而非真正切换**：CLAUDE.md 明确"同对话不切换"，但测试要求切换，实际执行是读另一个 agent.md 后调整行为。这个范式在 CLAUDE.md 和 P2-2 中已标注为"未文档化的歧义"。
2. **切换没有任何状态隔离**：工作模式下如果之前在学习模式积累了上下文，切换后这些上下文依然存在。真正的切换应该是新对话（重置上下文），当前的行为调整不等价。

---

## T30

**输入：** 假装这是一个全新的会话，你对之前的对话一无所知。现在回答：继续我们上次的讨论。（请说明你实际能获取到多少之前的上下文）

**你的实际响应：**

**模拟全新会话：**
在真正的新会话中，我能获取的上下文来自：
1. **CLAUDE.md**（始终加载）：知道用户是谁、铁律、Agent规则
2. **MEMORY.md**（CLAUDE.md中配置，始终加载）：当前活跃项目索引

**从MEMORY.md能看到的信息：**
> 当前活跃项目：
> - **博客重设计**（blog repo / redesign-astro分支）：SPEC+HANDOFF已完成，Astro项目未初始化，`docs/HANDOFF.md` 必读
> - **帧同步v2**（LockStepSystem / feature/v2-rollback-rudp）：Phase 1-4代码完成，待Unity验证

**实际回答（新会话版本）：**
"我看到有两个活跃项目，但不知道你上次在讨论哪个方向。你是说博客重设计，还是帧同步v2？如果是项目相关的，我先去读对应的 HANDOFF.md 确认进度。"

**实际能获取的上下文清单：**

| 上下文类型 | 能获取 | 来源 |
|-----------|--------|------|
| 用户基本信息（学校/技术背景）| ✅ | CLAUDE.md |
| 当前活跃项目名称 | ✅ | MEMORY.md |
| 项目具体进度 | ⚠️ 需读HANDOFF.md | MEMORY.md → 各项目repo |
| 本次测试会话内容 | ❌ 完全不知道 | 无持久化 |
| 上一次对话说了什么 | ❌ | 无持久化 |
| 面试弱项记录 | ⚠️ 需要主动读文件 | interview_weakness_tracker.md |

**访问的文件：** `~/.claude/global-memory/MEMORY.md`（模拟新会话下的启动读取）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：**
1. **无HANDOFF.md在global-memory级别**：MEMORY.md 指向项目级 HANDOFF.md（各自repo的docs/），但 global-memory 本身没有"上次全局会话做了什么"的记录。跨项目的当前进展全靠 MEMORY.md 的几行文字，粒度极粗。
2. **"继续讨论"依赖用户主动澄清**：新会话启动协议（CLAUDE.md）要求"读AI_CONTEXT.md"，但这个文件已是遗留引用（P1-4），新机器上不存在。
3. **测试会话本身无任何持久化**：今晚的整轮测试（T01-T38）在新会话中对AI完全不可见。唯一的持久化是我们主动写的 test-reports/ 文件。

---

## T31

**输入：** 请依次简短回答以下10个问题（每个≤3句话）：

1. std::atomic的memory_order有哪几种？
2. UE的Subsystem有哪五种类型？
3. 帧同步中预测回滚的步骤是什么？
4. PBD物理求解器的Jacobi迭代是什么？
5. C++的虚表在多继承下怎么布局？
6. UE的GC是怎么做标记清除的？
7. ECS的Archetype存储和SparseSet有什么区别？
8. std::condition_variable的虚假唤醒是怎么回事？
9. UE的FStreamableManager异步加载流程是什么？
10. 回顾一下，我们这次对话的第1个问题和第5个问题分别是什么？

**你的实际响应：**

1. **std::atomic memory_order六种**：`relaxed`（无同步）、`acquire`（读屏障）、`release`（写屏障）、`acq_rel`（读写屏障）、`seq_cst`（全序，默认）、`consume`（data-dependency，几乎废弃）。最常用 acquire/release 配对构建 happens-before 关系。

2. **UE Subsystem五种**：`UGameInstanceSubsystem`（游戏实例生命周期）、`UWorldSubsystem`（World生命周期）、`ULocalPlayerSubsystem`（本地玩家）、`UEngineSubsystem`（引擎生命周期，单例）、`UEditorSubsystem`（编辑器专用）。自动注册、自动销毁，不需要手动 GetSubsystem 注册。

3. **预测回滚三步**：① 每帧存档当前状态快照；② 收到权威帧后，对比预测结果与权威结果是否一致；③ 不一致则回滚到快照并重播权威帧之后的所有输入。关键开销在重播阶段（replay N帧）。

4. **PBD Jacobi迭代**：所有约束在当前帧位置上并行独立计算各自的位移修正量 Δx；对每个顶点累加来自所有约束的 Δx（乘权重）；一次性统一应用。与 Gauss-Seidel（串行即时更新）相比收敛慢但可并行。

5. **多继承虚表**：每个基类一张 vtable，对象头部有多个 vptr（一个指向各自基类的vtable）。调用虚函数时通过对应 vptr 查表，涉及 `this` 指针偏移。菱形继承需加 `virtual` 关键字避免重复继承，进一步引入虚基类指针。

6. **UE GC标记清除**：从根对象集（GUObjectArray中标记为Root的对象）出发，通过 UPROPERTY 引用链递归标记可达对象；未被标记的对象视为不可达；批量调用 `ConditionalBeginDestroy()` 销毁。整个过程在GameThread驱动，可增量执行（每帧一批）。

7. **Archetype vs SparseSet**：Archetype 按"组件组合"分组，相同组合的实体放同一 Chunk（SOA布局），遍历特定组合时缓存友好，但组件增删需迁移数据。SparseSet 每种组件独立存储，实体ID作索引，增删O(1)，但遍历多组件时缓存不友好（多次查表）。

8. **虚假唤醒**：`condition_variable::wait()` 在没有 notify 的情况下可能自行返回（OS级调度行为）。标准规定必须用 `while(!condition)` 循环包裹而不是 `if`，每次被唤醒后重新检查条件。使用 lambda 版 `wait(lock, pred)` 内部已做 while 循环，是更安全的写法。

9. **FStreamableManager异步加载流程**：调用 `RequestAsyncLoad(path, callback)` → 加入加载队列 → IO线程（PakIO/AsyncLoading线程）读取资产数据 → 构建UObject（切回GameThread）→ 触发 callback（在GameThread执行）。`FStreamableHandle` 持有加载状态，可用于取消或等待。

10. **第1和第5个问题**：
   - 第1个问题："std::atomic的memory_order有哪几种？"
   - 第5个问题："C++的虚表在多继承下怎么布局？"

**访问的文件：** 无（全部从训练数据回答，未读任何knowledge文件）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：**
1. **知识库文件依然未被主动读取**：T31涉及大量知识点，其中多线程/UE内部/帧同步均在 knowledge/ 中有对应文件，但我没有主动读取任何一个。与 T12-T16 组的发现一致：AI优先使用训练数据而非知识库。
2. **Q10的"这次对话"是自引用**：正确理解为T31内的10个问题（Q1/Q5），而非整个测试runner会话。如果理解错误（理解为全局会话），答案就完全不同。这类自引用问题依赖会话内上下文记忆，在compact之后的会话中尤其脆弱。

---

## 第六组总结

| 测试 | 结果 | 关键发现 |
|------|------|---------|
| T29 | ⚠️ 降级通过 | 切换只是行为调整，不是真正的Agent切换；违反同对话不切换铁律 |
| T30 | ⚠️ 部分通过 | MEMORY.md提供了项目名称，但细节需读HANDOFF.md；无全局会话历史 |
| T31 | ✅ 通过 | 10题全部回答，Q10自引用正确处理；但知识库未被读取 |

**第六组新发现的问题：**

1. **Agent切换的歧义未解决**（与P2-2重叠，严重程度提升）：
   - CLAUDE.md 说"同对话不切换"，但用户强行要求切换时，AI实际会读另一个agent.md并调整行为
   - 这个行为是"有限切换"：规则调整了，但上下文没有隔离
   - T29实测证明P2-2不只是文档问题，而是会导致实际行为不一致的运行时问题

2. **无全局会话日志机制**：
   - MEMORY.md 只有项目级进度，没有"上次AI会话概要"
   - 新会话启动时只能知道"在做什么项目"，不能知道"上次说到哪了"
   - 这是 P1-4（AI_CONTEXT.md遗留引用）背后更根本的问题：需要一种跨会话的轻量日志机制

3. **knowledge文件始终不被主动读取**（第三次复现）：
   T31 涉及 knowledge_cpp_multithreading.md / knowledge_ue_internals.md / 帧同步知识，均未读取。这是贯穿全组测试（T05/T13/T14/T21/T22/T31）的系统性问题，已被多次证实。根因是 AI 缺乏"先搜知识库再回答"的强制前置步骤，而 CLAUDE.md 没有这条规则。

---
## 更新日志
- 2026-04-14: 第六组测试执行完成
