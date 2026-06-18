"""Tests for gm.search backend wrapper."""
from __future__ import annotations

from unittest import mock

from harness.gm_mcp import search as gm_search
from harness.semantic.query import AcceptanceConfig


class _ConfigCapture:
    value = None


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


def test_search_demotes_q2q_intent_matches_to_raw(monkeypatch):
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

    assert result["hit"] is False
    assert result["count"] == 0
    assert "intent_matches" not in result
    assert "suggested_answer_refs" not in result
    assert result["raw"]["intent_matches"][0]["intent"] == "review_readonly"
    assert result["raw"]["suggested_answer_refs"] == ["agents/CLAUDE.md"]
    assert result["confidence"] == 1.0
    assert result["low_confidence"] is False
    assert result["debug"]["deliver_gate"]["intent_matches_demoted_to_raw"] is True


def test_log_summary_includes_only_delivered_pointer_refs():
    result = {
        "hit": True,
        "count": 1,
        "confidence": 0.9,
        "low_confidence": False,
        "pointers": [{"path": "docs/a.md", "summary": "A"}],
        "intent_matches": [{"intent": "x", "paraphrase_id": "x1", "answer_paths": ["rules/a.md"]}],
    }
    summary = gm_search.log_summary(result)
    assert summary["top_refs"] == ["docs/a.md"]
    assert summary["top_ids"] == ["docs/a.md"]
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
