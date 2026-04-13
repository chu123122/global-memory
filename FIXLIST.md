---
name: FIXLIST
description: CLI 迁移适配问题清单，由 Sonnet 4.6 扫描生成，待 Opus 修复
type: project
created: 2026-04-14
scanned_by: claude-sonnet-4-6
target: claude-opus-4-6（公司电脑）
---

# CLI 适配问题修复清单

> 背景：本系统原在公司 WorkBuddy 环境构建，2026-04-14 首次在个人电脑 Claude Code CLI 跑通。
> 本文档记录扫描发现的所有问题，按优先级排列，供 Opus 明天逐条修复。
>
> 扫描范围：Skills层 / Agents层 / Hooks层 / CLAUDE.md适配性 / CLI增量机会 / 记忆系统

---

## P0 — 影响核心功能，必须先修

### [P0-1] 双记忆系统冲突，无优先级定义
- **问题**：CLI 内置 memory 系统（`~/.claude/projects/E--CS-Study-Vibe/memory/`）和自定义 global-memory（`~/.claude/global-memory/`）并存，两套系统互不知晓。CLI 系统 prompt 指示写 CLI memory，CLAUDE.md 指示写 global-memory，Claude 无明确依据选择。
- **现状**：CLI memory 目录存在但为空（0文件），global-memory 正常运作（36文件）。
- **根因**：CLI 的 auto-memory 功能是 WorkBuddy 时代没有的，设计时未考虑。
- **修复方案（二选一，需 Opus 决策）**：
  - 方案A：禁用 CLI memory，在 CLAUDE.md 明确声明"全局记忆用 global-memory，CLI memory 不使用"
  - 方案B：整合两套——CLI memory 用于会话级快速记录，global-memory 用于持久化归档，在 CLAUDE.md 定义分工

### [P0-2] memory-rules.md 引用失效
- **问题**：CLAUDE.md 写着"CHANGELOG 分级规则见 memory-rules.md"，但此文件不在 global-memory/ 下，Claude 找不到。
- **实际位置**：`~/.claude/skills-repo/_archived/memory-manager/references/memory-rules.md` 和 `~/.claude/skills-repo/_bootstrap/memory-rules.md`（均不在 Claude 上下文路径内）
- **根因**：memory-manager skill 被归档时，引用没有同步更新。
- **修复**：将 memory-rules.md 复制到 `~/.claude/global-memory/memory-rules.md` 并在 MEMORY.md 中索引；或直接将规则内容内联到 CLAUDE.md 相关段落。

### [P0-3] skill-reviewer 未软链接，work-agent 引用失效
- **问题**：work-agent.md 的 Skill 触发表中引用了 `skill-reviewer`，但 `~/.claude/skills/` 下没有对应软链接，CLI 无法找到此 Skill。
- **实际情况**：`skill-reviewer/v1/SKILL.md` 在 skills-repo 中完整存在（代码/文档审查 Skill），只是没有被部署。
- **修复**：在 `~/.claude/skills/` 下为 skill-reviewer 创建软链接：
  ```
  ln -s ~/.claude/skills-repo/skill-reviewer/v1 ~/.claude/skills/skill-reviewer
  ```

---

## P1 — 功能不完整，影响日常使用

### [P1-1] Hooks 完全未配置
- **问题**：settings.json 里没有任何 hooks，以下脚本全部需要手动跑，自动化层断路。
- **应该接入 hooks 的脚本**：

| 脚本 | 期望触发时机 | 对应 CLI hook 类型 |
|------|-------------|-------------------|
| `post_task_hook.py` | 每次对话结束后 | `Stop`（after response） |
| `sync_index.py` | 写入记忆文件后 | `PostToolUse`（Write/Edit 工具） |
| `update_stats.py` | 同上 | `PostToolUse`（Write/Edit 工具） |
| `task_complete.py` | 交付代码前 | 手动触发为主，或 `Stop` |

- **修复**：在 settings.json 中补充 hooks 配置：
  ```json
  {
    "hooks": {
      "Stop": [
        {
          "matcher": "",
          "hooks": [{"type": "command", "command": "python ~/.claude/scripts/post_task_hook.py --auto-fix"}]
        }
      ],
      "PostToolUse": [
        {
          "matcher": "Write|Edit",
          "hooks": [{"type": "command", "command": "python ~/.claude/scripts/sync_index.py && python ~/.claude/scripts/update_stats.py"}]
        }
      ]
    }
  }
  ```
  **注意**：PostToolUse 在每次 Write/Edit 都触发，sync_index 需要加"只在 global-memory 目录下触发"的条件判断，否则会过度触发。

### [P1-2] SKILL.md description 字段对 CLI 触发不友好
- **问题**：大部分 SKILL.md 的 description 写的是"用户说X时使用"（面向用户描述），CLI 下 Claude 用 description 做语义匹配来决定是否调用 Skill，这种写法触发不精准。
- **各 Skill 现状**：

| Skill | description 问题 | 严重程度 |
|-------|-----------------|---------|
| bug-locator | "触发：用户说'定位bug'时使用" | ⚠️ 中等，触发词在里面但冗余 |
| cpp-tutor | "触发：用户说'学C++'时使用" | ⚠️ 中等 |
| migrate-executor | "触发：用户说'搬迁'时使用" | ⚠️ 中等 |
| skill-auditor | 描述详细，场景覆盖好 | ✅ 基本 OK |
| skill-creator | 英文功能性描述，CLI 兼容最好 | ✅ OK |
| skill-reviewer | "触发：用户说'审查代码'时使用" | ⚠️ 中等 |

- **修复方向**：description 改为语义描述（"when to use"），去掉"用户说X"的硬编码触发词写法，参考 skill-creator 的英文写法风格。示例：
  ```
  # 现在（不好）
  触发：用户说"定位bug""排查问题"时使用。
  
  # 改为（好）
  Use when debugging: systematically locate root cause via reproduce→narrow→identify→fix→verify.
  ```

### [P1-3] CLAUDE.md 中 WORKFLOW 优先级引用无效
- **问题**：CLAUDE.md 指令优先级写着 `3. WORKFLOW`，但 WORKFLOW.md 在 `_templates/` 下，不在任何 Claude 会加载的上下文路径里，CLI 下这条优先级没有实际意义。
- **修复（二选一）**：
  - 删除优先级第3条，或改为"项目 SPEC > 用户指令"
  - 将 WORKFLOW.md 移到 global-memory/ 或明确说明其作用范围仅限项目级

### [P1-4] AI_CONTEXT.md 引用是 WorkBuddy 遗留
- **问题**：CLAUDE.md 新对话启动协议写着"读 AI_CONTEXT.md（或 MEMORY.md+HANDOFF.md）"，AI_CONTEXT.md 是 WorkBuddy 特有的文件格式，CLI 下没有这个文件也不会生成。
- **修复**：删除 AI_CONTEXT.md 引用，直接写"读 MEMORY.md + 项目的 HANDOFF.md"。

### [P1-5] _templates/doc-templates.md 路径在 agents 里不可达
- **问题**：work-agent.md 的 Skill 触发表引用 `_templates/doc-templates.md (Reference)`，文件实际在 `~/.claude/skills-repo/_templates/doc-templates.md`，但 Claude 在对话中无法自动定位此路径（没有暴露给 agent 的路径约定）。
- **修复**：在 work-agent.md 里改为绝对路径引用，或将 doc-templates.md 复制到 global-memory/ 下并索引。

---

## P2 — 设计欠缺，不影响使用但影响体验

### [P2-1] 非代码复杂任务缺少"设计文档前置"规范
- **问题**：conventions.md 的 DOC-05 规范只覆盖代码项目（SPEC.md + TECHNICAL_DESIGN.md），但对于"系统审查""分析报告""规划任务"等非代码复杂任务，没有对应的前置文档规范，导致 AI 跳过设计步骤直接执行（本次扫描任务就发生了这个情况）。
- **修复**：在 conventions.md 中新增一条规范，例如：
  ```
  DOC-06：复杂非代码任务前置设计
  规则：预计 >3 轮的非代码任务（审查/分析/规划），
  开始前必须先输出任务计划（目标/范围/输出格式），
  经用户确认后再执行。
  ```

### [P2-2] Agent 切换范式差异未在文档中说明
- **问题**：learning-agent 和 work-agent 的原设计意图是"整个 session 切换为该模式"，但 CLI 下 agents/ 目录中的 agent 是以 subagent 形式被派生，不是替换主 Claude 的行为。这个差异没有在任何文档中说明，用户和 AI 都可能产生混淆。
- **现状**：通过 CLAUDE.md 的 Agent 判定规则（`@learning → 学习Agent`），主 Claude 读取规则后调整自身行为，这条路是通的；subagent 派生是另一条路。两条路并行存在但未明确定义使用场景。
- **修复**：在 CLAUDE.md 或 agents/ 的 README 中补充说明两种使用方式的区别和适用场景。

### [P2-3] CLI 增量功能未评估利用
- **问题**：以下 CLI 功能当前系统完全未用，部分有接入价值：

| 功能 | 当前状态 | 接入价值 |
|------|---------|---------|
| Hooks (PostToolUse/Stop) | ❌ 未配置 | ⭐⭐⭐ 高（已在P1-1列出） |
| MCP 服务器 | ❌ 未配置 | ⭐⭐ 中（可接 git/文件系统工具） |
| 自定义 keybindings | ❌ 未配置 | ⭐ 低（方便但非必须） |
| 后台 Agent（run_in_background） | ❌ 未使用 | ⭐⭐ 中（并行任务时有用） |
| Worktree 隔离 | ❌ 未使用 | ⭐ 低（已有 git 分支工作流） |
| Plan mode (`/plan`) | ❌ 未集成 | ⭐⭐ 中（可替代 SPEC 前置步骤） |

- **修复建议**：明天优先评估 MCP 服务器和 Plan mode 的接入价值，其余按需。

### [P2-4] skill-creator description 语言不统一
- **问题**：5个 Skill 的 description 中，skill-creator 是英文，其余是中文。CLI 的语义匹配需要一致的语言风格。
- **修复**：统一为中文或英文（建议参考 skill-creator 的英文风格，因为更适合 CLI 的描述匹配机制）。

---

## 今晚已修复

- [x] 初始化完成：global-memory + skills-repo 已克隆，auto-sync 守护进程运行
- [x] 5个 Skills 软链接已创建（bug-locator/cpp-tutor/migrate-executor/skill-auditor/skill-creator）
- [x] learning-agent + work-agent 已部署，CLI 下可作为 subagent 调用
- [x] verify_memory.py 13/13 PASS，verify_prompt_system.py 17/17 PASS

---

## 修复优先级建议（明天 Opus 执行顺序）

1. **P0-3** skill-reviewer 软链接（5分钟，立即生效）
2. **P0-2** memory-rules.md 位置修复
3. **P0-1** 双记忆系统冲突决策（需要架构决策，先讨论再动手）
4. **P1-4** 删除 AI_CONTEXT.md 引用
5. **P1-3** WORKFLOW 优先级修复
6. **P1-2** SKILL.md description 字段重写（6个 Skill，批量操作）
7. **P1-1** Hooks 配置（需要测试，最后处理）
8. **P1-5** doc-templates.md 路径修复
9. **P2-1** DOC-06 规范补充
10. **P2-2** Agent 范式差异说明
