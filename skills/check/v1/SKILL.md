---
name: check
description: "Run a design-stage review on an active task. Reads ~/.claude/projects/project_registry.json to resolve the task's docs directory, dispatches an isolated design-reviewer subagent (read-only, opus), and writes the structured markdown report to <task_dir>/REVIEW-<timestamp>.md. Invoke as '/check', '/check <task-name>', or '/check <absolute-path>'. Use when the user wants a second-opinion review of requirement / design documents before implementation."
---

# /check — 设计审查入口

> 固定流程：解析任务路径 → 派生独立 subagent → 写盘 → 摘要

## 何时使用
- 用户输入 `/check`、`/check <任务名>` 或 `/check <绝对路径>` 触发
- 适用场景：需求/设计文档完成，准备进入实现前
- **不适用**：代码已写完的交付前合规检查（用 guardian-agent）

## 输入解析

参数形式（`args`）：

| 形式 | 处理 |
|---|---|
| 空 | 列出 `project_registry.json` 中的 `active_tasks`，让用户选 |
| `<任务名>` | 在 `<tasks_root>/<任务名>/` 定位文档（支持模糊前缀匹配） |
| 绝对路径（含 `:` 或以 `/` 开头） | 直接使用该路径作为任务目录，跳过注册表 |

## 执行流程

### Step 1 — 加载项目注册表
```
Read ~/.claude/projects/project_registry.json
```
关键字段：
- `tasks_root`：任务根目录（如 `D:/ClaudeTasks/active`）
- `active_tasks`：当前活跃任务名列表
- `required_docs`：必备文档清单（用于完整性提示）

### Step 2 — 解析目标任务目录

**情况 A — 无参数**：
- 用 `Bash` 列出 `<tasks_root>/` 下的子目录（与 `active_tasks` 取并集）
- 用 `AskUserQuestion` 让用户选一个，或用户可以输入"全部"对每个跑一次（不推荐，先单选）

**情况 B — 任务名**：
- 拼接 `<tasks_root>/<任务名>`
- 不存在 → 在 `<tasks_root>/` 下做前缀模糊匹配（如 `android` → `android-apk-build`）
- 多个匹配 → 列出让用户消歧
- 零匹配 → 报错并列出所有 active_tasks

**情况 C — 绝对路径**：
- 校验路径存在且为目录
- 不存在 → 报错

### Step 3 — 收集待审文档
- 用 `Glob` 列出任务目录下所有 `*.md`，**排除 `REVIEW-*.md`**
- 与 `required_docs` 比对：缺失项在摘要中标注（不阻塞审查）
- 文档为空 → 报错：`任务目录无 .md 文档，无可审查内容`
- 文档过多（>10）→ 提示但继续

### Step 4 — 生成时间戳
```bash
date +"%Y-%m-%d-%H%M"
```
输出路径：`<任务目录>/REVIEW-<timestamp>.md`（绝对路径）

### Step 5 — 派生 subagent

调用 `Agent` 工具：
- `subagent_type`: `design-reviewer`
- `description`: `设计审查 - <任务名>`
- `prompt`: 严格按下方模板填充

**Prompt 模板**：
```
请对以下设计文档进行第二意见审查。

【任务名】：{任务名}

【待审文档】（绝对路径，请逐个 Read）：
- {绝对路径 1}
- {绝对路径 2}
...

【项目根目录】：{任务目录绝对路径}
（按需交叉验证代码，不强制全量扫描）

【目标输出路径】（仅用于在报告头部标注，请勿尝试写入——你没有写工具）：
{REVIEW 文件绝对路径}

【审查维度】（按 design-reviewer.md 第三步四维度模板执行）：
1. 需求覆盖度
2. 技术风险
3. 替代方案评估
4. 可测试性/可维护性

请按 design-reviewer.md 的报告模板返回完整 markdown 作为最终消息。
不要在报告外添加额外说明。
```

### Step 6 — 写盘

subagent 返回 markdown 后，主 Claude 用 `Write` 工具写入 `<任务目录>/REVIEW-<timestamp>.md`。

### Step 7 — 摘要

向用户展示：
1. 报告文件绝对路径
2. 总体判定（🟢/🟡/🔴）
3. 风险汇总表（直接从报告中提取）
4. 建议下一步的第 1 条
5. （如有）`required_docs` 缺失提示

**不要重复输出全文**——用户可点开文件细看。

## 错误处理
- 注册表读不到 / 字段缺失 → 报错并提示用户检查 `~/.claude/projects/project_registry.json`
- 任务目录解析失败 → 列出 `active_tasks` 供参考
- subagent 失败 / 返回非 markdown → 不写盘，原样报错给用户
- 写盘失败（权限/路径不存在）→ 报错并把 markdown 内容贴到对话中作为兜底

## 铁律
- **/check 自身不评审**。所有判断由 subagent 做，主 Claude 只负责调度+写盘+摘要
- **subagent 上下文隔离**。不要把主对话历史塞进 prompt
- **不修改源文档**。subagent 是只读的，主 Claude 也只写 REVIEW 文件
- **不覆盖旧 REVIEW**。时间戳保证唯一性
- **跨电脑可移植**。所有路径从 `project_registry.json` 推导，不硬编码 `D:/` 或 `C:/`
