---
name: /work skill 对纯文档任务跳过 task_complete.py
description: /work Step 4 收尾时对讨论阶段/无代码任务目录不应跑 task_complete.py，否则触发 DOC-01 误报
type: feedback
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

## 更新日志
- 2026-04-22：初次创建（ue-mcp-integration 讨论阶段触发 DOC-01 误报）
