from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from harness.scripts import retrieve_candidate_quality


def _ts(days_ago: int, hour: int, minute: int = 0) -> str:
    """Relative timestamp inside the default days=7 window (avoids date drift)."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    ).isoformat()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _args(tmp_path: Path, *, min_recalled: int = 1) -> argparse.Namespace:
    return argparse.Namespace(logs_root=str(tmp_path), days=7, min_recalled=min_recalled, limit=10, format="json")


def test_candidate_quality_counts_top_refs_and_read_consumption(tmp_path):
    _write_jsonl(
        tmp_path / "retrieve_calls.jsonl",
        [
            {
                "ts": _ts(1, 10),
                "query_id": "qid-1",
                "hook_session_id": "s1",
                "turn_id": "turn-1",
                "top_refs": ["rules/接入索引.md"],
                "top_candidate_paths": ["rules/接入索引.md", "docs/hook-chain.md"],
            }
        ],
    )
    _write_jsonl(
        tmp_path / "tool_audit.jsonl",
        [
            {
                "ts": _ts(1, 10, 5),
                "session": "s1",
                "turn_id": "turn-1",
                "tool": "Read",
                "input_summary": r"D:\global-memory\rules\接入索引.md",
            }
        ],
    )

    report = retrieve_candidate_quality.build_report(_args(tmp_path))

    assert report["delivered_pointer_count"] == 2
    assert report["consumed_pointer_count"] == 1
    assert report["consumption_rate"] == 0.5
    assert report["consumed_examples"][0]["path"] == "rules/接入索引.md"
    assert report["turn_quality"][0]["turn_id"] == "turn-1"
    assert report["turn_quality"][0]["consumption_rate"] == 0.5
    assert report["unconsumed_top_paths"][0]["path"] == "docs/hook-chain.md"
    assert report["candidate_downrank"][0]["path"] == "docs/hook-chain.md"


def test_candidate_quality_compat_legacy_all_hits(tmp_path):
    _write_jsonl(
        tmp_path / "retrieve_calls.jsonl",
        [
            {
                "ts": _ts(1, 11),
                "session": "legacy-session",
                "all_hits": [{"path": "knowledge/old.md"}],
            }
        ],
    )
    _write_jsonl(
        tmp_path / "tool_audit.jsonl",
        [
            {
                "ts": _ts(1, 11, 10),
                "session": "legacy-session",
                "tool": "Read",
                "input_summary": r"D:\global-memory\knowledge\old.md",
            }
        ],
    )

    report = retrieve_candidate_quality.build_report(_args(tmp_path))

    assert report["delivered_pointer_count"] == 1
    assert report["consumed_pointer_count"] == 1
    assert report["consumption_rate"] == 1.0
    assert report["candidate_downrank"] == []
