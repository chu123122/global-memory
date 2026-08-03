"""SQLite build/status helpers for semantic retrieval."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from harness.config import HARNESS_DIR, MEMORY_ROOT
from harness.semantic.corpus import MarkdownDocument, file_content_hash, scan_corpus
from harness.semantic.calibration import DEFAULT_POLICY, default_acceptance_config
from harness.semantic.embed import DEFAULT_DIM, DEFAULT_MODEL, blob_to_vector, embed_texts, vector_to_blob
from harness.semantic.query import acceptance_policy_dict
from harness.semantic.tokens import content_tokens
from harness.semantic.errors import SemanticError

DEFAULT_INDEX_PATH = HARNESS_DIR / "data" / "semantic_index.sqlite"
REQUIRED_TABLES = {"meta", "chunks", "fts", "fts5", "vectors", "token_df"}
SCHEMA_VERSION = "3"


@dataclass(frozen=True)
class BuildStats:
    files_seen: int
    files_indexed: int
    chunks_indexed: int
    vectors_indexed: int
    reused_files: int
    stale_removed: int
    index_path: Path


@dataclass(frozen=True)
class StaleStats:
    files_seen: int
    missing_files: list[str]
    dirty_files: list[str]
    stale_paths: list[str]
    index_path: Path

    @property
    def ok(self) -> bool:
        return not self.missing_files and not self.dirty_files and not self.stale_paths

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "index": str(self.index_path),
            "filesSeen": self.files_seen,
            "missingFiles": self.missing_files,
            "dirtyFiles": self.dirty_files,
            "stalePaths": self.stale_paths,
        }


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual', 'view')").fetchall()
    return {str(row[0]) for row in rows}


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            heading_path TEXT NOT NULL,
            authority_tier TEXT NOT NULL,
            summary TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            source_mtime REAL NOT NULL,
            metadata_json TEXT NOT NULL,
            source_id TEXT NOT NULL DEFAULT 'global-memory',
            source_type TEXT NOT NULL DEFAULT 'canonical_memory',
            source_root TEXT NOT NULL DEFAULT '',
            source_rel_path TEXT NOT NULL DEFAULT '',
            indexed_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS fts5 USING fts5(
            chunk_id UNINDEXED,
            path UNINDEXED,
            heading_path,
            text,
            metadata,
            lexical,
            tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vectors (
            chunk_id TEXT PRIMARY KEY,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE
        )
        """
    )
    _ensure_chunk_source_columns(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id, source_rel_path)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS token_df (
            token TEXT PRIMARY KEY,
            doc_freq INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            df_ratio REAL NOT NULL
        )
        """
    )
    # Contract names the lexical index as both fts5 (engine detail) and fts (table family).
    # Keep a read-only compatibility view so status/review can see both names.
    conn.execute("CREATE VIEW IF NOT EXISTS fts AS SELECT rowid, chunk_id, path, heading_path, text, metadata, lexical FROM fts5")


def _ensure_chunk_source_columns(conn: sqlite3.Connection) -> None:
    existing = {str(row[1]) for row in conn.execute("PRAGMA table_info(chunks)").fetchall()}
    columns = {
        "source_id": "TEXT NOT NULL DEFAULT 'global-memory'",
        "source_type": "TEXT NOT NULL DEFAULT 'canonical_memory'",
        "source_root": "TEXT NOT NULL DEFAULT ''",
        "source_rel_path": "TEXT NOT NULL DEFAULT ''",
        "indexed_at": "TEXT NOT NULL DEFAULT ''",
    }
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE chunks ADD COLUMN {name} {ddl}")


def ensure_schema(conn: sqlite3.Connection) -> None:
    missing = REQUIRED_TABLES - _tables(conn)
    if missing:
        raise SemanticError("SQLITE_SCHEMA_MISSING", f"Missing semantic index tables: {', '.join(sorted(missing))}")


def _meta(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        return {str(k): str(v) for k, v in conn.execute("SELECT key, value FROM meta").fetchall()}
    except sqlite3.Error as exc:
        raise SemanticError("SQLITE_SCHEMA_MISSING", f"Cannot read semantic meta table: {exc}") from exc


def ensure_index_compatible(conn: sqlite3.Connection, *, expected_model: str = DEFAULT_MODEL) -> None:
    meta = _meta(conn)
    model = meta.get("model")
    if model != expected_model:
        raise SemanticError("INDEX_MODEL_MISMATCH", f"Index model {model!r} does not match {expected_model!r}")


def open_readonly(path: Path, *, expected_model: str = DEFAULT_MODEL) -> sqlite3.Connection:
    if not path.exists():
        raise SemanticError("SQLITE_INDEX_MISSING", f"Semantic index not found: {path}")
    uri = f"file:{path.as_posix()}?mode=ro"
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(uri, uri=True)
        ensure_schema(conn)
        ensure_index_compatible(conn, expected_model=expected_model)
        return conn
    except SemanticError:
        if conn is not None:
            conn.close()
        raise
    except sqlite3.OperationalError as exc:
        if conn is not None:
            conn.close()
        raise SemanticError("SQLITE_OPEN_FAILED", str(exc)) from exc


def _delete_path(conn: sqlite3.Connection, path: str) -> int:
    chunk_ids = [row[0] for row in conn.execute("SELECT chunk_id FROM chunks WHERE path=?", (path,)).fetchall()]
    for chunk_id in chunk_ids:
        conn.execute("DELETE FROM vectors WHERE chunk_id=?", (chunk_id,))
    conn.execute("DELETE FROM chunks WHERE path=?", (path,))
    conn.execute("DELETE FROM fts5 WHERE path=?", (path,))
    return len(chunk_ids)


def _lexical_ngrams(text: str) -> str:
    import re

    tokens: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for size in (2, 3, 4):
            for start in range(0, max(len(run) - size + 1, 0)):
                tokens.append(run[start : start + size])
    return " ".join(tokens)


def _insert_document(conn: sqlite3.Connection, doc: MarkdownDocument, file_hash: str, vectors: list[list[float]], *, dim: int) -> None:
    if len(vectors) != len(doc.chunks):
        raise SemanticError("EMBEDDING_COUNT_MISMATCH", f"{doc.rel_path}: chunks={len(doc.chunks)} vectors={len(vectors)}")
    indexed_at = datetime.now(timezone.utc).isoformat()
    for chunk, vector in zip(doc.chunks, vectors):
        metadata = {
            "keywords": chunk.metadata_keywords,
            "tags": chunk.metadata_tags,
            **doc.source_metadata,
        }
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        metadata_terms = chunk.metadata_keywords + chunk.metadata_tags
        metadata_terms.extend(str(value) for value in doc.source_metadata.values() if value)
        metadata_terms.extend(f"{key}:{value}" for key, value in doc.source_metadata.items() if value)
        metadata_text = " ".join(metadata_terms)
        conn.execute(
            """
            INSERT INTO chunks(
                chunk_id,path,ordinal,heading_path,authority_tier,summary,content_hash,file_hash,source_mtime,metadata_json,
                source_id,source_type,source_root,source_rel_path,indexed_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                chunk.chunk_id,
                doc.rel_path,
                chunk.ordinal,
                chunk.heading_path,
                doc.authority.tier,
                doc.retrieve_summary[:200],
                chunk.content_hash,
                file_hash,
                chunk.source_mtime,
                metadata_json,
                doc.source_id,
                doc.source_type,
                str(doc.source_root),
                doc.source_rel_path,
                indexed_at,
            ),
        )
        conn.execute(
            "INSERT INTO fts5(chunk_id,path,heading_path,text,metadata,lexical) VALUES (?,?,?,?,?,?)",
            (chunk.chunk_id, doc.rel_path, chunk.heading_path, chunk.text, metadata_text, _lexical_ngrams(chunk.text)),
        )
        conn.execute(
            "INSERT INTO vectors(chunk_id,dim,vector) VALUES (?,?,?)",
            (chunk.chunk_id, dim, vector_to_blob(vector)),
        )


def _tokens_for_df(text: str) -> list[str]:
    import re

    raw = [tok for tok in re.split(r"\s+", text) if tok]
    raw.extend(_lexical_ngrams(text).split())
    return content_tokens(raw)


def rebuild_token_df(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT heading_path, text, metadata, lexical FROM fts5").fetchall()
    chunk_count = len(rows)
    counts: dict[str, int] = {}
    for heading_path, text, metadata, lexical in rows:
        haystack = " ".join(str(part or "") for part in (heading_path, text, metadata, lexical))
        for token in set(_tokens_for_df(haystack)):
            counts[token] = counts.get(token, 0) + 1
    conn.execute("DELETE FROM token_df")
    if chunk_count == 0:
        return
    conn.executemany(
        "INSERT INTO token_df(token,doc_freq,chunk_count,df_ratio) VALUES (?,?,?,?)",
        [(token, count, chunk_count, count / chunk_count) for token, count in sorted(counts.items())],
    )


def build_index(
    *,
    memory_root: Path = MEMORY_ROOT,
    index_path: Path = DEFAULT_INDEX_PATH,
    model: str = DEFAULT_MODEL,
    dim: int = DEFAULT_DIM,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
    manifest_path: Path | None = None,
) -> BuildStats:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    docs = scan_corpus(memory_root, manifest_path=manifest_path)
    embed = embedder or (lambda texts: embed_texts(texts, model=model, expected_dim=dim))
    conn = sqlite3.connect(index_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        create_schema(conn)
        existing_paths = {row[0] for row in conn.execute("SELECT DISTINCT path FROM chunks").fetchall()}
        current_paths = {doc.rel_path for doc in docs}
        stale_removed = 0
        for stale in sorted(existing_paths - current_paths):
            stale_removed += _delete_path(conn, stale)
        reused = 0
        files_indexed = 0
        for doc in docs:
            file_hash = file_content_hash(doc.source_root / doc.source_rel_path)
            row = conn.execute("SELECT DISTINCT file_hash FROM chunks WHERE path=?", (doc.rel_path,)).fetchone()
            if row and row[0] == file_hash:
                reused += 1
                continue
            _delete_path(conn, doc.rel_path)
            vectors = embed([chunk.embedding_text for chunk in doc.chunks])
            _insert_document(conn, doc, file_hash, vectors, dim=dim)
            files_indexed += 1
        rebuild_token_df(conn)
        existing_meta = _meta(conn)
        acceptance_policy = existing_meta.get(
            "acceptance_policy",
            json.dumps({**DEFAULT_POLICY, "selected": acceptance_policy_dict(default_acceptance_config())}, ensure_ascii=False),
        )
        meta = {
            "schema_version": SCHEMA_VERSION,
            "model": model,
            "dim": str(dim),
            "memory_root": str(memory_root.resolve()),
            "built_at": datetime.now(timezone.utc).isoformat(),
            "authority_epsilon": "0.05",
            "acceptance_policy": acceptance_policy,
            "corpus_hash": _corpus_hash(conn),
            "source_manifest": str(manifest_path.resolve()) if manifest_path else "default",
        }
        for key, value in meta.items():
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)", (key, value))
        conn.commit()
        status = index_status(conn)
        return BuildStats(
            files_seen=len(docs),
            files_indexed=files_indexed,
            chunks_indexed=int(status["chunks"]),
            vectors_indexed=int(status["vectors"]),
            reused_files=reused,
            stale_removed=stale_removed,
            index_path=index_path,
        )
    except sqlite3.OperationalError as exc:
        conn.rollback()
        raise SemanticError("SQLITE_BUILD_FAILED", str(exc)) from exc
    finally:
        conn.close()


def check_stale(
    *,
    memory_root: Path = MEMORY_ROOT,
    index_path: Path = DEFAULT_INDEX_PATH,
    manifest_path: Path | None = None,
) -> StaleStats:
    docs = scan_corpus(memory_root, manifest_path=manifest_path)
    current_hashes = {doc.rel_path: file_content_hash(doc.source_root / doc.source_rel_path) for doc in docs}
    if not index_path.exists():
        return StaleStats(
            files_seen=len(docs),
            missing_files=sorted(current_hashes),
            dirty_files=[],
            stale_paths=[],
            index_path=index_path,
        )
    conn = sqlite3.connect(index_path)
    try:
        ensure_schema(conn)
        existing_hashes = {
            str(path): str(hash_value)
            for path, hash_value in conn.execute("SELECT path, max(file_hash) FROM chunks GROUP BY path").fetchall()
        }
    finally:
        conn.close()
    current_paths = set(current_hashes)
    existing_paths = set(existing_hashes)
    missing = sorted(current_paths - existing_paths)
    dirty = sorted(path for path in current_paths & existing_paths if current_hashes[path] != existing_hashes[path])
    stale = sorted(existing_paths - current_paths)
    return StaleStats(
        files_seen=len(docs),
        missing_files=missing,
        dirty_files=dirty,
        stale_paths=stale,
        index_path=index_path,
    )


def _corpus_hash(conn: sqlite3.Connection) -> str:
    parts = [f"{path}:{hash_value}" for path, hash_value in conn.execute("SELECT path, max(file_hash) FROM chunks GROUP BY path ORDER BY path")]
    import hashlib

    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def index_status(conn: sqlite3.Connection) -> dict[str, object]:
    ensure_schema(conn)
    chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    fts5 = conn.execute("SELECT count(*) FROM fts5").fetchone()[0]
    vectors = conn.execute("SELECT count(*) FROM vectors").fetchone()[0]
    files = conn.execute("SELECT count(DISTINCT path) FROM chunks").fetchone()[0]
    dims = [row[0] for row in conn.execute("SELECT DISTINCT dim FROM vectors ORDER BY dim").fetchall()]
    high_df_tokens = conn.execute("SELECT count(*) FROM token_df WHERE df_ratio > 0.30").fetchone()[0]
    missing_vectors = conn.execute(
        "SELECT count(*) FROM chunks LEFT JOIN vectors USING(chunk_id) WHERE vectors.chunk_id IS NULL"
    ).fetchone()[0]
    return {
        "files": files,
        "chunks": chunks,
        "fts5": fts5,
        "vectors": vectors,
        "dims": dims,
        "missingVectors": missing_vectors,
        "highDfTokens": high_df_tokens,
        "meta": _meta(conn),
        "ok": chunks == fts5 == vectors and missing_vectors == 0 and dims == [DEFAULT_DIM],
    }


def status_path(index_path: Path = DEFAULT_INDEX_PATH) -> dict[str, object]:
    conn = open_readonly(index_path)
    try:
        return index_status(conn)
    finally:
        conn.close()


def save_acceptance_policy(index_path: Path, policy: dict[str, object]) -> None:
    if not index_path.exists():
        raise SemanticError("SQLITE_INDEX_MISSING", f"Semantic index not found: {index_path}")
    conn = sqlite3.connect(index_path)
    try:
        ensure_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta(key,value) VALUES ('acceptance_policy', ?)",
            (json.dumps(policy, ensure_ascii=False),),
        )
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise SemanticError("SQLITE_POLICY_SAVE_FAILED", f"Cannot save acceptance policy: {exc}") from exc
    finally:
        conn.close()


def load_vectors(conn: sqlite3.Connection) -> dict[str, list[float]]:
    return {str(chunk_id): blob_to_vector(blob) for chunk_id, blob in conn.execute("SELECT chunk_id, vector FROM vectors")}


