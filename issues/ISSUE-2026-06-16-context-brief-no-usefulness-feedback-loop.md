---
issue_id: context-brief-no-usefulness-feedback-loop
status: open
severity: major
created: 2026-06-16
source: global-memory-semantic-retrieval-survey 任务 C 阶段日志分析：近 14 天命中 741 次只 8 次 Read pointer，引出"无法判断注入是否有用"的根因
tags: [retrieve, context-brief, metrics, feedback-loop, governance, injection]
---

# Context Brief 注入缺"有用度"反馈回路，无法判断检索是否真帮上忙

## 事实（数据，2026-06-16）

- log-analyst 只读分析 `~/.claude/logs/retrieve_calls.jsonl`：
  - 近 14 天 968 次 retrieve 调用，zero-hit 20.8%。
  - 有命中的 741 次里，**只有 8 次后续真的 Read 了任一 pointer**（pointer ≈10/1562，pointer_rate ≈0.6%）。
- 表面看像"注入了没人读 = 没用"，但**不能据此判定无用**：上次修复（`decisions/decision_retrieve_injector_feedback_failure.md`）已把 summary 内联进 pointer，AI 可直接吃摘要、无需 Read → "用了摘要"在 Read 指标里不可见。
- 反过来也**证明不了有用**。

## 根因：缺消费端反馈回路（这是问题本质）

"有没有帮上忙"是**因果/反事实**问题：需比较"注入 vs 不注入"两分支的结果差。但日志只有一个分支、且无"结果好坏"标签。

现有指标全是**上游代理**，无一测**下游结果**：
- `call_rate`（检索跑没跑）/ `zero_hit`（命中没命中）= 生产端
- `pointer_rate`（读没读）= 半消费端
- ❌ 缺：注入有没有改 AI 决策 / 让结果更好

且代理双向都不准：读了≠有用（可能与 AI 已知重复）、没读≠没用（摘要已在 context 吃掉）。

**核心**：生产端忠实记"注入了啥"，消费端从不回报"有没有用"。没这个回路 → 改注入策略多少次都没有结果信号判好坏 → "修了还是一样"的真因（不是修得不对，是没标尺看是否修对）。

## 影响

- retrieve/Context Brief 的任何优化（RAG、alias、注入策略）都在**盲飞**：无法验证 ROI，易陷入"改了-没感觉-再改"循环。
- 本任务的 RAG PoC、关键词调优 ROI 评估，都因缺此信号只能停在"方向判断"而非"效果验证"。
- 与 `archived/harness-context-governance/FUZZY-AND-FEEDBACK-GAP.md` 的"推荐系统强/弱反馈回路缺口"是同一问题，已有方法论可接续。

## 现场实例（2026-06-17，firsthand）

来源：用户在一次"分析 loop engineering + 设计多 agent 调度"的对话中，质疑"为什么 global-memory 检索命中了 `knowledge_skill_design.md`"。核实后拆出两个不同现象，正好印证本 issue 的反馈回路缺口。

**(A) 注入噪声，但 pointer_rate 测不出。** 该轮 Context Brief 注入 3 条指针：`decision_retrieve_injector_feedback_failure`（`kw:concept:memory`，相关）+ `aik-refactor-ui-provider/复盘.md`、`设计文档.md`（`kw:concept:ui`，**与 loop/agent 主题无关**，靠可疑的 `concept:ui` alias 扩展命中，该轮 warning 含 `alias_expanded`）。AI 当轮 Read 了 0 条。

- 关键：这个 `pointer_rate=0` 同时混了两种情况——2 条是**无关噪声**（不该读）、1 条**摘要已够**（不必读）。上游指标无法区分，正是本 issue 的核心（read≠useful、no-read≠useless）。3 条里 2 条是噪声 → 该轮注入信噪比很差，但日志侧完全看不到。

**(B) AI 主动过度读，连注入账本都不在内。** 同轮 AI 自己 Read 了**未被注入**的 `knowledge/knowledge_skill_design.md`（探索期"顺手抓个 knowledge 样例"），内容是 Skill 撰写规范，与任务无关、且与后续读的权威模板冗余。

- 关键：用户最初以为是"检索命中"，实为 AI 自主读。这类"AI 主动拉边缘文档"的上下文成本，连 retrieve 日志的 injection 账本都不记录 → 比本 issue 描述的盲区更靠下游，现有任何上游代理都测不到。

**对本 issue 的含义**：单看该轮 `pointer_rate=0`，既可解读成"注入没用"也可"摘要够用"，还漏掉 AI 自主读的成本——三种都无信号。再次证明：不补下游"有用度/有没有被误导"信号，注入与探索的信噪比都无法评估。

## 修复方向（候选，未锁定）

1. **消费端显式反馈（个人 harness 唯一可行下游信号）**：让 AI 每轮/按需回报极轻量信号——`context_brief: {used: yes/no, pointer: <path>, helped: yes/no/misled}`，落日志聚合。缺点=自报偏差，但有总比无强。
2. **弱信号兜底**：检测 AI 当轮输出是否引用了注入 pointer 的路径/内容（比 Read 强，仍非因果）。
3. **A/B ablation（金标准，但个人 harness 不现实）**：随机注入/不注入比任务结果——需"任务成功"指标 + 样本量。
4. 先接 `FUZZY-AND-FEEDBACK-GAP.md` 的旧分析，确定先做哪种信号。

## 验收标准（修完怎么算好）

- [ ] 有一个**下游**信号（哪怕弱/自报）能聚合出"注入是否被使用/是否有用"，而不只是 call/zero_hit/pointer 三个上游代理。
- [ ] 能用该信号判断一次注入策略改动是"变好/变差/无差"，不再盲飞。

## 负面清单（别做）

- 不要继续只优化上游代理（zero_hit/pointer_rate）当"变好了"——它们测不到有用度。
- 不要因 pointer_rate 低就直接判"检索无用"（摘要内联使 Read 不可见）。

## 关联

- 触发：`global-memory-semantic-retrieval-survey` C 阶段（archived）
- 旧分析：`archived/harness-context-governance/FUZZY-AND-FEEDBACK-GAP.md`、`Context_Brief_深度分析.md`
- 相关：`decisions/decision_retrieve_injector_feedback_failure.md`、`knowledge/knowledge_retrieve_metrics_taxonomy.md`、`decisions/decision_retrieve_optim_roi_priority.md`
