# global-memory 维护工具手册

这份文档给人类维护者看，用来回答三个问题：

1. 当前这套 harness engineering 体系有哪些工具。
2. 自动同步、健康检查、任务收尾到底由谁触发。
3. 出问题时先看哪里、跑什么命令。

它不替代脚本源码中的细节注释；脚本行为以代码为准。

## 快速判断：我现在该用哪个工具

| 你想做什么 | 首选入口 | 说明 |
|---|---|---|
| 看仓库记忆索引、YAML、统计、Git 状态是否健康 | `python check_health.py` | 根目录入口，适合日常巡检。 |
| 自动修复 `MEMORY.md` 索引/统计 | `python check_health.py --fix` | 会改索引/统计；若有未提交变更，也会尝试自动 commit/push。 |
| 验证本机 `~/.claude` junction 和 hooks | `python bootstrap.py check` | 确认 active runtime 确实指向本仓库。 |
| 重新部署 agents/scripts/skills/settings hooks | `python bootstrap.py install` | 会写 `~/.claude/settings.json` 并重建 junction。 |
| 手动触发一次 Git 同步 | `python harness\auto_sync_daemon.py --once` | 会先跑索引/统计维护，再 pull/add/commit/push。 |
| 看全套 harness 检查项 | `python harness\verify_all.py --checks` | 只列检查项，不执行全部检查。 |
| 正式任务收尾 | `python harness\task_complete.py <project_dir> --fix` | 跑规范、基础设施、索引、统计、进度文档检查。 |
| 排查 Prompt/Agent/Skill 配置一致性 | `python harness\verify_prompt_system.py --report` | 检查 CLAUDE.md 与 Agent 配置重复、漂移、缺失。 |

## 部署与运行入口

### `bootstrap.py`

职责：把仓库部署到 Claude Code 运行位置。

常用命令：

```powershell
python bootstrap.py check
python bootstrap.py install
```

它负责：

| 项 | 行为 |
|---|---|
| Skill junction | `~/.claude/skills/<skill>` 指向 `skills/<skill>/v1`。 |
| Agent junction | `~/.claude/agents` 指向 `agents/`。 |
| Script junction | `~/.claude/scripts` 指向 `harness/`。 |
| Hook settings | 渲染 `~/.claude/settings.json` 的 `hooks` 字段。 |

当前部署的 Skill 清单在 `bootstrap.py` 的 `SKILLS` 常量里维护。

### `check_health.py`

职责：根目录级记忆仓库健康检查。

常用命令：

```powershell
python check_health.py
python check_health.py --fix
python check_health.py --json
```

注意：`--fix` 不只是“本地修复”。当前实现会在检测到未提交变更时执行 `git add -A`、自动 commit，并尝试 push。

它检查：

| 检查 | 内容 |
|---|---|
| 索引一致性 | `MEMORY.md` 链接是否指向真实文件。 |
| 孤儿文件 | topic 目录下是否有未收录到索引的文件。 |
| 文件计数 | `MEMORY.md` 底部统计是否和实际一致。 |
| YAML 规范 | topic 文件是否有必要 frontmatter 字段。 |
| 跨层重复 | 项目级 memory 和全局 memory 是否有同名文件。 |
| Git 同步 | 未提交变更、ahead/behind 状态；`--fix` 下会尝试提交和推送。 |

注意：历史文档里可能出现 `verify_memory.py` 作为健康检查入口；当前日常入口优先用根目录 `check_health.py`。

## 自动维护链路

### 对话结束链路：Stop hook

部署后，`~/.claude/settings.json` 中的 `Stop` hook 会调用：

```powershell
python ~/.claude/scripts/post_task_hook.py --auto-fix
```

因为 `~/.claude/scripts` 是 junction，所以实际脚本来自：

```text
harness/post_task_hook.py
```

它会做：

| 步骤 | 行为 |
|---|---|
| 索引检查 | 检查 `MEMORY.md` 的 `AUTO-INDEX` 是否和 topic 文件一致。 |
| CHANGELOG 检查 | 今天有 Git 变更但无 CHANGELOG 记录时给警告。 |
| 自动修复 | `--auto-fix` 下调用 `sync_index.py` 和 `update_stats.py`。 |
| Git 同步 | 对 active `global-memory` 仓库执行 `git add`、`commit`、`push`。 |

### 后台链路：自动同步守护进程

入口：

```powershell
python harness\auto_sync_daemon.py
pythonw harness\auto_sync_daemon.py
python harness\auto_sync_daemon.py --once
```

它监听 active 仓库文件修改，最后一次变更后空闲 5 分钟触发同步。同步前会运行：

```text
harness/sync_index.py
harness/update_stats.py
```

日志写到：

```text
~/.claude/auto_sync.log
```

如果要开机自启，当前仓库提供 `harness/auto_sync_startup.vbs`，可放到 Windows `shell:startup`。

## 健康检查与验证矩阵

| 脚本 | 用途 | 什么时候跑 |
|---|---|---|
| `check_health.py` | 记忆仓库日常健康检查。 | 平时最常用。 |
| `harness/verify_all.py` | Harness 总验证，一键检查基础设施并和基线对比。 | 改 Agent/Skill/harness 后。 |
| `harness/verify_docs.py` | 文档一致性检查。 | 改 `/work` 文档流程或任务文档后。 |
| `harness/verify_workflow.py` | 对照 `templates/workflow.json` 校验项目流程产物。 | 项目流程文档漂移时。 |
| `harness/verify_prompt_system.py` | 检查 `CLAUDE.md`、Agent 配置、Skill 引用一致性。 | 改 prompt/agent/skill 规则后。 |
| `harness/verify_conventions.py` | 跨项目规范硬检查。 | 正式项目交付前。 |
| `harness/task_complete.py` | 收尾总入口，组合规范、基础设施、索引、统计、进度文档检查。 | 正式任务完成前。 |

`verify_all.py --checks` 当前注册的检查包括：`CLAUDE.md`、`MEMORY.md`、Skill junction、Skill YAML、Agent 配置、核心脚本、工程模板、记忆健康度、文档一致性、Git 状态、自动同步。

## Hook 体系

`bootstrap.py install` 会把 hook 配置写进 `~/.claude/settings.json`。当前主要 hook 如下：

| Hook | 匹配 | 脚本 | 目的 |
|---|---|---|---|
| `Stop` | 全部 | `harness/post_task_hook.py --auto-fix` | 任务结束后修索引/统计并尝试同步。 |
| `PreToolUse` | `Bash` | `harness/hooks/dangerous_command_blocker.py` | 拦截危险 shell 命令。 |
| `PreToolUse` | `Write|Edit` | `harness/hooks/memory_file_protector.py` | 保护记忆文件写入规则。 |
| `PreToolUse` | `Write|Edit` | `harness/hooks/doc_gate.py` | 在任务文档状态不满足时拦截代码编辑。 |
| `PreToolUse` | `Write|Edit` | `harness/hooks/diff_backup.py` | 编辑前备份 diff。 |
| `PostToolUse` | 全部 | `harness/hooks/audit_logger.py` | 记录工具调用审计日志。 |
| `PostToolUse` | `Write|Edit` | `harness/hooks/diff_show.py` | 编辑后弹出 VS Code diff 视图。 |
| `SubagentStart` | 全部 | `harness/hooks/subagent_logger.py` | 记录 subagent 启动。 |

Hook 共享辅助库在 `harness/hooks/_hook_lib.py` 和 `harness/hooks/_task_resolver.py`。

## Agent / Skill / Script 分工

### Agent

| 文件 | 作用 |
|---|---|
| `agents/CLAUDE.md` | 全局约束、启动协议、记忆写入摘要。 |
| `agents/learning-agent.md` | 学习、面试、知识缺口追踪。 |
| `agents/work-agent.md` | 正式生产任务、代码、文档、审查、Bug 定位。 |
| `agents/design-reviewer.md` | 设计文档二次审查，只读。 |
| `agents/guardian-agent.md` | 交付前合规检查，只读。 |

### Skill

| Skill | 作用 |
|---|---|
| `work` | 正式任务入口，管理讨论文档、实现阶段和收尾检查。 |
| `check` | 设计阶段二次 review，输出结构化报告。 |
| `diff` | 交互式查看 edit/write 后积累的 diff。 |
| `bug-locator` | 系统化 Bug 定位流程。 |
| `cpp-tutor` | C++/并发/现代 C++ 学习辅导。 |
| `migrate-executor` | 多文件迁移、重构、回滚验证。 |
| `skill-creator` | 创建或更新 Skill。 |
| `skill-auditor` / `skill-reviewer` / `smoke-test` | Skill 质量、审查、冒烟测试辅助。 |

### Script / Harness

脚本按职责分组理解，不需要逐个背：

| 分组 | 代表脚本 | 作用 |
|---|---|---|
| 部署 | `bootstrap.py`、`deploy_hooks.py`、`deploy_skill_symlinks.*` | 把仓库接到运行时。 |
| 同步 | `auto_sync_daemon.py`、`sync_memory.sh`、`sync_manager.bat` | Git 自动/手动同步。 |
| 记忆维护 | `sync_index.py`、`update_stats.py`、`append_changelog.py`、`changelog_archive.py` | 维护 `MEMORY.md` 和 `CHANGELOG.md`。 |
| 项目流程 | `task_complete.py`、`verify_workflow.py`、`baseline_compare.py` | 正式任务收尾和流程基线。 |
| 规范验证 | `verify_all.py`、`verify_conventions.py`、`verify_docs.py`、`verify_prompt_system.py` | 检查系统、文档、prompt 和规范漂移。 |
| 上下文生成 | `generate_project_context.py`、`extract_to_memory.py`、`session_report.py` | 拼合项目上下文、提取记忆、生成会话报告。 |
| Hook | `harness/hooks/*.py` | Claude Code tool lifecycle 拦截和审计。 |

## 常见问题与排查

### 我不确定自动同步有没有在跑

先看守护进程：

```powershell
python harness\verify_all.py
```

再看日志：

```text
~/.claude/auto_sync.log
```

如果只想立即同步一次：

```powershell
python harness\auto_sync_daemon.py --once
```

### `~/.claude` 里的 Skill 或脚本不像是最新的

先检查：

```powershell
python bootstrap.py check
```

如果 junction 或 hooks 不一致，再重新部署：

```powershell
python bootstrap.py install
```

### `MEMORY.md` 索引不对

优先用根目录健康检查：

```powershell
python check_health.py --fix
```

如果只想重建索引和统计：

```powershell
python harness\sync_index.py
python harness\update_stats.py
```

### README 统计或说明过时

当前 README 不再作为完整工具清单维护，避免频繁漂移。工具细节优先更新本文件。

如果确实需要自动更新 README 统计，可看：

```powershell
python harness\update_readme.py --dry-run
```

### 修改 Agent / Skill / Prompt 后担心规则冲突

跑：

```powershell
python harness\verify_prompt_system.py --report
python harness\verify_all.py
```

如果只想看总检查项：

```powershell
python harness\verify_all.py --checks
```

### 正式任务收尾时该跑什么

在项目目录明确时：

```powershell
python harness\task_complete.py <project_dir> --fix
```

这会组合运行规范检查、基础设施检查、索引同步、统计更新和项目进度文档检查。

## 维护约定

| 规则 | 原因 |
|---|---|
| README 只写总览，不展开完整脚本表。 | 保持人类入口轻量，避免再次变成大杂烩。 |
| 工具说明集中写在 `MAINTENANCE.md`。 | 维护者要找命令时有单一入口。 |
| 脚本行为以源码 docstring 为准。 | 文档可能落后，代码是事实来源。 |
| 改 hook、Agent、Skill 后跑 `bootstrap.py check` 和 `verify_prompt_system.py`。 | 防止运行入口和配置说明漂移。 |
| 改记忆 topic 后按 `memory-rules.md` 判断是否更新 CHANGELOG。 | 保留审计链，避免记忆仓库不可追溯。 |
