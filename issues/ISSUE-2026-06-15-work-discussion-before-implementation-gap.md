---
issue_id: work-discussion-before-implementation-gap
status: closed
severity: major
created: 2026-06-15
closed: 2026-06-15
source: global-memory 维护讨论纠偏：旧 task 方向被判定错误
tags: [workflow, design, work]
---

# Work 在实现前的讨论阶段缺少方向校准门

## 事实（现场）

用户指出：当前这件事本身就是一个任务，之前 task 的方向错误了。真正要推进的是 `AGENTS.md` / `agents/CLAUDE.md` 的 global-memory 接入式入口 prompt，以及“PR-shaped”改动过滤机制；而不是继续沿 `global-memory-oss-readiness-hardening` 的开源成熟度治理方向推进。

这说明 `/work` 在进入实现前的讨论阶段仍不完善：它能加载上下文和延续既有 task，但对“当前意图是否已经偏离旧 task 目标”的校准不够强，容易把新需求吸收到一个看似相关、实际方向错误的旧任务里。

2026-06-15 追加纠偏：设计审查通过后，主模型不应直接派实现。应先向用户反馈大致方案、计划、取舍和边界，让用户知道“准备怎么做、为什么这样做、不会做什么”，得到确认后再进入实现或派 worker。设计审查结果不是实现授权。

## 根因

- `work_context_pack.py --intent` 能提示当前匹配到的 task，但后续流程更强调“继续 HANDOFF / Phase”，缺少一个强制的“方向复核”产物。
- Step 1 对“继续老任务”要求确认，但确认重点是“上次进度 X，本次继续 Y”，没有要求把用户的新意图与 task 原目标逐项比对。
- Step 2.5 能把讨论结论落地，但没有前置要求先判定：这是旧 task 的新 Phase，还是应新开 task / 关闭旧方向。
- 设计审查后的交互门缺失：审查报告回到主模型后，没有要求先给用户反馈方案概要和执行计划，而是可能直接进入实现。
- 当前流程对“实现前讨论”缺少可验证证据，导致错误方向可能在实现前没有被记录成 issue 或决策。

## 影响

- 新任务会被旧任务上下文吸走，导致讨论和实现都围绕错误成功判据推进。
- 任务文档会保留“看起来连续”的状态，但真实用户目标已经换轨。
- 后续派生给 GPT/worker 实现时，输入会继承错误边界，放大返工成本。
- 用户无法在实现前看到计划和取舍，导致“设计审查通过”被误用成“用户已授权实现”。

## 修复方向（候选，未锁定）

1. **新增方向校准门**：在 `/work` Step 1 和 Step 2 之间加入“intent alignment”检查，明确输出：用户新意图、当前 task 目标、是否同一任务、若不是则新建 task / 开 issue / 更新 HANDOFF。
2. **讨论阶段产物化**：在进入实现前，要求至少落一条 `ops/决策队列.md` 或 issue，记录“为什么继续旧 task / 为什么新开 task”。
3. **PR-shaped 改动包前置**：对 global-memory 维护类改动，先生成本地改动包说明，回答“为什么改、改什么、不改会怎样、验证证据是什么”，再允许进入实现。
4. **worker 派生前校验**：给 GPT/worker 的任务包必须带 `Intent / Decisions / Boundaries / Task`，并包含方向校准结论；缺失则不得派生。
5. **设计审查后用户确认门**：设计审查报告回传后，主模型必须先向用户反馈方案概要、执行计划、风险/取舍和待确认点；用户确认后才允许进入实现派工。

## 验收标准（修完怎么算好）

- [x] 当用户意图与当前 task 目标不一致时，`/work` 流程会显式建议新建 task 或开 issue，而不是默认续跑旧 task。
- [x] 继续旧 task 前，有可追溯的方向校准记录，能说明为什么它仍属于当前 task。
- [x] 实现前讨论结论有固定落点，不只停留在聊天上下文。
- [x] 对 global-memory 维护改动，PR-shaped 改动包能在实现前暴露动机、范围、证据和风险。
- [x] 设计审查通过后，用户能先看到方案概要和计划；没有用户确认时，不直接派实现 worker。

## 关闭记录（2026-06-15）

处理任务：`D:/ClaudeTasks/active/work-intent-alignment-gate`

修复摘要：

- `harness/work_context_pack.py --intent` 现在在无显式 `--task` 且命中高置信新 work/task 意图时，对 `cwd` / `task_resolver` / `session_task_file` 等自动解析到旧 task 的场景返回 `intent_guard.action=create_task_or_confirm`。
- 真实复现串 `triage 选择 issue: work-discussion-before-implementation-gap，进入 work 路径...` 现在返回 `level=WARNING`，推荐 `create_task.py` 或显式确认继续旧 task。
- 显式 `--task work-intent-alignment-gate` 不误拦；普通继续和 `继续维护当前 task Phase 2 实现` 不误报。
- 实现前确认门与 worker 派发包约束已在 work skill / Codex adapter 中存在，本轮用 `Intent / Decisions / Boundaries / Task` 派发并留痕。

验证证据：

- `pytest harness/tests/test_work_skill_tdd_rules.py -q` → `21 passed`
- `python C:/Users/XINDONG/.claude/scripts/work_context_pack.py --intent "triage 选择 issue: work-discussion-before-implementation-gap，进入 work 路径，解决 /work 在实现前缺少方向校准门的问题" --json --write-status` → `level=WARNING` + `intent_guard.action=create_task_or_confirm`
- `python C:/Users/XINDONG/.claude/scripts/work_context_pack.py --task work-intent-alignment-gate --intent "triage 选择 issue: work-discussion-before-implementation-gap，进入 work 路径，解决 /work 在实现前缺少方向校准门的问题" --json --write-status` → `level=PASS`，无 `intent_guard`
- `python harness/scripts/quality_gate.py verify --review-dir %TEMP%/work_intent_quality_reviews_v2 --path harness/work_context_pack.py --path harness/tests/test_work_skill_tdd_rules.py --json` → PASS

## 负面清单（别做）

- 不要只在提示词里加“记得确认方向”作为解法；需要有可检查的文档或脚本证据。
- 不要把所有讨论都升级成重流程；轻量任务可以只记录一条方向校准结论。
- 不要把 global-memory 仓库维护规则塞回全局 `agents/CLAUDE.md`，避免污染日常项目。
- 不要把设计审查通过等同于用户同意实现；审查只是输入，用户确认才是进入实现的门。

## 关联

- 现有任务：`D:/ClaudeTasks/active/global-memory-oss-readiness-hardening`
- 相关规则：`skills/work/v1/SKILL.md` Step 1 / Step 2 / Step 2.5
- 相关机制：`harness/work_context_pack.py --intent`
- 邻近 issue：`ISSUE-2026-06-04-archive-commit-skips-retrospective-gate`（文档要求与脚本强制点脱钩）
