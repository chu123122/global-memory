---
name: interview-mock-history
description: 模拟面试记录与评分
type: interview
created: 2026-04-01
updated: 2026-04-01
source: 学习 Agent
access_count: 0
---

# 模拟面试记录

## 评分标准
- 知识准确性：/5
- 表达清晰度：/5
- 追问应对：/5
- 综合评分：/5

## 历史记录

### 模拟面试 #1

**日期：** 2026-04-14
**主题：** C++多线程
**来源：** T38 系统自测模拟面试

| # | 问题摘要 | 评分 | 关键问题 |
|---|---------|------|---------|
| Q1 | mutex+cv有界队列实现 | 4.5/5 ✅ | notify_one选择依据未提 |
| Q2 | atomic memory_order区分 | 2.5/5 ⚠️ | acq/rel vs seq_cst语义混淆 |
| Q3 | DCLP单例+内存模型 | 0/5 ❌ | 完全不了解，需专项学习 |

**综合：** 2.5/5 — mutex/cv基础稳，atomic高级语义+DCLP是空白
**行动项：** 专项学习 DCLP + memory_order acq/rel vs seq_cst 区分场景

---
## 更新日志
- 2026-04-01: 初始创建
