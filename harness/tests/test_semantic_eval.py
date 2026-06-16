"""Tests for semantic eval metrics."""
from __future__ import annotations

import unittest

from harness.semantic.eval import evaluate_cases, evaluate_negative_cases, run_eval


class SemanticEvalMetricTests(unittest.TestCase):
    def test_recall_and_mrr_use_expected_paths(self) -> None:
        cases = [
            {"id": "g1", "query": "q1", "expect_paths": ["rules/a.md"]},
            {"id": "g2", "query": "q2", "expect_paths": ["docs/b.md"]},
        ]
        results = {
            "g1": [{"path": "x.md"}, {"path": "rules/a.md"}],
            "g2": [{"path": "docs/b.md"}],
        }
        metrics = evaluate_cases(cases, results)
        self.assertEqual(metrics["caseCount"], 2)
        self.assertEqual(metrics["Recall@5"], 1.0)
        self.assertEqual(metrics["Recall@10"], 1.0)
        self.assertAlmostEqual(metrics["MRR"], (1 / 2 + 1 / 1) / 2)

    def test_miss_lowers_recall_and_mrr(self) -> None:
        cases = [{"id": "g1", "query": "q1", "expect_paths": ["rules/a.md"]}]
        metrics = evaluate_cases(cases, {"g1": [{"path": "docs/other.md"}]})
        self.assertEqual(metrics["Recall@5"], 0.0)
        self.assertEqual(metrics["Recall@10"], 0.0)
        self.assertEqual(metrics["MRR"], 0.0)


    def test_eval_calibrates_absolute_gate_and_records_negative_rejections(self) -> None:
        golden = [{"id": "g", "query": "q", "expect_paths": ["rules/good.md"]}]
        negative = [{"id": "n", "query": "weather"}]
        calls = {
            ("q", 50): [
                {
                    "path": "rules/good.md",
                    "signals": {"evidence_class": "both", "raw_rrf": 0.01, "raw_bm25": 9.0, "raw_cosine": 0.6, "lexical_token_count": 2, "content_token_count": 2, "channel_ranks": {"bm25": 1, "vector": 1}},
                }
            ],
            ("weather", 50): [
                {
                    "path": "docs/noise.md",
                    "signals": {"evidence_class": "lexical_only", "raw_rrf": 0.99, "base_relevance": 1.0, "raw_bm25": 9.0, "raw_cosine": None, "lexical_token_count": 1, "content_token_count": 1, "channel_ranks": {"bm25": 1}},
                }
            ],
        }

        def query_fn(query: str, top: int):
            return calls[(query, top)]

        # Use run_eval's query_fn branch only for metric smoke; direct calibration is covered by run_eval integration below.
        from harness.semantic.calibration import calibrate_from_results, accepted_rows, annotate_rows

        calibrated = calibrate_from_results(golden, {"g": calls[("q", 50)]}, negative, {"n": calls[("weather", 50)]})
        self.assertFalse(calibrated.policy["uses_normalized_base_relevance"])
        accepted_neg = accepted_rows(calls[("weather", 50)], calibrated.config)
        self.assertEqual(accepted_neg, [])
        annotated = annotate_rows(calls[("weather", 50)], calibrated.config)
        self.assertFalse(annotated[0]["accepted"])
        self.assertIn("reject_reason", annotated[0])
        self.assertIn("selected", calibrated.policy)

    def test_run_eval_output_records_policy_and_raw_negative_signals(self) -> None:
        import json
        import sqlite3
        import tempfile
        from pathlib import Path
        from unittest import mock

        golden = [{"id": "g", "query": "q", "expect_paths": ["rules/good.md"]}]
        negative = [{"id": "n", "query": "weather"}]
        calls = {
            "q": [
                {
                    "path": "rules/good.md",
                    "signals": {
                        "evidence_class": "both",
                        "raw_rrf": 0.01,
                        "base_relevance": 1.0,
                        "raw_bm25": 9.0,
                        "raw_cosine": 0.6,
                        "lexical_token_count": 2,
                        "content_token_count": 2,
                        "channel_ranks": {"bm25": 1, "vector": 1},
                    },
                }
            ],
            "weather": [
                {
                    "path": "docs/noise.md",
                    "signals": {
                        "evidence_class": "both",
                        "raw_rrf": 0.99,
                        "base_relevance": 1.0,
                        "raw_bm25": 9.0,
                        "raw_cosine": 0.6,
                        "lexical_token_count": 1,
                        "content_token_count": 1,
                        "channel_ranks": {"bm25": 1, "vector": 1},
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as td:
            index_path = Path(td) / "idx.sqlite"
            conn = sqlite3.connect(index_path)
            conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("CREATE TABLE chunks (chunk_id TEXT)")
            conn.execute("CREATE VIRTUAL TABLE fts5 USING fts5(chunk_id)")
            conn.execute("CREATE VIEW fts AS SELECT rowid, chunk_id FROM fts5")
            conn.execute("CREATE TABLE vectors (chunk_id TEXT)")
            conn.execute("CREATE TABLE token_df (token TEXT PRIMARY KEY, doc_freq INTEGER NOT NULL, chunk_count INTEGER NOT NULL, df_ratio REAL NOT NULL)")
            conn.commit()
            conn.close()

            def fake_query(query: str, **_kwargs):
                return calls[query]

            with mock.patch("harness.semantic.engine.query_index", side_effect=fake_query):
                result = run_eval(index_path=index_path, query_fn=None, with_baseline=False, save_policy=True) if False else None
            # Patch load_fixture and query_index at run_eval import boundary.
            with mock.patch("harness.semantic.eval.load_fixture", side_effect=[golden, negative]), \
                mock.patch("harness.semantic.engine.query_index", side_effect=fake_query):
                result = run_eval(index_path=index_path, save_policy=True)

            self.assertEqual(result["negative"]["falsePositiveRate"], 0.0)
            self.assertIn("selected", result["acceptancePolicy"])
            raw_negative = result["details"]["negative"]["n"]["raw"][0]
            self.assertFalse(raw_negative["accepted"])
            self.assertEqual(raw_negative["reject_reason"], "min_lexical_tokens")
            self.assertEqual(raw_negative["signals"]["raw_bm25"], 9.0)
            conn = sqlite3.connect(index_path)
            saved = json.loads(conn.execute("SELECT value FROM meta WHERE key='acceptance_policy'").fetchone()[0])
            conn.close()
            self.assertEqual(saved["selected"], result["acceptancePolicy"]["selected"])

    def test_negative_false_positive_rate(self) -> None:
        cases = [
            {"id": "n1", "query": "weather"},
            {"id": "n2", "query": "stock"},
        ]
        results = {"n1": [], "n2": [{"path": "rules/a.md", "score": 0.2}]}
        metrics = evaluate_negative_cases(cases, results)
        self.assertEqual(metrics["caseCount"], 2)
        self.assertEqual(metrics["falsePositiveCount"], 1)
        self.assertEqual(metrics["falsePositiveRate"], 0.5)


if __name__ == "__main__":
    unittest.main()
