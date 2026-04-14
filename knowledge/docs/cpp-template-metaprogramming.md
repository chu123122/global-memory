---
name: cpp-template-metaprogramming
description: C++模板元编程SFINAE/CRTP/enable_if深度参考
type: knowledge-doc
created: 2026-04-13
updated: 2026-04-13
source: 多源整合（博客园/CSDN/阿里云/UE源码）
---

# C++ 模板元编程：SFINAE / CRTP / enable_if

> 快照文档 · 面试+UE源码阅读双用 · 2026-04-13

---

## 一、技术关系全景

```
type_traits（基础设施：编译期类型信息）
    │
    ├── enable_if + SFINAE（C++11：条件重载选择）
    │       │
    │       └── 被 if constexpr 部分替代（C++17）
    │             └── 被 Concepts 完全替代（C++20）
    │
    ├── 变参模板（C++11：处理任意参数）
    │       └── 折叠表达式简化（C++17）
    │
    └── CRTP（静态多态 / Mixin 注入）
```

---

## 二、SFINAE（Substitution Failure Is Not An Error）

### 核心原理
模板参数替换时产生无效类型/表达式 → 编译器**不报错** → 从重载候选集中**静默移除** → 继续匹配其他候选。

```cpp
// T=double 时，is_integral<double>::value = false
// → enable_if<false, double> 无 ::type 成员
// → 替换失败 → SFINAE → 移除此候选 → 不报错
template <typename T>
typename std::enable_if<std::is_integral<T>::value, T>::type
add(T a, T b) { return a + b; }
```

### SFINAE 只在直接上下文生效
```cpp
// ✅ SFINAE（替换发生在模板参数/返回值/函数参数）
template <typename T>
typename T::value_type foo(T);  // T 无 value_type → SFINAE

// ❌ 硬错误（函数体内不是直接上下文）
template <typename T>
void bar(T t) { typename T::value_type v; }  // T 无 value_type → 编译错误
```

---

## 三、std::enable_if

### 实现原理

```cpp
template<bool B, class T = void>
struct enable_if {};            // 默认：无 type

template<class T>
struct enable_if<true, T> {     // 偏特化：条件为 true
    typedef T type;             // 才有 type
};
```

### 三种用法

```cpp
// 1. 返回值类型（经典）
template <typename T>
typename std::enable_if<std::is_integral<T>::value, T>::type
foo(T val);

// 2. 额外模板参数（推荐，更清晰）
template <typename T, typename = std::enable_if_t<std::is_integral_v<T>>>
T foo(T val);

// 3. 函数参数（某些场景必须）
template <typename T>
T foo(T val, std::enable_if_t<std::is_integral_v<T>>* = nullptr);
```

---

## 四、if constexpr（C++17 推荐替代方案）

```cpp
template <typename T>
auto process(T val) {
    if constexpr (std::is_integral_v<T>) {
        return val * 2;       // 整数路径
    } else if constexpr (std::is_floating_point_v<T>) {
        return val * 2.0;     // 浮点路径
    } else {
        static_assert(false, "Unsupported type");
    }
}
```

**关键特性**：未选中的分支**不会被实例化** → 可以写只对特定类型有效的代码。

| | enable_if | if constexpr | Concepts (C++20) |
|---|---|---|---|
| C++ 版本 | 11 | 17 | 20 |
| 可读性 | 差 | 好 | 最好 |
| 适用场景 | 重载选择/类偏特化 | 函数体内分支 | 所有场景 |

---

## 五、CRTP（Curiously Recurring Template Pattern）

### 基本形式
```cpp
template <typename Derived>
class Base {
public:
    void interface() {
        static_cast<Derived*>(this)->implementation();
    }
    void implementation() { /* 默认实现 */ }
};

class MyClass : public Base<MyClass> {
public:
    void implementation() { /* MyClass 实现 */ }
};
```

### 核心用途

**1. 静态多态（零开销替代虚函数）**
```cpp
template <typename T>
void process(Base<T>& obj) {
    obj.interface();  // 编译期解析到 T::implementation()
    // 无虚表查找 → 零开销
}
```

**2. Mixin 注入通用功能**
```cpp
template <typename Derived>
class Printable {
public:
    void print() { std::cout << static_cast<Derived*>(this)->toString(); }
};

class MyObj : public Printable<MyObj> {
public:
    std::string toString() { return "MyObj"; }
};
```

**3. 标准库/UE 实例**
- `std::enable_shared_from_this<T>` → CRTP
- UE: `TSharedFromThis<T>` → CRTP
- UE: `FNoncopyable` → CRTP（禁止拷贝）

---

## 六、变参模板（Variadic Templates）

### 递归展开（C++11）
```cpp
// 终止
template <typename T>
T sum(T val) { return val; }

// 递归
template <typename T, typename... Args>
T sum(T first, Args... rest) {
    return first + sum(rest...);
}
```

### 折叠表达式（C++17）
```cpp
template <typename... Args>
auto sum(Args... args) {
    return (args + ...);  // 一元右折叠
}

// 四种折叠形式
(args + ...)        // 右折叠: a1 + (a2 + (a3 + a4))
(... + args)        // 左折叠: ((a1 + a2) + a3) + a4
(args + ... + init) // 二元右折叠
(init + ... + args) // 二元左折叠
```

---

## 七、type_traits 常用工具

```cpp
// === 类型判断 ===
std::is_integral_v<int>          // true
std::is_floating_point_v<double> // true
std::is_pointer_v<int*>          // true
std::is_same_v<int, int32_t>     // true（通常）
std::is_base_of_v<Base, Derived> // true
std::is_constructible_v<T, Args...>
std::is_trivially_copyable_v<T>  // POD 检查

// === 类型变换 ===
std::remove_const_t<const int>        // int
std::remove_reference_t<int&>         // int
std::decay_t<const int&>              // int
std::conditional_t<true, int, double> // int
std::common_type_t<int, double>       // double

// === 自定义 trait ===
template <typename T>
struct is_ue_object : std::is_base_of<UObject, T> {};
```

---

## 八、UE 引擎中的实际应用

### TSharedPtr 中的 SFINAE
```cpp
// 只有 OtherType 可转换为 ObjectType 时才启用构造
template <typename OtherType,
    typename = decltype(ImplicitConv<ObjectType*>((OtherType*)nullptr))>
TSharedPtr(TSharedPtr<OtherType, Mode> const& InSharedPtr);
```

### TIsPointerConvertibleFrom（CRTP + type_traits）
```cpp
template <typename From, typename To>
struct TIsPointerConvertibleFrom {
    static constexpr bool Value = std::is_convertible_v<From*, To*>;
};
```

### UE 的 Concepts 风格（C++17 模拟）
```cpp
// UE 中大量使用 TEnableIf
template <typename T,
    typename TEnableIf<TIsPointer<T>::Value, int>::Type = 0>
void Process(T Ptr);
```

### CRTP 在 UE 中
```cpp
// TSharedFromThis — CRTP
class FMyClass : public TSharedFromThis<FMyClass> {
    TSharedRef<FMyClass> GetSelf() {
        return AsShared();  // 安全地获取 this 的 TSharedRef
    }
};
```

---

## 九、实践选型指南

| 场景 | 推荐技术 |
|------|---------|
| 函数体内类型分支 | `if constexpr`（C++17） |
| 重载选择/禁用特定类型 | `enable_if` + SFINAE |
| C++20 可用 | **Concepts** 替代一切 |
| 静态多态（避免虚函数） | CRTP |
| 不定参数 | 变参模板 + 折叠表达式 |
| 编译期类型检查 | type_traits |

---

## 参考资料

- [SFINAE机制详解](https://www.cnblogs.com/Newdawn/p/18692110)
- [从enable_if到if constexpr到Concepts](https://developer.aliyun.com/article/1467528)
- [C++17模板编程与if constexpr](https://blog.csdn.net/qq_29111047/article/details/147104062)
- [SFINAE原理](https://zhuanlan.zhihu.com/p/67339307)
