---
description: AI 摘要文档不可作为 ground truth — L3 落地前强制原文复核
priority: medium
status: active
trigger:
  keywords:
    - concept:summary
    - concept:verify
  tags:
    - doc
  stages:
    - delivery
last_updated: 2026-05-20
---

---
name: AI 摘要文档不可作为 ground truth
description: AI 跨页/跨文档总结的报告（如 GAP-REPORT、汇总分析）会发生精度衰减；落地到业务文档前必须按"重新 fetch 原文 + byte-equal 抄录"协议验证
type: feedback
---

# AI 摘要文档不可作为 ground truth — L3 落地前强制原文复核

## 规则

任何由 AI agent 跨页/跨文档**总结、对比、汇总**产出的报告（GAP-REPORT、综合分析、行动清单等），**禁止直接当作 ground truth 引用**到正式业务文档（PLATFORM_DATA_MATRIX / DESIGN / SPEC / HANDOFF / 代码注释）。引用前必须：

1. **重新 fetch 原始来源**（Confluence 当场拉，不读 archive 副本）
2. 数字 / 公式 / 接口名 / 设备名 / 配置字段名 **byte-equal 抄录**，不许改写或归纳
3. 引用处加注脚：`<!-- source: pageId#section, fetched YYYY-MM-DD -->`
4. "原文没明说但通识可补"的内容必须显式标 `[推算: XXX]`，不许伪装成原文事实
5. 文档内部矛盾（同一页字段语义自打脸）必须 flag，不许选一种当事实

## Why

2026-04-28 XDAdaptivePerformance 重构任务，对 27 篇 Confluence 页做了两轮 agent 摘要（GAP-REPORT v1 + v2，合并 25 条 P0/P1/P2 行动清单）。红队 agent 独立 fetch 5 条关键结论复核结果：**0 fabrication，但 3/5 PARTIAL**。错误模式高度集中：

- **数字反推当原文**：agent 用通识知识"补全"原文没写的细节（"NDK r27" 原文只说 Android 15；"OverdrawRatio = FragmentOverdraw/1000" 原文只说"1000 倍扩大需单位换算"）
- **范畴坍缩**：把状态本质不同的项目归一类（"恒返 -1"+"不返回结构体"合并成"9 项无效"）
- **总数无源**：算出"57 项"但本页根本找不到 57 这个数
- **出处张冠李戴**：结论对，但归错来源页（Honor Magic 6 来自不兼容设备登记，不是 300 台兼容测试）
- **拼写漂移**：`LateZKillRatio` vs 原文 `LateZKilledRatio`（少 "ed"），若代码引用就是接口名错
- **未标注内部矛盾**：原文字段中文注释和字段名互换，agent 当一致来源用

如果直接执行 GAP-REPORT v2 的 P0 落地，这些精度损失会被洗白成"经过对比修订的可信结论"写进业务文档，进而被未来代码引用 / 重构期决策依赖，**形成长期技术债**。

## How to apply

- ✅ **整页 byte-equal 搬迁**（如把 Confluence 页面整篇拷贝到任务文档）安全，可直接做
- ✅ **单字符 typo 修复**（如删多余 `c`）安全，可直接做
- ❌ **基于摘要报告的"修订/对比/合并"动作禁止直接落地**——必须当场重新 fetch 原页验证后再写
- ❌ **不要让 AI 引用归档 markdown（_archive/.../*.md）作为业务依据**——归档只用于"被搜索的索引 + 可被验证的快照"，不是引用源
- ⚠️ 红队验证成本约 30k token / 5 分钟 / 5 条抽样，**任何 AI 跨文档摘要报告产出后，落地前必须做一次红队抽样**，最少抽 3 条最关键结论
- 全局适用：本规则不限于 Confluence，覆盖所有 AI 跨源摘要场景（多文件代码 review 总结、多 PR 对比报告、多 issue 归类等）

## 配套档案

- 完整案例与红队报告：`D:/ClaudeTasks/active/xd-adaptive-performance-refactor/_archive/confluence-snapshot-2026-04-28/VERIFICATION-RED-TEAM.md`
- 错误模式分类汇总在该报告 `## 总评` + `## 逐条核对` 下
