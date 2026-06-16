---
description: 本地 FTS5+bge-m3+RRF 检索 PoC 的可复用架构与评测资产
priority: medium
status: active
trigger:
  keywords:
    - concept:retrieval
    - concept:fts5
    - concept:rrf
    - tool:ollama
    - concept:evaluation
  tags:
    - tooling
    - memory
    - design
  stages:
    - implementation
    - review
last_updated: 2026-06-16
---

# 本地 hybrid retrieval PoC：FTS5 + bge-m3 + RRF + pointer-only

## 核心要点
- 可复用形态：SQLite FTS5 做 lexical，Ollama `bge-m3` 做本地 1024 维 embedding，裸 float32 BLOB 存向量，进程内点积，避免引入 sqlite-vec/Chroma/Qdrant 等复杂依赖。
- 融合方式：BM25 + vector channel 用 RRF，排序时 authority 只能做封顶小加成，不能乘法独裁。
- 输出契约：pointer-only（path/why/score/summary），debug/eval 才暴露 raw signals；不要把正文直接注入上下文。
- 评测资产比单次实现更值钱：golden/negative/semantic_positives fixtures、baseline 对账、held-out 负问、独立复验流程。
- `global-memory` PoC 数字：132 files / 1628 chunks；golden Recall@10=1.0、Recall@5=0.75；fixture negative FPR=0；held-out 13/13 负问挡住。但因 abstain/ROI 限制未部署。

## 常见误区
- 把 normalized RRF top=1 当 confidence；每个 query 的 top 都会归一到 1，不能用于负例接受门。
- 让 authority 或 vector_only 单独裁决；规则优先级只能在相关性近似同分时影响排序。
- 只跑 golden 不跑 negative/held-out。

## 参考
PoC 包：`harness/semantic/`（未部署，归档备查）。
