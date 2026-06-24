---
description: Skill 部署布局约定
priority: medium
status: active
trigger:
  keywords:
    - []
  tags:
    - skill
    - infra
    - memory
  stages:
    - implementation
last_updated: 2026-06-16
---

---
name: skill 部署布局约定
description: 新建/修改 skill 时必须遵守 global-memory 真源 + runtime junction/sync 的部署约定，不能直接在 runtime skills 目录下建真目录
type: feedback
---

# Skill 部署布局约定

新建或修改 skill 时，**真源文件必须放在** `~/.claude/global-memory/skills/<name>/`，`~/.claude/skills/<name>` 是 junction（mklink /J）指过去。

## Why
2026-04-28 建 `/learn` skill 时，直接在 `~/.claude/skills/learn/SKILL.md` 写了真目录 + 真文件。表面看 Claude Code 自动发现并注册了 skill，能用——但跑 `audit_skill.py` 时报 `missing-skill-md - SKILL.md not found: ~/.claude/global-memory\skills\learn\v1\SKILL.md`，因为脚本认 D: 路径。

根本原因：项目约定是**单一数据源**——skill 真源在 `~/.claude/global-memory/skills/<name>/`（当前机器上是该路径到仓库的 junction），Claude / Codex runtime skills 目录只是发现入口或生成物。审计脚本、版本管理、跨机器同步都基于 global-memory 真源；把真文件直接放 runtime 目录会破坏约定，导致审计和同步链找不到。

## How to apply

新建 skill：
```powershell
# 1. 在 global-memory 真源建目录
New-Item -ItemType Directory -Force ~/.claude/global-memory/skills/<name>
# 2. 写 SKILL.md 到真源
# ~/.claude/global-memory/skills/<name>/SKILL.md
# 3. 运行 bootstrap 同步 / junction 检查
python ~/.claude/global-memory/bootstrap.py install
python ~/.claude/global-memory/bootstrap.py check
```

修改已有 skill：优先编辑 `~/.claude/global-memory/skills/<name>/SKILL.md` 真源；若 runtime 目录确认是 junction/同步生成物，也可通过 runtime 路径编辑但必须确认会透传到真源。

## 自检触发词
准备 Write 到 runtime skills 路径时 → 先确认它是 junction/同步生成物且能回到 global-memory 真源；不确定时只写 `~/.claude/global-memory/skills/<name>/SKILL.md`，再跑 `bootstrap.py check`。

## 2026-06-16 triage 更新记录

本条保持 active，但已把旧 “D: 真源 + C: junction” 表述更新为当前可移植说法：`~/.claude/global-memory` 真源 + runtime junction/sync。

验证命令：

```powershell
python bootstrap.py check
python harness/scripts/triage_inbox.py --json
```
