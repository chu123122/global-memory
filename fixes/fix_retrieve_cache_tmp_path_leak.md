---
description: harness_retrieve cache 全局共享导致 tmp-path 残留泄漏到生产 dry-run
priority: high
status: active
trigger:
  keywords:
    - concept:cache
    - tool:retrieve
    - error:tmp-path-leak
  tags:
    - tooling
    - infra
    - memory
  stages:
    - debug
last_updated: 2026-05-20
---

# harness_retrieve cache tmp-path 泄漏

## 现象
生产 dry-run `--query "diff vscode"` 返回的 `relevant_pointers[].path` 指向 `C:/Users/.../Temp/l4e_staged_*/...`，tmp 目录已被 L4-E 测试删除，路径全部失效。

## 根因
- `~/.claude/cache/triggers.json` 单文件全局共享，未按 `memory_root` 隔离
- L4-E 仿真测试用 tmp memory_root 跑过 → 把 tmp 路径写进了共享 cache
- mtime 失效检查在源 dir 不存在时 silent fail，旧 cache 数据原样回灌

## 修复
- `_cache_path_for(memory_root)` 用 md5 hash 把 cache 按 memory_root 分桶 → `triggers_<hash>.json`
- `load_trigger_cache` 加 sanity check：entry path 不在 memory_root 下 → 强制重扫
- CLI `--cache` 默认改 None，由 `--memory-root` 派生

## 验证
- 删 stale `~/.claude/cache/triggers.json`
- 跑 `python harness_retrieve.py --query "diff vscode" --memory-root ~/.claude/global-memory --dry-run` → paths 全部 D:/ 开头 ✅
- 回归 65/65 PASS in 1.56s
