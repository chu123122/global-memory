---
description: subprocess Windows 读其他进程信息缺 errors="replace" → reader 线程 UnicodeDecodeError 污染 stderr
priority: high
status: active
trigger:
  keywords:
    - error:UnicodeDecodeError
    - tool:subprocess
    - platform:windows
    - concept:encoding
  tags:
    - python
    - infra
    - tooling
  stages:
    - debug
last_updated: 2026-05-21
---

# subprocess Windows 跨进程读 → 必加 errors="replace"

## 现象

`subprocess.run(["powershell", ..., "Get-CimInstance Win32_Process | ... CommandLine"], text=True, encoding="utf-8")` 正常退出 returncode=0，但 stderr 出现 Traceback：

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb0 ...
```

上游用 stderr 内容做 PASS/FAIL 判定（如 smoke_test 的 `CRASH_PATTERNS` 正则）会误判 WARN/FAIL。

## 根因

读其他系统进程 CommandLine / 输出时，目标进程编码可能是 cp936（中文 Windows 默认）。`subprocess.run(text=True, encoding="utf-8")` 在 decode 失败时由 reader 线程抛 UnicodeDecodeError，写到 stderr 但**不影响主流程 returncode**。

典型触发命令：
- `powershell Get-CimInstance Win32_Process`
- `tasklist /fo csv`
- 任何读其他进程 metadata 的 cmdlet

## 修复

三处调用统一加 `errors="replace"`：

```python
subprocess.run(
    ["powershell", "-NoProfile", "-Command", "Get-CimInstance ..."],
    capture_output=True, text=True,
    encoding="utf-8", errors="replace",  # ← 必加
    timeout=10
)
```

`errors="replace"` 把无法 decode 字节替换为 `?`，reader 线程不抛异常，stderr 保持干净。

## 验证

```bash
python verify_all.py 2>&1 1>/dev/null   # stderr 应为空
python smoke_test.py                     # WARN 数减少
```

实测案例：`harness-governance-followup` 修复 `verify_all.py:check_auto_sync` 后 smoke_test 23 PASS / 2 WARN（之前 22/3）。
