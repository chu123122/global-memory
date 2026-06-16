---
doc_type: harness-issue
id: ISSUE-2026-06-03-registry-single-source-autoindex
status: routed
opened: 2026-06-03
severity: high
layer: 维护层 → 沉淀层索引
source: harness-3layer-architecture P1 清理实操暴露
---

# 脚本登记应单一全局索引 + 自动注册，不应 5 处手维护

## 现象（触发场景）

P1 删 4 个 retrieve 诊断脚本时，为防巡检变红，必须**手动**同步清 5 处登记：

1. `harness/capability_manifest.json`（4 条）
2. `docs/scripts-registry.md`（4 行）
3. `docs/capability-map-and-oss-gap.md`（4 行）
4. `harness/README.md`（4 行 + 计数）
5. `docs/meta-evidence-pipeline.md`（4 行）

删 1 个脚本 → 改 5 个文件。增 1 个脚本同理。漏一处 → 巡检红。

## 根因

脚本「存在性」的真相源在**磁盘**，但被**复制成 5 份手维护副本**。每份都会和磁盘漂移。
现状只有**检测器**（`scan_orphan_scripts.py` / `check_capability_manifest.py`）报漂移，**没有自动消除漂移的机制**——它们指出红，但回填仍靠人手。

基线本身已红（3 个 unregistered：learning_opportunity_nudge / readback_audit / task_experience_index + README 计数 140≠143），正是这套手维护必然漂移的证据。

## 应改（方向，非定方案）

**单一全局索引 + 脚本自动注册/回填**：

- 真相源唯一 = 磁盘扫描结果（或一份机器生成的 index）。
- 其余 4 处人类文档表格**从 index 自动派生**（generate 而非 hand-edit），删/增脚本只动磁盘 + 跑一条 register 命令。
- `scan_orphan_scripts` / `check_capability_manifest` 从「只检测」升级为「检测 + `--fix` 自动回填/摘除登记」。
- 脚本新增时自带元数据（docstring 头或同名 sidecar），register 命令读它自动塞进 index + 派生文档。

## 上下文 / 关联

- 对应缺口：`harness-3layer-architecture` 落地映射缺口#3「反馈型 issue 文件夹」——本文件即该文件夹首条。
- 牵动组件：`scan_orphan_scripts.py`、`check_capability_manifest.py`、`update_readme`（若存在）、`scripts-registry.md`、`capability_manifest.json`、`capability-map-and-oss-gap.md`、`meta-evidence-pipeline.md`。
- 落点层：检测/回填脚本属**维护层**（但带 `--fix` 即越只读边界——需与「维护层只读」规格一起裁决，见缺口#5 各层规格）；index 数据本身属**沉淀层索引**。

## 流程归属

反馈型 issue → 人工门评审 → PR → merge 改 harness → 关闭（不进召回）。
当前 P1 仍按旧法手清 5 处（auto-index 未建），本 issue 记录该手工步骤应被消灭。

## 2026-06-15 partial fix 进展

- 已实现 MVP：新增 `harness/scripts/register_script.py`，提供默认 dry-run、`--apply` 写回的确定性注册入口。
- 覆盖范围：新增/已存在脚本的一次命令双登记，写入 `docs/scripts-registry.md` 的 Manual 治理脚本表与 `harness/capability_manifest.json` 指定 capability 的 `scripts[]`。
- 已用该命令注册自身到 `release_readiness` capability；选择理由是该工具服务 release/profile 检查中的脚本 registry/capability drift 消除。
- 未覆盖：完整 single-source SoT、README / capability-map / meta-evidence 派生更新、删除脚本或 stale 自动摘除。因此本 issue 保持 `status: open`，后续 full SoT 工作继续在本 issue 下追踪。

## 2026-06-16 triage 路由记录

关闭原因：本 issue 的直接 drift 已通过 `register_script.py` partial fix 与 2026-06-16 registry/capability 清理解决；剩余是 full single-source SoT 设计，不适合继续作为 open inbox 阻塞项。

后续 target：如要继续做完整 SoT，另开正式 `/work` 任务 `registry-single-source-autoindex-full-sot`，范围限定为 README / capability-map / meta-evidence 派生更新、删除脚本 stale 自动摘除、真正 single-source index 设计。

验证命令：

```powershell
python harness/scripts/scan_orphan_scripts.py --strict --json
python harness/scripts/check_capability_manifest.py --json
python harness/scripts/triage_inbox.py --verify-close issues/ISSUE-2026-06-03-registry-single-source-autoindex.md --json
```

reason：已路由到后续正式 work；当前 inbox 不再保持 open。
