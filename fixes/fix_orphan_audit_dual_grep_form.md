---
description: 审计可删文件时只 grep 路径限定形式会漏按文件名的引用，导致误删活文件
priority: high
status: active
trigger:
  keywords:
    - concept:workflow
    - tool:harness
  tags:
    - workflow
    - tooling
  stages:
    - debug
last_updated: 2026-06-04
---

# 孤立文件审计：引用检查必须同时 grep 路径限定形式和按文件名形式

## 现象

清理 global-memory 时，首轮用 `grep "templates/WORKFLOW.md"`（路径限定）判定 `templates/SPEC.md`/`WORKFLOW.md` 为"0 外部引用"的孤立文件，据此删除。回查才发现 `verify_all.check_templates()`、`workflow.json`、`test_stage_lib.py` 等是按 **basename**（`"WORKFLOW.md"`/`"SPEC.md"`）引用的，第一轮全漏掉，差点删掉活校验子系统依赖的文件。

## 根因

harness 里的引用有多种书写形式：路径限定（`templates/x.md`）、纯 basename（`"x.md"` 出现在 Python list/dict/JSON）、`TEMPLATES_DIR / "x.md"` 拼接。只 grep 一种形式 = 系统性漏判。memory 类文件（feedback/fixes/knowledge/decisions）更是按语义召回、根本不靠路径引用。

## 修复

审计某文件是否可删，引用检查至少覆盖三层：
1. 路径限定：`grep -rn "dir/name.ext"`
2. 纯 basename：`grep -rn '"name.ext"'`（抓 list/JSON/拼接）
3. 存在性检查：`grep -rn "name.ext" --include=*.py` 看有没有 `.is_file()/.exists()/required=[...]`
删前先回到"已知安全态"能力（git tracked → `git checkout HEAD -- <file>` 秒级回滚），把删除当可逆操作做。

## 验证

删除/退役后跑 `verify_all.py` + `smoke_test.py` + `scan_orphan_scripts.py --strict`，确认 0 ERROR/0 FAIL 且目标文件不出现在 orphan/dead-ref/missing-script 列表；再 `grep` 全仓确认无残留活引用（仅剩 CHANGELOG 历史 + 合法 basename 噪声过滤器）。
