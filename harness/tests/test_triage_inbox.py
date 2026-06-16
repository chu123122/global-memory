import json
import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TRIAGE_INBOX = REPO / "harness" / "scripts" / "triage_inbox.py"


def load_triage_inbox():
    spec = importlib.util.spec_from_file_location("triage_inbox_for_test", TRIAGE_INBOX)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_issue(root: Path, name: str, status: str, severity: str = "minor", body_extra: str = "") -> Path:
    path = root / "issues" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"issue_id: {path.stem}\n"
        f"status: {status}\n"
        f"severity: {severity}\n"
        "---\n\n"
        f"# {path.stem} title\n\n"
        "问题摘要。\n"
        f"{body_extra}",
        encoding="utf-8",
    )
    return path


def write_feedback(root: Path, name: str, status: str = "active", priority: str = "high", body_extra: str = "") -> Path:
    path = root / "feedback" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "description: 测试反馈条目\n"
        f"priority: {priority}\n"
        f"status: {status}\n"
        "---\n\n"
        "# 反馈标题\n\n"
        "## 规则\n\n"
        "必须保留用户确认门。\n"
        f"{body_extra}",
        encoding="utf-8",
    )
    return path


def snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def run_verify_close(module, repo_root: Path, path: Path, capsys):
    code = module.main([
        "--repo-root",
        str(repo_root),
        "--verify-close",
        path.relative_to(repo_root).as_posix(),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    return code, payload


def test_open_issue_is_scanned(tmp_path):
    module = load_triage_inbox()
    write_issue(tmp_path, "ISSUE-2026-06-15-demo.md", "open", severity="major")

    payload = module.build_payload(tmp_path)

    assert payload["kind"] == "triage_inbox.v1"
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["source_type"] == "issue"
    assert item["status"] == "open"
    assert item["suggested_lane"] == "work"
    assert item["path"] == "issues/ISSUE-2026-06-15-demo.md"


def test_closed_or_non_open_issue_is_not_scanned(tmp_path):
    module = load_triage_inbox()
    write_issue(tmp_path, "ISSUE-2026-06-15-closed.md", "closed", severity="major")
    write_issue(tmp_path, "ISSUE-2026-06-15-deferred.md", "deferred", severity="major")

    payload = module.build_payload(tmp_path)

    assert payload["items"] == []
    assert payload["summary"]["total"] == 0


def test_active_feedback_is_scanned(tmp_path):
    module = load_triage_inbox()
    write_feedback(tmp_path, "feedback_demo.md", status="active", priority="high")

    payload = module.build_payload(tmp_path)

    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["id"] == "feedback:feedback_demo"
    assert item["source_type"] == "feedback"
    assert item["status"] == "active"
    assert item["suggested_lane"] == "task"


def test_json_output_contract_is_stable(tmp_path, capsys):
    module = load_triage_inbox()
    write_issue(tmp_path, "ISSUE-2026-06-15-demo.md", "open", severity="minor")
    write_feedback(tmp_path, "feedback_demo.md", status="active", priority="high")

    assert module.main(["--repo-root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert sorted(payload.keys()) == ["items", "kind", "summary"]
    assert payload["kind"] == "triage_inbox.v1"
    assert payload["summary"] == {
        "counts": {
            "source_type": {"feedback": 1, "issue": 1},
            "suggested_lane": {"task": 2},
        },
        "total": 2,
    }
    assert [item["path"] for item in payload["items"]] == [
        "feedback/feedback_demo.md",
        "issues/ISSUE-2026-06-15-demo.md",
    ]
    assert sorted(payload["items"][0].keys()) == [
        "id",
        "path",
        "source_type",
        "status",
        "suggested_lane",
        "summary",
        "title",
    ]


def test_script_is_read_only_for_scanned_sources(tmp_path, capsys):
    module = load_triage_inbox()
    write_issue(tmp_path, "ISSUE-2026-06-15-demo.md", "open", severity="major")
    write_feedback(tmp_path, "feedback_demo.md", status="active", priority="high")
    before = snapshot_tree(tmp_path)

    assert module.main(["--repo-root", str(tmp_path), "--json"]) == 0
    capsys.readouterr()

    assert snapshot_tree(tmp_path) == before


def test_verify_close_fails_open_issue_without_close_record(tmp_path, capsys):
    module = load_triage_inbox()
    path = write_issue(tmp_path, "ISSUE-2026-06-16-open.md", "open", severity="major")
    before = snapshot_tree(tmp_path)

    code, payload = run_verify_close(module, tmp_path, path, capsys)

    assert code == 1
    assert payload["kind"] == "triage_close_verification.v1"
    assert payload["verdict"] == "FAIL"
    assert payload["source_type"] == "issue"
    assert payload["status"] == "open"
    assert any(check["name"] == "status_closed" and check["pass"] is False for check in payload["checks"])
    assert any(check["name"] == "evidence_present" and check["pass"] is False for check in payload["checks"])
    assert snapshot_tree(tmp_path) == before


def test_verify_close_fails_closed_issue_without_evidence(tmp_path, capsys):
    module = load_triage_inbox()
    path = write_issue(tmp_path, "ISSUE-2026-06-16-closed.md", "closed", severity="major")

    code, payload = run_verify_close(module, tmp_path, path, capsys)

    assert code == 1
    assert payload["verdict"] == "FAIL"
    assert payload["status"] == "closed"
    assert any(check["name"] == "status_closed" and check["pass"] is True for check in payload["checks"])
    assert any(check["name"] == "evidence_present" and check["pass"] is False for check in payload["checks"])


def test_verify_close_passes_closed_issue_with_close_record_and_verify_command(tmp_path, capsys):
    module = load_triage_inbox()
    path = write_issue(
        tmp_path,
        "ISSUE-2026-06-16-fixed.md",
        "closed",
        severity="major",
        body_extra="\n## 关闭记录\n\n验证命令：`pytest harness/tests/test_triage_inbox.py -q` PASS。\n",
    )

    code, payload = run_verify_close(module, tmp_path, path, capsys)

    assert code == 0
    assert payload["verdict"] == "PASS"
    assert payload["source_type"] == "issue"
    assert all(check["pass"] is True for check in payload["checks"])


def test_verify_close_fails_active_feedback(tmp_path, capsys):
    module = load_triage_inbox()
    path = write_feedback(tmp_path, "feedback_active.md", status="active", priority="high")

    code, payload = run_verify_close(module, tmp_path, path, capsys)

    assert code == 1
    assert payload["verdict"] == "FAIL"
    assert payload["source_type"] == "feedback"
    assert payload["status"] == "active"
    assert any(check["name"] == "status_closed" and check["pass"] is False for check in payload["checks"])


def test_verify_close_passes_dropped_feedback_with_drop_reason(tmp_path, capsys):
    module = load_triage_inbox()
    path = write_feedback(
        tmp_path,
        "feedback_drop.md",
        status="dropped",
        priority="low",
        body_extra="\n## 关闭原因\n\nDrop reason: duplicate with newer issue, user confirmed drop.\n",
    )

    code, payload = run_verify_close(module, tmp_path, path, capsys)

    assert code == 0
    assert payload["verdict"] == "PASS"
    assert payload["status"] == "dropped"
    assert all(check["pass"] is True for check in payload["checks"])


def test_verify_close_passes_superseded_feedback_with_reason(tmp_path, capsys):
    module = load_triage_inbox()
    path = write_feedback(
        tmp_path,
        "feedback_superseded.md",
        status="superseded",
        priority="low",
        body_extra="\n## 关闭记录\n\nSuperseded by ISSUE-2026-06-16-new-policy; reason: merged into broader rule.\n",
    )

    code, payload = run_verify_close(module, tmp_path, path, capsys)

    assert code == 0
    assert payload["verdict"] == "PASS"
    assert payload["status"] == "superseded"
    assert all(check["pass"] is True for check in payload["checks"])


def test_verify_close_fails_missing_source_file(tmp_path, capsys):
    module = load_triage_inbox()
    path = tmp_path / "issues" / "ISSUE-2026-06-16-missing.md"

    code = module.main([
        "--repo-root",
        str(tmp_path),
        "--verify-close",
        path.relative_to(tmp_path).as_posix(),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["verdict"] == "FAIL"
    assert any(check["name"] == "file_exists" and check["pass"] is False for check in payload["checks"])


def test_verify_close_fails_unsupported_source_path(tmp_path, capsys):
    module = load_triage_inbox()
    path = tmp_path / "docs" / "note.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nstatus: closed\n---\n\n## 关闭记录\n\n验证证据已记录。\n", encoding="utf-8")

    code = module.main([
        "--repo-root",
        str(tmp_path),
        "--verify-close",
        path.relative_to(tmp_path).as_posix(),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["verdict"] == "FAIL"
    assert payload["source_type"] == "unsupported"
    assert any(check["name"] == "path_supported" and check["pass"] is False for check in payload["checks"])
