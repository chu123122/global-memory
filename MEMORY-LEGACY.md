# 全局记忆索引

> 此文件始终参考。根据当前任务选择性读取具体文件。
> **新对话启动时：先读此文件 → 和用户核对当前项目进度 → 确认后再动手。**

## 🔥 当前活跃项目（新 AI 先看这里）

| 项目 | 仓库 | 分支 | 进度 | 交接文档 |
|------|------|------|------|---------|
| **博客重设计** | [blog](https://github.com/chu123122/blog.git) | `redesign-astro` | Phase 5 进行中（CF Pages 部署待确认），已添加页脚音乐播放器 | `docs/HANDOFF.md` ★必读 |
| **帧同步 v2** | [LockStepSystem](https://github.com/chu123122/LockStepSystem.git) | `feature/v2-rollback-rudp` | Phase 1-4 代码完成，待 Unity 验证 | `docs/PROGRESS.md` + `docs/HARNESS_REVIEW.md` |

> 接手任何项目前，**先读对应的交接文档**，再和用户确认"上次做到哪了"。

## 📌 系统规则与索引
- [MEMORY-RULES.md](docs/spec/MEMORY-RULES.md) — 记忆写入完整规则（CLAUDE.md 摘要的展开）
- [FIXLIST.md](FIXLIST.md) — 当前已知问题清单（含已关 / 未关混排）
- [knowledge/docs/INDEX.md](knowledge/docs/INDEX.md) — 30 篇深度文档总索引（C++ / UE / 面试 / 工程）
- [knowledge/references/search-engines.md](knowledge/references/search-engines.md) — 搜索引擎速查表

## 🏗️ 项目文档（global-memory/projects/）
- [xindong-engine/SPEC.md](projects/xindong-engine/SPEC.md) — 心动入职任务规格（Android APK 打包）
- [xindong-engine/dev-map.md](projects/xindong-engine/dev-map.md) — 开发地图
- [xindong-engine/onboarding-plan.md](projects/xindong-engine/onboarding-plan.md) — 入职 onboarding 计划
- [xindong-engine/task-board.md](projects/xindong-engine/task-board.md) — 任务看板

## 📜 复盘记录（global-memory/retrospectives/）
- [retro_2026-04-14_blog-music-player.md](retrospectives/retro_2026-04-14_blog-music-player.md) — 博客页脚音乐播放器复盘

## 📋 任务文档（global-memory/tasks/）
- [bepinex-generic-multiplayer-framework.md](tasks/bepinex-generic-multiplayer-framework.md) — 通用 Unity 单机游戏联机 Mod 框架构想（BepInEx + Harmony + Mono 反射）

<!-- AUTO-INDEX:BEGIN — 由 sync_index.py 维护，勿手动编辑 -->

## Feedback（行为纠正）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [feedback_ai_summary_drift.md](feedback/feedback_ai_summary_drift.md) | AI 摘要文档不可作为 ground truth — L3 落地前强制原文复核 | 2026-05-11 |
| [feedback_code_style.md](feedback/feedback_code_style.md) | 代码风格偏好 | 2026-04-14 |
| [feedback_collaboration_meta.md](feedback/feedback_collaboration_meta.md) | 协作元偏好 | 2026-04-24 |
| [feedback_compile_after_module_change.md](feedback/feedback_compile_after_module_change.md) | feedback_compile_after_module_change | 2026-04-24 |
| [feedback_diff_workflow.md](feedback/feedback_diff_workflow.md) | Diff 工作流（B 协议）+ 全局白名单 hook | 2026-04-24 |
| [feedback_harness_maintenance_flow.md](feedback/feedback_harness_maintenance_flow.md) | 新加 harness 脚本必走 5 步入维护流程，否则没人知道脚本存在 | 2026-05-20 |
| [feedback_infra_ops_windows.md](feedback/feedback_infra_ops_windows.md) | Windows 基础设施操作铁律 | 2026-04-24 |
| [feedback_learning_path.md](feedback/feedback_learning_path.md) | 学习模式教学路径偏好 | 2026-05-11 |
| [feedback_no_speculative_semantics_in_comments.md](feedback/feedback_no_speculative_semantics_in_comments.md) | feedback_no_speculative_semantics_in_comments | 2026-05-11 |
| [feedback_output_format.md](feedback/feedback_output_format.md) | 输出格式要求 | 2026-04-24 |
| [feedback_p4_checkpoint_per_stage.md](feedback/feedback_p4_checkpoint_per_stage.md) | feedback_p4_checkpoint_per_stage | 2026-04-24 |
| [feedback_skill_deployment_layout.md](feedback/feedback_skill_deployment_layout.md) | Skill 部署布局约定 | 2026-05-11 |
| [feedback_visual_aesthetic.md](feedback/feedback_visual_aesthetic.md) | 视觉美学偏好 | 2026-04-24 |
| [feedback_work_skill_doc_only_tasks.md](feedback/feedback_work_skill_doc_only_tasks.md) | /work Step 4 跑 task_complete.py 的适用条件 | 2026-04-24 |

## Knowledge（知识积累）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [knowledge_cpp_multithreading.md](knowledge/knowledge_cpp_multithreading.md) | C++ 多线程/并发编程 | 2026-04-22 |
| [knowledge_cpp_pitfalls.md](knowledge/knowledge_cpp_pitfalls.md) | C++ 常见陷阱 | 2026-04-20 |
| [knowledge_lua_patterns.md](knowledge/knowledge_lua_patterns.md) | Lua 编程模式 | 2026-04-13 |
| [knowledge_qt_pyside_styling.md](knowledge/knowledge_qt_pyside_styling.md) | Qt/PySide6 样式系统盲区 | 2026-04-24 |
| [knowledge_skill_design.md](knowledge/knowledge_skill_design.md) | Skill 设计经验 | 2026-04-13 |
| [knowledge_system_design.md](knowledge/knowledge_system_design.md) | 系统设计表达方法论 | 2026-04-14 |
| [knowledge_ue_internals.md](knowledge/knowledge_ue_internals.md) | UE 引擎底层 | 2026-05-11 |
| [knowledge_unity_dots.md](knowledge/knowledge_unity_dots.md) | Unity DOTS/ECS 架构经验 | 2026-04-13 |
| [knowledge_windows_dev_env.md](knowledge/knowledge_windows_dev_env.md) | Windows 开发环境踩坑记录 | 2026-04-21 |

## Fixes（修复经验）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [fix_retrieve_cache_tmp_path_leak.md](fixes/fix_retrieve_cache_tmp_path_leak.md) | harness_retrieve cache 全局共享导致 tmp-path 残留泄漏到生产 dry-run | 2026-05-20 |
| [fixes_common_build_errors.md](fixes/fixes_common_build_errors.md) | 常见构建错误 | 2026-04-01 |
| [fixes_shader_code_library_missing.md](fixes/fixes_shader_code_library_missing.md) | ShaderCodeLibrary::InitForRuntime 闪退修复 | 2026-04-22 |

## Interview（面试专用）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [autumn-positioning-2026-04-17.md](interview/autumn-positioning-2026-04-17.md) | 秋招定位澄清 + UE 对标研究入口 + 写作输出方向 | 2026-04-17 |
| [career-strategy-2027.md](interview/career-strategy-2027.md) | 2027届秋招全盘策略 + 5年职业路径推演 | 2026-04-14 |
| [interview_mock_history.md](interview/interview_mock_history.md) | 模拟面试记录与评分 | 2026-04-14 |
| [interview_question_bank.md](interview/interview_question_bank.md) | 面试真题积累，按方向分类（含心动二面完整记录 + 米哈游 140 题模拟题库） | 2026-04-14 |
| [interview_weakness_tracker.md](interview/interview_weakness_tracker.md) | 面试弱项追踪，记录每次面试暴露的短板和改进进度 | 2026-04-01 |
| [resume-versions.md](interview/resume-versions.md) | 简历定稿版（引擎版+客户端版），面试前 review 用 | 2026-04-14 |

## Decisions（架构决策）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [conventions.md](decisions/conventions.md) | 跨项目开发规范，从实际项目中提炼，含硬检查标注 | 2026-04-15 |
| [decision_work_mode_workflow.md](decisions/decision_work_mode_workflow.md) | /work skill 作为工作流程统一入口的架构决策与边界说明 | 2026-04-21 |

## 记忆统计
- 总文件数：67 / 80（上限）
- 最后维护时间：2026-05-20
- 下次清理时间：（30 天后自动提醒）
<!-- AUTO-INDEX:END -->
