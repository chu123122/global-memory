#!/usr/bin/env python3
"""Tests for governance_pulse helper contracts."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from governance_pulse import _parse_dual_storage_summary, _parse_orphan_scan_summary  # noqa: E402


class TestGovernancePulse(unittest.TestCase):
    def test_parse_orphan_scan_json_summary(self) -> None:
        payload = {
            "schema_version": 1,
            "kind": "orphan_script_scan",
            "summary": {
                "actual_scripts": 136,
                "unregistered": 2,
                "orphan_listed": 0,
                "stale_in_registry": 3,
            },
        }

        self.assertEqual(_parse_orphan_scan_summary(json.dumps(payload)), (2, 3))

    def test_parse_orphan_scan_rejects_human_text(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            _parse_orphan_scan_summary("UNREGISTERED: 0\nSTALE: 0\n")

    def test_parse_orphan_scan_requires_contract_kind(self) -> None:
        payload = {
            "kind": "other",
            "summary": {"unregistered": 0, "stale_in_registry": 0},
        }

        with self.assertRaises(ValueError):
            _parse_orphan_scan_summary(json.dumps(payload))

    def test_parse_dual_storage_json_summary(self) -> None:
        payload = {
            "schema_version": 1,
            "kind": "dual_storage_scan",
            "summary": {
                "active_dirs": 1,
                "archived_dirs": 2,
                "project_dirs": 3,
                "dual_count": 4,
            },
            "duplicates": [],
        }

        self.assertEqual(_parse_dual_storage_summary(json.dumps(payload)), 4)

    def test_parse_dual_storage_rejects_human_text(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            _parse_dual_storage_summary("dual_count=0\n")


if __name__ == "__main__":
    unittest.main()
