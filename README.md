# Global Memory

> 自举的个人 AI 工作系统：Claude Code harness + 记忆治理。一套模型，两条正交轴。

这是一个 **Claude Code harness + global memory 治理系统** —— 不是通用 memory engine / SDK。它把「AI 行为铁律、技能流程、确定性门禁、记忆沉淀与召回」装进同一个 Git 单仓库，通过 junction/符号链接部署到 Claude Code 运行时，让 AI 的工作方式被显式治理、可审计、可同步。

- **规模**：~74K 行 Python（315 文件）、759 个测试、294 commits / 4 个月持续演进
- **边界诚实**：Claude Code 全生命周期 stable；generic CLI 只保证 read-only Context Brief；Codex CLI experimental/manual
- **数据/代码分离**：数据产物（semantic index、catalog、HTML）全部 gitignore，代码资产与个人数据彻底分开

---

## 核心亮点

### 双轴正交架构

反对「L1→L4 线性 5 层链」的 category error，改为两条正交轴：

```
运转轴 HOW（每步怎么钉死）          设计轴 WHAT（数据怎么流）
───────────────────────            ───────────────────────
Rules   行为合同「做什么/不做什么」    执行(判断) → 沉淀 → 反馈
Skills  流程固化「怎么做/按什么顺序」    (推到验收)  (入库)  (召回注入)
Script  确定性变换+硬门禁「做没做到」       └────── 闭环 ──────┘
   旁挂 harness：强制执行 + 自动触发 + 隔离
```

### 本地语义 RAG（不套壳）

全本地、只读、可审计的检索链路：`corpus 分块 → bge-m3 嵌入（仅 loopback Ollama）→ SQLite 索引 → RRF 融合排序 → reranker`。

- **明确拒绝** Chroma/Qdrant/LlamaIndex/LangChain —— 技术自主
- **可量化**：Qwen reranker 在扩展集 100 例上把 Recall@5 **0.49→0.72**、MRR **0.36→0.55**、负样本 FPR **0.08→0.04**；golden Recall@10=1.0；13/13 负控阻断
- **诚实 fallback**：reranker 超时/异常回退原序，绝不谎报成功；rewrite 实验因超时过高（122/150）**主动暂停**

### 治理即代码（20+ hooks）

Claude Code 生命周期全覆盖：`UserPromptSubmit / PreToolUse / PostToolUse / Stop` 四个事件上挂了 20 个 hook，做**拦截（危险命令、越权路径）、审计（工具调用日志）、注入（Context Brief / 策略事实）、体检（9 项健康信号）**。

### 确定性信任模型（work_runner）

`/work` 工作流的 worker/verifier 门禁循环，核心原则：**runner 拥有状态，verifier 拥有 pass/fail，worker 输出不可信**。内置失败码审计（FORBIDDEN_SCOPE_TOUCHED / FAKE_WORKER_REPORTED_FAIL / VERIFIER_TIMEOUT / REPAIR_LIMIT_REACHED），有界 repair 循环，防 AI 谎报。

### 能力边界机器可读

`capability_manifest.json` 强制 209 个 harness 脚本全部分配到 **18 个能力域 × 5 种状态**（core/optional/experimental/legacy/deprecated），并有 OSS 就绪双 profile（`oss` / `private-audit`）聚合检查。

---

## 架构

### 目录结构（展示范围）

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
│   ├── verify/  health/  #   验证器 + 健康检查
│   └── tests/            #   759 个测试
├── docs/                 # 分类文档（spec/guide/reference + 能力地图）
├── templates/            # 工程文档模板
└── .github/workflows/    # OSS 就绪 CI
```

### 运行时部署

`bootstrap.py install` 把 `agents/ skills/ harness/` 通过 Windows junction 挂到 `~/.claude/`，并把 hooks/statusLine 渲染进 `~/.claude/settings.json`。数据产物（semantic index / catalog / HTML 预览）全部 gitignore，不污染版本库。

### 自动同步

| 链路 | 入口 | 行为 |
|---|---|---|
| 对话结束 | Stop hook → `post_task_hook.py` | 检查索引/CHANGELOG，stale 时刷新 semantic 派生索引 |
| 手动 Git 同步 | `maintain.py sync --preview` → `--source manual` | 先预览 checkpoint，再确认提交推送 |
| GUI 主控台 | `control_panel.bat` | 状态查看、同步预览、doctor、修复 |

---

## 功能特性

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

---

## 快速开始

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

### 文档

| 文档 | 内容 |
|---|---|
| [快速开始](docs/getting-started.md) | 最小安装、验证、接入路径 |
| [能力说明](docs/capabilities.md) | 18 个能力域的外部用户说明 |
| [能力与 OSS 缺口](docs/capability-map-and-oss-gap.md) | 当前能力整理和开源倒逼剩余缺口 |
| [贡献指南](docs/guide/CONTRIBUTING.md) | 新 Hook / Skill / Script / Agent 接入规则 |
| [发布范围](docs/publish-scope.md) | 外部发布范围和个人数据边界 |
| [维护手册](docs/guide/MAINTENANCE.md) | 日常维护、同步、体检 |
| [License 决策](docs/license-decision.md) | 许可证选型记录 |

---

## 技术栈

| 维度 | 内容 |
|---|---|
| 语言 | Python 3.12 |
| 运行时依赖 | `mcp` + `PyYAML`（numpy 可选） |
| 语义检索 | Ollama `bge-m3`（1024 维）+ Qwen3-Reranker-0.6B，SQLite 索引 |
| MCP | pull-mode stdio 工具 + loopback HTTP warm sidecar（p50≤1s） |
| 测试 | pytest 8（759 个测试 / 80 文件） |
| 规模 | 315 .py / 74K 行 / 426 tracked 文件 |

---

## 版本语义

| 变更类型 | 版本号 |
|---|---|
| 行为合同语义改动（CLAUDE.md 路由/安全边界） | major |
| 权威入口增减、agent 定义改结构 | minor |
| bug 修复、文案措辞、知识库增量 | patch |

## Release Notes

### v1.5.0（2026-06-03）
Harness 四层架构落地（执行/沉淀/反馈/维护）；CLAUDE.md 重写为 19 条纯行为铁律；新建 rules/（4 层规格 + 接入索引）；work SKILL 抽薄；RULE_ENFORCEMENT_MATRIX 加 R1-R19 索引。

### v1.4.0（2026-06-02）
Tier 2 强证据门：test-quality review 必需 Red-Evidence + Mutation 两节，防 AI 写全绿假测试。

### v1.3.x（2026-06-02）
跨任务经验召回层（task_experience_index + LLM triage）；work skill 统一 v2；vendor learning-opportunities skill。

### v1.2.0（2026-05-17）
/work 流程升级（DESIGN.md 替代 SPEC.md）；多 Agent sync 基础设施；check 双向兼容。

### v1.1.0（2026-05-16）
Stop hook git sync 错误处理降级为 warning；statusline 精简。

### v1.0.0（2026-05-15）
四层架构基线；单仓合并完成；bootstrap.py 部署/校验。

---

## License

[MIT](LICENSE) — 允许自由使用、修改、分发。LICENSE 决策记录见 [docs/license-decision.md](docs/license-decision.md)。
