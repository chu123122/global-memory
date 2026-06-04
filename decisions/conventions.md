---
name: conventions
description: 跨项目开发规范，从实际项目中提炼，含硬检查标注
type: decision
created: 2026-04-13
updated: 2026-04-13
source: 帧同步 v2 + 博客重设计
access_count: 0
priority: high
status: active
trigger:
  keywords:
    - concept:convention
    - concept:project
    - concept:spec
  tags:
    - workflow
    - design
    - tooling
  stages:
    - discussion
    - implementation
    - review
last_updated: 2026-06-04
---

# 跨项目开发规范

> 位置：~/.claude/global-memory/decisions/conventions.md
> 来源：从实际项目中提炼，每条规范标注了来源项目和具体案例
> 生效范围：所有项目（除非项目 SPEC 中明确覆盖）
> 硬检查：标注 🔒 的规范由 `verify_conventions.py` 自动检查，不靠 AI 自觉

---

## 文档规范

> **v2 task 结构（现行）**：`core/` + `design/` + `ops/` + `test/`（+ `_archive/`）。以下 DOC-* 按 v2 写；旧平铺 `docs/SPEC.md` 那套仅 legacy 任务只读兼容（`verify_conventions.py` 有 `is_v2_task()` 分支，v2 查下列文件，非 v2 回退旧检查）。规范流程单一源 = `docs/task-lifecycle.md`。

### DOC-01 🔒 项目必须有 背景 + HANDOFF
- **规则**：AI 协作开发的 v2 task，`core/HANDOFF.md` 必须存在；`design/设计文档.md`（完整等级）应存在
- **来源项目**：帧同步 v2 / 博客重设计
- **案例**：博客交接时新 AI 因没 HANDOFF 从零探索仓库，浪费大量 token
- **硬检查**：v2 → 查 `core/HANDOFF.md`（ERROR if缺）+ `design/设计文档.md`（WARNING if缺）；legacy → 查 `docs/SPEC.md` + `docs/HANDOFF.md`

### DOC-02 🔒 HANDOFF 必须包含"已确定的设计决策"
- **规则**：`core/HANDOFF.md` 中必须有"已确定的设计决策/下次开始"区块，列出不应被推翻的决策
- **来源项目**：博客重设计
- **案例**：不写明"技术栈用 Astro"这类已定决策，新 AI 会重新提问或另选方案
- **硬检查**：查 `core/HANDOFF.md`（legacy: `docs/HANDOFF.md`）是否含"已确定"或"设计决策"关键词

### DOC-03 🔒 多 Phase 项目必须有进度记录
- **规则**：超过 1 个 Phase 的项目必须有 `design/进度.md` + 各 `design/Phase<N>-*.md` Phase 卡（STATUS.md 由 `work_context_pack.py` 自动派生，不手维护）
- **来源项目**：帧同步 v2
- **案例**：4 Phase 开发中，进度记录让每次接续对话立即知道当前进度
- **硬检查**：v2 → 多 Phase 时查 `design/进度.md`（WARNING if缺）；legacy → 查 `docs/PROGRESS.md`

### DOC-04 每个 Phase 完成后写 Phase 卡记录
- **规则**：每个 Phase done 时在对应 `design/Phase<N>-*.md` 记录：设计决策、新增文件、TDD 验证（Red/Green）
- **来源项目**：帧同步 v2
- **案例**：预测回滚引擎涉及 5 个设计决策，不记录则后续 Phase 和复盘无法追溯
- **硬检查**：v2 → 检测到 done Phase 时查对应 Phase 卡有记录；内容质量无法自动检查

### DOC-05 🔒 开发前必须有计划文档，开发中必须有进度文档
- **规则**：v2 task 开发前产出 `core/背景.md`（是什么+为什么+边界）+ `design/设计文档.md`（方案+Phase 拆分表，每 Phase 必填「不做会怎样?」列）。多 Phase 维护 `design/进度.md`。每 Phase done 写回 Phase 卡。
- **来源项目**：帧同步 v2
- **案例**：LockStepSystem 完整文档体系（需求分析→模块设计→实时进度→Phase 决策记录→复盘→交接），迁移到 v2 即 `core/背景` → `design/设计文档` → `design/进度`+Phase 卡 → `core/复盘.md` → `core/HANDOFF.md`
- **硬检查**：v2 → 查 `core/背景.md` + `design/设计文档.md`（均 WARNING if缺）；legacy → 查 `docs/SPEC.md` + `docs/TECHNICAL_DESIGN.md`
- **v2 标准文档清单**：
  ```
  <task>/
  ├── core/
  │   ├── 背景.md          # 做之前（是什么+为什么+边界）
  │   ├── HANDOFF.md       # 交接（下次开始+已定决策）
  │   ├── STATUS.md        # 自动派生（work_context_pack）
  │   └── 复盘.md          # 做完之后（≥5 Phase/≥10 轮触发）
  ├── design/
  │   ├── 设计文档.md      # 做之前（方案+Phase 拆分表）
  │   ├── 进度.md          # 做的过程中
  │   └── Phase<N>-*.md    # 每 Phase 卡（status + TDD 记录）
  ├── ops/
  │   ├── CHANGELOG.md     # PR/commit 级改动审计
  │   └── 坑点.md          # 任务私有坑
  └── test/
      └── 测试.md          # 测试策略 + 证据
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

### HARNESS-01 🔒 项目开始前写设计文档
- **规则**：完整等级 v2 task 动手写代码前必须先有 `design/设计文档.md`（含方案 + Phase 拆分表）。轻量任务至少 `core/背景.md` 一段
- **来源项目**：帧同步 v2 + 博客重设计
- **案例**：两个项目都是设计先行，帧同步的需求文档列出 9 个现有 bug，后续反复引用
- **硬检查**：v2 → 查 `design/设计文档.md`（见 DOC-05）；legacy → 查 `docs/SPEC.md`

### HARNESS-02 项目完成后填复盘
- **规则**：v2 task ≥5 Phase 或 ≥10 轮交互完成后产出 `core/复盘.md`（含 M1 反问复审：「不做会怎样?」原答 vs 实际）。小任务跳过
- **来源项目**：帧同步 v2
- **案例**：帧同步复盘记录"验收标准被 AI 反复引用"等有价值发现
- **硬检查**：无（需要人工填写）

---

## 文件规范

### FILE-01 🔒 静态资源文件名必须 ASCII 化
- **规则**：提交到 Git 仓库的所有静态资源（图片/音频/字体/视频），文件名只允许 ASCII 字母、数字、连字符(`-`)、下划线(`_`)和点(`.`)。中文/日文/全角字符/空格/括号一律 rename 后再提交
- **来源项目**：博客重设计
- **案例**：下载的日文音乐文件 `1-【ヨルシカ】だから僕は音楽を辞めた...AVC.mp3` 包含全角字符/空格/括号，在 Git 路径、URL 编码、跨平台文件系统中均可能出问题。被迫 rename 为 `yorushika-dakara.mp3`
- **硬检查**：脚本检查 Git 暂存区中 `public/`、`assets/`、`static/` 下的文件名是否只含 `[a-zA-Z0-9._-]`

---

## 任务规范

### DOC-06 复杂非代码任务前置设计
- **规则**：预计 >3 轮的非代码任务（审查/分析/规划/迁移评估），开始前必须先输出任务计划（目标/范围/输出格式），经用户确认后再执行
- **来源项目**：CLI 迁移全量测试
- **案例**：T01-T38 全量扫描任务（约5小时）直接开始执行，没有前置设计导致扫描范围不清晰、输出格式反复调整
- **硬检查**：无（需要 AI 自觉判断任务轮数）

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
- 2026-04-15: 新增 DOC-06 复杂非代码任务前置设计规范（来源：CLI 迁移全量测试复盘）
- 2026-06-04: DOC-01~05 + HARNESS-01/02 对齐 v2 task 结构（core/design/ops/test），旧 docs/SPEC 套降级为 legacy 兼容。脚本 verify_conventions.py 本就有 is_v2_task 分支，无需改；本次只同步文本（harness 四层架构落地配套）
