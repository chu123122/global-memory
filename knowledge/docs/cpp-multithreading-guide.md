# C++ 多线程/并发编程完整知识体系

> 目标：游戏引擎 C++ 开发面试准备
> 深度：每个概念附代码示例 + 面试话术
> 生成日期：2026-04-13

---

## 第一章：基础概念

### 1.1 线程 vs 进程 vs 协程

| | 进程 | 线程 | 协程 |
|-|------|------|------|
| 内存空间 | 独立 | 共享 | 共享 |
| 切换开销 | 大（页表切换） | 中（内核态切换） | 小（用户态切换） |
| 创建开销 | 大 | 中 | 极小 |
| 通信方式 | IPC（管道/共享内存/Socket） | 直接读写共享内存 | 直接读写 |
| 并发/并行 | 真并行 | 真并行 | 并发（单线程内交替） |
| 典型用途 | 进程隔离（浏览器多标签） | CPU 密集并行（游戏多线程） | IO 密集（网络请求、UI） |

**面试话术**：
> 进程是资源分配的最小单位，线程是 CPU 调度的最小单位。游戏引擎用多线程而非多进程，因为线程间共享内存——渲染线程可以直接读取游戏线程写入的 Transform 数据，而进程间通信开销太大。协程是用户态调度，适合 IO 密集但不适合 CPU 密集——游戏中常见于异步加载 callback 链的简化（UE 的 Latent Action、Unity 的 Coroutine）。

### 1.2 竞态条件（Race Condition）

当两个线程同时读写同一数据且至少一个在写时，结果取决于执行顺序——这就是竞态条件。

```cpp
// ❌ 竞态条件
int counter = 0;

void ThreadA() { for (int i = 0; i < 10000; i++) counter++; }
void ThreadB() { for (int i = 0; i < 10000; i++) counter++; }
// 结果不一定是 20000，因为 counter++ 不是原子操作
// counter++ = read → increment → write，三步可能被打断

// ✅ 修复：用 mutex
std::mutex mtx;
void ThreadA() { 
    for (int i = 0; i < 10000; i++) {
        std::lock_guard<std::mutex> lock(mtx);
        counter++; 
    }
}

// ✅ 修复：用 atomic
std::atomic<int> counter{0};
void ThreadA() { for (int i = 0; i < 10000; i++) counter.fetch_add(1); }
```

### 1.3 死锁（Deadlock）

四个必要条件（**缺一不可**）：
1. **互斥**：资源不可共享
2. **持有并等待**：持有一个锁的同时等待另一个锁
3. **不可抢占**：锁不能被强制释放
4. **循环等待**：A 等 B，B 等 A

```cpp
// ❌ 经典死锁
std::mutex m1, m2;
void ThreadA() { std::lock_guard a(m1); std::lock_guard b(m2); } // 先锁 m1 再锁 m2
void ThreadB() { std::lock_guard a(m2); std::lock_guard b(m1); } // 先锁 m2 再锁 m1

// ✅ 修复方案1：统一加锁顺序
void ThreadA() { std::lock_guard a(m1); std::lock_guard b(m2); }
void ThreadB() { std::lock_guard a(m1); std::lock_guard b(m2); } // 也先锁 m1

// ✅ 修复方案2：std::scoped_lock（C++17，同时锁定，内部用 try-and-back-off 避免死锁）
void ThreadA() { std::scoped_lock lock(m1, m2); }
void ThreadB() { std::scoped_lock lock(m1, m2); }
```

### 1.4 活锁和饥饿

- **活锁**：两个线程不断"礼让"对方，都无法前进（类似两人走廊让路）
- **饥饿**：低优先级线程永远得不到资源（高优先级线程持续抢占）

**面试话术**：
> 死锁是两个线程互相等待，谁都不动；活锁是两个线程互相让步，谁都在动但都没进展。解决活锁的方法是引入随机退避。饥饿的解决方法是公平锁（FIFO 排队）。

---

## 第二章：C++ std 库多线程

### 2.1 std::thread

```cpp
#include <thread>

void Worker(int id, const std::string& name)
{
    std::cout << "Thread " << id << ": " << name << std::endl;
}

int main()
{
    std::thread t1(Worker, 1, "Alpha");
    std::thread t2(Worker, 2, "Beta");
    
    // 必须 join 或 detach，否则析构时 std::terminate
    t1.join();    // 阻塞等待 t1 完成
    t2.detach();  // 放手让 t2 自己跑（⚠️ 主线程结束后 t2 也会被杀）
    
    // 硬件并发数
    unsigned int n = std::thread::hardware_concurrency(); // 通常 = CPU 核心数
}
```

**面试追问**：join 和 detach 的区别？
> join 阻塞当前线程直到目标线程完成——保证同步。detach 让线程独立运行，不再关联——但如果主线程先退出，detached 线程也会被强制终止，可能导致资源泄漏。**生产代码几乎不用 detach**。

### 2.2 std::mutex 家族

```cpp
#include <mutex>

// 基础 mutex
std::mutex mtx;
mtx.lock();     // 阻塞直到获取锁
mtx.unlock();   // 释放锁
mtx.try_lock(); // 尝试获取锁，失败返回 false（不阻塞）

// recursive_mutex：同一线程可以多次 lock（必须 unlock 相同次数）
std::recursive_mutex rmtx;
void Recursive(int depth)
{
    std::lock_guard<std::recursive_mutex> lock(rmtx);
    if (depth > 0) Recursive(depth - 1); // 不会死锁
}

// timed_mutex：支持超时
std::timed_mutex tmtx;
if (tmtx.try_lock_for(std::chrono::milliseconds(100)))
{
    // 100ms 内获取到了锁
    tmtx.unlock();
}
```

### 2.3 RAII 锁

```cpp
// lock_guard：构造加锁，析构解锁，不可手动控制
{
    std::lock_guard<std::mutex> lock(mtx);
    // 临界区
} // 自动解锁

// unique_lock：更灵活，支持延迟加锁、手动解锁、配合 condition_variable
{
    std::unique_lock<std::mutex> lock(mtx, std::defer_lock); // 不立即加锁
    lock.lock();    // 手动加锁
    // ...
    lock.unlock();  // 手动解锁
    // ...
    lock.lock();    // 可以重新加锁
} // 析构时如果持有锁则解锁

// scoped_lock（C++17）：同时锁多个 mutex，防死锁
{
    std::scoped_lock lock(mtx1, mtx2, mtx3); // 原子地同时锁定
}
```

**面试话术**：
> lock_guard 最轻量，适合简单临界区。unique_lock 更灵活但开销略大，必须用它的场景：(1) 配合 condition_variable.wait()（wait 需要 unlock/lock）；(2) 需要延迟加锁或中途解锁。scoped_lock 专门解决多锁死锁问题。

### 2.4 std::condition_variable

```cpp
#include <condition_variable>

std::mutex mtx;
std::condition_variable cv;
std::queue<int> dataQueue;
bool done = false;

// 生产者
void Producer()
{
    for (int i = 0; i < 10; i++)
    {
        {
            std::lock_guard<std::mutex> lock(mtx);
            dataQueue.push(i);
        }
        cv.notify_one(); // 唤醒一个等待线程
    }
    {
        std::lock_guard<std::mutex> lock(mtx);
        done = true;
    }
    cv.notify_all(); // 唤醒所有等待线程
}

// 消费者
void Consumer()
{
    while (true)
    {
        std::unique_lock<std::mutex> lock(mtx); // ⚠️ 必须用 unique_lock
        cv.wait(lock, [&]{ return !dataQueue.empty() || done; }); // 防虚假唤醒
        
        while (!dataQueue.empty())
        {
            int val = dataQueue.front();
            dataQueue.pop();
            lock.unlock();       // 处理数据时不持锁
            Process(val);
            lock.lock();
        }
        
        if (done && dataQueue.empty()) break;
    }
}
```

**虚假唤醒（Spurious Wakeup）**：
> 操作系统可能在没有 notify 的情况下唤醒 wait 的线程——这是 POSIX 规范允许的优化。所以 **wait 必须用 predicate 版本**（带 Lambda），每次唤醒都检查条件是否真的满足。

### 2.5 std::future / std::promise / std::async

```cpp
#include <future>

// async：最简单的异步执行
std::future<int> fut = std::async(std::launch::async, []() {
    std::this_thread::sleep_for(std::chrono::seconds(1));
    return 42;
});
int result = fut.get(); // 阻塞直到结果就绪

// promise + future：手动设置结果
std::promise<std::string> prom;
std::future<std::string> fut = prom.get_future();

std::thread t([&prom]() {
    try {
        std::string result = DoHeavyWork();
        prom.set_value(result);       // 设置结果
    } catch (...) {
        prom.set_exception(std::current_exception()); // 传递异常
    }
});
std::string val = fut.get(); // 获取结果（如果有异常则抛出）
t.join();

// packaged_task：把函数包装成可异步调用的任务
std::packaged_task<int(int, int)> task([](int a, int b) { return a + b; });
std::future<int> fut = task.get_future();
std::thread t(std::move(task), 3, 4);
int result = fut.get(); // 7
t.join();
```

**面试话术**：
> async 是最方便的"提交一个任务拿到结果"的方式。promise/future 是底层机制——promise 是写端，future 是读端，用于线程间传递单次结果。packaged_task 把 callable 包装成 promise+callable 的组合体，适合丢进线程池。

### 2.6 std::atomic 与 memory_order

```cpp
#include <atomic>

std::atomic<int> counter{0};
std::atomic<bool> ready{false};

// 基本操作（默认 memory_order_seq_cst，最强语义）
counter.store(42);
int val = counter.load();
int old = counter.exchange(100);            // 原子交换，返回旧值
counter.fetch_add(1);                       // 原子加
bool ok = counter.compare_exchange_strong(expected, desired); // CAS

// memory_order 详解
// ┌─────────────────────────────────────────────────┐
// │ seq_cst  ← 最强，全局顺序一致（默认，最安全最慢）     │
// │ acq_rel  ← acquire + release 的组合              │
// │ release  ← store 时使用：本线程之前的写 对 acquire 可见 │
// │ acquire  ← load 时使用：看到 release 之前的所有写     │
// │ relaxed  ← 最弱，只保证原子性，不保证顺序             │
// └─────────────────────────────────────────────────┘

// 经典用法：无锁的"生产者-消费者"标志位
std::atomic<bool> dataReady{false};
int data = 0; // 非 atomic

void Producer()
{
    data = 42;                                    // 普通写
    dataReady.store(true, std::memory_order_release); // release：保证 data=42 在此之前完成
}

void Consumer()
{
    while (!dataReady.load(std::memory_order_acquire)) {} // acquire：看到 true 时，data=42 也可见
    assert(data == 42); // ✅ 保证成立
}
```

**面试话术（memory_order）**：
> 默认 seq_cst 最安全但最慢——所有线程看到相同的操作顺序。release/acquire 配对是性能和安全的平衡点：release 保证之前的写对 acquire 可见。relaxed 只保证原子性——适合纯计数器（不关心和其他变量的顺序关系）。游戏引擎中 95% 的场景用 seq_cst 就够了，只有性能热点才需要降级。

---

## 第三章：经典并发数据结构

### 3.1 线程安全队列（基于锁）

```cpp
template<typename T>
class ThreadSafeQueue
{
    std::queue<T> queue_;
    mutable std::mutex mtx_;
    std::condition_variable cv_;
    
public:
    void Push(T value)
    {
        {
            std::lock_guard<std::mutex> lock(mtx_);
            queue_.push(std::move(value));
        }
        cv_.notify_one();
    }
    
    // 阻塞等待
    T WaitAndPop()
    {
        std::unique_lock<std::mutex> lock(mtx_);
        cv_.wait(lock, [this]{ return !queue_.empty(); });
        T value = std::move(queue_.front());
        queue_.pop();
        return value;
    }
    
    // 非阻塞
    bool TryPop(T& value)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        if (queue_.empty()) return false;
        value = std::move(queue_.front());
        queue_.pop();
        return true;
    }
    
    bool Empty() const
    {
        std::lock_guard<std::mutex> lock(mtx_);
        return queue_.empty();
    }
};
```

### 3.2 无锁栈（CAS 实现）

```cpp
template<typename T>
class LockFreeStack
{
    struct Node
    {
        T data;
        Node* next;
        Node(T val) : data(std::move(val)), next(nullptr) {}
    };
    
    std::atomic<Node*> head_{nullptr};
    
public:
    void Push(T value)
    {
        Node* newNode = new Node(std::move(value));
        newNode->next = head_.load(std::memory_order_relaxed);
        // CAS：如果 head 还是 newNode->next，就把 head 换成 newNode
        while (!head_.compare_exchange_weak(
            newNode->next, newNode,
            std::memory_order_release,
            std::memory_order_relaxed)) {}
    }
    
    bool Pop(T& result)
    {
        Node* oldHead = head_.load(std::memory_order_relaxed);
        while (oldHead && !head_.compare_exchange_weak(
            oldHead, oldHead->next,
            std::memory_order_acquire,
            std::memory_order_relaxed)) {}
        if (!oldHead) return false;
        result = std::move(oldHead->data);
        delete oldHead; // ⚠️ 简化版，实际需要延迟释放（Hazard Pointer / Epoch-based）
        return true;
    }
};
```

**面试追问：ABA 问题是什么？**
> CAS 检查"值没变"，但可能 A→B→A 变回来了。解决方法：(1) 带版本号的 CAS（每次修改版本号+1）；(2) Hazard Pointer（标记正在使用的节点，延迟释放）；(3) Epoch-based Reclamation。

### 3.3 线程池（完整实现）

```cpp
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <functional>
#include <future>
#include <vector>

class ThreadPool
{
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex mtx_;
    std::condition_variable cv_;
    bool stop_ = false;
    
public:
    explicit ThreadPool(size_t numThreads)
    {
        for (size_t i = 0; i < numThreads; i++)
        {
            workers_.emplace_back([this]
            {
                while (true)
                {
                    std::function<void()> task;
                    {
                        std::unique_lock<std::mutex> lock(mtx_);
                        cv_.wait(lock, [this]{ return stop_ || !tasks_.empty(); });
                        if (stop_ && tasks_.empty()) return;
                        task = std::move(tasks_.front());
                        tasks_.pop();
                    }
                    task();
                }
            });
        }
    }
    
    template<typename F, typename... Args>
    auto Submit(F&& f, Args&&... args) -> std::future<decltype(f(args...))>
    {
        using ReturnType = decltype(f(args...));
        auto task = std::make_shared<std::packaged_task<ReturnType()>>(
            std::bind(std::forward<F>(f), std::forward<Args>(args)...)
        );
        std::future<ReturnType> future = task->get_future();
        {
            std::lock_guard<std::mutex> lock(mtx_);
            tasks_.emplace([task]{ (*task)(); });
        }
        cv_.notify_one();
        return future;
    }
    
    ~ThreadPool()
    {
        {
            std::lock_guard<std::mutex> lock(mtx_);
            stop_ = true;
        }
        cv_.notify_all();
        for (auto& w : workers_) w.join();
    }
};

// 使用
ThreadPool pool(4);
auto future = pool.Submit([](int a, int b){ return a + b; }, 3, 4);
int result = future.get(); // 7
```

### 3.4 读写锁

```cpp
#include <shared_mutex>

class DataStore
{
    mutable std::shared_mutex rwMtx_;
    std::map<std::string, int> data_;
    
public:
    int Read(const std::string& key) const
    {
        std::shared_lock<std::shared_mutex> lock(rwMtx_); // 多个读者可同时进入
        auto it = data_.find(key);
        return it != data_.end() ? it->second : -1;
    }
    
    void Write(const std::string& key, int value)
    {
        std::unique_lock<std::shared_mutex> lock(rwMtx_); // 独占写
        data_[key] = value;
    }
};
```

### 3.5 Double-Checked Locking

```cpp
// ❌ 经典错误版本（C++11 之前）
class Singleton
{
    static Singleton* instance;
    static std::mutex mtx;
public:
    static Singleton* GetInstance()
    {
        if (!instance)                    // 第一次检查（无锁）
        {
            std::lock_guard<std::mutex> lock(mtx);
            if (!instance)                // 第二次检查（有锁）
                instance = new Singleton(); // ⚠️ 可能被指令重排：先赋值指针再构造
        }
        return instance;
    }
};
// 问题：编译器/CPU 可能重排 new 的三步（分配→构造→赋值指针）为（分配→赋值指针→构造）

// ✅ 修复版本1：用 atomic + acquire/release
class Singleton
{
    static std::atomic<Singleton*> instance;
    static std::mutex mtx;
public:
    static Singleton* GetInstance()
    {
        Singleton* p = instance.load(std::memory_order_acquire);
        if (!p)
        {
            std::lock_guard<std::mutex> lock(mtx);
            p = instance.load(std::memory_order_relaxed);
            if (!p)
            {
                p = new Singleton();
                instance.store(p, std::memory_order_release);
            }
        }
        return p;
    }
};

// ✅ 修复版本2（推荐）：C++11 的 call_once
class Singleton
{
    static std::unique_ptr<Singleton> instance;
    static std::once_flag flag;
public:
    static Singleton& GetInstance()
    {
        std::call_once(flag, []{ instance = std::make_unique<Singleton>(); });
        return *instance;
    }
};

// ✅ 修复版本3（最推荐）：C++11 局部静态变量保证线程安全
class Singleton
{
public:
    static Singleton& GetInstance()
    {
        static Singleton instance; // C++11 保证线程安全初始化
        return instance;
    }
};
```

---

## 第四章：游戏引擎中的多线程

### 4.1 游戏主循环与多线程模型

```
单线程 Tick（传统模型）：
  Input → Logic → Physics → Animation → Render → Swap
  缺点：全串行，CPU 利用率低

多线程 Tick（UE 模型）：
  GameThread:   Input → Logic → Physics → 提交渲染命令
  RenderThread:                            执行渲染命令 → 
  RHIThread:                                              提交 GPU
  WorkerThreads:  TaskGraph 任务（动画、布料、AI寻路...）

Job System（Unity DOTS / 自研引擎模型）：
  MainThread:   调度 Job 依赖图
  WorkerPool:   并行执行 Job
  特点：数据驱动，Job 只操作数据，不持有状态
```

### 4.2 渲染线程与游戏线程同步

```cpp
// UE 的渲染命令提交
ENQUEUE_RENDER_COMMAND(UpdateTransform)(
    [Transform = MyTransform](FRHICommandListImmediate& RHICmdList)
    {
        // 这段代码在 RenderThread 执行
        // Transform 是值拷贝，不共享 GameThread 的数据
        UpdateGPUBuffer(Transform);
    }
);

// 同步等待
FRenderCommandFence Fence;
Fence.BeginFence();
Fence.Wait(); // 阻塞 GameThread 直到 RenderThread 处理完

// 为什么滞后 1 帧？
// GameThread Frame N 生成的渲染命令，RenderThread 在 Frame N+1 执行
// 好处：GameThread 和 RenderThread 可以真正并行
// 代价：画面延迟 1 帧（16ms@60fps，玩家几乎感知不到）
```

### 4.3 资源异步加载线程模型

```
GameThread:      RequestAsyncLoad(Path) ──→ 注册 Callback
                           ↓
AsyncLoadThread: 读取 .uasset → 反序列化 → 创建 UObject
                           ↓
GameThread:      Callback() ← 回到主线程执行
```

**关键问题：为什么 Callback 必须在 GameThread？**
> UObject 的创建和属性设置不是线程安全的——PostLoad、PostInitProperties 等函数可能触发蓝图逻辑、UI 更新。所以异步线程做 IO 和反序列化，最终的 UObject 注册和回调必须回到 GameThread。

### 4.4 ECS 中的多线程并行

```
思路：
1. System 声明"我要读哪些 Component，写哪些 Component"
2. 调度器分析依赖：读-读不冲突，读-写冲突，写-写冲突
3. 无冲突的 System 并行执行

Unity DOTS 的 Job System + Burst：
- Job 只操作 NativeArray（非托管内存），不触发 GC
- Burst 编译器把 C# 编译成 SIMD 优化的机器码
- IJobParallelFor 自动分片并行处理 Entity

UE 的 Mass Entity：
- 类似 ECS 的 Archetype 模式
- 用 FMassEntityQuery 声明读写依赖
- 调度器自动并行执行 Processor
```

---

## 第五章：面试高频题 30 道

### 基础概念（Q1-Q5）

**Q1：多线程和多进程的区别？游戏引擎为什么用多线程？**
> 线程共享内存空间，通信零拷贝——渲染线程直接读 Transform 数组，无需 IPC。进程隔离更安全但通信开销大。游戏引擎追求极致性能，必须共享内存。

**Q2：什么是竞态条件？怎么避免？**
> 多线程同时读写同一数据，结果取决于执行顺序。三种解决方案：(1) mutex 互斥（最通用）；(2) atomic 原子操作（无锁，适合简单操作）；(3) 数据隔离（每个线程操作自己的副本，最后合并）。

**Q3：死锁的四个条件？怎么预防？**
> 互斥、持有并等待、不可抢占、循环等待。预防：(1) 统一加锁顺序（打破循环等待）；(2) scoped_lock 同时锁多个（打破持有并等待）；(3) try_lock 超时（打破不可抢占）。

**Q4：mutex 和 spinlock 的区别？什么时候用 spinlock？**
> mutex 获取失败时线程进入内核态睡眠（context switch 开销大但不占 CPU）。spinlock 获取失败时忙等（占 CPU 但无切换开销）。临界区极短（< 1μs）且竞争低时用 spinlock——比如更新一个 atomic flag。

**Q5：什么是 False Sharing？**
> 两个线程修改不同变量，但这两个变量在同一个 Cache Line（通常 64 字节）中。每次一方写入，另一方的 Cache Line 失效，强制从主内存重新加载。解决：`alignas(64)` 对齐，或用 padding 分隔变量。

### 锁和同步（Q6-Q12）

**Q6：lock_guard 和 unique_lock 的区别？**
> lock_guard 构造即锁定、析构解锁，不能中途操作。unique_lock 支持延迟锁定、手动解锁、移动所有权——配合 condition_variable 时必须用 unique_lock（wait 内部需要 unlock）。

**Q7：condition_variable 的虚假唤醒是什么？**
> OS 可能在没有 notify 时唤醒 wait 线程。wait 必须用带 predicate 的版本：`cv.wait(lock, pred)`，内部等价于 `while(!pred()) cv.wait(lock);`。

**Q8：std::async 的 launch::async 和 launch::deferred 区别？**
> async 立即在新线程执行。deferred 延迟到 future.get() 时在调用线程执行（其实是惰性求值，不是多线程）。默认 `launch::async | launch::deferred`，由实现决定——**不要依赖默认行为**。

**Q9：怎么实现一个线程安全的单例？**
> C++11 最简洁的方式：函数内 static 变量——`static Singleton& Get() { static Singleton s; return s; }`，标准保证线程安全初始化。

**Q10：读写锁（shared_mutex）适用场景？**
> 读多写少。多个线程可以同时读（shared_lock），写时独占（unique_lock）。但有写饥饿风险——读太频繁时写者可能长时间拿不到锁。

**Q11：std::call_once 的实现原理？**
> 内部通常用 atomic flag + mutex。第一次调用执行函数并设置 flag，后续调用直接跳过。比 Double-Checked Locking 更安全，因为 once_flag 的语义由标准保证。

**Q12：怎么通知主线程一个异步任务完成了？**
> (1) future.get()（最简单，但阻塞）；(2) condition_variable + 标志位（主线程定期检查）；(3) 回调函数（异步线程完成后调用，注意线程安全）；(4) UE 中用 AsyncTask(ENamedThreads::GameThread, Callback) 把回调调度到主线程。

### Atomic 和无锁（Q13-Q18）

**Q13：atomic 的 load/store 为什么需要 memory_order？**
> 编译器和 CPU 会重排指令以优化性能。memory_order 告诉编译器/CPU "这些操作的顺序不能打乱"。默认 seq_cst 是全局一致序——所有线程看到相同顺序，最安全但最慢。

**Q14：memory_order_acquire 和 memory_order_release 配对怎么用？**
> release-store 保证之前的所有写在 store 之前完成；acquire-load 看到 release-store 的值时，也能看到 release 之前的所有写。典型用法：用 atomic bool 做"数据准备好了"的标志。

**Q15：CAS（Compare-And-Swap）是什么？**
> `compare_exchange_strong(expected, desired)`：如果当前值 == expected，则设为 desired 并返回 true；否则把当前值写入 expected 并返回 false。是无锁编程的基础原语。weak 版本允许虚假失败（在循环中使用效率更高）。

**Q16：ABA 问题怎么解决？**
> 加版本号：每次修改 version++，CAS 同时比较值和版本号。或用 Hazard Pointer 标记正在使用的节点延迟释放。C++20 的 `std::atomic_shared_ptr` 也能解决。

**Q17：无锁队列和有锁队列怎么选？**
> 有锁队列：实现简单、调试方便、性能在中低竞争时足够好。无锁队列：高竞争场景下吞吐量高，但实现复杂、调试困难、容易出 bug。**游戏引擎中优先用有锁，只在性能热点用无锁。**

**Q18：什么是 memory fence（内存屏障）？**
> 阻止编译器和 CPU 在 fence 两侧重排指令。`std::atomic_thread_fence(memory_order_acquire)` 等价于在此位置插入一个 acquire 屏障——之后的读不会被移到 fence 之前。

### 游戏引擎实践（Q19-Q25）

**Q19：UE 的 GameThread 和 RenderThread 怎么同步？**
> ENQUEUE_RENDER_COMMAND 把 Lambda 入队，RenderThread 逐个执行。GameThread 用 FRenderCommandFence 等待 RenderThread 追上。RenderThread 滞后 1 帧实现流水线并行。

**Q20：UE 的 TaskGraph 和 std::async 有什么区别？**
> TaskGraph 支持任务依赖（DAG）、指定执行线程、任务窃取。std::async 只是"异步执行返回 future"。TaskGraph 的调度器能更好地利用多核。

**Q21：为什么游戏引擎的异步加载回调要回到主线程？**
> UObject 创建、PostLoad、蓝图执行都不线程安全。异步线程做 IO，主线程做对象初始化——职责分离。

**Q22：ParallelFor 使用的注意事项？**
> (1) 确保元素间无数据竞争；(2) 元素太少不值得并行（调度开销 > 并行收益）；(3) 不能在 Lambda 里调用 GameThread-only API。

**Q23：帧同步中的确定性（Determinism）怎么保证？**
> (1) 相同输入序列 → 相同输出——禁用 float 的非确定性（使用定点数或保证编译器 FP 设置一致）；(2) 使用确定性随机数（共享种子）；(3) 固定帧步长；(4) 多线程中，并行任务的合并顺序必须固定。

**Q24：ECS 如何实现多线程并行而不加锁？**
> System 声明读写 Component 类型，调度器分析依赖：只读 vs 只读无冲突，可并行；涉及写则串行。加上数据布局紧凑（Archetype 连续内存），Cache 友好性极佳。

**Q25：线程池的工作窃取（Work Stealing）是什么？**
> 每个 Worker 有自己的任务队列。当自己的队列空了，从其他 Worker 的队列尾部"偷"任务。好处：负载自动均衡，减少空闲等待。UE 的 TaskGraph 和 Unity 的 Job System 都用这个机制。

### 高级题（Q26-Q30）

**Q26：如何设计一个支持优先级的线程安全任务队列？**
> 用 `std::priority_queue` + mutex + condition_variable。或无锁版：多个队列按优先级分级，Worker 按优先级高→低轮询。UE TaskGraph 用后者思路。

**Q27：什么是 Lock-Free 和 Wait-Free 的区别？**
> Lock-Free：至少有一个线程在有限步内完成操作（整体有进展，但某个线程可能被延迟）。Wait-Free：每个线程都在有限步内完成（最强保证，最难实现）。实际工程中 Lock-Free 就够用了。

**Q28：游戏中哪些系统适合多线程？哪些不适合？**
> 适合：物理模拟（多体并行）、AI 寻路（互不依赖）、动画更新、粒子系统、资源加载。不适合：游戏逻辑 Tick（状态依赖复杂）、UI（线程不安全）、蓝图执行（UE 蓝图 VM 单线程）。

**Q29：如何检测和调试多线程 Bug？**
> (1) ThreadSanitizer（TSan）——编译器插桩检测数据竞争；(2) 日志 + 线程 ID；(3) 确定性重放——记录线程调度顺序，replay 复现；(4) 最小化多线程代码——"能单线程就单线程"。

**Q30：你设计一个多线程资源加载系统，怎么处理优先级反转？**
> 优先级反转：低优先级任务持有锁，高优先级任务等锁，中优先级任务抢占低优先级导致高优先级无限等待。解决方案：(1) 优先级继承——低优先级任务持锁期间临时提升到高优先级；(2) 避免共享锁——用消息队列替代共享数据；(3) 限制持锁时间——临界区尽量短。
