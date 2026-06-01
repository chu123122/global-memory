---
description: harness/health/runner.py 含相对导入，必须 python -m 启动，直跑 ImportError
priority: medium
status: active
trigger:
  keywords:
    - error:ImportError
    - concept:relative-import
    - tool:python
  tags:
    - python
    - tooling
  stages:
    - debug
last_updated: 2026-05-22
---

# health/runner.py 必须 python -m 启动

## 现象

```
$ python ~/.claude/global-memory/harness/health/runner.py
ImportError: attempted relative import with no known parent package
```

## 根因

`runner.py:17` 用 `from .registry import` 相对导入，要求以包模式启动。
直跑（`python runner.py`）时 Python 不认 `__package__`，相对导入失败。

## 修复

```bash
cd ~/.claude/global-memory
python -m harness.health.runner [--check <id>] [--json] [--no-log]
```

或注册到 PATH 时确保 cwd 在 global-memory 下。

## 验证

P3 实测 `cd ~/.claude/global-memory && python -m harness.health.runner --no-log`
跑出 10 个 check 输出（含新增 retrieve_pointer_consumption / lint_failure_rate）。
