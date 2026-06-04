---
description: 文档更新直接替换为单一最新版，不留更替记录/取代横幅/版本号
priority: medium
status: active
trigger:
  keywords:
    - concept:doc
    - concept:changelog
    - concept:style
  tags:
    - doc
    - workflow
  stages:
    - implementation
    - delivery
last_updated: 2026-06-03
---

# 文档单一版本，不留更替痕迹

## 规则
一份文档只保留一个最新版，直接替换旧内容。**不要**在文档里写「取代 X.md / 已降级为过程稿 / 收敛某轮纠偏」这类更替横幅，**不要**标「权威版 / v2 / v3」。被取代的旧文档直接删掉，不保留。更替这件事只在 CHANGELOG 记一行就够。

## Why
用户明确要求（harness 任务，删除文档迭代时）：文档里挂「⚠️ 已被 X 取代…」横幅 + 标「权威版」是噪声，旧稿留着是垃圾。版本演进属于变更历史，CHANGELOG 已经在记，文档正文不该重复承载这种元信息。

## How to apply
写/改设计文档、方案、清单时：新版直接覆盖或新建单一文件，旧的同主题过程稿直接删除。文档标题不加版本/权威字样。需要交代「这版取代了谁、改了什么」时只写进 CHANGELOG，不写进文档正文。同时清掉别处对已删文档的悬挂引用。
