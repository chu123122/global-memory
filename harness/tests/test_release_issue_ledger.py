#!/usr/bin/env python3
"""Tests for release_issue_ledger owner decision records."""

from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from release_issue_ledger import (  # noqa: E402
    build_remaining_gap_table,
    build_owner_decision_record_report,
    compact_evidence,
    decision_state_findings,
    gap_table_view,
    ledger_exit_code,
    owner_decision_template_view,
    owner_decision_record_summary,
    owner_decisions_from_issues,
    owner_decisions_exit_code,
    owner_decisions_view,
    record_owner_decision,
    render_gap_table_text,
    render_owner_decisions_text,
    render_owner_decision_template_text,
    validate_owner_record,
)


def owner_issue() -> dict:
    return {
        "issue_id": "oss-project_metadata",
        "check_id": "project_metadata",
        "state": "open",
        "severity": "blocker",
        "gap": {
            "type": "owner_decision",
            "owner": "project_owner",
            "resolution": "Choose the project license.",
        },
        "summary": "checked=6, findings=1",
        "evidence": {
            "decision_plan": {
                "decision": "license_policy",
                "owner": "project_owner",
                "ready": False,
                "decision_doc": "docs/license-decision.md",
                "options": [
                    {"id": "mit", "action": "add_mit_license"},
                    {"id": "apache_2_0", "action": "add_apache_2_0_license"},
                ],
            }
        },
    }


def publish_scope_issue() -> dict:
    return {
        "issue_id": "oss-publish_scope",
        "check_id": "publish_scope",
        "state": "open",
        "severity": "blocker",
        "gap": {
            "type": "publish_scope_governance",
            "owner": "project_owner",
            "resolution": "Decide the publication boundary.",
        },
        "summary": "tracked_private_paths=175, unclassified_tracked_paths=0",
        "evidence": {
            "decision_plan": {
                "decision": "publish_scope_boundary",
                "owner": "project_owner",
                "ready": False,
                "decision_doc": "docs/publish-scope.md",
                "required_when": {
                    "private_tracked_paths": 175,
                    "unclassified_tracked_paths": 0,
                },
                "options": [
                    {"id": "split_clean_source_repository", "action": "publish_only_external_scope"},
                    {"id": "keep_private_maturity_audit", "action": "do_not_publish_source"},
                ],
            }
        },
    }


class TestOwnerDecisionRecords(unittest.TestCase):
    def test_compact_evidence_keeps_doc_entrypoint_frontmatter_count(self) -> None:
        evidence = compact_evidence({
            "frontmatter_checked": 5,
            "findings": [],
        })

        self.assertEqual(evidence["frontmatter_checked"], 5)
        self.assertEqual(evidence["findings"], [])

    def test_undecided_record_allows_empty_selected_option(self) -> None:
        valid, findings = validate_owner_record({"status": "undecided", "selected_option": ""}, {"mit"})

        self.assertTrue(valid)
        self.assertEqual(findings, [])

    def test_decided_record_rejects_unknown_option(self) -> None:
        valid, findings = validate_owner_record(
            {
                "status": "decided",
                "selected_option": "unknown",
                "decided_by": "owner",
                "decided_at": "2026-05-25",
            },
            {"mit"},
        )

        self.assertFalse(valid)
        self.assertIn("unknown_selected_option:unknown", findings)

    def test_decided_record_requires_actor_and_timestamp(self) -> None:
        valid, findings = validate_owner_record(
            {"status": "decided", "selected_option": "mit"},
            {"mit"},
        )

        self.assertFalse(valid)
        self.assertIn("missing_decided_by", findings)
        self.assertIn("missing_decided_at", findings)

    def test_owner_decisions_include_record_findings(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {
                "license_policy": {
                    "status": "decided",
                    "selected_option": "unknown",
                    "decided_by": "owner",
                    "decided_at": "2026-05-25",
                }
            },
        )

        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["decision"], "license_policy")
        self.assertFalse(decisions[0]["record_valid"])
        self.assertEqual(decisions[0]["record_findings"], ["unknown_selected_option:unknown"])

    def test_record_ready_is_separate_from_gate_ready(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {
                "license_policy": {
                    "status": "decided",
                    "selected_option": "mit",
                    "decided_by": "owner",
                    "decided_at": "2026-05-25",
                }
            },
        )

        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0]["record_ready"])
        self.assertFalse(decisions[0]["gate_ready"])
        self.assertFalse(decisions[0]["ready"])
        self.assertEqual(decisions[0]["record_gate_effect"]["effect"], "records_owner_choice_only")
        self.assertIs(decisions[0]["record_gate_effect"]["clears_release_blocker"], False)
        self.assertEqual(decisions[0]["gate_unblock_requirements"], {
            "status": "blocked_until_requirements_clear",
            "requirements": [
                {"kind": "rerun_release_check", "values": {}},
            ],
        })

    def test_missing_owner_record_is_invalid(self) -> None:
        decisions = owner_decisions_from_issues([owner_issue()], {})

        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0]["record_present"])
        self.assertFalse(decisions[0]["record_valid"])
        self.assertIn("missing_decision_state_record", decisions[0]["record_findings"])

    def test_stale_owner_record_is_reported(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {
                "license_policy": {"status": "undecided"},
                "removed_decision": {"status": "undecided"},
            },
        )

        findings = decision_state_findings(decisions, {
            "license_policy": {"status": "undecided"},
            "removed_decision": {"status": "undecided"},
        })

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "stale_decision_state_record")
        self.assertEqual(findings[0]["decision"], "removed_decision")

    def test_owner_decision_record_summary_counts_record_state(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {"license_policy": {"status": "undecided"}},
        )
        missing = owner_decisions_from_issues([owner_issue()], {})[0]
        findings = [{"code": "stale_decision_state_record", "decision": "removed_decision"}]

        summary = owner_decision_record_summary([decisions[0], missing], findings)

        self.assertEqual(summary["valid_records"], 1)
        self.assertEqual(summary["invalid_records"], 1)
        self.assertEqual(summary["missing_records"], 1)
        self.assertEqual(summary["stale_records"], 1)
        self.assertEqual(summary["record_status_counts"], {"undecided": 2})

    def test_ledger_exit_code_fails_on_bad_owner_record_even_without_blockers(self) -> None:
        self.assertEqual(ledger_exit_code({
            "blockers": 0,
            "decision_state_findings": 0,
            "owner_decision_records": {
                "invalid_records": 1,
                "missing_records": 0,
                "stale_records": 0,
            },
        }), 1)

    def test_ledger_exit_code_passes_when_no_blockers_or_state_findings(self) -> None:
        self.assertEqual(ledger_exit_code({
            "blockers": 0,
            "decision_state_findings": 0,
            "owner_decision_records": {
                "invalid_records": 0,
                "missing_records": 0,
                "stale_records": 0,
            },
        }), 0)

    def test_owner_decisions_exit_code_fails_on_not_ready_owner_queue(self) -> None:
        view = owner_decisions_view({
            "timestamp": "2026-05-25T00:00:00",
            "repo": "D:\\global-memory",
            "release_verdict": "blocked",
            "summary": {
                "owner_decision_records": {
                    "valid_records": 1,
                    "invalid_records": 0,
                    "missing_records": 0,
                    "stale_records": 0,
                },
            },
            "owner_decisions": [{
                "issue_id": "oss-project_metadata",
                "ready": False,
                "record_valid": True,
            }],
            "decision_state_findings": [],
        })

        self.assertEqual(owner_decisions_exit_code(view), 1)

    def test_owner_decisions_exit_code_ignores_non_owner_release_blockers(self) -> None:
        view = owner_decisions_view({
            "timestamp": "2026-05-25T00:00:00",
            "repo": "D:\\global-memory",
            "release_verdict": "blocked",
            "summary": {
                "blockers": 1,
                "owner_decision_records": {
                    "valid_records": 0,
                    "invalid_records": 0,
                    "missing_records": 0,
                    "stale_records": 0,
                },
            },
            "owner_decisions": [],
            "decision_state_findings": [],
        })

        self.assertEqual(owner_decisions_exit_code(view), 0)

    def test_owner_decisions_text_includes_record_commands(self) -> None:
        issues = [owner_issue(), publish_scope_issue()]
        view = owner_decisions_view({
            "timestamp": "2026-05-25T00:00:00",
            "repo": "D:\\global-memory",
            "release_verdict": "blocked",
            "summary": {
                "owner_decision_records": {
                    "valid_records": 2,
                    "invalid_records": 0,
                    "missing_records": 0,
                    "stale_records": 0,
                },
            },
            "owner_decisions": owner_decisions_from_issues(
                issues,
                {
                    "license_policy": {"status": "undecided"},
                    "publish_scope_boundary": {"status": "undecided"},
                },
            ),
            "decision_state_findings": [],
        })

        text = render_owner_decisions_text(view)

        self.assertIn("release_issue_ledger.py - owner decision queue", text)
        self.assertIn("gate_ready=0 gate_not_ready=2 record_ready=0 record_not_ready=2", text)
        self.assertIn("gate_ready=False record_ready=False", text)
        self.assertIn("gate_unblock_requirements: rerun_release_check", text)
        self.assertIn("gate_unblock_requirements: required_conditions", text)
        self.assertIn("release-record-decision --dry-run --decision license_policy", text)
        self.assertIn("release-record-decision --write --decision license_policy", text)
        self.assertIn("required_when: private_tracked_paths=175, unclassified_tracked_paths=0", text)
        self.assertIn("release-record-decision --dry-run --decision publish_scope_boundary", text)
        self.assertIn("release-record-decision --write --decision publish_scope_boundary", text)

    def test_remaining_gap_table_groups_open_and_deferred_work(self) -> None:
        owner_decisions = owner_decisions_from_issues(
            [owner_issue()],
            {"license_policy": {"status": "undecided"}},
        )
        code_issue = {
            "issue_id": "oss-source_export_plan",
            "check_id": "source_export_plan",
            "state": "open",
            "severity": "warning",
            "title": "Clean source export plan is reproducible",
            "gap": {
                "type": "code_remediation",
                "owner": "maintainer",
                "resolution": "Track external-scope files.",
            },
            "summary": "untracked_included=1",
            "next_action": "Stage or exclude external files.",
        }
        docs_issue = {
            "issue_id": "oss-external_source_safety",
            "check_id": "external_source_safety",
            "state": "open",
            "severity": "warning",
            "title": "External source safety",
            "gap": {
                "type": "docs_publish_scope_governance",
                "owner": "maintainer",
                "resolution": "Sanitize public history.",
            },
            "summary": "warnings=1",
            "next_action": "Sanitize public history.",
        }
        deferred_issue = {
            "issue_id": "oss-legacy_health",
            "check_id": "legacy_health",
            "state": "deferred",
            "severity": "info",
            "title": "Legacy health",
            "gap": {
                "type": "content_hygiene",
                "owner": "maintainer",
                "resolution": "Run when cleaning content.",
            },
            "summary": "deferred",
            "next_action": "Run explicitly.",
        }

        table = build_remaining_gap_table(
            [owner_issue(), code_issue, docs_issue, deferred_issue],
            owner_decisions,
        )

        self.assertEqual([item["issue_id"] for item in table["owner_decisions"]], ["oss-project_metadata"])
        self.assertEqual(table["owner_decisions"][0]["decision"], "license_policy")
        self.assertEqual(table["owner_decisions"][0]["required_artifacts"], [])
        self.assertEqual(table["owner_decisions"][0]["required_when"], {})
        self.assertEqual(table["owner_decisions"][0]["allowed_options"], ["mit", "apache_2_0"])
        self.assertEqual(
            table["owner_decisions"][0]["record_dry_run_command"],
            [
                "python",
                r"harness\maintain.py",
                "release-record-decision",
                "--dry-run",
                "--decision",
                "license_policy",
                "--selected-option",
                "<option>",
                "--decided-by",
                "<owner>",
                "--decided-at",
                "YYYY-MM-DD",
                "--json",
            ],
        )
        self.assertIn("--write", table["owner_decisions"][0]["record_write_command"])
        self.assertEqual([item["issue_id"] for item in table["code_remediation"]], ["oss-source_export_plan"])
        self.assertEqual([item["issue_id"] for item in table["docs_publish_scope_governance"]], ["oss-external_source_safety"])
        self.assertEqual([item["issue_id"] for item in table["deferred"]], ["oss-legacy_health"])

    def test_gap_table_view_is_concise_and_text_renderable(self) -> None:
        issues = [owner_issue(), publish_scope_issue()]
        table = build_remaining_gap_table(
            issues,
            owner_decisions_from_issues(
                issues,
                {
                    "license_policy": {"status": "undecided"},
                    "publish_scope_boundary": {"status": "undecided"},
                },
            ),
        )
        view = gap_table_view({
            "timestamp": "2026-05-25T00:00:00",
            "repo": "D:\\global-memory",
            "release_verdict": "blocked",
            "remaining_gap_table": table,
        })

        self.assertEqual(view["kind"], "release_gap_table")
        self.assertEqual(view["summary"]["owner_decisions"], 2)
        self.assertEqual(view["summary"]["code_remediation"], 0)
        self.assertEqual(view["summary"]["open_by_gap_type"], {
            "owner_decision": 1,
            "publish_scope_governance": 1,
        })
        text = render_gap_table_text(view)
        self.assertIn("release_issue_ledger.py - remaining gap table", text)
        self.assertIn("open_by_gap_type: owner_decision=1, publish_scope_governance=1", text)
        self.assertIn("oss-project_metadata", text)
        self.assertIn("doc: docs/license-decision.md", text)
        self.assertIn("allowed_options: mit, apache_2_0", text)
        self.assertIn("record_gate_effect: effect=records_owner_choice_only clears_release_blocker=False", text)
        self.assertIn("gate_unblock_requirements: rerun_release_check", text)
        self.assertIn("dry_run: python", text)
        self.assertIn("release-record-decision --dry-run --decision license_policy", text)
        self.assertIn("write: python", text)
        self.assertIn("release-record-decision --write --decision license_policy", text)
        self.assertIn("oss-publish_scope", text)
        self.assertIn("doc: docs/publish-scope.md", text)
        self.assertIn("required_when: private_tracked_paths=175, unclassified_tracked_paths=0", text)
        self.assertIn("allowed_options: split_clean_source_repository, keep_private_maturity_audit", text)
        self.assertIn("release-record-decision --dry-run --decision publish_scope_boundary", text)
        self.assertIn("release-record-decision --write --decision publish_scope_boundary", text)

    def test_owner_decision_template_exposes_editable_state_patch(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {"license_policy": {"status": "undecided"}},
        )
        view = owner_decision_template_view({
            "timestamp": "2026-05-25T00:00:00",
            "repo": "D:\\global-memory",
            "release_verdict": "blocked",
            "owner_decisions": decisions,
            "decision_state_findings": [],
        })

        self.assertEqual(view["kind"], "release_owner_decision_template")
        self.assertEqual(view["summary"]["templates"], 1)
        template = view["templates"][0]
        self.assertEqual(template["decision"], "license_policy")
        self.assertEqual([option["id"] for option in template["allowed_options"]], ["mit", "apache_2_0"])
        self.assertEqual(template["state_patch_template"]["status"], "decided")
        self.assertEqual(template["record_gate_effect"]["effect"], "records_owner_choice_only")
        self.assertIs(template["record_gate_effect"]["clears_release_blocker"], False)
        self.assertEqual(template["gate_unblock_requirements"]["requirements"][0]["kind"], "rerun_release_check")
        self.assertIn("selected_option", template["required_update_fields"])
        self.assertIn("license_policy", view["state_patch_template"]["decisions"])

        text = render_owner_decision_template_text(view)
        self.assertIn("release_issue_ledger.py - owner decision template", text)
        self.assertIn("license_policy", text)
        self.assertIn("record_gate_effect: effect=records_owner_choice_only clears_release_blocker=False", text)
        self.assertIn("gate_unblock_requirements: rerun_release_check", text)

    def test_owner_decision_record_report_validates_allowed_option(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {"license_policy": {"status": "undecided"}},
        )
        report, exit_code = build_owner_decision_record_report(
            {
                "timestamp": "2026-05-25T00:00:00",
                "repo": "D:\\global-memory",
                "release_verdict": "blocked",
                "owner_decisions": decisions,
                "decision_state_findings": [],
            },
            decision_id="license_policy",
            selected_option="mit",
            decided_by="owner",
            decided_at="2026-05-25",
            notes="owner selected MIT",
            dry_run=True,
            state_doc={"decisions": {"license_policy": {"status": "undecided"}}},
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(report["valid"])
        self.assertEqual(report["action"], "dry_run")
        self.assertEqual(report["record_gate_effect"]["effect"], "records_owner_choice_only")
        self.assertIs(report["record_gate_effect"]["clears_release_blocker"], False)
        self.assertEqual(report["gate_unblock_requirements"]["requirements"][0]["kind"], "rerun_release_check")
        self.assertEqual(report["proposed_record"]["status"], "decided")
        self.assertEqual(report["proposed_record"]["selected_option"], "mit")

    def test_publish_scope_record_report_preserves_required_when(self) -> None:
        decisions = owner_decisions_from_issues(
            [publish_scope_issue()],
            {"publish_scope_boundary": {"status": "undecided"}},
        )
        report, exit_code = build_owner_decision_record_report(
            {
                "timestamp": "2026-05-26T00:00:00",
                "repo": "D:\\global-memory",
                "release_verdict": "blocked",
                "owner_decisions": decisions,
                "decision_state_findings": [],
            },
            decision_id="publish_scope_boundary",
            selected_option="keep_private_maturity_audit",
            decided_by="owner",
            decided_at="2026-05-26",
            dry_run=True,
            state_doc={"decisions": {"publish_scope_boundary": {"status": "undecided"}}},
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(report["valid"])
        self.assertEqual(report["action"], "dry_run")
        self.assertEqual(report["allowed_options"], ["split_clean_source_repository", "keep_private_maturity_audit"])
        self.assertEqual(report["required_when"]["private_tracked_paths"], 175)
        self.assertEqual(report["required_when"]["unclassified_tracked_paths"], 0)
        self.assertEqual(report["gate_unblock_requirements"]["requirements"][0]["kind"], "required_conditions")
        self.assertEqual(report["proposed_record"]["selected_option"], "keep_private_maturity_audit")

    def test_owner_decision_record_report_rejects_unknown_option(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {"license_policy": {"status": "undecided"}},
        )
        report, exit_code = build_owner_decision_record_report(
            {
                "timestamp": "2026-05-25T00:00:00",
                "repo": "D:\\global-memory",
                "release_verdict": "blocked",
                "owner_decisions": decisions,
                "decision_state_findings": [],
            },
            decision_id="license_policy",
            selected_option="unknown",
            decided_by="owner",
            decided_at="2026-05-25",
            dry_run=True,
            state_doc={"decisions": {"license_policy": {"status": "undecided"}}},
        )

        self.assertEqual(exit_code, 1)
        self.assertFalse(report["valid"])
        self.assertIn("unknown_selected_option:unknown", {item["code"] for item in report["findings"]})

    def test_record_owner_decision_dry_run_does_not_write_temp_state(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {"license_policy": {"status": "undecided"}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "release_owner_decisions.json"
            state_path.write_text(json.dumps({
                "schema_version": 1,
                "kind": "release_owner_decision_state",
                "decisions": {"license_policy": {"status": "undecided"}},
            }), encoding="utf-8")

            report, exit_code = record_owner_decision(
                {
                    "timestamp": "2026-05-25T00:00:00",
                    "repo": "D:\\global-memory",
                    "release_verdict": "blocked",
                    "owner_decisions": decisions,
                    "decision_state_findings": [],
                },
                decision_id="license_policy",
                selected_option="mit",
                decided_by="owner",
                decided_at="2026-05-25",
                dry_run=True,
                state_path=state_path,
            )

            saved = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["action"], "dry_run")
        self.assertEqual(saved["decisions"]["license_policy"]["status"], "undecided")

    def test_record_owner_decision_write_updates_temp_state(self) -> None:
        decisions = owner_decisions_from_issues(
            [owner_issue()],
            {"license_policy": {"status": "undecided"}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "release_owner_decisions.json"
            state_path.write_text(json.dumps({
                "schema_version": 1,
                "kind": "release_owner_decision_state",
                "decisions": {
                    "license_policy": {
                        "status": "undecided",
                        "follow_up_artifacts": ["LICENSE"],
                    }
                },
            }), encoding="utf-8")

            report, exit_code = record_owner_decision(
                {
                    "timestamp": "2026-05-25T00:00:00",
                    "repo": "D:\\global-memory",
                    "release_verdict": "blocked",
                    "owner_decisions": decisions,
                    "decision_state_findings": [],
                },
                decision_id="license_policy",
                selected_option="mit",
                decided_by="owner",
                decided_at="2026-05-25",
                notes="owner selected MIT",
                dry_run=False,
                state_path=state_path,
            )
            saved = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["action"], "written")
        record = saved["decisions"]["license_policy"]
        self.assertEqual(record["status"], "decided")
        self.assertEqual(record["selected_option"], "mit")
        self.assertEqual(record["decided_by"], "owner")
        self.assertEqual(record["decided_at"], "2026-05-25")
        self.assertEqual(record["notes"], "owner selected MIT")
        self.assertEqual(record["follow_up_artifacts"], ["LICENSE"])


if __name__ == "__main__":
    unittest.main()
