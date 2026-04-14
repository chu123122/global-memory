---
name: ue5-uobject-reflection
description: UE5 UObject创建流程与反射系统深度参考
type: knowledge-doc
created: 2026-04-13
updated: 2026-04-13
source: 多源整合（知乎/CSDN/UE源码）
---

# UE5 UObject 创建流程与反射系统

> 快照文档 · 面试+工作双用 · 2026-04-13

---

## 一、UObject 继承链

```
UObjectBase
  │  ← 最底层：InternalIndex（GUObjectArray索引）、ClassPrivate、NamePrivate
  │
  ├── UObjectBaseUtility
  │     ← 工具方法：IsA()、GetWorld()、GetOuter()、GetPathName()
  │
  └──── UObject
        ← 完整功能：序列化、GC、反射、网络复制
        ← 虚函数：PostInitProperties()、BeginDestroy()、Serialize()
```

**关键设计**：三层继承不是过度设计。UObjectBase 只处理注册和标识（尽量轻量），UObjectBaseUtility 加工具方法，UObject 才是功能完整体。这样引擎内部可以在最底层操作对象而不引入上层依赖。

---

## 二、NewObject 完整调用链

```
NewObject<T>(Outer, Name, Flags, Template)
  │
  ▼
StaticConstructObject_Internal(FStaticConstructObjectParameters)
  │
  ├── Step 1: StaticAllocateObject(Class, InOuter, Name, Flags, ...)
  │     ├── 同名检查：Outer 下已有同名对象 → Rename 或销毁旧对象
  │     ├── 内存分配：按 Class->GetPropertiesSize() + 对齐
  │     │     └── FUObjectAllocator::AllocateUObject()
  │     │           └── GUObjectAllocator → FMemory::Malloc()
  │     ├── GUObjectArray 注册：分配 InternalIndex（GC 追踪的基础）
  │     └── placement new: new (Result) UObjectBase(Class, Flags, Outer, Name)
  │
  ├── Step 2: ClassConstructor 调用
  │     └── (*InClass->ClassConstructor)(FObjectInitializer(Result, Params))
  │           └── 通过反射调用正确的 C++ 构造函数
  │                 └── GENERATED_BODY() 宏生成的 __DefaultConstructor
  │
  └── Step 3: FObjectInitializer 析构（RAII）
        ├── InitProperties() — 从 CDO 或 Template 拷贝属性默认值
        ├── PostInitProperties() — 虚函数回调（用户可重写）
        └── CheckConfigProperties — 从 .ini 加载 Config 属性
```

**UE5 vs UE4 变化**：
- `ConstructObject` 已废弃 → 统一用 `NewObject`
- 参数改为 `FStaticConstructObjectParameters` 结构体传递
- GUObjectArray 从固定数组改为分块(Chunked)数组，支持更大规模

---

## 三、CDO（Class Default Object）

### 什么是 CDO
每个 UClass 有且仅有一个 CDO 实例，在引擎启动时通过 `NewObject` 同一套流程创建。CDO 存储该类所有 UPROPERTY 的**默认值**。

### 作用
1. **默认值模板**：NewObject 创建新实例时，从 CDO 拷贝属性默认值
2. **编辑器支持**：Details 面板显示的默认值来自 CDO
3. **序列化优化**：保存时只存与 CDO 不同的值（差量序列化）
4. **蓝图类**：每个蓝图类也有自己的 CDO

### 创建时机
```
引擎启动 → UClass 注册 → Z_Construct_UClass_XXX() 
  → 创建 CDO: NewObject<T>(GetTransientPackage(), Class)
  → CDO->PostCDOCompiled() 回调
```

**面试陷阱**：构造函数中不应有游戏逻辑，因为 CDO 也会走构造函数。在构造函数里 SpawnActor 或访问 World 会崩。

---

## 四、GUObjectArray 全局对象数组

```cpp
FUObjectArray GUObjectArray;  // 全局唯一

struct FUObjectItem {
    UObjectBase* Object;          // 对象指针
    int32 Flags;                  // RF_xxx 标记
    int32 ClusterRootIndex;       // GC 簇根
    int32 SerialNumber;           // 序列号（弱引用验证用）
};
```

### 注册机制
1. `StaticAllocateObject` 时调用 `GUObjectArray.AllocateUObjectIndex()`
2. 分配一个空闲的 `InternalIndex`
3. 将 `FUObjectItem` 写入数组对应位置
4. `UObjectBase::InternalIndex` 存储此索引

### GC 如何利用
- GC 遍历 GUObjectArray 检查 Reachability
- 标记-清除：从根集出发标记所有可达对象
- 未标记的对象 → `ConditionalBeginDestroy()` → 回收 Index

### UE5 改进：分块数组
```
UE4: 固定大小连续数组（2M 上限）
UE5: FChunkedFixedUObjectArray（64K 一块，动态扩展）
     → 支持大世界分区(WP)场景的海量对象
```

---

## 五、反射系统

### 5.1 为什么 UE 要自己造反射

| 需求 | C++ RTTI 能力 | UE 反射 |
|------|:---:|:---:|
| 蓝图调 C++ 函数 | ❌ | ✅ |
| 编辑器属性面板 | ❌ | ✅ |
| 序列化/反序列化 | ❌ | ✅ |
| GC 引用追踪 | ❌ | ✅ |
| 网络属性复制 | ❌ | ✅ |

C++ 的 `typeid`/`dynamic_cast` 只能做类型识别，无法枚举属性/函数。

### 5.2 GENERATED_BODY() 宏展开

```cpp
// 展开后核心内容（简化）
public:
    static UClass* StaticClass();                                    // 返回 UClass* 元数据
    static void __DefaultConstructor(const FObjectInitializer& X);   // 反射构造器
    typedef ParentClass Super;
    typedef ThisClass ThisClass;
private:
    // 禁止拷贝
```

### 5.3 UHT 代码生成流程

```
编写源码          UBT/UHT 处理              编译
┌──────────┐   ┌─────────────────┐   ┌──────────┐
│ MyActor.h │→ │ UHT 解析宏标记   │→ │ C++ 编译  │
│ UCLASS()  │   │ UCLASS/UPROPERTY│   │          │
│ UPROPERTY │   │ UFUNCTION       │   │          │
└──────────┘   └────────┬────────┘   └──────────┘
                        │ 生成
                ┌───────┴──────────┐
                │ MyActor.generated.h │ ← 声明
                │ MyActor.gen.cpp     │ ← 实现注册
                └──────────────────┘
```

### 5.4 属性/函数注册的四个阶段

```
阶段1: 生成（Build Time）
  UHT → .generated.h / .gen.cpp

阶段2: 收集（Module Load）
  static 自动注册变量 → 类信息收集到全局数组（延迟注册）
  关键结构: TClassCompiledInDefer<T>

阶段3: 注册（Engine Init）
  Z_Construct_UClass_XXX() → 创建 UClass 对象
  → 注册所有 FProperty（含偏移量 offset）
  → 注册所有 UFunction（含 Native 函数指针）

阶段4: 使用（Runtime）
  UClass 查询属性/函数元数据
  → 蓝图调用、编辑器面板、序列化、GC、网络复制
```

### 5.5 偏移量：反射的核心秘密

```cpp
// UHT 生成的属性注册
FProperty* NewProp_Health = new FFloatProperty(
    OwnerClass,
    "Health",
    STRUCT_OFFSET(AMyActor, Health),   // ★ 内存偏移量
    CPF_BlueprintVisible | CPF_Net,
    ...
);
```

**原理**：知道偏移量后，`对象基地址 + 偏移量` 就能直接读写任意属性，无需知道 C++ 类型。这是蓝图读写 C++ 属性、网络复制、序列化的根本原理。

### 5.6 运行时反射 API

```cpp
// 遍历所有属性
for (TFieldIterator<FProperty> It(AMyActor::StaticClass()); It; ++It)
    UE_LOG(LogTemp, Log, TEXT("Property: %s"), *It->GetName());

// 通过名称调用函数
UFunction* Func = MyClass->FindFunctionByName(TEXT("TakeDamage"));
struct { float Damage; } Params = { 50.f };
Instance->ProcessEvent(Func, &Params);

// 通过名称动态读写属性
FProperty* Prop = MyClass->FindPropertyByName(TEXT("Health"));
float* Ptr = Prop->ContainerPtrToValuePtr<float>(Instance);
*Ptr = 75.f;
```

---

## 六、面试高频题（5 道）

### Q1: NewObject 和 SpawnActor 的区别？
**答**：两者最终都走 `StaticConstructObject_Internal`，但 `SpawnActor` 额外做了：
1. World 注册（加入 Level 的 Actor 列表）
2. Transform 设置
3. `BeginPlay` 调用
4. 网络 Replication 注册
普通 UObject 用 `NewObject`，Actor 用 `SpawnActor`。

### Q2: 为什么不能用 new 创建 UObject？
**答**：三个原因：
1. 不会注册到 GUObjectArray → GC 无法追踪 → 内存泄漏或野指针
2. 不会调用 `PostInitProperties()` → 反射属性不初始化
3. 不会从 CDO 拷贝默认值 → 属性值不确定

### Q3: GENERATED_BODY() 干了什么？
**答**：声明了 `StaticClass()`（返回 UClass 元数据）、`__DefaultConstructor`（反射构造器，让只有 UClass* 时也能调正确的 C++ 构造函数）、Super/ThisClass 类型别名、禁止拷贝。实际实现在 UHT 生成的 `.gen.cpp` 中。

### Q4: UE 反射系统的性能开销？
**答**：反射信息（UClass、FProperty、UFunction）在引擎启动时一次性注册完毕，**运行时不产生注册开销**。但通过反射调用函数（ProcessEvent）比直接 C++ 调用慢约 10-100 倍（需要打包参数到堆栈帧、通过函数指针间接调用）。性能敏感路径应用 Native C++ 调用，蓝图接口用反射。

### Q5: CDO 是什么？为什么构造函数不应包含游戏逻辑？
**答**：CDO（Class Default Object）是每个 UClass 的唯一默认实例，引擎启动时创建。所有 `NewObject` 创建的实例都从 CDO 拷贝默认值。因为 CDO 也走构造函数，如果构造函数里 SpawnActor、访问 World、触发 Gameplay 事件，CDO 创建时就会崩或产生副作用。游戏逻辑应放在 `BeginPlay()` 或 `PostInitProperties()` 中。

---

## 参考资料

- [NewObject源码分析](https://zhuanlan.zhihu.com/p/454838825)
- [UObject创建流程全链路](https://zhuanlan.zhihu.com/p/252431932)
- [UObjectBase源码系列](https://zhuanlan.zhihu.com/p/453740744)
- [UE反射原理与使用](https://blog.csdn.net/hhw_hhw/article/details/139287867)
- [从源码深入理解UObject构造流程](https://blog.csdn.net/hacning/article/details/133614424)
- [UE5 UObject源码分析-类型系统与反射](https://zhuanlan.zhihu.com/p/26340380938)
