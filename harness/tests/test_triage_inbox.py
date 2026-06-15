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


def write_issue(root: Path, name: str, status: str, severity: str = "minor") -> Path:
    path = root / "issues" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"issue_id: {path.stem}\n"
        f"status: {status}\n"
        f"severity: {severity}\n"
        "---\n\n"
        f"# {path.stem} title\n\n"
        "问题摘要。\n",
        encoding="utf-8",
    )
    return path


def write_feedback(root: Path, name: str, status: str = "active", priority: str = "high") -> Path:
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
        "必须保留用户确认门。\n",
        encoding="utf-8",
    )
    return path


def snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


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
