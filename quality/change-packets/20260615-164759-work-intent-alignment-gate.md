---
packet_id: 20260615-164759-work-intent-alignment-gate
author: <agent-id or human>
created: 2026-06-15T16:47:59
risk_tier: 2
status: submitted
---

# Change Packet: Work intent alignment gate

## Motivation (WHY)

- 解决 `/work` 在实现前缺少方向校准门的问题：新意图可能被 cwd/task_resolver/session 自动解析到旧 task 后继续推进。
- 不修则用户新目标会被错误旧 task 吸收，后续设计、worker 派发和实现都会继承错误边界。

## Scope (WHAT)

Files to modify:
- `harness/work_context_pack.py`
- `harness/tests/test_work_skill_tdd_rules.py`
- `skills/work/v1/SKILL.md`（如脚本行为说明需同步）
- `skills/work/v1/codex-adapter.md` 或渲染产物（如需要）
- `D:/ClaudeTasks/active/work-intent-alignment-gate/*`

Files NOT touched:
- `agents/CLAUDE.md`
- hooks / retrieve / statusline
- unrelated task documents

New files to create:
- none

## Approach (HOW)

- 将 `intent_guard` 从仅覆盖 `session_task_file` 扩展到无显式 `--task` 的所有自动解析路径。
- 显式 `--task` 视为用户已选择任务，不触发新任务 guard 阻断。
- 用回归测试固定：新意图 + cwd 解析旧 task -> WARNING；普通继续任务不误报；显式 `--task` 不误拦。

## Evidence & Verification

- Pre-implementation: triage 真实复现命令显示 `work_context_pack.py --intent ...` 解析到旧 task `global-memory-oss-readiness-hardening`。
- Post-implementation: `pytest harness/tests/test_work_skill_tdd_rules.py -q`；真实复现命令返回 `intent_guard.action=create_task_or_confirm`；限定路径 `quality_gate.py verify --path ... --json`。

## Risks & Rollback

- 风险：过度拦截普通继续任务；缓解：只在 `--intent` 命中新任务模式且无显式 `--task` 时触发。
- 风险：显式续跑被误拦；缓解：`--task` 不触发 guard。
- 回滚：撤回 `work_context_pack.py` 与测试/文档改动。

## Intent Alignment

- Parent task: work-intent-alignment-gate
- Yes. 该改动直接服务“避免新意图被旧 task 吸走”的任务目标。
