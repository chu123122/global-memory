---
doc_type: reference
status: active
last_updated: 2026-05-21
retrieve: true
retrieve_summary: "Hook 链顺序：UserPromptSubmit→changelog_inject/sync_inject/route_check/retrieve_inject；PreToolUse Write|Edit→memory_protector/memory_lint/doc_gate/diff_backup；Stop→post_task_hook。失败不破业务。配置见 settings.json"
trigger:
  keywords: [concept:hook, concept:chain, tool:harness]
  tags: [workflow, tooling]
---

# Hook Chain · UserPromptSubmit / PreToolUse / PostToolUse 顺序与契约

> Hook 链 source of truth 是 `harness/hook_manifest.json`。`bootstrap.py install` 从 manifest 渲染 `~/.claude/settings.json`；本文按事件类型列顺序、输入输出、失败降级。
> 配套：`docs/scripts-registry.md` § 1 列出每 hook 用途。

---

## 总览：事件 → hook 列表

| 事件 | matcher | hook 链（按顺序）|
|---|---|---|
| `UserPromptSubmit` | * | changelog_inject → sync_inject → route_check → retrieve_inject |
| `PreToolUse` | Bash | dangerous_command_blocker |
| `PreToolUse` | Write\|Edit\|MultiEdit | memory_file_protector → memory_lint_gate → doc_gate → diff_backup |
| `PreToolUse` | Read | read_large_file_guard |
| `PreToolUse` | Agent | agent_prompt_gate |
| `PostToolUse` | * | audit_logger |
| `PostToolUse` | Write\|Edit | diff_show |
| `SubagentStart` | * | subagent_logger |
| `SubagentStop` | * | subagent_stop_logger |
| `Stop` | * | post_task_hook |
| `statusLine` | * | statusline |

---

## 1. UserPromptSubmit 链（用户每次提交触发）

```
[user prompt]
    │
    ▼
1. changelog_inject     stdin = 用户消息（纯文本）
   │  关键词命中 "pull|拉取|更新|同步" → 注入 CHANGELOG 末 20 行
   │  否则静默
   ▼
2. sync_inject          stdin = 通常不读
   │  扫 active task 目录的 .sync.jsonl
   │  有锁 / 30 分钟内事件 → 注入；否则静默
   ▼
3. route_check          stdin = 用户消息（纯文本）
   │  正则匹配低耦合 nudge（搜索/批改/日志/测试/文档）→ 注入提示
   │  同时写 ~/.claude/.current_turn.json 供 PostToolUse 关联
   ▼
4. retrieve_inject      stdin = JSON {prompt, session_id}
   │  调 harness_retrieve.retrieve() 出 Context Brief
   │  关闭：HARNESS_RETRIEVE_INJECT=0
   │  超时 1.0s → 静默
   ▼
[main model 收到全部注入内容 + 原 prompt]
```

### 失败降级（全部 fail-open）

| hook | 异常时行为 |
|---|---|
| changelog_inject | 静默退出 |
| sync_inject | 静默退出 |
| route_check | 静默退出，turn_id 仍写文件（best-effort）|
| retrieve_inject | 异常 / 超时 / 空结果 → 静默 |

**Note**：4 个 hook 之间无数据依赖。互相不可见对方输出。任何一个 crash 不影响其他 hook。

---

## 2. PreToolUse Write|Edit|MultiEdit 链（关键 BLOCK 链）

```
[Claude 准备写文件 path X]
    │
    ▼
1. memory_file_protector    检查 path X 是不是受保护的 global-memory 文件
   │  受保护 + 操作危险 → BLOCK
   │
   ▼
2. memory_lint_gate         若 path X ∈ global-memory/{feedback,knowledge,fixes,decisions}/
   │  必须有 frontmatter（trigger.keywords / tags / last_updated / status）
   │  缺字段 → BLOCK
   │
   ▼
3. doc_gate                 若 path X 在 active task 目录内
   │  任务 stage 要求的必读文档未读 → BLOCK（提示先读再写）
   │
   ▼
4. diff_backup              静默：把原文件备份到 diff_runs/
   │
   ▼
[工具执行写入]
```

### 顺序关键性

- **1 必须先**：保护文件不该被改的根本性拦截
- **2 紧跟**：记忆类文件的格式约束
- **3 第三**：任务流程纪律
- **4 必须最后**：写入前最后一刻才备份（前 3 个 block 时不浪费 IO）

---

## 3. PostToolUse Write|Edit 链

```
[工具写入完成]
    │
    ▼
audit_logger（matcher=*，所有工具都跑）→ 记 JSONL 日志
    │
    ▼
diff_show（仅 Write|Edit）→ 终端展示 diff
```

### 失败降级

- audit_logger 失败 → 静默；日志缺一条不影响主流程
- diff_show 失败 → 静默；用户错过 diff 但写入已成

---

## 4. statusLine（每帧终端刷新）

```
[CC 终端帧]
    │
    ▼
statusline.py    stdin = JSON {cwd, transcript_path, ...}
    │  读 ~/.claude/.current_task → 中文映射
    │  数 transcript 用户消息条数 → 40+ 黄 / 80+ 红
    │  失败 → 输出空 → 状态栏空白
    ▼
[终端显示]
```

**注**：每帧调一次，**必须** < 50ms。任何卡顿会冻 UI。

---

## 5. SubagentStart / Stop

| 事件 | hook | 用途 |
|---|---|---|
| SubagentStart | subagent_logger | 记 subagent 启动元数据（agent_type / prompt 摘要）|
| SubagentStop | subagent_stop_logger | 记结束 + 耗时 + 输出大小，供 route_audit.py 统计 |

失败：静默；审计数据缺失不影响主流程。

---

## 6. Stop（每次任务/turn 结束）

```
[Claude 准备 Stop]
    │
    ▼
post_task_hook.py --auto-fix
    │  若有未提交 CHANGELOG 改动 → 自动 append
    │  若 Stop 被 /goal session-scoped 条件挡 → 阻止 stop
    ▼
[Stop 实际执行 or 被阻]
```

---

## 加新 UserPromptSubmit hook 的规范

1. 写到 `harness/hooks/<name>.py`
2. 必须 `fail-open`：所有异常 silent return
3. stdout 任何输出都会注入主模型上下文 → 控制 token（≤ 200 token 推荐）
4. stdin 输入约定：
   - 大部分 hook 读纯文本（用户消息）
   - retrieve_inject 读 JSON `{prompt, session_id}` — 看 settings.json `inputType` 配置
5. 在 `harness/hook_manifest.json` 的 `UserPromptSubmit` 组添加注册条目，`path` 必须是 harness 内相对 `.py`，`failure_action` 必须是 `BLOCK|WARN|REPORT|NONE`
6. 决定插入顺序（默认追加末尾）
7. 更新本文档 § 1 表
8. 更新 `docs/scripts-registry.md` § 1
9. 运行 `python harness/scripts/check_hook_alignment.py --strict --json`

## 加新 PreToolUse BLOCK hook 的规范

1. 决定 matcher（Bash / Write|Edit / Read / Agent / ... ）
2. 决定在链中的位置（最早 = 最强阻断；最晚 = 最贴近工具）
3. stdout JSON `{"decision": "block", "reason": "..."}` 触发 BLOCK
4. 任何异常 = fail-open（不阻断），不要让 hook bug 卡死所有写入
5. 同步更新 `harness/hook_manifest.json`、本文档 § 2 和 scripts-registry；manifest 中的 `path` 必须是 harness 内相对 `.py`，`failure_action` 必须是 `BLOCK|WARN|REPORT|NONE`
6. 运行 `python harness/scripts/check_hook_alignment.py --strict --json`
