---
name: work
description: 工作模式入口。对话中开启正式开发流程：文档校验 → 区分新/老任务 → 目标/方案/风险/下一步 → 执行 → 收尾文档同步。Use when 用户打 /work 进入正式任务（新建或继续）。快速提问、闲聊、单行修改不要用。
---

# Work Mode

## When to use
- 正式开发/排查/文档任务（≥3 轮）
- 用户打 `/work [可选任务描述]` 时立即激活
- **不要用**：快速概念问答、闲聊、单行修改、单纯讨论

## Workflow（按序执行，不可跳）

### Step 0: 加载上下文 + 文档状态

按序运行（用 Bash 工具）：
```bash
python ~/.claude/skills/work/scripts/load_context.py
python ~/.claude/skills/work/scripts/check_doc_status.py
```

读完两个脚本输出，进入 Step 1。

### Step 1: 判定新任务 / 继续老任务

基于 `check_doc_status.py` 的「判定建议」+ 用户消息：

**继续老任务**（HANDOFF.md 存在 + 含进度章节，或用户提到老任务名）：
1. 必须先用 Read 工具读 HANDOFF.md 完整内容
2. 输出："上次进度是 X，本次是否继续 Y？"
3. **等用户确认再动手**——不要自作主张接着写

**新任务**（无 HANDOFF 或用户明确说"新做"）：

**小任务豁免**（先判断）：
- 改动 ≤1 个文件且 ≤30 行 → 可在聊天里**显式声明**"小改动豁免文档"+ 一句理由（如"单行 SKILL.md 注释修复"），跳过下面的模板创建直接进 Step 2
- **必须显式声明豁免理由**，否则按完整流程走
- 豁免任务不进 `active_tasks` 注册表

**完整流程**：
1. 在 `<tasks_root>/<task>/` 创建两份人类文档（从模板复制）：
   - `REQUIREMENTS.md`（来自 `templates/requirements_template.md`）
   - `DESIGN.md`（来自 `templates/design_template.md`）
   - 替换模板中的 `{{TASK_NAME}}`、`{{DATE}}`、`{{TASK_DIR}}` 占位符
   - 两份均带头部 `> Status: discussion`
2. **不创建** SPEC.md / HANDOFF.md（实现阶段才通过 `/work implement` 创建）
3. **强制 Read 风格参考**（写人类向文档前必做）：
   - `~/.claude/skills/work/HUMAN_DOC_STYLE.md`（风格规则）
   - `~/.claude/skills/work/style-refs/` 至少 1 份样例（取语境最贴近的；通用情况选 xd-adp 需求分析或设计文档）
   - 两份都不存在 → 警告用户"未配置风格参考，将以默认 AI 风格写作（建议先在 style-refs/ 投放样例）"
4. 提示用户："已创建讨论文档，开始讨论需求和设计。定稿后用 `/work implement <task>` 进入实现阶段。"
5. 进入 Step 2

### Step 2: 输出首条回答

按 `~/.claude/skills/work/templates/workflow.md` 模板（先 Read 一遍，再按结构填）输出：
- 🎯 目标
- 📋 任务类型（新 / 继续 task-X，含上次进度）
- 🛠️ 方案（≥1，复杂任务给 2 个对比）
- ⚠️ 风险/影响范围（含需同步的文档）
- 👉 下一步（最后一条必须是收尾跑 check_doc_sync + task_complete）

### Step 2.5: 讨论结论实时落地（discussion 阶段必做，小任务豁免不适用）

**触发**：本轮讨论得到一条**确定结论**（用户说"决定 / 选定 / 接受方案 / OK 就这样 / 就这么定 / 推荐 X"等）。

**动作**：立即用 Edit 工具回写到对应人类文档章节：

| 结论类型 | 落地目标 |
|---|---|
| 业务背景 / 痛点 | REQUIREMENTS §1.1 |
| 商业价值 | REQUIREMENTS §1.2 |
| 现有方案问题 | REQUIREMENTS §2 |
| 候选方案对比 + 选定 | REQUIREMENTS §3.1（表格） |
| 子决策（含选项 + 理由） | REQUIREMENTS §3.2 |
| 范围 / 验收标准 | REQUIREMENTS §4 |
| 风险 / 回滚 | REQUIREMENTS §5 |
| 架构图 | DESIGN §1 |
| 数据结构 | DESIGN §2 |
| 接口 / 函数签名 | DESIGN §3 |
| 算法 / 状态机 | DESIGN §5 |
| 边界 case | DESIGN §6 |
| 测试策略 | DESIGN §8 |

**写入规则**：
1. 该章节有内容时，**必须删除该章节内的 `<!-- ... -->` 占位注释**
2. 写作风格遵守 `HUMAN_DOC_STYLE.md`（已在 Step 1 Read），优先模仿 `style-refs/` 样例
3. 写完后简短告知用户："已落地到 REQUIREMENTS §3.1"——不在聊天里贴长文，只贴 diff 摘要
4. **每条结论单独 Edit**，不批量；批量易漏

**触发 Step 2.5 不阻塞 Step 3 执行**——讨论收敛过程中边讨论边落地，直到用户说"进入实现 / `/work implement`"。

### Step 3: 执行

按 `~/.claude/agents/work-agent.md` 的子模式：
- 需求拆解
- 方案设计（必须 ≥2 个方案对比）
- Skill 编写
- Bug 定位（参考 bug-locator skill）
- 代码审查（参考 skill-reviewer skill，**只报告不修复**——CLAUDE.md 铁律）
- 文档生成
- 资源管线

### Step 4: 收尾（强制，不可省）

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
- 检查记忆写入条件（按 CLAUDE.md 铁律 + work-agent.md 收紧版）：fixes/ decisions/ feedback/
- 输出收尾摘要：本轮做了什么 + 下一步建议

## `/work implement <task>` 子流程

触发：用户输入 `/work implement <task_name>`（或在 /work 对话中说"进入实现"）

### Implement Step 1: 校验

- 任务目录 `<tasks_root>/<task_name>/` 存在
- REQUIREMENTS.md + DESIGN.md 都存在
- 当前 Status 是 `discussion`
  - 如果是 `implementation` → 提示"已在实现期，无需再次执行"
  - 如果是 `missing-status` / `unknown` → 提示用户先修复 Status
- 两份文档 Status 一致（不一致 → 提示用户先修复）
- **人类文档已填充**（用 Bash 跑下面的 grep）：
  ```bash
  grep -E '^\s*<!--' "<tasks_root>/<task_name>/REQUIREMENTS.md" "<tasks_root>/<task_name>/DESIGN.md" || true
  ```
  - 任一行命中 → **拒绝**并提示："REQUIREMENTS / DESIGN 仍含模板占位符（独立行 `<!--`），讨论结论未落地。请回 Step 2.5 把结论 Edit 进对应章节，否则派生的 SPEC/HANDOFF 会基于空模板。"
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
3. 提示："已进入实现阶段。SPEC/HANDOFF 之后由你正常编辑，人类文档建议冻结。"

---

## 与 doc_gate.py 的协同

本 skill 在入口主动校验文档（提前预警），`doc_gate.py` 在编辑时被动拦截（兜底）。
**双方共享 `~/.claude/projects/project_registry.json`**——单一数据源。
如果用户跳过本 skill 的预警直接编辑代码，doc_gate 会按原逻辑拦下。

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
