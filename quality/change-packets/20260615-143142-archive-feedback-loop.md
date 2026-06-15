---
packet_id: 20260615-143142-archive-feedback-loop
author: <agent-id or human>
created: 2026-06-15T14:31:42
risk_tier: 2
status: submitted
---

# Change Packet: Inbox triage loop

## Motivation (WHY)

- 解决个人 AI 工作系统中问题来源分散、正式开 task 太重、全自动修复又不稳的问题。
- 不做则 issue / feedback / 归档候选 / health warning 仍需要人工逐处翻找，无法周期性快速消化。

## Scope (WHAT)

Files to modify:
- `skills/triage/v1/SKILL.md`
- `harness/scripts/triage_inbox.py`
- `harness/tests/test_triage_inbox.py`
- `docs/scripts-registry.md`
- `bootstrap.py`
- `D:/ClaudeTasks/active/archive-feedback-loop/*`
- `quality/change-packets/20260615-143142-archive-feedback-loop.md`

Files NOT touched:
- `agents/CLAUDE.md`
- hooks / retrieve / statusline runtime 链路
- `harness/scripts/archive_task.py` 的 triage/close 状态机扩张
- 既有 memory 自动写入逻辑

New files to create:
- `skills/triage/v1/SKILL.md`
- `harness/scripts/triage_inbox.py`
- `harness/tests/test_triage_inbox.py`

## Approach (HOW)

- 新增轻量 `/triage` skill：scan inbox -> AI propose -> user choose -> execute/route -> verify -> close source。
- 新增只读扫描脚本输出 JSON；来源原地不动，不建中心化数据库。
- 用户判断最小化为 `修` / `task` / `work` / `drop`；AI 不做无确认自动修复或关闭。

## Evidence & Verification

- Pre-implementation: Opus 4.8 high 设计复审已判定旧 archive 状态机过重，用户确认撤回旧实现并转向 triage skill。
- Post-implementation: `pytest harness/tests/test_triage_inbox.py -q`；`python harness/scripts/triage_inbox.py --json`；`python C:/Users/XINDONG/.claude/scripts/work_context_pack.py --task archive-feedback-loop --json --write-status`；限定路径 `quality_gate.py verify --path ... --json`。

## Risks & Rollback

- 风险：扫描来源太多导致结果噪声；缓解：MVP 只扫 2-3 类确定来源，并限制输出数量。
- 风险：skill 变成又一套重流程；缓解：用户只做 4 选 1，执行继续复用现有 `/work` / quality gate。
- 回滚：删除 `skills/triage/v1/SKILL.md`、`harness/scripts/triage_inbox.py`、`harness/tests/test_triage_inbox.py`，撤回 registry/bootstrap 文档改动。

## Intent Alignment

- Parent task: archive-feedback-loop
- Yes. 该改动服务用户重新确认的真实目标：轻量周期性消化问题，归档候选只是输入源之一。
