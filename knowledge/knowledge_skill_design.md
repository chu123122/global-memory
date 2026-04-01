---
name: knowledge-skill-design
description: Skill 设计经验，包括结构规范、防过拟合、Few-shot 积累
type: knowledge
created: 2026-04-01
updated: 2026-04-01
source: 手动
access_count: 0
---

# Skill 设计经验

## 结构规范
- SKILL.md ≤ 500 行
- 必须有 YAML frontmatter（name, description）
- 目录结构：v1/SKILL.md + examples/ + CHANGELOG.md
- 复杂 Skill 可有 scripts/ 和 references/

## 防过拟合原则
- 修改 Skill 前先问：通用问题还是特殊场景？
- 不为单次场景修改 Skill 核心流程
- 特殊场景的处理放到 examples/ 的反例中

## Few-shot 积累
- Few-shot 优于文字描述
- 每个 Skill 至少 1 个正例 + 1 个反例
- 示例从真实使用中提取，不要编造

## 版本管理
- 每次修改创建新版本目录（v1, v2, ...）
- 软链接指向当前版本
- CHANGELOG.md 记录每次变更

---
## 更新日志
- 2026-04-01: 初始创建
