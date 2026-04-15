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

### [P0-4] Subagent 从未真正派生，Agent工具调用路径断路
- **问题**：`Agent` 工具可用类型中已注册 `learning-agent` 和 `work-agent`，正确行为是：用户说"以学习Agent身份" → 主Claude调用 `Agent(subagent_type="learning-agent", prompt="...")` → 真正派生独立Agent。实际发生的是：主Claude读 agent.md 后调整自身行为，无任何 subagent 派生。
- **测试证据**：T01-T38 全程（38个测试），`Agent` 工具调用次数 = 0。
- **根因**：CLAUDE.md 的"Agent判定规则"只写了"触发学习Agent"，没有明确"通过 Agent 工具派生"还是"读 agent.md 调整行为"。主Claude默认选了成本更低的调整行为路径。
- **影响**：真正的subagent派生提供独立上下文+工具隔离；当前行为调整方式上下文共享，无隔离，两个"Agent"实际是同一个Claude换了规则。
- **修复**：在 CLAUDE.md 的 Agent判定规则中明确说明：**触发条件满足时，使用 `Agent(subagent_type=...)` 工具派生**，而不是手动读agent.md。同时在 learning-agent.md / work-agent.md 的 description 中补充触发语义。

### [P0-5] CLI 记忆沉淀为零，有机学习完全未发生
- **问题**：整个 38 测试会话（约5小时），`C:\Users\chu\.claude\projects\E--CS-Study-Vibe\memory\` 目录写入文件数 = 0。用户纠错、学习偏好、新发现事实等本应随对话自然沉淀的内容，全程无一记录。
- **根因（多层叠加）**：
  1. P0-1（双记忆冲突）导致写入目标不明确——CLI system prompt 说写 CLI memory，CLAUDE.md 说写 global-memory，主Claude无所适从默认不写
  2. P1-1（Hooks未配置）导致对话结束后无自动触发 post_task_hook.py
  3. P0-4（subagent未派生）导致 learning-agent 的"宽松记忆策略"从未在独立上下文中执行
  4. CLAUDE.md 的写入条件检查在"对话结束前"，但"对话结束"在CLI中没有明确的触发点
- **影响**：知识库停留在初始状态，feedback系统完全空洞（T16证实），弱项追踪无更新。系统越用越旧而不是越用越聪明。
- **修复**：解决 P0-1（确定写入目标）+ P0-4（subagent真正派生，让learning-agent的记忆策略在独立上下文生效）+ P1-1（Hooks触发收尾逻辑）。三者同时修复，有机沉淀才能真正启动。

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

### [P1-6] doc-generator 归档后无替代方案
- **问题**：doc-generator 已归档（`_archived/`），但"生成技术设计文档"和"生成学习笔记文档"是高频场景，归档后没有替代Skill。T23/T28两个测试均因此降级失败。
- **影响**："学习→记录"这条核心工作流断链（learning-agent → doc-generator）。
- **修复方向**：评估是否从 archived 中迁出（可能只是过时而非损坏），或新建轻量版笔记生成Skill。

### [P1-7] skill-auditor/scripts/audit_skill.py 不存在
- **问题**：skill-auditor 的 SKILL.md 引用 `scripts/audit_skill.py`，但 skill-auditor/v1/ 目录下只有 SKILL.md，scripts/ 目录从未创建，脚本从未实现。
- **影响**：skill-auditor 无法自动执行审计，只能手动根据 SKILL.md 的判断标准逐项检查，失去了自动化价值。
- **修复**：实现 `audit_skill.py`，或在 SKILL.md 中去除脚本引用，改为纯AI指令式执行。

### [P1-9] skill_regression_test.sh 的 `find` 缺 `-L` flag，symlink部署下永远失败
- **问题**：脚本中 `find "$SKILL_DIR" -name "SKILL.md"` 不追踪目录级软链接，导致所有以 symlink 方式部署的 Skill（当前5个）回归测试均报 "SKILL.md 不存在"，exit 1。
- **复现**：`bash skill_regression_test.sh cpp-tutor` → ❌
- **修复**：将脚本第22行改为 `find -L "$SKILL_DIR" -name "SKILL.md"`

### [P1-10] memory_cleanup.sh 在 Windows Git Bash 下静默失效
- **问题**：脚本用 `stat -f %m`（macOS）和 `stat -c %Y`（Linux）双路 fallback 获取文件修改时间，均在 Windows Git Bash 下失败。`DAYS_AGO` 赋值为多行文本，算术运算抛 syntax error，导致从不检查任何文件，但 exit 0。**假阳性，比报错更危险。**
- **修复**：改用 `python3 -c "import os; print(int(os.path.getmtime('$f')))"` 替代 stat，跨平台一致。

### [P1-11] test-runner.md 路径写错（文档缺陷）
- **问题**：T34/T35/T36 均使用 `~/.claude/skills/_bootstrap/scripts/`，该路径不存在。正确路径为 `~/.claude/skills-repo/_bootstrap/scripts/`。
- **影响**：测试runner无法直接粘贴运行，需要手动修正路径。
- **修复**：修改 test-runner.md 第3处路径；或在 `~/.claude/skills/` 下创建 `_bootstrap → ~/.claude/skills-repo/_bootstrap` 软链接。

### [P1-8] SKILL.md 触发条件是文档注释，CLI 下无自动触发机制
- **问题**：所有 SKILL.md 中"触发：用户说X时使用"的说明是面向人类的注释，CLI 环境下不存在任何 hook 或自动加载机制。只有 AI 在当前上下文中恰好读过该 SKILL.md 时才能手动跟随其流程。跨会话后上下文清空，这条路就断了。
- **根因**：P1-1（Hooks未配置）的直接后果。即使 Hooks 配置后，也需要设计"根据请求语义主动加载对应 SKILL.md"的触发逻辑。
- **修复**：
  1. 先修复 P1-1（配置 Hooks）
  2. 在 PostToolUse 或 Stop hook 中，根据对话内容语义匹配 SKILL.md description，自动 inject 到上下文
  3. 或在 CLAUDE.md 中明确说明"用户需要显式 /skill-name 触发"，设置用户预期

---

## 今晚已修复

- [x] 初始化完成：global-memory + skills-repo 已克隆，auto-sync 守护进程运行
- [x] 5个 Skills 软链接已创建（bug-locator/cpp-tutor/migrate-executor/skill-auditor/skill-creator）
- [x] learning-agent + work-agent 已部署，CLI 下可作为 subagent 调用
- [x] verify_memory.py 13/13 PASS，verify_prompt_system.py 17/17 PASS

## ba68de3 + c5ca678 修复（2026-04-14 CLI Sonnet）

- [x] **P0-1** 双记忆冲突 → CLAUDE.md 明确「唯一记忆存储 = global-memory」
- [x] **P0-4** Subagent 未派生 → CLAUDE.md Agent 判定规则改为「优先 Agent 工具派生 + fallback 行为调整」
- [x] **P1-3** WORKFLOW 优先级 → 改为「项目 SPEC」
- [x] **P1-4** AI_CONTEXT.md 引用 → 删除，改为 MEMORY.md + HANDOFF.md
- [x] **P1-7** skill-auditor 脚本不存在 → 改为 AI 指令式手动清单（8 项检查）
- [x] **P1-9** find 缺 -L → 已修复（两处）
- [x] **P1-10** memory_cleanup.sh stat 跨平台 → 改用 python3 os.path.getmtime()
- [x] feedback 空壳 → 两文件已激活（从 CLAUDE.md 提取已知偏好）
- [x] 新增 CLAUDE.md 铁律：知识库强制前置读取 / CHANGELOG 即时更新 / 纠正分类规则
- [x] 新增复盘触发规则（>10 轮自动建议）
- [x] verify_prompt_system.py 大重构（适配新规则）

## WorkBuddy 端修复（2026-04-14 09:54）

- [x] **P0-4 增强** guardian-agent.md 创建（规范守卫，交付前自动派生审计）
- [x] CLAUDE.md 新增「交付前门禁」铁律（guardian-agent 派生 + fallback task_complete.py）

## 心动公司电脑初始化修复（2026-04-15 Opus 4.6）

- [x] **P0-3** skill-reviewer Junction 链接已创建（PowerShell mklink /J）
- [x] **P0-2** memory-rules.md 复制到 global-memory/ 并在 MEMORY.md 中索引
- [x] **P1-1** Hooks 配置：Stop hook 接入 post_task_hook.py（settings.json）
- [x] **P1-2** SKILL.md description 已为英文语义描述风格（之前批次已修复）
- [x] **P1-5** work-agent.md 中 doc-templates.md 路径改为绝对路径 D:/skills-repo/_templates/
- [x] **P1-11** test-runner.md 已不存在，无需修复
- [x] **P2-1** DOC-06 复杂非代码任务前置设计规范已添加到 conventions.md
- [x] **P2-2** CLAUDE.md Agent 判定规则补充两种实现方式说明（行为调整 vs Subagent 派生）
- [x] Python 3.12 已安装（winget）
- [x] 全套 bootstrap 完成：CLAUDE.md + 3 agents + 30 scripts + 6 skills(Junction) + global-memory(Junction)

---

## 修复优先级建议（已大部分完成）

**第一批：≤30分钟，直接修**
1. **P0-3** skill-reviewer 软链接（`ln -s`，5分钟，立即生效）
2. **P0-4** CLAUDE.md Agent判定规则 → 补充"用 Agent(subagent_type=...) 派生"语义
3. **P1-4** 删除 CLAUDE.md 中的 AI_CONTEXT.md 引用
4. **P1-9** skill_regression_test.sh 的 `find` 加 `-L` flag（单行修改）
5. **P1-11** 修正 test-runner.md 路径（skills/ → skills-repo/）

**第二批：需要架构决策**
6. **P0-1 + P0-5** 双记忆冲突决策（是否废弃CLI memory，明确写入全走global-memory）→ 这是P0-5（记忆沉淀为零）的根因之一，先决策再修
7. **P0-2** memory-rules.md 位置修复
8. **P1-1** Hooks 配置（P0-5根因之二；配置后 post_task_hook/sync_index 才能自动触发）
9. **P1-3** WORKFLOW 优先级修复
10. **P1-6** doc-generator 归档评估（迁出还是重建轻量版）

**第三批：改进型**
11. **P1-2** SKILL.md description 重写（6个Skill批量操作）
12. **P1-5** doc-templates.md 路径修复
13. **P1-7** audit_skill.py 实现或 SKILL.md 修正
14. **P1-8** Skill 自动触发机制设计（依赖 P1-1 完成）
15. **P1-10** memory_cleanup.sh 跨平台修复
16. **P2-1** DOC-06 规范补充
17. **P2-2** Agent 范式差异说明补充文档
