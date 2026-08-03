"""Search backend wrapper for gm.search."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from harness.semantic import engine as semantic_engine
from harness.semantic import embed as semantic_embed
from harness.semantic import reranker as semantic_reranker
from harness.semantic import rewrite as semantic_rewrite
from harness.semantic.index import DEFAULT_INDEX_PATH
from harness.semantic.query import AcceptanceConfig

INTENT_BANK_PATH = Path(__file__).resolve().parents[1] / "semantic" / "fixtures" / "intent_bank.json"
LOW_CONFIDENCE_THRESHOLD = 0.622
DEFAULT_DELIVERED_UNIQUE_PATHS = 3
HOOK_DELIVERY_PROFILE = "interactive_hook"
HOOK_RERANK_ABSTAIN_THRESHOLD = 4.625
HOOK_PRE_RERANK_MIN_RAW_COSINE = LOW_CONFIDENCE_THRESHOLD
HOOK_RERANK_TOPK = 10
HOOK_RERANK_MAX_CHARS = 800
HOOK_RERANK_TIMEOUT_MS = 3000
HOOK_TOP = 2


@dataclass(frozen=True)
class DeliveryProfile:
    name: str
    top: int
    intent_top: int
    max_delivered_unique_paths: int
    rerank_top_k: int
    rerank_max_chars: int
    rerank_timeout_ms: int
    pre_rerank_min_raw_cosine: float
    rerank_abstain_threshold: float
    require_reranker_success: bool = True
    require_delivered_pointer: bool = True
    run_intent_q2q: bool = False
    deliver_intent_suggestions: bool = False


DELIVERY_PROFILES = {
    HOOK_DELIVERY_PROFILE: DeliveryProfile(
        name=HOOK_DELIVERY_PROFILE,
        top=HOOK_TOP,
        intent_top=1,
        max_delivered_unique_paths=HOOK_TOP,
        rerank_top_k=HOOK_RERANK_TOPK,
        rerank_max_chars=HOOK_RERANK_MAX_CHARS,
        rerank_timeout_ms=HOOK_RERANK_TIMEOUT_MS,
        pre_rerank_min_raw_cosine=HOOK_PRE_RERANK_MIN_RAW_COSINE,
        rerank_abstain_threshold=HOOK_RERANK_ABSTAIN_THRESHOLD,
    ),
}


def _resolve_delivery_profile(name: str | None) -> DeliveryProfile | None:
    if not name or name == "default":
        return None
    return DELIVERY_PROFILES.get(str(name).strip())


@dataclass(frozen=True)
class IntentParaphrase:
    intent: str
    paraphrase_id: str
    query: str
    source: str
    answer_paths: tuple[str, ...]
    vector: tuple[float, ...]
    specificity: str = ""


def _dot(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


@lru_cache(maxsize=1)
def _intent_bank_entries() -> tuple[IntentParaphrase, ...]:
    data = json.loads(INTENT_BANK_PATH.read_text(encoding="utf-8"))
    rows: list[tuple[str, str, str, str, tuple[str, ...]]] = []
    for intent in data.get("intents", []):
        intent_id = str(intent.get("intent") or "")
        answer_paths = tuple(str(path) for path in intent.get("answer_ref", {}).get("paths", []))
        routing = intent.get("routing") if isinstance(intent.get("routing"), dict) else {}
        specificity = str(routing.get("specificity") or "")
        for para in intent.get("train_paraphrases", []):
            rows.append((
                intent_id,
                str(para.get("id") or ""),
                str(para.get("query") or ""),
                str(para.get("source") or ""),
                answer_paths,
                specificity,
            ))
    texts = [row[2] for row in rows]
    vectors = semantic_embed.embed_texts(texts) if texts else []
    return tuple(
        IntentParaphrase(intent, pid, query, source, paths, tuple(vector), specificity)
        for (intent, pid, query, source, paths, specificity), vector in zip(rows, vectors)
    )


def warmup() -> dict[str, Any]:
    """Preload the loopback model and cache intent-bank embeddings."""
    start = time.perf_counter()
    semantic_embed.embed_texts(["gm_mcp_warmup"])
    vector_count = semantic_engine.warm_vector_cache(DEFAULT_INDEX_PATH)
    entries = _intent_bank_entries()
    return {
        "intent_paraphrases": len(entries),
        "vectors": vector_count,
        "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
    }


def _q2q_matches(query: str, query_vector: list[float], *, top: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[float, IntentParaphrase]]] = {}
    for entry in _intent_bank_entries():
        score = _dot(query_vector, entry.vector)
        grouped.setdefault(entry.intent, []).append((score, entry))

    rows: list[dict[str, Any]] = []
    for intent, matches in grouped.items():
        matches.sort(key=lambda item: (-item[0], item[1].paraphrase_id))
        best_score, best_entry = matches[0]
        top2 = matches[:2]
        avg_top2 = sum(score for score, _entry in top2) / len(top2)
        rows.append({
            "intent": intent,
            "paraphrase_id": best_entry.paraphrase_id,
            "query": best_entry.query,
            "source": best_entry.source,
            "score": round(best_score, 6),
            "best_score": round(best_score, 6),
            "avg_top2_score": round(avg_top2, 6),
            "specificity": best_entry.specificity,
            "answer_paths": list(best_entry.answer_paths),
            "matched_paraphrases": [
                {
                    "paraphrase_id": entry.paraphrase_id,
                    "query": entry.query,
                    "source": entry.source,
                    "score": round(score, 6),
                }
                for score, entry in matches[:3]
            ],
        })

    rows.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("intent") or "")))
    return rows[:top]


def _intent_suggested_paths(matches: list[dict[str, Any]], *, top: int = 3, margin: float = 0.08) -> list[dict[str, Any]]:
    if not matches:
        return []
    selected: list[dict[str, Any]] = []
    top_score = float(matches[0].get("score") or 0.0)
    for idx, match in enumerate(matches):
        score = float(match.get("score") or 0.0)
        specificity = str(match.get("specificity") or "")
        include = idx < top
        if idx >= top and specificity != "broad" and top_score - score <= margin:
            include = True
        if not include:
            continue
        paths = []
        seen: set[str] = set()
        for raw_path in match.get("answer_paths") or []:
            path = str(raw_path)
            if path and path not in seen:
                paths.append(path)
                seen.add(path)
        if not paths:
            continue
        selected.append({
            "intent": match.get("intent"),
            "score": round(score, 6),
            "paraphrase_id": match.get("paraphrase_id"),
            "specificity": specificity,
            "paths": paths,
            "reason": "q2q_intent_match",
        })
    return selected


def _format_pointer(row: dict[str, Any]) -> dict[str, Any]:
    signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
    raw_cosine = signals.get("raw_cosine") if isinstance(signals, dict) else None
    semantic_confidence = float(raw_cosine) if isinstance(raw_cosine, (int, float)) else 0.0
    lexical_confidence = 1.0 if signals.get("evidence_class") in {"both", "lexical_only"} else 0.0
    retrieval_score = row.get("retrieval_score", row.get("score", 0.0))
    reranker_score = row.get("reranker_score")
    reranker_enabled = bool(row.get("reranker_enabled"))
    rank_score = reranker_score if reranker_enabled and isinstance(reranker_score, (int, float)) else retrieval_score
    pointer = {
        "path": row.get("path"),
        "summary": row.get("summary", ""),
        "why": row.get("why", ""),
        "rank_score": rank_score,
        "retrieval_score": retrieval_score,
        "confidence": round(semantic_confidence, 6),
        "semantic_confidence": round(semantic_confidence, 6),
        "lexical_confidence": round(lexical_confidence, 6),
        "low_confidence": semantic_confidence < LOW_CONFIDENCE_THRESHOLD,
        "accepted": row.get("accepted"),
        "reject_reason": row.get("reject_reason"),
        "signals": signals,
        "reranker_enabled": reranker_enabled,
        "reranker_backend": row.get("reranker_backend"),
        "reranker_model": row.get("reranker_model"),
        "reranker_score": reranker_score,
        "reranker_rank": row.get("reranker_rank"),
        "reranker_latency_ms": row.get("reranker_latency_ms"),
        "confidence_calibrated": bool(row.get("confidence_calibrated", False)),
        "fallback_reason": row.get("fallback_reason"),
    }
    if row.get("chunk_id"):
        pointer["chunk_id"] = row.get("chunk_id")
    if row.get("heading_path"):
        pointer["heading_path"] = row.get("heading_path")
    return pointer


def _has_vector_evidence(pointer: dict[str, Any]) -> bool:
    signals = pointer.get("signals") if isinstance(pointer.get("signals"), dict) else {}
    raw_cosine = signals.get("raw_cosine") if isinstance(signals, dict) else None
    if not isinstance(raw_cosine, (int, float)):
        return False
    return signals.get("evidence_class") != "lexical_only"


def _rank_score(pointer: dict[str, Any]) -> float:
    score = pointer.get("reranker_score") if pointer.get("reranker_enabled") else pointer.get("rank_score")
    try:
        return float(score or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _best_reranker_score(pointers: list[dict[str, Any]]) -> float | None:
    scores = [item.get("reranker_score") for item in pointers if isinstance(item, dict)]
    numeric = [float(score) for score in scores if isinstance(score, (int, float))]
    return max(numeric) if numeric else None


def _best_raw_cosine(candidates: list[dict[str, Any]]) -> float | None:
    scores: list[float] = []
    for candidate in candidates:
        signals = candidate.get("signals") if isinstance(candidate.get("signals"), dict) else {}
        value = signals.get("raw_cosine") if isinstance(signals, dict) else None
        if isinstance(value, (int, float)):
            scores.append(float(value))
    return max(scores) if scores else None


def _candidate_snapshot(candidates: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    """Return compact candidate diagnostics for threshold analysis logs."""
    snapshot: list[dict[str, Any]] = []
    ranked = sorted(candidates, key=_candidate_retrieval_score, reverse=True)
    for candidate in ranked[: max(0, limit)]:
        signals = candidate.get("signals") if isinstance(candidate.get("signals"), dict) else {}
        raw_cosine = signals.get("raw_cosine") if isinstance(signals, dict) else None
        snapshot.append({
            "path": candidate.get("path"),
            "retrieval_score": candidate.get("retrieval_score", candidate.get("score")),
            "raw_cosine": raw_cosine,
            "evidence_class": signals.get("evidence_class") if isinstance(signals, dict) else None,
        })
    return snapshot

def _pre_rerank_abstain_reason(candidates: list[dict[str, Any]], profile: DeliveryProfile | None) -> str:
    if profile is None:
        return ""
    if not candidates:
        return "pre_rerank_no_candidates"
    evidence_classes = [
        (candidate.get("signals") if isinstance(candidate.get("signals"), dict) else {}).get("evidence_class")
        for candidate in candidates
    ]
    if evidence_classes and all(value == "lexical_only" for value in evidence_classes):
        return "pre_rerank_lexical_only"
    best_cosine = _best_raw_cosine(candidates)
    if best_cosine is None:
        return "pre_rerank_no_vector_evidence"
    if best_cosine < profile.pre_rerank_min_raw_cosine:
        return f"pre_rerank_raw_cosine_below_threshold:{round(best_cosine, 6)}<{profile.pre_rerank_min_raw_cosine}"
    return ""


def _profiled_reranker_config(config: semantic_reranker.RerankerConfig, profile: DeliveryProfile | None) -> semantic_reranker.RerankerConfig:
    if profile is None:
        return config
    return replace(
        config,
        top_k=max(1, min(config.top_k, profile.rerank_top_k)),
        timeout_ms=max(1, min(config.timeout_ms, profile.rerank_timeout_ms)),
        max_chars=max(200, min(config.max_chars, profile.rerank_max_chars)),
    )


def apply_deliver_gate(
    result: dict[str, Any],
    *,
    max_delivered_unique_paths: int = DEFAULT_DELIVERED_UNIQUE_PATHS,
    delivery_profile: str = "default",
    rerank_abstain_threshold: float | None = None,
    require_reranker_success: bool = False,
    require_delivered_pointer: bool = False,
    deliver_intent_suggestions: bool = True,
) -> dict[str, Any]:
    """Gate gm.search delivery without changing raw retrieval evidence."""
    raw_pointers = list(result.get("pointers") or [])
    raw_intents = list(result.get("intent_matches") or [])
    raw_answer_refs = list(result.get("suggested_answer_refs") or [])
    raw_intent_suggestions = list(result.get("intent_suggested_paths") or [])
    cap = max(1, int(max_delivered_unique_paths))
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    reranker_diag = diagnostics.get("reranker") if isinstance(diagnostics.get("reranker"), dict) else {}
    reranker_fallback_reason = reranker_diag.get("fallback_reason")
    reranker_fallback_count = 1 if reranker_fallback_reason else 0
    reranker_enabled = bool(reranker_diag.get("enabled"))
    best_reranker_score = _best_reranker_score(raw_pointers)
    pre_abstain_reason = str(result.get("pre_abstain_reason") or "")
    gate = {
        "policy": "overall_abstain_then_dedupe_require_vector_and_cap_pointers_only",
        "delivery_profile": delivery_profile,
        "max_delivered_unique_paths": cap,
        "raw_count": len(raw_pointers),
        "raw_intent_count": len(raw_intents),
        "raw_suggested_answer_ref_count": len(raw_answer_refs),
        "raw_intent_suggested_path_count": len(raw_intent_suggestions),
        "dropped_duplicate_paths": 0,
        "dropped_without_vector_evidence": 0,
        "dropped_by_cap": 0,
        "intent_matches_demoted_to_raw": True,
        "demoted_intent_matches": len(raw_intents),
        "suggested_answer_refs_demoted_to_raw": True,
        "demoted_suggested_answer_refs": len(raw_answer_refs),
        "delivered_unique_paths": 0,
        "delivered_count": 0,
        "intent_paths_hidden_by_pointer_cap": [],
        "rerank_abstain_threshold": rerank_abstain_threshold,
        "best_reranker_score": best_reranker_score,
        "reranker_fallback_count": reranker_fallback_count,
        "reranker_fallback_reason": reranker_fallback_reason,
        "require_reranker_success": require_reranker_success,
        "require_delivered_pointer": require_delivered_pointer,
    }

    delivered_pointers: list[dict[str, Any]] = []
    abstained = False
    abstain_reason = ""

    if pre_abstain_reason:
        abstained = True
        abstain_reason = pre_abstain_reason
    elif bool(result.get("low_confidence")):
        abstained = True
        abstain_reason = "overall_low_confidence"
    elif require_reranker_success and reranker_fallback_count > 0:
        abstained = True
        abstain_reason = f"reranker_fallback:{reranker_fallback_reason}"
    elif require_reranker_success and not reranker_enabled:
        abstained = True
        abstain_reason = "reranker_not_enabled"
    elif rerank_abstain_threshold is not None and (best_reranker_score is None or best_reranker_score < rerank_abstain_threshold):
        abstained = True
        shown = "none" if best_reranker_score is None else round(best_reranker_score, 6)
        abstain_reason = f"reranker_score_below_threshold:{shown}<{rerank_abstain_threshold}"

    if not abstained:
        deduped_by_path: dict[str, dict[str, Any]] = {}
        path_order: list[str] = []
        pathless: list[dict[str, Any]] = []
        for pointer in raw_pointers:
            if not isinstance(pointer, dict):
                continue
            path = str(pointer.get("path") or "")
            if not path:
                pathless.append(pointer)
                continue
            current = deduped_by_path.get(path)
            if current is None:
                deduped_by_path[path] = pointer
                path_order.append(path)
                continue
            gate["dropped_duplicate_paths"] += 1
            current_score = _rank_score(current)
            candidate_score = _rank_score(pointer)
            if candidate_score > current_score:
                deduped_by_path[path] = pointer

        deduped = [deduped_by_path[path] for path in path_order] + pathless

        vector_pointers = []
        for pointer in deduped:
            if _has_vector_evidence(pointer):
                vector_pointers.append(pointer)
            else:
                gate["dropped_without_vector_evidence"] += 1
        vector_pointers.sort(key=_rank_score, reverse=True)
        delivered_pointers = vector_pointers[:cap]
        gate["dropped_by_cap"] = max(0, len(vector_pointers) - len(delivered_pointers))
        delivered_paths = {str(item.get("path")) for item in delivered_pointers if isinstance(item, dict) and item.get("path")}
        raw_vector_paths = {str(item.get("path")) for item in vector_pointers if isinstance(item, dict) and item.get("path")}
        suggested_paths = {
            str(path)
            for suggestion in raw_intent_suggestions
            if isinstance(suggestion, dict)
            for path in suggestion.get("paths") or []
        }
        gate["intent_paths_hidden_by_pointer_cap"] = sorted((suggested_paths & raw_vector_paths) - delivered_paths)
        if require_delivered_pointer and not delivered_pointers:
            abstained = True
            abstain_reason = "no_delivered_pointer"
            delivered_pointers = []

    delivered_intent_suggestions = []
    if not abstained and deliver_intent_suggestions:
        delivered_intent_suggestions = raw_intent_suggestions

    gate["abstained"] = abstained
    gate["abstain_reason"] = abstain_reason
    gate["delivered_count"] = len(delivered_pointers)
    gate["delivered_unique_paths"] = len({str(item.get("path")) for item in delivered_pointers if isinstance(item, dict) and item.get("path")})
    raw = dict(result.get("raw") or {})
    raw.update({
        "pointers": raw_pointers,
        "intent_matches": raw_intents,
        "suggested_answer_refs": raw_answer_refs,
        "intent_suggested_paths": raw_intent_suggestions,
        "count": len(raw_pointers),
        "hit": bool(result.get("hit")),
    })
    debug = dict(result.get("debug") or {})
    debug["deliver_gate"] = gate

    gated = dict(result)
    gated.update({
        "hit": False if abstained else bool(delivered_pointers or delivered_intent_suggestions),
        "count": len(delivered_pointers),
        "pointers": delivered_pointers,
        "intent_suggested_paths": delivered_intent_suggestions,
        "abstained": abstained,
        "abstain_reason": abstain_reason,
        "low_confidence": bool(result.get("low_confidence")) or abstained,
        "raw": raw,
        "debug": debug,
    })
    gated.pop("intent_matches", None)
    gated.pop("suggested_answer_refs", None)
    if not delivered_intent_suggestions:
        gated.pop("intent_suggested_paths", None)
    return gated

def _candidate_retrieval_score(candidate: dict[str, Any]) -> float:
    for key in ("retrieval_score", "score", "rank_score"):
        value = candidate.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _candidate_dedupe_key(candidate: dict[str, Any]) -> str:
    chunk_id = str(candidate.get("chunk_id") or "").strip()
    if chunk_id:
        return f"chunk:{chunk_id}"
    path = str(candidate.get("path") or "").strip()
    if path:
        return f"path:{path}"
    return f"anon:{id(candidate)}"


def _dedupe_rewrite_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[str, dict[str, Any]] = {}
    first_index: dict[str, int] = {}
    for idx, candidate in enumerate(candidates):
        key = _candidate_dedupe_key(candidate)
        if key not in best_by_key:
            best_by_key[key] = candidate
            first_index[key] = idx
            continue
        if _candidate_retrieval_score(candidate) > _candidate_retrieval_score(best_by_key[key]):
            best_by_key[key] = candidate
    keys = list(best_by_key)
    keys.sort(key=lambda key: (-_candidate_retrieval_score(best_by_key[key]), first_index[key]))
    return [best_by_key[key] for key in keys]


def search(
    query: str,
    *,
    top: int = 5,
    intent_top: int = 3,
    index_path: Path = DEFAULT_INDEX_PATH,
    max_delivered_unique_paths: int = DEFAULT_DELIVERED_UNIQUE_PATHS,
    delivery_profile: str | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    clean = query.strip()
    if not clean:
        raise ValueError("query must not be empty")
    profile = _resolve_delivery_profile(delivery_profile)
    top = max(1, min(int(top), 20))
    intent_top = max(1, min(int(intent_top), 10))
    if profile is not None:
        top = min(top, profile.top)
        intent_top = min(intent_top, profile.intent_top)
        max_delivered_unique_paths = min(max_delivered_unique_paths, profile.max_delivered_unique_paths)
    rerank_config = _profiled_reranker_config(semantic_reranker.config_from_env(), profile)
    retrieval_top = top if not rerank_config.enabled else max(top, rerank_config.top_k)

    rewrite_config = semantic_rewrite.config_from_env()
    rewrite_start = time.perf_counter()
    rewrite_plan = semantic_rewrite.rewrite_query(clean, config=rewrite_config)
    rewrite_ms = (time.perf_counter() - rewrite_start) * 1000.0
    rewrite_queries = list(rewrite_plan.queries) or [clean]

    embed_start = time.perf_counter()
    query_vectors = semantic_embed.embed_texts(rewrite_queries)
    query_vector = query_vectors[0]
    embed_ms = (time.perf_counter() - embed_start) * 1000.0

    doc_start = time.perf_counter()
    per_query_counts: list[dict[str, Any]] = []
    merged_candidates: list[dict[str, Any]] = []
    for rewrite_query_text, rewrite_query_vector in zip(rewrite_queries, query_vectors):
        rows = semantic_engine.query_index(
            rewrite_query_text,
            index_path=index_path,
            top_n=retrieval_top,
            debug=True,
            acceptance_config=AcceptanceConfig.default_open(),
            query_vector=rewrite_query_vector,
        )
        per_query_counts.append({"query": rewrite_query_text, "count": len(rows)})
        merged_candidates.extend(dict(row) for row in rows)
    raw_candidates = _dedupe_rewrite_candidates(merged_candidates)
    doc_ms = (time.perf_counter() - doc_start) * 1000.0

    pre_abstain_reason = _pre_rerank_abstain_reason(raw_candidates, profile)
    rerank_start = time.perf_counter()
    if pre_abstain_reason:
        ranked_candidates = []
        reranker_diagnostics = {
            "requested_backend": rerank_config.backend,
            "backend": "skipped",
            "model": rerank_config.model,
            "enabled": False,
            "confidence_calibrated": False,
            "candidate_count": len(raw_candidates),
            "returned_count": 0,
            "latency_ms": 0.0,
            "fallback_reason": None,
            "skipped": True,
            "skipped_reason": pre_abstain_reason,
        }
    else:
        ranked_candidates, reranker_diagnostics = semantic_reranker.rerank_candidates(
            clean,
            raw_candidates[:retrieval_top],
            top_n=top,
            config=rerank_config,
        )
    rerank_ms = (time.perf_counter() - rerank_start) * 1000.0

    q2q_start = time.perf_counter()
    q2q = _q2q_matches(clean, query_vector, top=intent_top) if (profile is None or profile.run_intent_q2q) else []
    q2q_ms = (time.perf_counter() - q2q_start) * 1000.0

    pointers = [_format_pointer(dict(row)) for row in ranked_candidates]
    doc_confidence = max((float(item.get("confidence") or 0.0) for item in pointers), default=0.0)
    q2q_confidence = max((float(item.get("score") or 0.0) for item in q2q), default=0.0)
    confidence = max(doc_confidence, q2q_confidence)
    intent_suggestions = _intent_suggested_paths(q2q, top=min(intent_top, 3))
    answer_paths = []
    seen_answer_paths: set[str] = set()
    for suggestion in intent_suggestions:
        for path in suggestion.get("paths") or []:
            path = str(path)
            if path and path not in seen_answer_paths:
                answer_paths.append(path)
                seen_answer_paths.add(path)
    result = {
        "tool": "gm.search",
        "query": clean,
        "hit": bool(pointers or q2q),
        "count": len(pointers),
        "confidence": round(confidence, 6),
        "low_confidence": bool(pre_abstain_reason) or confidence < LOW_CONFIDENCE_THRESHOLD,
        "threshold": LOW_CONFIDENCE_THRESHOLD,
        "delivery_profile": profile.name if profile is not None else "default",
        "pre_abstain_reason": pre_abstain_reason,
        "mode": "vector_only_open_plus_reranker_plus_intent_q2q",
        "pointers": pointers,
        "intent_matches": q2q,
        "intent_suggested_paths": intent_suggestions,
        "suggested_answer_refs": answer_paths,
        "diagnostics": {
            "index_path": str(index_path),
            "intent_bank_path": str(INTENT_BANK_PATH),
            "delivery_profile": profile.name if profile is not None else "default",
            "acceptance": "default_open_debug_no_hard_filter",
            "rewrite": {
                "enabled": rewrite_config.enabled,
                "backend": rewrite_config.backend,
                "model": rewrite_config.model,
                "fallback_reason": rewrite_plan.fallback_reason,
                "query_count": len(rewrite_queries),
                "plan": rewrite_plan.to_dict(),
                "latency_ms": round(rewrite_ms, 3),
            },
            "recall": {
                "per_query_counts": per_query_counts,
                "merged_count": len(raw_candidates),
            },
            "reranker": reranker_diagnostics,
            "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
            "timings": {
                "rewrite_ms": round(rewrite_ms, 3),
                "embed_ms": round(embed_ms, 3),
                "q2doc_ms": round(doc_ms, 3),
                "rerank_ms": round(rerank_ms, 3),
                "q2q_ms": round(q2q_ms, 3),
            },
        },
        "debug": {
            "top_candidates": _candidate_snapshot(raw_candidates),
            "best_raw_cosine": _best_raw_cosine(raw_candidates),
            "thresholds": {
                "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
                "pre_rerank_min_raw_cosine": profile.pre_rerank_min_raw_cosine if profile is not None else None,
                "rerank_abstain_threshold": profile.rerank_abstain_threshold if profile is not None else None,
            },
        },
    }
    return apply_deliver_gate(
        result,
        max_delivered_unique_paths=max_delivered_unique_paths,
        delivery_profile=profile.name if profile is not None else "default",
        rerank_abstain_threshold=profile.rerank_abstain_threshold if profile is not None else None,
        require_reranker_success=profile.require_reranker_success if profile is not None else False,
        require_delivered_pointer=profile.require_delivered_pointer if profile is not None else False,
        deliver_intent_suggestions=profile.deliver_intent_suggestions if profile is not None else True,
    )


def log_summary(result: dict[str, Any]) -> dict[str, Any]:
    reranker_summary = (result.get("diagnostics") or {}).get("reranker") if isinstance(result.get("diagnostics"), dict) else None
    if result.get("abstained"):
        return {
            "hit": False,
            "count": 0,
            "top_refs": [],
            "top_ids": [],
            "intent_refs": [],
            "confidence": float(result.get("confidence") or 0.0),
            "low_confidence": True,
            "reranker": reranker_summary,
            "returned_summary": f"abstained: {result.get('abstain_reason') or 'low_confidence'}",
        }
    pointers = result.get("pointers") or []
    top_refs = [str(item.get("path")) for item in pointers[:3] if isinstance(item, dict) and item.get("path")]
    top_ids = [str(item.get("path")) for item in pointers[:3] if isinstance(item, dict) and item.get("path")]
    intent_suggestions = result.get("intent_suggested_paths") or []
    intent_refs = []
    for suggestion in intent_suggestions[:3]:
        if isinstance(suggestion, dict):
            intent_refs.extend(str(path) for path in suggestion.get("paths") or [] if path)
    parts = []
    for item in pointers[:2]:
        if isinstance(item, dict):
            parts.append(f"{item.get('path')}: {item.get('summary') or item.get('why')}")
    for suggestion in intent_suggestions[:2]:
        if isinstance(suggestion, dict):
            paths = ", ".join(str(path) for path in (suggestion.get("paths") or [])[:3])
            parts.append(f"intent {suggestion.get('intent')} suggests {paths}")
    return {
        "hit": bool(result.get("hit")),
        "count": int(result.get("count") or 0),
        "top_refs": top_refs[:5],
        "top_ids": top_ids[:5],
        "intent_refs": intent_refs[:10],
        "confidence": float(result.get("confidence") or 0.0),
        "low_confidence": bool(result.get("low_confidence")),
        "reranker": reranker_summary,
        "returned_summary": "; ".join(parts)[:500],
    }
