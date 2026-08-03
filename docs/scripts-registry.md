---
doc_type: registry
status: active
last_updated: 2026-05-25
trigger:
  keywords: [concept:registry, tool:harness, concept:script]
  tags: [workflow, tooling]
---

# Scripts Registry

> harness/ 下全部 .py 脚本一览表。新加脚本必须更新此表。
>
> 触发方分类：
> - **Hook** = settings.json 注册（PreToolUse / PostToolUse / Stop / UserPromptSubmit / statusLine）
> - **Gate** = `gate_check.py` G1-G8 内部调用
> - **Smoke** = `verify/smoke_test.py` 或其他 verify/ 调用
> - **Manual** = 手动 CLI，无自动触发
> - **CronOrDaemon** = 后台进程 / 定时任务
> - **Library** = 不可独立执行，被 import
> - **ORPHAN** = ⚠ 无任何已知调用方
> - **DEPRECATED** = 已知废弃/保留兼容，不进入默认 runtime/release
>
> 失败动作：
> - **BLOCK** = 阻断当前操作
> - **WARN** = 仅日志/打印，不阻断
> - **REPORT** = 写报告文件
> - **NONE** = 静默

Hook 链的机器可读 source of truth 是 `harness/hook_manifest.json`；`bootstrap.py install` 从该 manifest 渲染 `~/.claude/settings.json`。

能力边界的机器可读 source of truth 是 `harness/capability_manifest.json`；`check_capability_manifest.py` 校验 core/optional/experimental/legacy/deprecated 状态、脚本路径，以及每个 harness 脚本是否已归属某个能力域。

能力边界的人类可读入口是 `docs/capabilities.md`；每个能力节用 `capability:<id>` 绑定 manifest，缺失会被 `check_capability_manifest.py` 报错。

客户端支持边界的机器可读 source of truth 是 `harness/client_manifest.json`；`check_client_manifest.py` 会明确当前是 Claude Code harness、Context Brief CLI 契约，还是通用多客户端项目，并校验 README / getting-started / capabilities 这些外部入口没有越界宣称。

---

## 1. Hooks（settings.json 注册）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `hooks/dangerous_command_blocker.py` | 拦截 rm -rf / dd 等危险 Bash | PreToolUse:Bash | BLOCK |
| `hooks/memory_file_protector.py` | 防误删 global-memory 文件 | PreToolUse:Write\|Edit\|MultiEdit | BLOCK |
| `hooks/memory_lint_gate.py` | 写记忆文件时校验 frontmatter | PreToolUse:Write\|Edit\|MultiEdit | BLOCK |
| `hooks/doc_gate.py` | 任务目录写文件时检查必读 | PreToolUse:Write\|Edit\|MultiEdit | BLOCK |
| `hooks/diff_backup.py` | 写文件前备份原版到 diff_runs/ | PreToolUse:Write\|Edit | NONE |
| `hooks/read_large_file_guard.py` | 拦超大文件 Read | PreToolUse:Read | BLOCK |
| `hooks/agent_prompt_gate.py` | Subagent prompt 质量检查 5/3 | PreToolUse:Agent | BLOCK |
| `hooks/audit_logger.py` | 全工具调用记日志 | PostToolUse:* | NONE |
| `hooks/learning_opportunity_nudge.py` | Bash 后注入学习机会提示 | PostToolUse:Bash | NONE |
| `hooks/changelog_inject.py` | 用户提交时注入 CHANGELOG hint | UserPromptSubmit (1/4) | NONE |
| `hooks/route_check.py` | 路由 nudge | UserPromptSubmit (3/4) | NONE |
| `hooks/retrieve_inject.py` | 当前 hook/MCP/RAG 状态类问题调用 `runtime_brief.py` 生成 deterministic Runtime Config Brief；其他问题注入 Policy/RAG Brief（召回指针）；默认只请求 warm `gm.search` sidecar，连续失败后短期 cooldown，sidecar 不可用时静默不注入；`HARNESS_RAG_HOOK_ALLOW_COLD_FALLBACK=1` 仅作临时诊断 | UserPromptSubmit (3/3) | NONE |
| `hooks/statusline.py` | 终端 statusline 渲染 | statusLine | NONE |
| `hooks/route_gate.py` | 旧版路由计划阻断 hook；已被 `route_check.py` / route-system-v2 取代 | DEPRECATED | WARN |

### Hook 私有 library（被 import，不独立跑）

`_hook_lib.py` / `_prompt_loader.py` / `_task_resolver.py` / `policy_fact.py` / `runtime_brief.py` — Library

---

## 2. Gate 调用脚本（gate_check.py G1-G8）

| 脚本 | 用途 | Gate ID | 失败动作 |
|---|---|---|---|
| `scripts/scan_dual_storage.py` | 检查 active/archived task 与 `projects/` 的双写记忆；默认保留 `dual_count=` 文本给 G1，`--json` 输出 `dual_storage_scan` 并进入 output-contract / governance pulse | G1 / governance_pulse | REPORT |
| `scripts/harness_retrieve.py` | retrieve 引擎主入口（也是 hook 调用源） | G3 | REPORT |
| `scripts/check_trigger_coverage.py` | trigger 字段覆盖率 ≥ 90% | G4 | REPORT |
| `scripts/test_context_governance.py` | pytest 全套 | G7 | REPORT |
| `fix_hardcoded_paths.py` | 硬编码路径检测 | G9（WARN） | WARN |

注：G2 调 `git tag`，G5 直接 stat 文件，G6 读 settings.json，G8 占位 n/a。

---

## 3. Manual 治理脚本（无自动触发）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `scripts/change_packet.py` | Change Packet 前置门：`new` 建包 / `validate` 校验 / `status` 列表 | Manual | REPORT |
| `scripts/harness_memory_lint.py` | 单文件/批量记忆 lint | Manual + Hook(import) | REPORT |
| `scripts/client_context.py` | 通用 CLI 客户端 Context Brief 契约（默认只读不写日志）| Manual / Generic client | REPORT |
| `scripts/add_trigger_metadata.py` | 给记忆批量加 trigger | Manual | REPORT |
| `scripts/analyze_retrieve_log.py` | 7 天 retrieve 日志分析；`--json` 输出 retrieve hit/zero-hit/namespace/miss-sample 聚合并进入 output-contract | Manual | REPORT |
| `scripts/migrate_retrieve_logs.py` | 将 legacy Claude retrieve_calls.jsonl 迁移到 shared runtime retrieve log | Manual | REPORT |
| `scripts/retrieve_threshold_report.py` | 只读分析 shared `retrieve_calls.jsonl` 的 hook 阈值行为：注入率、abstain 分布、pre-rerank 拦截、reranker 边界样本、人工标注 useful/noise/unclear 汇总；只给观察建议，不自动改阈值 | Manual | REPORT |
| `scripts/context_meter.py` | 记忆/上下文体积统计 | Manual | REPORT |
| `scripts/gate_check.py` | 跑 G1-G9，`--json` 只读输出 verdict；默认兼容写 GATE-REPORT | Manual / Release profile | REPORT |
| `scripts/check_publish_scope.py` | 对账 `harness/publish_scope_manifest.json` 和 `git ls-files -z`，阻断已跟踪的个人/私有发布路径 | Manual / Release profile | REPORT |
| `scripts/export_source_scope.py` | 基于发布范围 manifest 生成只读 clean source 导出计划，列出 included / excluded-private / untracked-external，并给出不修改 index 的 tracking_plan | Manual / Release profile | REPORT |
| `scripts/scan_external_safety.py` | 扫描 clean source 计划内文件的明显密钥和本机绝对路径，密钥阻断、本机路径预警；public_history-only warning 会输出 policy_plan | Manual / Release profile | REPORT |
| `scripts/release_issue_ledger.py` | 将 OSS readiness 当前结果转成 open/resolved/deferred issue ledger，并按 owner/code/docs/publish-scope 缺口分类；输出顶层 `remaining_gap_table` 作为当前剩余缺口表；`--gap-table-only` 输出人类可读缺口表，并直接列出 owner 决策的 allowed options、dry-run/write 命令、`publish_scope` 的 private path group/reason 摘要，以及 `client_portability` 的 full-lifecycle required/missing capability 摘要；`--owner-decisions-only` 输出未决 owner 队列，合并/校验 `harness/release_owner_decisions.json` 的记录状态和 stale 记录，并在人类文本中列出 required follow-up、dry-run 和 write 命令；`--strict` 会按当前选择的视图返回非零：完整/缺口表视图看 open blocker，owner-only 视图只看 owner 决策 readiness 和记录合法性；默认跳过递归 output-contract 检查 | Manual / Release profile | REPORT |
| `scripts/scan_orphan_scripts.py` | 对账 `harness/` 下实际 Python 脚本和 `docs/scripts-registry.md`；`UNREGISTERED` 表示新增脚本未登记，`STALE` 表示 registry 仍列出已不存在脚本，`--strict --json` 是 release profile 的能力注册检查 | Manual / 控制面板 / Release profile | REPORT |
| `scripts/reconcile.py` | 多数据源统一治理：M1 扫 `RECONCILE` 标记从 source(如 hook_manifest.json)渲染 doc 块(`--fix`)；M2 委托 scan_orphan；M3 校验 rules/ 跨层引用指针存在；meta-check 启发式报疑似未标记镜像(advisory)。`--check` 报漂移/断链退 2。设计见 `docs/多数据源治理方案.md` | Manual / 控制面板 | REPORT |
| `scripts/render_codex_work_skill.py` | 从单一来源 `skills/work/SKILL.md` + `codex-adapter.md` 生成 `~/.codex/skills/codex-work/SKILL.md`；`--check` 用于漂移检查，避免 Claude/Codex 两套 work skill 手写分叉 | bootstrap install / Manual / Codex | REPORT |
| `scripts/quality_gate.py` | AI 代码质量门；按 git diff/风险路径/规模分 Tier，输出 plan/verify verdict，并生成四视角 review prompt | Manual / Codex / Claude Code hook candidate / Git hook candidate | REPORT / optional BLOCK |
| `hooks/quality_gate_stop.py` | AI 代码质量门 Stop hook 适配器；默认 warn-only，`HARNESS_QUALITY_GATE_ENFORCE=1` 时 BLOCK 可阻断；候选脚本，默认未注册到 hook_manifest/runtime | Manual candidate | WARN / optional BLOCK |
| `scripts/triage_inbox.py` | `/triage` skill 的只读 inbox 扫描与 close verify 机械门：汇总 open issue/active feedback；`--verify-close` 校验来源状态已关闭且证据落盘；不写 ledger、不自动关闭 | Manual | REPORT |
| `scripts/check_capability_manifest.py` | 校验 capability_manifest 的能力状态、release_scope、脚本路径和全脚本能力归属 | Manual / 控制面板 / Release profile | REPORT |
| `scripts/check_client_manifest.py` | 校验 client_manifest 的客户端支持范围、稳定客户端数量、入口路径、外部 claim policy，以及 full-lifecycle/context-brief 客户端能力矩阵 | Manual / Release profile | REPORT |
| `scripts/check_hook_alignment.py` | 校验 hook_manifest schema/path，并对账 bootstrap、运行 settings 和 registry 的 hook 漂移 | Manual / 控制面板 | REPORT |
| `scripts/oss_readiness_check.py` | 开源倒逼检查聚合器；主入口为 `maintain.py release-check --profile oss`，私有成熟度审计入口为 `maintain.py release-check --profile private-audit`；同时检查外部文档入口、maintenance manifest、自动组件目录 freshness、OSS workflow YAML/steps 是否有效，并覆盖输出契约、release checkpoint、gap table、owner queue、最终 release-check | Manual / 控制面板 | REPORT |
| `scripts/update_phase_status.py` | 一键三同步 Phase 状态（卡 frontmatter + 设计文档表行 + 验收清单）| Manual | NONE |
| `scripts/work_runner.py` | work-runner CLI；支持 verifier-only `check`、fake/codex-exec 单次 `run`、以及最多 3 次的 codex-exec `repair` 返修闭环，gate fail/infra fail 作为 JSON 数据返回 | Manual / Work runner | REPORT |
| `scripts/archive_task.py` | 任务归档三模式（--check Phase 状态 / --extract 抽 fixes/knowledge 候选 + 复盘 5 护栏 lint / --commit 物理归档，需 --yes）| Manual | REPORT |
| `governance_pulse.py` | 周期治理巡检 daemon（gate/orphan/dual_storage → governance_pulse.jsonl）| Manual / pythonw 后台 / cron | REPORT |
| `fix_hardcoded_paths.py` | 硬编码扫描（接入 G9 WARN）| Gate G9 + Manual | WARN |
| `note.py` | 速记本 | Manual | NONE |
| `scripts/register_script.py` | 新增 harness 脚本双登记工具；默认 dry-run，--apply 写回 registry 与 capability manifest | Manual | REPORT |
| `readback_audit.py` | 任务文档回读率审计：基于 tool_audit 统计 HANDOFF/STATUS/design 等任务文档是否被读回 | Manual | REPORT |
| `scripts/check_phase_evidence.py` | 检查 Phase 卡 status: done 时验收契约表 Green 与证据指针是否完整 | Manual | REPORT |
| `scripts/task_experience_index.py` | 维护跨任务经验索引候选、diff、prune/build，用于经验沉淀 triage 的确定性部分 | Manual | REPORT |

---

## 4. Self-loop / Retrieve evidence（实验与诊断）

> 这组脚本围绕 `.meta/` 证据链工作：proposal → simulation/evaluation → trial → candidate → optimization ledger → self-loop overview。默认只读；任何启用 fallback 或写 review artifact 的动作都必须显式 opt-in。

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `scripts/meta_optimize.py` | 从 health/retrieve/sync/task 信号生成只读优化建议；`--json` 输出 read-only finding ledger 和单一推荐动作，已进入输出契约 | maintain.py report / Manual | REPORT |
| `scripts/self_loop_report.py` | 汇总当前自循环状态、fallback 成本、候选和 assurance；`--json` 输出 `self-loop-overview`，已进入输出契约 | Manual | REPORT |
| `scripts/retrieve_zero_hit_analysis.py` | 分析 human query zero-hit 和短 follow-up zero-hit | Manual / meta_optimize | REPORT |
| `scripts/retrieve_downrank_simulation.py` | 模拟 retrieve downrank 参数对首屏 pointer 的影响 | Manual / meta_optimize | REPORT |
| `scripts/retrieve_fallback_candidates.py` | 从日志中发现 task-context fallback 候选并给 ACCEPT/REVIEW/REJECT | Manual / self_loop_report | REPORT |
| `scripts/retrieve_fallback_cost.py` | 汇总 fallback 触发次数、注入成本和命中数 | Manual / self_loop_report | REPORT |
| `scripts/retrieve_candidate_quality.py` | 只读关联 shared `retrieve_calls.jsonl` 与 `tool_audit.jsonl`，统计 `top_refs`/`top_candidate_paths`/legacy `all_hits` 召回指针后续是否被 Read 消费，并输出未消费 top paths / downrank 候选；不自动调阈值 | Manual | REPORT |
| `scripts/retrieve_trace.py` | 解释 retrieve scoring、downrank 和 task-context fallback 过程 | Manual | REPORT |
| `scripts/assurance_gate.py` | 给任务完成/交接状态生成机器可读 verdict | Manual / self_loop_report | REPORT |

---

## 5. Health 体检（harness/health/）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `health/runner.py` | 体检主入口（聚合 checks/*） | Manual / 控制面板 | REPORT |
| `health/registry.py` | check 注册表 | Library | — |
| `health/checks/changelog_drift.py` | 检测 CHANGELOG 漂移 | health/runner | REPORT |
| `health/checks/ghost_refs.py` | 死链 refs | health/runner | REPORT |
| `health/checks/invocation_freq.py` | 工具调用频率 | health/runner | REPORT |
| `health/checks/knowledge_unread.py` | 长期未读的 knowledge | health/runner | REPORT |
| `health/checks/log_liveness.py` | 日志活跃度 | health/runner | REPORT |
| `health/checks/memory_usage.py` | 记忆占用 | health/runner | REPORT |
| `health/checks/lint_failure_rate.py` | 近 7 天 memory lint 失败率 | health/runner | REPORT |
| `health/checks/retrieve_pointer_consumption.py` | retrieve pointer 真实消费率 | health/runner | REPORT |
| `health/checks/retrieve_hitrate.py` | retrieve 命中率 | health/runner | REPORT |
| `health/checks/sync_failures.py` | 同步失败统计 | health/runner | REPORT |
| `health/checks/traffic_imbalance.py` | 流量不均 | health/runner | REPORT |
| `health/checks/wip_age.py` | WIP 任务年龄 | health/runner | REPORT |

---

## 6. Reporting / 报表（harness/reporting/）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `reporting/harness_status.py` | harness 总体状态；`--tasks --json` 输出 `kind=harness_tasks`、summary、active/archived rows 和 stage 聚合 | 控制面板 / Manual | REPORT |
| `reporting/issue_tracker.py` | issue 跟踪 | 控制面板 | REPORT |
| `reporting/log_health.py` | 日志健康 | 控制面板 | REPORT |
| `reporting/outcomes_reader.py` | 任务结果读取 | 控制面板 | NONE |
| `reporting/overview_verdict.py` | 总体裁决 | 控制面板 | NONE |
| `reporting/session_report.py` | 会话报告 | 控制面板 / Manual | REPORT |
| `reporting/timeline_summary.py` | 时间线 | 控制面板 | NONE |

---

## 7. 控制面板 GUI（harness/control_panel_pyside/）

> Qt/PySide UI 模块树。仅 `control_panel_pyside_launch.py` 是入口；其余全部 Library。

| 脚本 | 用途 | 触发方 |
|---|---|---|
| `control_panel_pyside_launch.py` | 启动 Qt 面板 | Manual / control_panel_pyside.bat |
| `panel_api.py` | 面板后端 API | Library（被 GUI 调用）|
| `smoke_control_panel_exe.py` | 面板冒烟测试 | Manual / Smoke |
| `control_panel_pyside/__main__.py` | python -m 入口 | Library |
| `control_panel_pyside/cli_invoke.py` | CLI 调用封装 | Library |
| `control_panel_pyside/main_window.py` | 主窗口 | Library |
| `control_panel_pyside/polling.py` | 轮询调度 | Library |
| `control_panel_pyside/theme.py` | 主题 | Library |
| `control_panel_pyside/views/_base.py` | 视图基类 | Library |
| `control_panel_pyside/views/changelog.py` | CHANGELOG 视图 | Library |
| `control_panel_pyside/views/components.py` | 组件视图 | Library |
| `control_panel_pyside/views/diagnostics.py` | 诊断视图 | Library |
| `control_panel_pyside/views/health.py` | 体检视图 | Library |
| `control_panel_pyside/views/issue_loop.py` | issue loop 视图 | Library |
| `control_panel_pyside/views/status.py` | 状态视图 | Library |
| `control_panel_pyside/views/tasks.py` | 任务视图 | Library |
| `control_panel_pyside/widgets/debug_dock.py` | debug dock | Library |
| `control_panel_pyside/widgets/doc_sidebar.py` | 文档侧栏 | Library |

---

## 8. Verify / Smoke（harness/verify/）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `verify/verify_all.py` | 全量 verify；包含 Codex work skill 单源生成漂移检查 | Manual / task_complete | REPORT |
| `verify/smoke_test.py` | 烟雾测试 | Manual | REPORT |
| `verify/smoke_test_hooks.py` | hooks 烟雾测试 | Manual | REPORT |
| `verify/verify_conventions.py` | conventions 一致性 | Manual | REPORT |
| `verify/verify_doc_drift.py` | doc 漂移 | Manual | REPORT |
| `verify/verify_docs.py` | doc 完整性 | Manual | REPORT |
| `verify/verify_memory.py` | 记忆 verify | Manual | REPORT |
| `verify/verify_output_contracts.py` | 输出契约；额外保护 `gate_check.py` 的 G1-G9/summary/failures/verdict 一致性、`check_hook_alignment.py` 的 manifest/bootstrap/runtime/registry 计数与 drift verdict、`scan_dual_storage.py --json` 的 `dual_storage_scan` 计数/重复行一致性、`scan_orphan_scripts.py` 的 registry-drift JSON、capability/client manifest 的边界计数关系和客户端 full-lifecycle/context-brief 能力矩阵、`check_publish_scope.py` 的 tracked/external/private/unclassified 计数、分组汇总、scope、verdict 和 `decision_plan.required_when` 一致性、`export_source_scope.py` 的 source-export 计数、untracked 分组、tracking command/safety 和 verdict 一致性、`scan_external_safety.py` 的 summary/verdict/by_code/top_paths/remediation_groups/policy_plan 聚合一致性、`smoke_test.py` 的 summary/result/status/skip/zero-fail 一致性、`client_context.py` 的 generic context-brief.v1 ok/error/brief/brief_text/pointer/load-strategy 一致性、`generate_catalog.py --check --json` 的自动目录 freshness 契约、`audit_skill.py --all --json` 的 skill summary/level/issue-code/deployed-extra 一致性、`analyze_retrieve_log.py --json` 的 total/zero-hit rate/hit distribution/top path/noisy keyword/namespace/miss-sample 聚合一致性、`work_context_pack.py --json` 的 read-only `work_context` 摘要契约和 `--intent` 的 `intent_guard` 结构契约、`check_prepare.py --json` 的任务解析/review_docs/doc_scans/warnings/prompt_inputs 一致性、`harness_status.py --tasks --json` 的 active/archived/stage/missing/unknown 计数一致性、`self_loop_report.py --json` 的 self-loop summary/candidate/ledger 计数一致性、`meta_optimize.py --json` 的 finding ledger/user-visible decision 一致性、`maintain release-checkpoint` 普通/strict JSON 契约，`oss_readiness_check` / `maintain release-check` 的 docs entrypoint、maintenance manifest、catalog freshness 和 owner `decision_plan` 覆盖，release issue ledger 的 `gap` 字段、`owner_decisions`、`remaining_gap_table`、`client_lifecycle_gaps`、`publish_scope_breakdown`、owner 记录合法性和 open gap 汇总一致性，并默认实跑 `license_policy` / `publish_scope_boundary` 两条 `release-record-decision --dry-run` 记录入口 | Manual | REPORT |
| `verify/verify_prompt_system.py` | prompt 系统 | Manual | REPORT |

---

## Pull-mode memory MCP tools（experimental）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `gm_mcp/sidecar.py` | 本地 loopback `gm.search` HTTP sidecar，常驻预热 embedding/index/reranker，供 `retrieve_inject.py` 轻量请求；`/health` 暴露 ready/degraded/reranker fallback 状态 | Manual / Hook sidecar | REPORT |
| `gm_mcp/server.py` | 本地 stdio MCP server，默认暴露 `gm.search` / `gm.locate` / `gm.symbol` / `gm.inspect` / `gm.map` / `gm.answer`；`gm.rule` 保留为强制门后端/CLI probe，需 `GM_MCP_EXPOSE_RULE_TOOL=1` 才作为可选 MCP tool 暴露；提供 self-test / bench / direct probes | Manual / MCP | REPORT |
| `gm_mcp/catalog.py` | 结构化 catalog + Python AST symbol index：为 `gm.locate` / `gm.symbol` / `gm.inspect` / `gm.map` 提供权威入口、对象摘要和精确行号；可写 `harness/data/gm_catalog.json` / `gm_symbols.json` | Library / Manual | REPORT |
| `gm_mcp/search.py` | `gm.search` 后端包装：复用 `harness.semantic` + intent bank，返回 pointer / intent match / low_confidence 标记 | Library | — |
| `gm_mcp/rules.py` | `gm.rule` 后端：加载规则登记表并做纯内存匹配，返回 anchored rule snippets | Library | — |
| `gm_mcp/logging.py` | gm.* tool-call JSONL 日志，记录 source/mode/latency/result 摘要 | Library | — |

## Collaboration orchestration（experimental）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `collab/config.py` | 协同插件五角色配置 schema、默认值填充和确定性校验 | Library | — |
| `collab/errors.py` | 协同插件稳定错误码、`error_code` 映射和 CLI JSON error contract helper | Library | — |
| `collab/plan.py` | 根据配置生成 host-neutral dispatch plan 和 worker prompt | Library | — |
| `collab/adapters.py` | Codex / Claude Code / Orca / manual adapter contract 与声明式 runtime-shaped payload，不负责拉起进程 | Library | — |
| `collab/state.py` | 协同 dispatch plan 的轻量 JSON 状态、worker/session/report 字段和状态迁移校验 | Library | — |
| `collab/replay.py` | 从 plan + state 生成下一步 dispatch runbook/action cards，连接 adapter payload 与 state update 命令 | Library | — |
| `collab/dispatch.py` | 从 replay runbook 选择单个 dispatch，生成 dry-run dispatch packet、runtime payload 和状态更新命令 | Library | — |
| `collab/queue.py` | Host-neutral 多 worker 队列模型，支持 lease/retry/requeue/concurrency/labels，不启动 worker | Library | — |
| `collab/recover.py` | 从 plan/state/queue 生成恢复建议，覆盖 stale running、mismatch、schema/version 问题 | Library | — |
| `collab/ui_shell.py` | 从 plan/state/queue/recover/dispatch/report artifacts 生成可选 UI shell view model 与 Markdown dashboard | Library | — |
| `scripts/collab_plan.py` | CLI：生成或校验协同 dispatch plan，支持 Markdown / JSON、adapter payload 和可选 state JSON 输出 | Manual | REPORT |
| `scripts/collab_state.py` | CLI：校验、查看或更新协同 state JSON 中单个 dispatch 的 status/worker/session/report | Manual | REPORT |
| `scripts/collab_replay.py` | CLI：读取协同 plan/state，输出待执行 action cards、runtime payload 和 state update 示例，不调用 worker | Manual | REPORT |
| `scripts/collab_dispatch.py` | CLI：选择下一条或指定 dispatch，输出单个 dry-run 派发包；不调用 worker | Manual | REPORT |
| `scripts/collab_queue.py` | CLI：创建/查看/lease/requeue/complete/fail 协同队列 JSON；只改 artifact，不启动 worker | Manual | REPORT |
| `scripts/collab_recover.py` | CLI：读取 plan/state/queue 并输出恢复报告和建议动作，不自动修复状态 | Manual | REPORT |
| `scripts/collab_ui_shell.py` | CLI：读取协同 artifacts 并输出 deterministic UI shell JSON/Markdown；只读、不启动 worker | Manual | REPORT |
| `collab/bridge.py` | Python：standalone collab bridge executable spec、MCP-style tool surface、capability matrix 与 deferred worker launch blueprint | Manual | REPORT |
| `collab/bridge_host.py` | Python：Phase 7 local bridge host fake/manual event session、worker focus/message/report view-model；不启动真实 worker | Manual | REPORT |
| `collab/bridge_store.py` | Python：Phase 8 event-sourced bridge store summary、atomic snapshot、replay validation 与 migration stub | Manual | REPORT |
| `collab/worker_runtime.py` | Python：Phase 9 operator-configured worker command runtime alpha；显式 allow-spawn 后才启动进程并捕获 report | Manual | REPORT |
| `collab/mcp_bridge.py` | Python：Phase 10 lead CLI MCP-style bridge schema/probe/call surface；不接管主 CLI agent loop | Manual | REPORT |
| `collab/router.py` | Python：Phase 11 event-sourced router/report loop，支持 correlation id、dedupe、ack、fail、retry | Manual | REPORT |
| `collab/entry.py` | Python：Phase 12/18 product entry/readiness gate，生成 runbook、smoke artifacts、not-ready 或 experimental_ready 报告 | Manual | REPORT |
| `collab/real_worker.py` | Python：Phase 13 真实 Codex/Claude worker command builder/probe/classifier，支持事件日志 ingestion | Manual | REPORT |
| `collab/worker_supervisor.py` | Python：Phase 14 bridge-owned worker supervisor，支持 start/send/read/status/stop/timeout/crash 与 replay snapshot | Manual | REPORT |
| `collab/mcp_server.py` | Python：Phase 15/19 real stdio MCP server，实现 initialize、tools/list、tools/call over collab bridge tools，并提供 read-only annotations/probe classifier | Manual | REPORT |
| `collab/web_ui.py` | Python：Phase 16/20 local operable web UI backend/static shell/API smoke，支持 worker list/create/focus/send/enqueue/fail/retry/report/reload | Manual | REPORT |
| `collab/persistence.py` | Python：Phase 17 SQLite persistence/recovery，支持 import/export/list/append/reopen/recover | Manual | REPORT |
| `scripts/collab_bridge.py` | CLI：输出 standalone collab bridge executable spec 与可审查的 worker launch blueprint；生成阶段不启动 worker | Manual | REPORT |
| `scripts/collab_bridge_host.py` | CLI：创建/查看/更新 Phase 7 local bridge host events JSONL，并输出 UI view-model；fake/manual only | Manual | REPORT |
| `scripts/collab_bridge_store.py` | CLI：汇总/快照/回放 Phase 8 bridge events store；不接真实 runtime | Manual | REPORT |
| `scripts/collab_worker_runtime.py` | CLI：构造非启动 runtime request，或在 `--allow-spawn` 下运行 operator command worker 并写回 bridge event log | Manual | REPORT |
| `scripts/collab_real_worker.py` | CLI：Phase 13 真实 Codex/Claude worker request/classify/probe；真实启动必须显式 `--allow-spawn` | Manual | REPORT |
| `scripts/collab_worker_supervisor.py` | CLI：Phase 14 worker supervisor scenario/snapshot，覆盖 start/status/send/read/stop/crash/timeout | Manual | REPORT |
| `scripts/collab_mcp_bridge.py` | CLI：输出 MCP-style schema/probe，或调用 create/send/status/read/report 工具并同步 events JSONL | Manual | REPORT |
| `scripts/collab_mcp_server.py` | CLI：Phase 15/19 real stdio MCP server serve/config/self-test/codex-probe-command/classify-codex-probe，不持久写 Codex/Claude 配置 | Manual | REPORT |
| `scripts/collab_router.py` | CLI：router snapshot/enqueue/ack/fail/retry/report 操作，所有状态写入 events JSONL | Manual | REPORT |
| `scripts/collab_web_ui.py` | CLI：Phase 16/20 local web UI serve/smoke，提供 worker list/timeline/create/send/enqueue/fail/retry/report/reload 操作界面 | Manual | REPORT |
| `scripts/collab_persistence.py` | CLI：Phase 17 SQLite persistence init/import/export/list/append/migrate/recover | Manual | REPORT |
| `scripts/collab_entry.py` | CLI：Phase 12/18 runbook/readiness/smoke/xdmaker-smoke 入口；不修改 hooks/bootstrap/client readiness | Manual | REPORT |

## Semantic retrieval backend（experimental）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `semantic/cli.py` | 语义索引 build/status/query/eval CLI；为 pull-mode gm.search 提供本地 index 管理入口 | Manual | REPORT |
| `semantic/engine.py` | 语义检索 Q2doc 引擎：FTS/metadata/vector 召回与 pointer ranking | Library | — |
| `semantic/embed.py` | loopback bge-m3/Ollama embedding client 与向量校验 | Library | — |
| `semantic/index.py` | SQLite/FTS5/vector index build/status/read helpers | Library | — |
| `semantic/query.py` | ranking、acceptance config、debug signals 数据结构与打分逻辑 | Library | — |
| `semantic/reranker.py` | 可选本地 reranker 抽象与后端：off / SentenceTransformers / Transformers yes-no scoring / experimental vLLM；失败时显式 fallback，不把 raw score 当 calibrated confidence | Library | — |
| `semantic/reranker_bench.py` | 只读 benchmark：测 SentenceTransformers / Transformers / vLLM reranker cold load、warm p50/p95、score 分布与 fallback 诊断 | Manual | REPORT |
| `semantic/sources.py` | semantic source 配置加载、路径同步与来源声明 | Library | — |
| `semantic/corpus.py` | memory corpus 扫描、chunking、authority tier 提取 | Library | — |
| `semantic/eval.py` | 语义检索 fixture eval runner | Manual | REPORT |
| `semantic/phase7_eval.py` | Phase 7 reranker preflight/threshold calibration 只读报告；有 reranker fallback 时标记 invalid | Manual | REPORT |
| `semantic/rewrite.py` | gm.search 可选 query rewrite 层；失败时返回原 query fallback plan，不回答用户问题 | Library | — |
| `semantic/rewrite_bakeoff.py` | 只读比较 query rewrite 模型在 golden/negative fixtures 上的 gm.search 表现；不拉模型不改阈值 | Manual | REPORT |
| `semantic/calibration.py` | eval policy calibration helper | Library | — |
| `semantic/errors.py` | semantic backend explicit error type | Library | — |
| `semantic/tokens.py` | 查询/内容 token 过滤 helper | Library | — |

---

## 9. 顶层工具 / 维护脚本（harness/*.py）

| 脚本 | 用途 | 触发方 | 失败动作 |
|---|---|---|---|
| `post_task_hook.py` | 任务收尾自动修；Stop hook 内同步执行 semantic check + 必要时 force sync，并写 `semantic_refresh_events.jsonl` | Stop hook + Manual | WARN |
| `task_complete.py` | 交付前合规检查 | Manual（CLAUDE.md 钦点） | REPORT |
| `create_task.py` | 创建/注册 v2 work task，写入 `D:\ClaudeTasks\active` 任务骨架和 registry/current_task | Manual / codex-work | NONE |
| `task_sync.py` | multi-agent 同步 CLI | Manual | NONE |
| `route_audit.py` | 路由审计 | Manual（CLAUDE.md 钦点） | REPORT |
| `maintain.py` | 维护总入口，含 `doctor`/`status`/`sync`/`semantic-sync`/`report`/`release-check`/`release-checkpoint`/`release-gaps`/`release-decisions`/`release-record-decision`；`release-check --profile oss` 是公开发布 gate，`release-check --profile private-audit` 是私有成熟度审计视图；`release-checkpoint` 是只读 OSS checkpoint 聚合入口；`release-record-decision` 是显式 owner 状态写入口，默认建议先 `--dry-run` | Manual / Manifest | REPORT |
| `auto_sync_daemon.py` | legacy Git auto-sync daemon；保留兼容，不再承担 semantic refresh，默认推荐人工 `sync --preview` + `sync --source manual` | CronOrDaemon (legacy auto_sync_startup.vbs) | NONE |
| `semantic_refresh_worker.py` | 兼容/手动 drain 工具；有 queue 时 debounce 后复查 stale，并委托 `maintain.py semantic-sync --trigger worker` 刷新派生索引；Stop hook 不再 fire-and-forget 调用它 | Manual / Compatibility | WARN |
| `update_readme.py` | 自动更新 README | Manual / Manifest | NONE |
| `update_stats.py` | 自动更新 stats | Manual / Manifest | NONE |
| `sync_index.py` | 同步索引 | Manual / Manifest | NONE |
| `init_project.py` | 项目初始化 | Manual | NONE |
| `close_project.py` | 项目收尾 | Manual | NONE |
| `extract_to_memory.py` | 内容提到记忆 | Manual | NONE |
| `memory_gc.py` | 记忆 GC | Manual | REPORT |
| `audit_skill.py` | skill 审计；`--json` 输出 summary，按 skill level、issue level、issue code 和 deployed-extra 聚合 | Manual | REPORT |
| `baseline_compare.py` | baseline 对比 | Manual | REPORT |
| `changelog_archive.py` | CHANGELOG 归档 | Manual | NONE |
| `append_changelog.py` | append CHANGELOG CLI | Manual | NONE |
| `check_prepare.py` | `/check` 前置输入契约；`--json` 输出任务解析、review_docs、doc_scans、warnings 和 prompt_inputs | Skill /check | REPORT |
| `deploy_hooks.py` | 部署 hooks | Manual | NONE |
| `generate_catalog.py` | 生成 agents/skills/harness 自动组件目录；`--check --json` 只读验证 freshness，release-check 的 `catalog_freshness` 复用同一检查 | Manual / Manifest / Release profile | REPORT |
| `generate_project_context.py` | 生成项目上下文 | Manual | NONE |
| `show_diffs.py` | 显示 diff | Manual | NONE |
| `ai_runner.py` | AI 运行器 | ?? | — |
| `work_context_pack.py` | `/work` 上下文打包；`--json` 输出只读 `work_context` 摘要并进入 output-contract，默认非 JSON 模式仍可生成 STATUS.md；`--intent` 接收用户原话，明确新任务意图复用 `.current_task` 时输出 `intent_guard` warning | Manual / Manifest / 控制面板 | REPORT |
| `work_runner.py` | work-runner 状态机、verifier-only check、fake/codex-exec adapter、bounded repair loop、verifier gate；runner-owned state、gate feedback、JSONL log 的库实现 | Library | — |
| `config.py` | harness/repo/Claude/task/log/cache 根路径共享配置 | Library | — |
| `stage_lib.py` | 阶段检测 lib | Library | — |
| `_lib.py` | 公共 lib | Library | — |

---

## 10. md2html（harness/md2html/）

| 脚本 | 用途 | 触发方 |
|---|---|---|
| `md2html/md2html.py` | Markdown → HTML | Manual |
| `md2html/md2html_classifier.py` | 分类 | Library |
| `md2html/md2html_components.py` | 组件 | Library |

---

## ⚠ 待澄清 / Deprecated 总览

| 脚本 | 现状 |
|---|---|
| `hooks/route_gate.py` | deprecated；未在 settings.json 注册，保留作旧 route_pending 兼容参考 |
| `ai_runner.py` | 用途待标注 |

巡检：`python harness/scripts/scan_orphan_scripts.py --strict --json`。它只检查“脚本是否被登记”，不判断脚本是否属于外部 MVP；能力归属由 `check_capability_manifest.py` 继续校验。

---

## 添加新脚本 checklist

1. 选目录：hook → `harness/hooks/`，gate 候选 → `harness/scripts/`，治理 → `harness/`，体检 → `harness/health/checks/`
2. 写脚本，避免硬编码（用 `Path(__file__).parents[N]` 或 `Path.home()`）
3. 用 `python harness/scripts/register_script.py <harness-relative.py> --capability <id> --purpose "..." --trigger Manual --failure REPORT --apply` 同步更新本表与 `harness/capability_manifest.json`
4. 决定触发方：
   - 进 settings.json hooks → 见 `docs/hook-chain.md`
   - 进 gate_check → 见 `docs/gate-template.md`
   - 仅 Manual → 在 `CONTRIBUTING.md` 列 CLI 用法
5. 跑 `fix_hardcoded_paths.py` 自查
6. 跑 `verify/smoke_test.py` 验证
