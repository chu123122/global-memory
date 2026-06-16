---
packet_id: 20260616-103518-triage-close-verify-gate
author: codex
created: 2026-06-16T10:35:18
risk_tier: 2
status: submitted
---

# Change Packet: Triage close verify gate

## Motivation (WHY)

- 解决 `/triage` Step 5 关闭来源主要靠 AI 自觉的问题。
- 不修则可能出现口头 closed、但 issue/feedback frontmatter 仍 open/active 或无验证证据的假闭环。

## Scope (WHAT)

Files to modify:
- `harness/scripts/triage_inbox.py`
- `harness/tests/test_triage_inbox.py`
- `skills/triage/v1/SKILL.md`
- `docs/scripts-registry.md`（如 CLI 用法需同步）
- `CHANGELOG.md`
- `D:/ClaudeTasks/active/triage-close-verify-gate/*`

Files NOT touched:
- `archive_task.py`
- hooks / retrieve / statusline
- centralized ledger / database

New files to create:
- none

## Approach (HOW)

- 在 `triage_inbox.py` 增加 `--verify-close <path>` 只读模式。
- 校验 frontmatter status 已离开 inbox（issue 不再 open；feedback 不再 active），并要求正文含关闭记录/验证证据/drop reason/supersede 等证据关键词。
- 默认 scan 行为不变；verify-close 输出稳定 JSON 并用退出码表达 PASS/FAIL。

## Evidence & Verification

- Pre-implementation: Opus 4.8 xhigh 效果分析指出 triage 最大假闭环面是“关闭来源无机器门”。
- Red: 新增 verify-close 测试后，`pytest harness/tests/test_triage_inbox.py -q` -> 6 failed / 5 passed；失败原因是 argparse 不识别 `--verify-close`。
- Green: 实现后 `pytest harness/tests/test_triage_inbox.py -q` -> 11 passed。
- CLI fixture: temp closed issue + `python harness/scripts/triage_inbox.py --repo-root <tmp> --verify-close issues/ISSUE-2026-06-16-fixture.md --json` -> `verdict=PASS`。
- Syntax: `python -m py_compile harness/scripts/triage_inbox.py` -> PASS。
- Post-implementation: 限定 quality gate PASS。

## Risks & Rollback

- 风险：证据关键词不完美；缓解：保守 fail，提示缺失项，仍由用户/AI决定如何补证据。
- 风险：CLI 复杂度增加；缓解：新增独立 `--verify-close`，不改变默认 scan。
- 回滚：撤回 `triage_inbox.py` verify-close 分支、测试与 SKILL 文档说明。

## Intent Alignment

- Parent task: triage-close-verify-gate
- Yes. 该改动直接把 `/triage` 的关闭步骤从文档约定强化为机器可检查门。
