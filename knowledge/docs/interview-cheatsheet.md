# 面试速查卡：UE 引擎 + C++ 多线程

> 面试前 30 分钟快速过一遍。每个知识点一句话口语化表述 + 追问关键词。

---

## UE 引擎核心机制

### UObject 系统
- **一句话**：UE 所有游戏对象的基类，提供反射、序列化、GC、网络同步四大能力
- **CDO**：Class Default Object，每个 UClass 有一个，所有实例的属性初始值从 CDO 复制
- **Outer/Inner**：UObject 的树形归属关系，GC 用它判断"这个对象属于谁"
- **NewObject 流程**：分配内存→拷贝CDO→调用构造→注册到GC系统
- 🎯 追问：CDO 什么时候创建？→ UClass 注册时（引擎启动阶段）

### 反射 / 属性系统
- **一句话**：UHT 扫描 UPROPERTY/UFUNCTION 宏，生成 .generated.h，运行时通过 UField 链表遍历属性
- **蓝图调用C++链路**：BP节点→UFunction→FindFunction→ProcessEvent→NativeFunc指针
- 🎯 追问：反射的性能代价？→ FindFunction 是字符串哈希查找，热路径避免

### GC 系统
- **一句话**：标记-清除，从 Root Set 出发标记所有可达 UObject，未标记的清除
- **GC 簇**：把一组关联对象打包成簇，标记时整簇一起，减少遍历
- **MarkAsGarbage vs MarkPendingKill**：5.0 后 PendingKill 废弃，用 MarkAsGarbage
- **弱引用**：TWeakObjectPtr 不阻止GC，访问前必须 IsValid()
- 🎯 追问：GC 会卡主线程吗？→ 会，增量标记缓解但不能完全消除

### Subsystem
- **一句话**：UE 官方的"托管单例"，生命周期跟随 Owner（Engine/Editor/GameInstance/World/LocalPlayer）
- **vs 全局单例**：Subsystem 有生命周期管理、支持 PIE 多实例、可蓝图访问
- 🎯 追问：什么时候不该用 Subsystem？→ 跨 World 共享数据时（用 EngineSubsystem 或 GameInstanceSubsystem）

### Delegate
- **单播**：一对一绑定，FDelegate
- **多播**：一对多广播，FMulticastDelegate
- **动态代理**：支持蓝图绑定，有字符串开销
- 🎯 追问：多播线程安全吗？→ 不安全，Broadcast 和 Add/Remove 不能并发

### 资源管理
- **SoftObjectPtr**：只存路径，不自动加载，需要手动 LoadSynchronous 或 RequestAsyncLoad
- **异步加载链路**：RequestAsyncLoad→FAsyncPackage→FAsyncLoadingThread→IO→反序列化→GameThread PostLoad
- 🎯 追问：为什么 PostLoad 必须在 GameThread？→ 可能创建 UObject、触发 GC、修改世界状态

### 多线程
- **三线程模型**：GameThread（逻辑）+ RenderThread（渲染命令生成）+ RHIThread（GPU提交）
- **TaskGraph**：基于 DAG 的任务调度，Task 声明依赖→调度器自动并行
- **FRunnable**：最底层的线程封装，需要手动管理生命周期
- 🎯 追问：Game 和 Render 怎么同步？→ 双缓冲 + FRenderCommandFence

### 智能指针
- **TSharedPtr**：引用计数，线程安全（ ESPMode::ThreadSafe ）
- **TWeakPtr**：配合 TSharedPtr 使用，不增加引用计数，Pin() 后才能用
- **vs UObject GC 指针**：UObject 必须用 UPROPERTY，不要用 TSharedPtr 管 UObject
- 🎯 追问：TSharedPtr 的引用计数是原子的吗？→ ThreadSafe 模式下是，默认 NotThreadSafe

### 模块系统
- **加载顺序**：引擎模块→插件模块→项目模块，每个模块 StartupModule() 中初始化
- **Module vs Plugin**：Plugin 是可以开关的模块集合，Module 是代码组织单元
- 🎯 追问：如何控制模块加载顺序？→ .uproject/.uplugin 的 Dependencies 字段

---

## C++ 多线程

### 基础概念速记
- **线程 vs 进程**：进程有独立地址空间，线程共享进程的堆但有独立栈
- **竞态条件**：多线程读写共享数据且至少一个写，结果依赖执行顺序
- **死锁四条件**：互斥 + 持有并等待 + 不可抢占 + 循环等待（破坏任一即可）

### std 库核心 API
- **std::thread**：构造即启动，必须 join() 或 detach()，否则析构 terminate
- **std::mutex**：lock/unlock，不可重入。recursive_mutex 可重入但性能差
- **lock_guard**：RAII 锁，构造加锁析构解锁，不能手动控制
- **unique_lock**：RAII 锁，可以 defer_lock + 手动 lock/unlock，配合 condition_variable 用
- **scoped_lock(C++17)**：原子锁多个 mutex，**解决死锁的最优方案**
- **condition_variable**：wait + notify，**必须配合 unique_lock + while 循环**（防虚假唤醒）
- **future/promise**：一次性通信管道。promise.set_value → future.get
- **async**：最简单的异步执行，返回 future，注意 launch::async vs launch::deferred

### atomic & memory_order（面试重灾区）
- **std::atomic**：对基础类型的原子操作，不需要 mutex
- **memory_order 速记**：
  - `seq_cst`（默认）：最严格，全序一致，性能最差，**面试答这个最安全**
  - `acquire/release`：生产者 release 写，消费者 acquire 读，保证因果序
  - `relaxed`：只保证原子性，不保证顺序，用于纯计数器
- 🎯 追问：什么时候该用 relaxed？→ 统计计数器、引用计数（不依赖其他数据的场景）

### 经典并发结构
- **线程池**：固定线程数 + 任务队列 + condition_variable 通知。预分配线程避免频繁创建销毁
- **无锁队列**：CAS (compare_exchange) 实现入队出队，ABA 问题用版本号解决
- **读写锁(shared_mutex)**：多读一写，读多写少场景性能好
- **Double-checked locking**：经典错误——不加 memory_order 会被指令重排破坏，用 atomic + acquire/release 修复

### 游戏引擎中的多线程
- **Job System vs TaskGraph**：Job 是简单的 fork-join，TaskGraph 支持复杂 DAG 依赖
- **渲染线程同步**：Game 生成渲染命令→放入命令队列→Render 消费执行→Fence 同步
- **异步加载线程模型**：IO 线程读文件（IO bound）→ 序列化线程反序列化（CPU bound）→ GameThread PostLoad
- **ECS 多线程**：按 Archetype/Chunk 分组并行，System 声明读写 Component 类型→调度器自动判断可并行的 System

---

## 系统设计四步法速查

面试被问系统设计时，**严格按这四步走**：

```
1. 拆模块：这个系统可以拆成哪几个独立职责的模块？
2. 定数据：每个模块需要什么数据结构？模块间传什么数据？
3. 画交互：模块之间怎么通信？（事件/消息/直接调用/共享数据）
4. 走流程：用一个具体场景，从头到尾走一遍数据流
```

**表达技巧**：先说整体（"这个系统我会拆成 X 个模块"），再说细节（"核心模块是 A，负责..."），最后走流程验证。

---

> 最后提醒：面试时每个回答控制在 30-60 秒。面试官追问才展开细节。
> 如果不确定，说"我的理解是 XX，但具体实现可能因版本而异，需要看源码确认"。
