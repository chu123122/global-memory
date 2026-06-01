"""L4-B regression: 走真实 ClaudeTasks/active + 真实 global-memory 数据。

不模拟。读真实 task 目录、真实 memory 树。断言:
- retrieve 不崩
- <2s
- brief schema 合法
- handoff_path 非空（任务有 HANDOFF.md 时）

不强求 pointers 命中 —— sidecar 还没人工 review apply，
原始记忆文件无 trigger frontmatter，这里只测引擎健壮性。
"""
from __future__ import annotations

import time
import os
from pathlib import Path

import pytest

import harness_retrieve as hr  # type: ignore


REAL_MEMORY = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[4])))
REAL_TASK_ROOT = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(Path.home() / ".claude" / "tasks" / "active")))


def _list_real_tasks() -> list[str]:
    if not REAL_TASK_ROOT.exists():
        return []
    return sorted(
        d.name for d in REAL_TASK_ROOT.iterdir()
        if d.is_dir() and (d / "HANDOFF.md").exists()
    )


REAL_TASKS = _list_real_tasks()


@pytest.mark.skipif(not REAL_TASKS, reason="no real tasks with HANDOFF.md found")
@pytest.mark.parametrize("task_name", REAL_TASKS)
def test_l4b_real_task_no_crash(task_name, tmp_path):
    hr.load_aliases(force=True)
    cache = tmp_path / "triggers.json"
    t0 = time.perf_counter()
    brief = hr.retrieve(
        task_name=task_name, user_msg="继续上次进度",
        memory_root=REAL_MEMORY, task_root=REAL_TASK_ROOT, cache_path=cache,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"slow task={task_name} t={elapsed:.2f}"
    assert isinstance(brief, hr.ContextBrief)
    assert brief.schema_version == "v2"
    assert brief.handoff_path, f"empty handoff for {task_name}"


REAL_QUERIES = [
    "vscode diff 看代码",
    "qt qss 不生效",
    "编译 LNK2019 链接错误",
    "shader 缺失",
    "c++ 多线程 mutex",
    "ue 编辑器扩展",
    "pyside6 stylesheet",
    "学习路线",
]


@pytest.mark.skipif(not REAL_TASKS, reason="no real tasks")
@pytest.mark.parametrize("query", REAL_QUERIES, ids=[q[:20] for q in REAL_QUERIES])
def test_l4b_real_memory_no_crash(query, tmp_path):
    hr.load_aliases(force=True)
    cache = tmp_path / "triggers.json"
    pick = REAL_TASKS[0]
    t0 = time.perf_counter()
    brief = hr.retrieve(
        task_name=pick, user_msg=query,
        memory_root=REAL_MEMORY, task_root=REAL_TASK_ROOT, cache_path=cache,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"slow q={query!r} t={elapsed:.2f}"
    assert isinstance(brief, hr.ContextBrief)
