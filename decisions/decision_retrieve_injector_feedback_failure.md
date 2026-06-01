---
description: retrieve 注入器对 feedback 无效(命中0.33%)；feedback 走 CLAUDE.md 毕业路径而非 JIT 指针注入
priority: high
status: active
trigger:
  keywords:
    - concept:retrieve
    - concept:injection
    - tool:retrieve_inject
    - concept:feedback
    - concept:memory
  tags:
    - memory
    - tooling
    - infra
    - design
  stages:
    - discussion
    - implementation
last_updated: 2026-06-01
---

# retrieve 注入器对 feedback 失效 → feedback 走 CLAUDE.md 毕业路径

## 决定
1. retrieve 每轮注入**只保留 handoff，砍掉 memory pointer**（feedback/fixes/knowledge/decisions 指针）。
2. `feedback/*.md` 定位为**暂存/复审队列**，不是 JIT 注入源；够格的 feedback **升进 CLAUDE.md** 常驻，靠永远在场生效，而非靠关键词撞 + 指针。

## 备选方案
- **A 拉高 min_score 阈值**：否决。召回 99.9% 已是满分关键词命中，阈值无区分度，拉高几乎零效果。
- **B 意图门控**（仅检索意图词时注 pointer）：否决。过度设计——pointer 命中率上限 0.82%，"更聪明地注入"还是注废物，且动 hook 控制流风险高。
- **C 砍 pointer 只留 handoff**（选定）：删代码路径、低风险、损失 ≤0.82%。
- **D 注入内容而非指针**：搁置。关键词匹配器判断不了"真相关"，注内容=注噪声 + 高 token。

## 理由
近 30 天实测（read-only 日志分析）：
- 注入 4808 条 pointer，**94% 是 feedback**（4546 条）。
- feedback 被 Read 仅 15 次/30 天 → **0.33% 命中**。pointer 整体命中率上限 39/4769=0.82%（对齐 taxonomy pointer_rate 0.7%）。
- **pointer 带 summary 字段 = 0%**：每条只有 `path + why:kw:X`，无内容预览。

AI 不读的根因（按权重）：
1. **类目错配**：feedback 是行为规则（决策时须在场），被做成"留路径自己 fetch"的参考资料。规则不能靠面包屑生效。
2. **给指针非内容**（summary 0%）：`kw:concept:X` 标签只说明匹配器为何触发，不说值不值得读。
3. **brief 自带 `load_strategy: just_in_time`**：字面叫 AI 推迟，"要用时"很少到来。
4. **被标 background 非 instruction**：系统提醒明示低权威，AI 降优先级。
5. **关键词形状≠需求形状**：看不见上下文已有什么，撞词即注。

对照：handoff 读回率 68%（正式任务整会话口径），因为它是**需求形状**——任务恢复这一正确时刻交付正是需要的状态。

## 适用范围
- 适用：本机 harness 的 retrieve_inject 注入策略、feedback 记忆的流转路径。
- 不适用：handoff 注入（保留，已证明有效）；fixes/knowledge 作为"按需查"参考仍合理（模型自己 Grep/Glob 命中，30 天 fixes 读 12 / knowledge 读 13，靠自检索而非注入）。

## 复审条件
- 若 retrieve 输出加入**真实相似度 score 字段** + **summary 预览**，可重评"注入内容而非指针"方案 D。
- 若 readback_audit.py 显示 handoff 读回率跌破 ~40%，重评 handoff 注入是否也需改进。
- 若 CLAUDE.md feedback 毕业路径导致其膨胀超载（已 181 行），需另设分层加载机制。

相关：[[knowledge_retrieve_metrics_taxonomy]]（zero_hit/pointer_rate/call_rate 指标定义）
