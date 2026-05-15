---
name: work
description: 任务治理模式。按任务等级（轻量/完整）决定文档流程深度。轻量：目标+方案+执行，完整：需求分析+设计+SPEC+HANDOFF。Use when 用户打 /work 进入正式任务（新建或继续）。快速提问、闲聊、单行修改不要用。
---

# Work Mode

## When to use
- 正式开发/排查/文档任务（≥3 轮）
- 用户打 `/work [可选任务描述]` 时立即激活
- **不要用**：快速概念问答、闲聊、单行修改、单纯讨论

## Workflow（按序执行，不可跳）

### Step 0: 加载上下文 + 文档状态

优先运行 token saver（用 Bash 工具）。这是 `/work` 的硬启动动作，不是可选建议：
```bash
python ~/.claude/scripts/work_context_pack.py
```

运行后必须先读输出里的 `summary / stage / required_reads / recommended_next_step`，再进入 Step 1。脚本会写入 `~/.claude/logs/harness_tool_invocations.jsonl` 作为“脚本实际运行过”的证据；Claude 的 `tool_audit.jsonl` 仍是“AI 是否直接调用”的证据。

如果脚本不可用或命令失败，必须在回答开头声明：`/work context pack 未运行`，并说明原因；不能假装已经读取上下文。

只有在 pack 输出 `WARNING` 且需要完整 active_tasks 明细时，才降级运行：
```bash
python ~/.claude/skills/work/scripts/load_context.py
python ~/.claude/skills/work/scripts/check_doc_status.py
```

### Step 1: 判定任务等级 + 新/老任务

基于 `work_context_pack.py` 的 `task/stage/missing_required_docs/required_reads` + 用户消息：

**继续老任务**（HANDOFF.md 存在 + 含进度章节，或用户提到老任务名）：
1. 必须先用 Read 工具读 HANDOFF.md 完整内容
2. 输出："上次进度是 X，本次是否继续 Y？"
3. **等用户确认再动手**——不要自作主张接着写

**新任务** — 先判定等级，再决定流程：

#### 任务等级判定

| 等级 | 适用场景 | 文档要求 |
|------|---------|---------|
| **轻量**（默认） | 调试、bug 修复、构建修复、配置修改、≤3 文件改动、真机验证、继续已有任务 | 只维护 HANDOFF.md（可选） |
| **完整** | 新需求、大型重构、跨天设计任务、用户明确要求完整流程 | 需求分析.md + 设计文档.md + SPEC + HANDOFF |

判定规则：
- 默认轻量，除非明确命中完整条件
- 用户说"完整流程"/"走文档"/"正式立项" → 完整
- 拿不准 → 问用户"轻量还是完整？"

#### 轻量流程

1. 声明"轻量模式"+ 一句理由
2. 不创建需求/设计文档，不进 `active_tasks` 注册表
3. 直接进 Step 2（首条回答可精简，不强制完整模板）
4. 收尾时视情况创建/更新 HANDOFF.md

#### 完整流程

1. 在 `<tasks_root>/<task>/` 创建两份人类文档（从模板复制）：
   - `需求分析.md`（来自 `templates/需求分析_模板.md`）
   - `设计文档.md`（来自 `templates/设计文档_模板.md`）
   - 替换模板中的 `{{TASK_NAME}}`、`{{DATE}}`、`{{TASK_DIR}}` 占位符
   - 两份均带头部 `> Status: discussion`
2. **不创建** SPEC.md / HANDOFF.md（实现阶段才通过 `/work implement` 创建）
3. **写人类向文档前**读风格参考：
   - `~/.claude/skills/work/HUMAN_DOC_STYLE.md`
   - `~/.claude/skills/work/style-refs/` 至少 1 份样例
4. 提示用户："已创建讨论文档，定稿后用 `/work implement <task>` 进入实现阶段。"
5. 进入 Step 2

### Step 2: 输出首条回答

**完整等级**：按 `~/.claude/skills/work/templates/workflow.md` 模板输出完整结构（目标/方案/风险/下一步）。

**轻量等级**：自由格式。至少包含：目标一句话 + 方案 + 下一步。不强制模板结构。

### Step 2.5: 讨论结论落地（仅完整等级 discussion 阶段）

**触发分级**：
- **关键决策**（方案选定、架构方向、验收标准变更）→ 立即 Edit 到对应文档章节
- **普通讨论结论**（细节确认、补充说明）→ 积累到阶段性收敛时批量落地

**落地目标映射**：

| 结论类型 | 落地目标 |
|---|---|
| 业务背景 / 痛点 | 需求分析 §1 |
| 方案选定 + 对比 | 需求分析 §3 |
| 范围 / 验收标准 | 需求分析 §4 |
| 风险 | 需求分析 §5 |
| 架构 / 数据模型 / 接口 | 设计文档 §1-§3 |
| 算法 / 边界 case | 设计文档 §5-§6 |
| 测试策略 | 设计文档 §8 |

**写入规则**：
1. 写作风格遵守 `HUMAN_DOC_STYLE.md`
2. 写完后简短告知："已落地到需求分析 §3"——只贴 diff 摘要
3. 批量落地时可合并多条 Edit

### Step 3: 执行

**路由原则**：按任务耦合度决定谁执行（对齐 CLAUDE.md）。

#### 高耦合 → 主模型直接执行

以下任务主模型全程闭环，包括 Edit/Write/Bash：
- 编译 → 读错误 → 改代码 → 重编译
- 测试失败 → 定位 → 修复 → 复测
- 构建/部署失败修复
- 多文件关联改动（改 A 后需根据结果决定改 B）
- 设备/环境排查

#### 低耦合 → 可派 subagent

| 任务类型 | 派给 | 预算 |
|---------|------|------|
| 大范围 grep/符号定位 | Explore(haiku) | 工具 ≤10 |
| git log/status/diff 摘要 | haiku | 时限 5min |
| commit message 生成 | haiku | 回传 <200w |
| 独立文档生成 | sonnet | 边界清晰 |
| 边界清晰的单文件改动 | sonnet | 不依赖前后步骤 |

**歧义判断**：拿不准耦合度 → 主模型执行（宁可不派，不可错派）。

#### 实现计划（复杂改动时写）

每个 Step 含三要素：
- **动作**：文件路径 + 改动内容
- **成功后→**：进哪步
- **失败后→**：恢复动作 + 重试上限 + 兜底

按 `~/.claude/agents/work-agent.md` 子模式决定计划内容。

### Step 4: 收尾（按任务等级分级）

#### 轻量任务收尾

1. 一句话事实摘要：做了什么、验证结果
2. 判断是否需要更新 HANDOFF.md（跨天/中断才需要）
3. 检查记忆写入条件：fixes/ decisions/ feedback/（有触发才写）

#### 完整任务收尾

```bash
python ~/.claude/skills/work/scripts/check_doc_sync.py
```

读输出，对每条 ⚠️ 告警：
- 主动建议在对应 SPEC.md「## 进度」追加今日条目
- 主动建议在对应 HANDOFF.md「## 下次开始」更新状态
- **由用户确认后再写文档**（不要自动改 active_task 文档）

然后跑：
```bash
python ~/.claude/scripts/task_complete.py <项目目录> --fix
```

最后：
- 检查记忆写入条件（按 CLAUDE.md 安全边界 + work-agent.md 收紧版）：fixes/ decisions/ feedback/
- 输出收尾摘要：本轮做了什么 + 下一步建议

## `/work implement <task>` 子流程

触发：用户输入 `/work implement <task_name>`（或在 /work 对话中说"进入实现"）

### Implement Step 1: 校验

- 任务目录 `<tasks_root>/<task_name>/` 存在
- `需求分析.md` + `设计文档.md` 都存在
- 当前 Status 是 `discussion`
  - 如果是 `implementation` → 提示"已在实现期，无需再次执行"
  - 如果是 `missing-status` / `unknown` → 提示用户先修复 Status
- 两份文档 Status 一致（不一致 → 提示用户先修复）
- **人类文档已填充**（用 Bash 跑下面的 grep）：
  ```bash
  grep -E '^\s*<!--' "<tasks_root>/<task_name>/需求分析.md" "<tasks_root>/<task_name>/设计文档.md" || true
  ```
  - 任一行命中 → **拒绝**并提示："需求分析 / 设计文档 仍含模板占位符（独立行 `<!--`），讨论结论未落地。请回 Step 2.5 把结论 Edit 进对应章节，否则派生的 SPEC/HANDOFF 会基于空模板。"
  - 0 命中 → 通过
  - 用 `^\s*<!--` 而非裸 `<!--`：避免代码块/反引号包裹的元讨论误报

### Implement Step 2: 一次性生成 SPEC + HANDOFF

1. Read 两份人类文档全文
2. 基于需求分析的**范围与验收**（§4）+ 设计文档的**架构/接口/测试策略**，生成：
   - `SPEC.md`：验收清单（逐条 V1~Vn）、范围、里程碑、文件影响清单
   - `HANDOFF.md`：初始进度章节、下次开始建议、相关文件列表
3. **不写入** hash / 派生 metadata / AUTO-DERIVED 标记

### Implement Step 3: 用户 review

- 把生成的 SPEC + HANDOFF 内容展示给用户
- 等用户确认：
  - "接受" → 进入 Step 4
  - "调整" → 用户指出修改点，重新生成
  - "取消" → 丢弃，保持 discussion 阶段

### Implement Step 4: 接受后写入

1. 写入 SPEC.md / HANDOFF.md 到 `<tasks_root>/<task_name>/`
   - 如果 SPEC.md 已存在 → 提示"将被覆盖，确认？"
2. 把两份人类文档头部 `Status` 从 `discussion` 改为 `implementation`（**两份必须同步改**）
3. 转换人类文档为 HTML 预览（方便浏览器阅读）：
   ```bash
   python ~/.claude/scripts/md2html.py "<tasks_root>/<task_name>/需求分析.md"
   python ~/.claude/scripts/md2html.py "<tasks_root>/<task_name>/设计文档.md"
   ```
4. 提示："已进入实现阶段。SPEC/HANDOFF 之后由你正常编辑，人类文档建议冻结。HTML 预览已生成在同目录。"

---

## 与 doc_gate.py 的协同

本 skill 在入口主动校验文档（提前预警），`doc_gate.py` 在编辑时被动拦截（兜底）。
**双方共享 `~/.claude/projects/project_registry.json`**——单一数据源。
- registry 全局 sanity check 失败 → doc_gate 输出 warning（不阻断），继续 per-task 检查
- 当前文件匹配的 task 文档不全 → doc_gate 阻断该次编辑
- 当前文件不匹配任何 task → doc_gate 放行

## 任务文档存储位置

任务文档目录由 registry 中的 `tasks_root` 字段决定：
- 默认：`~/.claude/projects/<task>/`（旧路径，向后兼容）
- 本机当前配置：`D:/ClaudeTasks/active/<task>/`（归档任务在 `D:/ClaudeTasks/archived/`）

修改 `tasks_root` 字段即可全局切换路径，三个脚本（check_doc_status / check_doc_sync / doc_gate）都会自动跟进。

## 不做的事

- 不修改 doc_gate.py 等 hook
- 不自动改用户的 SPEC/HANDOFF（建议、由用户确认）
- 不在 Step 3 越过 work-agent.md 的子模式自行发挥
- 不用于快速提问场景（违反 CLAUDE.md 启动协议中的"快速提问"规则）
