---
description: gm_search 实测坐实"阈值-only gate 在小杂库不稳"；穷举 golden 方法论 + 三次"测错战场"反模式
priority: high
status: active
trigger:
  keywords:
    - concept:rag
    - concept:abstain
    - concept:similarity
    - concept:threshold
    - concept:golden
  tags:
    - memory
    - design
    - tooling
  stages:
    - discussion
    - implementation
    - review
last_updated: 2026-06-18
---

# gm_search deliver-gate 实测：阈值-only 在小杂库不稳（坐实 + 方法论）

## 核心要点

- **坐实了姊妹篇结论**（`knowledge_rag_abstain_similarity_not_intent`）：embedding cosine 衡量"像不像"≠"该不该答"。gm_search deliver-gate 三轮标定（0.62→0.590→0.622）反复证明——**小杂库里"通用技术问法但本库无对应"的负例（JS TypeError / Python ImportError / Docker permission）和真实经验正例高度交叠**，任何全局阈值都剃刀边缘。
- **0.590 在 21 条 golden 上看着稳，是过拟合**：穷举扩到 74 正/20 负立刻被 3 条通用技术负例击穿（0.593/0.621/0.594）。升到 0.622 达 FP=0，但分离裕度仅 0.0029——语料一变又会塌。**阈值-only gate 本质不稳，根治唯一路径 = 本地 LLM query-intent / rewrite（HyDE），不是再调阈值。**
- **pull 模式的正确标尺**：gm_search 是 AI 主动调、拿 pointer+summary 自筛的 pull 工具（判断归 AI）。不套"推模式每轮硬塞"的精度标尺。门的职责 = abstain + dedup + bound + 不投冒充"答案"的字段；最终相关性由 AI 读 summary 判。连更成熟的 UE RAG 模板（带远程 LLM）最后都退回"让调用方判相关、confidence 不当门槛"。
- **去噪到头的三选一裁决**（可迁移决策框架）：① 纯检索侧 cosine 门 → **否决**（要控精度得关 vector_only，赔掉跨语言/换说法召回）；② 本地 LLM 查询拆解 → **根治但加延迟**（park 为触发器，dogfood 真被噪声带偏再上）；③ AI 自筛（pull）→ **采纳**（小杂库最务实落点）。
- **金色战场 = 跨项目召回**：repo 内 grep 是更好的原生 pull 工具（file:line 精确 > pointer+summary），gm_search 真主场是"别的项目目录里、grep 够不着 global-memory"的跨项目/跨会话/换说法召回。**限定场景，不与 grep 竞争 repo 内检索。**

## 穷举 golden 方法论（小语料优势 + 防偏差）

- **小语料可穷举**：global-memory ~116 文件，核心 4 类（feedback/knowledge 非 docs/decisions/fixes）~69 条可全覆盖。穷举 golden 比小样本（21 条）稳得多——能暴露过拟合、发现更多天花板 case。
- **关键防偏差：query 必须"措辞漂移"**。用文件正文/description 里**没出现**的词问同一件事（测语义召回，不是关键词命中）。**禁抄 description**——自造 easy query 会让 recall 虚高、阈值标假。抽审方法：随机抽 N 条，核 query 词汇是否漂移。
- **query 分布匹配真实使用**：中文为主（~90%）+ 少量英文/换说法（~10%）。全英文会虚高天花板 case 比例。
- **injection-aware 口径**：已每轮自动注入的内容（如全局铁律 R17/R18/R9 在 CLAUDE.md）**不该用检索评测**——用检索测"召一个已在上下文里的东西"是伪需求。标 `injection_covered` 移出检索分母。逐条核实（别一刀切：像"记忆写入触发表"在 `rules/沉淀层.md` 没注入，是真检索需求，保留）。
- **负例要含"通用技术问法但本库无对应"**（JS/Python/Docker 报错类）——这类最容易骗过向量阈值，是关键压测点，别只挑明显离题（天气/写诗）。
- **FP-约束标定**：最大化正例投递 s.t. 负例 0 击穿；报分离裕度（最低回收正例 - 最高负例），裕度 <0.02 如实标"脆弱"。

## 三次"测错战场"反模式（本任务反复出现，值得警觉）

1. **Phase A**：在 global-memory repo **内**测 gm_search——grep 主场、工具最劣场。结论"AI 不调 search"过度外推到"整套别做"。（实则是测错战场。）
2. **0.590 标定**：在 21 条小 golden 上调阈值，看着稳就 commit。穷举一上立刻被击穿——**样本太小不代表真实分布**。
3. **p07 评测**：用检索去测一个**已每轮注入**的规则（R17）——标尺用错（注入覆盖的不该评检索）。
- **共性根因**：强先验 + 确认偏误 + 对自己结论不上验证。解法：测前先问"我测的是完整设计还是阉割版？样本够不够？标尺对不对？"；对自己结论用对 worker 的同一把尺（固定题集 + 期望答案 + 盲评）。

## 常见误区

- **误把"阈值调到 FP=0"当解**。小杂库里 FP=0 的阈值必然剃刀边缘（裕度<0.02），语料一变就塌。FP=0 ≠ 稳健。
- **以为 dedup / top-N cap 能去噪**。噪声是"向量召回但语义跑偏的不同文件"，按不可靠 rank_score 与正确结果**交错**排——dedup 删的是正确文件重复 chunk，cap 在固定题集 `dropped_by_cap=0`。真正去噪要 query-pointer 语义一致性门（需 LLM）。
- **把 intent_matches/suggested_answer_refs 当主投递**。它们以"答案"形式出现比单纯 pointer 更危险（冒充权威）。pull 模式里主投递只该是 pointers，AI 读 summary 自筛。
- **用推模式精度标尺量 pull 工具**。推模式怕噪是每轮硬塞且无反馈；pull 是 AI 主动调、可自筛。55% pointer 精度 + summary，AI 扫一眼能丢掉跑偏的。

## 参考

来源任务：`global-memory-pull-architecture`（gm_search deliver-gate + 穷举 golden + 阈值标定三轮）。
姊妹篇：`knowledge/knowledge_rag_abstain_similarity_not_intent.md`（抽象结论：相似度≠意图）+ `knowledge/knowledge_ue_rag_template_copy_boundary.md`（UE 模板可抄/不可抄边界：精度来自 LLM query rewrite，非免费 hybrid/RRF）。
实测证据：`D:/ClaudeTasks/active/global-memory-pull-architecture/test/gm_search_gate_core4_exhaustive_*.{json,md}` + `gm_search_threshold_calibration_core4_exhaustive.{json,md}`。
已 commit 阈值：0.622（commit `22136a3`）；诚实标"剃刀边缘、根治待本地 LLM"。
