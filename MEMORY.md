# 全局记忆索引

> 此文件始终参考。根据当前任务选择性读取具体文件。
> **新对话启动时：先读此文件 → 和用户核对当前项目进度 → 确认后再动手。**

## 🔥 当前活跃项目（新 AI 先看这里）

| 项目 | 仓库 | 分支 | 进度 | 交接文档 |
|------|------|------|------|---------|
| **博客重设计** | [blog](https://github.com/chu123122/blog.git) | `redesign-astro` | SPEC+HANDOFF 已完成，Astro 项目未初始化 | `docs/HANDOFF.md` ★必读 |
| **帧同步 v2** | [LockStepSystem](https://github.com/chu123122/LockStepSystem.git) | `feature/v2-rollback-rudp` | Phase 1-4 代码完成，待 Unity 验证 | `docs/PROGRESS.md` + `docs/HARNESS_REVIEW.md` |

> 接手任何项目前，**先读对应的交接文档**，再和用户确认"上次做到哪了"。




## Feedback（行为纠正）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [feedback_code_style.md](feedback/feedback_code_style.md) | 代码风格偏好记录，包括命名约定、缩进、注释风格等 | 2026-04-01 |
| [feedback_output_format.md](feedback/feedback_output_format.md) | 输出格式要求，包括代码块、折叠、表格等偏好 | 2026-04-01 |

## Knowledge（知识积累）

> **读取策略**：先看 summary 判断是否需要深入读取。summary 是该 Topic 的核心状态一句话概括。

| 文件 | summary（一句话状态） | 更新时间 |
|------|----------------------|---------|
| [knowledge_cpp_multithreading.md](knowledge/knowledge_cpp_multithreading.md) | ⚡最高优先级短板；UE关联已记录(FCriticalSection/FEvent/TAtomic/TaskGraph)；已掌握部分待填 | 2026-04-01 |
| [knowledge_cpp_pitfalls.md](knowledge/knowledge_cpp_pitfalls.md) | shared_ptr循环引用/make_shared/移动语义已记录；RAII/模板待填 | 2026-04-01 |
| [knowledge_lua_patterns.md](knowledge/knowledge_lua_patterns.md) | 框架已建，内容待实习中积累 | 2026-04-01 |
| [knowledge_skill_design.md](knowledge/knowledge_skill_design.md) | 结构规范+防过拟合+版本管理已定义 | 2026-04-01 |
| [knowledge_system_design.md](knowledge/knowledge_system_design.md) | 四步法(拆模块→定数据→画交互→走流程)+表达要点已定义；练习记录待填 | 2026-04-01 |
| [knowledge_ue_internals.md](knowledge/knowledge_ue_internals.md) | 实习经验已记录(Pak/模块依赖/资源管线/Git工具链)；源码/线程模型/UObject待学 | 2026-04-01 |
| [knowledge_unity_dots.md](knowledge/knowledge_unity_dots.md) | Archetype/Burst/四维性能分析已掌握；PBD+FlowField+Boids项目实践已记录 | 2026-04-01 |

### 深度文档（快照型，不持续更新）

> ⚠️ 以下文档是 2026-04-13 一次性生成的参考快照。**最新知识以上方 Topic 文件为准**。两者矛盾时以 Topic 为准。

| 文件 | 行数 | 内容 |
|------|:----:|------|
| [ue-engine-internals-guide.md](knowledge/docs/ue-engine-internals-guide.md) | 853 | UE 十大核心模块 + 面试题 |
| [cpp-multithreading-guide.md](knowledge/docs/cpp-multithreading-guide.md) | 755 | 五章系统学习 + 30 道面试题 |
| [prompt-engineering-system.md](knowledge/docs/prompt-engineering-system.md) | 504 | 8 场景模板 + 6 阶段 SOP |
| [interview-deep-dive-chains.md](knowledge/docs/interview-deep-dive-chains.md) | 269 | 12 知识点 × 3-5 层追问链 |
| [project-interview-scripts.md](knowledge/docs/project-interview-scripts.md) | 172 | 4 项目面试话术 |
| [code-review-and-blog-templates.md](knowledge/docs/code-review-and-blog-templates.md) | 198 | Code Review 清单 + 5 博客模板 |

### 参考文档

| 文件 | 说明 |
|------|------|
| [search-engines.md](knowledge/references/search-engines.md) | 17 个搜索引擎 URL 模板（原 multi-search-engine Skill 下沉） |

## Fixes（修复经验）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [fixes_common_build_errors.md](fixes/fixes_common_build_errors.md) | 常见构建错误的解决方案积累 | 2026-04-01 |

## Decisions（架构决策）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [conventions.md](decisions/conventions.md) | 跨项目开发规范，从实际项目中提炼，含硬检查标注 | 2026-04-13 |

## Interview（面试专用）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [interview_mock_history.md](interview/interview_mock_history.md) | 模拟面试记录与评分 | 2026-04-01 |
| [interview_question_bank.md](interview/interview_question_bank.md) | 面试真题积累，按方向分类 | 2026-04-01 |
| [interview_weakness_tracker.md](interview/interview_weakness_tracker.md) | 面试弱项追踪，记录每次面试暴露的短板和改进进度 | 2026-04-01 |

## 记忆统计
- 总文件数：28 / 50（上限）
- 最后维护时间：2026-04-13
- 下次清理时间：（30 天后自动提醒）