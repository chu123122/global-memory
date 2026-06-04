---
issue_id: rules-layer-minor-backlog
status: open
severity: minor
created: 2026-06-03
source: rules-predeploy-review workflow (落盘后 Minor 项汇总)
tags: [workflow, design]
---

# Rules 层落地 · Minor 待补 backlog

> 四层架构落盘后，体检（rules-predeploy-review）确认为真但非阻断的 Minor 细节。
> 落盘已放行（0 blocker）；这些是后续打磨项，逐条可独立补，不急。

## 待补清单

| # | 项 | 落点 | 说明 |
|---|----|------|------|
| 1 | TDD 写回格式未规格化 | `rules/执行层.md` | Red/Green 写回 Phase 卡的具体字段模板没定 |
| 2 | doc_gate 双层失败判据 | `rules/执行层.md` 强制点 | 主动/被动两道都失败时的兜底行为未写明 |
| 3 | 复盘触发阈值出处 | `skills/work/SKILL.md` / 执行层 | "≥5 Phase 或 ≥10 轮"阈值散落，宜下沉操作细则单一源 |
| 4 | S1/S2/S3 各层速查表 | `rules/*.md` 强制点 | 各层强制点强度可加统一速查 |
| 5 | 召回注入生命期 / MIN_QUERY_LEN 来源 | `rules/反馈层.md` | 阈值标注"来源=script 常量"指针 |
| 6 | 维护工作流 SOP | `rules/维护层.md` / MAINTENANCE.md | 巡检→提议→人裁→修复的标准动作顺序 |
| 7 | 沉淀层"记住这个"触发兜底 | `rules/沉淀层.md` | 无法归类时的兜底分类规则 |
| 8 | 维护层淘汰"人"的身份 | `rules/维护层.md` | 已改"用户/任务所有者确认"，可再明确权限边界 |

## matrix v3 smoke fixtures（5，已设计未实现 — 不塞 flaky）

两个故意没测的 hook，需测试隔离夹具。可直接执行方案：

- **doc_gate deny-path**：`doc_gate` 用 `Path.home()/.claude/projects/project_registry.json`。夹具 = subprocess 设 `env HOME / USERPROFILE = <tmp>`，在 `<tmp>/.claude/projects/project_registry.json` 造：`watched_paths` 含一个 tmp task 路径片段 + `active_tasks=[faketask]` + `task_paths` 映射 + faketask 目录**缺**必读文档 → stdin 指向该 task 内文件 → 期望 exit 2（deny）。先读 `harness/hooks/stage_lib.py` 的 `get_required_docs` 确认 registry schema。
- **post_task_hook**：`MEMORY_DIR = _lib.MEMORY_ROOT`（git ops `cwd=MEMORY_DIR`）。夹具 = 先确认 MEMORY_ROOT 是否 env 可覆盖；若否，需加 env 覆盖支持（小改）。再建 temp git repo（无 remote 防 push）指过去，跑 `--auto-fix` 期望不崩、不推。**绝不在真 repo 跑**。

价值最低（两 hook 生产每天跑），属回归补强，独立小任务做。

## reconcile MVP 首跑发现（2026-06-04，需确认后修）

- **`learning_opportunity_nudge` 是未纳管 hook**：在 settings.json 运行（PostToolUse Bash），但同时 ① 不在 `hook_manifest.json` ② capability_manifest unassigned ③ scripts-registry unregistered。manifest（声称源）与运行时不同步 = bootstrap-第二源问题实证。修 = 补进 manifest + 分配 capability + 登记 registry（触 hook 安装链，须确认再动）。
- 另 2 个既有 unassigned/unregistered：`readback_audit.py` / `scripts/task_experience_index.py`（pre-existing，与本次无关）。

## 落地期已记别处（非本 backlog）

- RECONCILE 标记 + `reconcile.py` 实现 → `docs/多数据源治理方案.md` §8 落地顺序（独立实现任务）。
- RULE-NNN↔R 全量合并 + smoke → RULE_ENFORCEMENT_MATRIX matrix v2。

## 已驳回（撞已锁决策，不补）

- PARAM_REGISTRY.md 集中参数 → 撞「参数下沉 script 旁」。
- Lane 矩阵展开进执行层 → 撞「路由删出 CLAUDE，归操作细则」。
- concurrent-access.md → 过度设计，`.session_tasks/` 已处理多终端。
