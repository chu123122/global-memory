"""Tests for source registry index stale/sync behavior."""
from __future__ import annotations

import json
import sqlite3

from harness.semantic.cli import main as semantic_cli_main
from harness.semantic.embed import DEFAULT_DIM
from harness.semantic.index import build_index, check_stale, index_status


def _embed(texts: list[str]) -> list[list[float]]:
    return [[0.0] * DEFAULT_DIM for _ in texts]


def test_build_index_detects_dirty_and_removes_deleted_source_files(tmp_path):
    root = tmp_path / "memory"
    docs = root / "docs"
    docs.mkdir(parents=True)
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        f"""
sources:
- id: test-memory
  root: {root.as_posix()}
  enabled: true
  source_type: canonical_memory
  priority: 100
  include:
  - docs/**/*.md
  exclude: []
""",
        encoding="utf-8",
    )
    doc = docs / "a.md"
    doc.write_text("# A\nfirst", encoding="utf-8")
    index = tmp_path / "semantic.sqlite"

    first = build_index(memory_root=root, index_path=index, manifest_path=manifest, embedder=_embed)
    assert first.files_indexed == 1
    assert check_stale(memory_root=root, index_path=index, manifest_path=manifest).ok

    doc.write_text("# A\nsecond", encoding="utf-8")
    dirty = check_stale(memory_root=root, index_path=index, manifest_path=manifest)
    assert dirty.dirty_files == ["test-memory:docs/a.md"]

    second = build_index(memory_root=root, index_path=index, manifest_path=manifest, embedder=_embed)
    assert second.files_indexed == 1
    assert check_stale(memory_root=root, index_path=index, manifest_path=manifest).ok

    doc.unlink()
    stale = check_stale(memory_root=root, index_path=index, manifest_path=manifest)
    assert stale.stale_paths == ["test-memory:docs/a.md"]
    third = build_index(memory_root=root, index_path=index, manifest_path=manifest, embedder=_embed)
    assert third.stale_removed >= 1
    conn = sqlite3.connect(index)
    try:
        assert index_status(conn)["files"] == 0
    finally:
        conn.close()


def test_cli_sources_list_and_check_support_json(tmp_path, capsys):
    root = tmp_path / "memory"
    root.mkdir()
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        f"""
sources:
- id: test-memory
  root: {root.as_posix()}
  enabled: true
  source_type: canonical_memory
  priority: 100
  include:
  - docs/**/*.md
  exclude: []
""",
        encoding="utf-8",
    )
    assert semantic_cli_main(["--memory-root", str(root), "--manifest", str(manifest), "sources", "list", "--json"]) == 0
    listed = capsys.readouterr().out
    assert "test-memory" in listed
    assert semantic_cli_main(["--memory-root", str(root), "--manifest", str(manifest), "sources", "check", "--json"]) == 0
    checked = capsys.readouterr().out
    assert '"ok": true' in checked

def test_claude_tasks_metadata_is_written_to_index(tmp_path):
    task_root = tmp_path / "ClaudeTasks"
    handoff = task_root / "active" / "ai-quality-gate" / "core" / "HANDOFF.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text("# Handoff\nClaude Code Stop hook 候选适配器 Codex 入口", encoding="utf-8")
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        f"""
sources:
- id: claude-tasks
  root: {task_root.as_posix()}
  enabled: true
  source_type: task_docs
  priority: 60
  include:
  - active/*/core/HANDOFF.md
  exclude:
  - '**/reference/**'
""",
        encoding="utf-8",
    )
    index = tmp_path / "semantic.sqlite"
    build_index(memory_root=tmp_path / "memory", index_path=index, manifest_path=manifest, embedder=_embed)
    conn = sqlite3.connect(index)
    try:
        row = conn.execute("SELECT path, metadata_json FROM chunks").fetchone()
        fts_row = conn.execute("SELECT metadata FROM fts5").fetchone()
    finally:
        conn.close()
    assert row[0] == "claude-tasks:active/ai-quality-gate/core/HANDOFF.md"
    metadata = json.loads(row[1])
    assert metadata["source_id"] == "claude-tasks"
    assert metadata["source_type"] == "task_docs"
    assert metadata["task_id"] == "ai-quality-gate"
    assert metadata["task_state"] == "active"
    assert metadata["task_doc_type"] == "handoff"
    assert "task_id:ai-quality-gate" in fts_row[0]
