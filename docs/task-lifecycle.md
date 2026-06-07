---
doc_type: reference
status: active
last_updated: 2026-05-21
retrieve: true
retrieve_summary: "Task 四状态机：创建（templates/task_template）→活跃（active/）→归档（archived/，需复盘+5护栏）→删除。状态转换条件、display_names 维护、归档触发点（用户决定不自动）见 archive_task.py --check/--extract/--commit"
trigger:
  keywords: [concept:task, concept:lifecycle, concept:archive]
  tags: [workflow]
---

# Task Lifecycle · 创建 → 活跃 → 归档 → 删除

> 一个 task 从立项到退役的 4 状态机。约定：什么时候转哪个状态、转的时候做什么、什么时候真的可以删。
>
> 配套：`docs/scripts-registry.md`、`templates/task_template/`

---

## 状态机

```
   ┌─ create ──→ active ──→ archived ──→ deleted
   │              │  ↑                       │
   │              │  └── reopen ─┐           │
   │              ▼               │           ▼
   │           paused ────────────┘        (永久)
```

| 状态 | 物理位置 | retrieve 扫描 | gate_check 扫描 |
|---|---|---|---|
| **active** | `$env:CLAUDE_TASKS_ACTIVE/<task-id>/` | ✅ | ✅ |
| **paused** | `$env:CLAUDE_TASKS_ACTIVE/<task-id>/`（加 `_paused` 标记）| ✅ | ❌ |
| **archived** | `$env:CLAUDE_TASKS_ARCHIVED/<task-id>/` | ❌ | ❌ |
| **deleted** | （从磁盘移除）| ❌ | ❌ |

---

## 1. create —— 新立项

### 转换条件
用户/AI 决定开新任务。

### 必做步骤
1. 起 task-id（kebab-case，含主题词，例 `harness-doc-completion`）
2. `Copy-Item -Recurse "~/.claude/skills-repo/_bootstrap/templates/task_template" "$env:CLAUDE_TASKS_ACTIVE/<task-id>"`
3. 删模板 `README.md`（不属于任务）
4. 全量替换 `task: <task-id>` 和 `<任务中文名>` 占位
5. 写 `core/背景.md`（一次性背景）
6. 写 `design/设计文档.md`（Phase 拆分、决策、不做）
   - **M1 反问（每 Phase 必填）**：在 Phase 拆分表加一列「不做会怎样？」，每 Phase 一行答。答不出具体后果 / 答出来是「没事」→ 砍 Phase。
     反例：「不做就没有 metrics」→ 反问「没 metrics 会怎样？」→ 答不出 → 砍。
     正例：「不做归档时无法拦过期复盘」→ 具体后果（治理债复发）→ 留。
     来源：`harness-governance-followup/core/复盘.md` P2/P5 伪需求事后审计。
7. `~/.claude/.current_task` 切到该 id
8. `~/.claude/projects/task_display_names.json` 加中文映射
9. 跑 `python ~/.claude/scripts/work_context_pack.py --task <task-id>` 生成 STATUS.md

### 验收
- `core/STATUS.md` 自动生成成功
- statusline 显示中文名

---

## 2. active —— 推进中

### 必做行为
- 每次 session 末尾：更新 `core/HANDOFF.md`「下次开始」段
- 每次 PR/commit 级改动：append `ops/CHANGELOG.md`
- 拍板 / 待决：写 `ops/决策队列.md`（pack 会抓 `- [ ]` 进 STATUS）
- 阶段切换：在 `design/Phase<N>-<name>.md` 加 `status: implementing`
- 代码改动开始前：当前 Phase 卡就是**最小契约实例**（四契约见 work SKILL「## 四契约」）；②验收契约要求 验收项 ↔ 验证方式 ↔ 证据 1:1，先把验收转成测试跑出 Red，再实现到 Green。无法先写测试时，在 Phase 卡②表写明原因和替代验证。
- 踩坑：写 `ops/坑点.md`（任务私有）；普适坑点同步到 `~/.claude/global-memory/fixes/`
- Phase 完结：把 Phase 卡 `status:` 改 `done`，同步 `设计文档.md` Phase 拆分表。**done 打回规则**：②每条验收项须有 Green/证据指针，缺则不得 done；override 跳过须按④权威契约留痕
- **M1 反问复审**（Phase done 时）：回看「不做会怎样？」原答案 vs 实际后果。原答案是凑数 → 在 `core/复盘.md` § 5 标「下次可能踩」+ § 6 标「不打算修」

### 别做
- ❌ 把流水账塞 HANDOFF.md（流水账归 `design/进度.md`）
- ❌ 把废弃方案留主目录（移到 `_archive/`）

### 四契约 Phase 卡（最小契约实例）

每个 Phase 卡按四契约组织（与 work SKILL「## 四契约」单一源一致）：

- **① 任务契约**：目标 / 边界 / 不做（含「不做会怎样?」M1 反问）。
- **② 验收契约**：验收项 ↔ 验证方式 ↔ 证据 1:1；done 前每行须有 Green/证据，缺则打回。
- **③ 执行契约**：读哪/改哪 + Red→Green；停与升权默认继承全局（R9/R17/sandbox）。
- **④ 权威契约**：冲突默认裁决链 **人工结论 > 可执行证据 > 设计文档 > 代码现状 > 自动状态文件**；override 可推翻但须 `ops/决策队列.md` 或 `CHANGELOG` 留痕，不抹平失败。Phase 无特例则继承不写。

---

## 3. paused —— 暂停（中长期不动）

### 转换条件
- 任务被搁置 ≥ 2 周但未结束
- 外部依赖卡住（等用户决策、等第三方）

### 必做步骤
1. `core/HANDOFF.md` 顶部加 `paused: <YYYY-MM-DD>: <理由>`
2. （可选）`New-Item -ItemType File "$env:CLAUDE_TASKS_ACTIVE/<task-id>/_paused"`
3. 保留 `.current_task` 切走

### reopen
1. 删 `_paused` 标记
2. 跑 work_context_pack 重生成 STATUS.md
3. 把 `.current_task` 切回来

---

## 4. archived —— 归档（任务收尾）

### 转换条件（任一即可）
- 设计文档「验收清单」全 `[x]`
- 用户明确说"这个任务结了"
- 任务被 supersede（新任务接管同一目标）

### 归档前复盘（5 条护栏）

> 来源：harness-governance-followup P6（D5 决策）
> 目的：防 AI「鸡蛋挑骨头」式硬编经验、把虚收益当真收益归档。
> 时机：满足转换条件后、走「必做步骤」前；产出 `core/复盘.md`。

| # | 护栏 | 落地动作 | FAIL 时怎么办 |
|---|---|---|---|
| 1 | **门槛** | 任务 ≥5 Phase 或 ≥10 轮用户交互才触发复盘；小任务直接跳本节走「必做步骤」 | 跳过本节，CHANGELOG 注「小任务无复盘」即可 |
| 2 | **跳过权** | 用户回答「这次没踩坑 / 没必要复盘」即合法终结，不强行编内容凑数 | 复盘.md 只写一句「本任务无重大踩点，跳过复盘」+ 时间戳 |
| 3 | **引用强制** | 每条优化项必须引用具体文件路径+行号（`file.py:123`）或具体踩坑现场（错误消息 / commit / 日期） | 无引用条目自动剔除，不进 `_archive/extract_candidates.md` |
| 4 | **ROI 强制** | 每条带「工作量估」（h）+「收益场景」（具体什么场景能省什么）；收益 < 2h 但工作量 > 4h 自动降 P3 或砍 | 标 `dropped` + 原因；不进入下个任务的设计基线 |
| 5 | **自检节** | 复盘末尾必须有两节：① 这次没踩但下次可能踩；② 不打算修的 + 原因 | 缺其一 → AI 自我承认局限，重写直到包含 |

### 护栏触发方式

复盘.md 末尾必须有一行 self-check：
```
self_check: rails={1,2,3,4,5}  reasoned=true
```

如 P8 `archive_task.py --extract` 启用 lint，会扫这行 + 引用计数 + 自检节；缺失则 extract 拒绝产出候选清单。

### 必做步骤

1. **整理目录**：
   - 废弃方案/中间产物移到 `_archive/`
   - `core/HANDOFF.md` 顶部加 `status: archived` + `archived: <YYYY-MM-DD>: <收尾摘要>`
   - `core/INDEX.md` 加「归档说明」

2. **抽取通用经验**：
   - 普适坑点 → `~/.claude/global-memory/fixes/`
   - 跨任务经验 → `~/.claude/global-memory/knowledge/`
   - 行为风格 → `~/.claude/global-memory/feedback/`
   - 架构决策 → `~/.claude/global-memory/decisions/`
   - **抽取后** 在原 task 留 supersede 链接

3. **物理迁移**：
   ```powershell
   Move-Item "$env:CLAUDE_TASKS_ACTIVE/<task-id>" "$env:CLAUDE_TASKS_ARCHIVED/<task-id>"
   ```

4. **清理引用**：
   - `~/.claude/.current_task` 若指向此 task → 切走或清空
   - `~/.claude/projects/task_display_names.json` 保留映射（archived 也要中文名）

5. **CHANGELOG**：
   ```
   ### [YYYY-MM-DD] [ARCHIVE] <task-id> 归档
   - 抽取记忆：fixes/X.md / knowledge/Y.md
   - 总输出：N 文档 / M 代码改动
   - 归档原因：完成 / supersede / 放弃
   ```

### 验收
- 物理在 `archived/<task-id>/`
- `.current_task` 不指它
- retrieve 不扫它（验证 `harness_retrieve.py --query <task相关词>` 不返回旧路径）

---

## 5. deleted —— 永久删除

### 转换条件（同时满足）
- 已 archived ≥ 6 个月
- 该任务的所有通用经验已抽取到 global-memory/
- 用户明确同意删除

### 必做步骤
1. 最后一次 grep：`Grep -r "<task-id>" ~/.claude/global-memory/` 确认无引用
2. `Remove-Item -Recurse "$env:CLAUDE_TASKS_ARCHIVED/<task-id>"`
3. `task_display_names.json` 删映射条目
4. CHANGELOG：`[DELETE] <task-id> 永久删除（archived 6+ 月后）`

### 防误删
- 不允许跳过 archived 直接 delete
- 删除前必须有 git tag 或备份快照

---

## 工具

| 操作 | 命令 |
|---|---|
| 起新任务 | `Copy-Item -Recurse "~/.claude/skills-repo/_bootstrap/templates/task_template" "$env:CLAUDE_TASKS_ACTIVE/<id>"` |
| 切 current_task | `echo -n "<id>" > ~/.claude/.current_task` |
| 生成 STATUS | `python ~/.claude/scripts/work_context_pack.py --task <id>` |
| 归档 | `Move-Item "$env:CLAUDE_TASKS_ACTIVE/<id>" "$env:CLAUDE_TASKS_ARCHIVED/<id>"` |
| 验证不被 retrieve 扫 | `python ~/.claude/global-memory/harness/scripts/harness_retrieve.py --query <kw>` |

---

## 历史现状（2026-05-21）

- `$env:CLAUDE_TASKS_ACTIVE/` 含 ≈ 12 个任务
- `$env:CLAUDE_TASKS_ARCHIVED/` 已存在但很少用
- **多数老任务平铺无 core/design/ops/test 分目录** — 新规范仅约束新任务，老任务保留原样
- 老任务归档时 **不强制**重整目录，只要求加 `archived:` frontmatter + 抽取记忆

---

## 反模式

1. **active 目录堆百份方案 v1/v2/v3 不归档** → 任何写到 v3 → v1/v2 应进 `_archive/` 并 supersede
2. **archived 还在 retrieve 命中** → 检查 retrieve 是否漏排 `archived/` 路径
3. **删 task 但 fixes/knowledge 没抽** → 经验丢失
4. **新任务建在 active/archived 平级**（如 `$env:CLAUDE_TASKS_ROOT/<id>/`）→ 状态机崩溃
