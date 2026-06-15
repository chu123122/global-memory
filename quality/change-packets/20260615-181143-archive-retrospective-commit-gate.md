---
packet_id: 20260615-181143-archive-retrospective-commit-gate
author: codex
created: 2026-06-15T18:11:43
risk_tier: 2
status: submitted
---

# Change Packet: Archive retrospective commit gate

## Motivation (WHY)

- 解决 `archive_task.py --commit` 只依赖 `--check`、可绕过 `core/复盘.md` 与 5 护栏的问题。
- 不修则大任务可静默归档，复盘候选不会被抽取/triage，刚建立的 inbox triage loop 会缺输入源。

## Scope (WHAT)

Files to modify:
- `harness/scripts/archive_task.py`
- archive_task 相关测试（优先新增或扩展 `harness/tests/test_archive_task.py`）
- `issues/ISSUE-2026-06-04-archive-commit-skips-retrospective-gate.md`
- `CHANGELOG.md`
- `D:/ClaudeTasks/active/archive-retrospective-commit-gate/*`

Files NOT touched:
- `harness/scripts/archive_task.py --triage/--close` 旧状态机路线（不恢复）
- hooks / retrieve / statusline
- `agents/CLAUDE.md`

New files to create:
- 如不存在 archive_task 测试文件，则新增 `harness/tests/test_archive_task.py`

## Approach (HOW)

- 在 `cmd_commit()` 中，于 `cmd_check()` PASS 后、`shutil.move()` 前调用 retrospective gate。
- Gate 以 `design/Phase*.md` 数量作为确定性门槛：`>=4` 必须存在 `core/复盘.md` 且通过现有 `lint_retro()`；`<4` 小任务缺复盘时写最小跳过声明。
- 不实现“>=10 轮用户交互”的自动判断，因为当前没有可靠机器源；避免把 AI 猜测写进确定性脚本。

## Evidence & Verification

- Pre-implementation: issue 原文复现说明 `--check -> --commit` 可跳过复盘；`archive_task.py` 当前 `cmd_commit()` 确认只调用 `cmd_check()` 后移动目录。
- Post-implementation: pytest 覆盖大任务缺复盘拒绝、大任务复盘 lint fail 拒绝、小任务跳过留痕、`--extract` lint 不回退；再跑限定路径 quality gate。

## Risks & Rollback

- 风险：误伤小任务归档；缓解：`Phase*.md < 4` 不要求完整复盘，只写跳过留痕。
- 风险：自动写 `core/复盘.md` 带来额外副作用；缓解：仅在显式 `--commit --yes` 路径发生，内容为最小留痕，不生成经验结论。
- 回滚：撤回 `archive_task.py` gate 与对应测试，恢复 commit 只依赖 `--check`。

## Intent Alignment

- Parent task: archive-retrospective-commit-gate
- Yes. 该改动直接服务用户在 `/triage` 中选择的 A：修复归档复盘文档强制但脚本不强制的缺口。
