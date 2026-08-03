# Global Memory

> 让 Claude Code 记住你的决定、按你的流程干活、不谎报完成。

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-759-brightgreen)
![Scale](https://img.shields.io/badge/code-76K%20lines-blue)
![Local](https://img.shields.io/badge/RAG-100%25%20local-orange)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

一个自举的 Claude Code harness —— 把「AI 行为铁律、技能流程、确定性门禁、记忆沉淀与召回」装进同一个 Git 单仓库，通过 junction 部署到运行时，让 AI 的工作方式**被显式治理、可审计、可同步**。

<!-- 截图位：把 control_panel / statusline / 一次 /work 跑完的截图放进 docs/assets/ 后，删掉本注释的首尾两行即可显示
![Global Memory 控制面板](docs/assets/control-panel.png)
-->

---

## 解决什么问题

| 痛点 | 这里怎么做 |
|---|---|
| 开新对话，AI 忘了上次定好的架构决策 | 对话与决策自动沉淀入库，检索后按需注入上下文 |
| AI 报告「完成」，实际静默跳过了一半 | worker/verifier 门禁循环：verifier 独占 pass/fail，附失败码审计 |
| AI 写一堆全绿假测试糊弄验收 | Tier 2 强证据门：test-quality review 必需 Red-Evidence + Mutation 两节 |
| 同一个坑踩第三遍 | 跨任务经验索引 + LLM triage，历史踩坑主动召回 |
| AI 跑危险命令、动不该动的路径 | PreToolUse hook 拦截越权路径与危险命令，全量工具调用留审计日志 |

## 硬指标

- **检索质量**：Qwen reranker 在 100 例扩展集上把 Recall@5 **0.49 → 0.72**、MRR **0.36 → 0.55**、负样本 FPR **0.08 → 0.04**；golden 集 Recall@10 = **1.0**；负控 **13/13** 阻断。该轮有 25/150 次 reranker 超时 fallback，因此按**方向性结论**采信，未作为严格 benchmark。
- **工程规模**：**76K** 行 Python（322 文件）、**759** 个测试、**20** 个生命周期 hook、**307** commits / 4 个月持续演进。
- **治理覆盖**：**209** 个 harness 脚本 **100%** 分配到 20 个能力域 × 5 种状态，机器可读、CI 聚合校验。

## 30 秒上手

前置：Python 3.12、git、Ollama。

```bash
git clone https://github.com/chu123122/global-memory.git
cd global-memory
python -m pip install -r requirements-dev.txt
ollama pull bge-m3            # 语义索引用嵌入模型
python bootstrap.py install   # 部署 junction + 渲染 hooks
python bootstrap.py check     # 验证部署
```

日常命令：

| 场景 | 命令 |
|---|---|
| 只读体检（权威入口） | `python harness\maintain.py doctor` |
| 快速状态快照 | `python harness\maintain.py status --json` |
| 安全本地修复 | `python harness\maintain.py fix` |
| 同步预览 | `python harness\maintain.py sync --preview --json` |
| 同步提交推送 | `python harness\maintain.py sync --source manual` |
| OSS 就绪检查 | `python harness\maintain.py release-check --profile oss --json` |

---

## 核心设计

### 1. 本地语义 RAG（不套壳）

全本地、只读、可审计的检索链路：

```
corpus 分块 → bge-m3 嵌入（仅 loopback Ollama）→ SQLite 索引 → RRF 融合排序 → reranker
```

- **明确拒绝** Chroma / Qdrant / LlamaIndex / LangChain —— 检索排序逻辑自主可控。
- **诚实 fallback**：reranker 超时或异常时回退原序，绝不谎报成功；rewrite 实验因超时率过高（122/150）**主动暂停**而非硬上。
- 检索能力经 `gm_mcp` 的 pull-mode MCP 工具暴露给 Agent，配 loopback HTTP warm sidecar（p50 ≤ 1s）。

### 2. 确定性信任模型（work_runner）

`/work` 工作流的 worker/verifier 门禁循环，核心原则：**runner 拥有状态，verifier 拥有 pass/fail，worker 输出不可信**。

内置失败码审计（`FORBIDDEN_SCOPE_TOUCHED` / `FAKE_WORKER_REPORTED_FAIL` / `VERIFIER_TIMEOUT` / `REPAIR_LIMIT_REACHED`）与有界 repair 循环，从机制上防 AI 谎报完成。

### 3. 治理即代码（20 个 hook）

Claude Code 生命周期全覆盖：`UserPromptSubmit` / `PreToolUse` / `PostToolUse` / `Stop` 四个事件上挂了 20 个 hook，负责**拦截**（危险命令、越权路径）、**审计**（工具调用日志）、**注入**（Context Brief、策略事实）、**体检**（9 项健康信号）。

---

## 架构

### 双轴正交模型

不用「L1→L4 线性 5 层链」那种分层（那是 category error：治理强度和数据流向是两个互不相干的维度），改为两条正交轴：

```
运转轴 HOW（每步怎么约束死）        设计轴 WHAT（数据怎么流）
───────────────────────           ───────────────────────
Rules   行为合同「做什么/不做什么」    执行(判断) → 沉淀 → 反馈
Skills  流程固化「怎么做/按什么顺序」    (推到验收)  (入库)  (召回注入)
Script  确定性变换 + 硬门禁「做没做到」     └────── 闭环 ──────┘
   旁挂 harness：强制执行 + 自动触发 + 隔离
```

- **运转轴**回答「这一步凭什么可信」：越往下越确定 —— Rules 是文字约束，Skills 是固定流程，Script 是可执行的硬门禁。
- **设计轴**回答「知识怎么循环」：干活时只让 AI 做判断，产出入库，下次任务自动召回注入。
- 两轴交叉点才是实际行为；判断只住执行层（AI + 人），外三层是纯契约。

### 运行时部署

`bootstrap.py install` 把 `agents/ skills/ harness/` 通过 Windows junction 挂到 `~/.claude/`，并把 hooks / statusLine 渲染进 `~/.claude/settings.json`。数据产物（semantic index / catalog / HTML 预览）全部 gitignore，不污染版本库。

### 自动同步

| 链路 | 入口 | 行为 |
|---|---|---|
| 对话结束 | Stop hook → `post_task_hook.py` | 检查索引/CHANGELOG，stale 时刷新 semantic 派生索引 |
| 手动 Git 同步 | `maintain.py sync --preview` → `--source manual` | 先预览 checkpoint，再确认提交推送 |
| GUI 主控台 | `control_panel.bat` | 状态查看、同步预览、doctor、修复 |

<details>
<summary><b>目录结构</b>（展示范围）</summary>

```
global-memory/
├── bootstrap.py          # 部署/校验（junction 到 ~/.claude/，渲染 hooks）
├── agents/               # 全局行为铁律 CLAUDE.md + Agent 角色定义
├── rules/                # 4 层规格（执行/沉淀/反馈/维护）+ 接入索引
├── skills/               # 流程固化 SKILL（work/check/bug-locator/cpp-tutor…）
├── harness/              # 核心：CLI + semantic RAG + MCP 工具 + hooks + verify + health
│   ├── maintain.py       #   唯一 CLI 入口（doctor/status/fix/sync/release-check…）
│   ├── semantic/         #   本地语义检索（embed/index/query/reranker/rewrite）
│   ├── gm_mcp/           #   pull-mode MCP 工具 + warm sidecar
│   ├── collab/           #   多 agent 协作编排（实验性，Phase 18）
│   ├── hooks/            #   Claude Code 生命周期钩子
│   ├── verify/  health/   #   验证器 + 健康检查
│   └── tests/            #   759 个测试
├── docs/                 # 分类文档（spec/guide/reference + 能力地图）
├── templates/            # 工程文档模板
└── .github/workflows/    # OSS 就绪 CI
```

</details>

<details>
<summary><b>能力域与状态</b></summary>

| 能力域 | 说明 | 状态 |
|---|---|---|
| 核心记忆检索 | retrieve/inject/sidecar/policy_fact | core |
| 运行时 hook 治理 | 生命周期拦截/审计/注入/体检 | core |
| 客户端可移植 | Claude Code stable / generic CLI / Codex | core |
| 发布就绪度 | OSS 双 profile 聚合检查 | core |
| 维护控制面 | maintain.py doctor/status/fix/sync | core |
| 语义检索工具 | gm_mcp 7 个 pull-mode 工具 | experimental |
| 协作编排 | collab lead-worker（Phase 18） | experimental |
| 记忆仓库维护 | 分层记忆 + 索引一致性 | optional |
| 自循环证据 | .meta 提案/实验/评估链 | optional |

完整清单见 `harness/capability_manifest.json`（209 脚本 / 20 域 / 5 状态，CI 强制全覆盖）。

</details>

<details>
<summary><b>技术栈</b></summary>

| 维度 | 内容 |
|---|---|
| 语言 | Python 3.12 |
| 运行时依赖 | `mcp` + `PyYAML`（numpy 可选） |
| 语义检索 | Ollama `bge-m3`（1024 维）+ Qwen3-Reranker-0.6B，SQLite 索引 |
| MCP | pull-mode stdio 工具 + loopback HTTP warm sidecar（p50 ≤ 1s） |
| 测试 | pytest 8（759 个测试 / 80 文件） |
| 规模 | 322 .py / 76K 行 / 427 tracked 文件 |

</details>

---

## 边界与限制

这是一个 **Claude Code harness + global memory 治理系统**，不是已经完成的通用多客户端 memory engine。诚实的能力边界：

| 客户端 | 支持程度 |
|---|---|
| Claude Code | 全生命周期 **stable** |
| `generic_cli` | read-only Context Brief **stable** |
| Codex CLI | **experimental / manual** |

一句话声明，不夸大：Claude Code 全生命周期 stable；`generic_cli` 只保证 read-only Context Brief stable；Codex CLI experimental / manual。

- **数据与代码分离**：数据产物（semantic index、catalog、HTML）全部 gitignore，代码资产与个人数据彻底分开；个人记忆路径不在本仓库展示范围内。
- **实验性能力**：`gm_mcp` 语义检索工具与 `collab` 协作编排标记为 experimental，接口可能变动。

## 深入阅读

| 文档 | 内容 |
|---|---|
| [快速开始](docs/getting-started.md) | 最小安装、验证、接入路径 |
| [能力说明](docs/capabilities.md) | 各能力域的外部用户说明 |
| [能力与 OSS 缺口](docs/capability-map-and-oss-gap.md) | 当前能力整理和开源倒逼剩余缺口 |
| [贡献指南](docs/guide/CONTRIBUTING.md) | 新 Hook / Skill / Script / Agent 接入规则 |
| [发布范围](docs/publish-scope.md) | 外部发布范围和个人数据边界 |
| [维护手册](docs/guide/MAINTENANCE.md) | 日常维护、同步、体检 |
| [License 决策](docs/license-decision.md) | 许可证选型记录 |

<details>
<summary><b>版本语义与 Release Notes</b></summary>

| 变更类型 | 版本号 |
|---|---|
| 行为合同语义改动（CLAUDE.md 路由/安全边界） | major |
| 权威入口增减、agent 定义改结构 | minor |
| bug 修复、文案措辞、知识库增量 | patch |

**v1.5.0**（2026-06-03）— Harness 四层架构落地（执行/沉淀/反馈/维护）；CLAUDE.md 重写为 19 条纯行为铁律；新建 rules/（4 层规格 + 接入索引）；work SKILL 抽薄；RULE_ENFORCEMENT_MATRIX 加 R1-R19 索引。

**v1.4.0**（2026-06-02）— Tier 2 强证据门：test-quality review 必需 Red-Evidence + Mutation 两节，防 AI 写全绿假测试。

**v1.3.x**（2026-06-02）— 跨任务经验召回层（task_experience_index + LLM triage）；work skill 统一 v2；vendor learning-opportunities skill。

**v1.2.0**（2026-05-17）— `/work` 流程升级（DESIGN.md 替代 SPEC.md）；多 Agent sync 基础设施；check 双向兼容。

**v1.1.0**（2026-05-16）— Stop hook git sync 错误处理降级为 warning；statusline 精简。

**v1.0.0**（2026-05-15）— 四层架构基线；单仓合并完成；bootstrap.py 部署/校验。

</details>

## License

[MIT](LICENSE) — 允许自由使用、修改、分发。选型记录见 [docs/license-decision.md](docs/license-decision.md)。
