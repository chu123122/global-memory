"""Phase 17 SQLite persistence and recovery for collab bridge events."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping, Sequence

from .bridge_host import BridgeHostError, _session_from_events  # type: ignore[attr-defined]
from .bridge_store import build_store_summary
from .errors import CollabError


class PersistenceError(CollabError):
    """Raised when Phase 17 persistence operations fail."""

    error_code = "COLLAB_PERSISTENCE_INVALID_INPUT"


SCHEMA_VERSION = 1


def init_persistence(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(path)) as conn:
        _ensure_schema(conn)
    return {"schema_version": 1, "kind": "collab_persistence_init", "phase": 17, "db": str(path), "storage": "sqlite", "migrated_to": SCHEMA_VERSION}


def import_event_log(db_path: str | Path, session_id: str, events_path: str | Path) -> dict[str, Any]:
    events = _read_events(events_path)
    sid = _required(session_id, "session_id")
    with closing(_connect(db_path)) as conn:
        _ensure_schema(conn)
        with conn:
            conn.execute("INSERT OR REPLACE INTO sessions(session_id, created_at, updated_at) VALUES(?, datetime('now'), datetime('now'))", (sid,))
            conn.execute("DELETE FROM events WHERE session_id=?", (sid,))
            for idx, event in enumerate(events, start=1):
                conn.execute("INSERT INTO events(session_id, idx, event_json, created_at) VALUES(?, ?, ?, datetime('now'))", (sid, idx, json.dumps(event, ensure_ascii=False, sort_keys=True)))
    return {"schema_version": 1, "kind": "collab_persistence_import", "phase": 17, "db": str(db_path), "session_id": sid, "event_count": len(events)}


def append_persistent_event(db_path: str | Path, session_id: str, event: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(event, Mapping):
        raise PersistenceError("event must be an object")
    sid = _required(session_id, "session_id")
    with closing(_connect(db_path)) as conn:
        _ensure_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("INSERT OR IGNORE INTO sessions(session_id, created_at, updated_at) VALUES(?, datetime('now'), datetime('now'))", (sid,))
            row = conn.execute("SELECT COALESCE(MAX(idx), 0) + 1 FROM events WHERE session_id=?", (sid,)).fetchone()
            idx = int(row[0])
            conn.execute("INSERT INTO events(session_id, idx, event_json, created_at) VALUES(?, ?, ?, datetime('now'))", (sid, idx, json.dumps(dict(event), ensure_ascii=False, sort_keys=True)))
            conn.execute("UPDATE sessions SET updated_at=datetime('now') WHERE session_id=?", (sid,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"schema_version": 1, "kind": "collab_persistence_append", "phase": 17, "session_id": sid, "idx": idx}


def export_event_log(db_path: str | Path, session_id: str, events_path: str | Path) -> dict[str, Any]:
    events = read_persistent_events(db_path, session_id)
    out = Path(events_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    return {"schema_version": 1, "kind": "collab_persistence_export", "phase": 17, "session_id": session_id, "events": str(out), "event_count": len(events)}


def read_persistent_events(db_path: str | Path, session_id: str) -> list[dict[str, Any]]:
    sid = _required(session_id, "session_id")
    with closing(_connect(db_path)) as conn:
        _ensure_schema(conn)
        rows = conn.execute("SELECT event_json FROM events WHERE session_id=? ORDER BY idx", (sid,)).fetchall()
    events: list[dict[str, Any]] = []
    for (raw,) in rows:
        payload = json.loads(raw)
        if isinstance(payload, Mapping):
            events.append(dict(payload))
    return events


def load_persistent_session(db_path: str | Path, session_id: str) -> dict[str, Any]:
    events = read_persistent_events(db_path, session_id)
    try:
        return _session_from_events(events)
    except BridgeHostError as exc:
        raise PersistenceError(str(exc)) from exc


def list_persistent_sessions(db_path: str | Path) -> dict[str, Any]:
    with closing(_connect(db_path)) as conn:
        _ensure_schema(conn)
        rows = conn.execute("SELECT s.session_id, s.created_at, s.updated_at, COUNT(e.id) FROM sessions s LEFT JOIN events e ON s.session_id=e.session_id GROUP BY s.session_id, s.created_at, s.updated_at ORDER BY s.updated_at DESC").fetchall()
    return {"schema_version": 1, "kind": "collab_persistence_sessions", "phase": 17, "db": str(db_path), "sessions": [{"session_id": row[0], "created_at": row[1], "updated_at": row[2], "event_count": row[3]} for row in rows]}


def migrate_persistence(db_path: str | Path) -> dict[str, Any]:
    return init_persistence(db_path) | {"kind": "collab_persistence_migration", "migration_applied": True}


def recover_persistence(db_path: str | Path) -> dict[str, Any]:
    sessions = list_persistent_sessions(db_path)["sessions"]
    recovered = []
    for row in sessions:
        sid = row["session_id"]
        try:
            session = load_persistent_session(db_path, sid)
            summary = build_store_summary(session)
            recovered.append({"session_id": sid, "ok": True, "summary": summary["materialized"]["summary"], "event_count": summary["event_count"]})
        except Exception as exc:
            recovered.append({"session_id": sid, "ok": False, "error": str(exc)})
    return {"schema_version": 1, "kind": "collab_persistence_recovery", "phase": 17, "db": str(db_path), "session_count": len(sessions), "recovered": recovered}


def dumps_persistence_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, idx INTEGER NOT NULL, event_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(session_id, idx), FOREIGN KEY(session_id) REFERENCES sessions(session_id))")
    conn.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))


def _read_events(path: str | Path) -> list[dict[str, Any]]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise PersistenceError(f"failed to read event log: {exc}") from exc
    events: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PersistenceError(f"event log line {index} is invalid JSON: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise PersistenceError(f"event log line {index} must be an object")
        events.append(dict(payload))
    return events


def _required(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PersistenceError(f"{field} is required")
    return text
