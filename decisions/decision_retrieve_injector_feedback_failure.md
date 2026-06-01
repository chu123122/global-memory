---
description: retrieve 注入改类型选择性(feedback排除/fixes-knowledge带summary)+CN alias桥+经验升进global-memory
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

# retrieve 注入器修复：类型选择性 + summary 投递 + CN alias 桥

> 演进记录：最初结论是"砍掉所有 pointer 只留 handoff"（commit 1e0d850）。后续发现注入器的失败
> 是三个**可修的输入洞**叠加，机制本身有价值，遂改为下方的类型选择性方案（8219213/79e5809/5e9b5a3）。

## 决定
1. retrieve 每轮注入采用**类型选择性**：
   - **feedback/*.md：从注入排除**。feedback 是行为规则，须决策时在场 → 升进 CLAUDE.md 常驻，不靠关键词撞指针。
   - **fixes/knowledge/decisions：保留注入**，且由裸指针升级为**带 summary 预览**（召回回退 `description` 一句话），AI 直接吃免再 Read。
2. `feedback/*.md` 定位为暂存/复审队列 + CLAUDE.md 毕业源，非 JIT 注入源。
3. 召回侧引入**中央 alias 桥**（`triggers_aliases.yaml`）：中文 query（安卓/打包/重签名/obb/真机等）映射到英文 canonical 关键词，命中英文标签的 doc。改 per-doc 双语为中央表，避开 lint 5-keyword cap 与 overtagging。
4. 够格经验**升进 global-memory/fixes**（如安卓打包坑 5e9b5a3），经 alias 命中 + summary 注入闭环生效。

## 备选方案
- **A 拉高 min_score 阈值**：否决。召回 99.9% 已是满分关键词命中，阈值无区分度。
- **B 意图门控**（仅检索意图词时注 pointer）：否决。过度设计——纯指针命中率上限 0.82%，"更聪明地注入"还是注废物，且动 hook 控制流风险高。
- **C 砍 pointer 只留 handoff**：阶段性采纳（1e0d850）后**被 C′ 取代**。
- **C′ 类型选择性注入**（最终选定）：feedback 排除、fixes/knowledge/decisions 带 summary 保留。删代码路径风险低，且不丢跨 task 浮出的真价值。
- **D 注入内容而非指针**：**已部分落地**（8219213 summary 投递 = D 的核心），不再"搁置"。

## 理由
近 30 天实测（read-only 日志）暴露三洞，分属三层，全部可修：
- **洞1 = 匹配层**：有 schema 也撞不上（中文 query ≠ 英文 canonical kw）。
- **洞2 = 索引层**：最该撞的 doc 不在 retrieve 索引域（卡在 CLI 自动记忆）。
- **洞3 = 投递层**：撞上了也不读（pointer 无 summary，AI 不点裸路径）。

逐洞: 
- **洞3 投递**：原 pointer 带 summary 字段 = 0%，每条只有 `path + why:kw:X`，AI 系统性不读（pointer_rate 0.7%）。→ 8219213 召回回退 `description`，fixes/knowledge/decisions 注入带一句话预览，命中即可用。
- **洞1 召回**：中文 query 撞不上英文 canonical 关键词（"安卓"≠`platform:android`，ambiguous_keyword 占空命中 96%）。→ 79e5809 中央 alias 桥。
- **洞2 覆盖**：安卓打包经验卡在 CLI 自动记忆（retrieve 不索引），最相关 doc 根本不在候选集。→ 5e9b5a3 升进 global-memory/fixes。

为何 feedback 仍排除、fixes/knowledge 保留：feedback 是行为规则（须决策时在场，靠面包屑无效，归 CLAUDE.md）；fixes/knowledge 是按需查参考，配 summary 后注入成本低、命中即省一次 Read，投递价值由负转正。原"≤0.82% 损失"只对纯裸指针成立。

为何 alias 选中央表而非 per-doc 双语：per-doc 加中文关键词撞 lint 5-keyword cap + 制造 overtagging（关键词术语须出现在正文）；中央表解耦召回词与 doc 标签，一处维护惠及所有 doc。

对照：handoff 读回率 68%（正式任务整会话口径），因为它是**需求形状**——任务恢复正确时刻交付正需要的状态。

## 两层架构（2026-06-01 追加，洞2 第二条路）

洞2 起初只靠**手动升进** global。后续定为**两层结构**，升进降级为例外：

- **前者 = global 库**（`global-memory/{feedback,knowledge,fixes,decisions}`）：跨项目、稳定、进 git、独立可用。
- **后者 = 局部层**（CLI 自动记忆 `~/.claude/projects/<slug>/memory`）：项目专用（局部）、按 cwd 隔离、**不进 global 库**。后者依赖前者（共用打分/alias），前者不读后者。

为何不是 A（把局部目录直接并进 global 索引）：破"global 唯一存储"、局部项目噪音污染全局排序、CLI 记忆无 git 备份却被当权威源。
为何不是纯 B（全量升进 global）：局部内容大多项目专用，批量升进 = 用局部噪音污染全局库。只有**真跨项目**的才手动升进（如安卓打包坑 5e9b5a3）。

机制（commit 2c91a04）：`retrieve(project_memory_root=...)` 扫当前项目 CLI 记忆，独立低阈值 0.3（让无 trigger.keywords 的 CLI 文件靠 description 回退浮出）、上限 1 条、标 `source:task-local`、缓存与 global 物理隔离。无匹配项目目录自动跳过（隔离）。起步仅 description 匹配，不读正文。

## 适用范围
- 适用：retrieve_inject 注入策略、retrieve 召回（alias/summary）、feedback 流转、经验升进路径、**项目局部记忆层**。
- 不适用：handoff 注入（保留，已证明有效）。feedback 仍排除注入（走 CLAUDE.md）。global 库不受局部层影响（依赖单向）。

## 复审条件
- 若带 summary 的 fixes/knowledge/decisions 注入经 `readback_audit.py` 显示读回率仍 <5%，重评是否对这三类也收紧为纯按需 Grep。
- 若 alias 表膨胀致误召回（中文词映射过宽撞无关 doc），对 `triggers_aliases.yaml` 加精度审计。
- handoff 读回率跌破 ~40% → 重评 handoff 注入。
- CLAUDE.md feedback 毕业膨胀超载（现 181 行）→ 分层加载机制。
- 真正新颖的改写/同义仍漏（alias 治不了）→ 评估上 embedding 语义检索（需常驻 daemon 抱模型，因 hook 每轮新进程冷加载撞 1.0s 超时）。
- 局部层（task-local）读回率一周后经 `readback_audit.py` 看：<5% → 评估是否上正文匹配或撤层；误召回多 → 调高 `PROJECT_LOCAL_MIN_SCORE`。
- CLI 局部记忆始终无 git 备份：若丢失痛点显著，单独给 `~/.claude/projects/` 加备份，**不**靠塞进 global 顺带解决。

相关：[[knowledge_retrieve_metrics_taxonomy]]（zero_hit/pointer_rate/call_rate 指标定义）
