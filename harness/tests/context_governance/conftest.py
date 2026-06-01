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
