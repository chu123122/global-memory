# Global Memory v1.2.0

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

## 组件调用关系

```
用户输入
  │
  ├─ /work ──▶ L2 Skill (SKILL.md)
  │             ├─ work_context_pack.py ──▶ 读 registry + 任务文档
  │             ├─ check_doc_status.py ──▶ 检查 DESIGN/HANDOFF 存在性
  │             └─ /work implement ──▶ 从人类文档派生 DESIGN.md
  │
  ├─ /check ──▶ L2 Skill → 派 design-reviewer (L3 Subagent)
  │
  ├─ 每轮对话 ──▶ UserPromptSubmit hooks (L4)
  │               ├─ changelog_inject.py ── 关键词触发注入 CHANGELOG
  │               └─ sync_inject.py ────── 注入其他 agent 的 sync 状态
  │
  ├─ 每次工具调用 ──▶ PreToolUse / PostToolUse hooks (L4)
  │                   ├─ dangerous_command_blocker.py ── Bash 命令拦截
  │                   ├─ doc_gate.py ──────────────────── 文档完整性拦截
  │                   ├─ diff_backup.py ───────────────── 编辑前备份
  │                   ├─ audit_logger.py ──────────────── 工具调用审计
  │                   └─ diff_show.py ─────────────────── 编辑后弹 diff
  │
  └─ 会话结束 ──▶ Stop hook (L4)
                  └─ post_task_hook.py
                      ├─ check_index_sync ──▶ MEMORY.md 索引一致性
                      ├─ check_changelog ───▶ CHANGELOG 新鲜度
                      ├─ git_sync_repo ────▶ maintain.py sync
                      ├─ health runner ────▶ 9 项健康检查
                      └─ issue_tracker ────▶ 问题闭环 ETL

体检入口：maintain.py doctor
  ├─ git status
  ├─ bootstrap.py check ──▶ junction/settings/skill 完整性
  ├─ verify_prompt_system.py ──▶ Agent 配置一致性
  ├─ verify_docs.py ──▶ 文档完整性
  └─ smoke_test.py ──▶ 全脚本冒烟
```

## 子目录文档

各子目录的组件清单由脚本自动生成：

| 目录 | README | 内容 |
|------|--------|------|
| `agents/` | [agents/README.md](agents/README.md) | 8 个 Agent 的名称和描述 |
| `skills/` | [skills/README.md](skills/README.md) | 11 个 Skill 的名称和描述 |
| `harness/` | [harness/README.md](harness/README.md) | 28 个脚本 + 15 个 hook + 10 个验证器 + 9 个健康检查 |

更新：`python harness/generate_catalog.py`

## Release Notes

### v1.2.0 (2026-05-17)
/work 流程升级：DESIGN.md 替代 SPEC.md 作为 AI 执行蓝图。
新增多 Agent sync 基础设施（.sync.jsonl + hook 注入）。
check 脚本双向兼容 DESIGN/SPEC。自动目录生成脚本。

### v1.1.0 (2026-05-16)
修复 stop hook git sync 错误处理（降为 warning + stderr 输出）。
statusline 精简为 git branch + context 压力。
bootstrap.py 注册 UserPromptSubmit hooks。

### v1.0.0 (2026-05-15)
四层架构基线。Rules/Skills/Subagent/Scripts 分层定义。
单仓合并完成，bootstrap.py 部署/校验。
