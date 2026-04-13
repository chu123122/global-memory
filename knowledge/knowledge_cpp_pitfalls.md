---
name: knowledge-cpp-pitfalls
description: C++ 常见陷阱，包括智能指针/RAII/模板/移动语义等
summary: "shared_ptr循环引用/make_shared/移动语义已记录；RAII/模板待填"
type: knowledge
created: 2026-04-01
updated: 2026-04-01
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

---
## 更新日志
- 2026-04-01: 初始创建，基于已有面试经验整理基础条目
