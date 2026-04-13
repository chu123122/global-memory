# UE 多线程资源加载插件 · 技术预研文档

> 版本：v1.0 | 日期：2026-04-13
> 用途：入职心动引擎中台前的方案预研，入职后作为实际设计方案的起点
> 作者：高翔

---

## 一、需求分析

### 1.1 问题定义

UE 默认的资源加载在大型开放世界/关卡切换场景下存在以下痛点：

| 问题 | 表现 | 影响 |
|------|------|------|
| 主线程阻塞 | `LoadObject`/`StaticLoadObject` 同步加载时阻塞 GameThread | 帧率骤降/卡顿 |
| 加载优先级缺失 | 所有异步请求平等排队，无法区分"玩家视野内"和"预加载" | 玩家可见区域加载慢 |
| 取消机制不完善 | 场景切换时无法批量取消上一场景的加载请求 | 内存浪费、带宽竞争 |
| 状态查询不便 | 调用方难以获取精确的加载进度和失败原因 | 难以做 Loading 界面和错误恢复 |

### 1.2 典型使用场景

```
场景1：流式加载（Streaming）
  玩家在开放世界中移动 → 预测前方区域 → 按距离优先级异步加载
  → 加载完成后无缝替换 LOD → 玩家离开后卸载

场景2：场景切换
  触发切换 → 显示 Loading UI → 批量异步加载新场景资源
  → 进度回调更新 Loading Bar → 全部完成后隐藏 UI

场景3：预加载（Warm-up）
  主菜单期间后台低优先级加载可能用到的资源
  → 进入战斗时资源已在内存中 → 减少首次卡顿

场景4：热更新资源加载
  下载完补丁包 → 异步加载替换资源 → 不打断当前游戏
```

### 1.3 设计目标

| 目标 | 指标 |
|------|------|
| 主线程零阻塞 | 加载请求提交 < 0.01ms，主线程只做调度和回调 |
| 优先级调度 | 至少 4 级优先级（Critical / High / Normal / Low） |
| 可取消 | 支持单个取消和按 Group 批量取消 |
| 进度查询 | 精确到百分比，支持 Poll 和 Callback 两种模式 |
| 错误恢复 | 加载失败时自动重试（可配次数），超过后回调通知 |
| 帧率友好 | 主线程每帧处理回调的时间可配（Budget 机制） |

---

## 二、UE 现有方案调研

### 2.1 FStreamableManager

```cpp
// 最常用的异步加载接口
FStreamableManager& Manager = UAssetManager::GetStreamableManager();
TSharedPtr<FStreamableHandle> Handle = Manager.RequestAsyncLoad(
    SoftObjectPath,
    FStreamableDelegate::CreateLambda([](){ /* 完成回调 */ }),
    FAsyncLoadPriority::Normal
);
```

**内部流程：**
```
RequestAsyncLoad()
  → 创建 FStreamableHandle
  → 调用 FAssetManager::LoadAssetList()
    → 对每个资源创建 FAsyncPackage
      → 进入 FAsyncLoadingThread 的请求队列
        → IO线程读取文件
        → 序列化线程反序列化
        → GameThread 上执行 PostLoad
  → Handle 状态变为 Completed
  → 触发 Delegate 回调
```

**优点：**
- UE 原生，与 AssetManager 集成良好
- 支持 SoftObjectPath，可在蓝图中使用
- Handle 支持 Cancel 和 IsActive 查询

**缺点：**
- 优先级只是 int 值，没有抢占/动态调整机制
- 回调固定在 GameThread 上，大量资源同时完成时会造成帧率毛刺
- 缺乏 Group 概念和批量操作
- 进度只有 "加载中/完成"，没有百分比

### 2.2 AsyncLoadObject / LoadPackageAsync

```cpp
// 底层接口
LoadPackageAsync(
    PackageName,
    FLoadPackageAsyncDelegate::CreateLambda(
        [](const FName& PackageName, UPackage* Package, EAsyncLoadingResult::Type Result){
            // 完成回调
        }
    ),
    0,              // PackageFlags
    PKG_ContainsMap // PackagePriority
);
```

**内部架构：**
```
FAsyncLoadingThread（独立线程）
├── RequestQueue（请求队列，线程安全）
├── AsyncPackages（正在处理的包列表）
├── EventQueue（发往 GameThread 的事件队列）
└── 工作流程：
    1. 从 RequestQueue 取出请求
    2. 创建 FAsyncPackage
    3. 按依赖关系排序
    4. 分 Tick 步骤执行：
       - CreateLinker → FinishLinker → CreateImports
       - CreateExports → PreLoadObjects → PostLoadObjects
       - FinishObjects → CallCompletionCallbacks
    5. 每步限时，超时则暂停到下一 Tick
```

**关键发现：**
- UE 的异步加载本质上是**协作式多任务**，不是真正的并行
- `FAsyncLoadingThread` 是单线程的，瓶颈在序列化（CPU bound）
- IO 部分走 `FIOSystem`，可以异步，但序列化不行
- `EDL`（Event Driven Loader，UE5）改善了这个问题，支持更细粒度的并行

### 2.3 TaskGraph 在资源加载中的应用

```
UE5 的 EDL（Event Driven Loader）架构：

        ┌─────────────┐
        │  GameThread  │  ← 只做 PostLoad 和回调
        └──────┬───────┘
               │ 事件通知
        ┌──────┴───────┐
        │  AsyncThread │  ← 协调加载流程
        └──────┬───────┘
               │ 创建 Task
        ┌──────┴───────┐
        │  TaskGraph   │  ← 真正的并行序列化
        │  ├─ Task A   │    （FAsyncPackage 的各阶段
        │  ├─ Task B   │     被拆成独立 Task，
        │  └─ Task C   │     依赖关系用 DAG 表达）
        └──────┬───────┘
               │ IO 请求
        ┌──────┴───────┐
        │  IO Service  │  ← 异步文件读取
        └──────────────┘
```

**关键类：**
- `FAsyncLoadingThread2`：EDL 的核心调度器
- `FEventLoadGraph`：加载事件的 DAG 图
- `FAsyncPackage2`：EDL 版本的异步包
- `FIoDispatcher`：IO 调度器（UE5 新增，替代旧的 FIOSystem）

### 2.4 现有方案对比

| 维度 | FStreamableManager | LoadPackageAsync | EDL (UE5) |
|------|:------------------:|:----------------:|:---------:|
| 易用性 | ⭐⭐⭐ | ⭐⭐ | ⭐ (内部API) |
| 并行度 | 低（单线程序列化） | 低 | 高（TaskGraph） |
| 优先级 | int 值，无抢占 | 同 | 有改善但不完善 |
| 取消 | Handle.Cancel() | 不方便 | 更好 |
| 进度 | 无百分比 | 无 | 有改善 |
| 帧率友好 | 一般 | 差 | 好（Budget 机制） |

---

## 三、设计方案

### 3.1 方案 A：独立 IO 线程 + 消息队列

```
架构：

GameThread                     IO Thread Pool
┌──────────────┐              ┌──────────────────┐
│ AsyncLoader  │  Request Q   │  IOWorker × N    │
│ (调度器)     │ ──────────→  │  ├─ ReadFile     │
│              │              │  ├─ Deserialize   │
│ Tick():      │  ←────────── │  └─ PostResult    │
│  处理完成队列 │  Complete Q  │                    │
│  触发回调    │              └──────────────────┘
└──────────────┘

优先级队列（堆结构）管理请求排序。
```

```cpp
// 核心接口
class FAsyncResourceLoader
{
public:
    // 提交加载请求
    FLoadHandle RequestLoad(
        const FSoftObjectPath& Path,
        ELoadPriority Priority = ELoadPriority::Normal,
        FOnLoadComplete OnComplete = nullptr,
        FLoadGroup* Group = nullptr
    );

    // 取消
    bool CancelLoad(FLoadHandle Handle);
    void CancelGroup(FLoadGroup* Group);

    // 查询
    ELoadStatus GetStatus(FLoadHandle Handle) const;
    float GetProgress(FLoadHandle Handle) const; // 0.0 ~ 1.0

    // 主线程每帧调用，处理完成回调
    void Tick(float DeltaTime, float BudgetMs = 2.0f);

private:
    TPriorityQueue<FLoadRequest> PendingQueue;     // 优先级队列
    TMap<FLoadHandle, FLoadRequest> ActiveRequests; // 活跃请求
    TQueue<FLoadResult, EQueueMode::Mpsc> CompletionQueue; // 完成队列（多生产者单消费者）
    FThreadPool IOThreadPool;                       // IO 线程池
};
```

**优点：**
- 架构简单直观，容易理解和调试
- IO 线程池大小可配，并行度可控
- MPSC 队列保证线程安全且无锁

**缺点：**
- 需要自己管理线程池，不复用 UE 的 TaskGraph
- 序列化部分如果在 IO 线程做，可能和 UE 的 GC 冲突（UObject 创建必须在 GameThread）
- 与 UE 内部的加载系统隔离，无法利用 UE 的缓存和引用管理

### 3.2 方案 B：基于 TaskGraph + 优先级扩展

```
架构：

GameThread
┌──────────────┐
│ AsyncLoader  │
│ (调度器)     │
│              │──→ FGraphEvent (CreateTask)
│ Tick():      │         │
│  收集完成    │    TaskGraph Worker Threads
│  触发回调    │    ┌─────────────────────┐
└──────────────┘    │ LoadTask_IO         │ ← 文件读取
                    │   → LoadTask_Parse  │ ← 解析/反序列化
                    │     → LoadTask_Init │ ← UObject 初始化（转 GT）
                    └─────────────────────┘
```

```cpp
// 利用 UE TaskGraph
class FAsyncResourceLoader
{
public:
    FLoadHandle RequestLoad(const FSoftObjectPath& Path, ELoadPriority Priority, ...);

private:
    void CreateLoadTasks(FLoadRequest& Request)
    {
        // Phase 1: IO (在 AnyBackgroundThreadNormalTask)
        FGraphEventRef IOEvent = FFunctionGraphTask::CreateAndDispatchWhenReady(
            [&Request](){
                Request.RawData = FFileHelper::LoadFileToArray(Request.Path);
            },
            TStatId(), nullptr, ENamedThreads::AnyBackgroundThreadNormalTask
        );

        // Phase 2: Parse (依赖 IO 完成)
        FGraphEventRef ParseEvent = FFunctionGraphTask::CreateAndDispatchWhenReady(
            [&Request](){
                Request.ParsedData = ParseAssetData(Request.RawData);
            },
            TStatId(), IOEvent, ENamedThreads::AnyBackgroundThreadNormalTask
        );

        // Phase 3: Init UObject (必须在 GameThread)
        FFunctionGraphTask::CreateAndDispatchWhenReady(
            [&Request](){
                Request.Object = CreateUObject(Request.ParsedData);
                CompletionQueue.Enqueue(Request);
            },
            TStatId(), ParseEvent, ENamedThreads::GameThread
        );
    }
};
```

**优点：**
- 复用 UE 的线程池，不引入新线程
- 任务依赖用 DAG 表达，天然支持复杂的加载依赖链
- 与 UE 的其他 TaskGraph 任务共享线程，资源利用率高

**缺点：**
- TaskGraph 的优先级控制有限（只有 Normal/High/Background）
- UObject 创建强制回 GameThread，限制了真正的并行度
- TaskGraph 不支持动态取消已调度的 Task

### 3.3 方案 C：Wrapper 模式（推荐）

**核心思路：不替代 UE 的加载系统，而是在上层做调度增强。**

```
架构：

GameThread
┌─────────────────────────┐
│   FSmartResourceLoader  │  ← 我们写的调度层
│   ├─ PriorityScheduler  │  ← 优先级队列 + 动态调整
│   ├─ GroupManager       │  ← Group 生命周期管理
│   ├─ BudgetController   │  ← 每帧回调时间控制
│   └─ StatusTracker      │  ← 状态/进度/错误追踪
│                         │
│   Tick() 每帧：          │
│   1. 按 Budget 提交新请求│
│   2. 收集完成回调        │
│   3. 触发用户回调        │
└────────────┬────────────┘
             │ 内部调用
    ┌────────┴────────┐
    │ UE 原生加载系统  │  ← FStreamableManager / LoadPackageAsync
    │ (不修改)         │
    └─────────────────┘
```

```cpp
class FSmartResourceLoader : public FTickableGameObject
{
public:
    struct FLoadConfig
    {
        ELoadPriority Priority = ELoadPriority::Normal;
        FName Group = NAME_None;
        int32 MaxRetries = 2;
        float TimeoutSeconds = 30.f;
    };

    // ─── 核心接口 ───
    FLoadHandle RequestLoad(
        const FSoftObjectPath& Path,
        const FLoadConfig& Config = {},
        FOnLoadComplete OnComplete = nullptr
    );

    FLoadHandle RequestBatchLoad(
        const TArray<FSoftObjectPath>& Paths,
        const FLoadConfig& Config = {},
        FOnBatchLoadComplete OnComplete = nullptr
    );

    bool Cancel(FLoadHandle Handle);
    void CancelGroup(FName Group);

    ELoadStatus GetStatus(FLoadHandle Handle) const;
    float GetProgress(FLoadHandle Handle) const;

    // ─── 配置 ───
    void SetFrameBudgetMs(float Ms);           // 默认 2.0ms
    void SetMaxConcurrentLoads(int32 Count);   // 默认 8
    void SetPriority(FLoadHandle Handle, ELoadPriority NewPriority); // 动态调整

    // ─── FTickableGameObject ───
    virtual void Tick(float DeltaTime) override;

private:
    // 调度层
    struct FPendingRequest
    {
        FLoadHandle Handle;
        FSoftObjectPath Path;
        FLoadConfig Config;
        FOnLoadComplete Callback;
        float SubmitTime;
        int32 RetryCount = 0;
    };

    TPriorityQueue<FPendingRequest> WaitingQueue;     // 等待调度
    TMap<FLoadHandle, FActiveLoad> ActiveLoads;        // 正在加载
    TMap<FName, TArray<FLoadHandle>> GroupMap;          // Group → Handles
    FStreamableManager& StreamableManager;              // UE 原生管理器

    int32 MaxConcurrent = 8;
    float FrameBudgetMs = 2.0f;
    FLoadHandle NextHandle = 1;
};
```

**优点：**
- **零侵入**：不修改 UE 源码，以 Plugin 形式存在
- **最大兼容**：底层复用 UE 的缓存/引用计数/GC 集成
- **调度增强**：在 UE 之上补全优先级/Group/Budget/重试/超时
- **风险最低**：出问题随时降级到直接调 FStreamableManager

**缺点：**
- 不能突破 UE 底层加载系统的性能上限
- 优先级调整只能控制"何时提交"，不能控制"UE 内部的调度顺序"
- 两层状态（我们的 + UE 的）需要仔细同步

### 3.4 方案对比

| 维度 | A: IO线程池 | B: TaskGraph | C: Wrapper（推荐） |
|------|:----------:|:----------:|:------------------:|
| 侵入性 | 高（绕过 UE 加载） | 中 | **低（纯上层）** |
| 实现复杂度 | 高 | 中 | **低** |
| 与 UE 兼容性 | 差（GC 冲突风险） | 好 | **最好** |
| 优先级控制 | 完全自主 | 有限 | 调度层自主 |
| 并行度上限 | 高 | 中 | 受限于 UE 底层 |
| 出错风险 | 高 | 中 | **低** |
| 适合场景 | 完全自研引擎 | 深度定制 UE | **引擎中台插件** |

**推荐方案 C**。原因：
1. 你是实习生/新人，零侵入方案出错风险最低
2. 引擎中台的需求是"增强"而非"替代"
3. 方案 C 留了退路——如果后续需要更深度的控制，可以逐步把底层替换为 B

---

## 四、关键技术难点

### 4.1 线程安全

**难点：主线程和 UE 异步加载线程之间的数据同步**

```cpp
// 问题场景：GameThread 取消请求时，UE 内部可能正在加载

// 解决方案：状态机 + 原子操作
enum class EInternalState : uint8
{
    Pending,    // 在 WaitingQueue 中，可安全移除
    Submitted,  // 已提交给 UE，需要等 UE 回调后再清理
    Completing, // UE 回调已触发，等待 Tick 处理
    Completed,  // 已完成
    Cancelled,  // 已取消（但 UE 内部可能还在加载）
    Failed      // 失败
};

// 取消逻辑
bool Cancel(FLoadHandle Handle)
{
    if (auto* Pending = WaitingQueue.Find(Handle))
    {
        // 还没提交给 UE，直接移除
        WaitingQueue.Remove(Handle);
        return true;
    }
    if (auto* Active = ActiveLoads.Find(Handle))
    {
        // 已提交给 UE，标记为取消
        // UE 回调时检查标记，跳过用户回调
        Active->State = EInternalState::Cancelled;
        Active->StreamableHandle->CancelHandle();
        return true;
    }
    return false; // 已完成或不存在
}
```

### 4.2 优先级反转

**难点：高优先级请求排在低优先级之后提交**

```cpp
// 解决方案：Budget 机制 + 优先级抢占
void Tick(float DeltaTime)
{
    double StartTime = FPlatformTime::Seconds();
    double BudgetEnd = StartTime + FrameBudgetMs * 0.001;

    // 1. 先处理完成队列（不受 Budget 限制）
    ProcessCompletions();

    // 2. 检查是否有高优先级请求需要"抢占"
    //    如果 ActiveLoads 满了但 WaitingQueue 顶部是 Critical，
    //    取消一个 Low 优先级的活跃加载
    if (ActiveLoads.Num() >= MaxConcurrent && !WaitingQueue.IsEmpty())
    {
        auto& Top = WaitingQueue.Top();
        if (Top.Config.Priority == ELoadPriority::Critical)
        {
            EvictLowestPriority(); // 取消最低优先级的活跃加载
        }
    }

    // 3. 按 Budget 提交新请求
    while (!WaitingQueue.IsEmpty()
           && ActiveLoads.Num() < MaxConcurrent
           && FPlatformTime::Seconds() < BudgetEnd)
    {
        SubmitToUE(WaitingQueue.Pop());
    }
}
```

### 4.3 资源生命周期管理

```
加载完成后资源的引用关系：

FSmartResourceLoader
  └─ FActiveLoad
       └─ TSharedPtr<FStreamableHandle>  ← 持有 UE 的引用
            └─ UObject*                   ← 实际资源

释放流程：
  用户调用 Release(Handle)
  → 移除我们的 Handle 记录
  → FStreamableHandle 析构
  → UE 引用计数减 1
  → 如果引用归零，UE GC 会在合适时机回收
```

**关键原则：**
- 我们只管调度，不直接持有 UObject*
- 让 FStreamableHandle 管理生命周期，与 UE GC 天然兼容
- 提供 `KeepLoaded(Handle)` 接口阻止意外卸载

### 4.4 错误处理与重试

```cpp
void OnUELoadComplete(FLoadHandle Handle, bool bSuccess)
{
    auto* Active = ActiveLoads.Find(Handle);
    if (!Active) return;

    if (Active->State == EInternalState::Cancelled)
    {
        // 用户已取消，静默丢弃
        ActiveLoads.Remove(Handle);
        return;
    }

    if (!bSuccess)
    {
        if (Active->RetryCount < Active->Config.MaxRetries)
        {
            // 重试：放回队列，优先级提升一级
            Active->RetryCount++;
            FPendingRequest Retry = MakePending(*Active);
            Retry.Config.Priority = FMath::Min(
                Retry.Config.Priority + 1, ELoadPriority::Critical);
            WaitingQueue.Push(Retry);
            ActiveLoads.Remove(Handle);
            UE_LOG(LogSmartLoader, Warning,
                TEXT("Retry %d/%d: %s"),
                Active->RetryCount, Active->Config.MaxRetries,
                *Active->Path.ToString());
            return;
        }
        // 重试耗尽
        Active->State = EInternalState::Failed;
    }
    else
    {
        Active->State = EInternalState::Completed;
    }

    // 加入完成队列，等 Tick 时触发回调
    CompletionQueue.Enqueue({Handle, Active->State, Active->Object});
}
```

---

## 五、Plugin 结构设计

```
Plugins/SmartResourceLoader/
├── SmartResourceLoader.uplugin
├── Source/
│   ├── SmartResourceLoader/
│   │   ├── Public/
│   │   │   ├── SmartResourceLoader.h         // 模块定义
│   │   │   ├── SmartResourceLoaderSubsystem.h // UGameInstanceSubsystem
│   │   │   ├── SmartLoadHandle.h             // Handle 类型定义
│   │   │   ├── SmartLoadTypes.h              // 枚举/结构体
│   │   │   └── SmartResourceLoaderBPLibrary.h // 蓝图接口
│   │   └── Private/
│   │       ├── SmartResourceLoader.cpp
│   │       ├── SmartResourceLoaderSubsystem.cpp
│   │       ├── SmartLoadScheduler.cpp        // 调度核心
│   │       └── SmartResourceLoaderBPLibrary.cpp
│   └── SmartResourceLoaderTests/             // 自动化测试
│       └── ...
└── Config/
    └── DefaultSmartResourceLoader.ini        // 默认配置
```

**选择 `UGameInstanceSubsystem` 而非全局单例的原因：**
- 生命周期跟随 GameInstance，自动创建/销毁
- 支持 PIE（Play In Editor）多实例
- UE 推荐的 Subsystem 模式，代码更规范

---

## 六、测试方案

### 6.1 单元测试

```cpp
// 基本加载
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSmartLoader_BasicLoad, ...)
bool FSmartLoader_BasicLoad::RunTest(const FString& Params)
{
    auto* Subsystem = GetSubsystem();
    bool bCompleted = false;

    auto Handle = Subsystem->RequestLoad(
        FSoftObjectPath("/Game/Test/TestMesh"),
        {},
        FOnLoadComplete::CreateLambda([&](UObject* Obj, bool bSuccess){
            bCompleted = true;
            TestTrue("Load succeeded", bSuccess);
            TestNotNull("Object valid", Obj);
        })
    );

    // 模拟 Tick 直到完成
    ADD_LATENT_COMMAND(FWaitUntil([&](){ return bCompleted; }, 10.f));
    return true;
}

// 优先级测试
// 取消测试
// 批量加载测试
// 错误重试测试
// Group 取消测试
// Budget 限制测试
```

### 6.2 性能测试指标

| 指标 | 测试方法 | 目标 |
|------|---------|------|
| **请求提交延迟** | 测量 RequestLoad() 耗时 | < 0.01ms |
| **Tick 耗时** | Stat 命令测量 | ≤ Budget 设定值 |
| **吞吐量** | 100 个资源并发加载时间 | ≤ 原生方案 ×1.05 |
| **内存开销** | 调度层自身内存 | < 1MB（1000 个活跃请求） |
| **取消响应** | Cancel 到实际停止的时间 | < 1帧 |

### 6.3 压力测试场景

```
场景 A：瞬间峰值
  1帧内提交 500 个加载请求（模拟场景切换）
  验证：不卡主线程，Queue 正确排序

场景 B：持续流式
  每帧提交 5-10 个，持续 60 秒（模拟开放世界）
  验证：内存稳定，无泄漏

场景 C：频繁取消
  提交后 50% 概率立即取消（模拟快速切场景）
  验证：无悬垂指针，无 UE 内部错误

场景 D：错误恢复
  模拟 20% 加载失败率
  验证：重试机制正常，最终状态正确
```

---

## 七、开发里程碑

| 阶段 | 内容 | 预估时间 |
|------|------|---------|
| M1 | 核心调度器 + 基本 RequestLoad/Cancel/Tick | 1 周 |
| M2 | 优先级队列 + Budget 机制 + Group 管理 | 1 周 |
| M3 | 错误重试 + 超时 + 状态查询 | 3 天 |
| M4 | 蓝图接口 + Subsystem 封装 | 3 天 |
| M5 | 单元测试 + 性能测试 + 压力测试 | 1 周 |
| M6 | 文档 + Code Review + 集成验证 | 3 天 |

**总计：约 4-5 周（实习期间全职）**

---

## 八、面试话术

> **30 秒版**：我在心动引擎中台做了一个多线程资源加载插件，以 UE Plugin 形式实现，核心是在 UE 原生 FStreamableManager 之上做调度增强——优先级队列、Group 批量管理、Budget 帧率控制、自动重试。零侵入设计，方案落地后把场景切换的加载卡顿减少了约 XX%。

> **被追问时的展开点**：
> 1. 为什么选 Wrapper 而非自己实现 IO 线程？→ 兼容性/GC 安全/实习生风险控制
> 2. 优先级反转怎么处理？→ 抢占机制 + 动态优先级调整
> 3. 线程安全怎么保证？→ 状态机 + 原子操作 + UE 的 MPSC 队列
> 4. 和 UE5 EDL 的关系？→ EDL 改善了底层并行，我们的调度层在任何版本都适用
