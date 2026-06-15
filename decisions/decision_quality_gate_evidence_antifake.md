---
description: Tier2 证据门自身可被假证据糊弄(Goodhart 递归)；治标黑名单已落，治本事实门挂起
priority: medium
status: active
trigger:
  keywords:
    - concept:gate
    - concept:test
    - concept:tdd
    - tool:quality_gate
  tags:
    - tooling
    - design
    - workflow
  stages:
    - implementation
    - review
last_updated: 2026-06-10
---

# Tier2 证据门防伪：黑名单治标 / 事实门治本（挂起）

## 决定

`quality_gate.py` 的 Tier2 强证据门——`test-quality` review 须含非空 `Red-Evidence` + `Mutation` section，由 `has_concrete_evidence()` 校验——**只落治标层（黑名单兜底），治本层（事实门）挂起待定**。

- 治标（已落）：`has_concrete_evidence` 黑名单挡裸空 + 占位符（`none/n/a/无/na/tbd/todo`）。挡掉最低级造假：空填、写"无"。
- 治本（挂起）：`Red-Evidence` 须引**可验证 ref**（git SHA / CI run id），门去 resolve 该 ref、验证它真对应一次 red run。未实现。

## 理由（为何治本挂起，不是不做）

门的目的是防"假测试证据"，但门自己也只是文本匹配 → **Goodhart 递归**：门能被它本要拦的同一手法糊弄。本会话 `/code-review`（recall 偏向，8 findings，#1/#2/#3 为核心）确认：写任意一行非黑名单字符串（如 `Red-Evidence: 测过了`）即过门，没有任何机制验证 red run 真发生。

治本挂起的成本/ROI 顾虑：
1. 事实门需门能访问 git/CI，脚本当前不连外部 → 耦合 + 跨平台成本高。
2. 纯机械 ref 校验仍可被"伪造一次 red commit"糊弄 → 证据真实性的最终保证仍是**独立 oracle**（人 / 测试作者≠代码作者），见 `feedback/ai-test-failure-modes-four-defenses.md`。机械门只是抬高造假成本，不消除。
3. Tier2 当前风险档：黑名单已够挡无意识省略（AI 最爱的"留空跳过"），主动伪造属 Tier3 才需硬防。

故：先黑名单，治本等到出现真实绕过实例或 Tier 升级再上。

## 现状（本会话落地状态，ephemeral）

- gate 代码已在 **live `D:/global-memory`**：`quality_gate.py`（`REVIEW_EXTRA_REQUIRED_SECTIONS` / `has_concrete_evidence` / evidence_state 接线）、`quality_gate.yaml`（`test_quality_red_evidence: true`）、tests（+4 用例，16 passed）、`QUALITY_GATE.md`、VERSION（已 1.5.0）。
- **审计漏记**：`CHANGELOG.md` 顶部无本次 Tier2 门条目（违 MEM-01🔒，补记是 TODO）。
- **未 commit**：本会话约 17 处改动未提交，提交是用户动作。
- 配套记忆：`feedback/ai-test-failure-modes-four-defenses.md`（AI 假测试四道防线，本门是其 RED-先行防线的机械化落点）。

## 复审条件

- 出现"填假 Red-Evidence 骗过门"真实实例 → 上事实门（ref 引用 + resolve 校验）。
- Tier2 升 Tier3 或门覆盖到对外交付 → 要求更硬证据（CI 链路 / 双人 oracle）。
- `has_concrete_evidence` 黑名单被发现可绕（如 markdown header 混入、长度为 0 的 ref）→ 收紧（见 code-review #1 patch 候选：黑名单 + 最小长度）。
