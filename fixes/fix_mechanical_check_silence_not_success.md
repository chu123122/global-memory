---
description: harness 机械检查"定位不到校验目标"时若静默跳过=不规范输入伪装成通过；必须给显式失败分支
priority: medium
status: active
trigger:
  keywords:
    - concept:gate
    - concept:lint
    - concept:validation
  tags:
    - harness
    - tooling
  stages:
    - debug
    - implementation
last_updated: 2026-06-04
---

# 机械检查的"找不到校验目标"必须判失败，不能静默跳过

> silence is not success。来源：`codex-work-flow-contract-tightening` / `check_phase_evidence.py` 硬化（archived）。

## 现象

写 gate/lint 类检查时，用"严格相等"定位要校验的目标（如表头列名 `h == "Green"`）；遇变体/不规范输入（表头写成 `Green结果`）时定位失败（`idx = None`），代码顺着"找不到就不查这一列"的分支走 → 该项被**静默跳过**，整体仍报 PASS。结果：不规范的 done 卡绕过"缺证据打回"，机械强制形同虚设。

## 根因

检查把"定位不到校验目标"与"校验通过"混为一谈。二者语义相反：前者是"无法判定"，后者是"判定为好"。默认走 pass 分支 = 把无法判定当通过。

## 修复

凡"先定位目标再校验"的检查，给"定位失败"一个显式 fail 分支：
- 上下文表明该检查本应适用（如 done 卡已出现「验收契约」标题）却定位不到关键列/表 → 判 **fail**，不是 skip。
- 真正不适用的旧格式（连标题都没有）才 skip。

参考实现：`harness/scripts/check_phase_evidence.py` 用 `find_contract_table` 返回 `(heading_present, table)` 区分"标题在不在"；标题在却定位不到 Green/证据列 → fail。

## 验证

构造变体表头的 done 卡跑检查 → 应 EXIT≠0 并指出"表头不规范/列定位失败"；合规卡仍 PASS。
