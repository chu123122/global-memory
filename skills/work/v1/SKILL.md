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
- 如 cwd 在 `watched_paths` 内（check_doc_status 会提示）且无 SPEC：
  - 提示用户："此目录在监控范围，编辑前需创建 SPEC（doc_gate 会拦），是否先建？"
  - 用户同意 → 在 `<tasks_root>/<task>/SPEC.md` 创建（`tasks_root` 见 `~/.claude/projects/project_registry.json`，本机配置为 `D:/ClaudeTasks/active`）
- 否则直接进入 Step 2

### Step 2: 输出首条回答

按 `~/.claude/skills/work/templates/workflow.md` 模板（先 Read 一遍，再按结构填）输出：
- 🎯 目标
- 📋 任务类型（新 / 继续 task-X，含上次进度）
- 🛠️ 方案（≥1，复杂任务给 2 个对比）
- ⚠️ 风险/影响范围（含需同步的文档）
- 👉 下一步（最后一条必须是收尾跑 check_doc_sync + task_complete）

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
