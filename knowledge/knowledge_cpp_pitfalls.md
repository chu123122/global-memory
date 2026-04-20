---
name: knowledge-cpp-pitfalls
description: C++ 常见陷阱，包括智能指针/RAII/模板/移动语义等
summary: "shared_ptr循环引用/make_shared/移动语义已记录；RAII/模板待填"
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

---
## 更新日志
- 2026-04-01: 初始创建，基于已有面试经验整理基础条目
- 2026-04-20: 加 const 位置规则（const T / T const / T* const 三态）+ 成员函数后置 const 语义（来自心动 UE 插件重构讨论）
