# UE C++ Code Review 检查清单

> UE 引擎开发专用，按严重程度分级
> 生成日期：2026-04-13

---

## 🔴 内存安全

| # | 检查点 | 为什么重要 | ❌ 错误示例 | ✅ 正确示例 |
|---|--------|-----------|-----------|-----------|
| M1 | UObject* 成员是否标记 UPROPERTY | 未标记的指针 GC 不追踪，对象可能被回收导致悬垂指针 | `UMyData* Data;` | `UPROPERTY() UMyData* Data;` |
| M2 | 非 UObject 类持有 UObject 引用是否用 FGCObject | 同 M1，GC 不知道你的引用 | 普通类直接存 `UObject*` | 继承 `FGCObject` 并重写 `AddReferencedObjects` |
| M3 | NewObject 的 Outer 是否正确 | Outer 为空时对象可能过早被 GC | `NewObject<T>(nullptr)` | `NewObject<T>(GetTransientPackage())` 或传入有意义的 Outer |
| M4 | 是否有裸 new/delete 用于 UObject | UObject 必须用 NewObject，不能用 C++ new | `new UMyActor()` | `NewObject<UMyActor>(Outer)` |
| M5 | TSharedPtr 是否管理了 UObject | 双重释放（GC + 引用计数） | `TSharedPtr<UMyData> Ptr` | UObject 用 UPROPERTY，非 UObject 用 TSharedPtr |
| M6 | 数组/容器 out-of-bounds | Crash | `Array[Index]` 无检查 | `Array.IsValidIndex(Index)` 或 `Array[FMath::Clamp(...)]` |
| M7 | FString/FName 使用后的生命周期 | `*FString` 返回的 TCHAR* 是临时的 | 存储 `*TempString` 到 `const TCHAR*` | 存储 FString 本身，需要时再取 `*` |

## 🔴 线程安全

| # | 检查点 | 为什么重要 | ❌ 错误示例 | ✅ 正确示例 |
|---|--------|-----------|-----------|-----------|
| T1 | 非 GameThread 是否访问了 UObject | UObject 操作非线程安全 | AsyncTask 内调用 `SpawnActor` | AsyncTask 中只处理数据，回到 GameThread 操作 UObject |
| T2 | 共享数据是否有锁保护 | 数据竞争 → 随机 crash | 两个线程直接读写同一 TArray | `FCriticalSection` 或 `FRWScopeLock` |
| T3 | Delegate 是否在正确线程 Broadcast | Delegate 非线程安全 | IO 线程 `OnComplete.Broadcast()` | `AsyncTask(GameThread, [=]{ OnComplete.Broadcast(); })` |
| T4 | 多锁是否有统一顺序 | 死锁 | A 先锁 m1 再 m2，B 先锁 m2 再 m1 | 统一按地址排序加锁，或用 `FScopeLock` 单锁 |
| T5 | Atomic 变量的 memory_order 是否正确 | 指令重排导致可见性问题 | `bReady.store(true, relaxed)` 配合非 atomic 数据 | `bReady.store(true, release)` + `bReady.load(acquire)` |

## 🟡 性能

| # | 检查点 | 为什么重要 | ❌ 错误示例 | ✅ 正确示例 |
|---|--------|-----------|-----------|-----------|
| P1 | 是否有不必要的拷贝 | 大对象拷贝开销大 | `FString Name = GetName();` 在循环中 | `const FString& Name = GetName();` |
| P2 | Tick 中是否有 O(N²) 逻辑 | 随实体数增加卡顿 | Tick 中双层循环碰撞检测 | 用空间划分降到 O(NlogN) 或 O(N) |
| P3 | 是否在 Tick 中做了查找 | FindActor/FindComponent 有遍历开销 | `Tick() { FindComponentByClass<>() }` | 在 BeginPlay 缓存引用 |
| P4 | TArray 是否有预分配 | 频繁扩容导致内存拷贝 | 不断 `Array.Add()` | `Array.Reserve(ExpectedSize)` |
| P5 | 是否有大对象按值传递 | 函数调用开销 | `void Func(TArray<FVector> Data)` | `void Func(const TArray<FVector>& Data)` |
| P6 | 字符串操作是否高效 | FString 拼接会反复分配 | 循环中 `Result += Item;` | `TStringBuilder<256>` 或预分配 `FString::Reserve` |
| P7 | 是否有不必要的动态转型 | Cast<T> 有开销 | Tick 中反复 `Cast<AMyActor>(Actor)` | BeginPlay 中缓存转型结果 |

## 🟡 UE 规范

| # | 检查点 | 为什么重要 | ❌ 错误示例 | ✅ 正确示例 |
|---|--------|-----------|-----------|-----------|
| U1 | 命名是否遵循 UE 规范 | 团队一致性 | `bool isReady; int hp;` | `bool bIsReady; int32 HP;` |
| U2 | UFUNCTION 的 Specifier 是否正确 | 蓝图可见性控制 | 应该 BlueprintPure 的函数标记为 BlueprintCallable | 纯函数用 `BlueprintPure`，有副作用用 `BlueprintCallable` |
| U3 | UPROPERTY 的 Category 是否设置 | 编辑器面板混乱 | `UPROPERTY(EditAnywhere)` 无 Category | `UPROPERTY(EditAnywhere, Category="Combat")` |
| U4 | 是否使用了 UE 的类型而非 std | 混用导致序列化/反射问题 | `std::string, std::vector` | `FString, TArray` |
| U5 | 日志是否有正确的 Category | 过滤困难 | `UE_LOG(LogTemp, ...)` 到处用 | 定义专属 `DECLARE_LOG_CATEGORY_EXTERN` |

## 🟢 可维护性

| # | 检查点 | 为什么重要 | 改进建议 |
|---|--------|-----------|---------|
| R1 | 函数是否超过 50 行 | 可读性差 | 拆分为子函数，每个有明确职责 |
| R2 | 类是否有超过 10 个公共方法 | 职责过多（God Class） | 考虑拆分为多个类或使用 Subsystem |
| R3 | 是否有魔法数字 | 含义不清 | 提取为 `constexpr` 常量或配置项 |
| R4 | 注释是否解释"为什么"而非"做什么" | 代码本身说明做什么，注释应解释决策 | `// 使用 128 因为超过此值性能下降明显（见 Profiler 截图 #42）` |
| R5 | 是否有合适的错误处理 | 静默失败最危险 | `check()` 用于不应该发生的、`ensure()` 用于可恢复的、`UE_LOG` 用于可预期的 |

---

# 技术博客写作模板体系

## 模板 1: 源码分析型

```markdown
# [模块名] 源码分析：[具体主题]

## 一、为什么读这段源码
[动机：遇到了什么问题 / 面试需要 / 好奇心]

## 二、整体架构
[模块在引擎中的位置，和其他模块的关系]
[关键类和它们的关系（文字版类图）]

## 三、核心流程
[用时序/流程的方式描述核心逻辑]
[配合关键代码片段]

## 四、设计意图
[作者为什么这样设计？做了什么取舍？]
[和其他常见实现方案的对比]

## 五、收获与关联
[学到了什么？和已有知识怎么关联？]
[如果我来设计会怎么做？]

## 附录
- 文件路径：
- UE 版本：
- 参考资料：
```

## 模板 2: 系统设计型

```markdown
# [系统名] 设计方案

## 一、背景与目标
- 要解决什么问题
- 性能/功能/可维护性目标

## 二、方案调研
| 方案 | 核心思路 | 优点 | 缺点 |
|------|---------|------|------|

## 三、选定方案详细设计
### 3.1 模块划分
### 3.2 核心数据结构
### 3.3 关键接口
### 3.4 数据流
### 3.5 线程模型（如适用）

## 四、关键技术决策
[每个有争议的决策：选了什么、为什么、备选方案]

## 五、风险与应对
| 风险 | 影响 | 应对 |
|------|------|------|

## 六、测试方案
## 七、排期
```

## 模板 3: Bug 复盘型

```markdown
# Bug 复盘：[Bug 简述]

## 现象
[具体表现、频率、环境]

## 排查过程
1. [第一步假设 → 验证结果]
2. [第二步假设 → 验证结果]
3. ...

## 根因
[准确描述 root cause]

## 修复方案
[代码改动 + 理由]

## 复盘
- 为什么没有在开发阶段发现？
- 以后怎么预防同类问题？
- 有没有类似的潜在风险需要排查？
```

## 模板 4: 面试总结型

```markdown
# [公司] [岗位] 面试总结

## 基本信息
- 日期：
- 轮次：
- 面试官风格：[追问型 / 广度型 / 项目型]

## 题目与表现
| 题目 | 我的回答 | 评价 | 标准答案/改进 |
|------|---------|------|-------------|

## 暴露的弱点
1. [弱点 + 改进计划]

## 做得好的地方
1. [亮点]

## Action Items
- [ ] [具体改进行动]
```

## 模板 5: 周报型

```markdown
# Week [N] 工作总结

## 本周完成
- [任务1]: [完成情况 + 结果]
- [任务2]: ...

## 进行中
- [任务]: [进度% + 下周计划]

## 阻塞项
- [问题]: [需要谁帮忙 / 什么资源]

## 技术积累
- [本周学到了什么值得记录的]

## 下周计划
1.
2.
3.
```
