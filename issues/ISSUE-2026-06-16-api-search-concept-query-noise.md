---
issue_id: api-search-concept-query-noise
status: open
severity: major
created: 2026-06-16
source: game-proto-mapping 任务 Stage2「②查询实现」实测：用玩法概念查 api-search 返噪声，差点把正常 TS 自实现误标为"降级"
tags: [skill, spec, api-search, ue, retrieval, workflow]
---

# api-search 对"玩法概念"查询返噪声，且使用规范没规定要先拆 primitive

## 事实（现场，firsthand 验证 2026-06-16）

`ue-api-search-mcp`（`D:/UE5.7.4/AIDev/Tools/ue-api-search-mcp`，release）实测：

- **玩法概念查询 → 噪声**：
  - `"dodge roll with temporary invincibility frames"` → SpringCharacterUpdate / AnimMontageInstance / **NiagaraLensEffectBase**（无一相关）
  - `"drink potion to heal with limited charges"` → AbilitySystemTestAttributeSet / **InAppPurchaseReceiptInfo2**（喝药返了内购票据）
- **primitive 查询 → 真 API 在前排**：
  - `"sphere trace ... melee hit"` → `SphereTraceMulti` / `SphereTraceSingle`
  - `"apply damage to an actor"` → `ApplyDamage` / `ApplyPointDamage` / `ApplyRadialDamageWithFalloff`
- **confidence 几乎全卡 0.73~0.76**，噪声与真命中同分 → 无法靠 confidence 阈值筛。

后果：worker（gpt-5.5）执行「②查询实现」时直接拿"翻滚闪避/喝药/卷轴台/拾取"等**概念名**去查，拿回噪声后把它们一律标成"降级/自实现"——而这些本就该用 "primitive + TS 状态机" 正常实现，根本不是降级。可行性判断因此失真。

## 根因（疑似 skill / 使用规范缺失，非纯工具 bug）

- api-search 工具自述把输入描述成"**一句话自然语言需求**"，示例也偏整句概念（如 "spawn Niagara impact effect and play sound on projectile hit"），**没有规定**"玩法概念要先拆成 primitive 再查、概念名直接查会返噪声"。
- 因此**驱动 api-search 使用的那份规范/skill 没规范好**：调用方（worker/agent）按字面"一句话需求"去查概念，命中噪声却无从识别（confidence 不分相关）。
- 玩法概念本质 = primitive + 自定义状态逻辑的组合，RAG 对概念整句没有对应符号可命中——这是可预期的，规范本应提前说明并给出拆解流程。
- 待确认：这份"使用规范"最终该落在哪——工具自述 / 某个 skill / 还是 game-proto 流程的「②查询实现」方法定义。

## 影响

- 「②查询实现」误用：概念查询拿噪声，污染"能力→实现"映射。
- 正常 TS 自实现被误标"降级"，让可行性结论偏悲观、可能引发不必要的真降级。
- confidence 平铺无信号，调用方无法自动判断"这次查到的是真命中还是噪声"。
- 跨 run 复用：后续 2D/3D 各种切片生成都会重复踩。

## 修复方向（候选，未锁定）

1. **使用规范明确拆 primitive**：在驱动 api-search 的规范/skill 里写死——查玩法能力先拆成 primitive 需求（翻滚=冲量+计时+免伤标志；喝药=改血字段+计时），逐个 primitive 查；概念名不直接搜；confidence 当参考不当门槛、靠 symbol 名判相关。
2. **工具侧（可选）**：概念查询先自动拆 facet→primitive 再检索；对"无强命中"返回低置信/显式提示，而不是平铺一堆 0.74 噪声。
3. **方法侧**：把"先拆 primitive"固化进 game-proto 的「②查询实现」步骤定义，并明确"用 primitive+TS 状态机自实现 ≠ 降级"。

## 验收标准（修完怎么算好）

- [ ] 调用方拿到一个玩法能力时，会先拆 primitive 再查 api-search，不直接搜概念名。
- [ ] 规范/skill 里有可检查的条目说明该拆解流程 + confidence 不可作门槛。
- [ ] "用 primitive+TS 自实现"不再被误标"降级"；降级只对应真正缺失的 primitive。
- [ ] （若做工具侧）概念查询能给出"无强命中"信号或自动拆解结果。

## 负面清单（别做）

- 不要只在某次 prompt 里加一句"记得拆 primitive"——要落进可检查的规范/skill。
- 不要因为概念查询返噪声就判"这个能力做不了"——多半是查法错，不是能力不可行。
- 不要用 confidence 阈值过滤结果（实测不分相关）。

## 关联

- 触发任务：`D:/ClaudeTasks/active/game-proto-mapping`（Stage2 ②查询实现）
- 任务私有记录：`game-proto-mapping/ops/坑点.md` Issue 1（同一问题的本地实例 + 证据）
- 工具：`D:/UE5.7.4/AIDev/Tools/ue-api-search-mcp`
- 设计：`game-proto-mapping/design/设计文档.md`「建」流程 ②查询实现
