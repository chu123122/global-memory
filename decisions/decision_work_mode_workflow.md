---
name: decision-work-mode-workflow
description: /work skill 作为工作流程统一入口的架构决策与边界说明
summary: "确定用 /work skill 而非自动 hook 或主对话 subagent，强调三层文档防线"
type: decision
created: 2026-04-17
updated: 2026-04-21
source: 通用工作流治理
access_count: 0
priority: high
status: active
trigger:
  keywords:
    - tool:work
    - tool:skill
  tags:
    - workflow
    - design
    - skill
  stages:
    - discussion
    - implementation
last_updated: 2026-06-01
---

# 决策：/work skill 作为工作流程统一入口

> 日期：2026-04-17
> 范围：~/.claude/skills/work/ + ~/.claude/agents/work-agent.md
> 状态：已实施

> **2026-06-01 更新**：核心决策（用 /work skill 做入口、不用 hook/subagent）依旧有效。但下文 §4/§7 描述的 **v1 平铺文档机制**（SPEC.md / 需求分析.md / 设计文档.md + discussion/implementation 二阶段 + check_doc_status 三层防线）已被 **v2 4 子目录结构**取代——`core/` + `design/` + `ops/` + `test/`，状态机改用 Phase 卡 `status:` 流转，校验入口改为 `work_context_pack.py`。v1 机制仅作老任务只读兼容保留。规范单一来源见 `docs/task-lifecycle.md`。下文 §4/§7 留作历史记录，勿据此新建任务。

> **2026-06-04 更新**：work 流程已用 SPEC「四契约」（任务/验收/执行/权威）重排为统一概念骨架——见 `skills/work/SKILL.md`「## 四契约」与 `docs/task-lifecycle.md` § 2。新增机制：done 打回规则（验收项 ↔ 证据 1:1，缺则不得 done）、默认权威裁决链（人工 > 可执行证据 > 设计文档 > 代码现状 > 自动状态文件，override 必留痕）、Phase 卡四契约小节、机械检查 `harness/scripts/check_phase_evidence.py`。SPEC 不新增文件/本体，只作为重排现有产物的概念词汇。来源任务：`codex-work-flow-contract-tightening`（archived）。

---

## 1. 问题陈述

`work-agent.md` 是「人格描述」而非「流程入口」：
- 靠 Claude 自觉走 CLAUDE.md 中的「新对话启动协议」（读 MEMORY → 读 HANDOFF → 核对进度）
- 实测会漏步骤，特别是文档校验和收尾同步
- `spec_gate.py` 是 PreToolUse 被动拦截，触发时已经在写代码了，体验差
- 新任务 vs 继续老任务没有显式分流，AI 容易"自作主张接着写"

## 2. 选项对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 纯行为调整（现状） | 零额外文件 | 依赖人格自觉，会漏步骤 |
| B. UserPromptSubmit hook 自动检测 @work | 用户无需记入口 | 自动检测不增值（用户本来就主动打）；多一个 hook 维护面 |
| C. /work skill 显式入口 | 单点维护、明确边界 | 用户需主动打 /work |
| D. B+C | 全覆盖 | 重复设计，hook 和 skill 功能重叠 |

**选 C**。理由：
1. 用户使用模式是「对话时主动打入口」，hook 的「自动检测」对此场景不增值
2. skill 在被 invoke 时才生效，安全（hook 出问题影响所有消息）
3. 流程强制由 skill 内部 Step 0-4 + 三层文档防线保证，不靠 hook 触发

## 3. 为什么不用 subagent

`Agent(subagent_type=...)` 切断上下文，每次需要重新调查 cwd / MEMORY / HANDOFF，反而比 inline 更慢。
work mode 的本质是「在主对话中切换工作模式」，不是「派生独立任务」。subagent 更适合并行调研、长时间隔离的子任务，不适合做主对话的工作流入口。

## 4. 三层文档防线设计

```
[/work 入口]
   └─ check_doc_status.py 主动校验 → 列出每个 active_task 的 SPEC/HANDOFF 状态
        ↓
[执行阶段：写代码]
   └─ spec_gate.py 被动拦截（保留不动）→ 缺/未填 SPEC 时 deny
        ↓
[/work 收尾 Step 4]
   └─ check_doc_sync.py → 对比 SPEC mtime 和 git log 改动 → 强制提示更新
```

**单一数据源**：三层共享 `~/.claude/projects/project_registry.json`。
**单点维护**：`UNFILLED_MARKERS` 在 `spec_gate.py` 定义，`check_doc_status.py` import 复用（避免双份）。

## 5. 与现有 hook 的关系

| Hook | 角色 | 改动 |
|------|------|------|
| spec_gate.py | 编辑时被动拦截 | **不动**（保留兜底功能） |
| dangerous_command_blocker.py | 危险命令拦截 | 不动 |
| memory_file_protector.py | 记忆文件保护 | 不动 |
| audit_logger.py | 审计 | 不动 |
| subagent_logger.py | subagent 日志 | 不动 |
| post_task_hook.py (Stop) | 结束自动修复 | 不动 |

`/work` skill 与 spec_gate 的关系是**叠加，不是替代**。skill 解决"提前预警 + 收尾追踪"，spec_gate 解决"编辑时硬拦截"。

## 6. 文件清单

新增：
- `~/.claude/skills/work/SKILL.md`
- `~/.claude/skills/work/scripts/load_context.py`
- `~/.claude/skills/work/scripts/check_doc_status.py`
- `~/.claude/skills/work/scripts/check_doc_sync.py`
- `~/.claude/skills/work/templates/workflow.md`

修改：
- `~/.claude/agents/work-agent.md`（顶部加「流程入口」章节）
- `~/.claude/global-memory/MEMORY.md`（Decisions 区块加索引）

不动：
- 所有 hook（含 spec_gate）
- `~/.claude/settings.json`
- `project_registry.json` 格式

## 7. 维护要点

- **修改 spec_gate 的 UNFILLED_MARKERS / check_doc_filled 时**：必须同步检查 `check_doc_status.py` 是否还能正常 import 复用
- **新增 required_doc 类型时**：在 `project_registry.json` 加，三个脚本都自动适配
- **新增 active_task 时**：必须先 mkdir + 填 SPEC/HANDOFF/HARNESS_REVIEW/WORKFLOW，否则 spec_gate 拦
- **/work skill 不要扩展为通用 agent**：保持只做「入口 + 流程编排」，子模式行为留在 work-agent.md

## 8. 验证清单

- [x] `python check_doc_status.py` 在 ~ 目录跑无崩溃，输出活跃任务文档状态
- [x] `python check_doc_sync.py` 同上，能识别非 git 仓库并退化提示
- [x] `python load_context.py` 输出 MEMORY 活跃项目表格
- [x] SKILL.md 被系统识别（available skills 中出现 `work`）
- [ ] 端到端：实际打 `/work test` 走完整 Step 0-4
- [ ] smoke_test.py 全套脚本无崩溃

## 9. 后续可能的演进（暂不做）

- 复制套路到 learning-agent / guardian-agent（看 work 验证效果）
- check_doc_sync 自动写入 SPEC「## 进度」（目前只建议，由用户确认）
- skill 内部加 token 估算（避免长流程爆上下文）
