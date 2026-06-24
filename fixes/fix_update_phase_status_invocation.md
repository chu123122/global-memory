---
description: update_phase_status.py 调用坑——位置参数 + task 须传绝对路径 + 验收清单需 P<n> 前缀
priority: medium
status: active
trigger:
  keywords:
    - tool:harness
    - tool:work
    - concept:phase
  tags:
    - workflow
    - tooling
  stages:
    - implementation
last_updated: 2026-06-17
---

# update_phase_status.py 调用坑

## 现象

标 Phase done 时连续踩 3 个坑：

1. `--task X --phase N --status done` → `error: unrecognized arguments: --task --phase --status`
2. 改用 `<task-id> 1 done` → `ERROR: design/ not under ~/.claude/global-memory\<task-id>`
3. 传绝对路径成功，但 `❌ acceptance list`：`no - [ ] P1 line found`，验收清单未被勾选（退出码 1）

## 根因

1. **位置参数**：usage 是 `update_phase_status.py task n {blocked,done,in_progress,pending}`，不是 `--task/--phase/--status`。状态枚举是 `in_progress`，不是 task-lifecycle / work skill 文档里写的 `implementing`。
2. **task 定位用 cwd 拼接**：脚本把第一个参数当 `cwd/<arg>` 去找 `design/`。任务在 `D:\ClaudeTasks\active\` 而非 cwd（如 `~/.claude/global-memory`）下时，必须传**任务目录绝对路径**，不能只传 task-id。
3. **验收清单勾选靠 `P<n>` 前缀**：脚本「三同步」（Phase 卡 frontmatter + 设计文档 Phase 表 + 验收清单）里，验收清单步只勾选形如 `- [ ] P1 xxx` 的行（前缀 `P<phase号>`）。验收项不带 `P<n>` 前缀 → 跳过，整体退出码非 0（即便前两同步成功）。

## 修复

- 调用：`python harness/scripts/update_phase_status.py "<任务目录绝对路径>" <N> done`
- 设计文档「验收」清单每项前加 `P<n>` 关联 Phase：`- [ ] P1 <验收项>`，脚本 done 时自动勾选。
- Phase 卡 frontmatter 初始 status 建议用脚本枚举值 `in_progress`（`implementing` 虽能被 done 覆盖，但非脚本合法枚举）。

## 验证

脚本输出三行 ✅/❌：`phase card frontmatter` / `design table row` / `acceptance list`，三者全 ✅ 即同步成功、退出码 0。
