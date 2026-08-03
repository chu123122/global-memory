---
doc_type: audit
status: draft
last_updated: 2026-05-26
trigger:
  keywords: [concept:capability-map, concept:open-source-readiness, tool:harness]
  tags: [workflow, tooling]
---

# 能力地图与开源倒逼缺口

本文不是判断项目是否真的要开源，而是用“可被外部用户安装、理解、验证、替换运行环境”的标准，倒逼当前 `global-memory` 的实现问题浮出水面。

当前结论：系统能力已经很多，主要风险不是“缺功能”，而是“能力增长速度超过了吸收机制”。历史上已经出现三类状态：

1. 已提交能力，但没有进入总览/注册表/主入口。
2. 文档已经声称存在，但文件或 bootstrap 运行链路未完全接上。
3. 产物体系已经形成，但没有概念入口和生命周期规则。

本轮已把“吸收机制”前移为机器检查：`check_capability_manifest.py --json` 现在不仅校验 manifest 内脚本存在，还反向扫描 `harness/`，要求 136 个实际 Python 脚本全部归属到 `core | optional | experimental | legacy | deprecated` 能力域。目前 `assigned_scripts=136`、`unassigned_scripts=0`、`coverage_exemptions=0`。同时新增 `docs/getting-started.md` 作为外部最小安装/验证入口，新增 `docs/capabilities.md` 作为能力人类可读入口；18 个能力域必须用 `capability:<id>` 绑定 manifest，否则检查失败。`release-check` 现在还会用 `catalog_freshness` 对比 `generate_catalog.py` 的当前输出，阻断 `agents/README.md`、`skills/README.md`、`harness/README.md` 这类自动组件目录漂移。

## 当前 checkpoint

2026-05-26 07:53 复核后的验证结论：当前 release 线已经能稳定给出同一个主结论，`verdict=blocked`。阻断项仍是 2 个 owner 决策；同时重新收紧客户端语义后，release-check 明确暴露 1 个 warning：当前只有 Claude Code 是 full-lifecycle stable，generic CLI 只稳定支持 read-only Context Brief。`check_client_manifest.py` 现在严格要求 readiness flag 是 boolean，并输出 `readiness.full_lifecycle_multi_client=1/2`、`readiness.context_cli=2/2`、`claim_policy_checked=3`、`claim_policy.forbidden_checked=3`，同时输出 `contracts.full_lifecycle_required_capabilities`、`clients[].missing_full_lifecycle_capabilities`、`clients[]` 摘要和 `remediation_plan`；`release-check`、`release_issue_ledger`、`release-gaps` 和 `release-checkpoint` 会保留这些证据，output-contract 会在证据丢失时失败。`client_portability` 的 warning 已从自由文本 `next_action` 收束为机器可读路线：要么保持窄叙事 `keep_narrow_claim`，要么补第二个 full-lifecycle stable 客户端 `add_second_full_lifecycle_client`。其中 full-lifecycle promotion 的机器清单是 install/bootstrap、automatic context injection、write governance、audit logging、rollback/disable、release health check。主入口缺口表也已经有自动化形态：`maintain.py release-gaps --strict --json` 会因当前 blocker/warning 返回非零，但仍输出可解析的 `release_gap_table` JSON；owner-only strict 只按 owner 决策队列 readiness 和记录合法性返回非零，不再被未来非 owner blocker 混淆。外部源码安全扫描已经作为独立 JSON 契约和 release-check 聚合项闭合：计划外发源码 `264` 个文件全量扫描，`blockers=0`、`warnings=0`。本轮把手工收束动作固化为 `maintain.py release-checkpoint --json`：一个只读 payload 同时给出外部源码安全、release verdict、issue ledger、gap table、owner decisions、owner-editable decision template 和 manifest 摘要。

| 分类 | 缺口 | 当前证据 | 处理性质 |
|---|---|---|---|
| Owner decision | `license_policy` 未定，缺 `LICENSE` / `LICENSE.md` / `COPYING` | `release-check`: `project_metadata` blocker；`release_issue_ledger`: `oss-project_metadata` open | 项目 owner 选择许可证或明确不按开源复用发布 |
| Owner decision / publish-scope governance | `publish_scope_boundary` 已定（public_showcase + private split）；当前 tracked private paths = 0，unclassified tracked paths = 10（根文件未归类） | `check_publish_scope.py --strict`: `private_tracked_paths=0`, `unclassified_tracked_paths=10`；`release_issue_ledger`: `oss-publish_scope` resolved | 个人数据已迁私有仓库，剩余 unclassified 根文件补入 publish_scope manifest |
| Code remediation | CI workflow 覆盖、maintenance manifest、自动组件目录 freshness、外部源码导出、外部源码安全扫描、hook 对齐、硬编码路径、输出契约、smoke、能力归属、task lifecycle 状态契约、self-loop 只读报告契约、release checkpoint 契约均已进入 release-check 或 output-contract 线 | `ci_workflow`: yaml_valid=true, steps=11, required_commands=7, findings=0；`maintenance_manifest`: commands=14, scripts=43, required=12, findings=0；`catalog_freshness`: targets=3, stale=0, missing=0；`export_source_scope.py --strict`: included=264, untracked_included=0；`scan_external_safety.py --strict`: scanned=264, blockers=0, warnings=0；`maintain.py release-checkpoint --json`: kind=release_checkpoint, release_verdict=blocked, code_remediation=0；`maintain.py release-checkpoint --strict --json`: exit 1 as expected, still emits parseable release_checkpoint JSON；`verify_output_contracts.py`: 42 cases / 0 error；`client_context_generic_cli`: docs 示例 `--client generic_cli` 进入 output-contract；`scan_dual_storage.py --json`: kind=dual_storage_scan；`analyze_retrieve_log.py --json`: retrieve hit/zero-hit/namespace/miss-sample 聚合契约；`work_context_pack.py --json`: kind=work_context and no session marker write；`harness_status.py --tasks --json`: kind=harness_tasks；`self_loop_report.py --json` / `meta_optimize.py --json`: 0 findings in contract check | 暂无主线代码整改 blocker |
| Docs / release-scope governance | getting-started、capabilities、capability gap checkpoint、contributing、license decision、publish scope 入口已被 release profile 覆盖；docs 入口 frontmatter 必须带 `status` 和 `last_updated`；客户端边界已从“两个 stable client”细化为 full-lifecycle vs Context Brief only；关键外部入口必须保留窄边界 claim policy 且禁止过度声明 | `docs_entrypoints`: `checked=6, frontmatter_checked=5, findings=0`；`release_issue_ledger`: `oss-docs_entrypoints.evidence.frontmatter_checked=5`；`client_portability`: readiness.full_lifecycle_multi_client=1/2, readiness.context_cli=2/2, claim_policy_checked=3, claim_policy.forbidden_checked=3, warnings=1；`check_client_manifest.py --json`: `contracts.full_lifecycle_required_capabilities=6`, `codex_cli.missing_full_lifecycle_capabilities=5`, `generic_cli.missing_full_lifecycle_capabilities=6`；`release_issue_ledger` / `release-gaps`: `oss-client_portability.evidence.clients[]`, `claim_policy`, and `remediation_plan` retained | 按 `remediation_plan.options`: 保持外部叙事为 Claude Code + Context Brief CLI，或补第二个 full-lifecycle stable 客户端 |

当前关键命令输出摘要：

- `python harness\maintain.py release-check --profile oss --json`: 15 PASS, 1 WARNING, 2 BLOCKER.
- `python harness\maintain.py release-checkpoint --json`: kind=release_checkpoint, release_verdict=blocked, release_pass=14, release_check_mode=skip_output_contracts, release_check_output_contracts_included=false, release_warnings=1, release_blockers=2, owner_decisions=2, owner_decision_templates=2, code_remediation=0, docs_publish_scope_governance=1, external_source_blockers=0, external_source_warnings=0. 这里的 `release_pass=14` 来自 checkpoint 内部的 `--skip-output-contracts` 子检查；完整 `release-check` 仍是 15 PASS。
- `python harness\maintain.py release-checkpoint --strict --json`: exit 1 as expected, kind=release_checkpoint, strict=true, release_verdict=blocked.
- `python harness\maintain.py release-gaps --json`: kind=release_gap_table, owner_decisions=2, code_remediation=0, docs_publish_scope_governance=1, deferred=1, open_by_gap_type.owner_decision=1, open_by_gap_type.publish_scope_governance=1, open_by_gap_type.verified_capability=1.
- `release-gaps` 和 `release-checkpoint` 内聚合的 `remaining_gap_table.owner_decisions[]` 会直接携带 `decision_doc`、`allowed_options`、`record_dry_run_command`、`record_write_command`，让 owner 决策从 gap 行即可进入文档、dry-run 和显式写入流程；`publish_scope` 行还携带 `publish_scope_breakdown`，直接显示 private tracked paths 的 by_path_group/by_reason 摘要，当前主噪声是 `knowledge=53`、`projects=42`、`feedback=26`、`.meta=22`；`release-checkpoint` 还聚合 `release_decision_template`，包含 `state_patch_template`，不用额外再跑一次 template 命令才能得到 owner 可编辑记录骨架；`docs_publish_scope_governance[]` 中的 `oss-client_portability` 会直接携带 `evidence.readiness`、`evidence.clients[]`、`evidence.remediation_plan` 和 `client_lifecycle_gaps`，不用回跳 full ledger 才能判断客户端边界、full-lifecycle promotion 清单和下一步选项。
- owner 决策模板、gap 行和 dry-run/write 报告都携带 `record_gate_effect.effect=records_owner_choice_only`、`record_gate_effect.clears_release_blocker=false`，避免把“记录 owner 选择”误判成“release blocker 已解除”。
- `release-decisions` 的 `ready` 保持兼容但现在明确等同 `gate_ready`；`record_ready` 单独表示 state file 是否已经有合法 `decided` 记录。当前快照是 `gate_ready=0`、`record_ready=0`。
- owner 决策、gap 行和 dry-run/write 报告还携带 `gate_unblock_requirements`：当前 `license_policy` 是 `required_artifacts=LICENSE/LICENSE.md/COPYING`，`publish_scope_boundary` 是 `required_conditions.private_tracked_paths=175`、`required_conditions.unclassified_tracked_paths=0`。
- `python harness\maintain.py release-decisions --json`: kind=release_owner_decisions, owner_decisions=2, valid_records=2, record_status_counts.undecided=2.
- `python harness\maintain.py release-decisions --strict --json`: exit 1 as expected, kind=release_owner_decisions, owner_decisions=2, not_ready=2.
- `python harness\maintain.py release-decisions --template --json`: kind=release_owner_decision_template, templates=2, includes allowed_options and state_patch_template for each owner decision.
- `python harness\maintain.py release-record-decision --dry-run --decision license_policy --selected-option no_public_license --decided-by contract-test --decided-at 2026-05-25 --json`: kind=release_owner_decision_record, valid=true, action=dry_run, writes nothing.
- `python harness\maintain.py release-record-decision --dry-run --decision publish_scope_boundary --selected-option keep_private_maturity_audit --decided-by contract-test --decided-at 2026-05-26 --json`: kind=release_owner_decision_record, valid=true, action=dry_run, required_when.private_tracked_paths=175, writes nothing.
- `python harness\scripts\release_issue_ledger.py --json`: open=3, resolved=14, deferred=1, remaining_gap_table.owner_decisions=2, code_remediation=0, docs_publish_scope_governance=1, summary.open_by_gap_type.owner_decision=1, summary.open_by_gap_type.publish_scope_governance=1, summary.open_by_gap_type.verified_capability=1.
- `python harness\scripts\release_issue_ledger.py --gap-table-only`: owner_decisions=2, code_remediation=0, docs_publish_scope_governance=1, deferred=1, open_by_gap_type.owner_decision=1, open_by_gap_type.publish_scope_governance=1, open_by_gap_type.verified_capability=1; human text includes decision docs, allowed_options plus dry-run/write commands for each owner decision, includes `publish_scope` private_by_path_group/private_by_reason summaries, and includes client readiness/client rows plus `full_lifecycle_required` and per-client `missing_full_lifecycle[...]` rows for `oss-client_portability`.
- `python harness\scripts\release_issue_ledger.py --owner-decisions-only --json`: owner_decisions=2, valid_records=2, record_status_counts.undecided=2.
- `python harness\scripts\release_issue_ledger.py --owner-decisions-only`: human text includes required follow-up context plus dry-run/write commands for each owner decision.
- `python harness\scripts\release_issue_ledger.py --decision-template --json`: kind=release_owner_decision_template, templates=2.
- `python harness\scripts\export_source_scope.py --strict --json`: verdict=ready, export_included_paths=264, excluded_private_paths=189, unclassified_paths=0.
- `python harness\scripts\scan_external_safety.py --strict --json`: verdict=ok, planned_external_files=264, scanned_files=264, blockers=0, warnings=0, by_code=0, top_paths=0, remediation_groups=0.
- `python harness\verify\verify_output_contracts.py --json`: 42 cases, 0 ERROR, 0 WARNING.
- `python harness\generate_catalog.py --check --json`: verdict=ok, targets=3, fresh=3, stale=0, missing=0, findings=0.
- `python harness\reporting\harness_status.py --tasks --json`: kind=harness_tasks, active=13, archived=16, missing_active=7, unknown_active=2.
- `python harness\scripts\self_loop_report.py --json`: mode=self-loop-overview, optimization_ledger.count=1, fallback_candidates.candidate_tasks=4.
- `python harness\scripts\meta_optimize.py --json`: mode=read-only, finding_count=12, user_visible.verdict=TASK_CONTEXT_TRIAL_PACK_READY.
- `python -m unittest harness.tests.test_release_issue_ledger harness.tests.test_verify_output_contracts harness.tests.test_oss_readiness_check harness.tests.test_governance_pulse`: 196 tests OK.

## 1. 当前能力分层

| 层级 | 代表能力 | 当前状态 | 主要问题 |
|---|---|---|---|
| Core memory | `harness_retrieve.py`, `client_context.py`, trigger frontmatter, `retrieve_calls.jsonl` | 已提交，已有测试和日志；硬编码路径检查已清零 | retrieve 注入已对齐 bootstrap；通用 CLI Context Brief 契约已稳定 |
| Runtime hooks | `dangerous_command_blocker.py`, `doc_gate.py`, `route_check.py`, `retrieve_inject.py`, `memory_lint_gate.py` | 当前 manifest/docs/bootstrap/runtime 已对齐 | 后续可从 manifest 生成文档，减少手写漂移 |
| Governance gates | `gate_check.py`, `scan_dual_storage.py`, `check_trigger_coverage.py`, `fix_hardcoded_paths.py` | `gate_check.py --json` 已可只读输出 verdict 并进入 release profile；`scan_dual_storage.py` 保留 `dual_count=` 文本给 G1，同时新增 `--json` 进入 output-contract、maintenance manifest 和 `governance_pulse` | G9 在旧 gate 中仍是 WARN 语义，但 OSS profile 另有 hardcoded_paths BLOCKER 检查 |
| Health signals | `health/runner.py`, `retrieve_hitrate.py`, `retrieve_pointer_consumption.py`, `lint_failure_rate.py` | 能产生诊断信号，已补进脚本注册表 | 作为 legacy/diagnostic 信号保留，不进入默认 release verdict |
| Self-loop | `meta_optimize.py`, `self_loop_report.py`, `.meta/optimizations` | 已提交且能输出总览，已补进脚本注册表、capability manifest 和 output-contract；统一支持 `--json` | 保持 optional diagnostics，不默认自动优化 |
| Retrieve experiments | `retrieve_*simulation.py`, `retrieve_*trial_pack.py`, `retrieve_fallback_candidates.py` | 已提交，形成证据链，已补进脚本注册表和 capability manifest | 已标 experimental，不进入默认 release scope |
| Task lifecycle | `archive_task.py`, `update_phase_status.py`, `assurance_gate.py`, `harness_status.py --tasks --json` | 已进入脚本注册、能力归属和 output-contract；当前任务概览输出 `kind=harness_tasks` 与 summary 计数 | 不是默认外部 MVP 阻断项，后续若提升为外部能力，再补归档/状态迁移行为验收 |
| GUI/reporting | control panel, `maintain.py report` | 已存在 | 更适合作为 optional diagnostics，不应是默认开源路径 |

## 2. 已提交但刚被总览吸收的能力

基线扫描曾暴露 14 个 tracked 脚本没有进入 `docs/scripts-registry.md`。本轮已把它们纳入注册表；当前 `python harness/scripts/scan_orphan_scripts.py --strict --json` 结果为：

- 实际脚本数：136
- `docs/scripts-registry.md` 提及：147
- 未注册：0
- 已知 ORPHAN：0
- stale registry：0

进一步的能力归属检查结果：

- `harness/capability_manifest.json` 能力域：18
- release scope 能力域：9
- 实际脚本数：136
- 已归属脚本数：136
- 未归属脚本：0
- coverage exemptions：0

本轮吸收的脚本：

| 文件 | 能力归属 | 应纳入位置 | 建议状态 |
|---|---|---|---|
| `harness/scripts/self_loop_report.py` | 自循环总览 | `scripts-registry.md`, `MAINTENANCE.md` | optional |
| `harness/scripts/meta_optimize.py` | 证据驱动优化建议 | `scripts-registry.md`, `maintenance_manifest.json` | optional |
| `harness/scripts/assurance_gate.py` | 任务完成门禁 | `scripts-registry.md`, release/profile checks | core-candidate |
| `harness/scripts/retrieve_fallback_candidates.py` | fallback 候选准入 | `scripts-registry.md`, `.meta` 说明 | experimental |
| `harness/scripts/retrieve_candidate_quality.py` | pointer 质量报告 | `scripts-registry.md`, health docs | optional |
| `harness/scripts/retrieve_downrank_simulation.py` | retrieve downrank 模拟 | `scripts-registry.md`, `.meta` 说明 | experimental |
| `harness/scripts/retrieve_fallback_cost.py` | fallback 成本统计 | `scripts-registry.md` | optional |
| `harness/scripts/retrieve_trace.py` | retrieve 评分解释 | `scripts-registry.md` | optional |
| `harness/scripts/retrieve_zero_hit_analysis.py` | zero-hit 分析 | `scripts-registry.md`, health docs | optional |
| `harness/health/checks/lint_failure_rate.py` | memory lint 失败率 | `scripts-registry.md`, health registry 文档 | core-candidate |
| `harness/health/checks/retrieve_pointer_consumption.py` | pointer 真消费率 | `scripts-registry.md`, health registry 文档 | core-candidate |

这批是最典型的“能力存在，但总览没有吸收”。它们已经 tracked，不能再当临时脚本处理；当前已经进入 `docs/scripts-registry.md`，并通过 `harness/capability_manifest.json` 标出 core/optional/experimental/legacy 边界。现在这个约束已经扩展为全脚本覆盖：registry 解决“文件是否被看见”，capability manifest 解决“脚本属于哪个能力”。

## 3. 曾经漂移、当前已被发布闭环吸收的能力

| 能力 | 文档状态 | 当前风险 | 建议动作 |
|---|---|---|---|
| `retrieve_inject.py` | `docs/hook-chain.md` 和 `docs/scripts-registry.md` 写成 UserPromptSubmit hook | 已进入 hook manifest、bootstrap、runtime settings 与 registry；release profile 通过 hook alignment | 保持为 core hook，后续用 manifest 生成文档以降低手写漂移 |
| `memory_lint_gate.py` | 文档写成 Write/Edit/MultiEdit BLOCK hook | 已进入 hook manifest、bootstrap、runtime settings 与 registry；release profile 通过 hook alignment | 保持 BLOCK 语义，后续补更细的行为级 smoke |
| `statusline.py` | 文档写成 statusLine hook | 已进入 hook manifest、bootstrap、runtime settings 与 registry | 继续由 `check_hook_alignment.py --strict` 对账 |
| `governance_pulse.py` | `scripts-registry.md` 已写成 daemon/cron | 已进入 capability manifest 和 maintenance manifest；`--once` 明确登记为 local log write，定位为 optional/diagnostic，不是默认 release gate | 保持非默认启用 |
| `archive_task.py` | `docs/task-lifecycle.md` 已引用归档流程 | 已进入脚本注册与能力归属；task lifecycle 不是默认外部 MVP 阻断项 | 后续按 task lifecycle 能力补行为验证 |
| `update_phase_status.py` | `scripts-registry.md` 已列为 phase 同步工具 | 已进入脚本注册与能力归属；不是默认发布 blocker | 后续按 task lifecycle 能力补行为验证 |

这类比“未注册”更危险，因为它会让读者以为系统已经稳定支持，而实际 fresh clone 或 bootstrap 不一定得到同样行为。当前已经通过 hook manifest、scripts registry、capability manifest 和 release profile 把它们吸收进主闭环；后续风险是再次手写漂移。

## 4. `.meta` 已经是隐形子系统

`.meta/` 当前包含：

| 目录 | 当前用途 | 风险 |
|---|---|---|
| `.meta/proposals/` | 优化提案 | 没有状态机，容易堆积 |
| `.meta/evaluations/` | 模拟/评审结果 | 没有统一索引 |
| `.meta/experiments/` | opt-in 实验配置 | 不清楚哪些可运行、哪些过期 |
| `.meta/trials/` | 试用包 | 没有归档规则 |
| `.meta/candidates/` | fallback 候选任务 | 没有准入/拒绝生命周期说明 |
| `.meta/optimizations/` | 已应用优化 ledger | 没有纳入 README/MAINTENANCE |

这条链路实际上已经形成：

`health/retrieve logs -> proposal -> simulation/evaluation -> trial -> candidate admission -> optimization ledger -> self_loop_report`

但这个概念没有被总览文档承认。开源倒逼下，它必须成为明确的 `experimental evidence pipeline`，或者被拆出 core 之外。

## 5. 开源倒逼出的主要实现问题

### P0: 能力注册缺失

现状：脚本可以存在、提交、被某个 report 调用，但不进 `scripts-registry.md`、`capability_manifest.json`、`maintenance_manifest.json`、README 或 doctor。本轮已把前四项做成强检查：`scan_orphan_scripts.py --strict --json` 输出 `kind=orphan_script_scan`，并在未登记脚本或 registry stale 记录存在时阻断；`check_capability_manifest.py` 在 `require_all_harness_scripts=true` 时阻断未归属能力的脚本；`release-check` 的 `maintenance_manifest` 检查会阻断 manifest 中不存在的脚本路径、重复 id、缺失 category，以及关键入口参数漂移；`catalog_freshness` 会阻断自动生成的 agents/skills/harness README 未刷新。

要求：

- 新增脚本必须进入 `docs/scripts-registry.md`；新增能力域必须进入 `harness/capability_manifest.json` 并标出状态；新增脚本还必须被某个能力域吸收或显式 exemption。
- `scan_orphan_scripts.py --strict` 应进入 release profile。
- `scripts-registry.md` 和 capability manifest 不应手工维护到长期漂移；当前已有 registry drift 与 capability coverage 阻断，后续可考虑从 manifest 生成人类文档。

### P0: Hook source of truth 不存在

现状：本轮已新增 `harness/hook_manifest.json` 作为 hook source of truth；`bootstrap.py` 从 manifest 渲染 hook 配置并在 install/check 时校验 manifest 文件存在性和枚举值，`check_hook_alignment.py --strict --json` 同时校验 manifest schema/path 并对账 manifest、bootstrap、实际 `settings.json` 和 `docs/scripts-registry.md`。

要求：

- `harness/hook_manifest.json` 继续作为唯一机器可读源。
- `bootstrap.py` 从 manifest 渲染。（已完成）
- docs 从 manifest 生成或校验。（当前为校验；后续可生成）
- `doctor`/release profile 对 manifest 与 runtime 做强校验。（release profile 已通过 `check_hook_alignment.py` 校验；坏 path/缺文件/非法 failure_action 会阻断）

### P0: 路径和客户端绑定过强

现状：本轮已清掉 `fix_hardcoded_paths.py` 能检测到的 Python 脚本和记忆/文档旧路径问题；`oss_readiness_check.py` 中 `hardcoded_paths` 已从 BLOCKER 变为 PASS。任务根已改为 `CLAUDE_TASKS_ACTIVE`/`CLAUDE_TASKS_ARCHIVED`/`CLAUDE_TASKS_ROOT` 可覆盖，记忆根使用 `GLOBAL_MEMORY_DIR`。新增 `harness/config.py` 后，release-facing 脚本和旧共享库 `_lib.py` / hook 共享层开始复用同一组 repo、Claude home、task、log、cache root 解析，避免每个脚本重新拼 `Path.home()/.claude`。

机器阻断：`oss_readiness_check.py` 已新增 `path_config` 检查，扫描 release-facing 路径表面；如果重新出现 `Path.home() / ".claude"`、`CLAUDE_HOME` 或 `GLOBAL_MEMORY_DIR` 的本地 fallback 复制，会作为 OSS profile blocker 暴露。

客户端边界：本轮新增 `harness/client_manifest.json` 和 `check_client_manifest.py --json`，并补了 `client_context.py` 作为通用 CLI 客户端 Context Brief 契约。当前 `claude_code` 是 `full_lifecycle` stable；`generic_cli` 是 `context_brief_only` stable；`codex_cli` 是 `context_brief_only` experimental。机器字段上 `context_cli_ready=true`，但 `multi_client_ready=false`；`readiness.context_cli` 是 `2/2`，`readiness.full_lifecycle_multi_client` 是 `1/2`。这表示“读取 Context Brief 的跨客户端入口”成立；完整 hook/write/audit 生命周期治理仍主要是 Claude Code harness，并会作为 release warning 暴露。`contracts.full_lifecycle_required_capabilities` 现在把 full lifecycle 明确定义为 install/bootstrap、automatic context injection、write governance、audit logging、rollback/disable、release health check；`clients[].missing_full_lifecycle_capabilities` 会直接列出 Codex/generic CLI 距离 stable full lifecycle 还缺什么。

要求：

- 继续把存量非 release-facing 脚本逐步迁到 `harness/config.py`，但不把这件事作为当前 OSS profile 的默认阻断项。
- `fix_hardcoded_paths.py` 在 `oss` profile 中继续对核心脚本硬阻断。
- `gate_check.py --json` 已是无副作用 JSON gate；默认 Markdown GATE-REPORT 模式保留兼容。
- 若要把 Codex CLI 做到 stable full-lifecycle，需要补 Codex 专属注入/安装路径、写入治理和审计 hook 映射；当前可通过通用 `client_context.py` 手动获取 Context Brief。

### P1: 主健康线没有唯一发布结论

现状：`maintain.py release-check --profile oss --json` 转发 `oss_readiness_check.py`，已经能把能力注册、maintenance manifest、客户端边界、hook 对齐、bootstrap、发布范围、导出计划、外部源码安全、路径配置、硬编码路径、输出契约、smoke 聚合成 `ready | needs_cleanup | blocked`。当前默认 OSS profile 是 `blocked`：2 个 blocker（license 未决、tracked private publish paths）和 1 个 warning（full-lifecycle stable client 只有 Claude Code；generic CLI 只覆盖 read-only Context Brief）。外部源码安全扫描只扫描 clean export 计划中的外部文件，高置信 secret 是 blocker，本机绝对路径是 warning；当前 docs/examples、runtime_source 与 public history 已清理，`PUBLIC_CHANGELOG.md` 作为公开历史进入 external scope，`CHANGELOG.md` 作为含本地来源的私有审计日志排除在 source export 外。`scan_external_safety.py` 仍会在 public_history-only warning 重新出现时输出 `policy_plan`。`check_health.py` 已标 LEGACY/DEPRECATED，主要审个人记忆索引/frontmatter 存量，改为 `--include-legacy-health` 显式 opt-in。

要求：

- `maintain.py release-check --profile oss` 是发布/外部接入评估主入口。
- 统一输出一个 verdict：`ready | needs_cleanup | blocked`。
- 每个 blocker 必须有 source、evidence、next_action。
- `release_issue_ledger.py --json` 将当前 release-check 结果派生成 open/resolved/deferred issue ledger，并给未决 owner 事项生成顶层 `owner_decisions` 队列和 `remaining_gap_table`，避免问题只停留在一次性报告里。

### P1: 自循环没有产品边界

现状：`meta_optimize.py` 和 `self_loop_report.py` 已能工作，并已统一支持 `--json`；输出契约现在检查 self-loop overview、优化 ledger、fallback candidate 计数、read-only finding ledger、user-visible decision 和 severity 聚合。它们仍定位为 optional diagnostics，不自动修改运行时默认行为。

要求：

- 明确它是 `optional diagnostics`，不是默认自动优化器。
- 保留只读原则：proposal/evaluation/trial 可以自动生成，apply 必须显式 opt-in。
- `.meta/optimizations/optimizations.jsonl` 作为 ledger，需要 schema 和 lifecycle。

### P2: 实验能力没有隔离

现状：retrieve simulation/trial/fallback candidates 与核心 retrieve 混在同一 scripts 目录；本轮已用 `harness/capability_manifest.json` 将 `retrieve_experiments` 标为 `experimental` 且 `release_scope=false`。

要求：

- 用 `capability_manifest.json` 标 `core | optional | experimental | legacy | deprecated`。
- release profile 默认只检查 core + optional smoke，不要求 experimental 全绿。
- experimental 文件必须有清晰入口和“不默认启用”的说明。

## 6. 建议的整理顺序

### Phase 1: 吸收现有能力，不改行为

目标：让系统看得见自己已经有什么。

任务：

1. 更新 `docs/scripts-registry.md`，纳入 14 个 tracked 脚本。（已完成，当前 `unregistered=0`）
2. 给 `.meta/` 增加 `docs/meta-evidence-pipeline.md`。
3. 在 `MAINTENANCE.md` 增加“自循环/优化证据链”小节。
4. 给能力边界增加状态：`core/optional/experimental/legacy/deprecated`。（已通过 `capability_manifest.json` 落地）
5. 让 `scan_orphan_scripts.py --strict` 成为可运行检查，并进入 release profile。
6. 让 `check_hook_alignment.py --strict` 成为可运行检查，用来暴露 bootstrap/runtime/registry drift。

验收：

- `scan_orphan_scripts.py --strict --json` 中 `verdict=ok`、`unregistered=0`、`stale_in_registry=0`，或所有未注册/过期记录均有明确处理。
- `check_hook_alignment.py --strict --json` 能列出 hook 漂移；当前 manifest、bootstrap、runtime settings 和 registry 已对齐。
- README/MAINTENANCE 能解释 `self_loop_report.py` 和 `.meta/`。

### Phase 2: 修 hook 漂移

目标：文档、bootstrap、runtime 对齐。

任务：

1. 建立 hook manifest。
2. `retrieve_inject.py`、`memory_lint_gate.py`、`statusline.py` 已进入默认 hook 链，并已对齐 bootstrap/runtime/registry。
3. 继续补行为级 smoke，而不是再补“是否接入”的检查。
4. 若未来从默认链路移除，必须同步从 hook-chain/registry 中降级为 experimental/planned。

验收：

- `bootstrap.py check` 不再因 hook 缺失 blocked。
- `docs/hook-chain.md` 与 bootstrap 期望一致。
- `check_hook_alignment.py --strict --json` 返回 `verdict=aligned`。

### Phase 3: 开源 profile

目标：用开源要求反推真正阻断项。

任务：

1. `maintain.py release-check --profile oss --json` 已提供只读 OSS profile 聚合入口；legacy health 已改为 opt-in。
2. G9/硬编码路径在 `oss` profile 下已作为 `hardcoded_paths` 检查项；当前为 PASS。
3. `health.runner` 支持直接执行或文档统一 module 执行。
4. `maintain.py` 已增加 release verdict 并转发 `oss_readiness_check.py`。

验收：

- 一条命令能回答“当前为什么还不能作为外部可接入项目”。
- 输出 blocker/warning 包含能力注册、客户端边界、hook 漂移、硬编码路径、输出契约、smoke 等问题；legacy health 作为内容治理债务单独追踪。

## 7. 当前优先级结论

现在最先做的不是继续新增能力，而是做“吸收层”：

1. `scripts-registry.md` 先吃掉 14 个 tracked 未注册脚本。
2. `.meta` 证据链写成正式 experimental pipeline。
3. hook manifest 解决“文档说有、bootstrap 没接”的漂移。
4. `gate_check` 做成无副作用 JSON 门禁，为开源 profile 提供机器可读 verdict。（已完成）

这四件事已经基本进入机器检查链；README 已补上真实产品边界和 release-check quickstart。常规开源事项中，CI 和开发验证依赖已经补上；`.github/workflows/oss-readiness.yml` 会先跑 release ledger/output contract、当前 release checkpoint、当前 gap table、owner decision queue，再跑最终 `release-check` 阻断。许可证仍需项目所有者显式选择，`release-check` 会把缺失 `LICENSE` 当作外部发布 blocker，而不是默认替你选择 MIT/Apache。`docs/license-decision.md` 记录可选路径和决策清单，`harness/release_owner_decisions.json` 记录 owner 选择状态，`release_issue_ledger.py` 会把它派生成 `oss-project_metadata.evidence.decision_plan` 和顶层 `owner_decisions[]`，但不会解除 blocker。

另一个被开源倒逼暴露出的真实阻断项是发布范围：当前 Git 跟踪了 `.meta/`、`projects/`、`feedback/`、`knowledge/`、`interview/`、`CHANGELOG.md` 等个人数据/任务上下文。`harness/publish_scope_manifest.json` 是机器可读边界，`docs/publish-scope.md` 说明默认外部源码范围；`release-check` 的 `publish_scope` 会通过 `check_publish_scope.py` 在这些路径仍被跟踪时阻断外部发布，并输出 `private_tracked_summary` 和 `decision_plan`，按 manifest 原因、顶层路径域、匹配类型和 owner 选择聚合。`export_source_scope.py` 进一步生成只读 clean source 导出计划，让拆仓/导出路径可以机器复查；如果未来又出现未跟踪的外部文件，它会输出 `tracking_plan`，给出精确 `git add -- ...` 参数向量但不修改 index。`release_issue_ledger.py` 把 release-check 当前结果派生成 open/resolved/deferred issue ledger，并给每个 issue 增加 `gap` 分类、`summary.open_by_gap_type` / `summary.open_by_owner` 聚合、顶层 `owner_decisions` 队列和 `remaining_gap_table`，补上“发现问题后当前真相在哪里看、该由谁推进”的缺口。
