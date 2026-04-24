---
name: diff
description: "Interactive picker for pending edits. Lists files in <task>/.diff/now/ as numbered options, waits for user selection (e.g. '1,3' or '1-3' or 'all' or 'skip'), then opens each picked file via Code.exe --diff and archives it to history/<ts>/. Invoke as '/diff' (all active tasks), '/diff <task>' (single task), or '/diff all'. Use when the user wants to visually review accumulated edits."
---

# /diff — 改动 diff 查看入口（交互式）

> 固定流程：列表 → 等用户选 → 循环 `--open` → 摘要

## 何时使用

- 改完一批文件后，想挑选性 visually review 部分改动
- 用户输入 `/diff`、`/diff <task>` 或 `/diff all`
- **不适用**：单文件即时 diff（直接 `git diff` / `p4 diff` 更轻）

## 输入解析

| 参数形式（`args`）| 行为 |
|---|---|
| 空 / `all` | 列出所有 `active_tasks` 的累积 pending diff |
| `<task>` | 单个 task，支持前缀模糊匹配（`xd` → `xd-adaptive-performance-refactor`） |

**不支持** `/diff <t1> <t2>` 多 task 入口（KISS：分多次调用）。

## 执行流程

### Step 1 — 列出待 diff 文件（不开 GUI）

Bash 直接调脚本的 `--list` 子命令：

```bash
python ~/.claude/scripts/show_diffs.py --list [<task>]
```

脚本输出形如：

```json
{"items":[{"idx":1,"task":"xd-adaptive-performance-refactor","bak":"foo.cpp.abc12345.bak","orig":"C:/Perforce/.../foo.cpp"}]}
```

**空清单 (`items=[]`)** → 输出"📭 无 pending diffs"，结束流程，**不**等用户输入。

### Step 2 — 渲染清单 + 提示用户

把 JSON 解析成人类可读编号清单（带 task 标签和文件名 basename）：

```text
待选 diff（共 N 项）：

  1. [xd-adaptive] foo.cpp
  2. [xd-adaptive] bar.h
  3. [android-apk-build] AndroidManifest.xml

回复编号选择要弹 VS Code 的文件：
  - 单选：1
  - 多选：1,3
  - 区间：1-3
  - 全开：all
  - 跳过：skip / q
```

**注意**：渲染时只展示 `basename(orig)`，不要把完整路径打到屏幕（噪音大）。如用户问起再展示完整路径。

### Step 3 — 解析用户选择

用户回复后，按以下规则解析：

- `skip` / `q` / 空 → 不开任何文件，输出"⏭️ 跳过，`now/` 不动"，结束
- `all` → 选中所有 `idx`
- `1,3` → 选 idx 1 和 3
- `1-3` → 选 idx 1、2、3
- `1,3-5,7` → 混合：1、3、4、5、7
- 去重 + 升序
- **非法编号**（超出范围、非数字）→ 报"⚠️ 跳过非法编号 X"，对其他合法编号继续

### Step 4 — 生成 ts 后循环 `--open`

在 SKILL 层一次性生成时间戳（保证同一次 /diff 内多文件共享同一 history 子目录）：

```bash
TS=$(date +%Y%m%d-%H%M%S)
```

对每个选中的 idx，按 (task, bak) 调脚本：

```bash
python ~/.claude/scripts/show_diffs.py --open <task> <bak_name> $TS
```

**可以一次 Bash 调用里串多条**（每对 `--open` 独立无状态）：

```bash
TS=$(date +%Y%m%d-%H%M%S)
python ~/.claude/scripts/show_diffs.py --open xd-adaptive foo.cpp.abc12345.bak $TS
python ~/.claude/scripts/show_diffs.py --open xd-adaptive bar.h.def67890.bak $TS
```

### Step 5 — 摘要输出

```text
✅ 打开 N 个 diff，归档到 <task>/.diff/history/<ts>/
保留 M 个未选中的 bak 在 now/（下次 /diff 仍可见）
```

如果某个 `--open` 退出码 != 0 → 把 stderr 透传给用户，归档计数减 1。

## 选择语法（合法形式速查）

| 输入 | 含义 |
|---|---|
| `1` | 单选 idx 1 |
| `1,3,5` | 多选 |
| `1-3` | 区间（含两端） |
| `1,3-5,7` | 混合 |
| `all` | 全选 |
| `skip` / `q` / 空 | 全跳过 |

## 与 diff_backup hook 的协同

- `~/.claude/settings.json` 中 PreToolUse `Write|Edit` 挂 `diff_backup.py`
- 备份在每次 Edit 前自动写入归属 task 的 `<task>/.diff/now/`
- `/diff` 是配套的"显示 + 文件级归档"端
- 是否自动弹即时 diff 由 `~/.claude/settings.json` 的 PostToolUse `diff_show.py` 决定

## 错误处理

- `--list` 退出码 != 0 → 把 stderr 透传给用户作为摘要，结束
- 常见错误：
  1. `Code.exe not found`（仅 `--open` 触发） — VS Code 的 `code` 不在 PATH，归档不会发生
  2. `failed to load project_registry.json` — registry 缺失/损坏
  3. `ambiguous task prefix` — 前缀同时匹配多个 task → 让用户用更长前缀重试
  4. `no task matched` — 前缀不匹配任何 active_task → 列出全集供用户挑

## 不做的事

- 不在 skill 内开 VS Code（统一由脚本做，DETACHED_PROCESS 防 cmd 残留）
- 不动备份语义（同一 /diff 周期内同文件多次 Edit 只保留首次原始版本）
- 不修改 settings.json / hook 配置
- 不清理 `history/`（永久保留，用户手动释放空间）
- 不展示完整路径除非用户明确要求（清单只显示 `basename(orig)` 减少噪音）

## 铁律

- skill 负责"列表渲染 + 选择解析 + 循环编排"，脚本只做无状态原语
- 不绕过 `_task_resolver.py` 自己解析 task 归属（单一权威）
- ts 必须在 SKILL 层一次性生成，多次 `--open` 共享，**不**让脚本自己取 `datetime.now()`（避免不同 `--open` 调用拿到不同 ts，归档分散到多个 history 子目录）
