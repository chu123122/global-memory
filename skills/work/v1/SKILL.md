---
name: work
description: 任务治理模式。新任务一律 task_template（5 子目录 core/design/ops/test/_archive），老任务保留平铺兼容。Use when 用户打 /work 进入正式任务（新建或继续）。快速提问、闲聊、单行修改不要用。
---

# Work Mode

## When to use
- 正式开发/排查/文档任务（≥3 轮）
- 用户打 `/work [可选任务描述]` 时立即激活
- **不要用**：快速概念问答、闲聊、单行修改、单纯讨论

## 两种任务结构（必读）

| 结构 | 何时用 | 物理布局 |
|---|---|---|
| **v2 / 4 子目录**（默认） | 所有 2026-05-21 之后立的新任务 | `core/` + `design/` + `ops/` + `test/` + `_archive/` |
| **v1 / 平铺**（向后兼容） | 2026-05-21 之前立的老任务，**不强制迁移** | `需求分析.md` + `设计文档.md` + `DESIGN.md` + `HANDOFF.md` 在任务根 |

**结构识别规则**：
- 任务目录存在 `core/` 子目录 → v2
- 否则 → v1

规范单一来源：`~/.claude/global-memory/docs/task-lifecycle.md`（新任务必读）+ `~/.claude/global-memory/_bootstrap/templates/task_template/README.md`（模板说明）。

## Workflow（按序执行，不可跳）

### Step 0: 加载上下文 + 文档状态

硬启动动作（用 Bash 工具跑）：
```bash
python ~/.claude/scripts/work_context_pack.py
```

读输出 `summary / stage / required_reads / recommended_next_step`，再进 Step 1。脚本写 `~/.claude/logs/harness_tool_invocations.jsonl` 作执行证据。

当用户原话包含“新任务 / 新开任务 / 维护 task / 迁移 task / 独立 task”等新任务意图时，硬启动必须把用户原话传给 intent guard：
```bash
python ~/.claude/scripts/work_context_pack.py --intent "<用户原话>" --json --write-status
```

若输出包含 `intent_guard.action=create_task_or_confirm`，不能继续沿用当前 `.current_task` 直接写文档或改代码；必须先运行 `create_task.py` 新建 task，或明确向用户确认“这是继续当前 task 还是新 task”。

脚本不可用 / 命令失败 → 回答开头声明：`/work context pack 未运行`，不能假装读过。

仅在 pack 输出 `WARNING` 且需 active_tasks 完整明细时降级：
```bash
python ~/.claude/skills/work/scripts/load_context.py
python ~/.claude/skills/work/scripts/check_doc_status.py
```

确定任务后写当前任务标记（statusline 自动显示）：
```bash
echo -n "<任务名>" > ~/.claude/.current_task
```

### Step 1: 判定新/老任务 + 结构

#### 继续老任务

**v2 任务**（任务目录有 `core/`）：
1. Read `core/HANDOFF.md` 全文（看「下次开始」+「当前目标」）
2. Read `core/STATUS.md`（pack 自动生成的快照）
3. 输出："上次进度 X，本次是否继续 Y？"
4. **等用户确认再动手**

**v1 任务**（无 `core/`，平铺）：
1. Read 任务根 `HANDOFF.md`
2. 输出 + 等确认

#### 新任务

**结构选择**：默认 v2。除非用户明确说"用旧结构"/"平铺"，否则一律 v2。

##### v2 立项流程（默认）

1. 起 task-id（kebab-case，含主题词）
2. 复制模板：
   ```powershell
   Copy-Item -Recurse "$env:GLOBAL_MEMORY_DIR/templates/task_template" "$env:CLAUDE_TASKS_ACTIVE/<task-id>"
   Remove-Item "$env:CLAUDE_TASKS_ACTIVE/<task-id>/README.md"  # 模板自身 README 不属于任务
   ```
3. 全量替换占位：
   - 所有 `task: <task-id>` frontmatter → 真实 id
   - 所有 `<任务中文名>` → 真实中文名
4. 切 current_task：
   ```powershell
   Set-Content -NoNewline ~/.claude/.current_task "<task-id>"
   ```
5. 加中文映射（statusline 显示用）：编辑 `~/.claude/projects/task_display_names.json` 加 `"<task-id>": "<中文名>"`
6. 生成 STATUS：
   ```bash
   python ~/.claude/scripts/work_context_pack.py --task <task-id>
   ```
7. **按等级填初始内容**：
   - **轻量**（调试/bug/单文件/≤3 改动）：只填 `core/背景.md` 一段话 + `core/HANDOFF.md` 「下次开始」
   - **完整**（新需求/重构/跨天设计）：
     - `core/背景.md`（一次性背景：是什么、为什么做、边界）
     - `design/设计文档.md`（方案概述、Phase 拆分表，**每 Phase 必填「不做会怎样？」列**）
     - `design/Phase1-<name>.md`（首个 Phase 卡，status=pending）
     - `core/HANDOFF.md`「下次开始」
8. 等级判定：
   - 默认轻量
   - "完整流程"/"走文档"/"正式立项" → 完整
   - 拿不准 → 问"轻量还是完整？"
9. 写人类向文档前读：
   - `~/.claude/skills/work/HUMAN_DOC_STYLE.md`
   - `~/.claude/skills/work/style-refs/` 至少 1 份样例

##### v1 立项流程（仅向后兼容，不推荐新用）

用户明确说"按旧 work skill 走"时才用。流程见 git history `SKILL.md@2026-05-18`。新任务**默认拒绝走 v1**，提示："新规范已升级为 v2 4 子目录结构（task-lifecycle.md），需要走 v1 请说明理由。"

### Step 2: 输出首条回答

**完整等级**：按 `~/.claude/skills/work/templates/workflow.md` 输出（目标/方案/风险/下一步）。
**轻量等级**：自由格式，至少含目标一句话 + 方案 + 下一步。

### Step 2.5: 讨论结论落地

**触发分级**：
- **关键决策**（方案选定、架构方向、验收标准）→ 立即 Edit 到对应文档
- **普通讨论结论** → 阶段性收敛时批量落地

**v2 落地目标**（4 子目录）：

| 结论类型 | 落地目标 |
|---|---|
| 业务背景 / 痛点 / 边界 | `core/背景.md` |
| 方案选定 + 对比 + 架构 / 接口 | `design/设计文档.md` |
| 单 Phase 实施细节 / 算法 / 边界 case | `design/Phase<N>-<name>.md` |
| 范围 / 验收标准 | `design/设计文档.md`「验收清单」 |
| 风险 / 待决 | `ops/决策队列.md`（`- [ ]` 项 pack 抓进 STATUS） |
| 测试策略 | `test/测试.md` |
| 改动审计 | `ops/CHANGELOG.md`（PR/commit 级 append） |
| 任务私有坑点 | `ops/坑点.md`；普适坑同步 `~/.claude/global-memory/fixes/` |

**v1 落地目标**（平铺，仅老任务）：

| 结论类型 | 落地目标 |
|---|---|
| 业务背景 / 痛点 | `需求分析.md`「业务背景」 |
| 方案选定 + 对比 | `需求分析.md`「方案选定」 |
| 范围 / 验收 | `需求分析.md`「范围与验收」 |
| 风险 | `需求分析.md`「风险与回滚」 |
| 架构 / 数据模型 / 接口 | `设计文档.md` |
| 算法 / 边界 case | `设计文档.md` |
| 测试策略 | `设计文档.md`「测试策略」 |

**写入规则**：
1. 遵守 `HUMAN_DOC_STYLE.md`
2. 写完简短告知："已落地到 `<file> 章节`"——只贴 diff 摘要
3. 批量落地可合并多条 Edit
4. **v2 任务每次落地必同步 `ops/CHANGELOG.md`** 一行（日期 + 一句话事件）

### Step 3: 执行

#### Phase TDD 执行规则（v2 任务）

Phase 卡就是最小 Spec 单元。v2 任务不新增独立 SPEC 文档；目标、边界、做什么、不做什么、验收和证据都落在 `design/设计文档.md` + 当前 `design/Phase<N>-*.md`。

**凡是改代码，必须有测试或替代验证。**

可自动化验证的代码改动按 TDD 跑：
1. 读当前 Phase 卡，把「验收」拆成可执行测试点。
2. 先写会失败的测试；bug fix 必须先写复现失败测试。
3. 跑测试并记录 **Red 结果**：失败命令、失败原因、为什么符合预期。
4. 写最小实现让测试通过。
5. 跑同一测试并记录 **Green 结果**：通过命令、结果摘要。
6. 需要重构时，重构后复跑同一测试。
7. 把 Red/Green 证据写回当前 Phase 卡的「TDD 记录」，并同步 `test/测试.md`。

无法先写测试时，必须先写明原因和替代验证（日志、截图、人工检查、构建结果等），再改代码。

硬规则：
- 实现后补的测试不算 TDD，只能算回归测试；要在 Phase 卡标明。
- Green 后不能为了通过而改松测试；确需改验收，先更新 Phase 卡里的验收理由。
- 文档、调研、纯配置说明可不强制 Red，但仍要有验收证据。

**路由原则**：按耦合度决定执行者（对齐 CLAUDE.md）。

#### 高耦合 → 主模型直接执行

- 编译 → 读错误 → 改代码 → 重编译
- 测试失败 → 定位 → 修复 → 复测
- 构建/部署失败修复
- 多文件关联改动（改 A 后据结果决定改 B）
- 设备/环境排查

#### 低耦合 → 可派 subagent

| 任务类型 | 派给 | 预算 |
|---------|------|------|
| 大范围 grep/符号定位 | Explore(haiku) | 工具 ≤10 |
| git log/status/diff 摘要 | haiku | 时限 5min |
| commit message 生成 | haiku | 回传 <200w |
| 独立文档生成 | sonnet | 边界清晰 |
| 边界清晰单文件改动 | sonnet | 不依赖前后步骤 |

**歧义**：拿不准 → 主模型执行。

#### Phase 状态切换（v2 任务）

每 Phase 卡 frontmatter 含 `status:`，按顺序流转：
- `pending` → 未开工
- `implementing` → 进行中
- `done` → 完结（同步改 `design/设计文档.md`「Phase 拆分」表对应行）

切换工具（无需手改）：
```bash
python ~/.claude/scripts/scripts/update_phase_status.py --task <id> --phase <N> --status implementing
```

**M1 反问复审**（Phase done 时）：回看「不做会怎样？」原答案 vs 实际后果。原答案凑数 → `core/复盘.md` § 5 标「下次可能踩」+ § 6 标「不打算修」。

#### 实现计划（复杂改动时写）

每个 Step 三要素：
- **动作**：文件路径 + 改动内容
- **成功后→**：进哪步
- **失败后→**：恢复动作 + 重试上限 + 兜底

按 `~/.claude/agents/work-agent.md` 子模式决定计划内容。

### Step 4: 收尾

#### v2 任务收尾

1. 一句话事实摘要
2. **必做**：`ops/CHANGELOG.md` append 今日条目（每次 PR/commit 级改动当场记，**不攒到结束**）
3. 跨天/中断 → 更新 `core/HANDOFF.md`「下次开始」
4. 阶段切换 → `update_phase_status.py` 或手改 Phase 卡 `status:`
5. 踩坑 → `ops/坑点.md`；普适坑同步 `~/.claude/global-memory/fixes/`
6. 收尾跑：
   ```powershell
   python ~/.claude/skills/work/scripts/check_doc_sync.py
   python ~/.claude/scripts/task_complete.py "$env:CLAUDE_TASKS_ACTIVE/<task-id>" --fix
   ```
7. 记忆写入：按 CLAUDE.md 安全边界，fixes/decisions/feedback/ 触发才写

#### v1 任务收尾

1. 跑 `check_doc_sync.py`，对每条 ⚠️ 主动建议：
   - DESIGN.md「## 进度」追加今日条目
   - HANDOFF.md「## 下次开始」更新
   - **由用户确认后再写**
2. 跑 `python ~/.claude/scripts/task_complete.py <项目目录> --fix`
3. 记忆写入条件检查

### 任务归档

满足任一即可归档：
- 设计文档「验收清单」全 `[x]`
- 用户明确说"任务结了"
- 被 supersede

归档流程见 `~/.claude/global-memory/docs/task-lifecycle.md` § 4（5 条护栏 + 必做步骤）。v2 任务**任务 ≥5 Phase 或 ≥10 轮交互才触发复盘**，小任务跳过。

---

## ~~/work implement <task>~~ 子流程（v1 遗留，v2 不用）

v1 流程用 discussion/implementation 二阶段切换。v2 不用此概念——改用 Phase 卡 `status:` 流转。

仍触发场景：用户对**老 v1 任务**打 `/work implement <task>`。

### v1 Implement Step 1: 校验

- 任务目录存在 + 是 v1 平铺结构（无 `core/`）
- `需求分析.md` + `设计文档.md` 都存在
- 当前 Status 是 `discussion`
  - `implementation` → 提示"已在实现期"
  - `missing-status` / `unknown` → 提示先修复 Status
- 两份 Status 一致
- **人类文档已填充**：
  ```bash
  grep -E '^\s*<!--' "<tasks_root>/<task_name>/需求分析.md" "<tasks_root>/<task_name>/设计文档.md" || true
  ```
  任一命中 → 拒绝，提示模板占位未替换；0 命中 → 通过

### v1 Implement Step 2-4

旧逻辑保留，见 git history。**v2 任务遇此命令 → 拒绝并提示"v2 任务用 Phase 状态切换，不走 implement"**。

---

## 与 doc_gate.py 的协同

skill 入口主动校验（提前预警），`doc_gate.py` 编辑时被动拦截（兜底）。
**双方共享 `~/.claude/projects/project_registry.json`**——单一数据源。
- registry sanity check 失败 → doc_gate 输出 warning，继续 per-task 检查
- 当前文件匹配的 task 文档不全 → doc_gate 阻断该次编辑
- 当前文件不匹配任何 task → 放行

## 任务文档存储位置

`tasks_root` 由 registry 决定：
- 本机：`$env:CLAUDE_TASKS_ACTIVE/<task>/`（归档 `$env:CLAUDE_TASKS_ARCHIVED/<task>/`）
- 修改 `tasks_root` 字段三脚本（check_doc_status / check_doc_sync / doc_gate）自动跟进

## 不做的事

- 不修改 doc_gate.py 等 hook
- 不自动改用户的 DESIGN/HANDOFF（建议、由用户确认）
- 不在 Step 3 越过 work-agent.md 的子模式自行发挥
- 不用于快速提问场景（违反 CLAUDE.md 启动协议）
- **v2 新任务不允许走 v1 平铺结构**，除非用户明确说明理由
