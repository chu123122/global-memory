---
description: retrieve 3 指标（zero_hit / pointer_rate / call_rate）写端 vs 读端互补不重叠
priority: high
status: active
trigger:
  keywords:
    - concept:retrieve
    - concept:metrics
    - tool:harness
  tags:
    - tooling
    - doc
  stages:
    - implementation
    - debug
last_updated: 2026-05-22
---

# Retrieve 3 指标语义区分

## 核心要点

| 指标 | 定义 | 治什么 | 来源 |
|---|---|---|---|
| **zero_hit_rate** | 召回 0 pointer 的调用 / 总调用 | 写端：frontmatter keyword 不够 / alias 缺 | `health/checks/retrieve_hitrate.py:47` |
| **call_rate** | ≥1 pointer 被 Read 的调用 / 总调用 | 读端：召回内容有用度（粗粒度） | `scripts/analyze_retrieve_log.py:197` |
| **pointer_rate** | 被 Read 的 pointer / 召回总 pointer | 读端：召回内容有用度（细粒度） | `scripts/analyze_retrieve_log.py:200` |

健康基线（XINDONG 系统 2026-05 实测）：
- zero_hit 50% / pointer_rate 0.7% / call_rate 1.6% = **两端同时坏**
- zero_hit 治：补 frontmatter
- pointer_rate 治：降 top_k + 删噪声 keyword

## 常见误区

- ❌ 把 zero_hit 当「没用」: zero_hit 50% + pointer_rate 5% = 召回少但有用；不同问题
- ❌ 单 top_k 降参治 zero_hit: top_k 是召回上限不是召回算法
- ❌ 算 call_rate 不算 pointer_rate: call_rate 粗（多 pointer 调用算 1 次），pointer_rate 细（每个 pointer 单独算）

## 参考

- `harness/scripts/analyze_retrieve_log.py:compute_consumption`
- `harness/health/checks/retrieve_hitrate.py`（zero_hit check）
- `harness/health/checks/retrieve_pointer_consumption.py`（call_rate / pointer_rate check）
