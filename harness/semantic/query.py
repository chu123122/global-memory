"""RRF and authority-weighted pointer ranking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from harness.semantic.tokens import content_tokens

EPSILON = 0.05
TIER_BONUS = {"T1": EPSILON, "T2": 0.66 * EPSILON, "T3": 0.33 * EPSILON, "T4": 0.0}
VECTOR_ONLY_PENALTY = -0.5 * EPSILON


@dataclass(frozen=True)
class ChannelHit:
    chunk_id: str
    channel: str
    raw_score: float
    keyword: str = ""
    vector_source: str = ""


@dataclass(frozen=True)
class ChunkInfo:
    chunk_id: str
    path: str
    authority_tier: str
    summary: str = ""
    text: str = ""
    heading_path: str = ""
    source_id: str = ""
    source_type: str = ""
    task_id: str = ""
    task_doc_type: str = ""
    task_state: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class FusedScore:
    base_relevance: float
    evidence_class: str
    raw_rrf: float
    channels: dict[str, ChannelHit] = field(default_factory=dict)
    channel_ranks: dict[str, int] = field(default_factory=dict)
    content_token_count: int = 0


@dataclass(frozen=True)
class EvidenceThreshold:
    min_bm25_score: float | None = None
    min_vector_score: float | None = None
    min_lexical_tokens: int = 0
    max_bm25_rank: int | None = None
    max_vector_rank: int | None = None


@dataclass(frozen=True)
class AcceptanceConfig:
    """Configurable gate based on absolute channel signals, calibrated by eval."""

    by_evidence: dict[str, EvidenceThreshold] = field(default_factory=dict)
    disabled_evidence_classes: frozenset[str] = field(default_factory=frozenset)

    @staticmethod
    def default_open() -> "AcceptanceConfig":
        return AcceptanceConfig({
            "both": EvidenceThreshold(),
            "lexical_only": EvidenceThreshold(),
            "vector_only": EvidenceThreshold(),
        })


@dataclass(frozen=True)
class CandidateScore:
    chunk_id: str
    final_score: float
    base_relevance: float
    authority_delta: float
    evidence_class: str


def authority_adjust(tier: str, evidence_class: str, *, epsilon: float = EPSILON) -> float:
    if tier not in TIER_BONUS:
        raise ValueError(f"Unknown authority tier: {tier}")
    scale = epsilon / EPSILON
    if evidence_class == "vector_only":
        return VECTOR_ONLY_PENALTY * scale
    return TIER_BONUS[tier] * scale


def final_score(base_relevance: float, tier: str, evidence_class: str, *, epsilon: float = EPSILON) -> float:
    return base_relevance + authority_adjust(tier, evidence_class, epsilon=epsilon)


def score_synthetic_candidates(
    candidates: Sequence[tuple[str, float, str, str]],
    *,
    epsilon: float = EPSILON,
) -> list[CandidateScore]:
    scored = [
        CandidateScore(
            chunk_id=chunk_id,
            final_score=final_score(base, tier, evidence, epsilon=epsilon),
            base_relevance=base,
            authority_delta=authority_adjust(tier, evidence, epsilon=epsilon),
            evidence_class=evidence,
        )
        for chunk_id, base, tier, evidence in candidates
    ]
    return sorted(scored, key=lambda item: (-item.final_score, item.chunk_id))


def evidence_class_for_channels(channels: Mapping[str, ChannelHit]) -> str:
    has_lexical = "bm25" in channels or "metadata" in channels
    has_vector = "vector" in channels
    if has_lexical and has_vector:
        return "both"
    if has_lexical:
        return "lexical_only"
    if has_vector:
        return "vector_only"
    return "lexical_only"


def rrf_scores(
    channel_hits: Mapping[str, list[ChannelHit]],
    *,
    k: int = 60,
    channel_weights: Mapping[str, float] | None = None,
) -> dict[str, FusedScore]:
    """Return RRF scores normalized by the max candidate RRF into [0, 1]."""
    weights = dict(channel_weights or {})
    raw: dict[str, float] = {}
    channels: dict[str, dict[str, ChannelHit]] = {}
    channel_ranks: dict[str, dict[str, int]] = {}
    for channel, hits in channel_hits.items():
        weight = float(weights.get(channel, 1.0))
        for rank, hit in enumerate(hits, start=1):
            raw[hit.chunk_id] = raw.get(hit.chunk_id, 0.0) + weight / (k + rank)
            channels.setdefault(hit.chunk_id, {})[channel] = hit
            channel_ranks.setdefault(hit.chunk_id, {})[channel] = rank
    if not raw:
        return {}
    max_raw = max(raw.values()) or 1.0
    return {
        chunk_id: FusedScore(
            min(score / max_raw, 1.0),
            evidence_class_for_channels(channels.get(chunk_id, {})),
            score,
            channels.get(chunk_id, {}),
            channel_ranks.get(chunk_id, {}),
        )
        for chunk_id, score in raw.items()
    }


def _trim_summary(summary: str, limit: int = 200) -> str:
    return summary[:limit]


def _why(score: FusedScore, chunk: ChunkInfo, delta: float) -> str:
    parts = [f"path={chunk.path}"]
    if chunk.heading_path:
        parts.append(f"heading={chunk.heading_path}")
    parts.append(f"evidence={score.evidence_class}")
    for channel in sorted(score.channels):
        hit = score.channels[channel]
        if channel == "bm25":
            suffix = f" token={hit.keyword}" if hit.keyword else ""
            parts.append(f"bm25{suffix}")
        elif channel == "metadata":
            suffix = f" field={hit.keyword}" if hit.keyword else ""
            parts.append(f"metadata{suffix}")
        elif channel == "vector":
            source = hit.vector_source or "local-vector"
            parts.append(f"vector source={source}")
        else:
            parts.append(channel)
    parts.append(f"authority={chunk.authority_tier}({delta:+.3f})")
    return "; ".join(parts)



def _lexical_token_count(score: FusedScore) -> int:
    tokens: set[str] = set()
    for channel in ("bm25", "metadata"):
        hit = score.channels.get(channel)
        if hit and hit.keyword:
            for token in hit.keyword.split():
                if token and token != "metadata" and not token.startswith("field="):
                    tokens.add(token)
    return len(tokens)


def _content_token_count(score: FusedScore) -> int:
    tokens: list[str] = []
    for channel in ("bm25", "metadata"):
        hit = score.channels.get(channel)
        if hit and hit.keyword:
            tokens.extend(hit.keyword.replace(":", " ").split())
    return len(content_tokens(tokens))




def _best_lexical_channel(score: FusedScore) -> ChannelHit | None:
    hits = [hit for hit in (score.channels.get("bm25"), score.channels.get("metadata")) if hit is not None]
    if not hits:
        return None
    return max(hits, key=lambda hit: hit.raw_score)


def rejection_reason(score: FusedScore, config: AcceptanceConfig | None = None) -> str:
    """Return empty string when accepted, otherwise a stable rejection reason."""
    if config is None:
        return ""
    if score.evidence_class in config.disabled_evidence_classes:
        return f"evidence_class_disabled:{score.evidence_class}"
    threshold = config.by_evidence.get(score.evidence_class)
    if threshold is None:
        return f"evidence_class_disabled:{score.evidence_class}"
    lexical = _best_lexical_channel(score)
    vector = score.channels.get("vector")
    if threshold.min_lexical_tokens and _lexical_token_count(score) < threshold.min_lexical_tokens:
        return "min_lexical_tokens"
    if threshold.min_lexical_tokens and score.content_token_count < threshold.min_lexical_tokens:
        return "min_content_tokens"
    if threshold.min_bm25_score is not None and (lexical is None or lexical.raw_score < threshold.min_bm25_score):
        return "min_bm25_score"
    if threshold.min_vector_score is not None and (vector is None or vector.raw_score < threshold.min_vector_score):
        lexical_only = config.by_evidence.get("lexical_only")
        if (
            lexical_only is not None
            and lexical is not None
            and (lexical_only.min_bm25_score is None or lexical.raw_score >= lexical_only.min_bm25_score)
            and score.content_token_count >= lexical_only.min_lexical_tokens
            and _lexical_token_count(score) >= lexical_only.min_lexical_tokens
        ):
            return ""
        return "min_vector_score"
    bm25_rank = score.channel_ranks.get("bm25")
    vector_rank = score.channel_ranks.get("vector")
    if threshold.max_bm25_rank is not None and (bm25_rank is None or bm25_rank > threshold.max_bm25_rank):
        return "max_bm25_rank"
    if threshold.max_vector_rank is not None and (vector_rank is None or vector_rank > threshold.max_vector_rank):
        return "max_vector_rank"
    return ""


def is_accepted(score: FusedScore, config: AcceptanceConfig | None = None) -> bool:
    """Return whether a candidate passes the eval-calibrated absolute-signal gate.

    The gate intentionally does not inspect normalized base_relevance because RRF
    max-normalization makes every query's top candidate equal to 1.0.
    """
    return rejection_reason(score, config) == ""

def _evidence_priority(evidence_class: str) -> int:
    return {"both": 0, "lexical_only": 1, "vector_only": 2}.get(evidence_class, 3)


def _signals(score: FusedScore) -> dict[str, object]:
    lexical = _best_lexical_channel(score)
    vector = score.channels.get("vector")
    return {
        "evidence_class": score.evidence_class,
        "raw_rrf": score.raw_rrf,
        "base_relevance": score.base_relevance,
        "raw_bm25": lexical.raw_score if lexical else None,
        "raw_cosine": vector.raw_score if vector else None,
        "lexical_token_count": _lexical_token_count(score),
        "content_token_count": score.content_token_count,
        "channel_ranks": dict(score.channel_ranks),
    }


def acceptance_policy_dict(config: AcceptanceConfig) -> dict[str, object]:
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


SOURCE_TYPE_BOOSTS = {("global-memory", "canonical_memory"): 0.03}
DOC_TYPE_BOOSTS = {
    "handoff": 0.04,
    "status": 0.035,
    "design": 0.035,
    "phase": 0.03,
    "test": 0.015,
    "decision_queue": 0.015,
}
NOISY_DOC_PENALTIES = {"changelog": -0.01}
SAME_TASK_STEP_PENALTY = -0.025
TASK_MATCH_BOOST = 0.05


def _query_hits_task_id(query: str, task_id: str) -> bool:
    return bool(task_id and task_id.lower() in query.lower())


def _rerank_components(query: str, chunk: ChunkInfo) -> dict[str, float]:
    source_boost = SOURCE_TYPE_BOOSTS.get((chunk.source_id, chunk.source_type), 0.0)
    doc_type_boost = DOC_TYPE_BOOSTS.get(chunk.task_doc_type, 0.0)
    noisy_doc_penalty = NOISY_DOC_PENALTIES.get(chunk.task_doc_type, 0.0)
    task_match_boost = TASK_MATCH_BOOST if _query_hits_task_id(query, chunk.task_id) else 0.0
    return {
        "source_boost": source_boost,
        "doc_type_boost": doc_type_boost,
        "task_match_boost": task_match_boost,
        "same_task_penalty": 0.0,
        "noisy_doc_penalty": noisy_doc_penalty,
    }


def _rerank_trace(base_score: float, final_score: float, chunk: ChunkInfo, components: Mapping[str, float]) -> dict[str, object]:
    return {
        "base_score": round(base_score, 6),
        "source_boost": round(float(components.get("source_boost", 0.0)), 6),
        "doc_type_boost": round(float(components.get("doc_type_boost", 0.0)), 6),
        "task_match_boost": round(float(components.get("task_match_boost", 0.0)), 6),
        "same_task_penalty": round(float(components.get("same_task_penalty", 0.0)), 6),
        "noisy_doc_penalty": round(float(components.get("noisy_doc_penalty", 0.0)), 6),
        "final_score": round(final_score, 6),
        "source_id": chunk.source_id,
        "source_type": chunk.source_type,
        "task_id": chunk.task_id,
        "task_doc_type": chunk.task_doc_type,
        "task_state": chunk.task_state,
    }


def rank_pointers(
    chunks: Mapping[str, ChunkInfo],
    channel_hits: Mapping[str, list[ChannelHit]],
    *,
    query: str = "",
    top_n: int = 5,
    k: int = 60,
    channel_weights: Mapping[str, float] | None = None,
    authority_epsilon: float = EPSILON,
    accepted_only: bool = False,
    acceptance_config: AcceptanceConfig | None = None,
    include_signals: bool = False,
) -> list[dict[str, object]]:
    fused = rrf_scores(channel_hits, k=k, channel_weights=channel_weights)
    for score in fused.values():
        score.content_token_count = _content_token_count(score)
    rows: list[dict[str, object]] = []
    for chunk_id, score in fused.items():
        chunk = chunks.get(chunk_id)
        if chunk is None:
            continue
        reason = rejection_reason(score, acceptance_config)
        accepted = reason == ""
        if accepted_only and not accepted:
            continue
        delta = authority_adjust(chunk.authority_tier, score.evidence_class, epsilon=authority_epsilon)
        base_score = score.base_relevance + delta
        components = _rerank_components(query, chunk)
        preliminary_score = base_score + sum(components.values())
        rows.append({
            "preliminary_score": preliminary_score,
            "final_score": preliminary_score,
            "priority": _evidence_priority(score.evidence_class),
            "chunk_id": chunk_id,
            "fused_score": score,
            "chunk": chunk,
            "authority_delta": delta,
            "base_score": base_score,
            "components": components,
            "accepted": accepted,
            "reject_reason": reason,
        })
    rows.sort(key=lambda item: (-float(item["preliminary_score"]), int(item["priority"]), item["chunk"].path, str(item["chunk_id"])))  # type: ignore[union-attr]

    task_counts: dict[str, int] = {}
    for row in rows:
        chunk = row["chunk"]
        assert isinstance(chunk, ChunkInfo)
        components = row["components"]
        assert isinstance(components, dict)
        if chunk.task_id:
            seen = task_counts.get(chunk.task_id, 0)
            components["same_task_penalty"] = SAME_TASK_STEP_PENALTY * seen
            task_counts[chunk.task_id] = seen + 1
        row["final_score"] = float(row["preliminary_score"]) + float(components.get("same_task_penalty", 0.0))

    rows.sort(key=lambda item: (-float(item["final_score"]), int(item["priority"]), item["chunk"].path, str(item["chunk_id"])))  # type: ignore[union-attr]
    pointers: list[dict[str, object]] = []
    for row in rows:
        fused_score = row["fused_score"]
        chunk = row["chunk"]
        assert isinstance(fused_score, FusedScore)
        assert isinstance(chunk, ChunkInfo)
        score_value = float(row["final_score"])
        delta = float(row["authority_delta"])
        pointer: dict[str, object] = {
            "path": chunk.path,
            "why": _why(fused_score, chunk, delta),
            "score": round(score_value, 6),
        }
        if chunk.summary:
            pointer["summary"] = _trim_summary(chunk.summary)
        if include_signals:
            pointer["chunk_id"] = chunk.chunk_id
            pointer["heading_path"] = chunk.heading_path
            if chunk.text:
                pointer["chunk_text"] = chunk.text
            pointer["signals"] = _signals(fused_score)
            pointer["accepted"] = bool(row["accepted"])
            pointer["reject_reason"] = str(row["reject_reason"])
            components = row["components"]
            assert isinstance(components, dict)
            pointer["rerank_trace"] = _rerank_trace(float(row["base_score"]), score_value, chunk, components)
        pointers.append(pointer)
        if len(pointers) >= top_n:
            break
    return pointers


