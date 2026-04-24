# Global Memory

这是个人 AI 工作系统的 active 单仓库：记忆、Agent、Skill、Hook 和 harness 脚本都从这里维护，并通过 Git 同步到多设备。

如果你只是想确认“这套东西现在怎么跑、该用哪个命令”，先读本页；如果你只想知道 GUI 面板怎么点，读 [CONTROL_PANEL.md](CONTROL_PANEL.md)；如果你要维护脚本、排查自动同步或理解 hook 链路，读 [MAINTENANCE.md](MAINTENANCE.md)。

## 3 分钟心智模型

这套仓库分三层：

| 层 | 目录 / 文件 | 作用 |
|---|---|---|
| 记忆层 | `MEMORY.md`、`feedback/`、`knowledge/`、`fixes/`、`decisions/`、`interview/` | 存长期记忆、项目上下文、经验沉淀；`MEMORY.md` 是索引入口。 |
| 工作流层 | `agents/`、`skills/`、`templates/` | 定义 AI 的角色、Skill 入口、人类/机器文档模板。 |
| Harness 层 | `bootstrap.py`、`check_health.py`、`harness/` | 部署 junction、运行 hook、自动同步、健康检查和任务收尾。 |

核心原则：动态判断放在 Agent，稳定流程放在 Skill，确定性规则放在脚本。能用脚本检查的，就不要靠 AI 记忆。

## 日常我该跑什么

| 场景 | 命令 |
|---|---|
| 打开人类主控 GUI | `harness\control_panel.bat` |
| 看面板怎么用 | [CONTROL_PANEL.md](CONTROL_PANEL.md) |
| 快速状态快照（只读） | `python harness\maintain.py status --json` |
| 只读体检总入口 | `python harness\maintain.py doctor` |
| GUI/脚本用 JSON 体检 | `python harness\maintain.py doctor --json` |
| 安全本地修复（不提交/不推送） | `python harness\maintain.py fix` |
| 同步前只读预览 | `python harness\maintain.py sync --preview --json` |
| checkpoint 提交并推送 | `python harness\maintain.py sync --source manual` |
| 生成维护报告 | `python harness\maintain.py report --markdown` |
| 快速检查记忆仓库健康 | `python check_health.py` |
| 检查本机 Claude Code junction 和 hooks 是否部署正确 | `python bootstrap.py check` |
| 重新部署 `~/.claude` 下的 agents/scripts/skills/settings hooks | `python bootstrap.py install` |
| 查看完整维护工具说明 | [MAINTENANCE.md](MAINTENANCE.md) |

## 当前运行入口

本仓库是 active source of truth。Claude Code 运行时入口通过 junction 指向这里：

| 运行位置 | 指向 |
|---|---|
| `~/.claude/global-memory` | 本仓库 |
| `~/.claude/scripts` | `harness/` |
| `~/.claude/agents` | `agents/` |
| `~/.claude/skills/<skill>` | `skills/<skill>/v1` |

`bootstrap.py` 负责创建和校验这些 junction，并渲染 `~/.claude/settings.json` 的 hooks。

## 自动同步到底有没有

有，但分两条链路：

| 链路 | 入口 | 做什么 |
|---|---|---|
| 对话结束后 | `Stop` hook -> `harness/post_task_hook.py --auto-fix` -> `maintain.py sync --source stop-hook` | 检查索引、CHANGELOG，必要时生成 `checkpoint:` 提交并推送。 |
| 后台守护进程 | `harness/auto_sync_daemon.py` -> `maintain.py sync --source daemon` | 监听仓库文件修改，空闲 5 分钟后触发统一同步入口。 |
| 人类主控台 | `harness\control_panel.bat` | GUI 中查看状态、同步预览、运行 doctor、安全修复、一键同步、管理 daemon、生成维护报告。 |

更多细节和排查方式见 [MAINTENANCE.md#自动维护链路](MAINTENANCE.md#自动维护链路)。

面板打开后会每 10 秒静默刷新快速状态，并每 2 秒读取外部事件。AI 或脚本可以用本地 CLI 写事件：

```powershell
python harness\panel_api.py notify --source ai --level info --title "分析完成" --message "建议先生成同步预览。"
```

## AI 工作流怎么看

| 入口 | 给谁看 | 说明 |
|---|---|---|
| `agents/CLAUDE.md` | AI | 全局约束、启动协议、记忆规则摘要。 |
| `agents/learning-agent.md` / `agents/work-agent.md` | AI | 学习模式和工作模式的详细行为定义。 |
| `skills/work/v1/SKILL.md` | AI + 维护者 | `/work` 正式任务流程：文档校验、讨论落地、实现、收尾。 |
| `templates/workflow.json` | 脚本 + 维护者 | 机器可读流程定义，供 `verify_workflow.py` 校验。 |
| `harness/ai_runner.py` | GUI + AI CLI adapter | V1 只允许只读诊断和计划生成；`execute` 模式明确禁用。 |
| `MAINTENANCE.md` | 人类 | 不逐个读脚本时，用来理解整体工具和流程。 |

## 目录导航

```text
global-memory/
├── README.md                # 人类总览入口
├── CONTROL_PANEL.md         # GUI 面板简单使用说明
├── MAINTENANCE.md           # 维护工具手册
├── MEMORY.md                # 全局记忆索引 + 活跃项目
├── CHANGELOG.md             # 变更审计日志
├── memory-rules.md          # 记忆写入和 CHANGELOG 分级规则
├── bootstrap.py             # 本机部署/校验入口
├── check_health.py          # 记忆仓库健康检查入口
├── agents/                  # Agent 配置源目录
├── skills/                  # Skill 源目录
├── harness/                 # GUI 主控、hooks、同步、验证、收尾脚本
├── templates/               # 工程文档模板和 workflow.json
├── feedback/                # 行为纠正
├── knowledge/               # 技术知识和深度文档
├── fixes/                   # Bug 修复经验
├── decisions/               # 架构决策和跨项目规范
├── interview/               # 面试准备
├── projects/                # 项目级上下文
└── archives/                # 冷存储归档
```

## 记忆写入规则摘要

| 内容 | 写到哪里 |
|---|---|
| 行为偏好、输出格式、工作习惯 | `feedback/` |
| 技术知识、概念盲区、学习沉淀 | `knowledge/` |
| 反复排查后的 Bug 经验 | `fixes/` |
| 架构选择、跨项目规范、流程决策 | `decisions/` |
| 面试题、话术、复盘 | `interview/` |

CHANGELOG 是否必须更新，以 [memory-rules.md](memory-rules.md) 为准。大原则是：`feedback/`、`fixes/`、`decisions/` 的实质修改必须记审计；普通知识追加可以省略。

## 维护边界

`README.md` 只回答“这是什么、入口在哪、日常怎么用”。不要把每个脚本、Skill、hook 的完整说明继续塞回 README；维护细节统一放进 [MAINTENANCE.md](MAINTENANCE.md)。

## 更新日志

- **2026-04-24**: 常规更新

- **2026-04-24**: 常规更新

- **2026-04-24**: 常规更新

- **2026-04-24**: 常规更新
