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
last_updated: 2026-05-20
---

---
name: skill 部署布局约定
description: 新建/修改 skill 时必须遵守"D: 真源 + C: junction"的部署约定，不能直接在 ~/.claude/skills/ 下建真目录
type: feedback
---

# Skill 部署布局约定

新建或修改 skill 时，**真源文件必须放在** `~/.claude/global-memory/skills/<name>/v1/`，`~/.claude/skills/<name>` 是 junction（mklink /J）指过去。

## Why
2026-04-28 建 `/learn` skill 时，直接在 `~/.claude/skills/learn/SKILL.md` 写了真目录 + 真文件。表面看 Claude Code 自动发现并注册了 skill，能用——但跑 `audit_skill.py` 时报 `missing-skill-md - SKILL.md not found: ~/.claude/global-memory\skills\learn\v1\SKILL.md`，因为脚本认 D: 路径。

根本原因：项目约定是**单一数据源**——所有 skill 真源在 D:，`~/.claude/skills/` 通过 symlink/junction 反射过去（`ls -la ~/.claude/skills/work` 显示 `lrwxrwxrwx ... -> /d/global-memory/skills/work/v1`）。这套布局让审计脚本、版本管理、跨机器同步都基于 D: 单点，C: 只是 Claude Code 扫描路径的兼容层。我把真文件放 C: → 破坏约定 → 审计找不到。

## How to apply

新建 skill：
```bash
# 1. D: 建真目录
mkdir -p "~/.claude/global-memory/skills/<name>/v1"
# 2. 写 SKILL.md 到 D:
Write ~/.claude/global-memory/skills/<name>/v1/SKILL.md
# 3. C: 建 junction（必须用 cmd.exe，Git Bash 的 ln -s 不行）
cmd.exe //c "mklink /J C:\Users\XINDONG\.claude\skills\<name> ~/.claude/global-memory\skills\<name>\v1"
# 4. 验证
ls -la ~/.claude/skills/<name>   # 应显示 lrwxrwxrwx ... -> /d/global-memory/skills/<name>/v1
python ~/.claude/scripts/audit_skill.py --skill <name>   # 应 PASS
```

修改已有 skill：直接编辑 `~/.claude/skills/<name>/SKILL.md`（junction 透传到 D:），不需要改部署。

## 自检触发词
准备 Write 到 `~/.claude/skills/<path>/SKILL.md` 时 → 先 `ls -la ~/.claude/skills/<path>` 确认是不是 junction → 是 junction 就直接编辑（透传） → 不是就按上面 4 步走。
