"""L2 integration tests — I1..I7."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import harness_retrieve as hr  # type: ignore


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    r = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace", env=env,
    )
    return r.returncode, r.stdout, r.stderr


def test_i1_retrieve_cli_under_2s(memory_root, task_root, cache_path):
    """I1: retrieve CLI 单次 <2s（含 spawn 开销）。"""
    t0 = time.perf_counter()
    rc, so, se = _run([
        sys.executable, str(SCRIPTS / "harness_retrieve.py"),
        "--task", "demo-task", "--query", "diff",
        "--memory-root", str(memory_root),
        "--task-root", str(task_root),
        "--cache", str(cache_path),
        "--dry-run", "--benchmark",
    ])
    elapsed = time.perf_counter() - t0
    assert rc == 0, f"stderr={se}"
    assert "schema_version" in so
    assert elapsed < 2.0, f"cli too slow: {elapsed:.2f}s"


def test_i2_retrieve_handles_missing_memory_root(tmp_path, task_root):
    """I2: memory_root 不存在 → 不崩，返回空指针 brief。"""
    brief = hr.retrieve(
        task_name="demo-task", user_msg="diff",
        memory_root=tmp_path / "nonexistent",
        task_root=task_root,
        cache_path=tmp_path / "c.json",
    )
    assert brief.relevant_pointers == []


def test_i3_check_trigger_coverage_runs(memory_root):
    """I3: check_trigger_coverage.py 能跑 + 输出 coverage 行。"""
    rc, so, se = _run([
        sys.executable, str(SCRIPTS / "check_trigger_coverage.py"),
        "--root", str(memory_root),
    ])
    assert rc == 0, f"stderr={se}"
    assert "coverage=" in so


def test_i4_scan_dual_storage_runs():
    """I4: scan_dual_storage 真实跑（信息性），输出 dual_count 行。"""
    rc, so, _ = _run([sys.executable, str(SCRIPTS / "scan_dual_storage.py")])
    assert rc == 0
    assert so.startswith("dual_count=")


def test_i5_add_trigger_writes_proposed(memory_root):
    """I5: add_trigger_metadata 不直接改原文件，只写 .proposed。"""
    target = memory_root / "feedback" / "feedback_notrigger.md"
    target.write_text("# no frontmatter at all\n", encoding="utf-8")
    rc, so, se = _run([
        sys.executable, str(SCRIPTS / "add_trigger_metadata.py"),
        "--root", str(memory_root),
    ])
    assert rc == 0, f"stderr={se}"
    sidecar = target.with_suffix(".md.proposed")
    assert sidecar.exists(), "expected .proposed sidecar"
    orig = target.read_text(encoding="utf-8")
    assert orig == "# no frontmatter at all\n", "original must be untouched"


def test_i6_context_meter_outputs_json():
    """I6: context_meter 输出合法 JSON 含 approx_tokens。"""
    rc, so, _ = _run([sys.executable, str(SCRIPTS / "context_meter.py")])
    assert rc == 0
    data = json.loads(so)
    assert "approx_tokens" in data
    assert isinstance(data["approx_tokens"], int)


def test_i7_legacy_memory_not_loaded(memory_root, task_root, cache_path):
    """I7: MEMORY-LEGACY.md 存在但 retrieve 不应扫它（仅扫 feedback/knowledge/fixes/decisions）。"""
    legacy = memory_root / "MEMORY-LEGACY.md"
    legacy.write_text("---\ndescription: legacy index\n---\nlots of content\n", encoding="utf-8")
    brief = hr.retrieve(
        task_name="demo-task", user_msg="legacy", memory_root=memory_root,
        task_root=task_root, cache_path=cache_path,
    )
    for p in [pp["path"] for pp in brief.relevant_pointers]:
        assert "MEMORY-LEGACY" not in p
