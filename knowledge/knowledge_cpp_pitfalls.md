---
name: knowledge-cpp-pitfalls
description: C++ 常见陷阱，包括智能指针/RAII/模板/移动语义/链接性/前置声明析构等
summary: "shared_ptr循环引用/make_shared/移动语义/const位置/链接 vs 作用域/PIMPL析构坑 已记录；RAII/模板待填"
type: knowledge
created: 2026-04-01
updated: 2026-04-20
source: 学习 Agent
access_count: 0
---

# C++ 常见陷阱

## 智能指针
- shared_ptr 循环引用 → 用 weak_ptr 打断
- make_shared vs new：make_shared 一次分配（对象+控制块），new 两次
- shared_ptr 线程安全：控制块的引用计数是原子的，但指向的对象不是

## RAII
（随学习积累）

## 模板
（随学习积累）

## 移动语义
- std::move 本身不移动，只做类型转换（左值→右值引用）
- 移动后的对象处于"有效但未指定"状态

## 其他
- enum class 是整数类型，不在堆上分配（区别于class仅在于作用域和类型安全）；new/malloc才是堆分配（2026-04-14 T19 纠正写入）

## const 位置规则（2026-04-20 写入）

### 非指针类型：const 左右等价
```cpp
const bool a = true;   // 老风格
bool const b = true;   // East-const 风格
// a 和 b 完全等价
```

### 指针类型：const 位置决定"谁不能改"
**记忆法**：从右往左读，`const` 修饰它**左边**的东西（左边没有就修饰右边）。

```cpp
const int*       p1;   // 指向 const int 的指针：不能改 *p1，能改 p1
int const*       p2;   // 等价 p1
int* const       p3;   // const 指针指向 int：能改 *p3，不能改 p3
const int* const p4;   // 都不能改
```

### 成员函数后置 const
```cpp
class Foo {
public:
    int Get() const;   // 承诺不修改非 mutable 成员
};

int Foo::Get() const {
    Member = 5;        // ❌ 编译错
    return Member;
}
```
**作用**：让编译器帮你保证"查询不改状态"。所有 getter / pure query 应该加 const。
**反过来**：const 对象（const Foo& f）只能调 const 成员函数。不加 const 的方法在 const 上下文里调不到。

## 链接性 vs 作用域 vs 存储期（2026-04-20 写入，面试高频）

三个常被混淆的独立维度，先分清：

| 维度 | 解决什么 | 关键字 |
|---|---|---|
| **作用域 (scope)** | 名字在代码里**哪段能看见** | `{}` / 文件 / 类 / namespace |
| **链接 (linkage)** | 不同 TU 里**同名实体是否同一个** | `static` / `extern` / 默认 |
| **存储期 (storage duration)** | 内存**何时分配何时释放** | `static` / 自动 / `new` |

**易混点**：`static` 关键字一词多义 —— 全局加 `static` 是改"链接"（变 internal），局部加 `static` 是改"存储期"（变持久）。

### 三种链接

| 类型 | 谁有 | 跨 TU 行为 |
|---|---|---|
| External linkage | 默认全局变量 / 函数 / class 成员 | 别的 TU 能 `extern` 看见 |
| Internal linkage | `static` 全局 / 匿名 namespace | 别的 TU **看不见**，即使 `extern` 也找不到 |
| No linkage | 局部变量 / 函数参数 | 不存在跨 TU 概念 |

### extern 是什么

**一句话**：`extern` = "**这是声明，不是定义。真正的定义在别的 TU**"。

```cpp
// 【定义】—— 分配内存 + 调构造，每个程序只能 1 份
TAutoConsoleVariable<float> CVar(...);

// 【声明】—— 不分配内存，只让本 TU 知道有这个名字
extern TAutoConsoleVariable<float> CVar;
```

链接器流程：
- TU-A 的 .obj 含定义（实际数据 + 构造调用）
- TU-B 的 .obj 含未解析符号（对同名变量的引用）
- 链接阶段：TU-B 的引用找到 TU-A 的定义 → 绑到同一块内存
- 最终内存里**只有一份对象**，多个 TU 共用

### 业界标准模式

把声明放共享 header：
```cpp
// X.h
extern T GlobalX;
// X.cpp
T GlobalX(...);  // 定义只 1 处
// 别处
#include "X.h"   // 不用手写 extern
```

### UE Unity Build 大坑（C4211）

UE 默认开 Unity Build —— 把多个 cpp 拼成一个大 TU 一起编译加速。导致：
- A.cpp: `static T X(...);`（internal linkage 定义）
- B.cpp: `extern T X;`（external linkage 声明）
- 单独编译两文件没问题；Unity 拼一起后**同一 TU 内**两个矛盾声明 → `C4211: 将"extern"重新定义为"static"`

修法：去 `static`（让 X 真正是 external linkage），或两个 cpp 都不要互相引用 X。

### 关键坑

- `static` 全局变量 + 别的 TU `extern` 引用 = 链接器 unresolved symbol（看不见）
- 头文件里写 `T X;`（无 extern）→ 每个 include 它的 TU 都生成一份定义 → 链接器 multiple definition
- header 里**只能写 `extern T X;` 声明**，定义放某个 cpp

---

## TUniquePtr<前置声明类> 析构坑（2026-04-20 写入，PIMPL 必踩）

### 现象

```cpp
// Foo.h
class Bar;                          // 前置声明
class Foo {
    TUniquePtr<Bar> Member;         // 这里能编译
};
// 隐式析构 ~Foo() 在某个 TU 展开时触发
// → C4150 / "deletion of pointer to incomplete type"
```

### 根因

`TUniquePtr<T>` / `std::unique_ptr<T>` / `TSharedPtr<T>` 析构时调 `delete ptr`，编译器需要 **T 的完整定义**才能：
- 知道 T 的 sizeof
- 找到 T 的析构函数（尤其是虚析构）

光 forward decl 不够。编译器为 `Foo` 生成的**隐式析构函数** `~Foo()` 会自动展开成员的析构调用。这个隐式析构在哪个 TU 生成？**任何包含 Foo.h 又触发析构展开的 TU**（包括别的模块）。这些 TU 通常没 include Bar.h → 看到的 Bar 只是 forward decl → 报错。

### 修法（PIMPL 标准）

`.h` 显式声明 ctor/dtor，`.cpp` 用 `= default` 实现。cpp 里能看到 Bar 完整定义，问题消失：

```cpp
// Foo.h
class Bar;
class Foo {
public:
    Foo();
    ~Foo();          // 显式声明，不在这定义
private:
    TUniquePtr<Bar> Member;
};

// Foo.cpp
#include "Bar.h"     // 完整类型在这可见
Foo::Foo() = default;
Foo::~Foo() = default;
```

### 适用范围

- `TUniquePtr<T>` / `std::unique_ptr<T>`：必踩
- `TSharedPtr<T>` / `std::shared_ptr<T>`：**也有这个坑**（虽然 shared_ptr 实现是类型擦除，但析构展开还是要看见 T）
- `TWeakObjectPtr<T>`：UObject 的弱引用，**不需要 delete**，没这个坑
- 裸指针成员：不需要管，因为不会自动 delete

### 触发条件

- forward decl + 智能指针成员
- 编译器要为持有者生成隐式 ctor/dtor/move
- 隐式析构在某个 TU 触发展开 → 那个 TU 没 include 完整定义 → 错

### 知识点串联

这是 PIMPL（Pointer to Implementation）模式必踩的坑 —— PIMPL 的核心就是把实现细节藏在 cpp 里，header 只 forward decl。智能指针成员让编译器不知所措。

---
## 更新日志
- 2026-04-01: 初始创建，基于已有面试经验整理基础条目
- 2026-04-20: 加 const 位置规则（const T / T const / T* const 三态）+ 成员函数后置 const 语义（来自心动 UE 插件重构讨论）
- 2026-04-20: 加链接性/作用域/存储期三概念区分 + extern 工作机制 + UE Unity Build C4211 坑（来自心动 XDAdaptivePerformance 重构 CVar 跨 TU 引用）
- 2026-04-20: 加 TUniquePtr<前置声明类> 析构 C4150 坑 + PIMPL 标准修法（同任务遇到）
