---
name: ue5-memory-allocator
description: UE5内存分配器FMalloc/Binned2深度参考
type: knowledge-doc
created: 2026-04-13
updated: 2026-04-13
source: 多源整合（知乎/CSDN/UE源码）
---

# UE5 内存管理体系：FMalloc / Binned2

> 快照文档 · 面试+工作双用 · 2026-04-13

---

## 一、调用链全景

```
用户代码: new / FMemory::Malloc()
    │
    ▼
FMemory::Malloc(Size, Alignment)     ← 静态工具类
    │
    ▼
GMalloc->Malloc(Size, Alignment)     ← FMalloc* 全局指针
    │
    ├── FMallocBinned2 (默认)
    │     ├── Small Pool (≤MAX_SMALL_POOL_SIZE) → PoolTable/FreeList
    │     └── Large Alloc → FPlatformMemory::BinnedAllocFromOS()
    │
    ├── FMallocBinned3 / FMallocTBB / FMallocAnsi / FMallocMimalloc ...
    │
    ▼
FPlatformMemory
    ├── Windows: VirtualAlloc / VirtualFree
    ├── Linux:   mmap / munmap
    └── iOS:     vm_allocate
```

---

## 二、四种分配器对比

| 分配器 | 原理 | 默认平台 | 性能特点 |
|--------|------|---------|---------|
| **FMallocAnsi** | 直接调 C 标准库 `malloc/free` | 调试/Sanitizer | 最慢但最简单，便于内存检测工具 |
| **FMallocBinned** (Binned1) | Pool + FreeList，固定 bin 大小 | UE4 早期 | 碎片少但 bin 粒度粗 |
| **FMallocBinned2** | 优化版 Pool，更精细的 bin + TLS 缓存 | UE4/5 主流 | ★ 最常用，性能和碎片的最佳平衡 |
| **FMallocBinned3** | 针对大内存优化，更大的 Page | UE5 特定场景 | 大对象分配更快，小对象不如 Binned2 |

---

## 三、Binned2 详解

### 3.1 Pool 大小分级（Size Classes）

```
16, 32, 48, 64, 80, 96, 112, 128,
160, 192, 224, 256, 288, 320, 384, 448,
512, 576, 640, 768, 896, 1024, 1168, 1360,
1632, 2048, 2336, 2720, 3264, 4096, 4672, 5456,
6544, 8192, 9360, 10912, 13104, 16384, 21840, 32768
```

请求的大小**向上取整**到最近的 bin size。如请求 50 字节 → 分配 64 字节的 Block。

### 3.2 Pool 结构

```
┌──────────────────────────────────────┐
│ FPoolTable (每个 Size Class 一个)      │
│  ┌─────────────────────────────────┐ │
│  │ FPoolInfo (Pool Page, ~64KB)     │ │
│  │  ┌───┬───┬───┬───┬───┬───┐     │ │
│  │  │ B │ B │ B │ B │ B │...│     │ │  ← Block: 固定大小分配单元
│  │  └───┴───┴───┴───┴───┴───┘     │ │
│  │  FreeList → B → B → NULL        │ │  ← 空闲链表
│  │  Taken: 已分配块数               │ │
│  └─────────────────────────────────┘ │
│  ┌─────────────────────────────────┐ │
│  │ FPoolInfo (下一个 Pool Page)      │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### 3.3 分配流程

```
Malloc(Size)
  │
  ├─ Size ≤ MAX_SMALL_POOL_SIZE (~32KB)?
  │   ├─ YES → 查找对应 SizeClass 的 PoolTable
  │   │         ├─ TLS 缓存有空闲 Block → 直接取（最快路径）
  │   │         ├─ Pool 有空闲 Block → 从 FreeList 摘取
  │   │         └─ Pool 已满 → BinnedAllocFromOS() 申请新 Page
  │   │
  │   └─ NO  → 大内存：BinnedAllocFromOS()（VirtualAlloc/mmap）
  │
  └─ 返回对齐后的指针
```

### 3.4 释放流程

```
Free(Ptr)
  │
  ├─ 通过地址定位到 FPoolInfo（哈希表查找）
  │   ├─ Block 归还 FreeList
  │   ├─ 整个 Page 全空 → BinnedFreeToOS() 归还 OS
  │   └─ 更新统计
  │
  └─ 大内存 → BinnedFreeToOS()
```

### 3.5 内存对齐

```cpp
#define MIN_ALIGNMENT 16  // Binned2 最小 16 字节对齐

// 大对齐请求的实现
void* AlignedMalloc(SIZE_T Size, uint32 Alignment) {
    void* Raw = Malloc(Size + Alignment + sizeof(void*));
    void* Aligned = Align(Raw + sizeof(void*), Alignment);
    *((void**)Aligned - 1) = Raw;  // 存储原始指针（Free 时用）
    return Aligned;
}
```

---

## 四、UObject 内存分配 vs 普通 C++ 对象

| | UObject | 普通 C++ 对象 |
|---|---|---|
| 分配方式 | `NewObject` → 内部走 GMalloc | `new` → 也走 GMalloc |
| 额外开销 | GUObjectArray 注册 + FObjectInitializer | 无 |
| 回收方式 | GC 标记清除 | 手动 delete 或智能指针 |
| 分配路径 | `FUObjectAllocator::AllocateUObject()` → GMalloc | 直接 GMalloc |

**关键区别**：UObject 的分配大小 = `GetPropertiesSize()` + alignment padding，由反射系统决定；普通对象大小由 `sizeof(T)` 决定。

---

## 五、游戏开发中的内存优化实践

### 5.1 对象池（Object Pool）
```cpp
// UE 内置 ActorPool
UWorld::SpawnActor() + SetActorHiddenInGame()
// 避免反复 SpawnActor/DestroyActor 的 GC 压力

// 自定义对象池
TArray<UObject*> Pool;
UObject* Get() { return Pool.Num() > 0 ? Pool.Pop() : NewObject<...>(); }
void Return(UObject* Obj) { Pool.Push(Obj); }
```

### 5.2 预分配（Reserve）
```cpp
TArray<FVector> Positions;
Positions.Reserve(10000);  // 预分配，避免多次 realloc
```

### 5.3 LLM（Low Level Memory Tracker）
```cpp
LLM_SCOPE(ELLMTag::Meshes);  // 标记内存用途
// 控制台: stat llm → 按 Tag 查看内存占用
```

### 5.4 调试命令
```
stat memory             // 内存概览
stat memoryallocator    // 分配器详细统计
memreport -full         // 完整内存报告（输出到文件）
obj list                // UObject 数量统计
```

---

## 参考资料

- [FMemory/Binned2内存分配器](https://zhuanlan.zhihu.com/p/432893686)
- [万字对比ANSI/Binned1/2/3](https://zhuanlan.zhihu.com/p/564078470)
- [UE5持久化对象池](https://zhuanlan.zhihu.com/p/577189417)
- [MallocBinned源码剖析](https://blog.csdn.net/weixin_30126739/article/details/112070605)
