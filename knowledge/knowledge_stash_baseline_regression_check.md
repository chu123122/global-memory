---
description: git stash 基线对比 = 区分 pre-existing vs 自引入失败的唯一可靠法
priority: high
status: active
trigger:
  keywords:
    - concept:regression
    - concept:verification
    - tool:git
    - tool:harness
  tags:
    - workflow
    - tooling
---

# stash 基线对比：区分 pre-existing vs 自引入失败

大改动后跑校验出一堆 FAIL/ERROR/blocker，凭印象判不准哪些是自己引入、哪些本就存在 → 要么背锅 pre-existing，要么把自己的当 pre-existing 放过。

**法**：
```
git stash push -u            # 暂存全部改动(含 rename/delete)，回 HEAD 干净态
python <checker> --json      # 捕基线
git stash pop                # 恢复改动
python <checker> --json      # 捕当前，diff 两者
```
差集 = 自己引入（必修）；交集 = pre-existing（非本次，记 backlog 不背锅）。

**现场**（harness-3layer-architecture 2026-06-04）：doc reorg 后 oss=blocked。stash 对比确认 `catalog_freshness` 2→3 stale(+agents/README) + `docs_entrypoints` PASS→BLOCKER(CONTRIBUTING 缺 frontmatter) = 自引入；其余 7 blocker + verify_memory 全 pre-existing。修完再比：blocker 9→7 零新增 = 诚实交付的硬证据。

**注**：Windows 下临时脚本别写 `/tmp`（不存在，会在 stash 前崩）；`stash -u` 含未跟踪文件。配套：搬文件前先 [[fix_fresh_grep_before_file_ops]]。
