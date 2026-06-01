---
description: /work Step 4 跑 task_complete.py 的适用条件
priority: medium
status: active
trigger:
  keywords:
    - concept:style
    - concept:workflow
  tags:
    - skill
    - workflow
    - doc
  stages:
    - implementation
last_updated: 2026-05-20
---

---
name: /work skill 触发场景规则 + 对纯文档任务跳过 task_complete.py
description: /work 何时该跑 / 何时跳过（同会话不重跑、压缩后必须重跑、纯文档任务跳 task_complete.py）
type: feedback
created: 2026-04-22
updated: 2026-04-24
source: ue-mcp-integration 讨论阶段 task_complete 误报复盘
access_count: 0
---

# /work Step 4 跑 task_complete.py 的适用条件

## 规则

`/work` skill Step 4 收尾时，**仅当任务目标包含真实代码项目时**才跑 `python ~/.claude/scripts/task_complete.py <项目目录> --fix`。
对仅有 REQUIREMENTS.md / DESIGN.md 的讨论阶段任务目录（典型路径 `D:/ClaudeTasks/active/<task>/`），**直接跳过**。

**Why**：
- `task_complete.py` 的 DOC-01 检查硬性要求 `<项目目录>/docs/` 存在；任务讨论目录里 REQUIREMENTS/DESIGN 直接放在根，没有 `docs/` 子目录
- 喂给它讨论目录会必然报 `❌ [DOC-01] docs/ 目录不存在`，干扰真问题判断
- 实测案例：2026-04-22 ue-mcp-integration 任务讨论阶段跑 task_complete 触发 1 ERROR 误报

**How to apply**：
- Step 4 流程里判断 `<项目目录>` 是否含 `docs/` 子目录或代码文件（`.cpp/.cs/.py/.ts` 等）
- 否（纯讨论文档）→ 跳过，输出一行说明"任务无代码项目，跳过 task_complete"
- 是（有代码项目）→ 正常跑
- `check_doc_sync.py` 仍要跑（它对讨论阶段会自动跳过 AI 文档同步检查，无副作用）

## 关联

- skill 文件：`~/.claude/skills/work/SKILL.md` Step 4
- 改进方向：要么在 SKILL.md 写明判断逻辑，要么 task_complete.py 自己检测到非代码目录时降级为 INFO 不报 ERROR

---

# `/work` skill 触发场景规则（2026-04-24 补）

## 规则

`/work` 的核心价值是 **load_context + check_doc_status**（拿全局 + 项目状态到上下文）。一旦激活，CLAUDE.md 铁律就会兜住后续工作。**不需要每个回合都重跑**。

### ✅ 应该跑 /work 的场景

| 场景 | 理由 |
|---|---|
| 新会话开第一刀正式活 | 上下文全空，必须 load |
| 切到新项目目录 | 全局 active project 变了 |
| 切到无关任务 | 上下文积累的是上个任务的，错配 |
| 跨天 / 跨周回来续上次任务 | HANDOFF / CHANGELOG 可能有他人改动 |
| **上下文压缩（compact）后** | 压缩用 summary 替换历史，工作记忆里的 file-path/HANDOFF-状态/CHANGELOG-条目精度下降 → 必须 reload 拿真档案状态 |

### ❌ 不该跑 /work 的场景

| 场景 | 理由 |
|---|---|
| 同会话内继续推进当前任务 | 全局 + 项目档案已在上下文里，重跑就是 token 浪费 |
| 微小修补 / 实验性试探 | Step 2 模板对小事过度结构化 |
| 紧接上一轮的 follow-up（"修一下那个 bug" / "再跑一次"）| 上下文已就绪 |

### 判定标准（一句话）

> **"我现在还需要重新加载全局上下文吗？"**
> - 已经在上下文里 → 跳过 /work，直接干（CLAUDE.md 铁律自动生效）
> - 不在 / 上下文被压缩了 → 跑 /work

## Why

- "效果稳定"的真因是 **CLAUDE.md 铁律**（CHANGELOG 当场记 / 不自评 / 沉淀记忆等），不是 /work 本身
- /work 只是**把铁律激活到上下文** —— 一旦激活，同会话内一直生效
- 实测：2026-04-24 长会话后半段没跑 /work，质量没掉
- 重复跑 /work：一次成本 ~3-5k tokens（load_context + check_doc_status + Step 0/1/2 模板），积累很可观

## How to apply

- 新会话第一次正式任务 → 用户输入 `/work` 时跑全套
- **检测到 system 触发 context compression / summary 替换** → 主动建议用户重跑 /work（"刚压缩了上下文，要不要 /work 重新拿档案状态？"）
- 同会话连续推进 / 用户没明说 /work → 直接干，不主动触发

## 不做的事

- ❌ 不要设计"轻量 /work"（over-engineering，用户已识别）
- ❌ 不要每个回合自动跑 load_context（同会话浪费）

## 更新日志
- 2026-04-22：初次创建（ue-mcp-integration 讨论阶段触发 DOC-01 误报）
- 2026-04-24：加 `/work` 触发场景规则段（用户在 XDAdaptivePerformance 长会话末尾问"轻量 work 是不是该做"，明确不做，改触发条件即可。同时补"压缩后必须重跑 /work"）
