# UE5 引擎核心模块源码级参考（交叉验证整合版）

> 整合日期：2026-04-13
> 来源：48 篇高质量技术文章交叉验证（详见 resource-links.md）
> 用途：面试准备 + 入职心动引擎中台的源码级参考
> 原则：不同文章矛盾处标注 ⚠️，互补处合并，遗漏处补充

---

## 一、UObject 反射系统

### 1.1 类型继承体系

```
UObjectBase                    ← 最底层：ObjectFlags/InternalIndex/ClassPrivate/NamePrivate/OuterPrivate
  └── UObjectBaseUtility       ← 工具方法层
        └── UObject            ← 用户层基类
              └── UField       ← 反射字段基类（UE5 中部分职责迁移到 FField）
                    ├── UStruct           ← 包含属性链 + 函数链
                    │     ├── UClass      ← 最核心：CDO + ClassConstructor + FuncMap + Interfaces
                    │     ├── UScriptStruct ← USTRUCT 的元数据
                    │     └── UFunction    ← UFUNCTION 的元数据
                    └── UEnum              ← UENUM 的元数据

UE5 重要变化：UProperty → FProperty（不再继承 UObject，减少内存开销）
```

### 1.2 UObjectBase 核心字段

```cpp
class UObjectBase {
    EObjectFlags   ObjectFlags;    // 对象标志位
    int32          InternalIndex;  // GUObjectArray 中的索引
    UClass*        ClassPrivate;   // 指向自身的 UClass
    FName          NamePrivate;    // 对象名（FName 高效比较）
    UObject*       OuterPrivate;   // 外部对象（Package→Level→Actor→Component）
};
```

### 1.3 UClass 关键成员

```cpp
class UClass : public UStruct {
    ClassConstructorType ClassConstructor;          // 构造函数指针
    ClassAddReferencedObjectsType ClassAddReferencedObjects; // GC 引用收集
    EClassFlags         ClassFlags;                // CLASS_Abstract 等
    EClassCastFlags     ClassCastFlags;            // 快速 Cast 标志
    UObject*            ClassDefaultObject;        // CDO
    TArray<FImplementedInterface> Interfaces;
    TMap<FName, UFunction*> FuncMap;               // 函数映射表
};
```

### 1.4 CDO（Class Default Object）机制

```
UClass::GetDefaultObject()
  ├── ClassDefaultObject 已存在 → 直接返回
  └── 否则 → CreateDefaultObject()
                ├── 调用 ClassConstructor 创建对象
                ├── 设置 RF_ClassDefaultObject 标志
                └── PostCDOContruct()

用途：属性默认值存储 / 序列化差异比对 / NewObject 时的属性拷贝源
CDO 创建时机：UClass 注册时（引擎启动阶段）
```

### 1.5 UHT 代码生成流程

```
.h 文件（含 UCLASS/UPROPERTY/UFUNCTION 宏）
    │ UHT 解析
    ▼
.generated.h + .gen.cpp
    │
    ▼
GENERATED_BODY() 展开为：
  ├── friend 声明（允许 UHT 生成代码访问私有成员）
  ├── StaticClass() 静态方法
  ├── Super 类型别名
  └── 序列化/复制辅助函数

.gen.cpp 中生成：
  ├── Z_Construct_UClass_XXX() → 构建 UClass 对象
  ├── 所有 UPROPERTY 的 FProperty 描述（含偏移量 offset）
  ├── 所有 UFUNCTION 的 UFunction 描述
  ├── StaticRegisterNatives → 绑定 Native 函数
  └── FCompiledInDefer 静态实例 → 模块加载时自动注册
```

### 1.6 启动时注册流程

```
引擎启动 → 静态初始化 → FCompiledInDefer 入队
    │
    ▼
ProcessNewlyLoadedUObjects()
    ├── UClassRegisterAllCompiledInClasses() → 遍历 FCompiledInDefer 链表
    │     └── GetPrivateStaticClassBody() → 创建 UClass 并加入全局表
    ├── UObjectProcessRegistrants() → 处理延迟注册队列
    └── UObjectLoadAllCompiledInStructs() → 构造 UScriptStruct/UEnum
```

### 1.7 反射运行时使用

**Cast 机制**：
```cpp
Cast<T>(Src)
  ├── 快速路径：ClassCastFlags 位检查（O(1)）
  └── 慢速路径：遍历继承链 IsA()
```

**函数调用链**：
```
UObject::ProcessEvent(UFunction*, void* Parms)
  ├── Native 函数 → Function->Invoke → execXXX(thunk) → 真正的 C++ 方法
  └── 蓝图函数 → 解释执行 Script 字节码
```

**蓝图调用 C++ 链路**：
```
BP 节点 → UFunction → FindFunction(字符串哈希查找) → ProcessEvent → NativeFunc 指针
⚠️ 面试追问：反射性能代价？→ FindFunction 是字符串哈希查找，热路径应避免
```

### 1.8 三种反射类型对比

| 特性 | UENUM | USTRUCT | UCLASS |
|------|-------|---------|--------|
| 生成元类型 | UEnum | UScriptStruct | UClass |
| 支持 GC | ❌ | ❌ | ✅ |
| 支持 UPROPERTY | ❌ | ✅ | ✅ |
| 支持 UFUNCTION | ❌ | ❌ | ✅ |
| CDO | ❌ | ❌ | ✅ |
| 蓝图可用 | ✅ | ✅ | ✅ |

---

## 二、GC 垃圾回收

### 2.1 核心算法：标记-清除

```
CollectGarbage() 入口
    │
    ├── 1. GC 锁（FGCCSyncObject）防止并发修改 UObject 图
    │
    ├── 2. 标记阶段（Mark Phase）
    │     ├── MarkObjectsAsUnreachable() → 将所有对象标记为不可达
    │     ├── PerformReachabilityAnalysis() → 从 Root Set 出发遍历引用链
    │     │     └── FReferenceFinder / ARO（AddReferencedObjects）
    │     └── 多线程标记：FGCReferenceProcessor 并行标记
    │
    ├── 3. 清理阶段（Sweep/Purge Phase）
    │     ├── UnhashUnreachableObjects() → 从全局哈希表移除
    │     ├── IncrementalPurgeGarbage() → 增量清理（分帧，避免卡顿）
    │     └── ConditionalBeginDestroy → BeginDestroy → FinishDestroy → 释放内存
    │
    └── 4. GC 簇（Cluster）优化：相关对象打包为簇，标记时整簇一起

⚠️ 面试追问：GC 会卡主线程吗？→ 会，增量标记缓解但不能完全消除
```

### 2.2 关键概念

- **Root Set**：通过 `AddToRoot()` 或 `UPROPERTY()` 标记的对象
- **弱引用**：`TWeakObjectPtr` 不阻止 GC，访问前必须 `IsValid()`
- **MarkAsGarbage vs MarkPendingKill**：UE5 后 PendingKill 废弃，用 MarkAsGarbage
- **GC 触发条件**：`GUObjectArray` 大小超阈值 / 手动 `ForceGarbageCollection()` / 定时（GCInterval）

---

## 三、Subsystem 子系统

### 3.1 五种 Subsystem 生命周期对比

```
UEngineSubsystem        ████████████████████████████  引擎启动 → 引擎关闭
UEditorSubsystem        ████████████████████████████  编辑器启动 → 编辑器关闭（仅编辑器）
UGameInstanceSubsystem    ██████████████████████████  游戏开始 → 游戏退出（跨关卡持久）
UWorldSubsystem               ████████  ████████      进入关卡 → 离开关卡
ULocalPlayerSubsystem     ████████████████████████    玩家加入 → 玩家移除
```

### 3.2 底层实现

```cpp
// FSubsystemCollection<TBaseType> 核心管理器
TMap<UClass*, USubsystem*> SubsystemMap;

// 自动发现流程：
Initialize(Outer) → 反射获取所有派生类 → ShouldCreateSubsystem() 过滤 → 创建实例

// 获取方式：
GameInstance->GetSubsystem<UMySubsystem>();
```

### 3.3 面试话术

> Subsystem 本质上是 UE 封装的**按作用域自动管理的单例模式**。vs 全局单例的优势：
> ① 有生命周期管理 ② 支持 PIE 多实例 ③ 可蓝图访问 ④ 无需修改引擎类

---

## 四、Delegate 代理系统

### 4.1 类型体系

| 类型 | 宏 | 绑定数 | 返回值 | 蓝图 | 序列化 |
|------|-----|:---:|:---:|:---:|:---:|
| 静态单播 | `DECLARE_DELEGATE` | 1 | ✅ | ❌ | ❌ |
| 静态多播 | `DECLARE_MULTICAST_DELEGATE` | N | ❌ | ❌ | ❌ |
| 动态单播 | `DECLARE_DYNAMIC_DELEGATE` | 1 | ✅ | ✅ | ✅ |
| 动态多播 | `DECLARE_DYNAMIC_MULTICAST_DELEGATE` | N | ❌ | ✅ | ✅ |

### 4.2 核心操作速查

| 操作 | 单播 | 多播 | 动态多播 |
|------|------|------|---------| 
| 绑定 | `BindUObject()` | `AddUObject()` | `AddDynamic()` |
| 执行 | `ExecuteIfBound()` | `Broadcast()` | `Broadcast()` |
| 解绑 | `Unbind()` | `Remove(Handle)` | `RemoveDynamic()` |

### 4.3 底层实现要点

- 静态委托：函数指针 + Payload 数据，编译时确定
- 动态委托：通过 `FName` 存储函数名，运行时反射查找（`ProcessDelegate`）
- 多播内部：`TArray<TDelegateInstanceInterface*>` 顺序调用
- **⚠️ Delegate 非线程安全**：IO 线程 Broadcast → 必须 `AsyncTask(GameThread, ...)` 回到主线程

---

## 五、多线程 & TaskGraph

### 5.1 三层多线程体系

| 层次 | 机制 | 特点 |
|------|------|------|
| 底层 | `FRunnable + FRunnableThread` | 最原始，手动管理 |
| 中层 | `FAsyncTask / FAutoDeleteAsyncTask` | 基于全局线程池 GThreadPool |
| 高层 | `TaskGraph (TGraphTask)` | DAG 依赖调度，命名线程分发 |

### 5.2 TaskGraph 核心

```cpp
// 创建依赖链
FGraphEventRef Task1 = TGraphTask<MyTask>::CreateTask().ConstructAndDispatchWhenReady(args);
FGraphEventArray Prereqs; Prereqs.Add(Task1);
FGraphEventRef Task2 = TGraphTask<MyTask>::CreateTask(&Prereqs).ConstructAndDispatchWhenReady(args);

// 调度原理
CreateTask → SetupPrereqs(前置事件) → NumberOfPrerequirementsOutstanding = N+1
前置完成 → --Counter → 降到 0 → QueueTask 投递到目标线程队列
线程主循环 → FindWork → Execute → DispatchSubsequents（通知后续任务）
```

### 5.3 渲染线程架构

```
GameThread ──ENQUEUE_RENDER_COMMAND──→ RenderThread ──RHI Commands──→ RHIThread
  逻辑更新                              场景渲染                      GPU提交

// ENQUEUE_RENDER_COMMAND 底层 = TGraphTask 投递到 ENamedThreads::GetRenderThread()
// 渲染线程本质上就是 TaskGraph 的一个命名线程

// 帧同步：GameThread 通过 FFrameEndSync::Sync 等待 RenderThread 不超前太多帧
```

### 5.4 线程安全铁律

- ❌ 非 GameThread 访问 UObject（GC 不安全）
- ❌ Worker 线程创建/销毁 Actor
- ✅ `FCriticalSection` / `FRWScopeLock` 保护共享数据
- ✅ `ENQUEUE_RENDER_COMMAND` 与渲染线程通信
- ✅ `AsyncTask(ENamedThreads::GameThread, Lambda)` 回到主线程

---

## 六、FTimerManager 定时器

### 6.1 核心实现

```
SetTimer(Handle, Object, Func, Rate, bLoop)
  → 创建 FTimerData → 加入 PendingTimerSet

FTimerManager::Tick(DeltaTime)
  → 遍历 ActiveTimerHeap（最小堆，按到期时间排序）
  → 到期 → 取出 → 调用回调
  → bLoop ? 重新入堆 : 移除

// 底层数据结构
TSparseArray<FTimerData> Timers;      // 所有定时器
TArray<FTimerHandle> ActiveTimerHeap; // 最小堆
TSet<FTimerHandle> PendingTimerSet;   // 待添加队列
TSet<FTimerHandle> PausedTimerSet;    // 暂停队列
```

### 6.2 三种 Tick 方式对比

| 方式 | 机制 | 适用场景 |
|------|------|---------|
| FTimerManager | 堆调度，可暂停/取消/循环 | 延迟调用、定时逻辑 |
| FTickFunction | 组件/Actor 自带 Tick | 每帧更新逻辑 |
| FTickableGameObject | 无需 Actor 的纯 C++ Tick | 全局管理器 |

---

## 七、资源管理 & 异步加载

### 7.1 加载架构

```
业务层 API
  ├── FStreamableManager::RequestAsyncLoad(路径, 回调)  ← 推荐
  ├── LoadObject<T>(路径)                               ← 同步
  └── LoadPackageAsync(路径)                             ← 底层入口

所有加载最终汇聚到 → LoadPackageAsync()
同步加载本质 = LoadPackageAsync + FlushAsyncLoading（阻塞等待）
```

### 7.2 异步加载四阶段

```
1. Summary 阶段：CreateLinker → 异步 IO → FinishLinker → 解析 ImportMap/ExportMap
2. Import 阶段：等待依赖资源（计数器归零机制）
3. Export 阶段：IO 读取 → 反序列化为 UObject
4. PostLoad 阶段：UObject::PostLoad() → 注册到 HashOuter 全局表 → 触发回调
```

### 7.3 硬引用 vs 软引用

| 类型 | 存储 | 加载行为 | 性能影响 |
|------|------|---------|---------|
| 硬引用 | `UObject*` | 反映到 Import 表，自动递归加载 | Import 越多越慢 |
| 软引用 | `FSoftObjectPath` / `TSoftObjectPtr` | 不自动加载，需手动调用 | 大幅减少 Import |

> ⚠️ C++ 中将硬引用改为软引用后，**必须重新保存**所有以该 C++ 类为基类的资源

---

## 八、关键源码文件索引

| 模块 | 文件路径 |
|------|---------|
| UObject 定义 | `Runtime/CoreUObject/Public/UObject/UObjectBase.h` / `Object.h` |
| UClass/UStruct | `Runtime/CoreUObject/Public/UObject/Class.h` |
| FProperty | `Runtime/CoreUObject/Public/UObject/Field.h` |
| GC | `Runtime/CoreUObject/Private/UObject/GarbageCollection.cpp` |
| 异步加载 | `Runtime/CoreUObject/Private/Serialization/AsyncLoading2.cpp` (UE5) |
| TaskGraph | `Runtime/Core/Private/Async/TaskGraph.cpp` |
| Delegate | `Runtime/Core/Public/Delegates/` |
| FTimerManager | `Runtime/Engine/Private/TimerManager.cpp` |
| UHT | `Source/Programs/UnrealHeaderTool/` |

---

*共 8 大模块，基于 48 篇文章交叉验证整合。最新知识以本文件为准。*
