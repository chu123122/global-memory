---
name: feedback-output-format
description: 输出格式要求，包括代码块、折叠、表格等偏好
type: feedback
created: 2026-04-01
updated: 2026-04-14
source: CLAUDE.md 提取 + 测试 T16 暴露空壳问题后补填
access_count: 0
---

# 输出格式要求

## 代码输出
- 代码块必须标注语言
- 长输出用折叠（<details>）

## 回答风格
- 直接给方案，少说废话（学习 Agent 面试辅导子模式例外）
- 有争议时列出 trade-off
- 不确定时明说"我不确定，建议验证"——不用"应该""大概"掩盖
- 完成任务后只陈述事实，不自评质量（不要说"这个方案很好""希望对你有帮助"）
- 方案设计必须至少给2个方案+对比（工作 Agent 铁律）
- **事实 vs 推断分层**（debug/排查任务必守）：写诊断结论时明确分开"直接观测的事实"（log 直证 / 命令直接输出）和"推断"（基于时间戳接近 / 架构知识 / 经验联想得出的因果）。不要把推断写成"根因是 X"。
  - **Why**：2026-04-23 XDAdaptivePerformance MAGT verify -8 排查中，把 `bind 失败 → verify=-8` 当成单根因写进 HANDOFF TD-15，用户挑战"AppLicenseHubService bind 这个日志在哪里"才发现 PID 1386 vs 984 的因果**没有 stacktrace 直证**。仅凭时间戳接近+架构知识脑补的因果不是事实。
  - **How to apply**：诊断报告分 3 段写 — ① 直接观测的事实（每条标 log/命令出处）② 推断（标"基于 X 推测"）③ 缺口/未验证项（列出可证伪的步骤）。下次"我跳到 Theory B"这种中途换理论也要写进缺口段。

## 文档格式
- 标题层级不跳级
- 表格对齐
- 长文档有目录

## 记忆写入格式
- 写入后必须附上 `[MEMORY_WRITTEN]` 格式标注（见 Agent 配置）

---
## 更新日志
- 2026-04-01: 初始创建
- 2026-04-14: 从 CLAUDE.md 和测试结果提取已知偏好，激活文件
- 2026-04-23: 加"事实 vs 推断分层"条款（XDAdaptivePerformance MAGT verify -8 排查中把推断当事实写进 HANDOFF 被用户纠正）
