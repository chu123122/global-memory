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
- [memory-rules.md](memory-rules.md) — 记忆写入完整规则（CLAUDE.md 摘要的展开）
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

<!-- AUTO-INDEX:BEGIN — 由 sync_index.py 维护，勿手动编辑 -->

## Feedback（行为纠正）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [feedback_code_style.md](feedback/feedback_code_style.md) | 代码风格偏好记录，包括命名约定、缩进、注释风格等 | 2026-04-14 |
| [feedback_infra_ops_windows.md](feedback/feedback_infra_ops_windows.md) | junction 创建方式 + 删 hook 引用目录的原子化要求（避免自锁） | 2026-04-20 |
| [feedback_output_format.md](feedback/feedback_output_format.md) | 输出格式要求，包括代码块、折叠、表格等偏好 | 2026-04-14 |

## Knowledge（知识积累）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [knowledge_cpp_multithreading.md](knowledge/knowledge_cpp_multithreading.md) | C++ 多线程/并发编程知识积累（当前最高优先级短板） | 2026-04-13 |
| [knowledge_cpp_pitfalls.md](knowledge/knowledge_cpp_pitfalls.md) | C++ 常见陷阱，包括智能指针/RAII/模板/移动语义/链接性/前置声明析构等 | 2026-04-20 |
| [knowledge_lua_patterns.md](knowledge/knowledge_lua_patterns.md) | Lua 编程模式和最佳实践，UE 业务层开发经验 | 2026-04-13 |
| [knowledge_skill_design.md](knowledge/knowledge_skill_design.md) | Skill 设计经验，包括结构规范、防过拟合、Few-shot 积累 | 2026-04-13 |
| [knowledge_system_design.md](knowledge/knowledge_system_design.md) | 系统设计表达方法论+万能框架+练习记录（面试最大短板改进） | 2026-04-14 |
| [knowledge_ue_internals.md](knowledge/knowledge_ue_internals.md) | UE 引擎底层知识，包括 TaskGraph/线程模型/UObject/Pak VFS | 2026-04-20 |
| [knowledge_unity_dots.md](knowledge/knowledge_unity_dots.md) | Unity DOTS/ECS 架构经验，Archetype/Chunk/SOA/Burst+JobSystem | 2026-04-13 |
| [knowledge_windows_dev_env.md](knowledge/knowledge_windows_dev_env.md) | Windows 开发环境踩坑记录，覆盖 Git Bash/MSYS 路径、软链、CRLF 等差异 | 2026-04-21 |

## Fixes（修复经验）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [fixes_android_apk_build.md](fixes/fixes_android_apk_build.md) | UE 4.26.2 + Git Bash 下 Android APK 打包的兼容性修复记录 | 2026-04-21 |
| [fixes_common_build_errors.md](fixes/fixes_common_build_errors.md) | 常见构建错误的解决方案积累 | 2026-04-01 |

## Decisions（架构决策）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [conventions.md](decisions/conventions.md) | 跨项目开发规范，从实际项目中提炼，含硬检查标注 | 2026-04-15 |
| [decision_work_mode_workflow.md](decisions/decision_work_mode_workflow.md) | /work skill 作为工作流程统一入口的架构决策与边界说明 | 2026-04-21 |

## Interview（面试专用）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [autumn-positioning-2026-04-17.md](interview/autumn-positioning-2026-04-17.md) | 秋招定位澄清 + UE 对标研究入口 + 写作输出方向 | 2026-04-17 |
| [career-strategy-2027.md](interview/career-strategy-2027.md) | 2027届秋招全盘策略 + 5年职业路径推演 | 2026-04-14 |
| [interview_mock_history.md](interview/interview_mock_history.md) | 模拟面试记录与评分 | 2026-04-14 |
| [interview_question_bank.md](interview/interview_question_bank.md) | 面试真题积累，按方向分类（含心动二面完整记录 + 米哈游 140 题模拟题库） | 2026-04-14 |
| [interview_weakness_tracker.md](interview/interview_weakness_tracker.md) | 面试弱项追踪，记录每次面试暴露的短板和改进进度 | 2026-04-01 |
| [resume-versions.md](interview/resume-versions.md) | 简历定稿版（引擎版+客户端版），面试前 review 用 | 2026-04-14 |

## 记忆统计
- 总文件数：53 / 50（上限）
- 最后维护时间：2026-04-21
- 下次清理时间：（30 天后自动提醒）
<!-- AUTO-INDEX:END -->
