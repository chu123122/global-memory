"""Tests for semantic corpus frontmatter/chunk helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from harness.semantic.corpus import authority_for_path, normalize_relative_path, parse_markdown_document, scan_corpus
from harness.semantic.sources import SourceDefinition, scan_source_files, source_rel_path


class SemanticCorpusTests(unittest.TestCase):
    def test_nested_trigger_frontmatter_is_preserved_as_metadata(self) -> None:
        text = """---
description: 审查规则
trigger:
  keywords: [审查, 改代码]
  tags: [review, rule]
---
# Root

Body.
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "agents" / "CLAUDE.md"
            path.parent.mkdir()
            path.write_text(text, encoding="utf-8")
            doc = parse_markdown_document(root, path)
        self.assertEqual(doc.description, "审查规则")
        self.assertEqual(doc.keywords, ["审查", "改代码"])
        self.assertEqual(doc.tags, ["review", "rule"])
        self.assertNotIn("审查", doc.chunks[0].embedding_text)
        self.assertEqual(doc.chunks[0].metadata_keywords, ["审查", "改代码"])


    def test_scan_corpus_is_recursive_and_skips_deprecated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "docs" / "spec" / "RULE_ENFORCEMENT_MATRIX.md"
            nested.parent.mkdir(parents=True)
            nested.write_text("# Rule Matrix\n", encoding="utf-8")
            deprecated = root / "feedback" / "old.md"
            deprecated.parent.mkdir()
            deprecated.write_text("---\nstatus: deprecated\n---\n# Old\n", encoding="utf-8")
            docs = scan_corpus(root)
        self.assertIn("docs/spec/RULE_ENFORCEMENT_MATRIX.md", [doc.rel_path for doc in docs])
        self.assertNotIn("feedback/old.md", [doc.rel_path for doc in docs])

    def test_scan_corpus_supports_explicit_source_include_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            memory_root = Path(td) / "memory"
            source_root = Path(td) / "external"
            (source_root / "keep").mkdir(parents=True)
            (source_root / "skip").mkdir()
            (source_root / "keep" / "a.md").write_text("# A\n", encoding="utf-8")
            (source_root / "skip" / "b.md").write_text("# B\n", encoding="utf-8")
            source = SourceDefinition(
                id="tmp-source",
                root=source_root,
                enabled=True,
                source_type="external_docs",
                priority=50,
                include=("**/*.md",),
                exclude=("skip/**",),
            )
            docs = scan_corpus(memory_root, sources=[source])
        self.assertEqual([doc.rel_path for doc in docs], ["tmp-source:keep/a.md"])
        self.assertEqual(docs[0].source_id, "tmp-source")
        self.assertEqual(docs[0].source_rel_path, "keep/a.md")


    def test_claude_tasks_source_scans_core_docs_and_excludes_noise(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "ClaudeTasks"
            keep = root / "active" / "ai-quality-gate" / "core" / "HANDOFF.md"
            keep.parent.mkdir(parents=True)
            keep.write_text("# Handoff\n", encoding="utf-8")
            status = root / "active" / "ai-quality-gate" / "core" / "STATUS.md"
            status.write_text("# Status\n", encoding="utf-8")
            noisy_paths = [
                root / "active" / "ai-quality-gate" / "reference" / "notes.md",
                root / "active" / "ai-quality-gate" / "node_modules" / "pkg" / "README.md",
                root / "active" / "ai-quality-gate" / "unity-project" / "README.md",
                root / "active" / "backup-old" / "core" / "HANDOFF.md",
            ]
            for path in noisy_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Noise\n", encoding="utf-8")
            source = SourceDefinition(
                id="claude-tasks",
                root=root,
                enabled=True,
                source_type="task_docs",
                priority=60,
                include=("active/*/**/*.md",),
                exclude=("**/reference/**", "**/node_modules/**", "**/unity-project/**", "**/backup-*", "**/backup-*/**"),
            )
            files = scan_source_files([source])
        self.assertEqual([item.source_rel_path for item in files], [
            "active/ai-quality-gate/core/HANDOFF.md",
            "active/ai-quality-gate/core/STATUS.md",
        ])
        self.assertEqual(source_rel_path(source, keep), "active/ai-quality-gate/core/HANDOFF.md")

    def test_authority_mapping_includes_agents_as_t1(self) -> None:
        self.assertEqual(authority_for_path("rules/x.md").tier, "T1")
        self.assertEqual(authority_for_path("agents/CLAUDE.md").tier, "T1")
        self.assertEqual(authority_for_path("AGENTS.md").tier, "T1")
        self.assertEqual(authority_for_path("feedback/x.md").tier, "T2")
        self.assertEqual(authority_for_path("knowledge/x.md").tier, "T3")
        self.assertEqual(authority_for_path("docs/x.md").tier, "T4")

    def test_output_path_must_be_memory_root_relative(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inside = root / "docs" / "x.md"
            inside.parent.mkdir()
            inside.write_text("# X\n", encoding="utf-8")
            self.assertEqual(normalize_relative_path(root, inside), "docs/x.md")
            with self.assertRaises(ValueError):
                normalize_relative_path(root, root.parent / "outside.md")
            with self.assertRaises(ValueError):
                normalize_relative_path(root, Path("../escape.md"))


if __name__ == "__main__":
    unittest.main()
