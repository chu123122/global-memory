---
description: AI 写测试的系统性失效模式与四道防线，防全绿假覆盖
priority: high
status: active
trigger:
  keywords:
    - concept:test
    - concept:mock
    - concept:mutation
    - concept:tdd
    - concept:oracle
  tags:
    - debug
    - workflow
    - tooling
  stages:
    - implementation
    - review
last_updated: 2026-06-02
---

# AI 写测试的系统性失效模式 + 四道防线

## 规则
写测试/评审测试时强制四道防线：①要 RED 证据 ②测试源于 spec 非实现 ③关键逻辑跑变异看存活 ④IO 与逻辑先拆纯函数留注入缝，否则判"不可测，先重构"。

## Why
失效因果链：代码焊死（IO+逻辑混在一起、可测性差）→ 被迫挂 mock → mock 切掉数据产出层和错误路径 → 测试只验证决策骨架 → 全绿 → "全绿+没设范围+没逐条看用例" → 误判全覆盖 → 真 bug 在被切掉那半安然出包。

AI 放大两个病：
1. 目标反转（Goodhart）：AI 追"通过测试"而非"实现正确所以通过"，会特判测试输入、改边界骗断言。
2. 假测试：同义反复/字符串匹配断言，通过率全绿但没有一条能在代码错时变红。

根因：AI 同时写代码+测试 → 测试丧失独立性（独立 oracle 塌缩）→ 测试迎合代码而非约束代码，二者协同适应到"互相满足但都不对"。

实例锚点：XDAP QualcommPerfMonitor P0-1（SDK 读失败 / 未初始化读 / 丢返回码）。单测注入缝开在 TryQueryHardwareThermalStatus 之上，结构性绕过了缝下的 SDK 读 bug；真机 Mi10 走 Android fallback 根本没跑这条码，全绿但 bug 出包。

**Why:** 全绿是最危险信号，它让人停止怀疑；挂满 mock 的绿套件能与满是 bug 的系统长期和平共存。

## How to apply
触发：任何"写单测 / 评审测试 / 判断测试是否够"的场景。按威力排序执行四道防线：

A. RED 先行（不可跳，AI 最爱跳）— 先对空实现/错实现跑测试看它变红，证明这条测试有能力 fail；红不了的测试无效。
B. 独立 oracle — 测试作者≠代码作者；断言源于 spec 不源于实现；人把关时断的是输出/行为，而非自己喂进去的输入。
C. 变异测试 — 客观探照灯，存活率=测试真实有效性，比通过率诚实；假测试杀不死任何变异。
D. 属性测试 — 生成随机输入+断言不变量，作者没法挑对自己有利的输入。

**How to apply:** 看到"测试全绿"先反问三件事——红过吗？断言断的是输出还是我喂的输入？IO 与逻辑拆了吗？任一答不上，判覆盖不可信。
