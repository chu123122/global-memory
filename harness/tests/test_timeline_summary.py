#!/usr/bin/env python3
"""Tests for timeline_summary.py read-only aggregation."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reporting"))

from timeline_summary import build_report  # noqa: E402


class TestTimelineSummary(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def append_jsonl(self, filename: str, record: dict) -> None:
        path = self.tmpdir / filename
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def test_empty_logs_are_safe(self) -> None:
        report = build_report(self.tmpdir, days=7, max_events=3)

        self.assertIsNone(report["latest_session"])
        tools = report["tracked_tool_usage"]["tools"]
        self.assertEqual(tools["work_context_pack.py"]["total_count"], 0)
        self.assertEqual(tools["work_context_pack.py"]["status"], "unused")
        self.assertEqual(report["latest_outcomes"], [])

    def test_session_tool_counts_invocations_and_outcomes(self) -> None:
        now = datetime.now().replace(microsecond=0)
        old = now - timedelta(days=30)
        self.append_jsonl(
            "tool_audit.jsonl",
            {
                "ts": old.isoformat(),
                "session": "old-session",
                "tool": "Bash",
                "input_summary": "python harness/audit_skill.py --json",
            },
        )
        self.append_jsonl(
            "tool_audit.jsonl",
            {
                "ts": now.isoformat(),
                "session": "fresh-session",
                "tool": "Read",
                "input_summary": "D:/global-memory/MEMORY.md",
            },
        )
        self.append_jsonl(
            "tool_audit.jsonl",
            {
                "ts": (now + timedelta(seconds=5)).isoformat(),
                "session": "fresh-session",
                "tool": "Bash",
                "input_summary": "python harness/work_context_pack.py --json --task demo",
            },
        )
        self.append_jsonl(
            "task_outcomes.jsonl",
            {
                "ts": now.isoformat(),
                "task": "demo delivery",
                "phase": "work",
                "outcome": "completed",
                "metrics": {"tool_calls": 2, "duration_min": 3},
                "lesson": "short task",
            },
        )
        self.append_jsonl(
            "harness_tool_invocations.jsonl",
            {
                "schema_version": 1,
                "ts": now.isoformat(),
                "script": "audit_skill.py",
                "source": "skill-audit",
                "argv": ["--all", "--json"],
            },
        )

        report = build_report(self.tmpdir, days=7, max_events=3)

        session = report["latest_session"]
        self.assertEqual(session["session"], "fresh-session")
        self.assertEqual(session["tool_calls"], 2)
        self.assertEqual(session["tool_counts"]["Bash"], 1)

        tools = report["tracked_tool_usage"]["tools"]
        self.assertEqual(tools["work_context_pack.py"]["audit_recent_count"], 1)
        self.assertEqual(tools["work_context_pack.py"]["status"], "recent")
        self.assertEqual(tools["audit_skill.py"]["audit_total_count"], 1)
        self.assertEqual(tools["audit_skill.py"]["audit_recent_count"], 0)
        self.assertEqual(tools["audit_skill.py"]["invocation_recent_count"], 1)
        self.assertEqual(tools["audit_skill.py"]["status"], "self-recent")

        outcomes = report["latest_outcomes"]
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["task"], "demo delivery")
        self.assertEqual(outcomes[0]["tool_calls"], 2)


if __name__ == "__main__":
    unittest.main()
