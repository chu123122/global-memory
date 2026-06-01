---
description: 不可逆操作（移动/删/写远端）双守护：--yes flag + 内部前置 check refuse
priority: high
status: active
trigger:
  keywords:
    - concept:irreversible
    - concept:guard
    - tool:cli
  tags:
    - design
    - tooling
    - workflow
  stages:
    - discussion
    - implementation
last_updated: 2026-05-21
---

# 不可逆操作双守护模式

## 决定

CLI 中任何不可逆操作（物理移动 / 删除 / 写全局状态 / 远端推送）必须**两层守护**：

1. **显式 flag**（`--yes` / `--force` / `--commit`），缺失 → refuse rc=1
2. **内部前置 check**，不通过 → refuse rc=1（即使 flag 已带）

例：`archive_task.py --commit` 须带 `--yes` + 内部跑 `--check` 验 Phase 全 done + 目标目录已存在则 abort。

## 备选方案

- A 单层 flag（`--yes` 即放行）：用户输错 `--yes` 后果不可逆
- **B 双层（flag + 前置 check）**（选）
- C 三层（flag + check + 5s 倒计时确认）：过烦

## 理由

A 缺点：人手抖 `--yes` 一次 → 整任务移走/删掉无救。
B 双重：flag 防误调用，check 防状态不满足时强行操作（如 Phase 未完就归档 → 后续 retry 困难）。
C 倒计时在脚本（非交互）场景失效；CI 跑过不去。

`archive_task.py` 案例：`--commit` 内部跑 `--check`，若有非 done Phase 直接 refuse；移动后写全局 CHANGELOG，回滚需 `git mv` + revert CHANGELOG → 双守护成本远低于回滚成本。

## 适用范围

适用：
- 文件系统物理移动 / 删除（`shutil.move` / `rm -rf`）
- 写全局共享状态（global CHANGELOG / 注册表 / 索引）
- 远端推送（`git push` / API 写）
- `DROP TABLE` 类 DB 操作

不适用：本地可逆操作（写本任务文件 / 加 commit 但不 push）。

## 复审条件

- 出现「带 --yes 仍出事」case → 加第三层（如 dry-run 默认）
- 误触发率 >1/100 调用 → 重审 flag 命名（`--yes` 太顺手 → 改 `--really-yes`）
