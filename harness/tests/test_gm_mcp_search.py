"""Tests for gm.search backend wrapper."""
from __future__ import annotations

from unittest import mock

import pytest

from harness.gm_mcp import search as gm_search
from harness.semantic.query import AcceptanceConfig


class _ConfigCapture:
    value = None


@pytest.fixture(autouse=True)
def _disable_default_reranker(monkeypatch):
    # Unit tests should not load optional local ML dependencies unless a test opts in explicitly.
    monkeypatch.setenv("GM_SEARCH_RERANKER", "off")
    monkeypatch.setenv("GM_SEARCH_REWRITE", "off")


def test_search_uses_open_debug_semantic_query_and_marks_low_confidence(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])

    def fake_query_index(query, *, index_path, top_n, debug, acceptance_config, query_vector):
        _ConfigCapture.value = acceptance_config
        assert query == "q"
        assert top_n == 2
        assert debug is True
        assert query_vector == [1.0, 0.0]
        return [
            {
                "path": "docs/example.md",
                "summary": "Example",
                "why": "vector",
                "score": 0.1,
                "accepted": False,
                "reject_reason": "would_have_been_filtered",
                "signals": {"raw_cosine": 0.5, "evidence_class": "vector_only"},
            }
        ]

    monkeypatch.setattr(gm_search.semantic_engine, "query_index", fake_query_index)
    result = gm_search.search("q", top=2)

    assert isinstance(_ConfigCapture.value, AcceptanceConfig)
    assert "vector_only" not in _ConfigCapture.value.disabled_evidence_classes
    assert result["abstained"] is True
    assert result["count"] == 0
    assert result["pointers"] == []
    assert result["raw"]["pointers"][0]["low_confidence"] is True
    assert result["raw"]["pointers"][0]["reject_reason"] == "would_have_been_filtered"
    assert result["raw"]["pointers"][0]["rank_score"] == 0.1


def test_search_demotes_q2q_matches_but_exposes_intent_suggested_paths(monkeypatch):
    entry = gm_search.IntentParaphrase(
        intent="review_readonly",
        paraphrase_id="p1",
        query="审查模式能不能改代码",
        source="seed",
        answer_paths=("agents/CLAUDE.md",),
        vector=(1.0, 0.0),
    )
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: (entry,))
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(gm_search.semantic_engine, "query_index", lambda *args, **kwargs: [])

    result = gm_search.search("代码审查时能不能顺手改", top=1, intent_top=1)

    assert result["hit"] is True
    assert result["count"] == 0
    assert "intent_matches" not in result
    assert "suggested_answer_refs" not in result
    assert result["intent_suggested_paths"] == [{
        "intent": "review_readonly",
        "score": 1.0,
        "paraphrase_id": "p1",
        "specificity": "",
        "paths": ["agents/CLAUDE.md"],
        "reason": "q2q_intent_match",
    }]
    assert result["raw"]["intent_matches"][0]["intent"] == "review_readonly"
    assert result["raw"]["suggested_answer_refs"] == ["agents/CLAUDE.md"]
    assert result["confidence"] == 1.0
    assert result["low_confidence"] is False
    assert result["debug"]["deliver_gate"]["intent_matches_demoted_to_raw"] is True


def test_q2q_groups_by_intent_and_keeps_matched_paraphrases(monkeypatch):
    entries = (
        gm_search.IntentParaphrase("same", "p1", "same weak", "seed", ("docs/a.md",), (0.5, 0.0)),
        gm_search.IntentParaphrase("same", "p2", "same strong", "seed", ("docs/a.md",), (1.0, 0.0)),
        gm_search.IntentParaphrase("other", "p3", "other", "seed", ("docs/b.md",), (0.0, 1.0)),
    )
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: entries)

    result = gm_search._q2q_matches("q", [1.0, 0.0], top=3)

    assert [item["intent"] for item in result] == ["same", "other"]
    assert result[0]["paraphrase_id"] == "p2"
    assert result[0]["best_score"] == 1.0
    assert result[0]["avg_top2_score"] == 0.75
    assert [item["paraphrase_id"] for item in result[0]["matched_paraphrases"]] == ["p2", "p1"]


def test_intent_suggestions_keep_specific_intent_near_broad_top1():
    matches = [
        {"intent": "broad", "score": 0.90, "specificity": "broad", "paraphrase_id": "b1", "answer_paths": ["rules/broad.md"]},
        {"intent": "specific", "score": 0.84, "specificity": "", "paraphrase_id": "s1", "answer_paths": ["decisions/specific.md"]},
    ]

    result = gm_search._intent_suggested_paths(matches, top=1, margin=0.08)

    assert [item["intent"] for item in result] == ["broad", "specific"]
    assert result[1]["paths"] == ["decisions/specific.md"]


def test_deliver_gate_marks_intent_paths_hidden_by_pointer_cap():
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 2,
        "confidence": 0.9,
        "low_confidence": False,
        "pointers": [
            {"path": "docs/top.md", "rank_score": 1.0, "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"}},
            {"path": "decisions/hidden.md", "rank_score": 0.8, "signals": {"raw_cosine": 0.85, "evidence_class": "vector_only"}},
        ],
        "intent_matches": [],
        "suggested_answer_refs": ["decisions/hidden.md"],
        "intent_suggested_paths": [{"intent": "x", "paths": ["decisions/hidden.md"]}],
    }, max_delivered_unique_paths=1)

    assert [item["path"] for item in result["pointers"]] == ["docs/top.md"]
    assert result["intent_suggested_paths"][0]["paths"] == ["decisions/hidden.md"]
    assert result["debug"]["deliver_gate"]["intent_paths_hidden_by_pointer_cap"] == ["decisions/hidden.md"]


def test_log_summary_includes_delivered_pointer_refs_and_intent_refs():
    result = {
        "hit": True,
        "count": 1,
        "confidence": 0.9,
        "low_confidence": False,
        "pointers": [{"path": "docs/a.md", "summary": "A"}],
        "intent_suggested_paths": [{"intent": "x", "paths": ["rules/a.md"]}],
    }
    summary = gm_search.log_summary(result)
    assert summary["top_refs"] == ["docs/a.md"]
    assert summary["top_ids"] == ["docs/a.md"]
    assert summary["intent_refs"] == ["rules/a.md"]
    assert "intent x suggests rules/a.md" in summary["returned_summary"]
    assert summary["low_confidence"] is False


def test_lexical_only_pointer_does_not_use_rank_score_as_confidence(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "knowledge/noise.md",
                "summary": "Noise",
                "why": "lexical token=天气",
                "score": 1.0165,
                "accepted": True,
                "reject_reason": "",
                "signals": {"evidence_class": "lexical_only", "raw_cosine": None},
            }
        ],
    )

    result = gm_search.search("天气真不错想出去走走", top=1, intent_top=1)

    pointer = result["raw"]["pointers"][0]
    assert pointer["rank_score"] == 1.0165
    assert pointer["confidence"] == 0.0
    assert pointer["lexical_confidence"] == 1.0
    assert pointer["low_confidence"] is True
    assert result["confidence"] == 0.0
    assert result["low_confidence"] is True
    assert result["abstained"] is True
    assert result["pointers"] == []


def test_threshold_delivers_lowest_retained_true_positive_like_core_decision_guard(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "decisions/decision_irreversible_op_double_guard.md",
                "summary": "Irreversible operations need a double guard",
                "why": "lowest retained true positive",
                "score": 1.0,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.624, "evidence_class": "vector_only"},
            }
        ],
    )

    result = gm_search.search("删除移动写远端这类危险动作为什么要两道确认", top=1, intent_top=1)

    assert gm_search.LOW_CONFIDENCE_THRESHOLD == 0.622
    assert result["low_confidence"] is False
    assert result["abstained"] is False
    assert result["pointers"][0]["path"] == "decisions/decision_irreversible_op_double_guard.md"


def test_threshold_abstains_js_error_like_borderline_noise(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "knowledge/noise.md",
                "summary": "Noise",
                "why": "tester JS error negative pressure case",
                "score": 1.0,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.593, "evidence_class": "vector_only"},
            }
        ],
    )

    result = gm_search.search("JavaScript 报错 TypeError 怎么修", top=1, intent_top=1)

    assert result["low_confidence"] is True
    assert result["abstained"] is True
    assert result["pointers"] == []


def test_threshold_abstains_python_import_error_like_high_negative(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "knowledge/noise.md",
                "summary": "Noise",
                "why": "highest exhaustive negative pressure case",
                "score": 1.0,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.621, "evidence_class": "vector_only"},
            }
        ],
    )

    result = gm_search.search("Python ImportError cannot import name 怎么解决", top=1, intent_top=1)

    assert result["low_confidence"] is True
    assert result["abstained"] is True
    assert result["pointers"] == []


def test_threshold_abstains_docker_permission_like_borderline_noise(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "knowledge/noise.md",
                "summary": "Noise",
                "why": "tester Docker permission negative pressure case",
                "score": 1.0,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.594, "evidence_class": "vector_only"},
            }
        ],
    )

    result = gm_search.search("Docker permission denied 该怎么排查", top=1, intent_top=1)

    assert result["low_confidence"] is True
    assert result["abstained"] is True
    assert result["pointers"] == []


def test_threshold_keeps_highest_observed_negative_abstained(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "agents/design-reviewer.md",
                "summary": "Noise",
                "why": "highest observed negative confidence",
                "score": 1.0,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.583363, "evidence_class": "vector_only"},
            }
        ],
    )

    result = gm_search.search("推荐一款性价比高的显卡", top=1, intent_top=1)

    assert result["low_confidence"] is True
    assert result["abstained"] is True
    assert result["pointers"] == []


def test_deliver_gate_abstains_on_overall_low_confidence():
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 1,
        "confidence": 0.2,
        "low_confidence": True,
        "pointers": [{
            "path": "knowledge/a.md",
            "signals": {"raw_cosine": 0.2, "evidence_class": "vector_only"},
        }],
        "intent_matches": [{"intent": "x", "answer_paths": ["knowledge/a.md"]}],
        "suggested_answer_refs": ["knowledge/a.md"],
    })

    assert result["abstained"] is True
    assert result["abstain_reason"] == "overall_low_confidence"
    assert result["hit"] is False
    assert result["count"] == 0
    assert result["pointers"] == []
    assert "intent_matches" not in result
    assert "suggested_answer_refs" not in result
    assert result["raw"]["pointers"][0]["path"] == "knowledge/a.md"


def test_deliver_gate_deduplicates_same_path_after_confident_search():
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 3,
        "confidence": 0.9,
        "low_confidence": False,
        "pointers": [
            {"path": "knowledge/a.md", "rank_score": 0.8, "signals": {"raw_cosine": 0.8, "evidence_class": "vector_only"}},
            {"path": "knowledge/a.md", "rank_score": 0.9, "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"}},
            {"path": "knowledge/b.md", "rank_score": 0.7, "signals": {"raw_cosine": 0.7, "evidence_class": "both"}},
        ],
        "intent_matches": [],
        "suggested_answer_refs": [],
    })

    assert result["abstained"] is False
    assert [item["path"] for item in result["pointers"]] == ["knowledge/a.md", "knowledge/b.md"]
    assert result["pointers"][0]["rank_score"] == 0.9
    assert result["debug"]["deliver_gate"]["dropped_duplicate_paths"] == 1


def test_deliver_gate_drops_lexical_only_without_vector_evidence():
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 2,
        "confidence": 0.91,
        "low_confidence": False,
        "pointers": [
            {"path": "knowledge/noise.md", "signals": {"raw_cosine": None, "evidence_class": "lexical_only"}},
            {"path": "knowledge/good.md", "signals": {"raw_cosine": 0.91, "evidence_class": "vector_only"}},
        ],
        "intent_matches": [],
        "suggested_answer_refs": [],
    })

    assert result["abstained"] is False
    assert [item["path"] for item in result["pointers"]] == ["knowledge/good.md"]
    assert result["debug"]["deliver_gate"]["dropped_without_vector_evidence"] == 1
    assert result["raw"]["pointers"][0]["path"] == "knowledge/noise.md"


def test_deliver_gate_delivers_confident_vector_results_unchanged():
    pointers = [
        {"path": "knowledge/a.md", "signals": {"raw_cosine": 0.91, "evidence_class": "vector_only"}},
        {"path": "knowledge/b.md", "signals": {"raw_cosine": 0.88, "evidence_class": "both"}},
    ]
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 2,
        "confidence": 0.91,
        "low_confidence": False,
        "pointers": pointers,
        "intent_matches": [{"intent": "x", "score": 0.9, "answer_paths": ["knowledge/a.md"]}],
        "suggested_answer_refs": ["unscored/ref.md"],
    })

    assert result["abstained"] is False
    assert result["abstain_reason"] == ""
    assert result["count"] == 2
    assert result["pointers"] == pointers
    assert "intent_matches" not in result
    assert "suggested_answer_refs" not in result
    assert result["raw"]["intent_matches"] == [{"intent": "x", "score": 0.9, "answer_paths": ["knowledge/a.md"]}]
    assert result["raw"]["suggested_answer_refs"] == ["unscored/ref.md"]


def test_deliver_gate_caps_delivered_unique_paths():
    pointers = [
        {
            "path": f"knowledge/{idx}.md",
            "rank_score": 1.0 - idx * 0.01,
            "signals": {"raw_cosine": 0.9 - idx * 0.01, "evidence_class": "vector_only"},
        }
        for idx in range(7)
    ]
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 7,
        "confidence": 0.9,
        "low_confidence": False,
        "pointers": pointers,
        "intent_matches": [],
        "suggested_answer_refs": [],
    })

    assert result["count"] == 3
    assert len({item["path"] for item in result["pointers"]}) <= 3
    assert [item["path"] for item in result["pointers"]] == [f"knowledge/{idx}.md" for idx in range(3)]
    assert result["debug"]["deliver_gate"]["max_delivered_unique_paths"] == 3
    assert result["debug"]["deliver_gate"]["dropped_by_cap"] == 4
    assert result["debug"]["deliver_gate"]["delivered_unique_paths"] == 3


def test_deliver_gate_cap_preserves_top_three_true_positive_fixture():
    pointers = [
        {"path": "expected/top1.md", "rank_score": 1.00, "signals": {"raw_cosine": 0.91, "evidence_class": "vector_only"}},
        {"path": "expected/top2.md", "rank_score": 0.99, "signals": {"raw_cosine": 0.90, "evidence_class": "vector_only"}},
        {"path": "expected/top3.md", "rank_score": 0.98, "signals": {"raw_cosine": 0.89, "evidence_class": "vector_only"}},
        {"path": "noise/4.md", "rank_score": 0.70, "signals": {"raw_cosine": 0.81, "evidence_class": "vector_only"}},
        {"path": "noise/5.md", "rank_score": 0.69, "signals": {"raw_cosine": 0.80, "evidence_class": "vector_only"}},
        {"path": "noise/6.md", "rank_score": 0.68, "signals": {"raw_cosine": 0.79, "evidence_class": "vector_only"}},
    ]
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 6,
        "confidence": 0.91,
        "low_confidence": False,
        "pointers": pointers,
        "intent_matches": [],
        "suggested_answer_refs": [],
    })

    delivered_paths = {item["path"] for item in result["pointers"]}
    assert {"expected/top1.md", "expected/top2.md", "expected/top3.md"} <= delivered_paths
    assert "noise/4.md" not in delivered_paths
    assert "noise/5.md" not in delivered_paths
    assert "noise/6.md" not in delivered_paths


def test_deliver_gate_demotes_intents_and_suggested_refs_to_raw():
    result = gm_search.apply_deliver_gate({
        "hit": True,
        "count": 1,
        "confidence": 0.9,
        "low_confidence": False,
        "pointers": [
            {"path": "knowledge/good.md", "rank_score": 0.9, "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"}},
        ],
        "intent_matches": [
            {"intent": "good", "score": 0.8, "answer_paths": ["knowledge/good.md"]},
            {"intent": "low", "score": 0.2, "answer_paths": ["knowledge/noise.md"]},
            {"intent": "unscored", "answer_paths": ["knowledge/unscored.md"]},
        ],
        "suggested_answer_refs": ["knowledge/no_score_ref.md"],
    })

    assert "intent_matches" not in result
    assert "suggested_answer_refs" not in result
    assert result["raw"]["intent_matches"] == [
        {"intent": "good", "score": 0.8, "answer_paths": ["knowledge/good.md"]},
        {"intent": "low", "score": 0.2, "answer_paths": ["knowledge/noise.md"]},
        {"intent": "unscored", "answer_paths": ["knowledge/unscored.md"]},
    ]
    assert result["raw"]["suggested_answer_refs"] == ["knowledge/no_score_ref.md"]
    assert result["debug"]["deliver_gate"]["intent_matches_demoted_to_raw"] is True
    assert result["debug"]["deliver_gate"]["demoted_intent_matches"] == 3
    assert result["debug"]["deliver_gate"]["suggested_answer_refs_demoted_to_raw"] is True
    assert result["debug"]["deliver_gate"]["demoted_suggested_answer_refs"] == 1



def test_search_reranker_enabled_path_reorders_candidates_and_reports_diagnostics(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_RERANKER", "sentence-transformers")
    monkeypatch.setenv("GM_SEARCH_RERANK_TOPK", "2")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])

    def fake_query_index(query, *, index_path, top_n, debug, acceptance_config, query_vector):
        assert top_n == 2
        return [
            {
                "path": "docs/retrieval-top.md",
                "summary": "Retrieval top",
                "why": "vector",
                "score": 0.9,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"},
            },
            {
                "path": "docs/reranker-top.md",
                "summary": "Reranker top",
                "why": "vector",
                "score": 0.2,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.8, "evidence_class": "vector_only"},
            },
        ]

    def fake_rerank(query, candidates, *, top_n, config):
        assert top_n == 2
        rows = [dict(candidates[1]), dict(candidates[0])]
        rows[0].update({
            "retrieval_score": 0.2,
            "reranker_enabled": True,
            "reranker_backend": "mock",
            "reranker_model": "mock-model",
            "reranker_score": 5.0,
            "reranker_rank": 1,
            "reranker_latency_ms": 1.0,
            "confidence_calibrated": False,
            "fallback_reason": None,
        })
        rows[1].update({
            "retrieval_score": 0.9,
            "reranker_enabled": True,
            "reranker_backend": "mock",
            "reranker_model": "mock-model",
            "reranker_score": 1.0,
            "reranker_rank": 2,
            "reranker_latency_ms": 1.0,
            "confidence_calibrated": False,
            "fallback_reason": None,
        })
        return rows, {"enabled": True, "backend": "mock", "model": "mock-model", "fallback_reason": None}

    monkeypatch.setattr(gm_search.semantic_engine, "query_index", fake_query_index)
    monkeypatch.setattr(gm_search.semantic_reranker, "rerank_candidates", fake_rerank)

    result = gm_search.search("q", top=2, intent_top=1)

    assert [item["path"] for item in result["pointers"]] == ["docs/reranker-top.md", "docs/retrieval-top.md"]
    assert result["pointers"][0]["rank_score"] == 5.0
    assert result["pointers"][0]["retrieval_score"] == 0.2
    assert result["pointers"][0]["confidence"] == 0.8
    assert result["pointers"][0]["confidence_calibrated"] is False
    assert result["diagnostics"]["reranker"]["enabled"] is True
    assert gm_search.log_summary(result)["reranker"]["backend"] == "mock"


def test_search_reranker_fallback_does_not_claim_enabled(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_RERANKER", "sentence-transformers")
    monkeypatch.setenv("GM_SEARCH_RERANK_TOPK", "1")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "docs/a.md",
                "summary": "A",
                "why": "vector",
                "score": 0.9,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"},
            }
        ],
    )

    def fake_rerank(query, candidates, *, top_n, config):
        row = dict(candidates[0])
        row.update({
            "retrieval_score": 0.9,
            "reranker_enabled": False,
            "reranker_backend": "sentence-transformers",
            "reranker_model": "mock-model",
            "reranker_score": None,
            "reranker_rank": None,
            "reranker_latency_ms": 1.0,
            "confidence_calibrated": False,
            "fallback_reason": "dependency missing",
        })
        return [row], {"enabled": False, "backend": "sentence-transformers", "model": "mock-model", "fallback_reason": "dependency missing"}

    monkeypatch.setattr(gm_search.semantic_reranker, "rerank_candidates", fake_rerank)

    result = gm_search.search("q", top=1, intent_top=1)

    assert result["pointers"][0]["reranker_enabled"] is False
    assert result["pointers"][0]["reranker_score"] is None
    assert result["pointers"][0]["fallback_reason"] == "dependency missing"
    assert result["diagnostics"]["reranker"]["enabled"] is False



def test_search_rewrite_off_preserves_single_query_recall_and_reports_diagnostics(monkeypatch):
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    seen_queries = []

    def fake_query_index(query, *, index_path, top_n, debug, acceptance_config, query_vector):
        seen_queries.append(query)
        return [{
            "path": "docs/a.md",
            "summary": "A",
            "why": "vector",
            "score": 0.9,
            "accepted": True,
            "reject_reason": "",
            "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"},
        }]

    monkeypatch.setattr(gm_search.semantic_engine, "query_index", fake_query_index)

    result = gm_search.search("q", top=1, intent_top=1)

    assert seen_queries == ["q"]
    assert result["pointers"][0]["path"] == "docs/a.md"
    assert result["diagnostics"]["rewrite"]["enabled"] is False
    assert result["diagnostics"]["rewrite"]["fallback_reason"] == "backend_off"
    assert result["diagnostics"]["rewrite"]["query_count"] == 1
    assert result["diagnostics"]["recall"]["per_query_counts"] == [{"query": "q", "count": 1}]


def test_search_mock_rewrite_runs_multiple_queries_and_deduplicates(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_REWRITE", "mock")
    monkeypatch.setenv("GM_SEARCH_REWRITE_MAX_QUERIES", "3")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    seen_queries = []

    def row(path, score, chunk_id=None):
        out = {
            "path": path,
            "summary": path,
            "why": "vector",
            "score": score,
            "accepted": True,
            "reject_reason": "",
            "signals": {"raw_cosine": score, "evidence_class": "vector_only"},
        }
        if chunk_id:
            out["chunk_id"] = chunk_id
        return out

    def fake_query_index(query, *, index_path, top_n, debug, acceptance_config, query_vector):
        seen_queries.append(query)
        if query == "q":
            return [row("docs/a.md", 0.8, "same")]
        if query == "q 规则":
            return [row("docs/a.md", 0.91, "same")]
        return [row("docs/b.md", 0.85, "b")]

    monkeypatch.setattr(gm_search.semantic_engine, "query_index", fake_query_index)

    result = gm_search.search("q", top=5, intent_top=1)

    assert seen_queries == ["q", "q 规则", "q global-memory"]
    assert [item["path"] for item in result["pointers"]] == ["docs/a.md", "docs/b.md"]
    assert result["pointers"][0]["retrieval_score"] == 0.91
    assert result["diagnostics"]["rewrite"]["enabled"] is True
    assert result["diagnostics"]["rewrite"]["fallback_reason"] is None
    assert result["diagnostics"]["rewrite"]["query_count"] == 3
    assert result["diagnostics"]["recall"]["merged_count"] == 2


def test_search_rewrite_backend_failure_falls_back_to_single_query(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_REWRITE", "mock")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    def explode(config):
        raise RuntimeError("boom")

    monkeypatch.setattr(gm_search.semantic_rewrite, "_backend_from_config", explode)
    seen_queries = []

    def fake_query_index(query, *, index_path, top_n, debug, acceptance_config, query_vector):
        seen_queries.append(query)
        return [{
            "path": "docs/a.md",
            "summary": "A",
            "why": "vector",
            "score": 0.9,
            "accepted": True,
            "reject_reason": "",
            "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"},
        }]

    monkeypatch.setattr(gm_search.semantic_engine, "query_index", fake_query_index)

    result = gm_search.search("q", top=1, intent_top=1)

    assert seen_queries == ["q"]
    assert "boom" in result["diagnostics"]["rewrite"]["fallback_reason"]
    assert result["diagnostics"]["rewrite"]["query_count"] == 1


def test_search_reranker_still_uses_original_query_after_rewrite(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_REWRITE", "mock")
    monkeypatch.setenv("GM_SEARCH_REWRITE_MAX_QUERIES", "2")
    monkeypatch.setenv("GM_SEARCH_RERANKER", "sentence-transformers")
    monkeypatch.setenv("GM_SEARCH_RERANK_TOPK", "2")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    def fake_query_index(query, *, index_path, top_n, debug, acceptance_config, query_vector):
        if query == "q":
            return [{
                "path": "docs/original.md",
                "summary": "Original",
                "why": "vector",
                "score": 0.7,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.7, "evidence_class": "vector_only"},
            }]
        return [{
            "path": "docs/expanded.md",
            "summary": "Expanded",
            "why": "vector",
            "score": 0.8,
            "accepted": True,
            "reject_reason": "",
            "signals": {"raw_cosine": 0.8, "evidence_class": "vector_only"},
        }]

    def fake_rerank(query, candidates, *, top_n, config):
        assert query == "q"
        assert {item["path"] for item in candidates} == {"docs/original.md", "docs/expanded.md"}
        rows = [dict(item) for item in candidates if item["path"] == "docs/expanded.md"]
        rows[0].update({
            "retrieval_score": 0.8,
            "reranker_enabled": True,
            "reranker_backend": "mock",
            "reranker_model": "mock-model",
            "reranker_score": 2.0,
            "reranker_rank": 1,
            "reranker_latency_ms": 1.0,
            "confidence_calibrated": False,
            "fallback_reason": None,
        })
        return rows, {"enabled": True, "backend": "mock", "model": "mock-model", "fallback_reason": None}

    monkeypatch.setattr(gm_search.semantic_engine, "query_index", fake_query_index)
    monkeypatch.setattr(gm_search.semantic_reranker, "rerank_candidates", fake_rerank)

    result = gm_search.search("q", top=1, intent_top=1)

    assert result["pointers"][0]["path"] == "docs/expanded.md"
    assert result["diagnostics"]["reranker"]["enabled"] is True
    assert result["diagnostics"]["rewrite"]["query_count"] == 2



def test_interactive_hook_profile_overrides_rerank_budget_and_delivers_above_threshold(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_RERANKER", "sentence-transformers")
    monkeypatch.setenv("GM_SEARCH_RERANK_TOPK", "30")
    monkeypatch.setenv("GM_SEARCH_RERANK_MAX_CHARS", "2000")
    monkeypatch.setenv("GM_SEARCH_RERANK_TIMEOUT_MS", "20000")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    def fake_query_index(query, *, index_path, top_n, debug, acceptance_config, query_vector):
        assert top_n == gm_search.HOOK_RERANK_TOPK
        return [
            {
                "path": f"docs/{idx}.md",
                "summary": f"Doc {idx}",
                "why": "vector",
                "score": 0.9 - idx * 0.01,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.9 - idx * 0.01, "evidence_class": "vector_only"},
            }
            for idx in range(3)
        ]

    def fake_rerank(query, candidates, *, top_n, config):
        assert top_n == gm_search.HOOK_TOP
        assert config.top_k == gm_search.HOOK_RERANK_TOPK
        assert config.max_chars == gm_search.HOOK_RERANK_MAX_CHARS
        assert config.timeout_ms == gm_search.HOOK_RERANK_TIMEOUT_MS
        rows = []
        for rank, candidate in enumerate(candidates[:top_n], start=1):
            row = dict(candidate)
            row.update({
                "retrieval_score": candidate["score"],
                "reranker_enabled": True,
                "reranker_backend": "mock",
                "reranker_model": "mock-model",
                "reranker_score": 5.0 - rank * 0.1,
                "reranker_rank": rank,
                "reranker_latency_ms": 1.0,
                "confidence_calibrated": False,
                "fallback_reason": None,
            })
            rows.append(row)
        return rows, {"enabled": True, "backend": "mock", "model": "mock-model", "fallback_reason": None}

    monkeypatch.setattr(gm_search.semantic_engine, "query_index", fake_query_index)
    monkeypatch.setattr(gm_search.semantic_reranker, "rerank_candidates", fake_rerank)

    result = gm_search.search("hook query", delivery_profile=gm_search.HOOK_DELIVERY_PROFILE)

    assert result["delivery_profile"] == gm_search.HOOK_DELIVERY_PROFILE
    assert result["abstained"] is False
    assert result["count"] == 2
    assert result["debug"]["deliver_gate"]["rerank_abstain_threshold"] == gm_search.HOOK_RERANK_ABSTAIN_THRESHOLD
    assert result["debug"]["deliver_gate"]["best_reranker_score"] == 4.9
    assert result["diagnostics"]["timings"]["q2q_ms"] == 0.0


def test_interactive_hook_profile_pre_rerank_abstains_without_reranker(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_RERANKER", "sentence-transformers")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "docs/noise.md",
                "summary": "Noise",
                "why": "weak vector",
                "score": 0.1,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.2, "evidence_class": "vector_only"},
            }
        ],
    )

    def explode(*args, **kwargs):
        raise AssertionError("reranker should be skipped by cheap pre-gate")

    monkeypatch.setattr(gm_search.semantic_reranker, "rerank_candidates", explode)

    result = gm_search.search("unrelated", delivery_profile=gm_search.HOOK_DELIVERY_PROFILE)

    assert result["abstained"] is True
    assert result["hit"] is False
    assert result["pointers"] == []
    assert result["abstain_reason"].startswith("pre_rerank_raw_cosine_below_threshold")
    assert result["diagnostics"]["reranker"]["skipped"] is True
    assert result["debug"]["deliver_gate"]["reranker_fallback_count"] == 0


def test_interactive_hook_profile_abstains_on_reranker_fallback(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_RERANKER", "sentence-transformers")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "docs/a.md",
                "summary": "A",
                "why": "vector",
                "score": 0.9,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"},
            }
        ],
    )

    def fake_rerank(query, candidates, *, top_n, config):
        row = dict(candidates[0])
        row.update({
            "retrieval_score": 0.9,
            "reranker_enabled": False,
            "reranker_backend": "mock",
            "reranker_model": "mock-model",
            "reranker_score": None,
            "reranker_rank": None,
            "reranker_latency_ms": 1.0,
            "confidence_calibrated": False,
            "fallback_reason": "timeout_ms_exceeded",
        })
        return [row], {"enabled": False, "backend": "mock", "model": "mock-model", "fallback_reason": "timeout_ms_exceeded"}

    monkeypatch.setattr(gm_search.semantic_reranker, "rerank_candidates", fake_rerank)

    result = gm_search.search("q", delivery_profile=gm_search.HOOK_DELIVERY_PROFILE)

    assert result["abstained"] is True
    assert result["hit"] is False
    assert result["pointers"] == []
    assert result["abstain_reason"].startswith("reranker_fallback:")
    assert result["debug"]["deliver_gate"]["reranker_fallback_count"] == 1


def test_interactive_hook_profile_abstains_below_reranker_threshold(monkeypatch):
    monkeypatch.setenv("GM_SEARCH_RERANKER", "sentence-transformers")
    monkeypatch.setattr(gm_search, "_intent_bank_entries", lambda: ())
    monkeypatch.setattr(gm_search.semantic_embed, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr(
        gm_search.semantic_engine,
        "query_index",
        lambda *args, **kwargs: [
            {
                "path": "docs/a.md",
                "summary": "A",
                "why": "vector",
                "score": 0.9,
                "accepted": True,
                "reject_reason": "",
                "signals": {"raw_cosine": 0.9, "evidence_class": "vector_only"},
            }
        ],
    )

    def fake_rerank(query, candidates, *, top_n, config):
        row = dict(candidates[0])
        row.update({
            "retrieval_score": 0.9,
            "reranker_enabled": True,
            "reranker_backend": "mock",
            "reranker_model": "mock-model",
            "reranker_score": 4.0,
            "reranker_rank": 1,
            "reranker_latency_ms": 1.0,
            "confidence_calibrated": False,
            "fallback_reason": None,
        })
        return [row], {"enabled": True, "backend": "mock", "model": "mock-model", "fallback_reason": None}

    monkeypatch.setattr(gm_search.semantic_reranker, "rerank_candidates", fake_rerank)

    result = gm_search.search("q", delivery_profile=gm_search.HOOK_DELIVERY_PROFILE)

    assert result["abstained"] is True
    assert result["hit"] is False
    assert result["pointers"] == []
    assert result["abstain_reason"].startswith("reranker_score_below_threshold:")
    assert result["debug"]["deliver_gate"]["best_reranker_score"] == 4.0
