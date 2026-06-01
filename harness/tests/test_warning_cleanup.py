import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
VERIFY_CONVENTIONS = REPO / "harness" / "verify" / "verify_conventions.py"
TASK_COMPLETE = REPO / "harness" / "task_complete.py"
ARCHIVE_TASK = REPO / "harness" / "scripts" / "archive_task.py"


def load_verify_conventions():
    spec = importlib.util.spec_from_file_location("verify_conventions_for_test", VERIFY_CONVENTIONS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_archive_task():
    spec = importlib.util.spec_from_file_location("archive_task_for_test", ARCHIVE_TASK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mem03_pointer_mode_does_not_require_exhaustive_index(tmp_path, monkeypatch):
    memory = tmp_path / "memory"
    (memory / "feedback").mkdir(parents=True)
    (memory / "feedback" / "feedback_example.md").write_text("# example\n", encoding="utf-8")
    (memory / "MEMORY.md").write_text(
        "# 全局记忆索引（指针模式）\n\n"
        "- `feedback/` — 行为纠正\n"
        "- 旧全索引：`MEMORY-LEGACY.md`\n",
        encoding="utf-8",
    )

    module = load_verify_conventions()
    monkeypatch.setattr(module, "MEMORY_DIR", memory)

    checker = module.ConventionChecker()
    checker.check_mem03_index_sync()

    assert ("MEM-03", "PASS", "MEMORY.md 使用指针模式；跳过旧全量链接索引检查") in checker.results


def test_harness02_warns_completed_small_v2_task_without_review(tmp_path):
    task = tmp_path / "task"
    (task / "core").mkdir(parents=True)
    (task / "design").mkdir()
    (task / "core" / "HANDOFF.md").write_text("# Handoff\n", encoding="utf-8")
    (task / "design" / "Phase1-small.md").write_text("---\nstatus: done\n---\n", encoding="utf-8")

    module = load_verify_conventions()
    checker = module.ConventionChecker()
    checker.check_harness02_review(task)

    assert ("HARNESS-02", "WARNING", "v2 小任务已完成，归档前补 core/复盘.md（可写跳过复盘）") in checker.results


def test_harness02_skips_unfinished_small_v2_task(tmp_path):
    task = tmp_path / "task"
    (task / "core").mkdir(parents=True)
    (task / "design").mkdir()
    (task / "core" / "HANDOFF.md").write_text("# Handoff\n", encoding="utf-8")
    (task / "design" / "Phase1-small.md").write_text("---\nstatus: pending\n---\n", encoding="utf-8")

    module = load_verify_conventions()
    checker = module.ConventionChecker()
    checker.check_harness02_review(task)

    assert ("HARNESS-02", "SKIP", "v2 小任务未达到复盘门槛，跳过 core/复盘.md") in checker.results


def test_task_complete_uses_v2_progress_docs():
    text = TASK_COMPLETE.read_text(encoding="utf-8")

    assert "core/HANDOFF.md" in text
    assert "design/进度.md" in text
    assert "v2 进度文档完整性检查" in text


def test_archive_check_requires_design_acceptance_sync(tmp_path, capsys):
    task = tmp_path / "task"
    (task / "design").mkdir(parents=True)
    (task / "design" / "Phase1-demo.md").write_text("---\nstatus: done\n---\n", encoding="utf-8")
    (task / "design" / "设计文档.md").write_text(
        "## Phase 拆分\n\n"
        "| Phase | 状态 | 做什么 |\n"
        "|---|---|---|\n"
        "| Phase 1 | pending | demo |\n"
        "\n"
        "## 验收清单\n"
        "- [ ] P1：同步设计文档\n",
        encoding="utf-8",
    )

    module = load_archive_task()
    rc = module.cmd_check(task)
    out = capsys.readouterr().out

    assert rc == 1
    assert "ready_to_archive: false" in out
    assert "design/设计文档.md Phase 1 status=pending" in out
    assert "unchecked acceptance" in out


def test_archive_check_reads_status_column_not_second_cell(tmp_path, capsys):
    task = tmp_path / "task"
    (task / "design").mkdir(parents=True)
    (task / "design" / "Phase1-demo.md").write_text("---\nstatus: done\n---\n", encoding="utf-8")
    (task / "design" / "设计文档.md").write_text(
        "| Phase | 内容 | 目的 | 状态 |\n"
        "|---|---|---|---|\n"
        "| Phase 1 | implement archive check | avoid false positives | done |\n"
        "\n"
        "## 验收清单\n"
        "- [x] P1：同步设计文档\n",
        encoding="utf-8",
    )

    module = load_archive_task()
    rc = module.cmd_check(task)
    out = capsys.readouterr().out

    assert rc == 0
    assert "ready_to_archive: true" in out
    assert "implement archive check" not in out


def test_archive_check_ignores_non_phase_tables_after_phase_section(tmp_path, capsys):
    task = tmp_path / "task"
    (task / "design").mkdir(parents=True)
    (task / "design" / "Phase1-demo.md").write_text("---\nstatus: done\n---\n", encoding="utf-8")
    (task / "design" / "设计文档.md").write_text(
        "## Phase 拆分\n\n"
        "| Phase | 主题 | 状态 |\n"
        "|---|---|---|\n"
        "| Phase 1 | demo | done |\n"
        "\n"
        "## 关键决策\n\n"
        "| # | 决策 | 理由 | 替代方案 |\n"
        "|---|---|---|---|\n"
        "| 1 | keep parser scoped | avoid table bleed | old behavior |\n"
        "\n"
        "## 验收清单\n"
        "- [x] P1：同步设计文档\n",
        encoding="utf-8",
    )

    module = load_archive_task()
    rc = module.cmd_check(task)
    out = capsys.readouterr().out

    assert rc == 0
    assert "ready_to_archive: true" in out
    assert "old behavior" not in out


def test_archive_destination_uses_sibling_archived_for_absolute_active_path(tmp_path):
    module = load_archive_task()
    task = tmp_path / "active" / "sample-task"

    assert module.archive_destination(task) == tmp_path / "archived" / "sample-task"


def test_archive_task_uses_shared_task_config_instead_of_local_absolute_path():
    text = ARCHIVE_TASK.read_text(encoding="utf-8")
    forbidden = 'Path("' + chr(68) + ':/ClaudeTasks")'

    assert forbidden not in text
    assert "from config import CLAUDE_TASKS_ROOT" in text


def test_archive_retro_requires_full_self_check(tmp_path):
    retro = tmp_path / "复盘.md"
    retro.write_text(
        "# 复盘\n\n"
        "## 下次可能踩\n\n"
        "- 见 `a.py:1`\n\n"
        "## 不打算修\n\n"
        "- 无。\n\n"
        "self_check: rails={1} reasoned=true\n",
        encoding="utf-8",
    )

    module = load_archive_task()
    ok, errors = module.lint_retro(retro)

    assert not ok
    assert any("缺 self_check 锚行" in e for e in errors)


def test_archive_retro_allows_explicit_small_task_skip(tmp_path):
    retro = tmp_path / "复盘.md"
    retro.write_text("本任务无重大踩点，跳过复盘。2026-06-01\n", encoding="utf-8")

    module = load_archive_task()
    ok, errors = module.lint_retro(retro)

    assert ok
    assert errors == []


def test_task_complete_reports_archive_readiness():
    text = TASK_COMPLETE.read_text(encoding="utf-8")

    assert "Archive readiness" in text
    assert "archive_task.py" in text
    assert "--extract <task>" in text
