---
description: Diff 工作流（B 协议）+ 全局白名单 hook
priority: medium
status: superseded
trigger:
  keywords:
    - tool:diff
    - concept:git
    - concept:vscode
    - concept:cherry-pick
  tags:
    - workflow
    - ue
  stages:
    - debug
    - implementation
last_updated: 2026-06-16
---

---
name: feedback-diff-workflow
description: Diff 工作流偏好：Edit/Write 后由全局 hook 备份并弹出 VS Code diff 视图
type: feedback
created: 2026-04-21
updated: 2026-04-24
source: 全局 diff hook 工作流
access_count: 0
---

# Diff 工作流（B 协议）+ 全局白名单 hook

> type: feedback
> 描述: Edit/Write 后自动弹 VS Code diff 视图的 hook 配置 + 白名单目录范围 + 扩展/禁用方法

## 核心规则

用户编辑长期文档（DESIGN/HANDOFF/源码等）时，**每次 Edit/Write 完成后会有 VS Code 自动弹 diff 三栏对比视图**。这是已配置的全局 hook 自动行为，AI 不需要主动操作。

**Why**：用户反馈 — 之前 AI 改完文件后只在 chat 里贴 "diff 表"（描述性总结），用户扫一眼就过了，等于没审查、把控感差。改用 VS Code diff 视图强制可视化对比，每次改动都能真实过眼。

**How to apply**：
- 编辑白名单目录下的文件 → 自动备份 + 弹窗，AI 无需主动调用
- 编辑非白名单目录（如 `~/.claude/`、其他项目）→ 不触发，无感
- AI **不要**在 chat 里再额外贴 "diff 描述表"，会跟弹窗重复
- 5 秒内连续编辑同文件只弹一次（debounce），所以 AI 可放心连续 Edit

## 白名单目录（仅这些目录会备份 + 弹 diff）

定义在两个 hook 脚本顶部 `WHITELIST` 常量（**两个文件必须同步修改**）：

```python
WHITELIST = [
    r"D:\ClaudeTasks\active",                                                          # 所有任务文档
    r"C:\Perforce\tl_gaoxinag_01\frontend\trunk\Editor\UE_game\Plugins\XDAdaptivePerformance",  # XD 插件源码
]
```

**扩白名单步骤**：
1. 改 `~/.claude/scripts/hooks/diff_backup.py` 顶部 WHITELIST 加路径前缀
2. 改 `~/.claude/scripts/hooks/diff_show.py` 顶部 WHITELIST 加同样路径
3. 不需要重启 Claude Code（hook 在每次工具调用时重新加载脚本）

**禁用整套**：注释 `~/.claude/settings.json` 里以下两条：
- PreToolUse(Write|Edit) 数组里的 `diff_backup.py` 条目
- PostToolUse(Write|Edit) 整个条目（含 `diff_show.py`）

## 配置文件路径

| 文件 | 作用 |
|---|---|
| `~/.claude/settings.json` | hook 注册（PreToolUse + PostToolUse 各加 Write\|Edit matcher 一条）|
| `~/.claude/scripts/hooks/diff_backup.py` | 编辑前备份（PreToolUse） |
| `~/.claude/scripts/hooks/diff_show.py` | 编辑后弹 diff（PostToolUse） |
| `D:\ClaudeTasks\.diff_backup\` | 备份目录（覆盖式，只保留每文件最近一次） |
| `D:\ClaudeTasks\.diff_backup\_lastshow.json` | debounce 状态（最近一次弹窗时间戳，5s 内同文件不重弹） |

## 实现细节

- 备份命名：`<文件名>.<sha1[:8]>.bak`（例：`DESIGN.md.a3b2c1d4.bak`），路径 hash 避免不同目录同名冲突
- 异步弹窗：`subprocess.Popen('start "" code --diff <bak> <file>', shell=True)` — 不阻塞 hook 退出
- 新建文件：无原内容可备份 → 跳过（弹空 diff 无意义）
- 失败容错：备份/弹窗失败不阻塞编辑（hook 始终 allow）

## 未来 AI 看到这些现象不要困惑

- 编辑白名单目录文件时 VS Code 自动弹三栏窗口 → 是 hook 设计，不是 bug
- `D:\ClaudeTasks\.diff_backup\` 下一堆 `.bak` 文件 → 是 hash 命名的备份，占用很小，不需要清理
- 用户在 chat 提到 "B 协议" / "diff 一下" → 指这个工作流
- `_lastshow.json` 是 debounce 状态文件，可以安全删除（删了下次自动重建）

## 历史

- 2026-04-21 配置完成
- 触发场景：XDAdaptivePerformance 重构期，用户反馈 AI 描述式 diff 总结不可控
- 方案演进：A（高敏感段用户自己 paste）→ B（VS Code 弹 diff）→ 最终选 B + 全自动化 hook，零额外 token 消耗

## 2026-06-16 triage 关闭记录

关闭原因：本条描述的是旧的“Edit/Write 后自动弹 VS Code diff”hook 工作流；该默认自动弹窗已在 2026-06-15 关闭，当前保留的是手动 `/diff` / 显式 review 路径。继续把旧自动 hook 规则标 active 会误导后续 agent 以为弹窗仍是默认行为。

验证命令：

```powershell
python bootstrap.py check
python harness/scripts/triage_inbox.py --verify-close feedback/feedback_diff_workflow.md --json
```

superseded reason：旧自动弹窗 diff hook 已被禁用；后续 diff 需求走显式工具/人工确认，不再作为默认行为规则。
