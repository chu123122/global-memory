---
issue_id: long-discussion-plan-drift-entropy
status: open
severity: major
created: 2026-06-18
source: 用户现场反馈 + 本会话(global-memory-pull-architecture)活案例
tags: [workflow, work, design, compact, context]
---

# 长对话讨论后方案/出发点丢失，绕回原点，任务级无序度发散

## 事实（现场）

用户指出一个反复出现的模式：**在一个任务里讨论很久之后，原本的方案常常丢失不见、上下文情况丢失**，用户「不想再分析判断了」，而对话「绕回来绕回去，感觉和最开始又一样了」。即任务推进了很多轮，却回到了起点附近。

用户的怀疑（主根因假设）：**最开始设计文档阶段的「阶段划分」和「阶段卡」没写好（或没写），`/work` 流程被破坏，导致无序度发散**（任务级熵随对话长度单调增，没有抗熵锚）。

本会话即活案例（`global-memory-pull-architecture`）：
- 经历多次 `/compact`。方案在长讨论中反复摆动：「pull MCP 工具面」→ Phase A 证伪 →「全降级/别做」→「转去修 issue」→ 用户拉回「我的出发点是 RAG/MCP 灵感」→ 最终收口「call 可强制、deliver 过门」。
- 用户多次喊话纠偏：「为什么这个明明是你之前自己提出的，但是反推了问题」、「但是这不是我的出发点」、「目前的设计方案是什么？你还是没有和我讲清楚」。
- `design/设计文档.md` 虽有 Phase 表，但正文被讨论反复覆写/追加转向；阶段卡 `Phase2-*.md` 还停在「写入健康度测量」，而实际早已转向「RAG 跨项目召回 + deliver-gate」——**阶段卡与实际讨论严重脱节**。`HANDOFF.md` 的「当前目标」被某轮写死成「转向 B / gm_search 降级」，用户拉回 RAG 后未同步更新，**锚本身漂了**。

## 根因（用户假设 + 本会话观察，候选未锁定）

- **设计文档没有不可变锚区**：任务的「原始出发点 / 北极星 / 成功判据」没有一个短小、顶置、只追加不重写的锚。讨论一长，正文被新争论覆写，出发点被稀释。
- **compact 有损且偏向最近上下文**：长讨论 + 多次 compact 后，summary 抓的是「最近在争什么」，而非「最初要什么」。早期确立的出发点/已决结论被挤出窗口，AI 据此**重新论证已决问题（re-litigate）**，于是绕圈。
- **抗熵锚（HANDOFF/阶段卡）会漂且不强制同步**：阶段卡内容过时、HANDOFF「当前目标」滞后于讨论，本应抗熵的产物反而固化了某一轮的错误转向。
- **缺「出发点漂移」校准门**：`ISSUE-2026-06-15-work-discussion-before-implementation-gap` 已解决「新意图 vs 旧 task 目标」的边界校准，但**没覆盖「同一 task 内、长讨论中途，当前方案是否仍服务任务原始出发点」**的校准。本 issue 是其延伸。
- **Context Brief 注入了 handoff_path，但没注入任务原始出发点/当前阶段卡原文**，每次新窗口仍要靠 summary 重新概括，丢失放大。

## 影响

- 用户被迫一次次重述出发点、重新判断已决问题 → 认知负担、疲劳、信任下降。
- AI 反复 re-derive / re-litigate → token 浪费、推进效率塌陷、过度外推（见设计文档「推理反模式」节）。
- 设计文档失去「单一事实源」作用；下次 compact/handoff 继承错误/过时状态，发散自我放大。
- 实质：**任务级无序度随对话长度单调增，缺乏抗熵机制**。

## 修复方向（候选，未锁定）

1. **设计文档顶部强制「不可变锚区」**：`出发点/北极星 + 成功判据`，明令「只追加纠偏、不重写」。短、顶置、compact 不易丢。每次重大转向必须显式回答「是否仍服务此出发点」。
2. **阶段卡/HANDOFF 与讨论同步的硬约束**：重大转向时，先更新阶段卡 +「当前目标」再继续；或 compact 前自动校验「HANDOFF.当前目标 vs 最近 N 轮讨论」一致性，不一致报漂移。
3. **compact/Brief 注入锚点原文**：把「出发点 + 当前阶段卡 + 成功判据」原文带入下个窗口（不靠 summary 重新概括）。Context Brief 增一个 `north_star` 字段。
4. **绕圈/re-litigate 检测**：当本轮结论与早前已决结论重复或冲突时，提示「这点 X 已决为 Z，是要推翻还是忘了」，而不是默默重新论证。
5. **接到 intent-alignment 机制上**：复用 `work_context_pack.py --intent` 的校准框架，新增「task 内出发点漂移」检测（前者管 task 边界，本 issue 管 task 内长讨论漂移）。

## 验收标准（修完怎么算好）

- [ ] 长对话 / 多次 compact 后，AI 仍能**一字不差复述任务原始出发点 + 成功判据**（不靠重新概括）。
- [ ] 重大方案转向时，有可追溯的「是否仍服务原始出发点」判定记录。
- [ ] 设计文档阶段卡与实际讨论状态不脱节（有同步证据或漂移告警）。
- [ ] 用户无需反复重述出发点；不再出现「绕回原点」的现场报告。

## 负面清单（别做）

- 别只在 prompt 里加「记得别忘出发点」当解法——要有可检查的文档锚 + 流程门。
- 别用「更长的设计文档」对抗发散——文档越长，compact 越容易丢；锚区要短、顶置、不可重写。
- 别把每次小讨论都升级成重流程；轻量任务一条锚 + 一条纠偏即可。

## 关联

- 延伸自：`ISSUE-2026-06-15-work-discussion-before-implementation-gap`（管 task 边界校准；本 issue 管 task 内长讨论的出发点漂移）。
- 邻近：`ISSUE-2026-06-16-context-brief-no-usefulness-feedback-loop`。
- 活案例：`D:/ClaudeTasks/active/global-memory-pull-architecture`（`design/设计文档.md` 推理反模式节 + 阶段卡脱节）。
- 相关机制：`skills/work/v1/SKILL.md`、`harness/work_context_pack.py --intent`、HANDOFF / 设计文档 / 阶段卡 / Context Brief 注入。
