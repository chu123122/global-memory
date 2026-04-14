---
name: conventions
description: 跨项目开发规范，从实际项目中提炼，含硬检查标注
type: decision
created: 2026-04-13
updated: 2026-04-13
source: 帧同步 v2 + 博客重设计
access_count: 0
---

# 跨项目开发规范

> 位置：~/.claude/global-memory/decisions/conventions.md
> 来源：从实际项目中提炼，每条规范标注了来源项目和具体案例
> 生效范围：所有项目（除非项目 SPEC 中明确覆盖）
> 硬检查：标注 🔒 的规范由 `verify_conventions.py` 自动检查，不靠 AI 自觉

---

## 文档规范

### DOC-01 🔒 项目必须有 SPEC + HANDOFF
- **规则**：任何由 AI 协作开发的项目，`docs/` 目录下必须有 `SPEC.md` 和 `HANDOFF.md`
- **来源项目**：帧同步 v2
- **案例**：博客项目交接时，新 AI 因为没有 HANDOFF 而从零探索仓库结构，浪费了大量 token
- **硬检查**：脚本检查 `docs/SPEC.md` 和 `docs/HANDOFF.md` 是否存在

### DOC-02 🔒 HANDOFF 必须包含"已确定的设计决策"
- **规则**：HANDOFF.md 中必须有"已确定的设计决策"区块，列出不应被推翻的决策
- **来源项目**：博客重设计
- **案例**：如果不写明"技术栈用 Astro"这类已确定的决策，新 AI 可能重新提问或选择其他方案
- **硬检查**：脚本检查 HANDOFF.md 中是否包含"已确定"或"设计决策"关键词

### DOC-03 🔒 多 Phase 项目必须有 PROGRESS.md
- **规则**：超过 1 个 Phase 的项目必须维护实时进度表 `docs/PROGRESS.md`
- **来源项目**：帧同步 v2
- **案例**：4 个 Phase 的开发过程中，PROGRESS.md 让每次接续对话都能立即知道当前进度
- **硬检查**：脚本检查如果存在 `phase2` 相关文件，则必须存在 `PROGRESS.md`

### DOC-04 每个 Phase 完成后写 dev-log
- **规则**：每个 Phase 完成后在 `docs/dev-log/phaseN.md` 记录：设计决策、新增文件、验证方法
- **来源项目**：帧同步 v2
- **案例**：Phase 2 的预测回滚引擎涉及 5 个设计决策，如果不记录，后续 Phase 和面试复盘都无法追溯
- **硬检查**：无（内容质量无法自动检查）

### DOC-05 🔒 开发前必须有计划文档，开发中必须有进度文档
- **规则**：项目开发前在 `docs/` 下产出 SPEC.md（需求+验收标准）+ TECHNICAL_DESIGN.md（架构+接口）。多 Phase 项目必须维护 PROGRESS.md。每个 Phase 完成后产出 dev-log。
- **来源项目**：帧同步 v2
- **案例**：LockStepSystem 的完整文档体系——SPEC(需求分析+9 个现有 bug)→TECHNICAL_DESIGN(7 模块设计)→PROGRESS(4 Phase 实时进度)→dev-log/phase1-4(设计决策记录)→HARNESS_REVIEW(体系验证)→HANDOFF(交接)
- **硬检查**：脚本检查 `docs/SPEC.md` + `docs/TECHNICAL_DESIGN.md` 是否存在；如果有 Phase 2+ 则必须有 `PROGRESS.md`
- **标准文档清单**：
  ```
  docs/
  ├── SPEC.md              # 做之前（需求+验收标准）
  ├── TECHNICAL_DESIGN.md  # 做之前（架构+接口+路线图）
  ├── PROGRESS.md          # 做的过程中（实时进度表）
  ├── HANDOFF.md           # 交接时（给新 AI 的上下文）
  ├── HARNESS_REVIEW.md    # 做完之后（10 个问题找问题）
  └── dev-log/
      └── phaseN.md        # 每个 Phase 完成后（设计决策记录）
  ```

---

## 代码规范

### CODE-01 🔒 新模块必须有 V1/V2 切换开关
- **规则**：重构或新增核心模块时，必须保留旧路径的切换开关（Inspector 可选或编译宏）
- **来源项目**：帧同步 v2 Phase 1
- **案例**：GameClockManager 的 `useNewSimulation` 开关让 V1（原版）和 V2（新引擎）可以随时切换验证，避免了"重构后没法回退"的风险
- **硬检查**：无（语义检查需要理解代码）

### CODE-02 🔒 C# 文件必须有 namespace
- **规则**：所有 C# 文件必须在 namespace 内
- **来源项目**：帧同步 v2
- **案例**：新增的 Core/ 模块全部在 `Client.Core` namespace 下，和现有 `Client` namespace 的旧代码隔离
- **硬检查**：脚本检查 `.cs` 文件中是否包含 `namespace`

### CODE-03 🔒 C++ header 必须有 pragma once 或 include guard
- **规则**：所有 `.hpp` / `.h` 文件必须有头文件保护
- **来源项目**：帧同步 v2 Phase 3
- **案例**：`rudp_transport.hpp` 和 `authority_validator.hpp` 都用了 `#pragma once`
- **硬检查**：脚本检查 `.hpp` / `.h` 文件的前 5 行是否包含 `#pragma once` 或 `#ifndef`

---

## Git 规范

### GIT-01 🔒 commit message 使用 conventional commits
- **规则**：格式 `type(scope): description`，type 限定为 feat/fix/docs/refactor/test/chore
- **来源项目**：帧同步 v2
- **案例**：`feat(phase2): prediction rollback engine` 让 git log 一目了然
- **硬检查**：脚本检查最近 N 条 commit message 格式

### GIT-02 特性开发用独立分支
- **规则**：新功能在独立分支开发，不直接改 main
- **来源项目**：帧同步 v2 (`feature/v2-rollback-rudp`) + 博客 (`redesign-astro`)
- **案例**：两个项目都在独立分支上，main 始终是可用状态
- **硬检查**：无（需要 git 上下文）

---

## 记忆规范

### MEM-01 🔒 修改记忆文件必须写 CHANGELOG
- **规则**：修改 `global-memory/` 下任何文件后，必须在 `CHANGELOG.md` 追加一条记录
- **来源项目**：通用（本次新增）
- **案例**：之前 5 次 commit 修改了记忆文件但没有追踪来源，无法溯源
- **硬检查**：脚本检查 global-memory 最近 commit 中修改的 .md 文件是否在 CHANGELOG.md 中有对应记录

### MEM-02 PROMOTE 规范到全局前须标注来源
- **规则**：从项目中提炼规范写入 `decisions/conventions.md` 时，必须标注来源项目和具体案例
- **来源项目**：通用（本次新增）
- **案例**：本文档中每条规范都标注了来源项目和案例
- **硬检查**：无（内容质量需人工判断）

### MEM-03 🔒 记忆索引同步
- **规则**：新增/删除 topic 文件后，`MEMORY.md` 索引表必须同步更新
- **来源项目**：通用
- **案例**：新增了 `CHANGELOG.md` 和 `decisions/conventions.md`，索引中必须有对应行
- **硬检查**：脚本比对 `MEMORY.md` 中列出的文件和实际存在的文件

---

## Harness 流程规范

### HARNESS-01 🔒 项目开始前写 SPEC
- **规则**：动手写代码之前必须先有 `docs/SPEC.md`
- **来源项目**：帧同步 v2 + 博客重设计
- **案例**：两个项目都是 SPEC 先行，帧同步的 SPEC 中列出了 9 个现有 bug，这些信息在后续设计中被反复引用
- **硬检查**：脚本检查仓库 docs/ 下是否有 SPEC.md

### HARNESS-02 项目完成后填 HARNESS_REVIEW
- **规则**：跑完 SPEC→WORKFLOW 流程后填写 10 个验证问题
- **来源项目**：帧同步 v2
- **案例**：帧同步项目的 HARNESS_REVIEW 记录了"SPEC 中验收标准被 AI 反复引用"等有价值的发现
- **硬检查**：无（需要人工填写）

---

## 文件规范

### FILE-01 🔒 静态资源文件名必须 ASCII 化
- **规则**：提交到 Git 仓库的所有静态资源（图片/音频/字体/视频），文件名只允许 ASCII 字母、数字、连字符(`-`)、下划线(`_`)和点(`.`)。中文/日文/全角字符/空格/括号一律 rename 后再提交
- **来源项目**：博客重设计
- **案例**：下载的日文音乐文件 `1-【ヨルシカ】だから僕は音楽を辞めた...AVC.mp3` 包含全角字符/空格/括号，在 Git 路径、URL 编码、跨平台文件系统中均可能出问题。被迫 rename 为 `yorushika-dakara.mp3`
- **硬检查**：脚本检查 Git 暂存区中 `public/`、`assets/`、`static/` 下的文件名是否只含 `[a-zA-Z0-9._-]`

---

## 规范维护规则

1. **新增规范的条件**：在至少 2 个不同项目中出现过同类问题，或 1 个项目中严重到直接影响交付质量
2. **删除规范的条件**：连续 5 个项目未触发该规范的检查（说明已内化或不再适用）
3. **每条规范必须有**：来源项目 + 具体案例 + 是否可硬检查
4. **标注 🔒 的规范**：由 `verify_conventions.py` 自动检查，违反时报 WARNING
5. **未标注 🔒 的规范**：软约束，靠 AI 自觉执行

---

## 更新日志

- 2026-04-13: 初始创建，从帧同步 v2 和博客重设计两个项目中提炼 12 条规范
- 2026-04-14: 新增 FILE-01 静态资源文件名 ASCII 化（来源：博客音乐播放器复盘）
