"""Tests for semantic hybrid query ranking."""
from __future__ import annotations

import unittest

from harness.semantic.query import (
    EPSILON,
    AcceptanceConfig,
    EvidenceThreshold,
    ChunkInfo,
    ChannelHit,
    authority_adjust,
    final_score,
    rank_pointers,
    rejection_reason,
    evidence_class_for_channels,
    rrf_scores,
    score_synthetic_candidates,
)


class SemanticQueryRankingTests(unittest.TestCase):
    def test_authority_adjust_is_capped_by_epsilon(self) -> None:
        for tier in ("T1", "T2", "T3", "T4"):
            for evidence in ("both", "lexical_only", "vector_only"):
                base = 0.73
                adjusted = final_score(base, tier, evidence)
                self.assertLessEqual(abs(adjusted - base), EPSILON + 1e-12)
        self.assertEqual(authority_adjust("T1", "both"), EPSILON)
        self.assertEqual(authority_adjust("T4", "both"), 0.0)
        self.assertEqual(authority_adjust("T1", "vector_only"), -0.5 * EPSILON)


    def test_unknown_authority_tier_fails_loud(self) -> None:
        with self.assertRaises(ValueError):
            authority_adjust("TX", "both")

    def test_evidence_class_from_channels_including_metadata(self) -> None:
        self.assertEqual(evidence_class_for_channels({"bm25": ChannelHit("c", "bm25", 1.0)}), "lexical_only")
        self.assertEqual(evidence_class_for_channels({"metadata": ChannelHit("c", "metadata", 1.0)}), "lexical_only")
        self.assertEqual(evidence_class_for_channels({"vector": ChannelHit("c", "vector", 0.9)}), "vector_only")
        self.assertEqual(
            evidence_class_for_channels({"metadata": ChannelHit("c", "metadata", 1.0), "vector": ChannelHit("c", "vector", 0.9)}),
            "both",
        )

    def test_a5_strong_t4_beats_weak_t1_with_numeric_regression_sentinel(self) -> None:
        ranked = score_synthetic_candidates([
            ("t4_strong", 0.80, "T4", "both"),
            ("t1_weak", 0.70, "T1", "both"),
        ])
        self.assertEqual([r.chunk_id for r in ranked], ["t4_strong", "t1_weak"])

    def test_a5_near_t1_beats_t4_by_capped_bonus(self) -> None:
        ranked = score_synthetic_candidates([
            ("t1_near", 0.70, "T1", "both"),
            ("t4_near", 0.72, "T4", "both"),
        ])
        self.assertEqual([r.chunk_id for r in ranked], ["t1_near", "t4_near"])

    def test_a5_multichannel_medium_beats_single_vector_rank_one_noise(self) -> None:
        chunks = {
            "both_medium": ChunkInfo("both_medium", "docs/relevant.md", "T4"),
            "vector_noise": ChunkInfo("vector_noise", "docs/noise.md", "T4"),
        }
        hits = {
            "bm25": [ChannelHit("both_medium", "bm25", 5.0, keyword="审查 改代码")],
            "vector": [
                ChannelHit("vector_noise", "vector", 0.99, vector_source="bge-m3"),
                ChannelHit("filler", "vector", 0.80, vector_source="bge-m3"),
                ChannelHit("both_medium", "vector", 0.70, vector_source="bge-m3"),
            ],
        }
        ranked = rank_pointers(chunks, hits, top_n=2)
        self.assertEqual(ranked[0]["path"], "docs/relevant.md")
        self.assertEqual(ranked[1]["path"], "docs/noise.md")

    def test_a5_vector_only_cannot_beat_near_relevant_both(self) -> None:
        ranked = score_synthetic_candidates([
            ("both_near", 0.70, "T4", "both"),
            ("vector_only", 0.72, "T4", "vector_only"),
        ])
        self.assertEqual([r.chunk_id for r in ranked], ["both_near", "vector_only"])

    def test_rrf_combines_channels_and_normalizes_by_candidate_max(self) -> None:
        hits = {
            "bm25": [ChannelHit("a", "bm25", 10.0, keyword="审查"), ChannelHit("b", "bm25", 8.0, keyword="审查")],
            "vector": [ChannelHit("b", "vector", 0.92, vector_source="bge-m3"), ChannelHit("a", "vector", 0.90, vector_source="bge-m3")],
        }
        scores = rrf_scores(hits, k=60)
        self.assertGreater(scores["a"].base_relevance, 0)
        self.assertGreater(scores["b"].base_relevance, 0)
        self.assertLessEqual(scores["a"].base_relevance, 1.0)
        self.assertLessEqual(scores["b"].base_relevance, 1.0)
        self.assertAlmostEqual(max(s.base_relevance for s in scores.values()), 1.0)
        self.assertEqual(scores["a"].evidence_class, "both")

    def test_vector_only_disabled_is_explicit_not_impossible_threshold(self) -> None:
        score = rrf_scores({"vector": [ChannelHit("v", "vector", 1.0, vector_source="bge-m3")]})["v"]
        config = AcceptanceConfig({"vector_only": EvidenceThreshold()}, disabled_evidence_classes=frozenset({"vector_only"}))
        self.assertEqual(rejection_reason(score, config), "evidence_class_disabled:vector_only")

    def test_accepted_gate_uses_configured_absolute_raw_signals_not_base(self) -> None:
        chunks = {
            "good": ChunkInfo("good", "agents/CLAUDE.md", "T1"),
            "weak": ChunkInfo("weak", "docs/noise.md", "T4"),
            "vector": ChunkInfo("vector", "docs/vector.md", "T4"),
        }
        hits = {
            "bm25": [
                ChannelHit("weak", "bm25", 4.0, keyword="今天 上海"),
                ChannelHit("good", "bm25", 5.0, keyword="审查 改代码"),
            ],
            "vector": [ChannelHit("vector", "vector", 0.99, vector_source="bge-m3"), ChannelHit("good", "vector", 0.70, vector_source="bge-m3")],
        }
        accepted = rank_pointers(
            chunks,
            hits,
            top_n=3,
            accepted_only=True,
            acceptance_config=AcceptanceConfig({"both": EvidenceThreshold(min_bm25_score=5.0, min_lexical_tokens=2)}),
        )
        self.assertEqual([p["path"] for p in accepted], ["agents/CLAUDE.md"])

    def test_rank_pointers_uses_evidence_class_and_accepted_only_gate(self) -> None:
        chunks = {
            "both_near": ChunkInfo("both_near", "docs/both.md", "T4"),
            "vector_only": ChunkInfo("vector_only", "rules/vector-only.md", "T1"),
        }
        hits = {
            "bm25": [ChannelHit("both_near", "bm25", 10.0, keyword="审查 改代码")],
            "vector": [ChannelHit("vector_only", "vector", 0.99, vector_source="bge-m3"), ChannelHit("both_near", "vector", 0.98, vector_source="bge-m3")],
        }
        ranked = rank_pointers(chunks, hits, top_n=2)
        self.assertEqual(ranked[0]["path"], "docs/both.md")
        self.assertEqual(ranked[1]["path"], "rules/vector-only.md")
        self.assertIn("evidence=vector_only", ranked[1]["why"])
        accepted = rank_pointers(
            chunks,
            hits,
            top_n=2,
            accepted_only=True,
            acceptance_config=AcceptanceConfig({"both": EvidenceThreshold(min_lexical_tokens=2)}),
        )
        self.assertEqual([p["path"] for p in accepted], ["docs/both.md"])



    def test_strong_metadata_can_pass_when_vector_channel_is_weak(self) -> None:
        chunks = {
            "c": ChunkInfo("c", "claude-tasks:active/ai-quality-gate/core/HANDOFF.md", "T3", source_id="claude-tasks", source_type="task_docs", task_id="ai-quality-gate", task_doc_type="handoff", task_state="active"),
        }
        hits = {
            "metadata": [ChannelHit("c", "metadata", 20.0, keyword="task_id:ai-quality-gate ai quality gate")],
            "vector": [ChannelHit("c", "vector", 0.0, vector_source="fake")],
        }
        accepted = rank_pointers(
            chunks,
            hits,
            query="ai-quality-gate 怎么接入",
            top_n=1,
            accepted_only=True,
            acceptance_config=AcceptanceConfig({
                "both": EvidenceThreshold(min_bm25_score=5.0, min_vector_score=0.55, min_lexical_tokens=2),
                "lexical_only": EvidenceThreshold(min_bm25_score=12.0, min_lexical_tokens=2),
            }),
        )
        self.assertEqual([row["path"] for row in accepted], ["claude-tasks:active/ai-quality-gate/core/HANDOFF.md"])

    def test_metadata_rerank_doc_type_task_match_and_changelog_penalty(self) -> None:
        chunks = {
            "change": ChunkInfo("change", "claude-tasks:active/other/ops/CHANGELOG.md", "T3", source_id="claude-tasks", source_type="task_docs", task_id="other", task_doc_type="changelog", task_state="active"),
            "handoff": ChunkInfo("handoff", "claude-tasks:active/ai-quality-gate/core/HANDOFF.md", "T3", source_id="claude-tasks", source_type="task_docs", task_id="ai-quality-gate", task_doc_type="handoff", task_state="active"),
        }
        hits = {"bm25": [ChannelHit("change", "bm25", 10.0, keyword="gate"), ChannelHit("handoff", "bm25", 9.0, keyword="gate")]}
        ranked = rank_pointers(chunks, hits, query="ai-quality-gate 怎么接入", top_n=2, include_signals=True)
        self.assertEqual(ranked[0]["path"], "claude-tasks:active/ai-quality-gate/core/HANDOFF.md")
        trace = ranked[0]["rerank_trace"]
        self.assertEqual(trace["doc_type_boost"], 0.04)
        self.assertEqual(trace["task_match_boost"], 0.05)
        self.assertEqual(trace["source_id"], "claude-tasks")
        self.assertEqual(trace["task_doc_type"], "handoff")
        self.assertEqual(ranked[1]["rerank_trace"]["noisy_doc_penalty"], -0.01)

    def test_metadata_rerank_applies_same_task_penalty_deterministically(self) -> None:
        chunks = {
            "a": ChunkInfo("a", "claude-tasks:active/t/core/HANDOFF.md", "T3", source_id="claude-tasks", source_type="task_docs", task_id="t", task_doc_type="handoff", task_state="active"),
            "b": ChunkInfo("b", "claude-tasks:active/t/core/STATUS.md", "T3", source_id="claude-tasks", source_type="task_docs", task_id="t", task_doc_type="status", task_state="active"),
            "c": ChunkInfo("c", "claude-tasks:active/t/design/Phase2.md", "T3", source_id="claude-tasks", source_type="task_docs", task_id="t", task_doc_type="phase", task_state="active"),
        }
        hits = {"bm25": [ChannelHit("a", "bm25", 10.0, keyword="x"), ChannelHit("b", "bm25", 9.0, keyword="x"), ChannelHit("c", "bm25", 8.0, keyword="x")]}
        ranked = rank_pointers(chunks, hits, query="x", top_n=3, include_signals=True)
        self.assertEqual([row["rerank_trace"]["same_task_penalty"] for row in ranked], [0.0, -0.025, -0.05])

    def test_metadata_rerank_boosts_global_memory_canonical_source(self) -> None:
        chunks = {
            "gm": ChunkInfo("gm", "rules/接入索引.md", "T1", source_id="global-memory", source_type="canonical_memory"),
        }
        ranked = rank_pointers(chunks, {"bm25": [ChannelHit("gm", "bm25", 10.0, keyword="规则")]}, top_n=1, include_signals=True)
        self.assertEqual(ranked[0]["rerank_trace"]["source_boost"], 0.03)

    def test_pointer_output_has_no_body_and_explains_allowed_fields(self) -> None:
        chunks = {
            "c": ChunkInfo("c", "rules/x.md", "T1", summary="x" * 250, text="SECRET BODY MUST NOT LEAK", heading_path="硬边界"),
        }
        hits = {
            "bm25": [ChannelHit("c", "bm25", 3.0, keyword="审查")],
            "vector": [ChannelHit("c", "vector", 0.8, vector_source="bge-m3")],
        }
        pointer = rank_pointers(chunks, hits, top_n=1)[0]
        self.assertEqual(set(pointer), {"path", "why", "score", "summary"})
        self.assertLessEqual(len(pointer["summary"]), 200)
        self.assertNotIn("SECRET BODY", str(pointer))
        self.assertIn("heading=硬边界", pointer["why"])
        self.assertIn("evidence=both", pointer["why"])
        self.assertIn("bm25", pointer["why"])
        self.assertIn("vector", pointer["why"])
        self.assertIn("token=审查", pointer["why"])
        self.assertIn("source=bge-m3", pointer["why"])
        self.assertIn("authority=T1(+0.050)", pointer["why"])
        self.assertNotIn("confidence", str(pointer).lower())


if __name__ == "__main__":
    unittest.main()




