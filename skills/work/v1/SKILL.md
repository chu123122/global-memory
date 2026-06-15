---
name: work
description: 任务治理模式。新任务一律 task_template（core/design/ops/test 4 工作子目录 + _archive 归档），老任务保留平铺兼容。Use when 用户打 /work 进入正式任务（新建或继续）。快速提问、闲聊、单行修改不要用。
---

# Work Mode

## When to use
- 正式开发/排查/文档任务（≥3 轮）
- 用户打 `/work [可选任务描述]` 时立即激活
- **不要用**：快速概念问答、闲聊、单行修改、单纯讨论（→ 启动协议，见 `D:\global-memory\rules\执行层.md`）

## 任务结构

**所有任务一律 v2 / 4 子目录**：`core/` + `design/` + `ops/` + `test/` + `_archive/`。
规范单一源：`~/.claude/global-memory/docs/task-lifecycle.md`（新任务必读）。

**Legacy 读兼容**：老任务平铺（根直放 HANDOFF.md）→ 只读，不迁移，继续时读任务根 HANDOFF。不再新建平铺。

## 四契约（概念骨架）

work 的产物不按文件理解，按**它在立哪份契约**理解。一个 task = 反复实例化这四份契约（spec = 可被验证/追溯的约束，非"写给人看的文档"）：

- **① 任务契约**：这次做什么 / 边界 / 不做（及「不做会怎样?」）。task 级立一次 → `core/背景.md` + `design/设计文档.md`。
- **② 验收契约**：什么算完成、什么证据能证明。**验收项 ↔ 验证方式 ↔ 证据 必须 1:1**（verifiable + traceable）。
- **③ 执行契约**：读哪 / 改哪 / 怎么记状态 / 何时停 / 何时升权。停与升权默认继承全局（R9 恢复边界 / R17 同错3次 / sandbox 升权，见 `执行层.md`）。
- **④ 权威契约**：冲突时谁说了算。默认裁决链 **人工当场显式结论 > 可执行证据(测试/命令/日志/产物) > 设计文档 > 代码现状 > 自动派生状态文件(STATUS/HANDOFF)**；override 可推翻任意层，但推翻「可执行证据」必须在 `ops/决策队列.md` 或 `CHANGELOG` 留痕（理由 + 待复审条件），不抹平失败事实。

**Phase 卡 = 最小契约实例**：携带本 Phase 的 ②③（④ 默认继承，特例才写），向上归属 task 的 ①④。下方 Step 0-4 是这四份契约「何时被立 / 被验」的时间投影。

## Workflow（按序执行，不可跳）

### Step 0: 加载上下文

硬启动（Bash 跑）：
```bash
python ~/.claude/scripts/work_context_pack.py
```
读 `summary / stage / required_reads / recommended_next_step` 再进 Step 1。

新任务意图（用户说"新任务/新开/迁移 task"等）→ 必带 intent guard：
```bash
python ~/.claude/scripts/work_context_pack.py --intent "<用户原话>" --json --write-status
```
输出 `intent_guard.action=create_task_or_confirm` → 不得沿用当前 task 直接写，先 `create_task.py` 或向用户确认。

脚本失败 → 回答开头声明 `/work context pack 未运行`，不假装读过。

### Step 1: 判定新/老 + 结构（立 ① 任务契约）

**继续老任务**：Read `core/HANDOFF.md`（下次开始+当前目标）→ Read `core/STATUS.md` → 输出"上次进度 X，本次继续 Y?" → **等用户确认再动手**。
> Legacy 平铺：Read 任务根 HANDOFF.md → 输出 + 等确认。

**新任务**（一律 v2 4 子目录）：
1. 起 task-id（kebab-case 含主题词）
2. 复制模板：
   ```powershell
   Copy-Item -Recurse "~/.claude/skills-repo/_bootstrap/templates/task_template" "$env:CLAUDE_TASKS_ACTIVE/<task-id>"
   Remove-Item "$env:CLAUDE_TASKS_ACTIVE/<task-id>/README.md"
   ```
3. 全量替换占位（`task: <task-id>` / `<任务中文名>`）
4. 写信息位 `.current_task`（仅记"最后活跃 task"，已无 reader 读取，不参与显示/解析）：`Set-Content -NoNewline ~/.claude/.current_task "<task-id>"`
5. 加中文映射：编辑 `~/.claude/projects/task_display_names.json`
6. 生成 STATUS：`python ~/.claude/scripts/work_context_pack.py --task <task-id>`
7. 按等级填初始内容：
   - **轻量**（调试/bug/单文件/≤3 改）：`core/背景.md` 一段 + `core/HANDOFF.md` 下次开始
   - **完整**（新需求/重构/跨天）：`core/背景.md` + `design/设计文档.md`（Phase 拆分表，每 Phase 必填「不做会怎样?」列）+ `design/Phase1-<name>.md`(status=pending) + HANDOFF
8. 等级判定：默认轻量；"完整流程/走文档/正式立项"→完整；拿不准→问
9. 写人类向文档前读：`~/.claude/skills/work/HUMAN_DOC_STYLE.md` + `style-refs/` 至少 1 份

确定任务后绑 session：
```bash
python ~/.claude/scripts/work_context_pack.py --task "<任务名>" --json --write-status >/dev/null
```
绑定写本终端私有 `.session_tasks/<session_id>`——这是 statusline 显示 + brief/pack 解析的**唯一**来源。全局 `.current_task` 仅"最后活跃 task"信息位，statusline/retrieve_inject/work_context_pack 均已不再读它，勿依赖它显示或定位当前 task。

### Step 2: 输出首条回答
**完整**：按 `templates/workflow.md`（目标/方案/风险/下一步）。**轻量**：自由，至少目标一句 + 方案 + 下一步。

### Step 2.5: 讨论结论落地（立 ②③ 验收/执行契约）

关键决策（方案/架构/验收）→ 立即 Edit；普通结论 → 收敛时批量。

| 结论类型 | 落地目标 |
|---|---|
| 业务背景/痛点/边界 | `core/背景.md` |
| 方案选定+对比+接口 | `design/设计文档.md` |
| 单 Phase 细节/算法/边界 case | `design/Phase<N>-<name>.md` |
| 范围/验收标准 | `design/设计文档.md`「验收清单」 |
| 风险/待决 | `ops/决策队列.md`（`- [ ]` 项被 pack 抓进 STATUS） |
| 测试策略 | `test/测试.md` |
| 改动审计 | `ops/CHANGELOG.md`（PR/commit 级 append） |
| 任务私有坑 | `ops/坑点.md`；普适坑同步 global `fixes/` |

写完简短告知"已落地到 `<file> 章节`"，只贴 diff 摘要。**v2 每次落地必同步 `ops/CHANGELOG.md` 一行。**

**②验收契约的硬约束**：每条验收项落地时必须同时给出「验证方式（命令/检查/日志/产物）」，不允许只写"做到 X"而无可验证手段。验收项与证据 1:1 绑定，绑定位 = Phase 卡②表。

### 实现前用户确认门

设计讨论、方案审查、design-reviewer/worker 返回的审查结果，都只是 Step 3 的输入，不是实现授权。进入 Step 3 或派 worker 前，先向用户反馈方案概要、执行计划、边界和主要取舍；**设计审查结果不是实现授权；用户确认才是进入实现或派 worker 的门。**

若用户已在本轮或任务指令中明确预授权（例如“直接实现”“不用确认”“just do it”“proceed”），可跳过此门，但回复或任务记录中必须说明跳过原因。没有明确预授权时，停在确认门，等待用户确认。

### Step 3: 执行（履行 ③，跑出 ② 的 Green）

- **改代码走 TDD**（Red→最小实现→Green→写回 Phase 卡+test/测试.md）→ 全文见 `D:\global-memory\rules\执行层.md`「本层细则·TDD 记录」。
- **路由按耦合度**（高耦合=主模型直跑；低耦合=派 subagent）→ 表见 `D:\global-memory\rules\执行层.md`「本层细则·路由细则」。
- 改代码必有测试或替代验证 = 全局铁律 R13，不复述。

Phase 状态切换：
```bash
python ~/.claude/global-memory/harness/scripts/update_phase_status.py --task <id> --phase <N> --status implementing
```
状态流：`pending → implementing → done`（done 同步改设计文档 Phase 表对应行）。
**done 打回规则**：Phase → `done` 要求②每条验收项都有 Green/证据指针；缺证据不得标 done（自然打回，回 implementing 补证据）。override 跳过须按④留痕，不抹平。
M1 反问复审（Phase done）：回看「不做会怎样?」原答 vs 实际 → 凑数的标 `core/复盘.md`。

实现计划（复杂改动）每 Step 三要素：动作（文件+改动）/ 成功后→哪步 / 失败后→恢复+重试上限+兜底。
子模式见 `~/.claude/agents/work-agent.md`。

### Step 4: 收尾（验 ②，冲突走 ④）
1. 一句话事实摘要
2. **必做** `ops/CHANGELOG.md` append 今日条目（当场记，不攒）
3. 跨天/中断 → 更 `core/HANDOFF.md`「下次开始」
4. 阶段切换 → `update_phase_status.py` 或手改 Phase 卡 status
5. 踩坑 → `ops/坑点.md`；普适坑同步 global `fixes/`
6. 收尾跑：
   ```powershell
   python ~/.claude/skills/work/scripts/check_doc_sync.py
   python ~/.claude/scripts/task_complete.py "$env:CLAUDE_TASKS_ACTIVE/<task-id>" --fix
   ```
7. 记忆写入：按 `D:\global-memory\rules\沉淀层.md` 触发表，触发才写。

### 任务归档
满足任一即可：设计文档「验收清单」全 `[x]` / 用户说"任务结了" / 被 supersede。
流程见 task-lifecycle.md § 4。v2 任务 ≥5 Phase 或 ≥10 轮才触发复盘，小任务跳过。
> Legacy 平铺收尾：`check_doc_sync.py` → 按建议更新根 DESIGN/HANDOFF（确认后写）→ `task_complete.py <目录> --fix`。

## 系统接线（移出，链过去）
- 文档强制：`doc_gate.py` 编辑时被动拦（兜底），skill 入口主动校验（预警）→ 机制见 `D:\global-memory\rules\执行层.md`「强制点」。
- 任务文档/记忆位置 → `project_registry.json` 单一源，见 `D:\global-memory\rules\接入索引.md`。
- 适配层 `codex-adapter.md`：Codex runtime 覆盖层，Claude Code 不加载，**保留勿删**（design-reserved）。

## 不做的事（work 独有；全局铁律不复述）
- 不自动改用户 DESIGN/HANDOFF——建议，用户确认后写。
- 不越过 `work-agent.md` 子模式自行发挥。
- 不新建 v1 平铺结构（老平铺只读兼容）。
- 不用于快速提问（→ 启动协议，`D:\global-memory\rules\执行层.md`）。
> 「审查只报告」「改代码必有测试」= 全局铁律（R18/R13）；「不修改 hook」= 维护层职责边界（`D:\global-memory\rules\维护层.md`）。遵守不复述。
