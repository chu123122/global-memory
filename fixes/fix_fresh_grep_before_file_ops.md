---
description: 搬/删/改名文件前必 fresh grep 全仓；workflow/agent 盘点对机器引用系统性漏报
priority: high
status: active
trigger:
  keywords:
    - concept:refactor
    - concept:file-move
    - tool:grep
    - tool:harness
  tags:
    - tooling
    - workflow
---

# 搬/删/改名文件前必 fresh grep 全仓

**坑**：sandboxed workflow / subagent 产出的「断链地图 / 影响盘点」对**机器引用**（`.py` 硬编码路径、`.json` manifest、checker 的 `REPO_DIR / "x"` 拼接）**系统性漏报**——它们靠语义推断而非全仓扫描。当成完备清单 → 漏改 → harness 静默断（fail-open hook 不报错）。

**现场**（harness-3layer-architecture 文档重组 2026-06-04）：
- `doc-reorg` workflow 称 `check_health.py`「10 refs / safe_to_delete」；fresh grep 实抓出 `oss_readiness_check.py:1238` 的 `check_health()` + `verify_output_contracts.py:111`（默认契约用例）+ `smoke_test.py:95` + `maintain.py` ×6 flag。
- `MEMORY.md` 搬迁地图只报 doc_sidebar；grep 出 `memory_usage.py:12`(`parents[3]/"MEMORY.md"`) + `maintain.py:226`(HARNESS_AUTO_FILES) + init/close_project 深度硬编码 → 结论翻转为「不搬，留根」。
- `note.py:13`（写 notes.md）、`ai_runner.py:111`、`docs/` 下 8 个 checker（`check_capability_manifest.py:31` 等）全漏。

**规矩**：每批 `git mv / rm / rename` 前，对每个受影响文件名 `grep -rn "<name>" --include=*.py --include=*.json --include=*.md` 全仓，逐条核机器引用。workflow 盘点当线索，不当清单。改完用 [[knowledge_stash_baseline_regression_check]] 验零新增失败。
