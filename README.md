# Global Memory v1.0.0

个人 AI 工作系统的 active 单仓库：记忆、Agent、Skill、Hook 和 harness 脚本都从这里维护，通过 Git 同步到多设备。

## 四层架构

```
┌──────────────────────────────────────────────────┐
│  L1 Rules — 行为合同                              │
│  "做什么、不做什么"                                │
│  载体: agents/CLAUDE.md, agents/*.md              │
├──────────────────────────────────────────────────┤
│  L2 Skills — 流程固化                             │
│  "怎么做、按什么顺序"                              │
│  载体: skills/*/v1/SKILL.md                       │
├──────────────────────────────────────────────────┤
│  L3 Subagent — 分工调度                           │
│  "谁来做"                                         │
│  载体: CLAUDE.md 路由表 + Agent tool 调用          │
├──────────────────────────────────────────────────┤
│  L4 Scripts — 硬性检查                            │
│  "做没做到"                                       │
│  载体: harness/verify/, harness/hooks/,           │
│        harness/health/                            │
├──────────────────────────────────────────────────┤
│  Utilities — 支撑工具（不参与版本治理）             │
│  harness/reporting/, harness/md2html/,            │
│  harness/control_panel_pyside/                    │
└──────────────────────────────────────────────────┘

数据层（semver 不覆盖）: knowledge/ feedback/ fixes/ projects/ tasks/
```

流转：Rules 定义 → Skills 编排 → Subagent 分派 → Scripts 验证 → 违规反馈回 Rules

## 日常命令

| 场景 | 命令 |
|---|---|
| 只读体检（唯一权威入口） | `python harness\maintain.py doctor` |
| JSON 体检（GUI/脚本用） | `python harness\maintain.py doctor --json` |
| 快速状态快照 | `python harness\maintain.py status --json` |
| 安全本地修复 | `python harness\maintain.py fix` |
| 同步预览 | `python harness\maintain.py sync --preview --json` |
| checkpoint 提交推送 | `python harness\maintain.py sync --source manual` |
| 维护报告 | `python harness\maintain.py report --markdown` |
| GUI 主控台 | `harness\control_panel.bat` |
| 部署校验 | `python bootstrap.py check` |
| 重新部署 | `python bootstrap.py install` |

> `check_health.py` 为 legacy 入口，已被 `maintain doctor` 取代。

## 运行入口

| 运行位置 | 指向 |
|---|---|
| `~/.claude/global-memory` | 本仓库 |
| `~/.claude/scripts` | `harness/` |
| `~/.claude/agents` | `agents/` |
| `~/.claude/skills/<skill>` | `skills/<skill>/v1` |

`bootstrap.py` 负责创建和校验 junction，并渲染 `~/.claude/settings.json` 的 hooks。

## 目录结构

```
global-memory/
├── VERSION                  # 版本号
├── README.md                # 本文件
├── MAINTENANCE.md           # 维护工具手册
├── MEMORY.md                # 全局记忆索引
├── CHANGELOG.md             # 变更审计日志
├── memory-rules.md          # 记忆写入和 CHANGELOG 分级规则
├── bootstrap.py             # 本机部署/校验
├── check_health.py          # [LEGACY] 记忆仓库健康检查
├── agents/                  # L1 Rules — Agent 配置
├── skills/                  # L2 Skills — 流程定义
├── harness/                 # L4 Scripts + Utilities
│   ├── maintain.py          #   唯一 CLI 入口
│   ├── verify/              #   L4 硬性检查
│   ├── hooks/               #   L4 运行时 hook
│   ├── health/              #   L4 健康检查
│   ├── reporting/           #   Utilities 报告
│   ├── md2html/             #   Utilities 渲染
│   ├── control_panel_pyside/#   Utilities GUI
│   └── tests/               #   测试
├── templates/               # 工程文档模板
├── feedback/                # 行为纠正
├── knowledge/               # 技术知识
├── fixes/                   # Bug 修复经验
├── decisions/               # 架构决策
├── interview/               # 面试准备
├── projects/                # 项目上下文
├── tasks/                   # 任务定义
└── archives/                # 冷存储归档
```

## 自动同步

| 链路 | 入口 | 做什么 |
|---|---|---|
| 对话结束后 | Stop hook → `post_task_hook.py` → `maintain.py sync` | 检查索引/CHANGELOG，生成 checkpoint 提交推送 |
| 后台守护 | `auto_sync_daemon.py` → `maintain.py sync` | 监听文件修改，空闲 5 分钟后同步 |
| GUI | `control_panel.bat` | 查看状态、同步预览、doctor、修复 |

详情见 [MAINTENANCE.md](MAINTENANCE.md)。

## 记忆写入规则

| 内容 | 写到哪里 |
|---|---|
| 行为偏好、输出格式 | `feedback/` |
| 技术知识、学习沉淀 | `knowledge/` |
| Bug 修复经验 | `fixes/` |
| 架构选择、跨项目规范 | `decisions/` |
| 面试题、话术 | `interview/` |

CHANGELOG 规则以 [memory-rules.md](memory-rules.md) 为准。

## 版本语义

| 变更类型 | 版本号 |
|---------|--------|
| 行为合同改动（CLAUDE.md 路由/安全边界） | major |
| 权威入口增减、agent 定义改结构 | minor |
| bug 修复、文案措辞、知识库增量 | patch |
| 模块层/数据层变更 | 不动核心版本号 |
