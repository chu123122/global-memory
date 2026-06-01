# Agents 目录

| Agent | 描述 |
|-------|------|
| **bounded-worker** | Use proactively for mechanical code edits with explicit file scope and clear target change: batch... |
| **CLAUDE** | （见 CLAUDE.md） |
| **code-reviewer** | Use proactively after multi-file edits (3 or more files changed), or when changes touch hooks, CL... |
| **control-panel-ui-implementer** | 当已有 UX 设计方案，需要实现技术主控台 / Tkinter 面板 / Dashboard UI 改造时使用。重点是把 CLI/JSON 数据提炼成结构化状态，隐藏默认命令行输出，补测试，确保... |
| **control-panel-ux-designer** | 当需要设计或评审技术主控台、维护面板、Dashboard、脚本驱动的运维 GUI 时使用。重点是降低理解门槛、隐藏默认命令行输出、明确下一步操作、把脚本/JSON 输出转成人类可操作结论。 |
| **design-reviewer** | 独立设计审查。读需求/设计文档，按四维度（覆盖度/技术风险/替代方案/可测试性）出结构化审查报告。只读不改。 |
| **guardian-agent** | 交付前合规检查。跑验证脚本、检查规范，报告 PASS/CONDITIONAL/FAIL。只读不改。 |
| **learning-agent** | 游戏引擎学习辅导。C++/UE/渲染学习，面试备战，苏格拉底提问法，知识盲区追踪。生产代码委托 work-agent。 |
| **log-triage** | Use proactively when build output, test results, or runtime logs are long (>100 lines) or contain... |
| **memory-rules** | （见 memory-rules.md） |
| **sidecar-explorer** | Use proactively for broad codebase searches spanning more than 3 files, call chain tracing, depen... |
| **work-agent** | 生产开发助手。需求拆解、代码实现、Skill 编写、文档生成、Bug 定位、代码审查（只报告不修复）、资产流水线维护。 |

> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。
