#!/usr/bin/env python3
"""Tests for oss_readiness_check helpers."""

from __future__ import annotations

import json
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from oss_readiness_check import (  # noqa: E402
    REQUIRED_CI_COMMANDS,
    build_report,
    evaluate_catalog_freshness_data,
    evaluate_codex_work_skill_render_data,
    evaluate_ci_workflow_text,
    evaluate_maintenance_manifest_data,
    validate_doc_entrypoint_frontmatter,
)
from check_client_manifest import validate_claim_policy, validate_client  # noqa: E402

HARNESS_DIR = Path(__file__).resolve().parent.parent


def valid_workflow_text() -> str:
    return "\n".join([
        "name: OSS Readiness",
        "on: [push]",
        "jobs:",
        "  readiness:",
        "    runs-on: windows-latest",
        "    steps:",
        "      - uses: actions/checkout@v4",
        "      - run: python -m unittest harness.tests.test_release_issue_ledger harness.tests.test_verify_output_contracts harness.tests.test_oss_readiness_check harness.tests.test_governance_pulse",
        r"      - run: python harness\generate_catalog.py --check --json",
        r"      - run: python harness\verify\verify_output_contracts.py --json",
        r"      - run: python harness\maintain.py release-checkpoint --json",
        r"      - run: python harness\maintain.py release-gaps --json",
        r"      - run: python harness\maintain.py release-decisions --json",
        r"      - run: python harness\maintain.py release-check --profile oss --json",
        "",
    ])


class TestCiWorkflowEvaluation(unittest.TestCase):
    def test_valid_workflow_has_no_findings(self) -> None:
        evidence = evaluate_ci_workflow_text(valid_workflow_text(), ".github/workflows/oss-readiness.yml")

        self.assertTrue(evidence["yaml_valid"])
        self.assertGreaterEqual(evidence["step_count"], 5)
        self.assertEqual(evidence["required_commands"], REQUIRED_CI_COMMANDS)
        self.assertEqual(evidence["findings"], [])

    def test_invalid_yaml_reports_parse_failure(self) -> None:
        evidence = evaluate_ci_workflow_text("jobs: [\n", ".github/workflows/oss-readiness.yml")

        self.assertFalse(evidence["yaml_valid"])
        self.assertEqual(evidence["step_count"], 0)
        issues = {item["issue"] for item in evidence["findings"]}
        self.assertIn("parse_failed", issues)

    def test_missing_required_command_is_reported(self) -> None:
        text = valid_workflow_text().replace(
            r"      - run: python harness\maintain.py release-decisions --json",
            "      - run: python --version",
        )

        evidence = evaluate_ci_workflow_text(text, ".github/workflows/oss-readiness.yml")

        self.assertTrue(evidence["yaml_valid"])
        missing = [item for item in evidence["findings"] if item.get("issue") == "missing_command"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["command"], r"python harness\maintain.py release-decisions --json")


class TestDocEntrypointFrontmatter(unittest.TestCase):
    def test_docs_entrypoint_requires_status_and_last_updated(self) -> None:
        findings = validate_doc_entrypoint_frontmatter(
            "getting_started",
            "docs/getting-started.md",
            "---\ndoc_type: guide\nstatus: active\n---\n# Getting Started\n",
        )

        self.assertIn("missing_frontmatter_field", {item["issue"] for item in findings})
        self.assertEqual(findings[0]["field"], "last_updated")

    def test_docs_entrypoint_rejects_invalid_last_updated(self) -> None:
        findings = validate_doc_entrypoint_frontmatter(
            "getting_started",
            "docs/getting-started.md",
            "---\ndoc_type: guide\nstatus: active\nlast_updated: yesterday\n---\n# Getting Started\n",
        )

        self.assertIn("invalid_last_updated", {item["issue"] for item in findings})

    def test_non_docs_entrypoint_does_not_require_frontmatter(self) -> None:
        findings = validate_doc_entrypoint_frontmatter(
            "contributing",
            "CONTRIBUTING.md",
            "# Contributing\n",
        )

        self.assertEqual(findings, [])


class TestMaintenanceManifest(unittest.TestCase):
    def test_current_manifest_has_no_findings(self) -> None:
        manifest = json.loads((HARNESS_DIR / "maintenance_manifest.json").read_text(encoding="utf-8"))
        evidence = evaluate_maintenance_manifest_data(manifest)

        self.assertGreaterEqual(evidence["summary"]["commands"], 10)
        self.assertGreaterEqual(evidence["summary"]["scripts"], 20)
        self.assertEqual(evidence["findings"], [])

    def test_self_loop_manifest_uses_public_json_alias(self) -> None:
        manifest = json.loads((HARNESS_DIR / "maintenance_manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["commands"]["self_loop"]["scripts"]
        args_by_id = {item["id"]: item["args"] for item in scripts}

        self.assertEqual(args_by_id["self_loop_report"], ["--json"])
        self.assertEqual(args_by_id["meta_optimize"], ["--json"])

    def test_open_source_readiness_manifest_exposes_gap_and_owner_views(self) -> None:
        manifest = json.loads((HARNESS_DIR / "maintenance_manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["commands"]["open_source_readiness"]["scripts"]
        args_by_id = {item["id"]: item["args"] for item in scripts}

        self.assertEqual(args_by_id["maintain_release_gaps"], ["release-gaps", "--json"])
        self.assertEqual(args_by_id["maintain_release_checkpoint"], ["release-checkpoint", "--json"])
        self.assertEqual(args_by_id["maintain_release_checkpoint_strict"], ["release-checkpoint", "--strict", "--json"])
        self.assertEqual(args_by_id["maintain_release_decisions"], ["release-decisions", "--json"])
        self.assertEqual(args_by_id["maintain_release_check"], ["release-check", "--profile", "oss", "--json"])

    def test_capability_audit_manifest_exposes_dual_storage_json(self) -> None:
        manifest = json.loads((HARNESS_DIR / "maintenance_manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["commands"]["capability_audit"]["scripts"]
        by_id = {item["id"]: item for item in scripts}

        self.assertEqual(by_id["scan_dual_storage"]["path"], "scripts/scan_dual_storage.py")
        self.assertEqual(by_id["scan_dual_storage"]["args"], ["--json"])
        self.assertEqual(by_id["scan_dual_storage"]["category"], "read_only")

    def test_side_effect_manifest_exposes_owner_decision_dry_run(self) -> None:
        manifest = json.loads((HARNESS_DIR / "maintenance_manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["commands"]["side_effects"]["scripts"]
        by_id = {item["id"]: item for item in scripts}

        self.assertEqual(
            by_id["maintain_release_record_decision_dry_run"]["args"],
            ["release-record-decision", "--dry-run"],
        )
        self.assertEqual(
            by_id["maintain_release_record_decision_dry_run"]["category"],
            "owner_state_write",
        )

    def test_governance_pulse_manifest_exposes_once_log_write(self) -> None:
        manifest = json.loads((HARNESS_DIR / "maintenance_manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["commands"]["governance_pulse"]["scripts"]
        by_id = {item["id"]: item for item in scripts}

        self.assertEqual(by_id["governance_pulse_once"]["path"], "governance_pulse.py")
        self.assertEqual(by_id["governance_pulse_once"]["args"], ["--once"])
        self.assertEqual(by_id["governance_pulse_once"]["category"], "local_log_write")

    def test_manifest_reports_required_arg_drift(self) -> None:
        manifest = json.loads((HARNESS_DIR / "maintenance_manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["commands"]["self_loop"]["scripts"]
        for item in scripts:
            if item["id"] == "meta_optimize":
                item["args"] = ["--format", "json"]

        evidence = evaluate_maintenance_manifest_data(manifest)

        self.assertIn("required_args_mismatch", {item["issue"] for item in evidence["findings"]})

    def test_maintain_report_uses_public_meta_optimize_json_alias(self) -> None:
        source = (HARNESS_DIR / "maintain.py").read_text(encoding="utf-8")

        self.assertIn('str(script), "--json"', source)
        self.assertNotIn('str(script), "--format", "json"', source)


class TestClientManifestRules(unittest.TestCase):
    def test_context_brief_only_requires_generic_context_entrypoint(self) -> None:
        findings = validate_client(
            {
                "id": "generic_cli",
                "name": "Generic CLI",
                "status": "stable",
                "integration": "manual_cli",
                "support_level": "context_brief_only",
                "entrypoints": ["harness/maintain.py status --json"],
                "capabilities": {
                    "context_brief_cli": False,
                    "json_output_contract": True,
                },
                "limitations": [],
            },
            set(),
        )

        self.assertIn("missing_context_cli_entrypoint", {item["code"] for item in findings})

    def test_full_lifecycle_rejects_manual_cli_integration(self) -> None:
        findings = validate_client(
            {
                "id": "manual_full",
                "name": "Manual full client",
                "status": "stable",
                "integration": "manual_cli",
                "support_level": "full_lifecycle",
                "entrypoints": ["harness/scripts/client_context.py"],
                "capabilities": {
                    "install_or_bootstrap": True,
                    "automatic_context_injection": True,
                    "write_governance": True,
                    "audit_logging": True,
                    "rollback_or_disable": True,
                    "release_health_check": True,
                },
                "limitations": [],
            },
            set(),
        )

        self.assertIn("invalid_full_lifecycle_integration", {item["code"] for item in findings})

    def test_full_lifecycle_requires_capability_matrix(self) -> None:
        findings = validate_client(
            {
                "id": "api_client",
                "name": "API client",
                "status": "stable",
                "integration": "api",
                "support_level": "full_lifecycle",
                "entrypoints": ["harness/scripts/client_context.py"],
                "capabilities": {
                    "install_or_bootstrap": True,
                    "automatic_context_injection": True,
                    "write_governance": False,
                    "audit_logging": True,
                    "rollback_or_disable": True,
                    "release_health_check": True,
                },
                "limitations": [],
            },
            set(),
        )

        self.assertIn("missing_full_lifecycle_capability", {item["code"] for item in findings})

    def test_claim_policy_rejects_forbidden_overclaim(self) -> None:
        _summary, findings = validate_claim_policy({
            "claim_policy": {
                "required_phrases": [
                    {
                        "path": "README.md",
                        "contains": ["Claude Code harness + global memory"],
                    }
                ],
                "forbidden_phrases": [
                    {
                        "path": "README.md",
                        "contains": ["Claude Code harness + global memory"],
                    }
                ],
            }
        })

        self.assertIn("claim_policy_forbidden_phrase", {item["code"] for item in findings})


class TestCatalogFreshness(unittest.TestCase):
    def test_matching_catalogs_have_no_findings(self) -> None:
        evidence = evaluate_catalog_freshness_data([
            {
                "path": "harness/README.md",
                "expected": "# Harness\n",
                "actual": "# Harness\r\n",
                "exists": True,
            }
        ])

        self.assertEqual(evidence["summary"]["targets"], 1)
        self.assertEqual(evidence["summary"]["fresh"], 1)
        self.assertEqual(evidence["findings"], [])

    def test_stale_catalog_is_reported(self) -> None:
        evidence = evaluate_catalog_freshness_data([
            {
                "path": "skills/README.md",
                "expected": "# Skills\n| Skill | 描述 |\n",
                "actual": "# Skills\n",
                "exists": True,
            }
        ])

        self.assertEqual(evidence["summary"]["stale"], 1)
        self.assertIn("stale_catalog", {item["issue"] for item in evidence["findings"]})

    def test_missing_catalog_is_reported(self) -> None:
        evidence = evaluate_catalog_freshness_data([
            {
                "path": "agents/README.md",
                "expected": "# Agents\n",
                "actual": None,
                "exists": False,
            }
        ])

        self.assertEqual(evidence["summary"]["missing"], 1)
        self.assertIn("missing_catalog", {item["issue"] for item in evidence["findings"]})


class TestCodexWorkSkillRender(unittest.TestCase):
    def test_valid_rendered_codex_skill_has_no_findings(self) -> None:
        content = "\n".join([
            "---",
            "name: codex-work",
            "---",
            "AUTO-GENERATED from global-memory/skills/work/SKILL.md",
            "## Shared Work Mode Source",
            "## Codex Adapter",
            "intent_guard",
        ])

        evidence = evaluate_codex_work_skill_render_data(content, render_returncode=0, check_returncode=0)

        self.assertEqual(evidence["summary"]["findings"], 0)
        self.assertEqual(evidence["findings"], [])

    def test_rendered_codex_skill_requires_intent_guard(self) -> None:
        content = "\n".join([
            "---",
            "name: codex-work",
            "---",
            "AUTO-GENERATED from global-memory/skills/work/SKILL.md",
            "## Shared Work Mode Source",
            "## Codex Adapter",
        ])

        evidence = evaluate_codex_work_skill_render_data(content, render_returncode=0, check_returncode=0)

        self.assertIn("missing_required_snippet", {item["issue"] for item in evidence["findings"]})
        missing = {item.get("id") for item in evidence["findings"]}
        self.assertIn("intent_guard_rule", missing)

    def test_release_profile_includes_codex_work_skill_render_check(self) -> None:
        def result(check_id: str, status: str = "PASS") -> dict[str, object]:
            return {
                "id": check_id,
                "title": check_id,
                "status": status,
                "returncode": 0,
                "summary": "",
                "evidence": {},
                "next_action": "",
                "command": [],
            }

        patches = [
            patch("oss_readiness_check.check_registry", lambda: result("capability_registry")),
            patch("oss_readiness_check.check_capability_manifest", lambda: result("capability_manifest")),
            patch("oss_readiness_check.check_maintenance_manifest", lambda: result("maintenance_manifest")),
            patch("oss_readiness_check.check_catalog_freshness", lambda: result("catalog_freshness")),
            patch("oss_readiness_check.check_client_manifest", lambda: result("client_portability")),
            patch("oss_readiness_check.check_docs_entrypoints", lambda: result("docs_entrypoints")),
            patch("oss_readiness_check.check_ci_workflow", lambda: result("ci_workflow")),
            patch("oss_readiness_check.check_project_metadata", lambda: result("project_metadata")),
            patch("oss_readiness_check.check_publish_scope", lambda: result("publish_scope")),
            patch("oss_readiness_check.check_source_export_plan", lambda: result("source_export_plan")),
            patch("oss_readiness_check.check_external_source_safety", lambda: result("external_source_safety")),
            patch("oss_readiness_check.check_hook_alignment", lambda: result("hook_alignment")),
            patch("oss_readiness_check.check_bootstrap", lambda: result("bootstrap_runtime")),
            patch("oss_readiness_check.check_codex_work_skill_render", lambda: result("codex_work_skill_render", "WARNING")),
            patch("oss_readiness_check.check_hardcoded_paths", lambda: result("hardcoded_paths")),
            patch("oss_readiness_check.check_path_config", lambda: result("path_config")),
            patch("oss_readiness_check.check_governance_gate", lambda: result("governance_gate")),
            patch("oss_readiness_check.check_smoke", lambda: result("smoke_test")),
        ]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            report = build_report(strict=False, skip_output_contracts=True)

        self.assertEqual(report["summary"]["WARNING"], 1)
        self.assertEqual(report["warnings"][0]["id"], "codex_work_skill_render")

    def test_private_audit_profile_does_not_block_on_publication_only_gaps(self) -> None:
        def result(check_id: str, status: str = "PASS") -> dict[str, object]:
            return {
                "id": check_id,
                "title": check_id,
                "status": status,
                "returncode": 1 if status == "BLOCKER" else 0,
                "summary": "",
                "evidence": {},
                "next_action": "",
                "command": [],
            }

        patches = [
            patch("oss_readiness_check.check_registry", lambda: result("capability_registry")),
            patch("oss_readiness_check.check_capability_manifest", lambda: result("capability_manifest")),
            patch("oss_readiness_check.check_maintenance_manifest", lambda: result("maintenance_manifest")),
            patch("oss_readiness_check.check_catalog_freshness", lambda: result("catalog_freshness")),
            patch("oss_readiness_check.check_client_manifest", lambda: result("client_portability")),
            patch("oss_readiness_check.check_docs_entrypoints", lambda: result("docs_entrypoints")),
            patch("oss_readiness_check.check_ci_workflow", lambda: result("ci_workflow")),
            patch("oss_readiness_check.check_project_metadata", lambda: result("project_metadata", "BLOCKER")),
            patch("oss_readiness_check.check_publish_scope", lambda: result("publish_scope", "BLOCKER")),
            patch("oss_readiness_check.check_source_export_plan", lambda: result("source_export_plan", "BLOCKER")),
            patch("oss_readiness_check.check_external_source_safety", lambda: result("external_source_safety")),
            patch("oss_readiness_check.check_hook_alignment", lambda: result("hook_alignment")),
            patch("oss_readiness_check.check_bootstrap", lambda: result("bootstrap_runtime")),
            patch("oss_readiness_check.check_codex_work_skill_render", lambda: result("codex_work_skill_render")),
            patch("oss_readiness_check.check_hardcoded_paths", lambda: result("hardcoded_paths")),
            patch("oss_readiness_check.check_path_config", lambda: result("path_config")),
            patch("oss_readiness_check.check_governance_gate", lambda: result("governance_gate")),
            patch("oss_readiness_check.check_smoke", lambda: result("smoke_test")),
        ]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            report = build_report(strict=False, skip_output_contracts=True, profile="private-audit")

        self.assertEqual(report["profile"], "private-audit")
        self.assertEqual(report["summary"]["BLOCKER"], 0)
        self.assertEqual(report["summary"]["WARNING"], 3)
        self.assertEqual(report["exit_code"], 0)
        demoted = {check["id"]: check for check in report["warnings"]}
        self.assertEqual(set(demoted), {"project_metadata", "publish_scope", "source_export_plan"})
        self.assertTrue(all(check["evidence"]["private_audit"]["accepted_private_publication_gap"] for check in demoted.values()))


if __name__ == "__main__":
    unittest.main()
