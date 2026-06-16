"""Tests for semantic read-only query engine."""
from __future__ import annotations

import sqlite3
import unittest
from unittest import mock

from harness.semantic.engine import lexical_hits, metadata_hits, query_index
from harness.semantic.errors import SemanticError
from harness.semantic.query import AcceptanceConfig, EvidenceThreshold, ChunkInfo, ChannelHit


class SemanticEngineTests(unittest.TestCase):
    def test_lexical_hits_add_cjk_ngrams_for_natural_queries(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE VIRTUAL TABLE fts5 USING fts5(chunk_id UNINDEXED, path UNINDEXED, heading_path, text, metadata, lexical, tokenize='unicode61')"
        )
        conn.execute(
            "INSERT INTO fts5(chunk_id,path,heading_path,text,metadata,lexical) VALUES (?,?,?,?,?,?)",
            ("agents/CLAUDE.md#6", "agents/CLAUDE.md", "硬边界", "审查只报告不改代码", "", "审查 改代码 代码"),
        )
        hits = lexical_hits(conn, "审查模式能不能改代码", limit=5)
        self.assertEqual(hits[0].chunk_id, "agents/CLAUDE.md#6")


    def test_lexical_hits_sqlite_query_failure_is_explicit(self) -> None:
        conn = sqlite3.connect(":memory:")
        with self.assertRaises(SemanticError) as ctx:
            lexical_hits(conn, "审查", limit=5)
        self.assertEqual(ctx.exception.error_code, "SQLITE_QUERY_FAILED")

    def test_high_df_token_is_not_acceptance_evidence(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE VIRTUAL TABLE fts5 USING fts5(chunk_id UNINDEXED, path UNINDEXED, heading_path, text, metadata, lexical, tokenize='unicode61')"
        )
        conn.execute("CREATE TABLE token_df (token TEXT PRIMARY KEY, doc_freq INTEGER NOT NULL, chunk_count INTEGER NOT NULL, df_ratio REAL NOT NULL)")
        conn.execute("INSERT INTO token_df(token,doc_freq,chunk_count,df_ratio) VALUES ('审查', 60, 100, 0.60)")
        conn.execute(
            "INSERT INTO fts5(chunk_id,path,heading_path,text,metadata,lexical) VALUES (?,?,?,?,?,?)",
            ("c", "rules/noise.md", "审查", "审查", "", "审查"),
        )
        self.assertEqual(lexical_hits(conn, "审查", limit=5), [])

    def test_debug_query_includes_raw_signals(self) -> None:
        with mock.patch("harness.semantic.engine.open_readonly") as open_mock, \
            mock.patch("harness.semantic.engine.lexical_hits", return_value=[ChannelHit("c", "bm25", 7.5, keyword="审查 改代码")]), \
            mock.patch("harness.semantic.engine.metadata_hits", return_value=[]), \
            mock.patch("harness.semantic.engine.vector_hits", return_value=[ChannelHit("c", "vector", 0.88, vector_source="bge-m3")]), \
            mock.patch("harness.semantic.engine.load_chunk_info", return_value={"c": ChunkInfo("c", "agents/CLAUDE.md", "T1")}):
            conn = mock.Mock()
            open_mock.return_value = conn
            row = query_index("q", debug=True)[0]
        signals = row["signals"]
        self.assertEqual(signals["evidence_class"], "both")
        self.assertEqual(signals["raw_bm25"], 7.5)
        self.assertEqual(signals["raw_cosine"], 0.88)
        self.assertIn("raw_rrf", signals)
        self.assertEqual(signals["channel_ranks"], {"bm25": 1, "vector": 1})

    def test_low_information_tokens_are_not_acceptance_evidence(self) -> None:
        with mock.patch("harness.semantic.engine.open_readonly") as open_mock, \
            mock.patch("harness.semantic.engine.lexical_hits", return_value=[ChannelHit("noise", "bm25", 30.0, keyword="今天 什么")]), \
            mock.patch("harness.semantic.engine.metadata_hits", return_value=[]), \
            mock.patch("harness.semantic.engine.vector_hits", return_value=[ChannelHit("noise", "vector", 0.8, vector_source="bge-m3")]), \
            mock.patch("harness.semantic.engine.load_chunk_info", return_value={"noise": ChunkInfo("noise", "docs/noise.md", "T4")}), \
            mock.patch("harness.semantic.engine.load_acceptance_config", return_value=AcceptanceConfig({"both": EvidenceThreshold(min_bm25_score=1.0, min_lexical_tokens=2)})):
            conn = mock.Mock()
            open_mock.return_value = conn
            self.assertEqual(query_index("今天什么", debug=False), [])
            debug = query_index("今天什么", debug=True)[0]
        self.assertFalse(debug["accepted"])
        self.assertEqual(debug["reject_reason"], "min_content_tokens")
        self.assertEqual(debug["signals"]["content_token_count"], 0)

    def test_query_default_returns_accepted_not_raw_vector_only(self) -> None:
        with mock.patch("harness.semantic.engine.open_readonly") as open_mock, \
            mock.patch("harness.semantic.engine.lexical_hits", return_value=[]) as _lex, \
            mock.patch("harness.semantic.engine.metadata_hits", return_value=[]) as _meta, \
            mock.patch("harness.semantic.engine.vector_hits", return_value=[ChannelHit("v", "vector", 0.99, vector_source="bge-m3")]) as _vec, \
            mock.patch("harness.semantic.engine.load_chunk_info", return_value={"v": ChunkInfo("v", "docs/noise.md", "T4")}) as _chunks:
            conn = mock.Mock()
            open_mock.return_value = conn
            self.assertEqual(query_index("q"), [])
            self.assertEqual(query_index("q", debug=True)[0]["path"], "docs/noise.md")


if __name__ == "__main__":
    unittest.main()
