# Harness 目录


## 核心脚本

| 文件 | 描述 |
|------|------|
| `_lib.py` | _lib.py — 记忆维护脚本的共享工具库 |
| `ai_runner.py` | ai_runner.py — 桌面主控台的 AI 适配层 |
| `append_changelog.py` | append_changelog.py — 追加 CHANGELOG.md 审计记录 |
| `audit_skill.py` | audit_skill.py — 确定性 Skill 结构审计 |
| `auto_sync_daemon.py` | auto_sync_daemon.py — global-memory 自动同步守护进程 |
| `baseline_compare.py` | baseline_compare.py — 改代码前后的验证结果对比工具 |
| `changelog_archive.py` | changelog_archive.py — CHANGELOG 周归档脚本 |
| `check_prepare.py` | check_prepare.py — /check 设计审查的确定性输入准备 |
| `close_project.py` | close_project.py — 从 MEMORY.md 活跃项目表中移除 |
| `config.py` | Shared path configuration for the global-memory harness. |
| `control_panel_pyside_launch.py` | PyInstaller 入口 wrapper（v2.1 R4-a 修复）。 |
| `create_task.py` | Create or register a work task in the shared Claude/Codex task layout. |
| `deploy_hooks.py` | deploy_hooks.py — Hook 部署脚本 |
| `extract_to_memory.py` | extract_to_memory.py — 从工作区日志提取内容到全局记忆 |
| `fix_hardcoded_paths.py` | fix_hardcoded_paths.py — 硬编码路径检测与修复 |
| `generate_catalog.py` | generate_catalog.py — 自动生成各子目录的 README.md（组件目录）。 |
| `generate_project_context.py` | generate_project_context.py — 为项目生成 AI 上下文拼合文件 |
| `governance_pulse.py` | governance_pulse.py — 周期性治理巡检 daemon |
| `init_project.py` | init_project.py — 在 MEMORY.md 活跃项目表中添加一行 |
| `maintain.py` | maintain.py — global-memory harness 的统一控制面入口 |
| `memory_gc.py` | memory_gc.py — global-memory 周期性垃圾回收 |
| `note.py` | note.py — 便利签 CLI。skill 直接调，极省 token。 |
| `panel_api.py` | panel_api.py — 桌面主控台的本地事件 API |
| `post_task_hook.py` | post_task_hook.py — 任务后自动拦截检查 + 同步上传 |
| `route_audit.py` | route_audit.py — 路由行为审计 v2。从真实日志统计 subagent 使用、missed opportunities。 |
| `show_diffs.py` | show_diffs.py — 手动 diff 入口（/diff skill 调用） |
| `smoke_control_panel_exe.py` | smoke_control_panel_exe.py — 打包后主控台 exe 的递归自启冒烟测试 |
| `stage_lib.py` | stage_lib.py — work agent 双轨文档体系 阶段感知共享库（v3.1） |
| `sync_index.py` | sync_index.py — 重建 MEMORY.md 自动索引区 |
| `task_complete.py` | task_complete.py — 任务收尾一键脚本 |
| `task_sync.py` | task_sync.py — 多 Agent 任务同步 CLI |
| `update_readme.py` | update_readme.py — 自动更新仓库 README 的统计数据和更新日志 |
| `update_stats.py` | update_stats.py — 更新 MEMORY.md 的记忆统计区块 |
| `work_context_pack.py` | work_context_pack.py — 把 /work 上下文压缩为短确定性摘要 |

## 上下文治理脚本

| 文件 | 描述 |
|------|------|
| `add_trigger_metadata.py` | add_trigger_metadata.py — Half-automatic trigger frontmatter proposal. |
| `analyze_retrieve_log.py` | analyze_retrieve_log.py — 分析 retrieve_calls.jsonl 产出数据驱动 keyword 建议 |
| `archive_task.py` | archive_task.py — 三模式归档辅助 (P8) |
| `assurance_gate.py` | assurance_gate.py — read-only completion gates for task/harness work. |
| `check_capability_manifest.py` | Validate harness/capability_manifest.json. |
| `check_client_manifest.py` | Validate client support scope and external claim policy. |
| `check_hook_alignment.py` | check_hook_alignment.py — compare hook source-of-truth surfaces. |
| `check_publish_scope.py` | Check tracked files against the publish-scope manifest. |
| `check_trigger_coverage.py` | check_trigger_coverage.py — Verify frontmatter trigger coverage and vocab com... |
| `client_context.py` | Stable context-brief CLI for non-hook clients. |
| `context_meter.py` | context_meter.py — Estimate fixed-context token cost per turn. |
| `export_source_scope.py` | Build a read-only source export plan from the publish-scope manifest. |
| `gate_check.py` | gate_check.py — HARD GATE (P2 → P3) enforcement. |
| `harness_memory_lint.py` | Memory frontmatter linter / compiler. |
| `harness_retrieve.py` | harness_retrieve.py — Context Brief 生成器（方向 B 骨干） |
| `meta_optimize.py` | meta_optimize.py — read-only suggestions for improving the harness. |
| `oss_readiness_check.py` | oss_readiness_check.py — read-only open-source readiness profile. |
| `quality_gate.py` | quality_gate.py — risk-tiered gate for AI-generated code changes. |
| `release_issue_ledger.py` | Render OSS readiness checks as a machine-readable issue ledger. |
| `render_codex_work_skill.py` | render_codex_work_skill.py — generate Codex work skill from Claude work skill. |
| `retrieve_candidate_quality.py` | retrieve_candidate_quality.py — read-only quality report for retrieve pointers. |
| `retrieve_downrank_simulation.py` | retrieve_downrank_simulation.py — replay retrieve queries with candidate down... |
| `retrieve_fallback_candidates.py` | retrieve_fallback_candidates.py - find task-context fallback candidates. |
| `retrieve_fallback_cost.py` | retrieve_fallback_cost.py - summarize task-context fallback runtime cost. |
| `retrieve_optin_compare.py` | retrieve_optin_compare.py — side-by-side default vs opt-in retrieve output. |
| `retrieve_task_context_simulation.py` | retrieve_task_context_simulation.py — simulate task-context fallback for zero... |
| `retrieve_task_context_trial_pack.py` | retrieve_task_context_trial_pack.py — before/after pack for task-scoped fallb... |
| `retrieve_trace.py` | retrieve_trace.py - explain retrieve scoring and task-context fallback. |
| `retrieve_zero_hit_analysis.py` | retrieve_zero_hit_analysis.py — read-only user-query zero-hit report. |
| `scan_dual_storage.py` | scan_dual_storage.py — Detect task docs duplicated across |
| `scan_external_safety.py` | Scan planned external source files for obvious local paths and secrets. |
| `scan_orphan_scripts.py` | scan_orphan_scripts.py — harness/ 孤儿脚本巡检 |
| `self_loop_report.py` | self_loop_report.py - one-screen view of the current self-optimization loop. |
| `test_context_governance.py` | test_context_governance.py — single entry to run all layered tests. |
| `update_phase_status.py` | update_phase_status.py — 一键三同步 Phase 状态。 |
| `view_retrieve_log.py` | view_retrieve_log.py — pretty-print recent retrieve_calls.jsonl entries. |

## Hooks

| 文件 | 描述 |
|------|------|
| `_hook_lib.py` | _hook_lib.py — Claude Code hooks 共享工具库 |
| `_prompt_loader.py` | _prompt_loader.py — hook 提示文案加载器 |
| `_task_resolver.py` | _task_resolver.py — 公共归属解析库 |
| `agent_prompt_gate.py` | PreToolUse Agent hook: subagent prompt 质量门。 |
| `audit_logger.py` | audit_logger.py — PostToolUse hook（异步） |
| `changelog_inject.py` | UserPromptSubmit hook: inject CHANGELOG tail when user mentions pull/sync. |
| `dangerous_command_blocker.py` | dangerous_command_blocker.py — PreToolUse Bash hook |
| `diff_backup.py` | diff_backup.py — PreToolUse(Write|Edit) hook v2 |
| `diff_show.py` | diff_show.py — PostToolUse(Write|Edit) hook：编辑后异步弹 VS Code 三栏 diff 视图。 |
| `doc_gate.py` | spec_gate.py — PreToolUse Write|Edit hook (v3.2 一对一拦截) |
| `memory_file_protector.py` | memory_file_protector.py — PreToolUse Write|Edit hook |
| `memory_lint_gate.py` | memory_lint_gate.py — PreToolUse Write|Edit|MultiEdit hook |
| `quality_gate_stop.py` | Optional Claude Code Stop hook adapter for quality_gate.py. |
| `read_large_file_guard.py` | read_large_file_guard.py — PreToolUse Read hook |
| `retrieve_inject.py` | retrieve_inject.py — UserPromptSubmit hook |
| `route_check.py` | UserPromptSubmit hook: 高置信低耦合场景 nudge + turn_id 生成。 |
| `route_gate.py` | PreToolUse hook (Write|Edit): 阻断未完成路由计划的实现动作。 |
| `statusline.py` | statusline.py — Claude Code statusLine: git branch + context pressure warning. |
| `subagent_logger.py` | subagent_logger.py — SubagentStart hook（异步） |
| `subagent_stop_logger.py` | subagent_stop_logger.py — SubagentStop hook |
| `sync_inject.py` | sync_inject.py — UserPromptSubmit hook for multi-agent task sync. |

## 验证器

| 文件 | 描述 |
|------|------|
| `smoke_test.py` | smoke_test.py — 基础设施冒烟测试 |
| `smoke_test_hooks.py` | smoke_test_hooks.py - Phase 3 MVP: harness hooks 端到端冒烟测试 |
| `verify_all.py` | verify_all.py — 总验证脚本（一键跑所有检查 + 基线对比） |
| `verify_conventions.py` | verify_conventions.py — 跨项目规范硬检查脚本 |
| `verify_doc_drift.py` | verify_doc_drift.py - Phase 2-B: 文档与实现漂移扫描 |
| `verify_docs.py` | verify_docs.py — 文档一致性检查 |
| `verify_memory.py` | verify_memory.py — 记忆仓库健康检查脚本 |
| `verify_output_contracts.py` | Verify CLI output contracts for harness scripts. |
| `verify_prompt_system.py` | verify_prompt_system.py — Prompt 系统一致性检查 |
| `verify_workflow.py` | verify_workflow.py — 流程校验脚本 |

## 健康检查

| 文件 | 描述 |
|------|------|
| `changelog_drift.py` | 检测「改记忆当场记 CHANGELOG」铁律是否生效。 |
| `ghost_refs.py` | 扫描关键文档中提到的本地文件引用，验证文件实际存在。 |
| `invocation_freq.py` | harness_tool_invocations.jsonl 7 天调用排行 + 找零调用脚本。 |
| `knowledge_unread.py` | knowledge/*.md 顶层文件 access_count=0 计数。 |
| `lint_failure_rate.py` | lint_failure_rate.py — memory_lint_gate.jsonl 7d 失败率检查。 |
| `log_liveness.py` | 复用 log_health.scan() 输出，把 STALE/DEAD 提为 signal。 |
| `memory_usage.py` | MEMORY.md 文件数 / 80 上限。 |
| `retrieve_hitrate.py` | retrieve_hitrate.py — retrieve_calls.jsonl 命中质量周期检查。 |
| `retrieve_pointer_consumption.py` | retrieve_pointer_consumption.py — retrieve 真消费率 7d 趋势检查。 |
| `sync_failures.py` | 扫 maintain.jsonl 最近条目，区分 user_wip 跳过 vs 真失败。 |
| `traffic_imbalance.py` | skills 投入（行数）vs 产出（7 天调用次数）比例。 |
| `wip_age.py` | git status dirty 文件计数 + 最老未提交文件年龄。 |

> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。
