---
description: 互斥多模式 CLI 用单脚本 argparse mutually_exclusive_group 而非分多脚本
priority: medium
status: active
trigger:
  keywords:
    - concept:cli
    - tool:argparse
    - concept:mode
  tags:
    - python
    - design
    - tooling
  stages:
    - discussion
last_updated: 2026-05-21
---

# 多模式 CLI 用单脚本 argparse mutex group

## 决定

CLI 工具有 N 个互斥操作模式（如 `--check` / `--extract` / `--commit`），用单脚本 + `argparse.add_mutually_exclusive_group(required=True)`，不拆 N 个独立脚本。

## 备选方案

- A 拆 N 个独立脚本（如 `archive_check.py` / `archive_extract.py` / `archive_commit.py`）
- **B 单脚本 argparse mutex group**（选）
- C 子命令 subparser（如 `archive task check / extract / commit`）

## 理由

A 缺点：
- 共享解析（task_dir / frontmatter）重复实现 3 次或抽 lib
- 用户记 3 个脚本名
- registry 注册 3 行

B 优点：
- 单文件 ~400 行可接受
- 共享解析自然
- `--help` 一次看全模式

C 适用更大规模（每模式自身 ≥5 flag）；3 模式且 flag 少时 mutex group 更简洁。

## 适用范围

适用：N=2-4 互斥模式，每模式 ≤3 flag。
不适用：N≥5 或每模式 flag 多 → 用 subparser（C）。

## 复审条件

- 单脚本超 600 行 → 考虑拆 C
- 模式数 >4 → 转 C
