"""L3 smoke tests — S1..S5 replay simulated user-prompts against retrieve."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import harness_retrieve as hr  # type: ignore


@pytest.fixture
def fat_memory(tmp_path):
    """Larger fixture mirroring real memory layout: 多个 feedback/knowledge/fixes。"""
    root = tmp_path / "mem"
    for sub in ("feedback", "knowledge", "fixes", "decisions"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    files = [
        ("feedback", "feedback_diff_workflow.md", "tool:diff,tool:vscode", "workflow", "debug"),
        ("feedback", "feedback_code_style.md", "concept:style", "doc", "implementation"),
        ("feedback", "feedback_compile_after_module_change.md", "concept:build", "build", "implementation"),
        ("feedback", "feedback_visual_aesthetic.md", "tool:ui", "ui", "implementation"),
        ("knowledge", "knowledge_qt_pyside_styling.md", "tool:qt,concept:style", "ui", "implementation"),
        ("knowledge", "knowledge_cpp_multithreading.md", "concept:cpp,concept:thread", "cpp", "implementation"),
        ("knowledge", "knowledge_ue_internals.md", "tool:ue", "ue", "implementation"),
        ("fixes", "fixes_common_build_errors.md", "concept:build,error:link", "build", "debug"),
        ("fixes", "fixes_shader_code_library_missing.md", "error:shader,tool:ue", "build", "debug"),
    ]
    for sub, name, kws, tag, stage in files:
        (root / sub / name).write_text(
            "---\n"
            f"description: {name}\n"
            "priority: medium\n"
            "status: active\n"
            "trigger:\n"
            "  keywords:\n"
            + "".join(f"    - {k}\n" for k in kws.split(",")) +
            "  tags:\n"
            f"    - {tag}\n"
            "  stages:\n"
            f"    - {stage}\n"
            "---\n"
            f"# {name}\n",
            encoding="utf-8",
        )
    return root


@pytest.fixture
def fat_task(tmp_path):
    root = tmp_path / "tasks"
    t = root / "harness-context-governance"
    t.mkdir(parents=True)
    (t / "HANDOFF.md").write_text("# H\n\n## 下次开始\n继续 retrieve 实现。\n", encoding="utf-8")

    new = root / "new-test-task"
    new.mkdir()
    return root


def _paths(b):
    return [p["path"] for p in b.relevant_pointers]


def test_s1_new_task_brief(fat_memory, fat_task, tmp_path):
    """S1: 新任务 /work new-test-task → brief 不崩，handoff 空但不抛异常。"""
    cache = tmp_path / "c.json"
    b = hr.retrieve(task_name="new-test-task", user_msg="just starting",
                    memory_root=fat_memory, task_root=fat_task, cache_path=cache)
    assert b.task == "new-test-task"
    assert b.handoff_path == ""


def test_s2_continue_task_handoff(fat_memory, fat_task, tmp_path):
    """S2: 续老任务 → brief 含 HANDOFF excerpt。"""
    cache = tmp_path / "c.json"
    b = hr.retrieve(task_name="harness-context-governance", user_msg="继续做",
                    memory_root=fat_memory, task_root=fat_task, cache_path=cache)
    assert b.handoff_path.endswith("HANDOFF.md")


def test_s3_compile_debug_routes_to_fixes(fat_memory, fat_task, tmp_path):
    """S3: 编译失败 query → 推 fixes_common_build_errors。"""
    cache = tmp_path / "c.json"
    b = hr.retrieve(task_name="harness-context-governance",
                    user_msg="concept:build error link issue",
                    memory_root=fat_memory, task_root=fat_task, cache_path=cache, stage="debug")
    paths = _paths(b)
    assert any("fixes_common_build_errors" in p for p in paths)


def test_s4_ui_routes_to_qt(fat_memory, fat_task, tmp_path):
    """S4: UI/Qt query → 推 knowledge_qt_pyside_styling。"""
    cache = tmp_path / "c.json"
    b = hr.retrieve(task_name="harness-context-governance",
                    user_msg="tool:qt style not applied",
                    memory_root=fat_memory, task_root=fat_task, cache_path=cache, stage="implementation")
    paths = _paths(b)
    assert any("knowledge_qt_pyside_styling" in p for p in paths)


def test_s5_diff_routes_to_workflow(fat_memory, fat_task, tmp_path):
    """S5: diff 工具 query → 推 feedback_diff_workflow。"""
    cache = tmp_path / "c.json"
    b = hr.retrieve(task_name="harness-context-governance",
                    user_msg="check tool:vscode diff",
                    memory_root=fat_memory, task_root=fat_task, cache_path=cache)
    paths = _paths(b)
    assert any("feedback_diff_workflow" in p for p in paths)
