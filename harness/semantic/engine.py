"""Read-only query engine for the semantic retrieval PoC."""
from __future__ import annotations

import re
import json
import sqlite3
from pathlib import Path
from functools import lru_cache
from typing import Any

from harness.semantic.embed import DEFAULT_MODEL, embed_texts
from harness.semantic.errors import SemanticError
from harness.semantic.index import DEFAULT_INDEX_PATH, load_vectors, open_readonly
from harness.semantic.calibration import acceptance_config_from_policy, default_acceptance_config
from harness.semantic.query import AcceptanceConfig, ChannelHit, ChunkInfo, rank_pointers
from harness.semantic.tokens import content_tokens, is_content_token


def _query_tokens(query: str) -> list[str]:
    """Return lexical query tokens without adding a CJK segmenter dependency."""
    raw_tokens = [tok for tok in re.split(r"\s+", query.strip()) if tok]
    out: list[str] = []
    for token in raw_tokens:
        out.append(token)
        # unicode61 treats contiguous CJK text as long tokens; add short CJK ngrams
        # so a natural-language query can still hit terms like "审查" / "改代码".
        for cjk_run in re.findall(r"[\u4e00-\u9fff]{2,}", token):
            for size in (2, 3, 4):
                for start in range(0, max(len(cjk_run) - size + 1, 0)):
                    out.append(cjk_run[start : start + size])
    seen: set[str] = set()
    deduped: list[str] = []
    for token in out:
        if token not in seen:
            seen.add(token)
            deduped.append(token)
    return deduped


def _low_df_tokens(conn: sqlite3.Connection, tokens: list[str], *, max_df_ratio: float = 0.30) -> set[str]:
    content = content_tokens(tokens)
    if not content:
        return set()
    placeholders = ",".join("?" for _ in content)
    try:
        rows = conn.execute(
            f"SELECT token, df_ratio FROM token_df WHERE token IN ({placeholders})",
            tuple(content),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "token_df" in str(exc):
            return set(content)
        raise SemanticError("SQLITE_QUERY_FAILED", f"token df query failed: {exc}") from exc
    ratios = {str(token): float(ratio) for token, ratio in rows}
    return {token for token in content if ratios.get(token, 0.0) <= max_df_ratio}


def _fts_tokens(query: str) -> list[str]:
    return [token for token in _query_tokens(query) if len(token) >= 2 and is_content_token(token)]

def _fts_query(query: str) -> str:
    tokens = _fts_tokens(query)
    if not tokens:
        return '""'
    return " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)


def _matched_query_tokens(query: str, text: str) -> list[str]:
    tokens = _fts_tokens(query)
    # Prefer more specific longer tokens in explanations and reranking.
    tokens.sort(key=lambda item: (-len(item), item))
    matched: list[str] = []
    for token in tokens:
        if token in text and token not in matched:
            matched.append(token)
        if len(matched) >= 6:
            break
    return matched


def lexical_hits(conn: sqlite3.Connection, query: str, *, limit: int = 20) -> list[ChannelHit]:
    fts_query = _fts_query(query)
    try:
        rows = conn.execute(
            """
            SELECT chunk_id, bm25(fts5) AS score, heading_path, text, metadata, lexical
            FROM fts5
            WHERE fts5 MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (fts_query, max(limit * 5, limit)),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        raise SemanticError("SQLITE_QUERY_FAILED", f"FTS query failed: {exc}") from exc
    ranked = []
    for chunk_id, score, heading_path, text, metadata, lexical in rows:
        haystack = " ".join(str(part or "") for part in (heading_path, text, metadata, lexical))
        matched = _matched_query_tokens(query, haystack)
        low_df = _low_df_tokens(conn, matched)
        content = [token for token in content_tokens(matched) if token in low_df]
        specificity = sum(len(token) for token in content)
        ranked.append((specificity, -float(score), str(chunk_id), content))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [
        ChannelHit(chunk_id, "bm25", raw_score, keyword=" ".join(matched[:4]))
        for specificity, raw_score, chunk_id, matched in ranked[:limit]
        if matched
    ]


def metadata_hits(conn: sqlite3.Connection, query: str, *, limit: int = 20) -> list[ChannelHit]:
    tokens = _fts_tokens(query)
    if not tokens:
        return []
    likes = []
    params: list[str | int] = []
    for token in tokens[:6]:
        likes.append("metadata_json LIKE ?")
        params.append(f"%{token}%")
    params.append(limit)
    try:
        rows = conn.execute(
            f"""
            SELECT chunk_id, path, ordinal, metadata_json
            FROM chunks
            WHERE {' OR '.join(likes)}
            ORDER BY path, ordinal
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        raise SemanticError("SQLITE_QUERY_FAILED", f"metadata query failed: {exc}") from exc
    hits: list[ChannelHit] = []
    for chunk_id, _path, _ordinal, metadata_json in rows:
        keyword = ""
        text = str(metadata_json or "")
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError:
            parsed = {}
        for token in tokens[:6]:
            if token not in text or token not in _low_df_tokens(conn, [token]):
                continue
            field = "metadata"
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if token in str(value):
                        field = str(key)
                        break
            expanded = token.replace("-", " ")
            keyword = f"{field}:{token} {expanded}" if expanded != token else f"{field}:{token}"
            break
        if keyword:
            hits.append(ChannelHit(str(chunk_id), "metadata", 20.0, keyword=keyword))
    return hits


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@lru_cache(maxsize=4)
def _load_vector_cache(index_path_text: str, mtime_ns: int) -> dict[str, Any]:
    path = Path(index_path_text)
    conn = open_readonly(path)
    try:
        vectors = load_vectors(conn)
    finally:
        conn.close()
    ids = tuple(vectors)
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return {"backend": "python", "vectors": vectors}
    matrix = np.asarray([vectors[chunk_id] for chunk_id in ids], dtype=np.float32)
    return {"backend": "numpy", "ids": ids, "matrix": matrix, "vectors": vectors}


def _vectors_for_query(conn: sqlite3.Connection, index_path: Path | None) -> dict[str, Any]:
    if index_path is None:
        return {"backend": "python", "vectors": load_vectors(conn)}
    try:
        stat = index_path.stat()
    except OSError:
        return {"backend": "python", "vectors": load_vectors(conn)}
    return _load_vector_cache(str(index_path.resolve()), stat.st_mtime_ns)


def warm_vector_cache(index_path: Path = DEFAULT_INDEX_PATH) -> int:
    """Load read-only vectors into the process cache and return vector count."""
    stat = index_path.stat()
    cache = _load_vector_cache(str(index_path.resolve()), stat.st_mtime_ns)
    if cache["backend"] == "numpy":
        return len(cache["ids"])
    return len(cache["vectors"])


def _vector_scores(query_vector: list[float], cache: dict[str, Any], *, limit: int) -> list[tuple[str, float]]:
    if cache.get("backend") == "numpy":
        try:
            import numpy as np  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            pass
        else:
            ids = cache["ids"]
            matrix = cache["matrix"]
            query = np.asarray(query_vector, dtype=np.float32)
            scores = matrix @ query
            if len(scores) <= limit:
                indices = np.argsort(-scores)
            else:
                candidates = np.argpartition(-scores, limit - 1)[:limit]
                indices = candidates[np.argsort(-scores[candidates])]
            return [(ids[int(idx)], float(scores[int(idx)])) for idx in indices[:limit]]
    vectors = cache["vectors"]
    scored = [(chunk_id, _dot(query_vector, vector)) for chunk_id, vector in vectors.items()]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def vector_hits(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
    model: str = DEFAULT_MODEL,
    query_vector: list[float] | None = None,
    index_path: Path | None = None,
) -> list[ChannelHit]:
    query_vector = query_vector or embed_texts([query], model=model)[0]
    cache = _vectors_for_query(conn, index_path)
    scored = _vector_scores(query_vector, cache, limit=limit)
    return [ChannelHit(chunk_id, "vector", score, vector_source=model) for chunk_id, score in scored]


def _metadata_dict(metadata_json: str) -> dict[str, object]:
    try:
        parsed = json.loads(metadata_json or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_chunk_info(conn: sqlite3.Connection, chunk_ids: set[str]) -> dict[str, ChunkInfo]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" for _ in chunk_ids)
    rows = conn.execute(
        f"""
        SELECT chunk_id,path,authority_tier,summary,heading_path,metadata_json,source_id,source_type
        FROM chunks
        WHERE chunk_id IN ({placeholders})
        """,
        tuple(chunk_ids),
    ).fetchall()
    text_by_chunk: dict[str, str] = {}
    try:
        text_rows = conn.execute(
            f"""
            SELECT chunk_id,text
            FROM fts5
            WHERE chunk_id IN ({placeholders})
            """,
            tuple(chunk_ids),
        ).fetchall()
        text_by_chunk = {str(chunk_id): str(text or "") for chunk_id, text in text_rows}
    except sqlite3.OperationalError:
        # Older in-memory tests and partially-built indexes may not expose fts5 here.
        text_by_chunk = {}
    chunks: dict[str, ChunkInfo] = {}
    for chunk_id, path, authority_tier, summary, heading_path, metadata_json, source_id, source_type in rows:
        metadata = _metadata_dict(str(metadata_json or ""))
        chunk_id_text = str(chunk_id)
        chunks[chunk_id_text] = ChunkInfo(
            chunk_id=chunk_id_text,
            path=str(path),
            authority_tier=str(authority_tier),
            summary=str(summary or ""),
            text=text_by_chunk.get(chunk_id_text, ""),
            heading_path=str(heading_path or ""),
            source_id=str(source_id or metadata.get("source_id") or ""),
            source_type=str(source_type or metadata.get("source_type") or ""),
            task_id=str(metadata.get("task_id") or ""),
            task_doc_type=str(metadata.get("task_doc_type") or ""),
            task_state=str(metadata.get("task_state") or ""),
            metadata=metadata,
        )
    return chunks


def load_acceptance_config(conn: sqlite3.Connection) -> AcceptanceConfig:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='acceptance_policy'").fetchone()
    except sqlite3.OperationalError as exc:
        raise SemanticError("SQLITE_QUERY_FAILED", f"acceptance policy read failed: {exc}") from exc
    if not row:
        return default_acceptance_config()
    if not isinstance(row, (tuple, list)):
        return default_acceptance_config()
    try:
        policy = json.loads(str(row[0]))
    except json.JSONDecodeError as exc:
        raise SemanticError("ACCEPTANCE_POLICY_INVALID", f"acceptance_policy is not JSON: {exc}") from exc
    if not isinstance(policy, dict):
        raise SemanticError("ACCEPTANCE_POLICY_INVALID", "acceptance_policy must be a JSON object")
    return acceptance_config_from_policy(policy)


def query_index(
    query: str,
    *,
    index_path: Path = DEFAULT_INDEX_PATH,
    top_n: int = 5,
    recall_limit: int = 50,
    debug: bool = False,
    acceptance_config: AcceptanceConfig | None = None,
    query_vector: list[float] | None = None,
) -> list[dict[str, object]]:
    conn = open_readonly(index_path)
    try:
        bm25 = lexical_hits(conn, query, limit=max(recall_limit, top_n * 5))
        metadata = metadata_hits(conn, query, limit=recall_limit)
        vector = vector_hits(conn, query, limit=max(recall_limit, top_n * 5), query_vector=query_vector, index_path=index_path)
        chunk_ids = {hit.chunk_id for hit in bm25 + metadata + vector}
        chunks = load_chunk_info(conn, chunk_ids)
        config = acceptance_config or load_acceptance_config(conn)
        return rank_pointers(
            chunks,
            {"bm25": bm25, "metadata": metadata, "vector": vector},
            query=query,
            top_n=top_n,
            accepted_only=not debug,
            acceptance_config=config,
            include_signals=debug,
        )
    finally:
        conn.close()



