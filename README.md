# Global Memory v1.2.0

个人 AI 工作系统的 active 单仓库：记忆、Agent、Skill、Hook 和 harness 脚本都从这里维护，通过 Git 同步到多设备。

当前更准确的产品边界：这是 **Claude Code harness + global memory 治理系统**，不是已经完成的通用多客户端 memory engine。`harness/client_manifest.json` 里 `claude_code` 是完整生命周期 stable，`generic_cli` 只保证 read-only Context Brief stable，Codex CLI 仍是 experimental/manual。用开源化标准评估时，以 `maintain.py release-check --profile oss --json` 的 blocker/warning 为准；只做私有成熟度审计时，用 `maintain.py release-check --profile private-audit --json`，它不会把不发布决策误当成本地治理 blocker。

## 当前边界

| 维度 | 当前状态 | 机器检查 |
|---|---|---|
| 外部入门 | 最小 read-only 评估、Claude Code 安装、generic CLI Context Brief | [docs/getting-started.md](docs/getting-started.md) |
| 能力边界 | core / optional / experimental / legacy 已分层；140 个 harness 脚本均有能力归属 | [docs/capabilities.md](docs/capabilities.md) / `python harness\scripts\check_capability_manifest.py --json` |
| 客户端支持 | Claude Code full-lifecycle stable；generic CLI context stable；Codex CLI experimental/manual；完整多客户端闭环仍是 warning | `python harness\scripts\check_client_manifest.py --json` |
| 许可证 | 未决；缺少 `LICENSE` 会阻断外部发布 profile | [docs/license-decision.md](docs/license-decision.md) |
| 发布范围 | 当前仓库含个人数据/任务上下文；外部发布需拆分或脱敏 | [docs/publish-scope.md](docs/publish-scope.md) |
| 路径配置 | `harness/config.py` 集中解析 repo、Claude home、task、log、cache roots | `python harness\scripts\gate_check.py --json` |
| Hook 配置 | `hook_manifest.json` 为 source of truth，bootstrap 渲染 settings | `python harness\scripts\check_hook_alignment.py --strict --json` |
| 当前 OSS checkpoint | 外部源码安全、release verdict、ledger/gaps/decisions、manifest 摘要聚合；剩余缺口按 owner/code/docs 分类 | `python harness\maintain.py release-checkpoint --json` / [docs/capability-map-and-oss-gap.md](docs/capability-map-and-oss-gap.md) |
| 发布/外部接入评估 | 聚合 blocker/warning；legacy health 需显式 opt-in | `python harness\maintain.py release-check --profile oss --json` |
| 私有成熟度审计 | 保留发布类缺口为 warning；用于当前不公开发布的治理视图 | `python harness\maintain.py release-check --profile private-audit --json` |

## 架构（双轴）

一套模型，两条正交轴——别当线性嵌套层级。每轴「3 核心 + 1 旁挂管理者」。

**运转轴（HOW · 用什么把每步钉死）** —— 核心三层级，抽象高→低、确定性低→高：

```
┌──────────────────────────────────────────────────┐
│  Rules   — 行为合同「做什么、不做什么」            │
│            载体: agents/CLAUDE.md, rules/*.md      │
├──────────────────────────────────────────────────┤
│  Skills  — 流程固化「怎么做、按什么顺序」          │
│            载体: skills/*/v1/SKILL.md              │
├──────────────────────────────────────────────────┤
│  Script  — 确定性变换 + 硬门禁「做没做到」         │
│            载体: harness/verify/ hooks/ health/    │
└──────────────────────────────────────────────────┘
   旁挂 ▸ harness — 强制执行 + 自动触发 + 隔离的包裹层
          (CLI 无关; hook 只是 Claude Code 实现)
   [DORMANT] Subagent — 理应更高一层, 当前不需要已暂移
             (非 harness 隔离子功能, 非伪层)
```

**设计轴（WHAT · 数据怎么流、生命周期）** —— 核心闭环 + 旁挂维护：

```
        ┌──────────────────────────────────┐
        ▼                                  │
   执行(含判断) → 沉淀 → 反馈 ─────────────┘
   (推到验收)   (入库)  (召回注入回执行)

   旁挂 ▸ 维护 — 在闭环外, 不参与流转,
                只观测统计三层健康
```

**判断**不入任一轴的组件/钉法列：判断 = AI 残余（住执行层）+ 人（principal）。

**两轴正交**：HOW 定每步钉法，WHAT 定数据流与生命周期，交叉处的应然分布（WHAT 4 层 × 钉法）见 `rules/接入索引.md` §0 的格子图。

```
支撑工具（不参与版本治理）: harness/reporting/ md2html/ control_panel_pyside/
数据层（semver 不覆盖）: knowledge/ feedback/ fixes/ projects/ tasks/
```

> 旧表述「L1 Rules → L2 Skills → L3 Subagent → L4 Scripts 线性 5 层链」已废止——它把 HOW 职责、harness 包裹层、Subagent 与 Utilities 硬塞进一条嵌套链，是 category error。术语与交叉详见 `rules/接入索引.md` §0。

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
| OSS checkpoint 聚合 | `python harness\maintain.py release-checkpoint --json` |
| OSS checkpoint 阻断态 JSON | `python harness\maintain.py release-checkpoint --strict --json` |
| 外部接入/开源倒逼检查 | `python harness\maintain.py release-check --profile oss --json` |
| 私有成熟度审计检查 | `python harness\maintain.py release-check --profile private-audit --json` |
| 当前剩余缺口表 | `python harness\maintain.py release-gaps` |
| CI/自动化缺口阻断 | `python harness\maintain.py release-gaps --strict --json` |
| Owner 决策队列 | `python harness\maintain.py release-decisions --json` |
| Owner 决策阻断 | `python harness\maintain.py release-decisions --strict --json` |
| 能力边界检查 | `python harness\scripts\check_capability_manifest.py --json` |
| 客户端边界检查 | `python harness\scripts\check_client_manifest.py --json` |
| 通用 CLI 获取 Context Brief | `python harness\scripts\client_context.py --client generic_cli --task unknown --query "你的问题" --json` |
| 安装开发验证依赖 | `python -m pip install -r requirements-dev.txt` |
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
├── CHANGELOG.md             # 私有变更审计日志
├── PUBLIC_CHANGELOG.md      # 外部源码范围的公开变更记录
├── memory-rules.md          # 记忆写入和 CHANGELOG 分级规则
├── bootstrap.py             # 本机部署/校验
├── check_health.py          # [LEGACY] 记忆仓库健康检查
├── agents/                  # L1 Rules — CLAUDE.md 全局铁律 + Agent 配置
├── rules/                   # L1 Rules — 4 层规格(执行/沉淀/反馈/维护) + 接入索引
├── skills/                  # L2 Skills — 流程定义
├── harness/                 # L4 Scripts + Utilities
│   ├── maintain.py          #   唯一 CLI 入口
│   ├── verify/              #   L4 硬性检查
│   ├── hooks/               #   L4 运行时 hook
│   ├── health/              #   L4 健康检查
│   ├── reporting/           #   Utilities 报告
│   ├── md2html/             #   Utilities 渲染
│   ├── control_panel_pyside/#   Utilities GUI
│   ├── capability_manifest.json # 能力边界 source of truth
│   ├── client_manifest.json     # 客户端支持边界 source of truth
│   ├── config.py                # repo/Claude/task/log/cache 根路径共享配置
│   ├── hook_manifest.json       # Hook 链 source of truth
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
| 行为合同语义改动（CLAUDE.md 路由/安全边界，改变"做什么/不做什么"） | major |
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
  │               ├─ sync_inject.py ────── 注入其他 agent 的 sync 状态
  │               ├─ route_check.py ────── 注入路由提示
  │               └─ retrieve_inject.py ── 注入 Context Brief
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

外部接入/开源倒逼入口：maintain.py release-check --profile oss --json
私有成熟度审计入口：maintain.py release-check --profile private-audit --json
  ├─ scan_orphan_scripts.py ──▶ 脚本是否进入 registry
  ├─ check_capability_manifest.py ──▶ 能力边界是否机器可读
  ├─ maintenance_manifest ──▶ 主控/GUI/AI 维护入口是否存在且参数一致
  ├─ catalog_freshness ──▶ agents/skills/harness 自动目录是否已刷新
  ├─ check_client_manifest.py ──▶ 客户端支持是否被夸大
  ├─ check_hook_alignment.py ──▶ hook manifest/bootstrap/runtime/registry 对齐
  ├─ bootstrap.py check ──▶ 运行时部署完整性
  ├─ check_publish_scope.py ──▶ tracked private paths 是否阻断外部发布
  ├─ export_source_scope.py ──▶ clean source 导出计划是否可复查
  ├─ scan_external_safety.py ──▶ 计划外发源码是否有 secret/本机路径风险
  ├─ path_config ──▶ release-facing 脚本是否复用 harness/config.py
  ├─ fix_hardcoded_paths.py ──▶ 本机硬编码路径阻断
  ├─ gate_check.py --json ──▶ G1-G9 治理门禁
  ├─ verify_output_contracts.py ──▶ JSON/stdout/stderr 契约
  └─ smoke_test.py ──▶ smoke 无 fail/warn

派生缺口视图：release_issue_ledger.py --json
主入口 checkpoint 聚合：maintain.py release-checkpoint --json
自动化 checkpoint 阻断：maintain.py release-checkpoint --strict --json
主入口缺口表：maintain.py release-gaps
自动化阻断缺口表：maintain.py release-gaps --strict --json
主入口 owner 决策队列：maintain.py release-decisions --json
自动化 owner 决策阻断：maintain.py release-decisions --strict --json
人类可读脚本缺口表：release_issue_ledger.py --gap-table-only
  └─ 读取 release-check 当前结果，生成 open/resolved/deferred issue ledger 与 owner 决策队列
```

## 子目录文档

各子目录的组件清单由脚本自动生成：

| 目录 | README | 内容 |
|------|--------|------|
| `agents/` | [agents/README.md](agents/README.md) | 12 个 Agent 的名称和描述 |
| `skills/` | [skills/README.md](skills/README.md) | 11 个 Skill 的名称和描述 |
| `harness/` | [harness/README.md](harness/README.md) / [docs/scripts-registry.md](docs/scripts-registry.md) | 以 registry 和 manifests 为准 |
| `CONTRIBUTING.md` | [CONTRIBUTING.md](CONTRIBUTING.md) | 新 Hook / Skill / Script / Agent 的接入规则 |
| `docs/getting-started.md` | [docs/getting-started.md](docs/getting-started.md) | 外部最小安装、验证、接入路径 |
| `docs/capabilities.md` | [docs/capabilities.md](docs/capabilities.md) | 18 个能力域的外部用户说明 |
| `docs/capability-map-and-oss-gap.md` | [docs/capability-map-and-oss-gap.md](docs/capability-map-and-oss-gap.md) | 当前能力整理和开源倒逼剩余缺口 |
| `docs/license-decision.md` | [docs/license-decision.md](docs/license-decision.md) | 许可证未决 blocker 的决策说明 |
| `docs/publish-scope.md` | [docs/publish-scope.md](docs/publish-scope.md) | 外部发布范围和个人数据边界 |

更新：`python harness/generate_catalog.py`。检查：`python harness/generate_catalog.py --check --json`。`release-check --profile oss` 会通过 `catalog_freshness` 检查阻断过期的自动目录。

## Release Notes

### v1.5.0 (2026-06-03)
Harness 四层架构落地（执行/沉淀/反馈/维护）。`agents/CLAUDE.md` 重写为 19 条纯行为铁律（177→~50 行，路由/阈值/编码规范/记忆写入全移出）；新建 `rules/`（4 层规格 + 接入索引，AI 按需加载）；`docs/` 加工具组件总览 + 主循环与日志地图 + 多数据源治理方案；work SKILL 抽薄（257→~143 行，查阅型移层规格，留必跑步引全局）；RULE_ENFORCEMENT_MATRIX 加 R1-R19 索引。设计/落地全程见 task `harness-3layer-architecture`。reconcile.py（多源统一治理）设计已定，实现待后续。

### v1.4.0 (2026-06-02)
Tier 2 强证据门：quality_gate.py 的 test-quality review 新增必需 `Red-Evidence` + `Mutation` 两节（非空，写 none 判格式错误 → Tier 2 BLOCK），防 AI 写全绿假测试。review-pack 模板同步、可经 `evidence.test_quality_red_evidence` 关闭。配套 feedback 记忆 `ai-test-failure-modes-four-defenses`。

### v1.3.1 (2026-06-02)
agents/CLAUDE.md 措辞原子化 + 去模糊：删自我稀释句、拆复合规则为原子、补缺失阈值、行内映射转表格、拆解「其他」垃圾抽屉。无规则语义变更，纯可读性/可遵守性优化。

### v1.3.0 (2026-06-02)
跨任务经验召回层（task_experience_index：旁路索引 + LLM triage + 跨任务 retrieve + 升进提醒）。
work skill 删 v1，统一 v2 4 子目录 + legacy 读兼容。
vendor learning-opportunities skill（AI 辅助编码学习练习）+ git commit 自动触发 hook（python 移植）。

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
