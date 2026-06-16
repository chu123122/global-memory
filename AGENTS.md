# Global Memory Agent 入口

## 仓库定位

这是 **Claude Code harness + global memory 治理系统**：维护跨设备同步的记忆、Agent、Skill、Hook、harness 脚本与治理文档。它不是通用 memory SDK，也不是已经完成的多客户端闭环引擎；客户端能力边界以 `README.md`、`harness/client_manifest.json` 和对应检查脚本为准。

根 `AGENTS.md` 只做仓库门厅：告诉 agent 先读什么、任务去哪、哪些边界不能碰、交付前怎么验。具体规则继续回到各自 source of truth。

## 先读顺序

1. `README.md`：仓库定位、能力边界、日常命令、运行入口和目录地图。
2. `agents/CLAUDE.md`：跨项目常驻行为合同；除非任务明确要求，不改其语义。
3. `rules/接入索引.md`：规则体系和非 skill 入口；按任务再加载对应层规格。
4. `docs/spec/QUALITY_GATE.md`：AI 代码质量门、风险分级和 review 文件格式。
5. `docs/guide/CONTRIBUTING.md`：新增或修改 Hook / Skill / Script / Agent 的接入规则。
6. 相关地图和 registry：改 hook/main loop 前读 `docs/主循环与日志地图.md`、`docs/hook-chain.md`；改工具前读 `docs/工具组件总览.md`、`docs/scripts-registry.md`；改能力或客户端边界前读对应 manifest。

## 任务路由

| 任务类型 | 先看哪里 | 注意 |
|---|---|---|
| 架构理解、仓库边界 | `README.md`、`rules/接入索引.md` | 根入口不复述深层模型，只导航。 |
| 正式任务执行、任务文档续跑 | `/work` 流程、任务目录、`project_registry.json` | 先读 HANDOFF / Phase / test，再按验收推进。 |
| 记忆写入规则 | `rules/沉淀层.md`、`docs/spec/MEMORY-RULES.md` | 记忆库是数据层；不要把临时任务记录写成长期规范。 |
| Hook、主循环、日志链路 | `docs/主循环与日志地图.md`、`docs/hook-chain.md`、`hook_manifest.json` | 改前确认注册、运行时渲染和日志位置。 |
| harness 脚本、工具、registry | `docs/工具组件总览.md`、`docs/scripts-registry.md`、`docs/guide/CONTRIBUTING.md`、相关 manifest | 新脚本必须接入 registry / manifest / 检查链路，不能孤立落地。 |
| 发布、外部接入、能力评估 | `README.md`、`docs/capabilities.md`、`docs/capability-map-and-oss-gap.md`、release-check 系列命令 | 不夸大客户端能力；以机器检查结果为准。 |
| Codex 质量门 | `docs/spec/QUALITY_GATE.md`、`quality_gate.yaml` | 本轮改动最终用 `quality_gate.py verify` 验证，dirty 仓库限定路径。 |

## 改动前置门（Change Packet · 仅本仓库维护）

> 这是本仓库（`~/.claude/global-memory`）维护时的附加接入层，叠加在全局行为合同（`agents/CLAUDE.md`）和默认 `/work` 流程之上。不替代、不修改全局规则，也不要求其他项目采纳。

维护本仓库时，非纯格式/注释/行尾空格的改动，在实现前产出一份 Change Packet：

```powershell
python harness\scripts\change_packet.py new --title "<改动标题>" --task <task-id> [--risk-tier N]
```

填写动机（WHY）、范围（WHAT）、方案（HOW）、验证证据、风险与回滚、意图对齐后，校验：

```powershell
python harness\scripts\change_packet.py validate quality\change-packets\<packet>.md --json
```

规则：
- 模板：`templates/change_packet.md.tmpl`。存储：`quality/change-packets/`。
- `status: draft` 允许空白字段；`submitted` 及以上必须所有必填字段非空。
- Scope 包含 `agents/CLAUDE.md` 时，必须附 justification 说明为何不能只用本文件解决。
- Change Packet 是实现前 intent/scope gate；`quality_gate.py` 是实现后 correctness/test gate。
- 此门仅在 CWD 为本仓库且进行维护改动时生效；日常项目、其他 repo 不受影响。

## 硬边界

- 不改 `agents/CLAUDE.md` 的行为语义，除非任务明确点名。
- 不把 `rules/接入索引.md` 或层规格的大段内容搬进根入口。
- 不新增孤儿脚本、孤儿文档或未注册能力；新增组件必须同步 registry / manifest / 文档入口。
- 不宣称尚未由 manifest 和检查脚本支持的客户端能力。
- `README.md` 是人类向导览，不当作执行协议；执行细节回到 rules / docs / scripts。
- 不碰 memory 数据、hooks、bootstrap、sync 链路，除非任务明确纳入范围。
- XDMaker 只作为“第一屏可行动入口”的参考；不要复制其产品、桌面、UI、进程或工程命令规则。

## 改动原则

- 改前先读调用方、导出点、manifest、registry 和现有测试。
- 只做任务要求范围内的局部改动；不顺手重构无关命名、格式或结构。
- 脚本和检查保持确定性：路由、重试、解析、格式化、门禁优先用代码表达。
- 文档、registry、manifest、测试证据要和实现一起更新。
- 长期 dirty 仓库中运行质量门时，必须用 `--path` 限定本轮实际修改范围。

## 交付前质量门

本仓库的代码改动默认受 AI 代码质量门约束。

修改代码后，在最终回复前运行：

```powershell
python harness\scripts\quality_gate.py verify --json
```

长期 dirty 仓库中，必须用 `--path` 限定本轮实际修改范围，避免把历史未提交变更混入质量门：

```powershell
python harness\scripts\quality_gate.py verify --path harness\scripts\quality_gate.py --path harness\tests\test_quality_gate.py --json
```

如果需要强制阻断语义，运行：

```powershell
python harness\scripts\quality_gate.py verify --enforce --json
```

规则入口：`docs/spec/QUALITY_GATE.md`。项目配置：`quality_gate.yaml`。

执行原则：

- Tier 0/1 可以只记录验证说明。
- Tier 2 必须有测试证据和 `correctness` / `test-quality` 两个审查结果。
- Tier 3 必须有四视角审查、人工裁决、回滚或恢复说明。
- AI review 不能替代确定性检查。
- Review 结果必须放在 `quality/reviews/<kind>.md` 或用 `--review-dir` 指定；文件需要合法 `Verdict`、`Confidence` 和固定 section，不能只保存 review prompt。
