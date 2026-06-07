---
issue_id: archive-commit-skips-retrospective-gate
status: open
severity: major
created: 2026-06-04
source: global-memory-stale-cleanup 归档时发现（AI 走 --check→--commit 跳过复盘且未被拦）
tags: [workflow, design]
---

# 归档复盘是"文档强制、脚本不强制"——`--commit` 可绕过 5 护栏

> task-lifecycle.md §4 把"归档前复盘（5 护栏）"写成必经步骤，retrieve_summary 也称"归档需复盘+5护栏"。
> 但 `archive_task.py --commit` 的唯一前提是 `--check` PASS，**不校验复盘是否存在/合规**。

## 事实（现场）

- `archive_task.py` 三模式职责分离：
  - `--check` = Phase status + 设计文档 Phase 表 + 验收清单 三者一致 → `ready_to_archive`
  - `--extract` = 抽 fixes/knowledge 候选 + lint `复盘.md`（P6 5 护栏 self_check 锚 + 引用计数 + 自检节）；缺失则 **extract** 拒绝产出（exit 2）
  - `--commit` = 物理归档，**仅要 `--check` PASS**
- 复盘的强制 lint 只长在 `--extract`，而 `--extract` 不是 `--commit` 的前置。
- 实证：`global-memory-stale-cleanup` 走 `--check → --commit` 归档成功，全程没有 `复盘.md`、`--extract` 从未运行、5 护栏从未触发。

## 根因

意图（§4 文档 + 生命周期 summary）与强制点（脚本 commit 路径）脱钩：
- 文档把复盘写成"满足转换条件后、走必做步骤前"的必经节。
- 脚本把复盘 lint 放进一个**可选的、与 commit 无依赖关系的** `--extract` 子命令。
- 没有任何 hook / gate 在 commit 时回查"该不该有复盘 / 复盘是否过 lint"。

## 影响

- 护栏 #1 门槛是"≥5 Phase **或** ≥10 轮"。**小任务跳过是设计内的**，问题不大。
- 但 **≥5 Phase / ≥10 轮的大任务**：复盘本应强制，`--commit` 却照过——5 护栏（防虚收益、强制引用、ROI 砍、自检节）与跨任务经验抽取可被**静默绕过**，正是复盘系统要防的失效模式。
- 叠加 AI 倾向走捷径（本次我只盯"1 Phase=小任务"，忽略了 ≥10 轮那半句，且跳过后未按护栏 #1 FAIL 动作在 CHANGELOG 注"小任务无复盘"），绕过会常态化。

## 修复方向（候选，未锁定）

1. **commit 前置加复盘门**：`--commit` 在 `--check` PASS 后，按门槛（Phase 数 / 交互轮数，轮数来源待定）判定"是否要求复盘"；要求则强制 `复盘.md` 存在且过 5 护栏 lint（复用 `--extract` 的 lint），否则 exit 1。小任务允许"复盘.md 仅一句跳过声明 + self_check"放行。
2. **轮数来源**：门槛里"≥10 轮用户交互"目前 AI 凭感觉判，无机器源。需定可信计数（session log? 还是退化为只认 Phase 数 + 人工 override）。
3. **跳过留痕**：跳过复盘时强制写 CHANGELOG「小任务无复盘」或 `复盘.md` 跳过声明（护栏 #1/#2 FAIL 动作落地为脚本检查，而非靠 AI 自觉）。

## 验收标准（修完怎么算好）

- [ ] 大任务（命中门槛）缺合规复盘时，`--commit` 拒绝并给出原因。
- [ ] 小任务跳过复盘时，归档产物里有机器可查的跳过留痕（CHANGELOG 行或 复盘.md 声明）。
- [ ] 有回归测试：构造一个命中门槛、无复盘的 task → `--commit` exit≠0。

## 负面清单（别做）

- 别把复盘搞成无差别强制（小任务凑数复盘 = 护栏 #2 明确反对）。
- 别在 AI 提示词里加"记得跑 --extract"当解法——靠自觉不算强制点。

## 关联

- 文档源：`docs/task-lifecycle.md` §4「归档前复盘（5 护栏）」+ 护栏触发方式。
- 脚本：`harness/scripts/archive_task.py`（`--check`/`--extract`/`--commit`）。
- 邻近任务：`v2-task-retrospective-audit`（看名字正审此类复盘强制/审计，宜并入或交叉引用）。
