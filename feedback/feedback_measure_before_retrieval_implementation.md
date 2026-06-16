---
description: 昂贵实现前先只读测量信号分布，证伪假设再动手
priority: high
status: active
trigger:
  keywords:
    - concept:validation
    - concept:evaluation
    - concept:distribution
    - concept:hypothesis
    - concept:poc
  tags:
    - workflow
    - tooling
    - design
  stages:
    - discussion
    - implementation
    - review
last_updated: 2026-06-16
---

# 昂贵实现前先只读测量证伪假设

## 规则
做检索、分类门、abstain、reranker、自动化 gate、复杂调度等昂贵实现前，先用现有数据只读测量关键分布；若正负例信号不可分，先回报负结果，不要直接开工调阈值或堆实现。

## Why
**Why:** `global-memory-semantic-retrieval-survey` 里两次先验测量省掉了无用实现：
1. 全语料 top1 cosine：离题问（周报/Python/手机推荐）分数高过跨语言治理正例，证明单阈值 domain gate 不可行。
2. 按目录 facet 只看治理组 cosine：治理正例与 held-out 负例仍重叠，证明免费分区也不够。

如果跳过这一步，AI 很容易 Goodhart：围着 10 来条 fixture 调阈值，看似 Recall/FPR 漂亮，换 held-out 立即失真。

## How to apply
触发：准备实现任何“先假设信号可分/规则有效”的昂贵工程前，尤其是检索、分类、abstain、rerank、confidence threshold、domain gate。

最小流程：
1. 先定义正例/负例/held-out，不写业务代码。
2. 只读跑现有信号：BM25、cosine、内容词数、分区内 top1、baseline 输出等。
3. 打印 min/max/sorted 和关键 overlap case。
4. 只有看到可分间隔或明确 trade-off，才进入实现；否则先汇报“信号不可分”。
