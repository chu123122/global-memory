# Agents 目录

| Agent | 描述 |
|-------|------|
| **CLAUDE** | （见 CLAUDE.md） |
| **control-panel-ui-implementer** | 当已有 UX 设计方案，需要实现技术主控台 / Tkinter 面板 / Dashboard UI 改造时使用。重点是把 CLI/JSON 数据提炼成结构化状态，隐藏默认命令行输出，补测试，确保... |
| **control-panel-ux-designer** | 当需要设计或评审技术主控台、维护面板、Dashboard、脚本驱动的运维 GUI 时使用。重点是降低理解门槛、隐藏默认命令行输出、明确下一步操作、把脚本/JSON 输出转成人类可操作结论。 |
| **design-reviewer** | Independent design reviewer. Reads requirement/design docs in docs/active/ and produces a structu... |
| **guardian-agent** | Pre-delivery compliance checker. Runs verify scripts, checks conventions, reports PASS/CONDITIONA... |
| **learning-agent** | Personal learning tutor for game engine dev. C++/UE/rendering study, interview prep with Socratic... |
| **memory-rules** | （见 memory-rules.md） |
| **work-agent** | Production dev assistant. Requirements breakdown, code impl, Skill authoring, doc gen, bug locati... |

> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。
