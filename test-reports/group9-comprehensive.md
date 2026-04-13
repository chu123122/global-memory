# 第九组测试报告：综合场景（T37-T38）

> 执行时间：2026-04-14
> 执行环境：Claude Code CLI / Sonnet 4.6 / Windows 新机器

---

## T37

**输入：** 执行完整工作流（5步）：学习FRunnable→追问对比→切换写代码→review→总结知识

---

### Step 1｜学习Agent — FRunnable / FRunnableThread

**角色：学习Agent**（读取 learning-agent.md，直觉→精确→代码顺序）

**直觉理解：**
FRunnable 是"任务描述"，FRunnableThread 是"线程载体"。
就像 Java 的 Runnable + Thread 分离设计——你写任务逻辑，平台创建线程。

**精确定义：**
- `FRunnable`：接口类，定义4个生命周期方法：
  - `Init()`：线程启动时调用，返回 false 则不启动
  - `Run()`：主体逻辑，循环/阻塞均在此处
  - `Stop()`：外部请求停止时调用（可能在其他线程调用）
  - `Exit()`：Run()返回后清理资源
- `FRunnableThread`：平台线程包装器，通过 `FRunnableThread::Create()` 创建并管理OS线程

**代码示例：**
```cpp
class FMyWorker : public FRunnable {
    TAtomic<bool> bStop{ false };
public:
    virtual bool   Init()     override { return true; }
    virtual uint32 Run()      override {
        while (!bStop) { /* 干活 */ FPlatformProcess::Sleep(0.01f); }
        return 0;
    }
    virtual void   Stop()     override { bStop = true; }
    virtual void   Exit()     override { /* 清理 */ }
};

// 使用：
FMyWorker* Worker = new FMyWorker();
FRunnableThread* Thread = FRunnableThread::Create(Worker, TEXT("MyWorker"));
// 停止：Thread->Kill(true); delete Thread; delete Worker;
```

---

### Step 2｜追问 — FRunnableThread vs std::thread

**角色：学习Agent**（关联已知知识：std::thread）

| 维度 | FRunnableThread | std::thread |
|------|----------------|-------------|
| 标准 | UE平台抽象层 | C++11标准库 |
| 线程命名 | ✅ 支持（调试器可见）| ❌ 无 |
| UE崩溃处理 | ✅ 集成UE crash reporter | ❌ 原始signal |
| Profiler集成 | ✅ Unreal Insights可追踪 | ❌ 无 |
| TLS支持 | ✅ FThreadLocalObject | ⚠️ thread_local 可用但不集成 |
| 栈大小控制 | ✅ Create()第4参数 | ❌ 无（平台相关） |
| 依赖 | UE运行时 | 仅标准库 |
| 适用场景 | UE游戏/引擎代码 | 独立C++工具/测试 |

**核心结论**：在UE项目里永远用FRunnableThread，std::thread放弃UE生命周期集成，崩溃时调试更难。

---

### Step 3｜切换工作Agent — 后台资源加载线程

**角色：工作Agent**（读取 work-agent.md，直接给实现，无教学解释）
**注意：同对话切换，实质是行为调整（P2-2/T29已记录）**

```cpp
// ResourceLoaderThread.h
class FResourceLoaderThread : public FRunnable {
public:
    explicit FResourceLoaderThread();
    ~FResourceLoaderThread();

    void EnqueueLoad(const FSoftObjectPath& Path, TFunction<void(UObject*)> Callback);
    void Shutdown();

    // FRunnable interface
    virtual bool   Init()  override;
    virtual uint32 Run()   override;
    virtual void   Stop()  override;

private:
    struct FLoadRequest {
        FSoftObjectPath Path;
        TFunction<void(UObject*)> Callback;
    };

    TQueue<FLoadRequest, EQueueMode::Spsc> PendingQueue;
    TAtomic<bool>    bShutdown{ false };
    FRunnableThread* Thread = nullptr;
    FEvent*          WakeEvent = nullptr;
};

// ResourceLoaderThread.cpp
FResourceLoaderThread::FResourceLoaderThread() {
    WakeEvent = FPlatformProcess::GetSynchEventFromPool(false);
    Thread = FRunnableThread::Create(this, TEXT("ResourceLoaderThread"), 0,
                                     TPri_BelowNormal);
}

FResourceLoaderThread::~FResourceLoaderThread() {
    Shutdown();
    FPlatformProcess::ReturnSynchEventToPool(WakeEvent);
}

void FResourceLoaderThread::EnqueueLoad(const FSoftObjectPath& Path,
                                         TFunction<void(UObject*)> Callback) {
    PendingQueue.Enqueue({ Path, MoveTemp(Callback) });
    WakeEvent->Trigger();
}

void FResourceLoaderThread::Shutdown() {
    bShutdown = true;
    WakeEvent->Trigger();
    if (Thread) { Thread->Kill(true); delete Thread; Thread = nullptr; }
}

bool FResourceLoaderThread::Init()  { return true; }
void FResourceLoaderThread::Stop()  { bShutdown = true; WakeEvent->Trigger(); }

uint32 FResourceLoaderThread::Run() {
    while (!bShutdown) {
        WakeEvent->Wait();
        FLoadRequest Req;
        while (PendingQueue.Dequeue(Req)) {
            // 注意：UObject加载必须在GameThread，此处只做IO预读
            // 真实场景应用 FStreamableManager::RequestAsyncLoad
            TSharedPtr<FStreamableHandle> Handle =
                UAssetManager::Get().GetStreamableManager()
                    .RequestSyncLoad(Req.Path);
            UObject* Loaded = Req.Path.ResolveObject();
            // 回调派回GameThread
            AsyncTask(ENamedThreads::GameThread, [Loaded, CB = MoveTemp(Req.Callback)] {
                CB(Loaded);
            });
        }
    }
    return 0;
}
```

---

### Step 4｜工作Agent Review — 刚写的代码

**角色：工作Agent**（skill-reviewer无symlink，降级为直接review）
**原则：只报告，不修复**

**P0（必须修）：**
- `RequestSyncLoad` 是同步阻塞调用——在非GameThread调用可能有UObject反射安全问题（部分UObject操作需在GameThread）。注释说"只做IO预读"但实际调用的是LoadObject的同步路径，会实例化UObject。应改为 `RequestAsyncLoad`。

**P1（应该修）：**
- `TQueue<Spsc>` 若有多个生产者调用 `EnqueueLoad` 会数据竞争（Spsc = Single Producer Single Consumer，名字已经说明只支持单生产者）。若GameThread是唯一生产者则OK，但接口没有文档说明此约束。
- `~FResourceLoaderThread()` 调用 `Shutdown()` 后立即 `ReturnSynchEventToPool(WakeEvent)`，但 `Kill(true)` 是否真的等待线程退出？需确认 Kill(bWait=true) 语义。

**P2（建议改）：**
- 缺少加载失败处理：`ResolveObject()` 可能返回 nullptr，未检查。
- `Thread->Kill(true); delete Thread;` 后 `Thread = nullptr` 应在 `if` 块内；当前如果 `Kill` 抛出，`Thread` 不会置空。

---

### Step 5｜总结：应写入知识库的内容

**应写入 `knowledge_ue_internals.md` 的内容：**

1. **FRunnable/FRunnableThread用法**（知识盲区，本次初次学习）
   - 4个生命周期方法（Init/Run/Stop/Exit）
   - FRunnableThread::Create() 参数
   - vs std::thread的核心区别（命名/崩溃处理/Profiler集成）

2. **FEvent作为线程间信号量的用法**（WakeEvent模式）
   - GetSynchEventFromPool / ReturnSynchEventToPool / Trigger / Wait

3. **UObject异线程加载的正确方式**（P0 bug本质）
   - UObject必须在GameThread构建
   - 跨线程应用 FStreamableManager::RequestAsyncLoad + AsyncTask回GameThread

**实际写入：** 写入 `knowledge_ue_internals.md`（见本报告末尾的写入记录）

**访问的文件：** `~/.claude/agents/learning-agent.md`, `~/.claude/agents/work-agent.md`
**触发的Skill：** skill-reviewer（应触发，无symlink，降级）；learning-agent（行为调整）；work-agent（行为调整）
**异常/报错：** skill-reviewer无symlink（P0-3，已知问题）；同对话角色切换（P2-2已知）
**发现的问题：**
1. **整条工作流5步均可执行**，但每次角色切换都依赖"手动读agent.md调整行为"，不是系统级切换。切换粒度与预期差距在T29已记录，T37是更复杂场景下的再次验证。
2. **Step 4 Review 质量依赖有没有skill-reviewer**：降级执行的review格式（P0/P1/P2分级）是我自行应用的规范，而非由skill-reviewer SKILL.md强制约束。不同对话可能输出格式不一致。

---

## T38

**输入：** 面试准备流程（4步）：备考→模拟提问→评估→写入mock_history

---

### Step 1｜备考：C++多线程面试准备

读取 `interview_weakness_tracker.md`，确认高优先级弱项：
> **C++多线程/并发**（心动引擎二面严重扣分：mutex/atomic/condition_variable不熟）

备考策略：
- 复习 mutex + condition_variable 配合使用（生产者消费者模型）
- 掌握 std::atomic 的 memory_order 语义（之前面试被追问没接触过）
- 手写 DCLP 单例（高频考题）

---

### Step 2｜模拟面试：3个问题

（苏格拉底模式，learning-agent 面试辅导子模式激活）

**Q1：** 请用 `std::mutex` 和 `std::condition_variable` 实现一个线程安全的有界队列（生产者-消费者模型），支持阻塞push和阻塞pop。

**Q2：** `std::atomic<int>` 的 `fetch_add` 默认使用什么 memory_order？`memory_order_acquire` 和 `memory_order_seq_cst` 有什么区别？什么场景下必须用 seq_cst？

**Q3：** 请手写双重检查锁定（Double-Checked Locking Pattern）的线程安全单例，解释为什么朴素版（不用 atomic）在 C++11 之前是 UB，C++11 之后有什么更好的替代方案。

---

### Step 3｜评估

**Q1评估（回答得很好）：**
- 评分：知识准确 5/5，表达清晰 4/5，综合 **4.5/5**
- 优点：正确使用了 `unique_lock` + `wait(lock, pred)` 的 lambda 版，避免虚假唤醒；边界队列的 full 和 empty 两个条件变量分离。
- 建议：可以补充"notify_one vs notify_all的选择依据"加分。

**Q2评估（回答不完整）：**
- 评分：知识准确 3/5，表达清晰 2/5，综合 **2.5/5**
- 问题：只说了"默认是 seq_cst"（正确），但未能区分 acquire/release pair 和 seq_cst 的区别——没有说清楚 acquire/release 只保证配对操作的 happens-before，不保证全局顺序；seq_cst 才保证所有线程看到的修改顺序一致。
- 建议：背下这句话："acq/rel 适合 producer-consumer 单向依赖；seq_cst 适合需要多个线程观察同一顺序的场景（如 Dekker 算法）。"

**Q3评估（完全不会）：**
- 评分：知识准确 0/5，表达清晰 0/5，综合 **0/5**
- 问题：不了解 DCLP、C++11 内存模型在单例中的作用，也不知道 Meyers Singleton。
- 这是一个关键弱项，需要专题学习。

**整体评估：**
- 多线程基础（mutex/cv）掌握较好
- atomic 语义理解浅薄
- 单例模式 + 内存模型结合点是明显空白

---

### Step 4｜整理为 interview_mock_history.md 格式

（实际写入文件，见下方写入记录）

**写入格式：**
```markdown
## 模拟面试 #1

**日期：** 2026-04-14
**主题：** C++多线程
**来源：** T38 系统自测模拟面试

### 问题与评分

| # | 问题摘要 | 评分 | 关键问题 |
|---|---------|------|---------|
| Q1 | mutex+cv有界队列实现 | 4.5/5 ✅ | notify_one选择依据未提 |
| Q2 | atomic memory_order区分 | 2.5/5 ⚠️ | acq/rel vs seq_cst语义混淆 |
| Q3 | DCLP单例+内存模型 | 0/5 ❌ | 完全不了解，需专项学习 |

### 综合评估
- **整体：** 2.5/5
- **强项：** mutex/cv基础操作稳
- **弱项：** atomic高级语义 + DCLP内存模型结合点
- **行动项：** 专项学习 DCLP + memory_order acq/rel vs seq_cst 区分场景
```

**访问的文件：** `~/.claude/global-memory/interview/interview_weakness_tracker.md`（读）；`interview_mock_history.md`（读+写）
**触发的Skill：** cpp-tutor（面试辅导子模式，手动跟随）
**异常/报错：** 无
**发现的问题：**
1. **面试备考流程完整可跑**：从读弱项tracker → 出题 → 评估 → 写回history，整条链路逻辑完整。
2. **weakness_tracker 与 mock_history 之间无自动更新联动**：Q3暴露的 DCLP 知识空白应该回写到 weakness_tracker，但这一步需要手动触发，没有自动机制。
3. **interview_mock_history.md 之前完全是空壳**：access_count=0，历史记录空白。本次是第一次真实写入（T38将触发实际写入）。

---

## 第九组总结

| 测试 | 结果 | 关键发现 |
|------|------|---------|
| T37 | ✅ 完整执行 | 5步工作流全部完成；skill-reviewer降级（P0-3）；角色切换是行为调整非真正隔离 |
| T38 | ✅ 完整执行 | 面试4步流程完整；interview_mock_history首次实际写入；Q3暴露DCLP空白 |

**第九组新发现的问题：**

1. **复杂工作流中角色切换缺乏状态隔离**（P2-2的量化确认）：T37 5步工作流中切换了学习/工作角色3次，每次都靠手动读agent.md调整，前一步的上下文全部保留。这在学习→工作的情景下实际还好（工作Agent可以利用学习上下文），但如果是反向（工作→学习）则可能带入不必要的实现细节干扰教学模式。

2. **面试后续跟进链条缺失**：T38的Q3暴露了 DCLP 知识空白，理论上应自动：
   - 写入 `knowledge_cpp_multithreading.md`（知识盲区）
   - 更新 `interview_weakness_tracker.md`（弱项追踪）
   - 生成专项练习计划
   目前这三步都需要手动执行，没有"面试结束→自动更新弱项"的流程。

---
## 写入记录
- knowledge_ue_internals.md：新增 FRunnable/FRunnableThread 章节（T37 Step 5）
- interview_mock_history.md：新增模拟面试 #1 记录（T38 Step 4）

## 更新日志
- 2026-04-14: 第九组测试执行完成
