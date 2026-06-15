---
packet_id: 20260615-193511-script-registry-single-source-autoindex
author: codex
created: 2026-06-15T19:35:11
risk_tier: 2
status: submitted
---

# Change Packet: Script registry single source autoindex

## Motivation (WHY)

- 解决新增/删除 harness 脚本时需要手动同步 registry 与 capability 等多处登记的问题。
- 不修则新增脚本继续容易出现 unregistered/unassigned drift，后续靠人工补漏。

## Scope (WHAT)

Files to modify:
- `harness/scripts/register_script.py`（拟新增）
- `harness/tests/test_register_script.py`（拟新增）
- `docs/scripts-registry.md`
- `harness/capability_manifest.json`
- `issues/ISSUE-2026-06-03-registry-single-source-autoindex.md`
- `CHANGELOG.md`
- `D:/ClaudeTasks/active/script-registry-autoindex/*`

Files NOT touched:
- hooks / retrieve / statusline
- `agents/CLAUDE.md`
- 删除脚本自动化或 stale 自动摘除
- 全量 README / capability-map / meta-evidence 生成链重构

New files to create:
- `harness/scripts/register_script.py`
- `harness/tests/test_register_script.py`

## Approach (HOW)

- 新增 deterministic register CLI：默认 dry-run，`--apply` 才写。
- CLI 校验脚本路径、capability id、触发方和失败动作后，一次性更新 `docs/scripts-registry.md` 与 `harness/capability_manifest.json`。
- 重复执行保持幂等；错误输入 fail loud 且不写文件。

## Evidence & Verification

- Pre-implementation: issue 原文记录新增/删除脚本需手改多处；现有 `scan_orphan_scripts.py` 与 `check_capability_manifest.py` 只能报 drift，不能自动回填。
- Red: `pytest harness/tests/test_register_script.py -q` 在 `register_script.py` 不存在时 5 failed，失败点均为 `FileNotFoundError`。
- Green: `pytest harness/tests/test_register_script.py -q` → 5 passed；覆盖 dry-run/apply/幂等/错误路径与 fixture checker。
- CLI: `python harness/scripts/register_script.py --help` → PASS；对自身重复 `--apply --json` 返回 `would_change=false`，证明幂等。
- Existing checker reality: fixture 中 monkeypatch 现有 checker 可验证无 unregistered/unassigned；实际仓库级 `scan_orphan_scripts.py --strict --json` 与 `check_capability_manifest.py --json` 仍因历史 drift 失败（`readback_audit.py` / `check_phase_evidence.py` / `task_experience_index.py` / `change_packet.py` / README 计数），本轮未越界修复。
- Post-implementation: 限定 quality gate 通过。

## Risks & Rollback

- 风险：Markdown 表格改写脆弱；缓解：只更新固定工具表，找不到 anchor 就 fail loud。
- 风险：MVP 不是完整单一 SoT；缓解：本轮只承诺消灭新增脚本 registry + capability 双写，issue 可按 partial 关闭或保留后续。
- 回滚：删除新增脚本/测试，撤回 registry/capability/CHANGELOG/issue 改动。

## Intent Alignment

- Parent task: script-registry-autoindex
- Yes. 该改动直接服务 `/triage` 选择的 A：减少脚本登记手工多处同步与 drift。
