import importlib.util
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REGISTER_SCRIPT = REPO / "harness" / "scripts" / "register_script.py"
SCAN_ORPHAN = REPO / "harness" / "scripts" / "scan_orphan_scripts.py"
CHECK_CAPABILITY = REPO / "harness" / "scripts" / "check_capability_manifest.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_register_script():
    return load_module(REGISTER_SCRIPT, "register_script_for_test")


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    harness = root / "harness"
    docs = root / "docs"
    (harness / "scripts").mkdir(parents=True)
    docs.mkdir(parents=True)
    (harness / "scripts" / "existing.py").write_text("print('existing')\n", encoding="utf-8")
    (harness / "scripts" / "new_tool.py").write_text("print('new')\n", encoding="utf-8")
    (harness / "capability_manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "kind": "global_memory_capability_manifest",
        "script_coverage": {"require_all_harness_scripts": True, "exemptions": []},
        "capabilities": [
            {
                "id": "task_lifecycle",
                "title": "Task lifecycle tooling",
                "status": "optional",
                "release_scope": False,
                "boundary": "Test boundary",
                "external_story": "Test external story",
                "scripts": ["scripts/existing.py"],
            }
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (docs / "scripts-registry.md").write_text(
        "# Scripts Registry\n\n"
        "## 3. Manual 治理脚本（无自动触发）\n\n"
        "| 脚本 | 用途 | 触发方 | 失败动作 |\n"
        "|---|---|---|---|\n"
        "| `scripts/existing.py` | 现有脚本 | Manual | REPORT |\n"
        "\n---\n",
        encoding="utf-8",
    )
    (docs / "capabilities.md").write_text("# capabilities\n\ncapability:task_lifecycle\n", encoding="utf-8")
    (root / "README.md").write_text("2 个 harness 脚本\n", encoding="utf-8")
    return root


def snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def run_cli(module, args: list[str]):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = module.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def test_dry_run_outputs_json_preview_and_does_not_write(tmp_path):
    module = load_register_script()
    root = make_repo(tmp_path)
    before = snapshot_tree(root)

    code, out, err = run_cli(module, [
        "scripts/new_tool.py",
        "--capability", "task_lifecycle",
        "--purpose", "新工具登记测试",
        "--trigger", "Manual",
        "--failure", "REPORT",
        "--repo-root", str(root),
        "--json",
    ])

    assert code == 0, err
    payload = json.loads(out)
    assert payload["dry_run"] is True
    assert payload["would_change"] is True
    assert sorted(payload["changed_files"]) == [
        "docs/scripts-registry.md",
        "harness/capability_manifest.json",
    ]
    assert any(action["kind"] == "manifest_add_script" for action in payload["actions"])
    assert any(action["kind"] == "registry_add_row" for action in payload["actions"])
    assert snapshot_tree(root) == before


def test_apply_adds_script_to_registry_and_capability_manifest(tmp_path):
    module = load_register_script()
    root = make_repo(tmp_path)

    code, out, err = run_cli(module, [
        "scripts/new_tool.py",
        "--capability", "task_lifecycle",
        "--purpose", "新工具登记测试",
        "--trigger", "Manual",
        "--failure", "REPORT",
        "--repo-root", str(root),
        "--apply",
        "--json",
    ])

    assert code == 0, err
    payload = json.loads(out)
    assert payload["dry_run"] is False
    manifest = json.loads((root / "harness" / "capability_manifest.json").read_text(encoding="utf-8"))
    scripts = manifest["capabilities"][0]["scripts"]
    assert scripts == ["scripts/existing.py", "scripts/new_tool.py"]
    registry = (root / "docs" / "scripts-registry.md").read_text(encoding="utf-8")
    assert "| `scripts/new_tool.py` | 新工具登记测试 | Manual | REPORT |" in registry
    assert set(payload["changed_files"]) == {"docs/scripts-registry.md", "harness/capability_manifest.json"}


def test_repeated_register_is_idempotent_without_duplicate_entries(tmp_path):
    module = load_register_script()
    root = make_repo(tmp_path)
    args = [
        "scripts/new_tool.py",
        "--capability", "task_lifecycle",
        "--purpose", "新工具登记测试",
        "--trigger", "Manual",
        "--failure", "REPORT",
        "--repo-root", str(root),
        "--apply",
        "--json",
    ]

    first = run_cli(module, args)
    second = run_cli(module, args)

    assert first[0] == 0, first[2]
    assert second[0] == 0, second[2]
    second_payload = json.loads(second[1])
    assert second_payload["would_change"] is False
    manifest = json.loads((root / "harness" / "capability_manifest.json").read_text(encoding="utf-8"))
    assert manifest["capabilities"][0]["scripts"].count("scripts/new_tool.py") == 1
    registry = (root / "docs" / "scripts-registry.md").read_text(encoding="utf-8")
    assert registry.count("`scripts/new_tool.py`") == 1


def test_invalid_capability_missing_script_and_escape_path_fail_without_writes(tmp_path):
    module = load_register_script()
    root = make_repo(tmp_path)
    cases = [
        ["scripts/new_tool.py", "--capability", "missing_capability"],
        ["scripts/missing.py", "--capability", "task_lifecycle"],
        ["../outside.py", "--capability", "task_lifecycle"],
    ]

    for extra in cases:
        before = snapshot_tree(root)
        args = extra + [
            "--purpose", "bad",
            "--trigger", "Manual",
            "--failure", "REPORT",
            "--repo-root", str(root),
            "--apply",
            "--json",
        ]
        code, out, err = run_cli(module, args)
        assert code != 0
        payload = json.loads(out)
        assert payload["error"]
        assert snapshot_tree(root) == before


def test_missing_registry_anchor_fails_without_writes(tmp_path):
    module = load_register_script()
    root = make_repo(tmp_path)
    registry = root / "docs" / "scripts-registry.md"
    registry.write_text("# Scripts Registry\n\n## Other Section\n\nno table here\n", encoding="utf-8")
    before = snapshot_tree(root)

    code, out, err = run_cli(module, [
        "scripts/new_tool.py",
        "--capability", "task_lifecycle",
        "--purpose", "新工具登记测试",
        "--trigger", "Manual",
        "--failure", "REPORT",
        "--repo-root", str(root),
        "--apply",
        "--json",
    ])

    assert code != 0
    payload = json.loads(out)
    assert "registry heading not found" in payload["error"]
    assert snapshot_tree(root) == before


def test_registered_fixture_passes_existing_drift_checkers_with_monkeypatched_roots(tmp_path, monkeypatch):
    module = load_register_script()
    root = make_repo(tmp_path)
    code, out, err = run_cli(module, [
        "scripts/new_tool.py",
        "--capability", "task_lifecycle",
        "--purpose", "新工具登记测试",
        "--trigger", "Manual",
        "--failure", "REPORT",
        "--repo-root", str(root),
        "--apply",
        "--json",
    ])
    assert code == 0, err

    scan = load_module(SCAN_ORPHAN, "scan_orphan_for_register_test")
    monkeypatch.setattr(scan, "HARNESS_DIR", root / "harness")
    scan_stdout = io.StringIO()
    with redirect_stdout(scan_stdout):
        scan_code = scan.main([
            "--root", str(root / "harness"),
            "--registry", str(root / "docs" / "scripts-registry.md"),
            "--strict",
            "--json",
        ])
    scan_payload = json.loads(scan_stdout.getvalue())
    assert scan_code == 0
    assert scan_payload["unregistered"] == []
    assert scan_payload["stale_in_registry"] == []

    check = load_module(CHECK_CAPABILITY, "check_capability_for_register_test")
    monkeypatch.setattr(check, "HARNESS_DIR", root / "harness")
    monkeypatch.setattr(check, "REPO_DIR", root)
    monkeypatch.setattr(check, "CAPABILITIES_DOC_PATH", root / "docs" / "capabilities.md")
    monkeypatch.setattr(check, "README_PATH", root / "README.md")
    report = check.build_report(root / "harness" / "capability_manifest.json")
    assert report["coverage"]["unassigned"] == []
    assert not [item for item in report["findings"] if item["code"] == "missing_script"]
