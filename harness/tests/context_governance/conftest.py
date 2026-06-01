"""Shared pytest fixtures for context governance tests."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def memory_root(tmp_path: Path) -> Path:
    """Build a minimal feedback/knowledge/fixes fixture tree under tmp."""
    root = tmp_path / "global-memory"
    for sub in ("feedback", "knowledge", "fixes", "decisions"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    (root / "feedback" / "feedback_diff_workflow.md").write_text(
        _md(
            description="VS Code diff workflow",
            tags=["workflow"],
            keywords=["tool:diff", "tool:vscode"],
            stages=["debug"],
            body="# diff workflow\n\n用 VS Code 看 diff。\n",
        ),
        encoding="utf-8",
    )
    (root / "feedback" / "feedback_unrelated.md").write_text(
        _md(
            description="unrelated coffee preference",
            tags=["doc"],
            keywords=["concept:coffee"],
            stages=["delivery"],
            body="# nothing\n",
        ),
        encoding="utf-8",
    )
    (root / "feedback" / "feedback_deprecated.md").write_text(
        _md(
            description="old deprecated rule",
            tags=["workflow"],
            keywords=["tool:diff"],
            stages=["debug"],
            body="# old\n",
            status="deprecated",
        ),
        encoding="utf-8",
    )
    (root / "feedback" / "feedback_broken_yaml.md").write_text(
        "---\ndescription: broken\nkeywords: [tool:diff,\nbody not yaml\n---\n# broken\n",
        encoding="utf-8",
    )
    (root / "knowledge" / "knowledge_qt_pyside_styling.md").write_text(
        _md(
            description="Qt QSS pitfalls",
            tags=["ui"],
            keywords=["tool:qt", "concept:style"],
            stages=["implementation"],
            body="# Qt\n",
        ),
        encoding="utf-8",
    )
    (root / "fixes" / "fixes_common_build_errors.md").write_text(
        _md(
            description="common build error recipes",
            tags=["build"],
            keywords=["concept:build", "error:link"],
            stages=["debug"],
            body="# build\n",
        ),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def task_root(tmp_path: Path) -> Path:
    root = tmp_path / "tasks" / "active"
    task = root / "demo-task"
    task.mkdir(parents=True)
    (task / "HANDOFF.md").write_text(
        "# Demo HANDOFF\n\n## 进度\n\n- 2026-05-20 上次写到 phase 1\n\n## 下次开始\n\n继续 phase 1 第 3 步。\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def cache_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "triggers.json"


@pytest.fixture
def task_index_path(tmp_path: Path) -> Path:
    """ClaudeTasks 跨任务经验索引（workflow 内容分类产出格式）。"""
    p = tmp_path / "data" / "task_experience_index.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({
            "schema_version": "v1",
            "source": "task-experience-triage",
            "count": 2,
            "entries": [
                {
                    "path": "D:/ClaudeTasks/archived/some-task/ops/坑点.md",
                    "task": "archived/some-task",
                    "type": "pitfall",
                    "description": "android apk packaging resign obb pitfalls",
                    "keywords": ["platform:android", "concept:packaging", "concept:obb"],
                    "tags": ["build", "ue"],
                    "confidence": 0.9,
                },
                {
                    "path": "D:/ClaudeTasks/archived/other-task/core/复盘.md",
                    "task": "archived/other-task",
                    "type": "retrospective",
                    "description": "lua coroutine scheduling lessons",
                    "keywords": ["concept:coroutine", "lua:scheduler"],
                    "tags": ["lua"],
                    "confidence": 0.8,
                },
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return p


def _md(description: str, tags: list[str], keywords: list[str], stages: list[str],
        body: str, status: str = "active", priority: str = "medium") -> str:
    lines = [
        "---",
        f"description: {description}",
        f"priority: {priority}",
        f"status: {status}",
        "trigger:",
        "  keywords:",
        *[f"    - {k}" for k in keywords],
        "  tags:",
        *[f"    - {t}" for t in tags],
        "  stages:",
        *[f"    - {s}" for s in stages],
        "---",
        body,
    ]
    return "\n".join(lines)
