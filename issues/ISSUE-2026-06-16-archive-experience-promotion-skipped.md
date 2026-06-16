---
issue_id: archive-experience-promotion-skipped
status: open
severity: major
created: 2026-06-16
source: global-memory-semantic-retrieval-survey 任务归档：extract 产出 11 条经验候选，但归档完成后未升进 global-memory，沉淀闭环在归档处断裂
tags: [skill, workflow, archive, memory, 沉淀, governance]
---

# 归档时经验候选未升进 global-memory，「沉淀」步骤被静默跳过

## 事实（现场，2026-06-16）

- `global-memory-semantic-retrieval-survey` 任务归档：
  - `archive_task.py --extract` 产出 **11 条经验候选** → `_archive/extract_candidates.md`。
  - `archive_task.py --commit --yes` 物理归档 `active/ → archived/`，全局 CHANGELOG 追加。
- 但归档完成后，这 11 条候选**没有任何一条被 review / 升进** `feedback/` `fixes/` `knowledge/`。
- 复盘 `core/复盘.md` **写了**（task-local 文档，归档随迁）；但**跨任务经验未进 global 反馈层** → "执行→沉淀→反馈"闭环在归档这一步断裂。
- 候选现状：静默躺在 `archived/global-memory-semantic-retrieval-survey/_archive/extract_candidates.md`，无提醒、无强制、易被永久遗忘。

## 根因（疑似，两层叠加）

1. **工作流设计缺口**：
   - `archive_task.py --extract` **故意只产候选不自动写 global-memory**（合理：什么进共享库需人判断）。
   - 但 `--commit` 仅 gate 在 `--check`（Phase 状态 + 复盘 lint + 验收清单），**不 gate "候选是否已 review/升进"**。
   - 结果：可以 extract → 直接 commit 归档，候选从未升进，也无 pending 标记/提醒。
2. **AI 执行缺口**：
   - work skill 收尾 Step 4 第 7 条已写"记忆写入：按 `rules/沉淀层.md` 触发表，触发才写"。
   - 但本次 lead 把"沉淀（候选→memory_write）"**降级为可选追问**而非收尾必做，做完 extract+commit 即归档。
   - 长上下文（1000+ 轮、决策密集流程）疑似加剧该降级。
   - 工作流缺口（无强制/提醒）使该执行缺口**无人兜底、静默通过**。

## 影响

- 跨 run 经验复用丢失：本任务 11 条本可复用经验（评测 harness + 独立复验 + 先验可分性省钱打法 + 共享工作树竞态 + "相似度≠意图" + UE 模板可抄/不可抄边界 等）未进 global 库，未来重复踩。
- "执行→沉淀→反馈"闭环（系统设计轴的核心）在归档处系统性断裂——不止本任务，任何走 extract→commit 的归档都可能漏。
- 复盘写了 ≠ 沉淀做了：易产生"已收尾"的错觉。

## 修复方向（候选，未锁定）

1. **工作流兜底（治本）**：`--commit` 前加一道软门/提醒——检测 `_archive/extract_candidates.md` 存在且未标记"已处理"时，WARN 或要求显式 `--skip-promotion --reason`；或归档后产出一个 pending-promotion 待办，进 health/inbox。
2. **规范/skill 强制点**：把"沉淀（候选→memory_write 或显式跳过+理由）"从 Step 4 一行升级为收尾**必经步骤**，与 archive 串起来（先沉淀/决策、再 commit）。
3. **AI 行为**：收尾时主动执行沉淀，不降级为可选追问；长上下文下尤其要回看收尾 checklist。

## 验收标准（修完怎么算好）

- [ ] 归档流程里，经验候选要么被升进、要么被显式跳过（带理由），二者必居其一、不可静默。
- [ ] 有可检查的机制（脚本门 / skill 强制点）防止"extract 了但从没 promote"静默通过。
- [ ] 规范明确"沉淀"是收尾必做，且与 archive 顺序绑定。

## 负面清单（别做）

- 不要让 `--extract` 自动写 global-memory（人判断不能省，会污染共享库）。
- 不要只在某次 prompt 里提醒一句"记得沉淀"——要落进可检查的门/规范。
- 不要把"复盘已写"当成"沉淀已做"。

## 关联

- 本任务：`D:/ClaudeTasks/archived/global-memory-semantic-retrieval-survey/_archive/extract_candidates.md`（11 候选，待处理）
- 规则：`rules/沉淀层.md`（触发表）、work skill 收尾 Step 4 第 7 条
- 脚本：`harness/scripts/archive_task.py`（--extract / --commit）
