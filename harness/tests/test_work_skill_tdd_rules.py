import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WORK_SKILL = REPO / "skills" / "work" / "v1" / "SKILL.md"
CREATE_TASK = Path.home() / ".claude" / "scripts" / "create_task.py"
RENDER_CODEX_WORK = REPO / "harness" / "scripts" / "render_codex_work_skill.py"
CODEX_ADAPTER = REPO / "skills" / "work" / "v1" / "codex-adapter.md"
VERIFY_ALL = REPO / "harness" / "verify" / "verify_all.py"
WORK_CONTEXT_PACK = REPO / "harness" / "work_context_pack.py"


def load_verify_all():
    spec = importlib.util.spec_from_file_location("verify_all_for_test", VERIFY_ALL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_work_context_pack():
    spec = importlib.util.spec_from_file_location("work_context_pack_for_test", WORK_CONTEXT_PACK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_work_skill_requires_phase_tdd_loop():
    text = WORK_SKILL.read_text(encoding="utf-8")

    required_phrases = [
        "Phase 卡就是最小 Spec 单元",
        "先写会失败的测试",
        "Red 结果",
        "Green 结果",
        "实现后补的测试不算 TDD",
        "不新增独立 SPEC 文档",
    ]

    missing = [phrase for phrase in required_phrases if phrase not in text]
    assert missing == []


def test_work_skill_has_code_change_test_rule():
    text = WORK_SKILL.read_text(encoding="utf-8")

    assert "凡是改代码，必须有测试或替代验证" in text
    assert "无法先写测试" in text


def test_work_skill_requires_intent_guard_for_new_task_requests():
    text = WORK_SKILL.read_text(encoding="utf-8")

    assert "--intent" in text
    assert "intent_guard" in text
    assert "create_task.py" in text


def test_create_task_phase_template_has_tdd_record():
    text = CREATE_TASK.read_text(encoding="utf-8")

    assert "## TDD 记录" in text
    assert "Red 结果" in text
    assert "Green 结果" in text
    assert "无法先写测试" in text


def test_codex_work_skill_is_generated_from_work_source():
    script = RENDER_CODEX_WORK.read_text(encoding="utf-8")
    adapter = CODEX_ADAPTER.read_text(encoding="utf-8")

    assert "AUTO-GENERATED from global-memory/skills/work/v1/SKILL.md" in script
    assert "codex-adapter.md" in script
    assert "Do not rely on Claude Code-only statusline, hooks, or subagents." in adapter
    assert "apply_patch" in adapter


def test_verify_all_runs_codex_work_drift_check(monkeypatch):
    module = load_verify_all()
    calls = []

    class RunResult:
        returncode = 0
        stdout = "codex-work generated skill is up to date"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return RunResult()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.check_codex_work_skill_drift()

    assert result.level == "PASS"
    assert calls
    assert "--check" in calls[0]
    assert any("render_codex_work_skill.py" in str(part) for part in calls[0])
    assert any(
        name == "Codex work skill" and check_fn == module.check_codex_work_skill_drift
        for name, check_fn in module.ALL_CHECKS
    )


def test_work_context_pack_warns_when_new_task_intent_uses_current_task(tmp_path, monkeypatch):
    module = load_work_context_pack()
    tasks_root = tmp_path / "active"
    task_dir = tasks_root / "old-task"
    (task_dir / "core").mkdir(parents=True)
    (task_dir / "design").mkdir()
    (task_dir / "ops").mkdir()
    for rel in [
        "core/HANDOFF.md",
        "core/INDEX.md",
        "core/背景.md",
        "design/设计文档.md",
        "design/进度.md",
        "ops/CHANGELOG.md",
    ]:
        (task_dir / rel).write_text("# doc\n", encoding="utf-8")

    registry = {
        "active_tasks": ["old-task"],
        "tasks_root": str(tasks_root),
        "task_structure_v2": {
            "required_files": [
                "core/HANDOFF.md",
                "core/INDEX.md",
                "core/背景.md",
                "design/设计文档.md",
                "design/进度.md",
                "ops/CHANGELOG.md",
            ]
        },
    }

    monkeypatch.setattr(module, "load_registry", lambda: registry)
    monkeypatch.setattr(module, "read_current_task_file", lambda: "old-task")

    report = module.build_report(
        None,
        tmp_path,
        update_session=False,
        intent="新开一个 work skill 维护 task，跑实现",
    )

    assert report["level"] == "WARNING"
    assert report["intent_guard"]["action"] == "create_task_or_confirm"
    assert "create_task.py" in report["recommended_next_step"]
