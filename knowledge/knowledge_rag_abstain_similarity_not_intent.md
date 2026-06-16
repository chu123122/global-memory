---
description: 小杂语料里相似度不等于意图；非 LLM abstain 难同时保召回和精度
priority: high
status: active
trigger:
  keywords:
    - concept:rag
    - concept:abstain
    - concept:similarity
    - concept:embedding
    - concept:roi
  tags:
    - memory
    - design
    - tooling
  stages:
    - discussion
    - review
last_updated: 2026-06-16
---

# RAG abstain：相似度不是意图，小杂语料非 LLM 门很难解

## 核心要点
- embedding cosine 衡量“像不像”，不等于“该不该答”。离题但术语相邻的问题（周报、Python error、推荐手机）可能比真正跨语言治理正例分数更高。
- 在又小又杂的知识库里，模板、技术笔记、fix 记录都是噪声磁铁；仅靠全局阈值或目录 facet 阈值很难同时挡噪声和赚回语义召回。
- `global-memory-semantic-retrieval-survey` 实测：全语料 top1 cosine 不可分；按 governance facet 后仍重叠。免费非 LLM abstain 路线被证伪。
- 保守无 LLM 方案会退化为“内容词锚定 hybrid retrieval + vector rerank”：精度能控，但 vector_only 必须关掉，英文/纯换说法召回回不来。
- 对 100 多文件级小库，RAG ROI 未必超过 grep/关键词 alias；真正值得做通常是大语料或 hot-path 自动防违规场景。

## 常见误区
- 误把 top1 cosine 当 confidence。
- 只在调参 fixture 上看 FPR，不看 held-out。
- 以为加分区就等于有意图判断；分区只能隔离部分噪声，不能理解用户意图。

## 参考
来源任务：`global-memory-semantic-retrieval-survey`。结论：本地语义检索召回验证成立，但暂不部署；若未来要做 hot-path 自动防违规，需要本地 LLM rewrite/domain classifier 或 HyDE，再扩 golden 集验证。
