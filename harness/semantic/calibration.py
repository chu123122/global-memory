"""Acceptance gate calibration for semantic retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from harness.semantic.query import AcceptanceConfig, EvidenceThreshold


@dataclass(frozen=True)
class CalibrationResult:
    config: AcceptanceConfig
    policy: dict[str, object]


DEFAULT_POLICY = {
    "kind": "absolute_signal_by_evidence_class",
    "selection": "grid_search_maximize_recall_then_minimize_negative_fpr",
    "notes": "v1 heuristic policy: stop tokens and threshold grid are manually seeded; token_df high-DF filtering is the data-derived guardrail.",
    "uses_normalized_base_relevance": False,
    "threshold_grid": {
        "min_bm25_score": [0.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0, 20.0],
        "min_vector_score": [0.0, 0.55, 0.57, 0.60, 0.62, 0.65],
        "min_lexical_tokens": [0, 1, 2, 3],
    },
}


def default_acceptance_config() -> AcceptanceConfig:
    # Conservative v1 heuristic policy until M4 calibration persists a tuned one.
    return AcceptanceConfig(
        {
            "both": EvidenceThreshold(min_bm25_score=5.0, min_vector_score=0.55, min_lexical_tokens=2),
            "lexical_only": EvidenceThreshold(min_bm25_score=12.0, min_lexical_tokens=2),
            "vector_only": EvidenceThreshold(),
        },
        disabled_evidence_classes=frozenset({"vector_only"}),
    )


def acceptance_config_from_policy(policy: Mapping[str, object]) -> AcceptanceConfig:
    selected = policy.get("selected")
    if not isinstance(selected, Mapping):
        return default_acceptance_config()
    thresholds: dict[str, EvidenceThreshold] = {}
    for evidence, value in selected.items():
        if not isinstance(value, Mapping):
            continue
        thresholds[str(evidence)] = EvidenceThreshold(
            min_bm25_score=_optional_float(value.get("min_bm25_score")),
            min_vector_score=_optional_float(value.get("min_vector_score")),
            min_lexical_tokens=int(value.get("min_lexical_tokens") or 0),
            max_bm25_rank=_optional_int(value.get("max_bm25_rank")),
            max_vector_rank=_optional_int(value.get("max_vector_rank")),
        )
    disabled = {
        str(evidence)
        for evidence, value in selected.items()
        if isinstance(value, Mapping) and value.get("enabled") is False
    }
    return AcceptanceConfig(thresholds, disabled_evidence_classes=frozenset(disabled)) if thresholds else default_acceptance_config()


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _case_hit(rows: Sequence[Mapping[str, object]], expected: set[str], top: int) -> bool:
    return any(str(row.get("path") or "") in expected for row in rows[:top])


def _false_positive(rows: Sequence[Mapping[str, object]]) -> bool:
    return bool(rows)


def row_rejection_reason(row: Mapping[str, object], config: AcceptanceConfig) -> str:
    signals = row.get("signals", {}) if isinstance(row.get("signals"), dict) else {}
    evidence = str(signals.get("evidence_class") or "")
    threshold = config.by_evidence.get(evidence)
    if threshold is None:
        return f"evidence_class_disabled:{evidence}"
    if evidence in config.disabled_evidence_classes:
        return f"evidence_class_disabled:{evidence}"
    raw_bm25 = signals.get("raw_bm25")
    raw_cosine = signals.get("raw_cosine")
    ranks = signals.get("channel_ranks", {}) if isinstance(signals.get("channel_ranks"), dict) else {}
    if threshold.min_lexical_tokens:
        token_count = signals.get("lexical_token_count")
        if token_count is None or int(token_count) < threshold.min_lexical_tokens:
            return "min_lexical_tokens"
        content_count = signals.get("content_token_count")
        if content_count is None or int(content_count) < threshold.min_lexical_tokens:
            return "min_content_tokens"
    if threshold.min_bm25_score is not None and (raw_bm25 is None or float(raw_bm25) < threshold.min_bm25_score):
        return "min_bm25_score"
    if threshold.min_vector_score is not None and (raw_cosine is None or float(raw_cosine) < threshold.min_vector_score):
        return "min_vector_score"
    if threshold.max_bm25_rank is not None and (ranks.get("bm25") is None or int(ranks.get("bm25")) > threshold.max_bm25_rank):
        return "max_bm25_rank"
    if threshold.max_vector_rank is not None and (ranks.get("vector") is None or int(ranks.get("vector")) > threshold.max_vector_rank):
        return "max_vector_rank"
    return ""


def annotate_rows(rows: Sequence[Mapping[str, object]], config: AcceptanceConfig) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        copied = dict(row)
        reason = row_rejection_reason(copied, config)
        copied["accepted"] = reason == ""
        copied["reject_reason"] = reason
        out.append(copied)
    return out


def accepted_rows(rows: Sequence[Mapping[str, object]], config: AcceptanceConfig) -> list[dict[str, object]]:
    return [row for row in annotate_rows(rows, config) if row.get("accepted")]


def calibrate_from_results(
    golden_cases: Sequence[Mapping[str, object]],
    golden_raw: Mapping[str, Sequence[Mapping[str, object]]],
    negative_cases: Sequence[Mapping[str, object]],
    negative_raw: Mapping[str, Sequence[Mapping[str, object]]],
) -> CalibrationResult:
    """Select a simple absolute-signal policy from fixture raw candidates.

    This keeps one generic threshold set per evidence class. It does not use
    normalized base_relevance and does not special-case individual queries.
    """
    candidates: list[AcceptanceConfig] = []
    bm25_grid = DEFAULT_POLICY["threshold_grid"]["min_bm25_score"]  # type: ignore[index]
    vec_grid = DEFAULT_POLICY["threshold_grid"]["min_vector_score"]  # type: ignore[index]
    lexical_token_grid = DEFAULT_POLICY["threshold_grid"]["min_lexical_tokens"]  # type: ignore[index]
    for both_bm25 in bm25_grid:
        for both_vec in vec_grid:
            for min_tokens in lexical_token_grid:
                candidates.append(
                    AcceptanceConfig(
                        {
                            "both": EvidenceThreshold(
                                min_bm25_score=float(both_bm25),
                                min_vector_score=float(both_vec),
                                min_lexical_tokens=int(min_tokens),
                            ),
                            "lexical_only": EvidenceThreshold(min_bm25_score=20.0, min_lexical_tokens=3),
                            # No current golden case proves pure semantic vector-only
                            # acceptance, so v1 explicitly disables this class rather
                            # than hiding the decision behind an impossible cosine.
                            "vector_only": EvidenceThreshold(),
                        },
                        disabled_evidence_classes=frozenset({"vector_only"}),
                    )
                )

    from harness.semantic.query import rank_pointers

    def apply_config(rows: Sequence[Mapping[str, object]], config: AcceptanceConfig) -> list[dict[str, object]]:
        return accepted_rows(rows, config)

    best: tuple[float, float, float, float, AcceptanceConfig] | None = None
    for config in candidates:
        recall10 = 0
        recall5 = 0
        for idx, case in enumerate(golden_cases):
            case_id = str(case.get("id") or idx)
            expected = {str(p) for p in case.get("expect_paths", []) if str(p)}  # type: ignore[arg-type]
            accepted = apply_config(golden_raw.get(case_id, []), config)
            recall10 += int(_case_hit(accepted, expected, 10))
            recall5 += int(_case_hit(accepted, expected, 5))
        fp = 0
        for idx, case in enumerate(negative_cases):
            case_id = str(case.get("id") or idx)
            fp += int(_false_positive(apply_config(negative_raw.get(case_id, []), config)))
        total_g = max(len(golden_cases), 1)
        total_n = max(len(negative_cases), 1)
        # Primary contract target: keep Recall@10 >= 0.7 where possible, then
        # minimize negative FPR.  Within equal FPR prefer stricter lexical
        # specificity (content-token count) before recall@5/MRR-friendly laxness.
        recall10_rate = recall10 / total_g
        recall5_rate = recall5 / total_g
        fpr = fp / total_n
        target_met = 1.0 if recall10_rate >= 0.7 else 0.0
        both_threshold = config.by_evidence.get("both", EvidenceThreshold())
        score = (
            target_met,
            -fpr,
            recall10_rate,
            float(both_threshold.min_lexical_tokens),
            float(both_threshold.min_bm25_score or 0),
            recall5_rate,
            -sum((t.min_vector_score or 0) for t in config.by_evidence.values()),
        )
        if best is None or score > best[:4]:
            best = (score[0], score[1], score[2], score[3], config)
    assert best is not None
    config = best[4]
    return CalibrationResult(config=config, policy={**DEFAULT_POLICY, "selected": _config_dict(config)})


def _config_dict(config: AcceptanceConfig) -> dict[str, object]:
    return {
        evidence: {
            "enabled": evidence not in config.disabled_evidence_classes,
            "min_bm25_score": threshold.min_bm25_score,
            "min_vector_score": threshold.min_vector_score,
            "min_lexical_tokens": threshold.min_lexical_tokens,
            "max_bm25_rank": threshold.max_bm25_rank,
            "max_vector_rank": threshold.max_vector_rank,
        }
        for evidence, threshold in sorted(config.by_evidence.items())
    }
