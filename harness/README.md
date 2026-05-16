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
| `control_panel_pyside_launch.py` | PyInstaller 入口 wrapper（v2.1 R4-a 修复）。 |
| `deploy_hooks.py` | deploy_hooks.py — Hook 部署脚本 |
| `extract_to_memory.py` | extract_to_memory.py — 从工作区日志提取内容到全局记忆 |
| `fix_hardcoded_paths.py` | fix_hardcoded_paths.py — 硬编码路径检测与修复 |
| `generate_catalog.py` | generate_catalog.py — 自动生成各子目录的 README.md（组件目录）。 |
| `generate_project_context.py` | generate_project_context.py — 为项目生成 AI 上下文拼合文件 |
| `init_project.py` | init_project.py — 在 MEMORY.md 活跃项目表中添加一行 |
| `maintain.py` | maintain.py — global-memory harness 的统一控制面入口 |
| `memory_gc.py` | memory_gc.py — global-memory 周期性垃圾回收 |
| `panel_api.py` | panel_api.py — 桌面主控台的本地事件 API |
| `post_task_hook.py` | post_task_hook.py — 任务后自动拦截检查 + 同步上传 |
| `show_diffs.py` | show_diffs.py — 手动 diff 入口（/diff skill 调用） |
| `smoke_control_panel_exe.py` | smoke_control_panel_exe.py — 打包后主控台 exe 的递归自启冒烟测试 |
| `stage_lib.py` | stage_lib.py — work agent 双轨文档体系 阶段感知共享库（v3.1） |
| `sync_index.py` | sync_index.py — 重建 MEMORY.md 自动索引区 |
| `task_complete.py` | task_complete.py — 任务收尾一键脚本 |
| `task_sync.py` | task_sync.py — 多 Agent 任务同步 CLI |
| `update_readme.py` | update_readme.py — 自动更新仓库 README 的统计数据和更新日志 |
| `update_stats.py` | update_stats.py — 更新 MEMORY.md 的记忆统计区块 |
| `work_context_pack.py` | work_context_pack.py — 把 /work 上下文压缩为短确定性摘要 |

## Hooks

| 文件 | 描述 |
|------|------|
| `_hook_lib.py` | _hook_lib.py — Claude Code hooks 共享工具库 |
| `_prompt_loader.py` | _prompt_loader.py — hook 提示文案加载器 |
| `_task_resolver.py` | _task_resolver.py — 公共归属解析库 |
| `audit_logger.py` | audit_logger.py — PostToolUse hook（异步） |
| `changelog_inject.py` | UserPromptSubmit hook: inject CHANGELOG tail when user mentions pull/sync. |
| `dangerous_command_blocker.py` | dangerous_command_blocker.py — PreToolUse Bash hook |
| `diff_backup.py` | diff_backup.py — PreToolUse(Write|Edit) hook v2 |
| `diff_show.py` | diff_show.py — PostToolUse(Write|Edit) hook：编辑后异步弹 VS Code 三栏 diff 视图。 |
| `doc_gate.py` | spec_gate.py — PreToolUse Write|Edit hook (v3.2 一对一拦截) |
| `memory_file_protector.py` | memory_file_protector.py — PreToolUse Write|Edit hook |
| `read_large_file_guard.py` | read_large_file_guard.py — PreToolUse Read hook |
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
| `log_liveness.py` | 复用 log_health.scan() 输出，把 STALE/DEAD 提为 signal。 |
| `memory_usage.py` | MEMORY.md 文件数 / 80 上限。 |
| `sync_failures.py` | 扫 maintain.jsonl 最近条目，区分 user_wip 跳过 vs 真失败。 |
| `traffic_imbalance.py` | skills 投入（行数）vs 产出（7 天调用次数）比例。 |
| `wip_age.py` | git status dirty 文件计数 + 最老未提交文件年龄。 |

> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。
