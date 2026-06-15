import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ARCHIVE_TASK = REPO / "harness" / "scripts" / "archive_task.py"


def load_archive_task():
    spec = importlib.util.spec_from_file_location("archive_task_for_retrospective_test", ARCHIVE_TASK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_ready_task(task: Path, phase_count: int) -> None:
    (task / "core").mkdir(parents=True)
    (task / "design").mkdir()
    rows = []
    checks = []
    for index in range(1, phase_count + 1):
        (task / "design" / f"Phase{index}-demo.md").write_text("---\nstatus: done\n---\n", encoding="utf-8")
        rows.append(f"| Phase {index} | done | demo {index} |")
        checks.append(f"- [x] P{index}: done")
    (task / "design" / "设计文档.md").write_text(
        "## Phase 拆分\n\n"
        "| Phase | 状态 | 做什么 |\n"
        "|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n## 验收清单\n"
        + "\n".join(checks)
        + "\n",
        encoding="utf-8",
    )


def write_valid_retro(task: Path) -> None:
    (task / "core" / "复盘.md").write_text(
        "# 复盘\n\n"
        "## 经验\n\n"
        "- 结论：归档 commit 必须验证复盘，见 `harness/scripts/archive_task.py:1`。\n\n"
        "## 下次可能踩\n\n"
        "- 只跑 check 可能漏掉 extract，见 `harness/scripts/archive_task.py:1`。\n\n"
        "## 不打算修\n\n"
        "- 本轮不实现交互轮数门槛，见 `docs/task-lifecycle.md:1`。\n\n"
        "self_check: rails={1,2,3,4,5}  reasoned=true\n",
        encoding="utf-8",
    )


def patch_changelog(module, tmp_path, monkeypatch):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("---\n", encoding="utf-8")
    monkeypatch.setattr(module, "CHANGELOG_MD", changelog)


def test_commit_blocks_big_task_without_retrospective_before_move(tmp_path, monkeypatch):
    module = load_archive_task()
    active = tmp_path / "active"
    task = active / "big-task"
    write_ready_task(task, phase_count=4)
    patch_changelog(module, tmp_path, monkeypatch)

    rc = module.cmd_commit(task, yes=True, reason="done")

    assert rc == 1
    assert task.is_dir()
    assert not (tmp_path / "archived" / "big-task").exists()


def test_commit_blocks_big_task_with_retrospective_lint_fail_before_move(tmp_path, monkeypatch):
    module = load_archive_task()
    active = tmp_path / "active"
    task = active / "big-task"
    write_ready_task(task, phase_count=4)
    (task / "core" / "复盘.md").write_text("# 复盘\n\n空泛总结，没有护栏。\n", encoding="utf-8")
    patch_changelog(module, tmp_path, monkeypatch)

    rc = module.cmd_commit(task, yes=True, reason="done")

    assert rc == 1
    assert task.is_dir()
    assert not (tmp_path / "archived" / "big-task").exists()


def test_commit_small_task_without_retrospective_writes_skip_note_and_moves(tmp_path, monkeypatch):
    module = load_archive_task()
    active = tmp_path / "active"
    task = active / "small-task"
    write_ready_task(task, phase_count=3)
    patch_changelog(module, tmp_path, monkeypatch)

    rc = module.cmd_commit(task, yes=True, reason="done")

    archived = tmp_path / "archived" / "small-task"
    assert rc == 0
    assert not task.exists()
    assert archived.is_dir()
    retro = archived / "core" / "复盘.md"
    assert retro.is_file()
    assert "本任务无重大踩点，跳过复盘" in retro.read_text(encoding="utf-8")


def test_extract_missing_retrospective_still_returns_lint_fail(tmp_path):
    module = load_archive_task()
    task = tmp_path / "task"
    (task / "core").mkdir(parents=True)
    (task / "ops").mkdir()

    rc = module.cmd_extract(task)

    assert rc == 2
