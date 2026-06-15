---
name: triage
description: 轻量问题消化流程。Use when 用户打 /triage，或想周期性处理 issues、feedback、归档候选、health warning 等 inbox；AI 先扫描并提案，用户确认“修/task/work/drop”后才执行或关闭。不要用于已明确进入 /work 的正式实现任务。
---

# Triage

## When to use

- 用户说 `/triage`、问题消化、清 backlog、处理 open issue / feedback / warning。
- 目标是快速决定“现在修、开 task、进正式 work、还是丢弃”。
- **不要用**：用户已明确要求直接实现某个确定任务（按普通执行或 `/work`）。

## Workflow

### 1. Scan inbox first

先跑只读扫描脚本，不手翻目录开局：

```powershell
python ~/.claude/scripts/scripts/triage_inbox.py --json
```

如 junction 不可用，在仓库内跑：

```powershell
python harness/scripts/triage_inbox.py --json
```

脚本只做确定性收集和建议档，不调用 LLM、不写文件。

### 2. AI propose

基于扫描结果给用户一个短列表，按影响和可行动性排序。每项最多一行：

- 来源与标题
- 建议：`修` / `task` / `work` / `drop`
- 理由
- 若建议 `修`，列最小 patch 和验证命令

AI 只提案；不要替用户做最终价值判断。

### 3. User choose

等待用户选择，或用户批量确认。四个动作含义：

- `修`：范围小、可逆、验证清楚；直接最小改动 + 跑验证。
- `task`：范围清楚但不适合当场做；创建/追加轻量 task。
- `work`：多文件、有设计取舍或风险；切到正式 `/work` 流程。
- `drop`：重复、陈旧、低价值或越界；必须写 drop reason。

未确认前不要修改来源状态，不要关闭 issue/feedback。

### 4. Execute or route

- `修`：只改必要文件；跑对应测试/检查；失败则 fail loud，不伪装完成。
- `task`：用现有 task 创建/续跑规则，不新建第二套 ledger。
- `work`：按 `/work` 读取上下文、确认目标、走 Change Packet / quality gate（如适用）。
- `drop`：只在用户确认后回写来源，记录原因。

### 5. Verify and close source

完成后把验证证据写回来源文件或任务测试记录：

- issue：确认修复/路由/drop 后，按现有 issue 文件格式把 `status` 改为 `closed`，追加关闭原因和验证命令。
- feedback：只有用户确认该条不再需要 active 时，才改状态或追加 supersede/drop 说明。
- task/work：在对应任务的 `test/测试.md`、`ops/CHANGELOG.md` 或交付记录里留下证据。

关闭必须可追溯：写清动作、原因、验证命令或人工确认。
