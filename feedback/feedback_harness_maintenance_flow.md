---
description: 新加 harness 脚本必走 5 步入维护流程，否则没人知道脚本存在
priority: high
status: active
trigger:
  keywords:
    - tool:harness
    - concept:maintenance
    - tool:manifest
    - cmd:doctor
  tags:
    - tooling
    - workflow
    - skill
  stages:
    - implementation
    - delivery
last_updated: 2026-05-20
---

# Harness 脚本维护流程（写新脚本必走）

## 规则

新加任何 `~/.claude/global-memory/harness/` 下脚本（scripts/ verify/ health/ hooks/）→ 必走 5 步入流程，否则脚本写完没人发现、没人跑、没人维护。

## Why

2026-05-20 harness-context-governance 任务中，AI 准备加 `analyze_retrieve_log.py` 时不知道现成的反遗忘机制（README 自动生成 / maintain.py 统一入口 / manifest 注册表 / health/ 周期检查），被用户追问后才派 subagent 搜出来。流程成熟但**没 surface 到任何启动上下文**，每个新会话 AI 都要重发现，浪费 token + 容易遗漏注册导致脚本变孤儿。

## How to apply

**新脚本完工后 5 步**：

1. **docstring 第一行格式**：`脚本名 — 一句话用途`（`generate_catalog.py` 抓这行入 README 表）
2. **注册** `~/.claude/global-memory/harness/maintenance_manifest.json` 对应 category：
   - `read_only` / `safe_fix` / `token_savers` / `legacy_deep_checks` / `side_effects` / `panel_event`
3. **重跑** `python ~/.claude/global-memory/harness/generate_catalog.py` → README.md 自动更新（不要手改 README）
4. **周期检查**放 `~/.claude/global-memory/harness/health/<name>.py` → 自动入 `invocation_freq` / `knowledge_unread` 类面板
5. **CHANGELOG.md** 记一条（feedback 强约束，同 XDAdaptivePerformance 规则）

**验证脚本入流程**：
```bash
python ~/.claude/global-memory/harness/maintain.py doctor
python ~/.claude/global-memory/harness/generate_catalog.py
```

**关键入口文件**（脑里记住）：
- `~/.claude/global-memory/harness/README.md` — 自动生成索引（scripts/hooks/verify/health 四块）
- `~/.claude/global-memory/harness/maintain.py` — 统一控制面（doctor/fix/sync/report/token_savers）
- `~/.claude/global-memory/harness/maintenance_manifest.json` — 脚本注册表
- `~/.claude/global-memory/harness/generate_catalog.py` — 重生成 README
- `~/.claude/global-memory/harness/health/` — 周期面板检查脚本目录

**触发**：用户说"加 harness 脚本"/"新加 verify"/"加 health 检查"/"hook 一个 jsonl 日志分析器" → 必读本条。
