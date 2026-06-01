# Skills 目录

| Skill | 描述 |
|-------|------|
| **bug-locator** | 系统化 Bug 调查流程 — 复现、二分、根因、修复、验证。用于定位 bug、调试崩溃、排查异常行为（快速修复失败 2 次以上时使用）。 |
| **check** | 设计阶段审查。读 project_registry.json 定位任务文档目录，派独立 design-reviewer subagent（只读，opus），把结构化审查报告写到 REVIEW-<... |
| **cpp-tutor** | 苏格拉底式 C++ 教学，覆盖多线程、模板、内存模型和现代 C++ 模式。用于学习或练习 C++ 概念，尤其是并发和无锁编程等弱项。 |
| **diff** | 待编辑文件交互选择器。列出 <task>/.diff/now/ 中的文件为编号选项，等用户选择后打开 VS Code diff 视图并归档。 |
| **learn** | 学习模式入口。对话中切换到 learning-agent 行为：读 agent 配置 → 核对上次学到哪 → 检查弱项 → 按子模式（C++/UE/渲染/系统设计/面试/算法/简历/个人项目）分... |
| **migrate-executor** | 代码和资源迁移执行器 — 依赖分析、迁移计划、逐步执行。 |
| **skill-auditor** | Skill 结构合规检查。验证文件完整性、渐进隔离分层。 |
| **skill-creator** | Create new skills, modify and improve existing skills, and measure skill performance. Use when us... |
| **skill-reviewer** | 代码和输出质量审查。审查 agent 产出的代码、文档和配置的正确性。 |
| **smoke-test** | 基础设施冒烟测试。按硬编码清单 subprocess 执行 harness 基础设施脚本（verify/sync/hooks 等）， |
| **work** | 任务治理模式。新任务一律 task_template（5 子目录 core/design/ops/test/_archive），老任务保留平铺兼容。Use when 用户打 /work 进入正式... |

> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。
