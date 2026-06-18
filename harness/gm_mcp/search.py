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
LOW_CONFIDENCE_THRESHOLD = 0.62
DEFAULT_DELIVERED_UNIQUE_PATHS = 3


@dataclass(frozen=True)
class IntentParaphrase:
    intent: str
    paraphrase_id: str
    query: str
    source: str
    answer_paths: tuple[str, ...]
    vector: tuple[float, ...]


def _dot(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


@lru_cache(maxsize=1)
def _intent_bank_entries() -> tuple[IntentParaphrase, ...]:
    data = json.loads(INTENT_BANK_PATH.read_text(encoding="utf-8"))
    rows: list[tuple[str, str, str, str, tuple[str, ...]]] = []
    for intent in data.get("intents", []):
        intent_id = str(intent.get("intent") or "")
        answer_paths = tuple(str(path) for path in intent.get("answer_ref", {}).get("paths", []))
        for para in intent.get("train_paraphrases", []):
            rows.append((
                intent_id,
                str(para.get("id") or ""),
                str(para.get("query") or ""),
                str(para.get("source") or ""),
                answer_paths,
            ))
    texts = [row[2] for row in rows]
    vectors = semantic_embed.embed_texts(texts) if texts else []
    return tuple(
        IntentParaphrase(intent, pid, query, source, paths, tuple(vector))
        for (intent, pid, query, source, paths), vector in zip(rows, vectors)
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
    rows = []
    for entry in _intent_bank_entries():
        score = _dot(query_vector, entry.vector)
        rows.append((score, entry))
    rows.sort(key=lambda item: (-item[0], item[1].intent, item[1].paraphrase_id))
    return [
        {
            "intent": entry.intent,
            "paraphrase_id": entry.paraphrase_id,
            "query": entry.query,
            "source": entry.source,
            "score": round(score, 6),
            "answer_paths": list(entry.answer_paths),
        }
        for score, entry in rows[:top]
    ]


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
    cap = max(1, int(max_delivered_unique_paths))
    gate = {
        "policy": "overall_abstain_then_dedupe_require_vector_and_cap_pointers_only",
        "max_delivered_unique_paths": cap,
        "raw_count": len(raw_pointers),
        "raw_intent_count": len(raw_intents),
        "raw_suggested_answer_ref_count": len(raw_answer_refs),
        "dropped_duplicate_paths": 0,
        "dropped_without_vector_evidence": 0,
        "dropped_by_cap": 0,
        "intent_matches_demoted_to_raw": True,
        "demoted_intent_matches": len(raw_intents),
        "suggested_answer_refs_demoted_to_raw": True,
        "demoted_suggested_answer_refs": len(raw_answer_refs),
        "delivered_unique_paths": 0,
        "delivered_count": 0,
    }

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
        "count": len(raw_pointers),
        "hit": bool(result.get("hit")),
    })
    debug = dict(result.get("debug") or {})
    debug["deliver_gate"] = gate

    gated = dict(result)
    gated.update({
        "hit": bool(delivered_pointers),
        "count": len(delivered_pointers),
        "pointers": delivered_pointers,
        "abstained": abstained,
        "abstain_reason": abstain_reason,
        "raw": raw,
        "debug": debug,
    })
    gated.pop("intent_matches", None)
    gated.pop("suggested_answer_refs", None)
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
    answer_paths = []
    for match in q2q[:1]:
        answer_paths.extend(match.get("answer_paths") or [])
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
            "confidence": float(result.get("confidence") or 0.0),
            "low_confidence": True,
            "returned_summary": f"abstained: {result.get('abstain_reason') or 'low_confidence'}",
        }
    pointers = result.get("pointers") or []
    top_refs = [str(item.get("path")) for item in pointers[:3] if isinstance(item, dict) and item.get("path")]
    top_ids = [str(item.get("path")) for item in pointers[:3] if isinstance(item, dict) and item.get("path")]
    parts = []
    for item in pointers[:2]:
        if isinstance(item, dict):
            parts.append(f"{item.get('path')}: {item.get('summary') or item.get('why')}")
    return {
        "hit": bool(result.get("hit")),
        "count": int(result.get("count") or 0),
        "top_refs": top_refs[:5],
        "top_ids": top_ids[:5],
        "confidence": float(result.get("confidence") or 0.0),
        "low_confidence": bool(result.get("low_confidence")),
        "returned_summary": "; ".join(parts)[:500],
    }
