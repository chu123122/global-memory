---
description: sidecar 报「无消费方/DEAD」结论必须 grep reader 路径验证才能采信
priority: high
status: active
trigger:
  keywords:
    - concept:sidecar
    - concept:audit
    - tool:harness
  tags:
    - tooling
    - workflow
  stages:
    - debug
    - discussion
last_updated: 2026-05-22
---

# sidecar 摘要「DEAD」结论必须 grep reader 验证

## 现象

harness-usage-audit P1 sidecar 报「`memory_writes.jsonl` DEAD write-only」。
P2 ls 实测：490 行 / 今日 mtime / 有消费方 `changelog_drift.py:20`。
sidecar 判错。

## 根因

sidecar 200w 摘要协议限制，凭文件名 + hook 出现位置臆断「无消费方」，未 grep reader 路径。
主模型/用户若直接采纳，会做错处置决策（误删活日志）。

## 修复

sidecar 涉及「dead/无消费方/未使用」结论时：

1. 主模型必须二次验证：`Grep "<文件名>" path:<相关目录>`
2. 找到 reader 路径才确认 dead；找不到才信 sidecar 判定
3. ls 体积 + mtime 辅证（write 仍发生 ≠ alive，要看是否有 reader）

## 验证

P2 实测同时核查 2 文件：
- `memory_lint_gate.jsonl` 23 行 / 无 reader → 真 dead ✅ sidecar 对
- `memory_writes.jsonl` 490 行 / `changelog_drift.py:20` reader → alive ❌ sidecar 错
