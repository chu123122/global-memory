---
description: harness health check 新增 3 步：写 check 文件 + runner imports + 跑通验证
priority: medium
status: active
trigger:
  keywords:
    - concept:health
    - concept:checker
    - tool:harness
  tags:
    - tooling
    - workflow
  stages:
    - implementation
last_updated: 2026-05-22
---

# Health Check 新增完整 3 步

## 核心要点

1. **写 check 文件** `harness/health/checks/<name>.py`：
   ```python
   from ..registry import Signal, register

   @register("<check_id>")
   def check() -> list[Signal]:
       return [Signal(check_id="<check_id>", status="ok", headline="...")]
   ```

2. **注册到 runner** `harness/health/runner.py:18-29` imports 列表加 `<name>`：
   ```python
   from .checks import (  # noqa: F401  触发注册
       ...
       <name>,
   )
   ```

3. **验证**：`cd ~/.claude/global-memory && python -m harness.health.runner --no-log`
   - check_id 出现在输出
   - status 不是 critical 检测器异常

## 常见误区

- ❌ 只写 check 文件不改 runner imports：装饰器不触发，runner 不知道
- ❌ 直跑 `python runner.py`：相对导入失败（见 `fix_health_runner_module_invocation`）
- ❌ check 函数 raise 不 catch：runner 会包装成 critical signal，输出含 `检测器自身异常：` 前缀

## 参考

- `harness/health/registry.py`（Signal dataclass + register 装饰器）
- `harness/health/runner.py`（imports + collect 调度）
- `harness/health/checks/retrieve_pointer_consumption.py`（2026-05 新加示例）
