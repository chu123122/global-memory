# Skills 目录

| Skill | 描述 |
|-------|------|
| **bug-locator** | 系统化 Bug 调查流程 — 复现、二分、根因、修复、验证。用于定位 bug、调试崩溃、排查异常行为（快速修复失败 2 次以上时使用）。 |
| **check** | 设计阶段审查。读 project_registry.json 定位任务文档目录，派独立 design-reviewer subagent（只读，opus），把结构化审查报告写到 REVIEW-<... |
| **cpp-tutor** | 苏格拉底式 C++ 教学，覆盖多线程、模板、内存模型和现代 C++ 模式。用于学习或练习 C++ 概念，尤其是并发和无锁编程等弱项。 |
| **diff** | 待编辑文件交互选择器。列出 <task>/.diff/now/ 中的文件为编号选项，等用户选择后打开 VS Code diff 视图并归档。 |
| **document-structure-restorer** | 文档结构重建器。用于处理被反复追加、打补丁、插入碎片、重复说明或层级混乱破坏的 Markdown/文档/设计说明/架构说明；当用户想把混乱文档重新整理成完整、稳定、适合 AI 阅读和人类维护的结... |
| **learn** | 学习模式入口。对话中切换到 learning-agent 行为：读 agent 配置 → 核对上次学到哪 → 检查弱项 → 按子模式（C++/UE/渲染/系统设计/面试/算法/简历/个人项目）分... |
| **skill-auditor** | Skill 结构合规检查。验证文件完整性、渐进隔离分层。 |
| **triage** | 轻量问题消化流程。Use when 用户打 /triage，或想周期性处理 issues、feedback、归档候选、health warning 等 inbox；AI 先扫描并提案，用户确认“... |
| **work** | 任务治理模式。新任务一律 task_template（core/design/ops/test 4 工作子目录 + _archive 归档），老任务保留平铺兼容。Use when 用户打 /wo... |

> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。
