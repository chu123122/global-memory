# global-memory · 接入指南

> 这份文档回答一个问题：**新东西怎么接入 harness 体系**。
>
> 配套阅读：
> - `MAINTENANCE.md`：现有工具命令清单（已存在的东西怎么用）
> - `README.md`：体系总览 + Release Notes
> - `memory-rules.md`：记忆写入规则细节

---

## 0. 接入前先问自己

| 问题 | 答案 |
|---|---|
| 是「行为约束」吗？ | → 改 `agents/CLAUDE.md` 或新增 `feedback/*.md` |
| 是「跨任务知识」吗？ | → 新增 `knowledge/*.md` |
| 是「跨任务复用流程」吗？ | → 新增 Skill |
| 是「lifecycle 拦截/自动化」吗？ | → 新增 Hook |
| 是「批处理/CLI 工具」吗？ | → 新增 Script |
| 是「subagent 职能」吗？ | → 新增 Agent |
| 都不是 | → 想清楚再来 |

**硬约束**：每个文件归属一个分类，分类决定路径、frontmatter 规范、是否被 lint gate 拦。

---

## 1. 加 Hook（lifecycle 拦截）

### 1.1 放哪

```
~/.claude/global-memory/harness/hooks/<hook_name>.py
```

命名：`<动词>_<对象>.py`，例 `retrieve_inject.py` / `memory_lint_gate.py` / `doc_gate.py`。

### 1.2 入口契约

stdin = cc 传入的 JSON（按 hook event 决定字段，PreToolUse/UserPromptSubmit/Stop 等不同）。
stdout = 注入给 AI 的额外 context 或拦截信号。
exit code = 0 放行 / 非 0 阻断（按 event 决定语义）。

**必须遵守**：
- 失败必须 fail-open（默认放行），用 `try/except Exception` 兜底
- 单次执行 ≤2s，超时自己降级
- 提供 env 总开关，例 `HARNESS_<NAME>=0` 关闭
- 异常落到独立 debug 日志（`~/.claude/logs/<name>_debug.log`），不要 silent pass

### 1.3 注册

在 `$env:CLAUDE_HOME/settings.json` 的 `hooks.<EventName>` 数组里追加：

```json
{
  "type": "command",
  "command": "python ~/.claude/global-memory/harness/hooks/<your_hook>.py"
}
```

注意 hook 链有顺序，注入类放链尾，拦截类放链头。

### 1.4 测试

```bash
# 手动 fire
echo '{"prompt":"test","session_id":"x"}' | python ~/.claude/global-memory/harness/hooks/<your_hook>.py
echo "exit: $?"

# 验证日志写盘
stat ~/.claude/logs/<your_hook>*.log
```

### 1.5 别做

- ❌ 写共享文件不加锁
- ❌ 拉网络（hook 是热路径）
- ❌ 调外部 LLM
- ❌ 长时间持锁

---

## 2. 加 Skill（用户/AI 可调用的流程）

### 2.1 放哪

仓库结构：
```
~/.claude/global-memory/skills/<skill_name>/v1/
  SKILL.md          # 必需，frontmatter + 说明
  scripts/          # 可选
  templates/        # 可选
```

部署后通过 junction 暴露到 `~/.claude/skills/<skill_name>`。

### 2.2 SKILL.md frontmatter（必需）

```markdown
---
name: <skill-slug>
description: 一句话说清楚干什么 + 触发场景（描述决定 cc 何时推荐）
---

# Skill 正文
```

`description` 决定 cc 是否在用户消息中识别并触发，必须含**何时用 / 何时不用**两面。

### 2.3 注册到 bootstrap

`~/.claude/global-memory/bootstrap.py` 的 `SKILLS` 常量里加 `<skill_name>`。然后跑：

```powershell
python ~/.claude/global-memory/bootstrap.py install
```

### 2.4 测试

```powershell
# 检查 junction
ls "$env:CLAUDE_HOME/skills/<skill_name>"

# 让 cc 识别（重启会话或 /skill 列表）
```

### 2.5 与 Subagent 的区别

| Skill | Subagent |
|---|---|
| 主对话内执行，共享上下文 | 独立子上下文，回传摘要 |
| 流程固化（多步序列）| 职能单一（一个角色） |
| 用户/AI 主动调用（/skill）| 主模型按耦合度派遣 |

不确定 → 优先 Skill。

---

## 3. 加 Script（CLI 工具）

### 3.1 放哪

```
~/.claude/global-memory/harness/<script_name>.py        # 维护类
~/.claude/global-memory/harness/scripts/<script_name>.py # 一般工具
```

部署后通过 `~/.claude/scripts` junction 暴露。

### 3.2 入口契约

- `argparse` 标准 CLI，含 `--help`
- 退出码：0 成功 / 1 用户错误 / 2 系统错误
- 默认只读，写操作必须 opt-in（`--fix` / `--apply` / `--write`）
- 长操作支持 `--dry-run`
- 输出双模：人类可读 + `--json` 机器可读

### 3.3 日志接入（可选）

如果是常态运行的脚本，写到 `~/.claude/logs/<script>.jsonl`，one record per line。便于 `view_*` viewer 和 `analyze_*` 周报。

### 3.4 注册到 MAINTENANCE

新 CLI 进 `MAINTENANCE.md` 的「快速判断」表 + 「健康检查矩阵」表，否则后续维护者找不到。

### 3.5 接入 gate_check.py（可选）

如果脚本是「治理硬约束」（违反必须修才能推进），考虑接入 `gate_check.py` 成 G<N>。

完整模板：`docs/gate-template.md`

简版 5 步：
1. 确认脚本退出码语义清晰（0=过，非 0=违规）+ stdout 含稳定标志
2. 在 `gate_check.py` `check_prereqs()` 追加 G<N> 项
3. 决定严重度 FAIL / WARN（存量遗留多用 WARN）
4. 跑一次 gate_check.py 看 GATE-REPORT
5. 更新 `docs/scripts-registry.md` § 2 + `docs/gate-template.md` 当前列表

### 3.6 别让脚本成孤儿

新加的 script 必须：
- 进 `docs/scripts-registry.md` 注册（含触发方 / 失败动作）
- 选触发方：Hook / Gate / Manual / CronOrDaemon / Smoke 之一
- 若仅 Manual，在 `MAINTENANCE.md` 给 CLI 用法
- 任何脚本默认在 ≤ 6 周后被 `scan_orphan_scripts.py` 标 ORPHAN（待 P5 实现）

---

## 4. 加 Memory（feedback / knowledge / fixes / decisions）

### 4.1 选分类

| 分类 | 用途 | 触发写入 |
|---|---|---|
| `feedback/` | 行为纠正、风格偏好 | 用户说"不要这样" / "这样写好" |
| `knowledge/` | 跨任务知识、概念解释 | 学到新东西、踩坑后总结 |
| `fixes/` | 具体修复经验 | bug 定位+修复后 |
| `decisions/` | 架构决策记录 | 重大方向取舍 |

### 4.2 模板（强制 frontmatter）

写入前 Read 对应模板：
- `~/.claude/global-memory/templates/memory_feedback.md.tmpl`
- `~/.claude/global-memory/templates/memory_knowledge.md.tmpl`
- `~/.claude/global-memory/templates/memory_fixes.md.tmpl`
- `~/.claude/global-memory/templates/memory_decision.md.tmpl`

照搬骨架：
```yaml
---
description: <一句话摘要，给 retrieve 决定相关性用>
priority: high | medium | low
status: active | deprecated
trigger:
  keywords:
    - tool:<name>      # 带 namespace 前缀
    - concept:<name>
    - error:<name>
  tags:
    - <domain>          # 必须来自 triggers_vocab.yaml 的 domains 列表
  stages:
    - discussion | implementation | debug
last_updated: YYYY-MM-DD
---

# 标题

## 现象 / 现状
## 根因 / 原因
## 修复 / 决策
## 验证
```

### 4.3 trigger metadata 规则

- `keywords` 1-5 个，**带 namespace 前缀**（`tool:` / `concept:` / `error:` / `cmd:` / `platform:`），从用户原话挑高频术语
- `tags` ≤5 个，**必须**来自 `~/.claude/global-memory/harness/scripts/triggers_vocab.yaml` 的 `domains` 列表
- 无 namespace → memory_lint_gate 会拦 + 报 ambiguous warning

### 4.4 写完自查

```bash
python ~/.claude/global-memory/harness/scripts/harness_memory_lint.py <file>
```

PreToolUse `memory_lint_gate.py` 会在写入时自动拦。

### 4.5 MEMORY.md 索引

新加的 memory 文件由 `sync_index.py` 自动收录到 MEMORY.md AUTO-INDEX 区。**别手动改 MEMORY.md 索引区**。

---

## 5. 加 Agent（subagent 职能）

### 5.1 放哪

```
~/.claude/global-memory/agents/<agent-name>.md
```

部署后 `~/.claude/agents` junction 暴露。

### 5.2 内容契约

frontmatter：
```yaml
---
name: <agent-name>
description: 何时用 / 何时不用（决定主模型派遣判断）
tools: [Read, Grep, Glob, ...]   # 限定工具权限
---
```

正文写：
- 角色定位（一句话）
- 输入契约（主模型派遣时传什么）
- 输出契约（回传格式，≤200w 硬约束）
- 失败/拒绝行为
- 不做的事

### 5.3 预算约束

每次派遣主模型必须传：
- 工具上限（探索 ≤10 / grep ≤5）
- 时限 5min
- 回传 <200w，禁返 raw grep / file contents
- 失败格式：已试 / 错误 / 怀疑 / 建议

详见 `agents/CLAUDE.md` 「Subagent 约束」节。

### 5.4 注册到 bootstrap

如改了 agent 列表，跑 `python bootstrap.py install` 重建 junction。

---

## 6. 改 CLAUDE.md（行为合同）

### 6.1 改在哪

- **全局行为**：`~/.claude/global-memory/agents/CLAUDE.md`（已通过 junction 链接到 `~/.claude/CLAUDE.md`）
- **项目级覆盖**：项目根 `CLAUDE.md`（不在本仓库）

### 6.2 哪些改动需要同步 README + VERSION

按版本级判定（参照 README Release Notes 历史）：

| 改动 | 是否版本级 | 同步项 |
|---|---|---|
| 加 hook | 是 | README Release Notes + VERSION bump |
| 加 skill | 是 | 同上 |
| 加 agent | 是 | 同上 |
| 架构改动（如四层 → 五层） | 是 | 同上 + 改 README 架构图 |
| 改单条 feedback / knowledge | 否 | 仅 CHANGELOG.md |
| 文档措辞调整 | 否 | 仅 CHANGELOG.md |

### 6.3 CHANGELOG 强约束

修改 `global-memory/` 任意文件 → 必须 append 到 `CHANGELOG.md`（按月归档到 `CHANGELOG_archive/`）。审计链。

---

## 7. 接入完成后

跑下面三个，全过才算完：

```powershell
# 部署检查
python ~/.claude/global-memory/bootstrap.py check

# 全套规范验证
python ~/.claude/global-memory/harness/verify_all.py

# 体检
python ~/.claude/global-memory/harness/maintain.py doctor
```

任一有问题 → 修了再交付。

---

## 8. 常见误区

| 误区 | 正解 |
|---|---|
| feedback 写满"应该"/"大概" | 必须明说"不确定"或具体到 case |
| keywords 不加 namespace | 加 `tool:` / `concept:` / `error:` 前缀，否则 lint 拦 |
| Skill 描述只写"做什么"不写"何时" | description 必须含触发场景，cc 才能识别 |
| Hook 用 `except Exception: pass` 吞错 | 必须落 debug 日志，不然出问题查不到 |
| Memory 写完不进 MEMORY.md | 别手动改，`sync_index.py` 自动收录 |
| 加 agent 不给预算契约 | 派遣时必须传工具上限/时限/回传上限 |
| 同步改 README 忘了 VERSION | 版本级改动两者捆绑，少一就漏 |

---

## 9. 反馈本指南

发现接入流程缺步骤或文档不准 → 改本文件 + append CHANGELOG。

> 创建：2026-05-21
> 配套：MAINTENANCE.md（命令）+ memory-rules.md（记忆规则）+ README.md（总览）
