---
name: knowledge-ue-internals
description: UE 引擎底层知识，包括 TaskGraph/线程模型/UObject/Pak VFS
summary: "实习经验(Pak/模块依赖/资源管线/Git工具链)已记录；源码/线程模型/UObject待学"
type: knowledge
created: 2026-04-01
updated: 2026-04-20
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

## 线程编程（FRunnable / FRunnableThread）

### FRunnable/FRunnableThread 用法（2026-04-14 T37写入，初次学习）
- `FRunnable`：任务接口，4个生命周期：Init()/Run()/Stop()/Exit()
- `FRunnableThread`：平台线程包装，`FRunnableThread::Create(runnable, name, stackSize, priority)`
- 停止线程：`bStop = true` → `Thread->Kill(true)` → `delete Thread; delete Worker`

### FRunnableThread vs std::thread
- FRunnableThread 支持：线程命名（调试器可见）、UE崩溃处理集成、Unreal Insights Profiler追踪、栈大小控制
- std::thread 无上述集成，在UE项目中应始终用FRunnableThread

### FEvent 线程间信号量模式
- `FPlatformProcess::GetSynchEventFromPool(false)` 获取事件
- `WakeEvent->Trigger()` 唤醒等待线程
- `WakeEvent->Wait()` 阻塞等待
- `ReturnSynchEventToPool(WakeEvent)` 归还池

### UObject 跨线程加载约束
- UObject 必须在 GameThread 构建（反射/GC要求）
- 跨线程加载正确姿势：`FStreamableManager::RequestAsyncLoad` + `AsyncTask(ENamedThreads::GameThread, callback)`
- 不要在工作线程调用 `RequestSyncLoad`（会在工作线程实例化UObject，违反线程安全约束）

## 和面试的关联
- FPakPlatformFile → VFS 设计 → 面试聊引擎底层的入口
- 模块依赖 → UBT 编译系统 → 面试聊工程架构

---

## UE 智能指针 / RAII 包装（2026-04-20 心动 XDAdaptivePerformance 重构期写入）

### TUniquePtr / TSharedPtr / TSharedRef 三件套
- `MakeUnique<T>(...)` → `TUniquePtr<T>`，独占所有权，对应 std::make_unique
- `MakeShared<T>(...)` → `TSharedRef<T>`（能隐式转 TSharedPtr），引用计数共享
- `MakeShareable(new T(...))` 是历史写法：两次分配（new + 控制块），**首选 MakeShared**（一次分配 + 异常安全）
- `TWeakPtr<T>` 弱引用，打破循环
- **铁律**：上面三种**只能管非 UObject**。UObject 用 `UPROPERTY` + `TWeakObjectPtr` / `TObjectPtr`，靠 GC 不靠 RAII

### FAutoConsoleCommand —— RAII 自注册命令
- 位置：`Engine/Source/Runtime/Core/Public/HAL/IConsoleManager.h`
- 构造时自动 `RegisterConsoleCommand`，析构时自动 `UnregisterConsoleObject`
- **必须用成员变量持有**（栈对象一出作用域就注销）：`TSharedPtr<FAutoConsoleCommand> Cmd;`
- Lambda 接收的参数类型由 delegate 类型决定：
  - `FConsoleCommandDelegate` → `[](){}`
  - `FConsoleCommandWithArgsDelegate` → `[](const TArray<FString>& Args){}`
  - `FConsoleCommandWithWorldDelegate` → `[](UWorld*){}`
  - `FConsoleCommandWithOutputDeviceDelegate` → `[](FOutputDevice& Ar){}`

### UE_NONCOPYABLE(T) 宏
- 展开 = delete 拷贝构造 + 拷贝赋值 + 移动构造 + 移动赋值
- 用途：类内含子线程 / 唯一资源 / handle 时防止意外被拷贝导致 UAF
- 副作用：禁了 move 后**不能塞 TArray 等容器**，只能用 TUniquePtr/TSharedPtr/裸成员持有

## UE 类型命名前缀完整表（2026-04-20 写入）

| 前缀 | 含义 | 例 | GC | 反射 |
|---|---|---|---|---|
| `U` | UObject 派生 | `UTexture2D` | ✅ | ✅ |
| `A` | Actor 派生（UObject 子集） | `ACharacter` | ✅ | ✅ |
| `F` | 普通 C++ 类/结构体（非 UObject） | `FVector`、`FString` | ❌ | 🟡 仅 USTRUCT |
| `U`（接口） | UInterface 反射壳 | `UMyInterface` | ✅ | ✅ |
| `I` | UInterface C++ 实现接口 | `IMyInterface`（**真正写代码用这个**） | ❌ | ❌ |
| `E` | enum / enum class | `EThermalStatus` | — | 🟡 仅 UENUM |
| `T` | 模板类 | `TArray`、`TUniquePtr` | — | — |
| `S` | Slate widget（纯 C++ UI） | `SButton`、`SOverlay` | ❌ | ❌ |
| `b` | bool 变量（不是类型，是变量名前缀） | `bIsValid`、`bUseUmg` | — | — |

**核心心智**：前缀对应**完全不同的内存模型**。`U*` = heap + GC + 必须 UPROPERTY 防 GC；`F*` = 普通值类型，自己管生命周期。
**易混淆**：U 接口（`UMyInterface`）只是反射壳，`Cast<>` 时用的是 `IMyInterface`。

## UE 模块 Public/Private 目录的真正语义（2026-04-20 写入）

**不是 .h/.cpp 分开**，是 **API 跨模块可见性**：

| 目录 | 谁能 #include | 谁能用符号 |
|---|---|---|
| `Public/Foo.h` | 本模块 + **所有依赖本模块的模块** | 同上 |
| `Private/Foo.h` | **只有本模块** | 只有本模块 |
| `Private/Foo.cpp` | 一般不直接 include | — |

**关键**：`.h` 可以放任一边，决定标准 = "这个类是否给别的模块用"。
**放错代价**：
- 内部类放 Public/ → 编译时间膨胀（依赖方扫所有 Public 头）+ 无意中暴露 API → 重构时怕破坏外部
- 公开 API 放 Private/ → 其他模块编译失败
- Public 类要给跨模块用必须 `MODULENAME_API` 导出宏，否则 link 失败

**判定**：grep 看本类是否被其他模块 include。0 命中 → 放 Private。

---

## 心动 XD 引擎源码精读路线（2026-04-24 写入）

> 详细路线图：`D:/docs/engine-source-reading-roadmap.md`
> 全貌图：`D:/docs/engine-panorama-report.md`

### 关键定位规则
- **源码根**：`C:\Perforce\tl_gaoxinag_01\frontend\trunk\Editor\`（subst → `Z:\`）
- **所有 XD 自定义开关**定义在 C# 配置：`Engine/Source/Programs/UnrealBuildTool/Configuration/XDBuildConfiguration/`，**不在 C++ 头**
- **真实 `#if` 使用**要 grep `Engine/Source/Runtime/...`，**必须排除 `Intermediate/`/`Build/`/`.Rider/`**（panorama 报告里的"289 处"包括 PCH，不等于真实源码次数）
- **C# 配置里大多附 Wiki 链接**——作者亲笔设计文档，先读 Wiki 比反推代码快 5 倍

### Topic 1：FParticleLockFreeMemoryPool（已定位，待精读）
- 开关：`XD_OPT_LOCK_FREE_PARTICLE_MEMORY_POOL`（XDBuildOptConfiguration.cs:289）
- 实现核心：`Engine/Source/Runtime/Engine/Private/Particles/ParticleMemoryPool.cpp`（616 行，Alloc 在 L115，Free 在 L215，PrebuiltBlockSizes 在 L307）
- 接口：`Engine/Source/Runtime/Engine/Public/ParticleMemoryPool.h`（92 行）
- Wiki：xindong.atlassian.net/wiki/spaces/ENUE4/pages/983811634/ParticleLockFreeMemoryPool
- 读完应能回答：lock-free 原语、ABA、size class 策略、HasInit() 生命周期

### 教训
panorama 统计 `XD_OPT_PARTICLE_INSTANCE_MULTI_THREAD_FILL_DATA` 84 处，但 grep `Engine/Source/` 真实 `.cpp/.h` **零命中**——只在 C# 定义文件出现。说明 panorama 的次数统计扫了 PCH/Intermediate，**不等于真实使用**。下次定位前先排除构建产物。

---

## UE Module 系统 / LoadingPhase（2026-04-28 学习写入）

### IMPLEMENT_MODULE 宏的真实作用
- 生成 C 风格导出函数 `InitializeModule`，UE 通过 `LoadLibrary` + `GetProcAddress`（或 dlsym）找它构造模块对象
- **缺这一行**：编译/链接都过，dll 加载也过，但 `FModuleManager` 找不到入口符号 → 报 "Module 'X' could not be loaded" → StartupModule 永远不会被调
- 注意：UE **能扫到 .uplugin**（知道插件存在），找不到的是模块**怎么实例化**

### LoadingPhase 选错的双向口诀 ⚡（2026-04-28 答错盲区）
> **太早 → 我依赖的没就绪；太晚 → 我的客户已经过期。**

| LoadingPhase 情况 | 谁的问题 | 典型现象 |
|---|---|---|
| 太早（如 `EarliestPossible`） | **我依赖的子系统**还没起 | GConfig=nullptr 读 ini 崩；FCoreDelegates 全局对象未构造；UE_LOG 默默丢弃 |
| 太晚（如 `Default` 之后） | **我的客户**已经在调我 | 业务侧调 BPLib API 拿到 NotAvailable；OnPostEngineInit 已广播完，注册了也收不到 |

**`PreDefault` 是延迟初始化插件的甜蜜点**：Config/Log/委托都 ready（解决"太早"），业务模块还没开始调（解决"太晚"）。

**XDAdaptivePerformance 选 PreDefault** 即此原因。本插件依赖 GConfig 读 DeviceProfiler.ini + 注册 OnPostEngineInit 等 RHI/JNI 就绪。

### StartupModule vs 析构函数（清理逻辑写哪）
- **ShutdownModule**：UE 主动调，引擎其他子系统**还活着**——委托反注册、`InitFuture.WaitFor` 阻塞等子线程、`Widget->RemoveFromRoot()` UObject 释放、`FTicker::RemoveTicker` 都写这里
- **析构函数**：跑得更晚一拍，子系统状态不保证——FCoreDelegates 可能已析构 / TaskGraph 可能已 teardown / GC 可能已停
- **规则**：依赖引擎子系统的清理 → ShutdownModule；纯 RAII 内存清理 → 默认析构（`= default`）即可
- **本插件**：`~FXDAdaptivePerformanceModule() = default`，所有真清理在 ShutdownModule

### 学习地图入口
- 时序图：`D:/ClaudeTasks/active/xd-adaptive-performance-refactor/LEARNING-ENGINE-MAP.md` §二
- 真代码：`Editor/UE_game/Plugins/XDAdaptivePerformance/Source/XDAdaptivePerformance/Private/XDAdaptivePerformance.cpp:519/726/1072`
- .uplugin：同插件目录下，`"LoadingPhase": "PreDefault"`

---
## 更新日志
- 2026-04-01: 初始创建，迁移 my-learning-agent 中的实习经验
- 2026-04-20: 加 UE 智能指针 / FAutoConsoleCommand / 命名前缀完整表 / Public-Private 目录语义（来自心动 XDAdaptivePerformance 重构期讨论）
- 2026-04-24: 加心动 XD 引擎源码精读路线（Topic 1 ParticleLockFreeMemoryPool 已定位）
- 2026-04-28: 加 Module 系统 / LoadingPhase 双向口诀（学习地图第 1 节，Q2 答错盲区记录）
