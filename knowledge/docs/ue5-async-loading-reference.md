# UE5 资源异步加载深度参考

> 搜索日期：2026-04-13
> 核心来源：BoilTask's Blog（基于 UE5.5 源码分析）
> 补充来源：CSDN/知乎多篇 UE5 多线程文章
> 用途：补充 async-resource-loading-preresearch.md，提供源码级细节

---

## 一、FStreamableManager 完整加载流程（5 阶段）

### 阶段 1：请求发起 — RequestAsyncLoadInternal

```cpp
TSharedPtr<FStreamableHandle> FStreamableManager::RequestAsyncLoadInternal(
    TArray<FSoftObjectPath>&& TargetsToStream, 
    FStreamableDelegate&& DelegateToCall, 
    TAsyncLoadPriority Priority, 
    bool bManageActiveHandle, 
    bool bStartStalled, 
    FString&& DebugName)
```

步骤：创建 FStreamableHandle → 验证资源路径 → 管理句柄 → 调用 StartHandleRequests

### 阶段 2：加载处理 — StartHandleRequests

遍历所有资源，逐个调用 StreamInternal，已在内存中的直接标记完成。

### 阶段 3：核心 — StreamInternal

```
资源已在内存？
├── 是 → 直接返回
└── 否 → 创建 FStreamable
         ├── 需同步加载？→ StaticLoadObject
         └── 异步加载 → LoadPackageAsync（提交到加载线程）
```

**强制同步的三种情况**：
1. 游戏初始化阶段
2. 对象构造函数中
3. bForceSynchronousLoads 标志

### 阶段 4：回调 — AsyncLoadCallback

- **必须在主线程**（`check(IsInGameThread())`）
- 标记加载完成 → FindInMemory 查找资源 → CheckCompletedRequests

### 阶段 5：完成检查 — CheckCompletedRequests

所有关联资源加载完成 → 执行用户回调

---

## 二、线程交互模型

```
主线程                              加载线程
  │                                    │
  ├─ RequestAsyncLoad ──────┐          │
  ├─ StartHandleRequests    │          │
  ├─ StreamInternal         │          │
  ├─ LoadPackageAsync ──────┼────→ 接收加载任务
  │                         │     读取磁盘/解析包/加载资源
  │   （继续其他工作）        │          │
  │                         │     加载完成 ──→ 回调通知
  ├─ AsyncLoadCallback ←────┘          │
  ├─ CheckCompletedRequests            │
  └─ 执行用户回调                       │
```

---

## 三、关键类

| 类 | 职责 |
|---|---|
| FStreamableManager | 核心管理类，发起请求、调度、回调 |
| FStreamableHandle | 跟踪单个请求的状态和回调 |
| FStreamable | 跟踪单个资源的加载状态 |
| FSoftObjectPath | 软引用路径 |

---

## 四、依赖自动处理

```
StaticMesh'/Game/Meshes/Sphere.Sphere'
  └── Material'/Game/Materials/Metal.Metal'
        └── Texture2D'/Game/Textures/Metal_Albedo'
```

加载顺序：纹理 → 材质 → 网格 → 用户回调。所有依赖完成后才触发最终通知。

---

## 五、UE5 多线程体系总结

来自多篇文章的综合整理：

### UE5 三种多线程机制

| 机制 | 适用场景 | 特点 |
|------|---------|------|
| **FRunnable** | 独立长期线程 | 最底层，手动管理 |
| **AsyncTask** | 一次性异步任务 | 简单易用，适合资源加载/网络 |
| **TaskGraph** | 复杂依赖任务图 | UE 引擎内部大量使用，高级 |

### AsyncTask 实战模式

```cpp
// 最简单的异步任务
AsyncTask(ENamedThreads::AnyBackgroundThreadNormalTask, [=]()
{
    // 在后台线程执行耗时操作
    LoadHeavyResource();
    
    // 回到主线程更新 UI
    AsyncTask(ENamedThreads::GameThread, [=]()
    {
        UpdateUI();
    });
});
```

### 性能优化要点

| 方向 | 建议 |
|------|------|
| 加载策略 | 批量合并请求、合理优先级、提前预加载 |
| 内存管理 | 及时 ReleaseHandle、优化依赖减少冗余 |
| 错误处理 | 失败回调、超时检测、详细日志 |

---

## 六、与你预研文档的对比

你的 `async-resource-loading-preresearch.md` 中推荐的 Wrapper 方案与 UE5 实际机制的对比：

| 你的设计 | UE5 实际 | 对齐度 |
|---------|---------|:------:|
| 独立 IO 线程 + 消息队列 | LoadPackageAsync → 加载线程 | ✅ 一致 |
| 回调回主线程 | AsyncLoadCallback 必须主线程 | ✅ 一致 |
| 优先级调度 | TAsyncLoadPriority 参数 | ✅ 一致 |
| GC 集成 | FStreamableHandle 管理生命周期 | ⚠️ 你的设计需要补充 |

**建议**：入职后重点看 FStreamableHandle 如何与 UE GC 交互——这是你预研中相对薄弱的部分。

---
## 更新日志
- 2026-04-13: 初始创建，基于 UE5.5 源码分析文章和多篇技术博客
