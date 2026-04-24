# SPEC · token-cost-governance

> 派生自: `需求分析.md` + `设计文档.md`
> Status: implementation
> 创建: 2026-04-24

## 1. 目标

把 `/work`、`/check`、`skill-auditor` 中的机械上下文搬运下沉到只读脚本,减少 AI 重复读取与人工扫描。

## 2. 范围

本轮实现:
- `harness/audit_skill.py`
- `harness/work_context_pack.py`
- `harness/check_prepare.py`
- `harness/maintenance_manifest.json` 增加 `token_savers`
- `skills/work/v1/SKILL.md`、`skills/check/v1/SKILL.md`、`skills/skill-auditor/v1/SKILL.md` 接入脚本优先流程
- `harness/harness_status.py` 改为默认不写 `STATUS_SNAPSHOT.md`,显式 `--write-snapshot` 才落盘

不做:
- 不新增 daemon / HTTP / MCP
- 不实现 `review_preflight.py` / `bug_pack.py` / `memory_add.py`
- 不自动修改任务文档、记忆文件或 git 提交

## 3. 验收清单

| ID | 验收项 | 命令 |
|---|---|---|
| V1 | 只读状态命令不默认写 snapshot | `python harness/harness_status.py --json` |
| V2 | Skill 审计脚本可跑全量 | `python harness/audit_skill.py --all --json` |
| V3 | `/work` 上下文 pack 可解析当前任务 | `python harness/work_context_pack.py --task token-cost-governance` |
| V4 | `/check` preflight 可解析当前任务 | `python harness/check_prepare.py --task token-cost-governance --json` |
| V5 | Skill 文档已接入 token saver | grep/Select-String 检查三个 SKILL.md |
| V6 | manifest 登记 token_savers | 读取 `harness/maintenance_manifest.json` |
| V7 | Python 脚本无硬编码绝对路径 | `python harness/fix_hardcoded_paths.py` 的 Python 脚本部分为通过 |
| V8 | 全局健康检查通过 | `python check_health.py` |

## 4. 文件影响

新增:
- `harness/audit_skill.py`
- `harness/work_context_pack.py`
- `harness/check_prepare.py`
- `projects/token-cost-governance/SPEC.md`
- `projects/token-cost-governance/HANDOFF.md`

修改:
- `harness/harness_status.py`
- `harness/maintenance_manifest.json`
- `harness/smoke_test_hooks.py`
- `harness/verify_doc_drift.py`
- `skills/work/v1/SKILL.md`
- `skills/check/v1/SKILL.md`
- `skills/skill-auditor/v1/SKILL.md`
- `projects/token-cost-governance/需求分析.md`
- `projects/token-cost-governance/设计文档.md`
- `CHANGELOG.md`

## 5. 进度

- 2026-04-24:进入 implementation,首批三个 token saver 已开始实现。
