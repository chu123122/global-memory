# Agents 目录

| Agent | 描述 |
|-------|------|
| **bounded-worker** | Use proactively for mechanical code edits with explicit file scope and clear target change: batch... |
| **CLAUDE** | （见 CLAUDE.md） |
| **code-reviewer** | Use proactively after multi-file edits (3 or more files changed), or when changes touch hooks, CL... |
| **design-reviewer** | 独立设计审查。读需求/设计文档，按四维度（覆盖度/技术风险/替代方案/可测试性）出结构化审查报告。只读不改。 |
| **general-purpose** | General-purpose agent for researching complex questions, searching for code, and executing multi-... |
| **guardian-agent** | 交付前合规检查。跑验证脚本、检查规范，报告 PASS/CONDITIONAL/FAIL。只读不改。 |
| **memory-rules** | （见 memory-rules.md） |
| **sidecar-explorer** | Use proactively for broad codebase searches spanning more than 3 files, call chain tracing, depen... |
| **work-agent** | 生产开发助手。需求拆解、代码实现、Skill 编写、文档生成、Bug 定位、代码审查（只报告不修复）、资产流水线维护。 |

> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。
