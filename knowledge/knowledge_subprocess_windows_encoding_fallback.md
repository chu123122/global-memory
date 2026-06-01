---
description: subprocess Windows 跨进程读：编码兜底原理 + reader 线程异常机制
priority: high
status: active
trigger:
  keywords:
    - concept:encoding
    - tool:subprocess
    - platform:windows
    - error:UnicodeDecodeError
  tags:
    - python
    - infra
    - debug
  stages:
    - implementation
    - debug
last_updated: 2026-05-21
---

# subprocess Windows 跨进程编码兜底原理

## 核心要点

1. **Windows 默认进程编码非 utf-8**：中文 Windows 系统进程通常 cp936（GBK）。命令行工具输出 / CommandLine metadata 都可能含 cp936 字节。

2. **`subprocess.run(text=True, encoding="utf-8")` 不安全**：text=True 触发 decode；`encoding="utf-8"` 显式指定 UTF-8；遇到非 UTF-8 字节 → `UnicodeDecodeError`。

3. **reader 线程异常机制**：subprocess 内部用后台线程读 stdout/stderr 并 decode；decode 失败时**异常抛在 reader 线程**，写到主进程 stderr 但**不传播到 returncode**。主进程看 `result.returncode == 0`，stderr 却有 Traceback。

4. **副作用**：上游用 stderr 内容判 PASS/FAIL 的检测器（如 `CRASH_PATTERNS = re.compile(r"Traceback|UnicodeDecodeError|...")`）会误判 WARN/FAIL。本质是「调试信息污染了诊断信号」。

5. **修复模式**：`encoding="utf-8", errors="replace"` 两个参数一起加。`errors="replace"` 把非法字节替换为 `?`，reader 线程不抛异常。

6. **何时必加**：subprocess 读**其他进程**信息时（`tasklist` / `powershell Get-CimInstance` / `wmic` / `ps aux` 跨平台）。读自家 Python 子进程时一般 stdout 是 UTF-8 不需要。

7. **替代方案**：`encoding=None`（默认）→ 返回 bytes，调用方自己 decode；`errors="ignore"` 静默丢字节。`errors="replace"` 在「保留可读 + 不丢信号」中折中。

## 常见误区

- 「我加了 `encoding="utf-8"` 已经处理编码了」→ 错。`encoding` 指定**预期编码**，遇到非该编码字节就抛错；`errors=` 才控制**异常处理策略**。
- 「returncode=0 就是成功」→ 错。subprocess reader 线程异常 returncode 仍 0。
- 「stderr 有 Traceback 一定挂了」→ 错。Windows 跨进程读时常态。

## 参考

- 修复案例：`~/.claude/global-memory/harness/verify/verify_all.py:248,258,267`
- 关联 bug：`~/.claude/global-memory/fixes/fix_subprocess_windows_cross_process_encoding.md`
- Python 文档：[Popen — text mode](https://docs.python.org/3/library/subprocess.html#frequently-used-arguments)
