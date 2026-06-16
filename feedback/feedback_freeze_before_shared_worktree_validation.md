---
description: 多 worker 共用一个工作树时，必须先冻结再让 tester/reviewer 验证
priority: medium
status: active
trigger:
  keywords:
    - concept:worktree
    - concept:freeze
    - concept:validation
    - concept:multi-agent
  tags:
    - workflow
    - tooling
  stages:
    - implementation
    - review
    - delivery
last_updated: 2026-06-16
---

# 共享工作树验证协议：dev 冻结后 tester 再验

## 规则
多个 worker 共用同一个 repo/worktree 时，dev 未声明“已冻结，可验证”前，tester/reviewer 不应采信结果；冻结后 dev 不再改码、不重建、不跑会改变状态的命令，直到复验完成。

## Why
**Why:** `global-memory-semantic-retrieval-survey` 中 tester 复验 semantic index 时，dev 同时重建索引/调整 gate，导致同一负例一会儿 FPR=0、一会儿 FPR=1。共享工作树下，代码、SQLite 生成物、meta policy 都可能被并发改变，复验结果不可解释。

## How to apply
触发：Orca/多 worker/多人共用一个本地 repo，尤其有生成物（SQLite、cache、build output、policy meta）。

协议：
1. dev 完成后跑测试与必要 build，回报“已冻结，可验证”。
2. 冻结期间 dev 不改码、不重建、不写生成物。
3. tester/reviewer 只读复验。
4. 若需要二次调整，lead 明确解冻后再改。
