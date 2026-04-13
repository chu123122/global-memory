# 全局记忆索引

> 此文件始终参考。根据当前任务选择性读取具体文件。
> **新对话启动时：先读此文件 → 和用户核对当前项目进度 → 确认后再动手。**

## 🔥 当前活跃项目（新 AI 先看这里）

| 项目 | 仓库 | 分支 | 进度 | 交接文档 |
|------|------|------|------|---------|
| **博客重设计** | [blog](https://github.com/chu123122/blog.git) | `redesign-astro` | Phase 5 进行中（CF Pages 部署待确认），已添加页脚音乐播放器 | `docs/HANDOFF.md` ★必读 |
| **帧同步 v2** | [LockStepSystem](https://github.com/chu123122/LockStepSystem.git) | `feature/v2-rollback-rudp` | Phase 1-4 代码完成，待 Unity 验证 | `docs/PROGRESS.md` + `docs/HARNESS_REVIEW.md` |

> 接手任何项目前，**先读对应的交接文档**，再和用户确认"上次做到哪了"。







## Feedback（行为纠正）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [feedback_code_style.md](feedback/feedback_code_style.md) | 代码风格偏好记录，包括命名约定、缩进、注释风格等 | 2026-04-01 |
| [feedback_output_format.md](feedback/feedback_output_format.md) | 输出格式要求，包括代码块、折叠、表格等偏好 | 2026-04-01 |

## Knowledge（知识积累）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [knowledge_cpp_multithreading.md](knowledge/knowledge_cpp_multithreading.md) | C++ 多线程/并发编程知识积累（当前最高优先级短板） | 2026-04-13 |
| [knowledge_cpp_pitfalls.md](knowledge/knowledge_cpp_pitfalls.md) | C++ 常见陷阱，包括智能指针/RAII/模板/移动语义等 | 2026-04-13 |
| [knowledge_lua_patterns.md](knowledge/knowledge_lua_patterns.md) | Lua 编程模式和最佳实践，UE 业务层开发经验 | 2026-04-13 |
| [knowledge_skill_design.md](knowledge/knowledge_skill_design.md) | Skill 设计经验，包括结构规范、防过拟合、Few-shot 积累 | 2026-04-13 |
| [knowledge_system_design.md](knowledge/knowledge_system_design.md) | 系统设计表达方法论，四步法训练记录 | 2026-04-13 |
| [knowledge_ue_internals.md](knowledge/knowledge_ue_internals.md) | UE 引擎底层知识，包括 TaskGraph/线程模型/UObject/Pak VFS | 2026-04-13 |
| [knowledge_unity_dots.md](knowledge/knowledge_unity_dots.md) | Unity DOTS/ECS 架构经验，Archetype/Chunk/SOA/Burst+JobSystem | 2026-04-13 |

## Fixes（修复经验）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [fixes_common_build_errors.md](fixes/fixes_common_build_errors.md) | 常见构建错误的解决方案积累 | 2026-04-01 |

## Decisions（架构决策）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [conventions.md](decisions/conventions.md) | 跨项目开发规范，从实际项目中提炼，含硬检查标注 | 2026-04-13 |

## Retrospectives（流程复盘）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [retro_2026-04-14_blog-music-player.md](retrospectives/retro_2026-04-14_blog-music-player.md) | 博客页脚音乐播放器开发复盘，真实流程 vs 规范流程对照，整体评分 2/5 | 2026-04-14 |

## 待修复（CLI 迁移）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [FIXLIST.md](FIXLIST.md) | CLI 适配问题清单（3P0+5P1+4P2），供 Opus 明天修复 | 2026-04-14 |

## Interview（面试专用）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [interview_mock_history.md](interview/interview_mock_history.md) | 模拟面试记录与评分 | 2026-04-01 |
| [interview_question_bank.md](interview/interview_question_bank.md) | 面试真题积累，按方向分类 | 2026-04-01 |
| [interview_weakness_tracker.md](interview/interview_weakness_tracker.md) | 面试弱项追踪，记录每次面试暴露的短板和改进进度 | 2026-04-01 |

## Test Reports（测试报告）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [smoke-2026-04-14-night.md](test-reports/smoke-2026-04-14-night.md) | 夜间冒烟：verify_memory 12P/1W、verify_prompt 17P、skill_regression 0P/5F(P1-9) | 2026-04-14 |

## 记忆统计
- 总文件数：31 / 50（上限）
- 最后维护时间：2026-04-14
- 下次清理时间：（30 天后自动提醒）