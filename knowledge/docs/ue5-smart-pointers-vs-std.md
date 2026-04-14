---
name: ue5-smart-pointers-vs-std
description: UE5智能指针 vs std智能指针完整对比
type: knowledge-doc
created: 2026-04-13
updated: 2026-04-13
source: 多源整合（知乎/CSDN/UE源码）
---

# UE5 智能指针 vs std 智能指针 完整对比

> 快照文档 · 面试高频 · 2026-04-13

---

## 一、总览对比表

| 特性 | UE5 | std (C++11/14/17) |
|------|-----|--------------------|
| 共享指针 | `TSharedPtr<T, Mode>` | `std::shared_ptr<T>` |
| 不可空共享引用 | `TSharedRef<T, Mode>` ✅ | ❌ 无对应类型 |
| 弱引用 | `TWeakPtr<T, Mode>` | `std::weak_ptr<T>` |
| 独占指针 | `TUniquePtr<T>` | `std::unique_ptr<T>` |
| 线程安全可选 | ✅ `ESPMode` 参数 | ❌ 始终原子操作 |
| 自定义删除器 | ✅ | ✅ |
| 从 this 获取 | `TSharedFromThis<T>` | `std::enable_shared_from_this<T>` |
| 创建函数 | `MakeShared<T>(...)` | `std::make_shared<T>(...)` |

---

## 二、TSharedPtr vs std::shared_ptr

### 2.1 引用计数实现差异

```cpp
// UE5: 独立的引用计数控制器
class FReferenceControllerBase {
    int32 SharedReferenceCount;  // 强引用计数
    int32 WeakReferenceCount;    // 弱引用计数
    virtual void DestroyObject() = 0;
};

// TSharedPtr 数据成员
template<class T, ESPMode Mode>
class TSharedPtr {
    T* Object;                                           // 原始指针
    SharedPointerInternals::FSharedReferencer<Mode> Ref;  // 引用计数管理器
};
```

```cpp
// std: control block 通常和对象一起分配（make_shared优化）
// control block 包含 shared_count + weak_count + deleter + allocator
```

### 2.2 线程安全模式 ESPMode

```cpp
enum class ESPMode : uint8 {
    NotThreadSafe = 0,  // 普通 ++/--（零原子开销）
    ThreadSafe   = 1,   // InterlockedIncrement/Decrement
};

// 非线程安全（性能最优，单线程场景用）
TSharedPtr<FMyClass, ESPMode::NotThreadSafe> FastPtr;

// 线程安全（跨线程传递时用）
TSharedPtr<FMyClass, ESPMode::ThreadSafe> SafePtr;
```

**UE5 默认值变化**：UE4 默认 `NotThreadSafe`，UE5 较新版本默认改为 `ThreadSafe`。

**std::shared_ptr**：始终使用原子操作，无法关闭 → 单线程场景有不必要的性能开销。

### 2.3 线程安全 vs 非线程安全的性能差异

```cpp
// NotThreadSafe: 直接自增
Controller->SharedReferenceCount++;

// ThreadSafe: 原子操作
FPlatformAtomics::InterlockedIncrement(&Controller->SharedReferenceCount);
```

原子操作在 x86 上约 10-40ns，普通自增 <1ns。高频拷贝场景（如每帧传递指针）差距显著。

---

## 三、TSharedRef（UE 独有）

### 核心特性：不可为空

```cpp
// 构造必须传入有效对象
TSharedRef<FMyClass> Ref = MakeShared<FMyClass>(); // ✅
TSharedRef<FMyClass> Ref = nullptr;                // ❌ 编译错误

// 运行时检查
TSharedRef(OtherType* InObject) {
    check(InObject != nullptr);  // 断言保证
}
```

### 与 TSharedPtr 的转换

```cpp
// Ref → Ptr（隐式，安全）
TSharedPtr<T> Ptr = MyRef;

// Ptr → Ref（显式，可能崩溃）
TSharedRef<T> Ref = MyPtr.ToSharedRef();  // Ptr 为 null → 断言失败
```

### 使用场景
- 函数返回值保证非空 → `TSharedRef`
- 函数参数可能为空 → `TSharedPtr`
- 类成员保证始终有效 → `TSharedRef`

---

## 四、TWeakPtr vs std::weak_ptr

### 弱引用计数释放机制差异

```
UE5 TWeakPtr:
  SharedCount → 0: 销毁对象（调用 DestroyObject）
  WeakCount → 0: 销毁引用计数控制器本身

std::weak_ptr:
  use_count → 0: 销毁对象
  weak_count → 0: 销毁 control block
  ⚠️ make_shared 时 control block 和对象一起分配
     → 即使对象已销毁，只要还有 weak_ptr，内存不释放！
```

**面试重点**：`std::make_shared` 的"内存延迟释放"问题——对象和 control block 共享同一块内存，weak_ptr 存活时整块内存都不释放。UE5 的 `MakeShared` 也有类似行为。

### Pin 操作

```cpp
// UE5
TSharedPtr<T> Pinned = WeakPtr.Pin();
if (Pinned.IsValid()) { /* 使用 */ }

// std
std::shared_ptr<T> Pinned = WeakPtr.lock();
if (Pinned) { /* 使用 */ }
```

---

## 五、TUniquePtr vs std::unique_ptr

基本等价，核心差异：

| | TUniquePtr | std::unique_ptr |
|---|---|---|
| 自定义删除器 | `TUniquePtr<T, TDefaultDelete<T>>` | `std::unique_ptr<T, Deleter>` |
| 数组支持 | `TUniquePtr<T[]>` | `std::unique_ptr<T[]>` |
| Reset | `Reset(NewPtr)` | `reset(NewPtr)` |
| Release | `Release()` | `release()` |

两者行为几乎相同，UE 版本主要是为了保持 API 风格统一。

---

## 六、UE 智能指针与 UObject GC 指针的配合规则

### ⚠️ 黄金规则：UObject 用 UPROPERTY，非 UObject 用 TSharedPtr

```cpp
UCLASS()
class AMyActor : public AActor {
    GENERATED_BODY()

    // ✅ UObject 派生类 → 用 UPROPERTY（GC 追踪）
    UPROPERTY()
    UStaticMeshComponent* MeshComp;

    // ✅ 非 UObject → 用 TSharedPtr
    TSharedPtr<FMyData> DataPtr;

    // ❌ 错误！UObject 不应用 TSharedPtr
    // TSharedPtr<UTexture2D> BadPtr;  // GC 会把对象回收，TSharedPtr 变野指针
};
```

### 为什么 UObject 不能用 TSharedPtr

1. GC 通过 `UPROPERTY` 标记追踪引用关系
2. TSharedPtr 的引用计数对 GC 不可见
3. GC 认为对象不可达 → 回收 → TSharedPtr 持有野指针 → 崩溃

### 混合使用指南

| 场景 | 用什么 |
|------|--------|
| UObject 成员引用 | `UPROPERTY() UMyObject*` |
| UObject 弱引用 | `TWeakObjectPtr<UMyObject>` |
| UObject 软引用（延迟加载） | `TSoftObjectPtr<UMyObject>` |
| 非 UObject 共享所有权 | `TSharedPtr<FMyStruct>` |
| 非 UObject 独占所有权 | `TUniquePtr<FMyStruct>` |
| 非 UObject 弱引用 | `TWeakPtr<FMyStruct>` |

---

## 七、面试追问链（3 层）

### Layer 1: 基础
**Q**: UE 为什么不用 std::shared_ptr？
**A**: 三个原因：①线程安全可选（ESPMode），单线程场景零原子开销；②有 TSharedRef（不可空保证）；③完全控制内存分配，跨平台行为一致。

### Layer 2: 原理
**Q**: ESPMode::ThreadSafe 具体怎么实现的？和 std 有什么区别？
**A**: UE 用 `FPlatformAtomics::InterlockedIncrement/Decrement`（映射到 x86 的 `lock xadd`），std 也是原子操作。关键区别不在实现而在**可选性**——UE 允许 NotThreadSafe 模式完全避免原子开销，std 不行。

### Layer 3: 陷阱
**Q**: TSharedPtr 和 GC 混用会怎样？
**A**: UObject 用 TSharedPtr 会导致 GC 不可见引用 → 对象被 GC 回收后 TSharedPtr 变野指针。正确做法是 UObject 用 `UPROPERTY` + `TWeakObjectPtr`，非 UObject 才用 TSharedPtr。另外 `MakeShared` 和 `std::make_shared` 都有弱引用延迟释放问题——对象已销毁但 control block 和对象共享内存，weak_ptr 存活时内存不释放。

---

## 参考资料

- [UE5智能指针源码上篇-TSharedRef](https://zhuanlan.zhihu.com/p/580469704)
- [UE5智能指针源码下篇-TSharedPtr/TWeakPtr](https://zhuanlan.zhihu.com/p/581169238)
- [深入分析虚幻源码——智能指针](https://zhuanlan.zhihu.com/p/261684074)
- [STL与UE智能指针对比](https://blog.csdn.net/inspironx/article/details/122774357)
