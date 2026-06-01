---
description: 路径 linter 把守护测试的「断言硬编码不存在」误报为硬编码违规；smoke-test 退出码分类埋根因
priority: medium
status: active
trigger:
  keywords:
    - tool:fix_hardcoded_paths
    - tool:smoke-test
    - concept:false-positive
    - concept:hardcoded-path
    - concept:guard-test
  tags:
    - tooling
    - debug
    - python
    - infra
  stages:
    - debug
last_updated: 2026-06-01
---

# 路径 linter 误报守护测试 + smoke-test WARN 不透明

## 现象
`fix_hardcoded_paths.py --check` 报 `tests/test_warning_cleanup.py:L170 硬编码 Path() 路径: Path("D:/`，但该行是 `assert 'Path("D:/ClaudeTasks")' not in text`——防回退的守护测试。smoke-test 同时只把它显示为 `WARN exit 1`，看不出根因，要手动跑 linter 才知道是误报。

## 根因
两层独立缺陷：
1. **linter 裸正则匹配字面量**，分不清「生产代码里的真硬编码路径」和「测试里被断言『不应出现』的字符串」。测试 fixture 路径同理是合法的。`check_python_scripts` 只跳了注释行/docstring 起始行，没跳测试文件。
2. **smoke-test 退出码分类**（`smoke_test.py` run/hook 分支）：exit≠0 且无 Traceback → 一律 WARN，detail 只写 `exit {code}`。「打印 usage 的脚本」和「检测到真问题的脚本」退出码长得一样，根因被压成不透明 WARN。

附：当时还叠加了并发会话正在重构 `archive_task.py`（去硬编码中途），导致 linter 两次运行命中不同文件，一度误判成 linter 归因 bug——实为文件被并发修改。排查时先查 mtime/git status 能避开此坑。

## 修复
1. `fix_hardcoded_paths.py` `check_python_scripts`：循环内跳过测试文件——
   ```python
   parts_lower = {p.lower() for p in py_file.parts}
   if "tests" in parts_lower or "__pycache__" in parts_lower:
       continue
   if py_file.stem.startswith("test_") or py_file.stem.endswith("_test"):
       continue
   ```
2. `smoke_test.py`：加 `summarize_output(combined)`，WARN 分支 detail 改为 `f"exit {code}: {summary}"`，摘一行含 `发现/问题/drift/缺少/ERROR` 等关键词的输出，否则取末行。

## 验证
- linter 复跑 Python 段 → `✅ 无硬编码路径`
- smoke-test → 24 PASS / 0 WARN / 0 FAIL
- `summarize_output` 单测：关键词行 / 无关键词取末行 / 空串 三用例通过
- commit `dc4ace9`（global-memory main）
