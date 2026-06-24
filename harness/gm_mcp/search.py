"""Search backend wrapper for gm.search."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from harness.semantic import engine as semantic_engine
from harness.semantic import embed as semantic_embed
from harness.semantic.index import DEFAULT_INDEX_PATH
from harness.semantic.query import AcceptanceConfig

INTENT_BANK_PATH = Path(__file__).resolve().parents[1] / "semantic" / "fixtures" / "intent_bank.json"
LOW_CONFIDENCE_THRESHOLD = 0.622
DEFAULT_DELIVERED_UNIQUE_PATHS = 3


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
    return {
        "path": row.get("path"),
        "summary": row.get("summary", ""),
        "why": row.get("why", ""),
        "rank_score": row.get("score", 0.0),
        "confidence": round(semantic_confidence, 6),
        "semantic_confidence": round(semantic_confidence, 6),
        "lexical_confidence": round(lexical_confidence, 6),
        "low_confidence": semantic_confidence < LOW_CONFIDENCE_THRESHOLD,
        "accepted": row.get("accepted"),
        "reject_reason": row.get("reject_reason"),
        "signals": signals,
    }


def _has_vector_evidence(pointer: dict[str, Any]) -> bool:
    signals = pointer.get("signals") if isinstance(pointer.get("signals"), dict) else {}
    raw_cosine = signals.get("raw_cosine") if isinstance(signals, dict) else None
    if not isinstance(raw_cosine, (int, float)):
        return False
    return signals.get("evidence_class") != "lexical_only"


def _rank_score(pointer: dict[str, Any]) -> float:
    try:
        return float(pointer.get("rank_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def apply_deliver_gate(
    result: dict[str, Any],
    *,
    max_delivered_unique_paths: int = DEFAULT_DELIVERED_UNIQUE_PATHS,
) -> dict[str, Any]:
    """Gate gm.search delivery without changing raw retrieval evidence."""
    raw_pointers = list(result.get("pointers") or [])
    raw_intents = list(result.get("intent_matches") or [])
    raw_answer_refs = list(result.get("suggested_answer_refs") or [])
    raw_intent_suggestions = list(result.get("intent_suggested_paths") or [])
    cap = max(1, int(max_delivered_unique_paths))
    gate = {
        "policy": "overall_abstain_then_dedupe_require_vector_and_cap_pointers_only",
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
    }

    delivered_intent_suggestions = [] if bool(result.get("low_confidence")) else raw_intent_suggestions

    if bool(result.get("low_confidence")):
        delivered_pointers: list[dict[str, Any]] = []
        abstained = True
        abstain_reason = "overall_low_confidence"
        gate["abstained"] = True
    else:
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
        abstained = False
        abstain_reason = ""
        gate["abstained"] = False

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
        "hit": bool(delivered_pointers or delivered_intent_suggestions),
        "count": len(delivered_pointers),
        "pointers": delivered_pointers,
        "intent_suggested_paths": delivered_intent_suggestions,
        "abstained": abstained,
        "abstain_reason": abstain_reason,
        "raw": raw,
        "debug": debug,
    })
    gated.pop("intent_matches", None)
    gated.pop("suggested_answer_refs", None)
    if not delivered_intent_suggestions:
        gated.pop("intent_suggested_paths", None)
    return gated


def search(
    query: str,
    *,
    top: int = 5,
    intent_top: int = 3,
    index_path: Path = DEFAULT_INDEX_PATH,
    max_delivered_unique_paths: int = DEFAULT_DELIVERED_UNIQUE_PATHS,
) -> dict[str, Any]:
    start = time.perf_counter()
    clean = query.strip()
    if not clean:
        raise ValueError("query must not be empty")
    top = max(1, min(int(top), 20))
    intent_top = max(1, min(int(intent_top), 10))

    embed_start = time.perf_counter()
    query_vector = semantic_embed.embed_texts([clean])[0]
    embed_ms = (time.perf_counter() - embed_start) * 1000.0

    doc_start = time.perf_counter()
    raw_pointers = semantic_engine.query_index(
        clean,
        index_path=index_path,
        top_n=top,
        debug=True,
        acceptance_config=AcceptanceConfig.default_open(),
        query_vector=query_vector,
    )
    doc_ms = (time.perf_counter() - doc_start) * 1000.0

    q2q_start = time.perf_counter()
    q2q = _q2q_matches(clean, query_vector, top=intent_top)
    q2q_ms = (time.perf_counter() - q2q_start) * 1000.0

    pointers = [_format_pointer(row) for row in raw_pointers]
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
        "low_confidence": confidence < LOW_CONFIDENCE_THRESHOLD,
        "threshold": LOW_CONFIDENCE_THRESHOLD,
        "mode": "vector_only_open_plus_intent_q2q",
        "pointers": pointers,
        "intent_matches": q2q,
        "intent_suggested_paths": intent_suggestions,
        "suggested_answer_refs": answer_paths,
        "diagnostics": {
            "index_path": str(index_path),
            "intent_bank_path": str(INTENT_BANK_PATH),
            "acceptance": "default_open_debug_no_hard_filter",
            "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
            "timings": {
                "embed_ms": round(embed_ms, 3),
                "q2doc_ms": round(doc_ms, 3),
                "q2q_ms": round(q2q_ms, 3),
            },
        },
    }
    return apply_deliver_gate(result, max_delivered_unique_paths=max_delivered_unique_paths)


def log_summary(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("abstained"):
        return {
            "hit": False,
            "count": 0,
            "top_refs": [],
            "top_ids": [],
            "intent_refs": [],
            "confidence": float(result.get("confidence") or 0.0),
            "low_confidence": True,
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
        "returned_summary": "; ".join(parts)[:500],
    }
