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
<<<<<<< Updated upstream
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [knowledge_cpp_multithreading.md](knowledge/knowledge_cpp_multithreading.md) | C++ 多线程/并发编程知识积累（当前最高优先级短板） | 2026-04-13 |
| [knowledge_cpp_pitfalls.md](knowledge/knowledge_cpp_pitfalls.md) | C++ 常见陷阱，包括智能指针/RAII/模板/移动语义等 | 2026-04-13 |
| [knowledge_lua_patterns.md](knowledge/knowledge_lua_patterns.md) | Lua 编程模式和最佳实践，UE 业务层开发经验 | 2026-04-13 |
| [knowledge_skill_design.md](knowledge/knowledge_skill_design.md) | Skill 设计经验，包括结构规范、防过拟合、Few-shot 积累 | 2026-04-13 |
| [knowledge_system_design.md](knowledge/knowledge_system_design.md) | 系统设计表达方法论，四步法训练记录 | 2026-04-13 |
| [knowledge_ue_internals.md](knowledge/knowledge_ue_internals.md) | UE 引擎底层知识，包括 TaskGraph/线程模型/UObject/Pak VFS | 2026-04-13 |
| [knowledge_unity_dots.md](knowledge/knowledge_unity_dots.md) | Unity DOTS/ECS 架构经验，Archetype/Chunk/SOA/Burst+JobSystem | 2026-04-13 |
=======

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
| [async-resource-loading-preresearch.md](knowledge/docs/async-resource-loading-preresearch.md) | 692 | 多线程资源加载预研（3 方案对比，推荐方案 C Wrapper） |
| [interview-cheatsheet.md](knowledge/docs/interview-cheatsheet.md) | 118 | 面试速查卡（UE 10 模块 + C++ 多线程一句话速记） |
| [game-physics-reference.md](knowledge/docs/game-physics-reference.md) | — | 物理模拟技术参考（PBD/XPBD/赛车物理 + GDC 演讲） |
| [game-networking-reference.md](knowledge/docs/game-networking-reference.md) | — | 网络同步技术参考（帧同步/RUDP/GGPO + 行业方案） |
| [ue5-async-loading-reference.md](knowledge/docs/ue5-async-loading-reference.md) | — | UE5 异步加载最新实践参考 |
| [interview-trends-2025-2026.md](knowledge/docs/interview-trends-2025-2026.md) | — | 2025-2026 游戏客户端面试趋势 |
| [xindong-tech-intel.md](knowledge/docs/xindong-tech-intel.md) | — | 心动技术情报（引擎中台相关） |
| [harness-engineering-2026.md](knowledge/docs/harness-engineering-2026.md) | — | Harness 工程 2026 最新实践 |
| [ue-source-deep-dive.md](knowledge/docs/ue-source-deep-dive.md) | ~500 | **UE 8 大模块源码级参考**（反射/GC/Subsystem/Delegate/TaskGraph/Timer/资源管理，48 篇文章交叉验证） |
| [cpp-memory-model-lockfree.md](knowledge/docs/cpp-memory-model-lockfree.md) | ~300 | **C++ 内存模型+无锁编程**（6 种 memory_order/CAS/无锁栈/自旋读写锁+代码+性能测试） |
| [resource-links.md](knowledge/docs/resource-links.md) | ~200 | 48 篇技术资料链接索引（9 大类，每类标 ★ 最佳入口） |
| [gdc-must-watch.md](knowledge/docs/gdc-must-watch.md) | ~230 | **GDC 必看演讲清单**（28 演讲 × 7 方向，入门→进阶→高级分层，面试速查 + 8 周学习路线） |
| [ai-impact-game-dev.md](knowledge/docs/ai-impact-game-dev.md) | ~200 | **AI 对游戏程序员的影响推演**（替代风险排序/值钱能力/独立开发门槛/10 年建议） |
| [learning-methodology.md](knowledge/docs/learning-methodology.md) | ~250 | **学习方法论：AESR 四步法**（诊断/框架/间隔重复/周计划/AI Agent 配置） |

### 参考文档

| 文件 | 说明 |
|------|------|
| [search-engines.md](knowledge/references/search-engines.md) | 17 个搜索引擎 URL 模板（原 multi-search-engine Skill 下沉） |
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
| [FIXLIST.md](FIXLIST.md) | CLI 适配问题清单（3P0+5P1+4P2），供 Opus 明天修复 | 2026-04-14 |
=======
| [xindong-engine/dev-map.md](projects/xindong-engine/dev-map.md) | 心动引擎中台项目导航（入职后填充） | 2026-04-13 |
| [xindong-engine/task-board.md](projects/xindong-engine/task-board.md) | 心动引擎中台任务看板（当前：多线程资源加载插件） | 2026-04-13 |
| [xindong-engine/onboarding-plan.md](projects/xindong-engine/onboarding-plan.md) | **★ 入职过渡 + 生活优化方案**（时间分配/两周清单/运动/作息/心理预期） | 2026-04-13 |
>>>>>>> Stashed changes

## Interview（面试专用）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [interview_mock_history.md](interview/interview_mock_history.md) | 模拟面试记录与评分 | 2026-04-01 |
| [interview_question_bank.md](interview/interview_question_bank.md) | 面试真题积累，按方向分类 | 2026-04-01 |
| [interview_weakness_tracker.md](interview/interview_weakness_tracker.md) | 面试弱项追踪，记录每次面试暴露的短板和改进进度 | 2026-04-01 |
| [career-strategy-2027.md](interview/career-strategy-2027.md) | **★ 2027 届秋招全盘策略 + 5 年路径推演**（时间线/公司分级/简历/优先级/风险） | 2026-04-13 |

## Test Reports（测试报告）
| 文件 | 描述 | 更新时间 |
|------|------|---------|
| [smoke-2026-04-14-night.md](test-reports/smoke-2026-04-14-night.md) | 夜间冒烟：verify_memory 12P/1W、verify_prompt 17P、skill_regression 0P/5F(P1-9) | 2026-04-14 |

## 记忆统计
<<<<<<< Updated upstream
- 总文件数：31 / 50（上限）
- 最后维护时间：2026-04-14
=======
- 总文件数：41 / 50（上限）
- 最后维护时间：2026-04-13
>>>>>>> Stashed changes
- 下次清理时间：（30 天后自动提醒）