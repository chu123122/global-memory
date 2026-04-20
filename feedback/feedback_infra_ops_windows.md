---
name: Windows 基础设施操作铁律
description: junction 创建方式 + 删 hook 引用目录的原子化要求（避免自锁）
type: feedback
---

# Windows 基础设施操作铁律

## 规则 1：建 directory junction 用 PowerShell，不用 git bash 调 mklink

**Why**：从 git bash 跑 `cmd //c mklink /J "path1" "path2"` 实测报"无效语法 - "path"。"，原因是引号 + 反斜杠 + cmd 解析的多层转义不可靠。直接 PowerShell 调用稳定。

**How to apply**：任何需要建 directory junction 的场景，统一用：

```bash
powershell -NoProfile -Command "New-Item -ItemType Junction -Path 'C:\target\link' -Target 'C:\source\real'"
```

验证：`Get-Item ... | Select FullName, LinkType, Target`

不要再花时间调试 `cmd //c mklink`。

---

## 规则 2：删除 hook 引用的目录前，必须做成"删 + 重建"原子单条命令

**Why**：2026-04-20 批次 3 翻车——按"先删 A → 单独建 junction A→B"两步走，删完 A 后 PreToolUse/PostToolUse hook 路径全部断裂（hook 脚本在被删的目录内），导致 AI 自身**所有工具被 PreToolUse 阻塞**，连 mklink 都跑不了；只能让用户手动改 settings.json 把 hook 路径切到新位置后才解锁。代价：~30 分钟死锁、用户介入。

**How to apply**：未来涉及替换 `~/.claude/scripts/`、`~/.claude/hooks/` 或任何 settings.json 引用的目录时：

1. **优先方案**：先把替换目标准备好（cp 文件、建好 B 的等价副本），再用单条 bash 命令做 `rm -rf A && powershell ... New-Item -ItemType Junction -Path A -Target B`，**绝不分两步**
2. **更稳方案**：先 Edit settings.json 把 hook 路径改到新位置（B 的真实路径），再 rm A、再建 junction（此时 hook 已不依赖 A）
3. **预检清单**：`grep -rn "<目标目录>" ~/.claude/settings*.json ~/.claude/hooks/` 确认所有引用方都能容忍短暂中断或都已切换

类比：拆桥前先架好替代桥，不要拆完才发现自己也站桥上。

---

## 规则 3：用 marker 包裹自动维护区时，所有改写该区附近的脚本必须感知 marker

**Why**：2026-04-20 sync_index 改 marker 模式后，姊妹脚本 `update_stats.py` 的正则 `## 记忆统计\n.*?(?=\n## |\Z)` 仍按"到下一个 H2 或 EOF"匹配，会**连同 `<!-- AUTO-INDEX:END -->` 一起吃掉**。下一次 sync_index 发现 BEGIN 但缺 END → 走 legacy-migrate → 在 `before` 中保留旧 BEGIN + 又插入新 BEGIN → 每次 Stop hook 累积一个 BEGIN，7 次后才被发现。

**How to apply**：
1. 加 marker 时同步排查所有改写该文件相同区域的脚本（grep 文件名）
2. 让任何"按 H2/EOF 边界匹配"的正则也把 `<!-- ... -->` 注释当作边界
3. 在 marker-based 脚本的 fallback 路径里**主动 strip 孤儿 marker**作为防御（即使别处没维护好，自己也能自愈，不会无限累积）

通用启示：**单一脚本的"自我幂等"不够，整个工具链必须 marker-aware**。

## 更新日志
- 2026-04-20：初次创建（claude-system-cleanup 批次 3 翻车 + sync_index marker 累积 bug 二连击）
