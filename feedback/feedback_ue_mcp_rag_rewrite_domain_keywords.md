---
description: UE MCP 查询先把陌生语义 rewrite 成领域关键词再检索
priority: high
status: active
trigger:
  keywords:
    - tool:ue-api-search-mcp
    - concept:rewrite
    - concept:RAG
    - concept:primitive
    - concept:facet
  tags:
    - workflow
    - tooling
    - ue
    - design
  stages:
    - discussion
    - implementation
    - review
last_updated: 2026-06-22
---

# UE MCP/RAG 查询要通过 rewrite 约束生成

## 规则
UE MCP/RAG 可实现性查询应先把陌生自然语言语义 rewrite 成 UE/游戏实现领域的关键词、primitive、facet，再做向量/关键词检索和 hit/partial/miss 裁定。

## Why
2026-06-22 在 `game-proto-mapping` 8 步流程讨论中，用户指出：UE MCP 查询（包括 ue-api-search-mcp）的 rewrite 很有价值，它不是简单翻译，而是把“用户/AI 陌生语义”转换成“特定领域关键词”，再进入本地向量库匹配查找。这个中间层会约束 AI 的生成，避免 AI 直接凭自然语言想象实现或把玩法概念误当 API 证据。

相关旧问题：`issues/ISSUE-2026-06-16-api-search-concept-query-noise.md` 已记录过“玩法概念整句查询会返噪声，primitive 查询更可靠”。本反馈进一步明确 rewrite 的正向定位：它是从自然语义到领域检索语言的约束层。

## How to apply
触发：UE API 可实现性查询、能力/表现到代码模板映射、game prototype 第 4 步 MCP/RAG 裁定、或审查“查询记录是否足够约束生成”时。

执行方式：
1. 先从第一层映射拆出 primitive/facet，不直接拿玩法概念整句当最终裁定。
2. rewrite 目标是生成 UE/游戏实现领域关键词，例如输入轴、Character movement、SphereTrace、ApplyDamage、SetActorEnableCollision、Canvas DrawText、time dilation、camera shake 等。
3. 用 rewrite 后的领域关键词进入向量/BM25/RAG 检索，保存原始 MCP 返回。
4. 根据返回 symbol/signature/why 做 hit/partial/miss 裁定；miss/partial 要记录原因和替换方案。
5. 查询慢时优先把 query 拆短、拆 primitive/facet；不要绕过 MCP/RAG，也不要用人工常识或历史记录冒充本轮查询证据。
