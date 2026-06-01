"""L4-A regression: fuzzy / typo / Chinese / abbrev queries.

每条用例: (query, expected_basename | None, label)
expected_basename = None 表示空查询/无效查询，只断言"不崩 + 返回合法 brief"。
其它情况断言期望文件出现在 top-N pointers。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import harness_retrieve as hr  # type: ignore


FUZZY_CASES: list[tuple[str, str | None, str]] = [
    # 1. 英文 typo
    ("vscod diff this file", "feedback_diff_workflow.md", "typo:vscod"),
    # 2. 纯中文
    ("帮我看一下样式失效的问题", "knowledge_qt_pyside_styling.md", "zh:样式失效"),
    # 3. 缩写
    ("qss 不生效", "knowledge_qt_pyside_styling.md", "abbrev:qss"),
    # 4. 编译报错 - 中文
    ("链接错误 undefined reference", "fixes_common_build_errors.md", "zh+en:link"),
    # 5. ld: error 黑话
    ("ld: error: cannot find -lfoo", "fixes_common_build_errors.md", "linker"),
    # 6. 大小写混合
    ("PySide6 StyleSheet setStyleSheet", "knowledge_qt_pyside_styling.md", "mixed-case"),
    # 7. 长粘贴日志含 LNK2019
    ("error LNK2019: unresolved external symbol _foo referenced in function bar (xxx).obj : "
     "error LNK2001: unresolved external symbol", "fixes_common_build_errors.md", "pasted-log"),
    # 8. 中文同义词
    ("我想看下代码对比", "feedback_diff_workflow.md", "zh:对比"),
    # 9. 空查询
    ("", None, "empty"),
    # 10. 纯符号
    ("???!!!@@@", None, "symbol-only"),
]


def _paths(brief: hr.ContextBrief) -> list[str]:
    return [p["path"] for p in brief.relevant_pointers]


@pytest.mark.parametrize("query,expected,label", FUZZY_CASES, ids=[c[2] for c in FUZZY_CASES])
def test_l4a_fuzzy_query(query, expected, label, memory_root, task_root, cache_path):
    hr.load_aliases(force=True)
    t0 = time.perf_counter()
    brief = hr.retrieve(
        task_name="demo-task", user_msg=query,
        memory_root=memory_root, task_root=task_root, cache_path=cache_path,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"slow:{label} t={elapsed:.2f}"
    assert isinstance(brief, hr.ContextBrief)
    assert brief.schema_version == "v2"
    if expected is None:
        return
    paths = _paths(brief)
    assert any(expected in p for p in paths), (
        f"MISS [{label}] query={query!r} expected={expected} got={paths}"
    )
