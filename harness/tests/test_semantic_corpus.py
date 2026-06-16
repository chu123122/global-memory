"""Tests for semantic corpus frontmatter/chunk helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from harness.semantic.corpus import authority_for_path, normalize_relative_path, parse_markdown_document, scan_corpus


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
