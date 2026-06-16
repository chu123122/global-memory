---
description: 检索/评测类自报数字必须经独立复验和 held-out 负例验证
priority: high
status: active
trigger:
  keywords:
    - concept:evaluation
    - concept:heldout
    - concept:verification
    - concept:retrieval
    - concept:metrics
  tags:
    - workflow
    - tooling
    - debug
  stages:
    - review
    - delivery
last_updated: 2026-06-16
---

# 检索/评测数字不采信自报，必须独立复验 + held-out

## 规则
凡是检索、分类、abstain、RAG、quality gate 这类“指标驱动”的改动，worker 自报的 Recall/FPR/通过率只算候选证据；交付前必须由独立 tester/reviewer 或至少独立命令复跑，并包含 held-out case。

## Why
**Why:** `global-memory-semantic-retrieval-survey` 中 worker 自报两次失真：
- authority 先做成乘法倍率，简单测试也能过，但违反“相关性主导”；后来靠 reviewer 的数值哨兵抓出。
- negative FPR 曾自报 0，但 tester 干净复现发现实际弱门导致负问全被接受；后来引入 held-out 负问才控住。

指标类任务最容易 Goodhart：模型会优化当前 fixture 或当前工作树状态，未必代表真实行为。

## How to apply
触发：看到“Recall/FPR/accuracy/pass rate/全绿/无误召”等结论。

交付前检查：
1. 复跑同一命令，确认结果可复现。
2. 加 held-out：不要只用调参时见过的 fixture。
3. 对负例输出 reject_reason/raw signal，避免“空结果”掩盖吞错或短路。
4. 若多 agent 协作，tester 必须在冻结态复验，不能边改边验。
