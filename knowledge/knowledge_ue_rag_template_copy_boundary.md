---
description: 抄 UE RAG 模板时要区分可免费复用的工程形态和不可硬抄的 LLM rewrite
priority: medium
status: active
trigger:
  keywords:
    - concept:rag
    - concept:facet
    - concept:rewrite
    - concept:template
    - concept:ue
  tags:
    - design
    - tooling
    - memory
  stages:
    - discussion
    - implementation
last_updated: 2026-06-16
---

# UE RAG 模板可抄/不可抄边界

## 核心要点
- 可抄：分区/facet 思想、BM25+vector 双通道、RRF 融合、pointer 输出、eval fixture、baseline/held-out 复验流程。
- 对 `global-memory` 更便宜的部分：目录本身就是 facet（rules/agents/decisions/feedback/fixes/knowledge/docs），不必用 LLM 给文档分类。
- 不可硬抄：UE 的 query rewrite/domain 判断依赖 LLM；如果本项目边界要求零远程/零 LLM，就不能把这一步当免费能力。
- 实测结论：只抄免费 facet 分区仍不能解决 abstain；治理组内正例/负例 cosine 重叠。缺 query-side rewrite/intent 判断时，跨语言和纯换说法召回很难同时保精度。

## 常见误区
- 用户说“照 UE 模板写”不等于所有步骤都可复制；必须拆出依赖、延迟、隐私和 ROI。
- 把 facet 分区当作意图判断替代品；facet 只能约束文档侧，不能理解 query。

## 参考
来源：`global-memory-semantic-retrieval-survey` 对 `ue-api-search-mcp` 模板的对照分析与 Phase 3 facet 先验测量。
