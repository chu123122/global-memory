---
description: 代码风格偏好
priority: medium
status: active
trigger:
  keywords:
    - concept:cpp
    - tool:ue
  tags:
    - cpp
    - ue
    - unity
    - lua
    - doc
  stages:
    - implementation
    - delivery
last_updated: 2026-05-20
---

---
name: feedback-code-style
description: 代码风格偏好记录，包括命名约定、缩进、注释风格等
type: feedback
created: 2026-04-01
updated: 2026-04-14
source: CLAUDE.md 提取 + 测试 T16 暴露空壳问题后补填
access_count: 0
---

# 代码风格偏好

## 通用规则
- 遵循项目已有命名约定，不自作主张改风格
- 代码块必须标注语言
- 代码示例优先 C++（用户主力语言）

## C++ 风格
- new + free 是绝对红线，必须 new + delete 配对，优先推荐智能指针
- 解释概念时用用户已会的东西类比（ECS、帧同步、PBD）
- UE 项目中遵循 UE 命名约定（PascalCase、A/F/U/E 前缀、UPROPERTY/UFUNCTION 宏）
- 头文件使用 `#pragma once`

## Lua 风格
（随使用积累）

## C# (Unity) 风格
- namespace 必须（CODE-02 硬检查规范）
- 参考 Unity DOTS 项目的已有约定

---
## 更新日志
- 2026-04-01: 初始创建
- 2026-04-14: 从 CLAUDE.md 和测试结果提取已知偏好，激活文件
