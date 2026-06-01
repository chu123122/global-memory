#!/usr/bin/env python3
"""
_task_resolver.py — 公共归属解析库

按 ~/.claude/projects/project_registry.json 的 task_paths 解析文件归属哪个 active_task。

调用方：
- diff_backup.py  （本任务新引入）
- show_diffs.py   （本任务新引入）
- doc_gate.py     仍用自己的 tasks_owning_path（TD-5：后续独立任务迁移）

匹配规则（D-10）：
1. 遍历 active_tasks，对每个 task 看 task_paths[task] 中有无片段命中 file_path
2. 命中后记录 (task, 该 task 命中片段的最大长度, list 中位置)
3. 排序：片段长度降序 → list 位置升序（同长 tie-break）
4. 取首个

设计参见 $env:CLAUDE_TASKS_ACTIVE/diff-workflow-redesign/{DESIGN,SPEC}.md
"""

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CLAUDE_HOME  # noqa: E402

CLAUDE_DIR = CLAUDE_HOME
REGISTRY_FILE = CLAUDE_DIR / "projects" / "project_registry.json"


def load_registry() -> dict:
    """读 ~/.claude/projects/project_registry.json；失败返回 {}。"""
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize(path: str) -> str:
    """统一为正斜杠（Windows 路径与 task_paths 片段对齐）。"""
    return path.replace("\\", "/")


def resolve_task_owner(file_path: str, registry: dict) -> Optional[str]:
    """
    返回 file_path 归属的 active_task 名；不归属任何 task 返回 None。

    退化场景：
    - file_path 为空 → None
    - registry 缺 active_tasks 或 task_paths → None
    - 无任何 task 的片段命中 → None
    """
    if not file_path:
        return None
    active_tasks = registry.get("active_tasks", []) or []
    task_paths = registry.get("task_paths", {})
    if not active_tasks or not isinstance(task_paths, dict):
        return None

    fp = normalize(file_path)
    candidates = []  # [(task, max_fragment_len, list_index)]
    for idx, task in enumerate(active_tasks):
        fragments = task_paths.get(task, []) or []
        best_len = -1
        for frag in fragments:
            if frag and frag in fp:
                if len(frag) > best_len:
                    best_len = len(frag)
        if best_len > 0:
            candidates.append((task, best_len, idx))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[1], x[2]))
    return candidates[0][0]
