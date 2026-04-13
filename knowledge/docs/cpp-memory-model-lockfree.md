# C++ 内存模型与无锁编程深度参考（交叉验证整合版）

> 整合日期：2026-04-13
> 来源：6 篇高质量文章交叉验证（详见 resource-links.md 第八类）
> 用途：面试准备（最高优先级短板）+ 入职技术储备
> 深度：能应对 3 层追问 + 附完整代码示例

---

## 一、为什么需要内存模型？

三个层面的重排风险：
1. **编译器优化**：可能重排无依赖的指令
2. **CPU 乱序执行**：超标量流水线可能改变内存操作的可见顺序
3. **多核缓存不一致**：各核心的 L1/L2 cache 不一定及时同步（MESI 协议延迟）

C++11 引入 `<atomic>` 和 memory order，让程序员精确控制多线程间内存操作的可见性和顺序。

---

## 二、两个核心关系

### 2.1 Happens-Before（先行发生）

如果操作 A **happens-before** 操作 B，则 A 的效果对 B **可见**。

```
Happens-Before = Sequenced-Before（线程内程序顺序）
               + Synchronizes-With（线程间同步）
               + 传递性
```

### 2.2 Synchronizes-With（同步关系）

一个线程的 **release 写**，与另一个线程对同一原子变量的 **acquire 读**（且读到了那个值）之间建立同步关系。

```cpp
// 线程 A
data = 42;                                    // (1)
flag.store(true, std::memory_order_release);  // (2) release 写

// 线程 B
while (!flag.load(std::memory_order_acquire)); // (3) acquire 读
assert(data == 42);                            // (4) ✅ 保证成功

// 关系链：(1) seq-before (2), (2) sync-with (3), (3) seq-before (4)
// 因此 (1) happens-before (4)
```

---

## 三、六种 Memory Order 详解

### 速查表

| Memory Order | 类型 | 强度 | 用途 |
|---|---|---|---|
| `relaxed` | 无序 | 最弱 | 计数器、统计（仅保证原子性） |
| `consume` | 消费 | 弱 | **不要使用**（编译器退化为 acquire） |
| `acquire` | 获取 | 中 | load 端：后面的操作不上移 ↓ |
| `release` | 释放 | 中 | store 端：前面的操作不下移 ↑ |
| `acq_rel` | 获取+释放 | 较强 | RMW 操作（CAS 等） |
| `seq_cst` | 顺序一致 | 最强 | 默认值，全局全序，最安全 |

### 形象理解

```
              读/写操作 A
              读/写操作 B
              ↑ 前面的操作不下移（release 屏障）
         ═══════ release store ═══════

         ═══════ acquire load ═══════
              ↓ 后面的操作不上移（acquire 屏障）
              读/写操作 C
              读/写操作 D
```

### 选择决策树

```
需要多线程排序保证吗？
  否 → relaxed
  是 → 需要全局一致顺序吗？
         是 → seq_cst
         否 → 操作类型？
               load  → acquire
               store → release
               RMW   → acq_rel
```

---

## 四、无锁编程核心概念

### Lock-Free vs Wait-Free

| 特性 | Lock-Free（无锁） | Wait-Free（无等待） |
|------|-------------------|---------------------|
| 保证 | **至少一个**线程能在有限步完成 | **每个**线程都能在有限步完成 |
| 实现 | CAS 循环重试 | 极复杂 |
| 实际应用 | 广泛 | 极少 |

### CAS（Compare-And-Swap）原理

```cpp
// 伪代码
bool CAS(atomic<T>& target, T& expected, T desired) {
    if (target == expected) {
        target = desired;
        return true;   // 成功
    } else {
        expected = target; // 失败，更新 expected 为当前值
        return false;       // 调用者重试
    }
}
// 整个操作是硬件原子的（x86: LOCK CMPXCHG）
```

### compare_exchange_weak vs strong

| | weak | strong |
|---|---|---|
| 虚假失败 | 可能（即使值相等也可能返回 false） | 不会 |
| 性能 | 更快（ARM 上明显） | 略慢 |
| 适用 | 循环中使用 | 单次判断 |

---

## 五、实战代码

### 5.1 无锁栈（Lock-Free Stack）

```cpp
template<typename T>
class LockFreeStack {
    struct Node {
        T data;
        Node* next;
        Node(const T& val) : data(val), next(nullptr) {}
    };
    std::atomic<Node*> head_{nullptr};

public:
    void push(const T& val) {
        Node* new_node = new Node(val);
        new_node->next = head_.load(std::memory_order_relaxed);
        while (!head_.compare_exchange_weak(
            new_node->next, new_node,
            std::memory_order_release,    // 成功：release
            std::memory_order_relaxed     // 失败：relaxed
        )) {}  // CAS 失败自动重试，new_node->next 已被更新
    }

    bool pop(T& result) {
        Node* old_head = head_.load(std::memory_order_acquire);
        while (old_head && !head_.compare_exchange_weak(
            old_head, old_head->next,
            std::memory_order_acq_rel,
            std::memory_order_acquire
        )) {}
        if (!old_head) return false;
        result = old_head->data;
        delete old_head;  // ⚠️ 简化处理，生产环境需 hazard pointer
        return true;
    }
};
```

### 5.2 自旋读写锁

```cpp
class SpinRWLock {
    // 0 = 无锁, 正数N = N个读者, -1 = 1个写者
    std::atomic<int> state_{0};

public:
    void read_lock() {
        int expected;
        do {
            expected = state_.load(std::memory_order_relaxed);
            if (expected < 0) expected = 0;  // 等写者释放
        } while (!state_.compare_exchange_weak(
            expected, expected + 1,
            std::memory_order_acquire, std::memory_order_relaxed));
    }
    void read_unlock()  { state_.fetch_sub(1, std::memory_order_release); }

    void write_lock() {
        int expected = 0;
        while (!state_.compare_exchange_weak(
            expected, -1,
            std::memory_order_acquire, std::memory_order_relaxed))
            expected = 0;
    }
    void write_unlock() { state_.store(0, std::memory_order_release); }
};
```

### 5.3 与 UE 的关联（面试必考）

| C++ 标准 | UE 封装 | 说明 |
|---------|---------|------|
| `std::mutex` | `FCriticalSection` | 平台抽象互斥锁 |
| `std::condition_variable` | `FEvent` | 平台抽象条件变量 |
| `std::atomic` | `TAtomic` / `FThreadSafeCounter` | UE 原子封装 |
| `std::thread` | `FRunnable + FRunnableThread` | UE 线程抽象 |
| `std::async` | `AsyncTask` / `Async()` | UE 异步任务 |
| 线程池 | `GThreadPool (FQueuedThreadPool)` | 引擎全局线程池 |
| DAG 调度 | TaskGraph | UE 特有的任务依赖调度 |

---

## 六、性能对比参考

```
线程数: 1  | 无锁栈: ~12ms | 互斥锁栈: ~19ms | 加速比: 1.5x
线程数: 2  | 无锁栈: ~25ms | 互斥锁栈: ~58ms | 加速比: 2.3x
线程数: 4  | 无锁栈: ~49ms | 互斥锁栈: ~156ms | 加速比: 3.2x
线程数: 8  | 无锁栈: ~95ms | 互斥锁栈: ~413ms | 加速比: 4.3x

结论：线程数越多，无锁方案优势越明显（锁竞争加剧导致互斥锁性能骤降）
```

---

## 七、面试速记

```
Q: memory_order 有几种？分别什么意思？
A: 6 种。relaxed 只保证原子性；acquire/release 配对建立 happens-before；
   acq_rel 用于 RMW；seq_cst 全局全序最强最安全。consume 别用。

Q: 什么是 CAS？
A: Compare-And-Swap，硬件原子操作。比较当前值和期望值，相等则写入新值，
   不等则返回当前值。是所有无锁数据结构的基础。

Q: 无锁编程的难点是什么？
A: ① ABA 问题（版本号/tagged pointer 解决）
   ② 内存回收（hazard pointer / epoch-based reclamation）
   ③ 正确选择 memory order（错误选择→未定义行为，且难复现）

Q: UE 中怎么做多线程？
A: 三层：FRunnable（底层手动）→ AsyncTask（线程池）→ TaskGraph（DAG 调度）。
   渲染线程是 TaskGraph 的命名线程，通过 ENQUEUE_RENDER_COMMAND 通信。
   关键规则：非 GameThread 不能访问 UObject。
```

---

*基于 6 篇文章交叉验证。⚠️ memory_order_consume 在所有主流编译器中退化为 acquire，不要使用。*
