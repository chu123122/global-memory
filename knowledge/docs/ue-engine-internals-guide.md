# UE 引擎核心机制全景图

> 目标读者：高级 C++ 游戏程序员面试准备
> 深度：能应对 3 层追问
> 生成日期：2026-04-13

---

## 目录

1. [UObject 系统](#1-uobject-系统)
2. [属性系统（反射）](#2-属性系统反射)
3. [GC 系统](#3-gc-系统)
4. [Subsystem](#4-subsystem)
5. [Delegate 系统](#5-delegate-系统)
6. [资源管理](#6-资源管理)
7. [序列化](#7-序列化)
8. [多线程](#8-多线程)
9. [智能指针](#9-智能指针)
10. [模块系统](#10-模块系统)

---

## 1. UObject 系统

### 核心概念

UObject 是 UE 所有托管对象的基类，提供：
- **反射**：运行时类型信息查询
- **GC**：自动垃圾回收（标记-清除）
- **序列化**：属性自动存盘/加载
- **CDO**（Class Default Object）：每个 UClass 有一个默认实例，用于拷贝初始值
- **Outer/Inner 链**：对象归属树，决定 GC 可达性和包归属

### 工作原理

**对象创建流程（NewObject）**：

```
NewObject<T>(Outer, Name, Flags)
  → StaticAllocateObject()          // 分配内存（FMemory::Malloc 或内存池）
    → StaticConstructObject_Internal()
      → (*InClass->ClassConstructor)(Params)  // 调用构造函数
        → UObject::UObject()
        → T::T()                    // 用户构造函数
      → PostInitProperties()        // CDO 属性拷贝
      → PostLoad()                  // 反序列化后回调
```

**关键细节**：
- `NewObject` 不走 C++ 的 `new`，而是 `StaticAllocateObject` 自己分配内存
- CDO 在引擎启动时由 `UClass::CreateDefaultObject()` 创建
- Outer 决定对象的"容器"——UActorComponent 的 Outer 是其 AActor，AActor 的 Outer 是 ULevel

### 关键类和接口

| 类 | 职责 |
|----|------|
| `UObject` | 所有托管对象基类 |
| `UClass` | 描述一个 C++ 类的元信息（属性列表、函数列表、CDO 指针） |
| `UPackage` | 资产包，是 Outer 链的根节点 |
| `FObjectInitializer` | `NewObject` 内部传递给构造函数的初始化上下文 |
| `UObjectBaseUtility` | 提供 `GetClass()`、`GetOuter()`、`GetName()` 等便利函数 |

### 代码示例

```cpp
// 创建一个 UObject
UMyData* Data = NewObject<UMyData>(this, TEXT("MyData"));

// 遍历 Outer 链
for (UObject* O = Data; O; O = O->GetOuter())
{
    UE_LOG(LogTemp, Log, TEXT("Outer: %s"), *O->GetName());
}

// 获取 CDO
const UMyData* CDO = GetDefault<UMyData>();
// 或
const UMyData* CDO = UMyData::StaticClass()->GetDefaultObject<UMyData>();
```

### 常见面试题

**Q1：NewObject 和 new 有什么区别？**
> NewObject 走 UE 自己的分配器（StaticAllocateObject），分配后自动注册到 GC 系统、设置 Outer、拷贝 CDO 属性。普通 new 只分配内存+调构造函数，不参与 GC。

**Q2：CDO 是什么？什么时候创建？有什么用？**
> Class Default Object，每个 UClass 有一个。引擎启动时 UHT 生成的 `StaticRegisterNatives` 阶段创建。用途：(1) 作为属性初始值模板，NewObject 时从 CDO 拷贝默认值；(2) 蓝图编辑器读取默认值；(3) 序列化时只存储与 CDO 不同的属性（差量序列化）。

**Q3：Outer 链有什么用？如果 Outer 被 GC 了会怎样？**
> Outer 链决定对象归属。GC 标记阶段，一个对象的 Inner 对象靠 Outer 链可达。如果 Outer 被 GC 了（不可达），其所有 Inner 对象也变得不可达，会被一起回收——除非 Inner 被其他引用持有。

---

## 2. 属性系统（反射）

### 核心概念

UE 的反射系统 **不使用 C++ RTTI**，而是在编译前由 **UHT**（Unreal Header Tool）解析头文件中的宏标记（UCLASS、UPROPERTY、UFUNCTION），生成 `.generated.h` 和 `.gen.cpp` 代码，在引擎启动时注册类型信息。

### 工作原理

**UHT 代码生成流程**：

```
MyClass.h (UCLASS/UPROPERTY/UFUNCTION 宏)
  → UHT 解析
    → MyClass.generated.h    // GENERATED_BODY() 展开的声明
    → MyClass.gen.cpp        // StaticRegisterNatives + 属性/函数注册代码
      → 引擎启动时执行
        → UClass 对象创建
        → FProperty 链表构建
        → UFunction 注册
```

**关键宏展开**：

```cpp
// UPROPERTY(EditAnywhere, BlueprintReadWrite)
// float Health;
// 
// 生成的 .gen.cpp 中大致逻辑：
static const FStructPropertyParams NewProp_Health = {
    "Health",
    RF_Public,
    CPP_PROPERTY_BASE(UMyClass, Health),
    METADATA_PARAMS(...)
};

// UFUNCTION(BlueprintCallable)
// void TakeDamage(float Damage);
//
// 生成：UFunction 对象 + 参数 FProperty + ProcessEvent 入口
```

### 关键类和接口

| 类 | 职责 |
|----|------|
| `UClass` | 类的元信息容器 |
| `FProperty` | 属性描述（名称、偏移、类型、标志）。UE5 用 `FProperty` 替代了 UE4 的 `UProperty` |
| `UFunction` | 函数描述（参数列表、Native 指针或蓝图字节码） |
| `UHT` | 编译前工具，解析宏并生成注册代码 |
| `UField` | UE4 中 UProperty/UFunction 的基类（UE5 中 FProperty 不再继承 UObject） |

### 代码示例

```cpp
// 运行时遍历类的所有属性
for (TFieldIterator<FProperty> It(UMyClass::StaticClass()); It; ++It)
{
    FProperty* Prop = *It;
    UE_LOG(LogTemp, Log, TEXT("Property: %s, Offset: %d"), 
           *Prop->GetName(), Prop->GetOffset_ForInternal());
}

// 运行时通过名字查找并设置属性值
FProperty* HealthProp = UMyClass::StaticClass()->FindPropertyByName(TEXT("Health"));
if (HealthProp)
{
    float NewValue = 100.f;
    HealthProp->SetValue_InContainer(MyObject, &NewValue);
}

// 运行时调用函数
UFunction* Func = MyObject->FindFunction(TEXT("TakeDamage"));
if (Func)
{
    struct { float Damage; } Params = { 50.f };
    MyObject->ProcessEvent(Func, &Params);
}
```

### 常见面试题

**Q1：UE 为什么不用 C++ 的 RTTI？**
> (1) C++ RTTI 只有 typeid 和 dynamic_cast，信息太少——没有属性列表、函数列表；(2) RTTI 不支持序列化、蓝图绑定；(3) UE 需要的是完整的属性系统（可遍历、可编辑器面板展示、可网络同步），只能自己实现。

**Q2：GENERATED_BODY() 展开了什么？**
> 展开为：(1) 类注册相关的静态函数声明（`StaticClass()`）；(2) `__DefaultConstructor` 和 `__VTableCtorCaller`；(3) 阻止用户写默认构造函数时的编译错误处理。具体内容在 `.generated.h` 中，每个类不同。

**Q3：FProperty 和 UE4 的 UProperty 有什么区别？为什么改？**
> UE4 的 UProperty 继承 UObject，意味着每个属性描述本身是个 GC 对象——浪费内存且增加 GC 压力。UE5 改成 FProperty（普通 C++ 对象），不参与 GC，内存占用更小、创建更快。这是一个典型的**性能导向的架构改进**。

---

## 3. GC 系统

### 核心概念

UE 使用**标记-清除**（Mark-Sweep）GC，特点：
- **非分代**：不像 Java 分 Young/Old，UE 每次 GC 扫描所有对象
- **增量标记**：可以分帧完成标记阶段（`IncrementalPurgeGarbage`）
- **GC 簇**（Cluster）：一组对象绑在一起，只要簇根可达，整个簇都可达——减少标记遍历量
- **主线程触发**：GC 只在 GameThread 的特定时机触发（`CollectGarbage` 或 `TryCollectGarbage`）

### 工作原理

**完整 GC 流程**：

```
1. CollectGarbage(GARBAGE_COLLECTION_KEEPFLAGS, true)
   → MarkObjectsAsUnreachable()   // 把所有 UObject 标记为"不可达"
   → PerformReachabilityAnalysis() // 从根集合开始标记"可达"
     → 根集合来源：
       (a) AddToRoot() 的对象
       (b) 被 UPROPERTY() 引用的对象链
       (c) FGCObject::AddReferencedObjects() 注册的非 UObject 引用
       (d) GC 簇根
   → IncrementalPurgeGarbage()     // 分帧销毁不可达对象
     → ConditionalBeginDestroy()
     → ConditionalFinishDestroy()
     → 释放内存
```

**GC 簇（Cluster）**：

```cpp
// 创建簇：将多个对象绑到一个簇根
void UMyAsset::CreateCluster()
{
    if (CanCreateCluster())
    {
        TArray<UObject*> ObjectsInCluster;
        GetObjectsInCluster(ObjectsInCluster);
        FGCCluster::Create(this, ObjectsInCluster);
    }
}
// 簇内对象不单独参与标记，整个簇作为一个标记单元
// StaticMesh 的 LOD/Materials 通常放在同一个簇中
```

### 关键类和接口

| 类/函数 | 职责 |
|---------|------|
| `CollectGarbage()` | 触发完整 GC |
| `TryCollectGarbage()` | 尝试 GC（可能因为时间不够而跳过） |
| `AddToRoot()` / `RemoveFromRoot()` | 手动添加/移除 GC 根引用 |
| `FGCObject` | 非 UObject 类持有 UObject 引用时，继承此类并重写 `AddReferencedObjects` |
| `MarkPendingKill()` | UE4 标记对象即将销毁（UE5 已废弃） |
| `MarkAsGarbage()` | UE5 替代 MarkPendingKill 的新 API |
| `TWeakObjectPtr` | 弱引用，不阻止 GC，访问前检查 `IsValid()` |

### 代码示例

```cpp
// 防止 GC 回收
MyObject->AddToRoot();
// ... 使用完毕
MyObject->RemoveFromRoot();

// 非 UObject 类持有 UObject 引用
class FMyManager : public FGCObject
{
    TArray<UMyData*> CachedData;
    
    virtual void AddReferencedObjects(FReferenceCollector& Collector) override
    {
        Collector.AddReferencedObjects(CachedData);
    }
    virtual FString GetReferencerName() const override
    {
        return TEXT("FMyManager");
    }
};

// UE5 推荐：用 TStrongObjectPtr 代替 AddToRoot
TStrongObjectPtr<UMyData> StrongRef(NewObject<UMyData>());
// 析构时自动 RemoveFromRoot，比手动 AddToRoot 安全
```

### 常见面试题

**Q1：UPROPERTY 不标记会怎样？**
> 不标记 UPROPERTY 的 UObject* 成员变量不参与 GC 引用追踪——GC 不知道你持有这个引用，可能把目标对象回收掉，导致**悬垂指针**。这是 UE 开发中最经典的 crash 来源之一。

**Q2：MarkPendingKill 和 MarkAsGarbage 的区别？**
> UE4 的 `MarkPendingKill` 在下次 GC 时回收对象，但有个问题：标记后 `IsValid()` 立即返回 false，但对象还在内存中，某些代码可能仍然访问它。UE5 的 `MarkAsGarbage` 行为更明确：标记为垃圾但不影响指针有效性检查，在 GC 标记阶段才处理。UE5 还引入了 `bMarkAsGarbageOnDestroy` 自动化标记。

**Q3：GC 簇有什么用？什么场景下用？**
> GC 簇把一组生命周期一致的对象绑在一起——比如 StaticMesh 和它的 Materials/LOD 数据。好处是 GC 标记阶段不需要逐个遍历簇内对象，只检查簇根即可，对于资源密集的项目能显著减少 GC 耗时。缺点是簇内对象不能单独释放。

---

## 4. Subsystem

### 核心概念

Subsystem 是 UE 的**托管单例**模式——引擎自动创建、管理生命周期，避免手写全局单例的各种问题。

### 五种类型

| Subsystem 类型 | 生命周期 | 典型用途 |
|---------------|---------|---------|
| `UEngineSubsystem` | 引擎启动 → 关闭 | 全局服务（日志、分析） |
| `UEditorSubsystem` | 编辑器启动 → 关闭 | 编辑器工具、扩展 |
| `UGameInstanceSubsystem` | GameInstance 创建 → 销毁 | 跨关卡数据（成就、设置） |
| `UWorldSubsystem` | World 创建 → 销毁 | 关卡级服务（AI 管理器） |
| `ULocalPlayerSubsystem` | LocalPlayer 创建 → 销毁 | 玩家级服务（UI 管理） |

### 工作原理

```
引擎启动/World 创建/GameInstance 创建
  → USubsystemCollectionBase::Initialize()
    → 遍历所有注册的 Subsystem 类
      → ShouldCreateSubsystem() 检查
      → NewObject<T>() 创建实例
      → Initialize() 回调
      
引擎关闭/World 销毁/GameInstance 销毁
  → Deinitialize() 回调
  → 析构
```

### 代码示例

```cpp
// 定义一个 GameInstance Subsystem
UCLASS()
class UMyGameSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override
    {
        return true; // 可以根据条件决定是否创建
    }
    virtual void Initialize(FSubsystemCollectionBase& Collection) override
    {
        // 初始化逻辑。Collection 可以获取其他 Subsystem 的引用
        // Collection.InitializeDependency<UOtherSubsystem>(); // 声明依赖
    }
    virtual void Deinitialize() override { /* 清理 */ }
    
    void DoSomething() { /* 业务逻辑 */ }
};

// 使用：
UGameInstance* GI = GetGameInstance();
UMyGameSubsystem* Sub = GI->GetSubsystem<UMyGameSubsystem>();
Sub->DoSomething();
```

### 常见面试题

**Q1：Subsystem 和自己写单例有什么区别？**
> (1) 生命周期自动管理——不需要手动 Init/Shutdown，不会忘记清理；(2) 可以声明 Subsystem 间的依赖顺序；(3) 支持条件创建（ShouldCreateSubsystem）；(4) 是 UObject，支持反射/蓝图访问。手写单例容易出现初始化顺序问题、忘记清理、跨模块访问困难。

**Q2：World Subsystem 在切换关卡时会怎样？**
> World 销毁 → Deinitialize → 析构 → 新 World 创建 → 新 Subsystem 创建 → Initialize。每次切关卡都是全新实例，不会有残留状态。这也是 Subsystem 比全局单例安全的原因——状态不会跨关卡泄漏。

---

## 5. Delegate 系统

### 核心概念

UE 的委托系统实现了**类型安全的回调机制**，四种类型：

| 类型 | 宏 | 绑定数 | 蓝图 | 线程安全 |
|------|-----|:------:|:----:|:-------:|
| 单播 | `DECLARE_DELEGATE` | 1 | ❌ | ❌ |
| 多播 | `DECLARE_MULTICAST_DELEGATE` | N | ❌ | ❌ |
| 动态单播 | `DECLARE_DYNAMIC_DELEGATE` | 1 | ✅ | ❌ |
| 动态多播 | `DECLARE_DYNAMIC_MULTICAST_DELEGATE` | N | ✅ | ❌ |

### 代码示例

```cpp
// 单播
DECLARE_DELEGATE_OneParam(FOnHealthChanged, float);
FOnHealthChanged OnHealthChanged;
OnHealthChanged.BindUObject(this, &UMyClass::HandleHealthChanged);
OnHealthChanged.ExecuteIfBound(100.f);

// 多播
DECLARE_MULTICAST_DELEGATE_OneParam(FOnDamage, float);
FOnDamage OnDamage;
FDelegateHandle Handle = OnDamage.AddUObject(this, &UMyClass::HandleDamage);
OnDamage.Broadcast(50.f);
OnDamage.Remove(Handle); // 用 Handle 解绑

// 动态多播（蓝图可用）
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnScoreChanged, int32, NewScore);

UPROPERTY(BlueprintAssignable) // 蓝图可绑定
FOnScoreChanged OnScoreChanged;

OnScoreChanged.Broadcast(999);
```

### 关键细节

**线程安全问题**：
- 所有委托类型的 `Broadcast` / `Execute` 都**不是线程安全的**
- 在非 GameThread 调用 Broadcast → 未定义行为
- 解决方案：用 `AsyncTask(ENamedThreads::GameThread, [=]{ Delegate.Broadcast(); })`

**绑定方式**：
```cpp
BindUObject(Obj, &Func)      // 绑定 UObject 成员函数（弱引用，GC 后自动失效）
BindSP(SharedPtr, &Func)     // 绑定 TSharedPtr 持有的对象
BindRaw(RawPtr, &Func)       // 绑定原始指针（⚠️ 不检查生命周期）
BindLambda(Lambda)            // 绑定 Lambda
BindStatic(&StaticFunc)       // 绑定静态/全局函数
```

### 常见面试题

**Q1：动态委托和普通委托的区别？**
> 动态委托通过函数名字符串绑定（FindFunction），支持蓝图、支持序列化，但调用开销大（ProcessEvent）。普通委托通过函数指针直接调用，性能好但不支持蓝图。选择原则：需要蓝图交互用动态，纯 C++ 用普通。

**Q2：多播委托的 Broadcast 期间，某个回调 Remove 了自己会怎样？**
> UE 的多播实现允许在 Broadcast 遍历期间 Remove——内部用了 CompactInvocationList 机制，被移除的槽位标记为无效但不立即删除，遍历结束后再清理。所以是安全的。

---

## 6. 资源管理

### 核心概念

| 概念 | 作用 |
|------|------|
| `UPackage` | 资产文件（.uasset）在内存中的表示 |
| `FAssetData` | 轻量级资产元信息（路径、类型、标签），不加载资产本身 |
| `UAssetManager` | 资产注册、发现、加载调度的中央管理器 |
| `FStreamableManager` | 异步加载管理，支持加载完成回调 |
| `FSoftObjectPath` | 字符串形式的资产路径（`/Game/Meshes/SM_Chair.SM_Chair`） |
| `TSoftObjectPtr<T>` | 类型安全的软引用，按需加载 |

### 异步加载流程

```
RequestAsyncLoad(SoftPath, Callback)
  → FStreamableManager::RequestAsyncLoad()
    → 创建 FStreamableHandle
    → 通过 FAsyncLoadingThread 发起异步加载请求
      → IO 线程读取 .uasset 文件
      → 反序列化（FLinkerLoad）
      → 创建 UObject
      → 回到 GameThread
    → 调用 Callback
    → Handle 引用计数管理加载资产的生命周期
```

### 代码示例

```cpp
// 软引用（不自动加载）
UPROPERTY(EditAnywhere)
TSoftObjectPtr<UStaticMesh> MeshRef;

// 同步加载
UStaticMesh* Mesh = MeshRef.LoadSynchronous();

// 异步加载
FStreamableManager& SM = UAssetManager::GetStreamableManager();
TSharedPtr<FStreamableHandle> Handle = SM.RequestAsyncLoad(
    MeshRef.ToSoftObjectPath(),
    FStreamableDelegate::CreateUObject(this, &UMyClass::OnMeshLoaded)
);

// PrimaryAsset 系统
// 在 AssetManager 中注册资产类型
UCLASS()
class UMyItemData : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    virtual FPrimaryAssetId GetPrimaryAssetId() const override
    {
        return FPrimaryAssetId(TEXT("Item"), GetFName());
    }
};

// 加载
UAssetManager& AM = UAssetManager::Get();
AM.LoadPrimaryAsset(FPrimaryAssetId("Item:Sword"), {}, 
    FStreamableDelegate::CreateLambda([](){ /* 加载完成 */ }));
```

### 常见面试题

**Q1：SoftObjectPtr 和硬引用有什么区别？什么时候用哪个？**
> 硬引用（直接 UObject*）：拥有者加载时自动加载目标，形成依赖链——一个 Blueprint 引用了 100 个 Mesh，打开 Blueprint 就加载 100 个 Mesh。软引用只存路径字符串，不触发自动加载，需要时才 Load。**原则：大量或可选资源用软引用，核心依赖用硬引用。**

**Q2：FStreamableHandle 有什么用？**
> Handle 持有加载请求的引用计数。只要 Handle 存活，加载的资源就不会被 GC。Handle 销毁 → 引用计数减少 → 可能被 GC。所以异步加载后必须保持 Handle 存活，否则资源可能加载完立刻被回收。

---

## 7. 序列化

### 核心概念

UE 的序列化系统以 `FArchive` 为核心，用**操作符重载** `<<` 实现读/写双向复用：

```cpp
// 同一套代码，根据 Archive 方向自动读或写
FArchive& operator<<(FArchive& Ar, FMyStruct& S)
{
    Ar << S.Health;     // Ar.IsLoading() → 读；Ar.IsSaving() → 写
    Ar << S.Name;
    return Ar;
}
```

### 工作原理

**包加载流程（简化）**：

```
LoadPackage("/Game/Maps/Level01")
  → CreateLinkerForPackage()
    → FLinkerLoad 创建
    → 读取 PackageFileSummary（文件头）
    → 读取 NameMap（字符串表）
    → 读取 ImportMap（外部依赖列表）
    → 读取 ExportMap（本包导出对象列表）
  → 逐个 Export 创建 UObject
    → PreSerialize()
    → Serialize(FArchive&)    // 调用每个类的序列化函数
    → PostLoad()
```

**ExportMap / ImportMap**：
- ExportMap：本 .uasset 文件中包含的对象列表
- ImportMap：本文件引用的外部对象列表（指向其他 .uasset）
- 加载时先解析 ImportMap，递归加载依赖包

### 关键类

| 类 | 职责 |
|----|------|
| `FArchive` | 序列化基类（抽象 I/O 流） |
| `FMemoryReader` / `FMemoryWriter` | 内存序列化 |
| `FLinkerLoad` | .uasset 文件加载器 |
| `FLinkerSave` | .uasset 文件保存器 |
| `FObjectAndNameAsStringProxyArchive` | 用名字替代指针引用的序列化（SaveGame） |

### 代码示例

```cpp
// 自定义序列化
void UMyData::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 版本控制
    int32 Version = 2;
    Ar << Version;
    
    Ar << Health;
    Ar << Name;
    
    if (Version >= 2)
    {
        Ar << NewField; // V2 新增字段
    }
}

// SaveGame 序列化
TArray<uint8> SaveData;
FMemoryWriter Writer(SaveData);
FObjectAndNameAsStringProxyArchive WriterProxy(Writer, false);
WriterProxy.ArIsSaveGame = true;
MyObject->Serialize(WriterProxy);
```

### 常见面试题

**Q1：FArchive 的 `<<` 操作符怎么做到同一份代码读写通用的？**
> `FArchive` 是基类，`FMemoryReader` 重写了 `Serialize(void*, int64)` 为**读**操作，`FMemoryWriter` 重写为**写**操作。`<<` 最终调用 `Serialize()`，运行时多态决定读还是写。

**Q2：UE 序列化如何处理版本兼容？**
> 两层机制：(1) 引擎级——PackageFileSummary 中的 FileVersion，引擎升级时自动转换旧格式；(2) 用户级——在 Serialize 函数中自己维护版本号，根据版本决定读取哪些字段。还有 `FCustomVersionRegistration` 可以注册自定义版本号。

---

## 8. 多线程

### 核心概念

UE 的多线程模型以**三线程 + TaskGraph** 为核心：

| 线程 | 职责 | 帧内时序 |
|------|------|---------|
| **GameThread** | 游戏逻辑 Tick、输入处理、GC | 帧开始最先执行 |
| **RenderThread** | 渲染命令生成（晚 GameThread 1 帧） | 滞后 1 帧 |
| **RHIThread** | 底层图形 API 调用提交（DX12/Vulkan） | 滞后 RenderThread |

```
Frame N:   GameThread [Tick] ──→ 生成渲染命令 ──→ 
Frame N+1:              RenderThread [执行命令] ──→
Frame N+2:                            RHIThread [提交 GPU]
```

### TaskGraph

TaskGraph 是 UE 的**任务并行框架**，基于 DAG（有向无环图）调度：

```cpp
// 定义一个 Task
class FMyTask
{
public:
    static ENamedThreads::Type GetDesiredThread() 
    { 
        return ENamedThreads::AnyThread; // 或指定线程
    }
    
    static ESubsequentsMode::Type GetSubsequentsMode() 
    { 
        return ESubsequentsMode::TrackSubsequents; 
    }
    
    FORCEINLINE TStatId GetStatId() const { RETURN_QUICK_DECLARE_CYCLE_STAT(FMyTask, STATGROUP_TaskGraphTasks); }
    
    void DoTask(ENamedThreads::Type CurrentThread, const FGraphEventRef& MyCompletionGraphEvent)
    {
        // 实际工作
    }
};

// 提交任务
FGraphEventRef Task = TGraphTask<FMyTask>::CreateTask().ConstructAndDispatchWhenReady();

// 带依赖的任务
FGraphEventArray Prerequisites;
Prerequisites.Add(TaskA);
Prerequisites.Add(TaskB);
FGraphEventRef TaskC = TGraphTask<FMyTask>::CreateTask(&Prerequisites).ConstructAndDispatchWhenReady();

// 等待完成
FTaskGraphInterface::Get().WaitUntilTaskCompletes(Task);
```

### 其他线程工具

```cpp
// FRunnable — 传统线程封装
class FMyThread : public FRunnable
{
    virtual bool Init() override { return true; }
    virtual uint32 Run() override 
    { 
        while (!bStopping) { /* 工作 */ }
        return 0; 
    }
    virtual void Stop() override { bStopping = true; }
    
    FRunnableThread* Thread;
    bool bStopping = false;
public:
    void Start()
    {
        Thread = FRunnableThread::Create(this, TEXT("MyThread"));
    }
};

// AsyncTask — 简便异步
AsyncTask(ENamedThreads::GameThread, [this]()
{
    // 回到 GameThread 执行
    OnLoadComplete.Broadcast();
});

// ParallelFor — 数据并行
ParallelFor(Array.Num(), [&](int32 Index)
{
    ProcessItem(Array[Index]);
});
```

### 常见面试题

**Q1：GameThread 和 RenderThread 是怎么同步的？**
> 通过 **FRenderCommandFence** 和 **ENQUEUE_RENDER_COMMAND** 宏。GameThread 把渲染命令打包放到队列里，RenderThread 逐个执行。GameThread 可以用 Fence 等待 RenderThread 追上。RenderThread 始终滞后 GameThread 1 帧。

**Q2：TaskGraph 和 std::async 有什么区别？**
> TaskGraph 是任务图，支持依赖关系（A→B→C）、指定执行线程、任务窃取（WorkStealing）。std::async 只是简单的"提交一个异步任务返回 future"，没有依赖管理。TaskGraph 的调度器会把任务分配到线程池的最空闲线程，效率更高。

**Q3：ParallelFor 的陷阱？**
> (1) Lambda 中不能访问 GameThread-only 的 API（比如 SpawnActor）；(2) 需要确保数组元素间没有数据竞争——如果处理 Array[i] 时读写了 Array[j]，就不安全；(3) 元素太少时 ParallelFor 的调度开销可能超过并行收益。

---

## 9. 智能指针

### UE 的两套智能指针

| 指针类型 | 管理对象 | 引用计数 | GC 参与 |
|---------|---------|:-------:|:------:|
| `TSharedPtr` / `TWeakPtr` / `TUniquePtr` | 非 UObject（普通 C++ 类） | ✅ 侵入式 | ❌ |
| `TObjectPtr` / `TWeakObjectPtr` / `TStrongObjectPtr` | UObject | GC 管理 | ✅ |

### TSharedPtr（非 UObject 用）

```cpp
// 创建
TSharedPtr<FMyData> Ptr = MakeShared<FMyData>(Args...);

// 共享所有权
TSharedPtr<FMyData> Ptr2 = Ptr; // 引用计数 +1

// 弱引用
TWeakPtr<FMyData> Weak = Ptr;
if (TSharedPtr<FMyData> Pinned = Weak.Pin()) // 尝试提升为强引用
{
    Pinned->DoSomething();
}

// 独占指针
TUniquePtr<FMyData> Unique = MakeUnique<FMyData>();
// TUniquePtr<FMyData> Copy = Unique; // ❌ 编译错误，不可复制
TUniquePtr<FMyData> Moved = MoveTemp(Unique); // ✅ 可移动
```

### UObject 指针对比

```cpp
// 硬引用（UPROPERTY 标记）——GC 安全
UPROPERTY()
UMyData* SafeRef; // GC 知道你持有这个引用

// 裸指针（无 UPROPERTY）——GC 不安全 ⚠️
UMyData* DangerousRef; // GC 可能随时回收它

// 弱引用——不阻止 GC，访问前检查
TWeakObjectPtr<UMyData> WeakRef;
if (WeakRef.IsValid()) { WeakRef->DoSomething(); }

// 强引用（非 UPROPERTY 场景）
TStrongObjectPtr<UMyData> StrongRef(NewObject<UMyData>());
// 内部调用 AddToRoot，析构时 RemoveFromRoot

// UE5 的 TObjectPtr——编辑器下有访问追踪
UPROPERTY()
TObjectPtr<UMyData> ObjPtr; // 运行时等价于裸指针，编辑器下有额外检查
```

### 常见面试题

**Q1：TSharedPtr 和 std::shared_ptr 有什么区别？**
> (1) UE 的 TSharedPtr 支持**线程安全模式**：`TSharedPtr<T, ESPMode::ThreadSafe>`，引用计数原子操作；默认是 `ESPMode::NotThreadSafe`（更快）。std::shared_ptr 始终线程安全。(2) UE 的用 `MakeShared` 而非 `make_shared`。(3) UE 不支持 `shared_from_this` 模式，而是用 `TSharedFromThis<T>` 基类。

**Q2：什么时候用 TSharedPtr，什么时候用 UPROPERTY？**
> **UObject 用 UPROPERTY，非 UObject 用 TSharedPtr。** 永远不要用 TSharedPtr 管理 UObject——UObject 有自己的 GC 系统，用 TSharedPtr 会导致双重释放（GC 释放一次 + 引用计数归零释放一次）。

**Q3：TWeakObjectPtr 和 TWeakPtr 的区别？**
> TWeakObjectPtr 用于 UObject，内部通过 GC 的对象索引表判断对象是否存活；TWeakPtr 用于非 UObject，内部通过引用计数控制块判断。两者机制完全不同，不能混用。

---

## 10. 模块系统

### 核心概念

UE 的代码组织以 **Module** 为单位：
- 每个 Module 是一个独立编译单元（.dll / .so）
- Module 之间通过 `.Build.cs` 声明依赖
- Module 的加载由 `FModuleManager` 管理

### Module vs Plugin

| | Module | Plugin |
|-|--------|--------|
| 定义 | 一组编译单元（.Build.cs） | 一组 Module + 配置（.uplugin） |
| 可选性 | 通常必须 | 可启用/禁用 |
| 分发 | 随引擎/项目编译 | 可独立分发 |
| 典型用途 | 引擎核心、项目业务代码 | 扩展功能、第三方库封装 |

### Module 加载顺序

```
引擎启动
  → PreInit 阶段
    → 核心模块（Core, CoreUObject, Engine...）
    → 平台模块
  → Init 阶段
    → StartupModule() 按依赖顺序调用
    → 项目模块
    → 插件模块
  → PostInit 阶段
    → PostEngineInit 广播
```

### 代码示例

```cpp
// Module 定义
// MyModule.h
class FMyModule : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        // 模块加载时执行
        // 注册 Slate 样式、注册控制台命令等
    }
    virtual void ShutdownModule() override
    {
        // 模块卸载时清理
    }
};

// MyModule.cpp
IMPLEMENT_MODULE(FMyModule, MyModule)

// .Build.cs
public class MyModule : ModuleRules
{
    public MyModule(ReadOnlyTargetRules Target) : base(Target)
    {
        PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });
    }
}

// 跨模块获取实例
IMyModule& Mod = FModuleManager::LoadModuleChecked<IMyModule>("MyModule");
```

### 常见面试题

**Q1：PublicDependencyModuleNames 和 PrivateDependencyModuleNames 的区别？**
> Public 依赖会传递——如果 A Public 依赖 B，那么依赖 A 的模块 C 也能访问 B 的头文件。Private 依赖不传递——只有 A 的 .cpp 能用 B，A 的头文件不暴露 B。原则：尽量用 Private 减少编译依赖。

**Q2：模块的加载顺序怎么控制？**
> (1) Build.cs 中的依赖关系自动决定编译和加载顺序；(2) .uplugin 中的 `LoadingPhase` 可以指定加载阶段（Default / PreLoadingScreen / PostConfigInit 等）；(3) StartupModule 中可以用 `FModuleManager::Get().IsModuleLoaded()` 检查依赖是否已加载。

---

## 附录：十大模块关系图

```
UObject 系统
  ├── 属性系统（反射）──→ 序列化（属性自动读写）
  ├── GC 系统 ──→ 智能指针（GC 指针 vs 手动指针）
  └── CDO ──→ 序列化（差量存储）

资源管理
  ├── 序列化（.uasset 读写）
  ├── 多线程（异步加载线程）
  └── 模块系统（按需加载 Module）

Subsystem ──→ UObject 生命周期
Delegate ──→ 多线程（线程安全问题）
```
