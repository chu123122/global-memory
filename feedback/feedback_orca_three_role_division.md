---
description: orca 多 agent 任务固定 developer/reviewer/tester 三角色；测试/验证类跑动一律派 tester，lead 不自跑
priority: medium
status: active
trigger:
  keywords:
    - concept:orca
    - concept:multi-agent
    - concept:tester
    - concept:verification
    - concept:roles
  tags:
    - workflow
    - tooling
  stages:
    - discussion
    - implementation
    - review
    - delivery
last_updated: 2026-06-16
---

# Orca 多 agent 固定三角色：developer / reviewer / tester

## 规则
Orca 多 agent 任务固定拆成 developer、reviewer、tester 三角色；测试、eval、held-out、验证脚本等跑动一律派 tester，lead 只做编排和裁决，不亲自跑测试/验证命令。

## Why
**Why:** 本会话实测教训：lead 自己跑测试/eval 会破坏“运动员≠裁判”的独立性，也会和 worker 共享工作树产生竞态，导致结果不可复现。dev 自报数字两次失真（authority 乘法 vs 封顶加成、negative FPR 0 vs 1.0）正是靠独立 tester 复验 + held-out 才抓出来的。若 lead 亲自下场跑验证，就会把编排者、裁判、执行者边界混在一起。

## How to apply
起 Orca team 时固定三角色：
- developer：实现和自测，负责把工作树推进到“已冻结，可验证”。
- reviewer：只报告不改码，审正确性、过拟合、边界和可维护性。
- tester：独立复验，跑测试/eval/held-out/验证脚本，输出可复现证据。

lead 只做编排 + 裁决：可以读代码、写文档、写记忆、整理结论，但不亲自跑测试/eval/验证脚本；这类命令必须派 tester。验收以 tester 独立复现为准，不采信 dev 自报。
