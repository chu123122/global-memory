#!/usr/bin/env python3
"""Tests for output-contract validators."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verify"))

from verify_output_contracts import (  # noqa: E402
    ContractCase,
    validate_capability_manifest_contract,
    validate_check_prepare_contract,
    validate_client_context_contract,
    validate_client_manifest_contract,
    validate_dual_storage_scan_contract,
    validate_export_source_scope_contract,
    validate_external_source_safety_contract,
    validate_gate_check_contract,
    validate_generate_catalog_contract,
    validate_harness_tasks_contract,
    validate_hook_alignment_contract,
    validate_maintain_status_contract,
    validate_meta_optimize_contract,
    validate_analyze_retrieve_log_contract,
    validate_orphan_script_scan_contract,
    validate_oss_readiness_contract,
    validate_publish_scope_contract,
    validate_release_checkpoint_contract,
    validate_release_gap_table_contract,
    validate_release_issue_ledger_contract,
    validate_release_owner_decision_record_contract,
    validate_release_owner_decisions_contract,
    validate_release_owner_decision_template_contract,
    validate_skill_audit_contract,
    validate_self_loop_report_contract,
    validate_smoke_test_contract,
    validate_work_context_pack_contract,
)


def case() -> ContractCase:
    return ContractCase("oss_readiness_check", ["oss_readiness_check.py"])


def ledger_case() -> ContractCase:
    return ContractCase("release_issue_ledger", ["release_issue_ledger.py"])


def gap_table_case() -> ContractCase:
    return ContractCase("release_gap_table", ["release_issue_ledger.py", "--gap-table-only"])


def decision_template_case() -> ContractCase:
    return ContractCase("release_owner_decision_template", ["release_issue_ledger.py", "--decision-template"])


def owner_decisions_case() -> ContractCase:
    return ContractCase("release_owner_decisions", ["release_issue_ledger.py", "--owner-decisions-only"])


def record_decision_case() -> ContractCase:
    return ContractCase("maintain_release_record_decision_dry_run", ["maintain.py", "release-record-decision", "--dry-run"])


def publish_scope_record_decision_case() -> ContractCase:
    return ContractCase("maintain_release_record_publish_scope_dry_run", ["maintain.py", "release-record-decision", "--dry-run"])


def status_case() -> ContractCase:
    return ContractCase("maintain_status", ["maintain.py", "status", "--json"])


def harness_tasks_case() -> ContractCase:
    return ContractCase("harness_tasks", ["harness_status.py", "--tasks", "--json"])


def smoke_case() -> ContractCase:
    return ContractCase("smoke_test", ["smoke_test.py", "--json"])


def orphan_scan_case() -> ContractCase:
    return ContractCase("scan_orphan_scripts", ["scan_orphan_scripts.py", "--strict", "--json"])


def dual_storage_case() -> ContractCase:
    return ContractCase("scan_dual_storage", ["scan_dual_storage.py", "--json"])


def capability_manifest_case() -> ContractCase:
    return ContractCase("check_capability_manifest", ["check_capability_manifest.py", "--json"])


def client_manifest_case() -> ContractCase:
    return ContractCase("check_client_manifest", ["check_client_manifest.py", "--json"])


def client_context_case() -> ContractCase:
    return ContractCase("client_context", ["client_context.py", "--json"])


def generate_catalog_case() -> ContractCase:
    return ContractCase("generate_catalog_check", ["generate_catalog.py", "--check", "--json"])


def skill_audit_case() -> ContractCase:
    return ContractCase("audit_skill_all", ["audit_skill.py", "--all", "--json"])


def analyze_retrieve_log_case() -> ContractCase:
    return ContractCase("analyze_retrieve_log", ["analyze_retrieve_log.py", "--json"])


def work_context_case() -> ContractCase:
    return ContractCase("work_context_pack", ["work_context_pack.py", "--json"])


def work_context_intent_case() -> ContractCase:
    return ContractCase("work_context_pack_intent_guard", ["work_context_pack.py", "--intent", "新开一个维护 task", "--json"])


def check_prepare_case() -> ContractCase:
    return ContractCase("check_prepare", ["check_prepare.py", "--json"])


def self_loop_case() -> ContractCase:
    return ContractCase("self_loop_report", ["self_loop_report.py", "--json"])


def meta_optimize_case() -> ContractCase:
    return ContractCase("meta_optimize", ["meta_optimize.py", "--json"])


def gate_case() -> ContractCase:
    return ContractCase("gate_check", ["gate_check.py", "--json"])


def hook_alignment_case() -> ContractCase:
    return ContractCase("check_hook_alignment", ["check_hook_alignment.py", "--strict", "--json"])


def external_safety_case() -> ContractCase:
    return ContractCase("scan_external_safety", ["scan_external_safety.py", "--json"])


def publish_scope_case() -> ContractCase:
    return ContractCase("check_publish_scope", ["check_publish_scope.py", "--json"])


def export_source_case() -> ContractCase:
    return ContractCase("export_source_scope", ["export_source_scope.py", "--json"])


def valid_status_report() -> dict:
    return {
        "timestamp": "2026-05-25T00:00:00+08:00",
        "repo": "D:\\global-memory",
        "mode": "status",
        "capabilities": {
            "status": "read-only control-plane snapshot",
            "doctor": "read-only aggregate health check",
            "release-check": "read-only OSS readiness verdict",
            "release-checkpoint": "read-only OSS checkpoint: safety, release, ledger, gap, and manifest summaries",
            "release-gaps": "read-only categorized release gap table",
            "release-decisions": "read-only owner decision queue",
            "fix": "local safe fixes only; no commit or push",
            "sync": "checkpoint commit and push",
            "ai": "diagnose/plan only in V1; execute is disabled",
        },
    }


def valid_release_checkpoint_report() -> dict:
    def check(check_id: str, summary: dict, verdict: str = "ok", payload: dict | None = None) -> dict:
        if payload is None:
            payload = {
                "kind": check_id,
                "verdict": verdict,
                "summary": summary,
            }
        return {
            "id": check_id,
            "returncode": 0,
            "parsed": True,
            "summary": "ok",
            "command": ["python", "tool.py", "--json"],
            "payload": payload,
        }

    gap_summary = {"owner_decisions": 1, "code_remediation": 0, "docs_publish_scope_governance": 0, "deferred": 1, "open_by_gap_type": {"owner_decision": 1}}
    gap_payload = {
        "kind": "release_gap_table",
        "verdict": None,
        "summary": gap_summary,
        "remaining_gap_table": valid_ledger_report()["remaining_gap_table"],
    }
    decision_template_payload = valid_decision_template_report()

    return {
        "schema_version": 1,
        "kind": "release_checkpoint",
        "timestamp": "2026-05-26T00:00:00+08:00",
        "repo": "D:\\global-memory",
        "release_verdict": "blocked",
        "strict": False,
        "summary": {
            "release_pass": 15,
            "release_warnings": 1,
            "release_blockers": 2,
            "release_check_mode": "skip_output_contracts",
            "release_check_output_contracts_included": False,
            "owner_decisions": 2,
            "code_remediation": 0,
            "docs_publish_scope_governance": 1,
            "deferred": 1,
            "external_source_blockers": 0,
            "external_source_warnings": 0,
            "owner_decision_templates": 1,
            "owner_decision_records": {"valid_records": 2, "invalid_records": 0},
        },
        "checks": [
            check("external_source_safety", {"blockers": 0, "warnings": 0}),
            check("release_check", {"PASS": 15, "WARNING": 1, "BLOCKER": 2}, "blocked"),
            check("release_issue_ledger", {"open": 3, "resolved": 14}),
            check("release_gaps", gap_summary, payload=gap_payload),
            check("release_decisions", {"owner_decisions": 2, "ready": 0, "not_ready": 2}),
            check("release_decision_template", {"templates": 1, "owner_decisions": 1}, payload=decision_template_payload),
            check("capability_manifest", {"capabilities": 18, "ERROR": 0, "WARNING": 0}),
            check("client_manifest", {"clients": 3, "ERROR": 0, "WARNING": 1}),
            check("publish_scope_manifest", {"private_tracked_paths": 175, "unclassified_tracked_paths": 0}, "blocked"),
        ],
        "exit_code": 0,
    }


def valid_harness_tasks_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "harness_tasks",
        "summary": {
            "active": 3,
            "archived": 2,
            "total": 5,
            "active_by_stage": {"implementation": 1, "missing": 1, "unknown": 1},
            "archived_by_stage": {"archived": 1, "implementation": 1},
            "missing_active": 1,
            "unknown_active": 1,
        },
        "active": [
            {
                "name": "alpha",
                "stage": "implementation",
                "brief": "Alpha is active.",
                "path": "tasks/active/alpha",
            },
            {
                "name": "beta",
                "stage": "missing",
                "brief": "(task directory missing)",
                "path": "tasks/active/beta",
            },
            {
                "name": "gamma",
                "stage": "unknown",
                "brief": "(no brief)",
                "path": "tasks/active/gamma",
            },
        ],
        "archived": [
            {
                "name": "old-alpha",
                "stage": "implementation",
                "brief": "Old active work.",
                "path": "tasks/archived/old-alpha",
            },
            {
                "name": "old-beta",
                "stage": "archived",
                "brief": "(no brief)",
                "path": "tasks/archived/old-beta",
            },
        ],
    }


def valid_smoke_report() -> dict:
    return {
        "timestamp": "2026-05-26 01:05",
        "duration": 1.9,
        "summary": {"PASS": 2, "WARN": 0, "FAIL": 0, "SKIP": 1},
        "results": [
            {
                "script": "verify/verify_all.py",
                "category": "run",
                "status": "PASS",
                "exit_code": 0,
                "duration": 0.68,
                "detail": "",
            },
            {
                "script": "verify/verify_memory.py",
                "category": "usage",
                "status": "PASS",
                "exit_code": 1,
                "duration": 0.08,
                "detail": "printed usage",
            },
            {
                "script": "auto_sync_daemon.py",
                "category": "skip",
                "status": "SKIP",
                "exit_code": -1,
                "duration": 0.0,
                "detail": "has side effects, skipped",
            },
        ],
    }


def valid_self_loop_report() -> dict:
    return {
        "schema_version": 1,
        "mode": "self-loop-overview",
        "inputs": {
            "repo_root": "repo",
            "tasks_root": "tasks/active",
            "logs_root": "logs",
            "days": 7,
        },
        "enabled_task_fallbacks": [],
        "optimization_ledger": {
            "count": 1,
            "latest": [
                {
                    "optimization_id": "OPT-1",
                    "status": "applied",
                    "rollback": "disable config",
                }
            ],
        },
        "fallback_cost": {
            "schema_version": 1,
            "summary": {
                "total_retrieve_calls": 10,
                "fallback_triggered": 1,
            },
        },
        "fallback_candidates": {
            "schema_version": 1,
            "summary": {
                "candidate_tasks": 3,
                "accept": 1,
                "already_enabled": 0,
                "review": 1,
                "reject": 1,
            },
            "candidates": [
                {"summary": {"task": "alpha", "recommendation": "ACCEPT"}},
                {"summary": {"task": "beta", "recommendation": "REVIEW"}},
            ],
        },
        "assurance": [],
    }


def valid_meta_optimize_report() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-05-26T01:43:12",
        "mode": "read-only",
        "inputs": {
            "logs_root": "logs",
            "tasks_root": "tasks/active",
            "days": 7,
        },
        "summary": {
            "finding_count": 2,
            "by_severity": {"high": 1, "medium": 1},
        },
        "user_visible": {
            "verdict": "READY_FOR_PROPOSAL",
            "conclusion": "Current top issue.",
            "recommended_first_action": "Write a read-only proposal.",
            "do_not_do_now": "Do not apply automatically.",
            "experience_snapshot": {
                "window_days": 7,
                "has_single_recommended_action": True,
            },
            "top_opportunities": [],
        },
        "findings": [
            {
                "id": "MO-001",
                "severity": "high",
                "area": "retrieve",
                "symptom": "Noisy pointer.",
                "evidence": ["a.md"],
                "suggested_change": "Reduce noisy keyword.",
                "consumer": "harness_retrieve.py",
                "risk_if_ignored": "Noise remains.",
                "source": "logs/health_checks.jsonl",
                "priority_rank": 1,
                "actionability": "actionable",
            },
            {
                "id": "MO-002",
                "severity": "medium",
                "area": "sync",
                "symptom": "Large WIP set.",
                "evidence": [],
                "suggested_change": "Split checkpoint.",
                "consumer": "maintain.py sync",
                "risk_if_ignored": "Sync keeps skipping.",
                "source": "logs/maintain.jsonl",
                "priority_rank": 2,
                "actionability": "actionable",
            },
        ],
    }


def valid_client_context_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "client_context",
        "client_id": "generic_cli",
        "contract": "global-memory.context-brief.v1",
        "task": "unknown",
        "stage": None,
        "ok": True,
        "error": "",
        "brief": {
            "schema_version": "v2",
            "task": "unknown",
            "stage": None,
            "handoff_path": "",
            "relevant_pointers": [
                {
                    "path": "docs/capabilities.md",
                    "why": "capability overview",
                    "summary": "Capability registry overview.",
                }
            ],
            "load_strategy": "just_in_time",
            "warnings": ["ambiguous_keyword:test"],
        },
        "brief_text": (
            "schema_version: v2\n"
            "task: unknown\n"
            "stage: unknown\n"
            "handoff_path: (none)\n"
            "relevant_pointers:\n"
            "  - path: docs/capabilities.md\n"
            "    why: capability overview\n"
            "load_strategy: just_in_time\n"
            "warnings:\n"
            "  - ambiguous_keyword:test\n"
        ),
        "elapsed_ms": 15.2,
    }


def failed_client_context_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "client_context",
        "client_id": "generic_cli",
        "contract": "global-memory.context-brief.v1",
        "task": "unknown",
        "stage": None,
        "ok": False,
        "error": "empty_query",
        "brief": None,
        "brief_text": "",
        "elapsed_ms": 0.0,
    }


def valid_generate_catalog_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "catalog_freshness_check",
        "repo": "D:\\global-memory",
        "verdict": "ok",
        "summary": {
            "targets": 3,
            "fresh": 3,
            "stale": 0,
            "missing": 0,
            "findings": 0,
        },
        "targets": [
            {
                "path": "agents/README.md",
                "exists": True,
                "fresh": True,
                "expected_lines": 17,
                "actual_lines": 17,
            },
            {
                "path": "skills/README.md",
                "exists": True,
                "fresh": True,
                "expected_lines": 16,
                "actual_lines": 16,
            },
            {
                "path": "harness/README.md",
                "exists": True,
                "fresh": True,
                "expected_lines": 120,
                "actual_lines": 120,
            },
        ],
        "findings": [],
    }


def valid_skill_audit_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "skill_audit",
        "level": "CONDITIONAL",
        "summary": {
            "checked_skills": 3,
            "level_counts": {"PASS": 1, "WARNING": 1, "CONDITIONAL": 1, "FAIL": 0},
            "issue_counts": {"ERROR": 0, "WARNING": 3},
            "by_issue_code": [
                {"level": "WARNING", "code": "deployed-extra", "count": 1},
                {"level": "WARNING", "code": "missing-reference", "count": 1},
                {"level": "WARNING", "code": "weak-trigger", "count": 1},
            ],
            "deployed_extras": 1,
        },
        "skills": [
            {
                "name": "work",
                "path": "D:\\global-memory\\skills\\work\\v1",
                "level": "PASS",
                "line_count": 278,
                "estimated_tokens": 1773,
                "issues": [],
            },
            {
                "name": "skill-auditor",
                "path": "D:\\global-memory\\skills\\skill-auditor\\v1",
                "level": "CONDITIONAL",
                "line_count": 79,
                "estimated_tokens": 446,
                "issues": [
                    {
                        "level": "WARNING",
                        "code": "weak-trigger",
                        "message": "description does not clearly state trigger/use conditions",
                    },
                    {
                        "level": "WARNING",
                        "code": "missing-reference",
                        "message": "referenced path does not exist: references/design-tradeoffs.md",
                    },
                ],
            },
            {
                "name": "note",
                "path": "C:\\Users\\XINDONG\\.claude\\skills\\note",
                "level": "WARNING",
                "issues": [
                    {
                        "level": "WARNING",
                        "code": "deployed-extra",
                        "message": "deployed skill is not declared in bootstrap.SKILLS",
                    }
                ],
            },
        ],
    }


def unresolved_check_prepare_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "check_prepare",
        "level": "WARNING",
        "task": None,
        "summary": "No task resolved. Provide an active task name or absolute path.",
        "candidates": ["alpha", "beta"],
        "review_docs": [],
    }


def valid_check_prepare_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "check_prepare",
        "level": "WARNING",
        "task": "alpha",
        "task_dir": "tasks/active/alpha",
        "resolution": "exact",
        "stage": "implementation",
        "diagnostic": "",
        "required_docs": ["SPEC.md", "HANDOFF.md"],
        "missing_required_docs": ["HANDOFF.md"],
        "review_docs": ["tasks/active/alpha/SPEC.md"],
        "doc_scans": [
            {
                "path": "tasks/active/alpha/SPEC.md",
                "name": "SPEC.md",
                "bytes": 120,
                "line_count": 12,
                "todo_or_placeholders": [{"line": 5, "text": "TODO: fill tests"}],
                "empty_headings": ["## Tests"],
                "too_long": False,
            }
        ],
        "warnings": [
            "Missing required docs: HANDOFF.md",
            "SPEC.md has TODO/TBD/placeholders",
            "SPEC.md has empty headings",
        ],
        "summary": "task=alpha; stage=implementation; review_docs=1; warnings=3",
        "prompt_inputs": [
            "【任务名】：alpha",
            "【待审文档】：",
            "- tasks/active/alpha/SPEC.md",
            "【项目根目录】：tasks/active/alpha",
        ],
        "candidates": [],
    }


def valid_work_context_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "work_context",
        "level": "PASS",
        "task": "demo-task",
        "task_dir": "D:\\ClaudeTasks\\active\\demo-task",
        "resolution": "exact",
        "confidence": 1.0,
        "stage": "v2-active",
        "diagnostic": None,
        "memory_line": "",
        "existing_docs": ["core/HANDOFF.md"],
        "missing_required_docs": [],
        "doc_snippets": {"core/HANDOFF.md": "HANDOFF"},
        "progress": "next step",
        "summary": "task=demo-task; stage=v2-active; docs=1 existing/0 missing required",
        "recommended_next_step": "Read core/HANDOFF.md.",
        "required_reads": ["D:\\ClaudeTasks\\active\\demo-task\\core\\HANDOFF.md"],
        "candidates": [],
    }


def valid_analyze_retrieve_log_report() -> dict:
    return {
        "schema_version": "v2",
        "total_calls": 5,
        "zero_hit_calls": 2,
        "zero_hit_rate": 0.4,
        "avg_elapsed_ms": 17.5,
        "hit_count_distribution": {"0": 2, "1": 2, "3": 1},
        "top1_path_top10": [["docs/capabilities.md", 2], ["README.md", 1]],
        "noisy_kw_candidates": [{"why": "common keyword", "freq": 3, "share": 0.6}],
        "namespace_distribution": {"docs": 3, "tasks": 2},
        "miss_queries_sample": [
            {"ts": "2026-05-26T00:00:00+08:00", "task": "alpha", "query": "missing pointer"},
            {"ts": None, "task": None, "query": None},
        ],
        "miss_queries_total": 2,
    }


def valid_oss_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "oss_readiness_check",
        "summary": {"PASS": 13, "WARNING": 0, "BLOCKER": 2},
        "checks": [
            {
                "id": "docs_entrypoints",
                "status": "PASS",
                "summary": "checked=6, frontmatter_checked=5, findings=0",
                "evidence": {"frontmatter_checked": 5, "findings": []},
            },
            {
                "id": "ci_workflow",
                "status": "PASS",
                "summary": "yaml_valid=true, steps=11, required_commands=7, findings=0",
                "evidence": {
                    "workflow": ".github/workflows/oss-readiness.yml",
                    "yaml_valid": True,
                    "step_count": 11,
                    "required_commands": [
                        "python -m unittest harness.tests.test_release_issue_ledger harness.tests.test_verify_output_contracts harness.tests.test_oss_readiness_check harness.tests.test_governance_pulse",
                        r"python harness\generate_catalog.py --check --json",
                        r"python harness\verify\verify_output_contracts.py --json",
                        r"python harness\maintain.py release-checkpoint --json",
                        r"python harness\maintain.py release-gaps --json",
                        r"python harness\maintain.py release-decisions --json",
                        r"python harness\maintain.py release-check --profile oss --json",
                    ],
                    "findings": [],
                },
            },
            {
                "id": "maintenance_manifest",
                "status": "PASS",
                "summary": "commands=13, scripts=27, required=5, findings=0",
                "evidence": {
                    "summary": {
                        "commands": 13,
                        "scripts": 27,
                        "required_commands": 7,
                        "findings": 0,
                    },
                    "findings": [],
                },
            },
            {
                "id": "catalog_freshness",
                "status": "PASS",
                "summary": "targets=3, stale=0, missing=0, findings=0",
                "evidence": {
                    "summary": {
                        "targets": 3,
                        "fresh": 3,
                        "stale": 0,
                        "missing": 0,
                        "findings": 0,
                    },
                    "findings": [],
                },
            },
            {
                "id": "client_portability",
                "status": "WARNING",
                "summary": "scope=claude_code_harness_with_generic_context_cli, stable_full_lifecycle=1, stable_context=2, claim_policy_checked=3, warnings=1, errors=0",
                "evidence": {
                    "summary": {
                        "clients": 3,
                        "stable_full_lifecycle_clients": 1,
                        "stable_context_clients": 2,
                        "claim_policy_checked": 3,
                        "WARNING": 1,
                        "ERROR": 0,
                    },
                    "readiness": {
                        "full_lifecycle_multi_client": {
                            "ready": False,
                            "stable_clients": 1,
                            "required_clients": 2,
                        },
                        "context_cli": {
                            "ready": True,
                            "stable_clients": 2,
                            "required_clients": 2,
                        },
                    },
                    "contracts": valid_client_contracts(),
                    "clients": [
                        {
                            "id": "claude_code",
                            "status": "stable",
                            "integration": "hooks_settings",
                            "support_level": "full_lifecycle",
                        },
                        {
                            "id": "generic_cli",
                            "status": "stable",
                            "integration": "manual_cli",
                            "support_level": "context_brief_only",
                        },
                    ],
                    "claim_policy": {"checked": 3, "required": 3, "findings": []},
                    "remediation_plan": valid_client_remediation_plan(),
                    "findings": [{"level": "WARNING", "code": "single_full_lifecycle_client_scope"}],
                },
            },
            {
                "id": "project_metadata",
                "status": "BLOCKER",
                "summary": "checked=6, findings=1",
                "evidence": {
                    "decision_plan": {
                        "decision": "license_policy",
                        "owner": "project_owner",
                        "options": [{"id": "mit"}],
                    }
                },
            },
            {
                "id": "publish_scope",
                "status": "BLOCKER",
                "summary": "tracked_private_paths=175, unclassified_tracked_paths=0",
                "evidence": {
                    "decision_plan": {
                        "decision": "publish_scope_boundary",
                        "owner": "project_owner",
                        "options": [{"id": "split_clean_source_repository"}],
                    }
                },
            },
        ],
    }


def valid_ledger_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "release_issue_ledger",
        "summary": {
            "open": 1,
            "resolved": 0,
            "deferred": 1,
            "blockers": 1,
            "warnings": 0,
            "open_by_gap_type": {"owner_decision": 1},
            "open_by_owner": {"project_owner": 1},
            "owner_decisions": 1,
            "decision_state_findings": 0,
            "owner_decision_records": {
                "valid_records": 1,
                "invalid_records": 0,
                "missing_records": 0,
                "stale_records": 0,
                "record_status_counts": {"undecided": 1},
            },
        },
        "remaining_gap_table": {
            "owner_decisions": [
                {
                    "issue_id": "oss-project_metadata",
                    "check_id": "project_metadata",
                    "severity": "blocker",
                    "gap_type": "owner_decision",
                    "owner": "project_owner",
                    "title": "Open-source project metadata is explicit",
                    "summary": "checked=6, findings=1",
                    "resolution": "Choose the project license.",
                    "next_action": "Choose a license.",
                    "decision": "license_policy",
                    "record_status": "undecided",
                    "decision_doc": "docs/license-decision.md",
                    "required_artifacts": ["LICENSE"],
                    "required_when": {},
                    "allowed_options": ["mit"],
                    "record_dry_run_command": [
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
                    "record_write_command": [
                        "python",
                        r"harness\maintain.py",
                        "release-record-decision",
                        "--write",
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
                    "record_gate_effect": {
                        "effect": "records_owner_choice_only",
                        "clears_release_blocker": False,
                        "next_check": "rerun release-check after required artifacts or publish-scope changes are complete",
                    },
                    "gate_unblock_requirements": {
                        "status": "blocked_until_requirements_clear",
                        "requirements": [
                            {"kind": "required_artifacts", "values": ["LICENSE"]},
                        ],
                    },
                }
            ],
            "code_remediation": [],
            "docs_publish_scope_governance": [],
            "deferred": [
                {
                    "issue_id": "oss-legacy_health",
                    "check_id": "legacy_health",
                    "severity": "info",
                    "gap_type": "content_hygiene",
                    "owner": "maintainer",
                    "title": "Legacy repository health has no errors",
                    "summary": "deferred",
                    "resolution": "Run when cleaning content.",
                    "next_action": "Run explicitly.",
                }
            ],
        },
        "owner_decisions": [
            {
                "issue_id": "oss-project_metadata",
                "check_id": "project_metadata",
                "severity": "blocker",
                "owner": "project_owner",
                "decision": "license_policy",
                "ready": False,
                "gate_ready": False,
                "record_ready": False,
                "record_status": "undecided",
                "selected_option": "",
                "decided_by": "",
                "decided_at": "",
                "record_present": True,
                "record_valid": True,
                "record_findings": [],
                "decision_state_file": "harness/release_owner_decisions.json",
                "decision_doc": "docs/license-decision.md",
                "required_artifacts": ["LICENSE"],
                "required_when": {},
                "record_gate_effect": {
                    "effect": "records_owner_choice_only",
                    "clears_release_blocker": False,
                    "next_check": "rerun release-check after required artifacts or publish-scope changes are complete",
                },
                "gate_unblock_requirements": {
                    "status": "blocked_until_requirements_clear",
                    "requirements": [
                        {"kind": "required_artifacts", "values": ["LICENSE"]},
                    ],
                },
                "options": [{"id": "mit"}],
            }
        ],
        "decision_state_findings": [],
        "issues": [
            {
                "issue_id": "oss-project_metadata",
                "check_id": "project_metadata",
                "state": "open",
                "severity": "blocker",
                "gap": {
                    "type": "owner_decision",
                    "owner": "project_owner",
                    "resolution": "Choose the project license.",
                },
                "evidence": {
                    "decision_plan": {
                        "decision": "license_policy",
                        "owner": "project_owner",
                        "options": [{"id": "mit"}],
                    }
                },
            },
            {
                "issue_id": "oss-legacy_health",
                "check_id": "legacy_health",
                "state": "deferred",
                "severity": "info",
                "gap": {
                    "type": "content_hygiene",
                    "owner": "maintainer",
                    "resolution": "Run when cleaning content.",
                },
            },
        ],
    }


def valid_decision_template_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "release_owner_decision_template",
        "decision_state_file": "harness/release_owner_decisions.json",
        "summary": {
            "templates": 1,
            "owner_decisions": 1,
        },
        "state_patch_template": {
            "decisions": {
                "license_policy": {
                    "status": "decided",
                    "selected_option": "<one of allowed_options.id>",
                    "decided_by": "<owner>",
                    "decided_at": "YYYY-MM-DD",
                    "notes": "",
                }
            }
        },
        "templates": [
            {
                "decision": "license_policy",
                "issue_id": "oss-project_metadata",
                "check_id": "project_metadata",
                "owner": "project_owner",
                "record_status": "undecided",
                "current_selected_option": "",
                "record_valid": True,
                "record_findings": [],
                "decision_doc": "docs/license-decision.md",
                "decision_state_file": "harness/release_owner_decisions.json",
                "summary": "checked=6, findings=1",
                "resolution": "Choose the project license.",
                "allowed_options": [{"id": "mit", "action": "add_mit_license", "effect": "Permissive reuse."}],
                "required_update_fields": ["status", "selected_option", "decided_by", "decided_at"],
                "state_patch_template": {
                    "status": "decided",
                    "selected_option": "<one of allowed_options.id>",
                    "decided_by": "<owner>",
                    "decided_at": "YYYY-MM-DD",
                    "notes": "",
                },
                "required_artifacts": ["LICENSE"],
                "required_when": {},
                "record_gate_effect": {
                    "effect": "records_owner_choice_only",
                    "clears_release_blocker": False,
                    "next_check": "rerun release-check after required artifacts or publish-scope changes are complete",
                },
                "gate_unblock_requirements": {
                    "status": "blocked_until_requirements_clear",
                    "requirements": [
                        {"kind": "required_artifacts", "values": ["LICENSE"]},
                    ],
                },
                "gate_note": "Recording the owner decision is necessary but may not make release-check pass until required artifacts or publish-scope changes are also present.",
            }
        ],
        "decision_state_findings": [],
    }


def valid_record_decision_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "release_owner_decision_record",
        "dry_run": True,
        "action": "dry_run",
        "decision_state_file": "harness/release_owner_decisions.json",
        "decision": "license_policy",
        "selected_option": "no_public_license",
        "allowed_options": ["mit", "no_public_license"],
        "valid": True,
        "findings": [],
        "record": {
            "status": "decided",
            "selected_option": "no_public_license",
            "decided_by": "contract-test",
            "decided_at": "2026-05-25",
            "notes": "",
        },
        "previous_record": {"status": "undecided"},
        "proposed_record": {
            "status": "decided",
            "selected_option": "no_public_license",
            "decided_by": "contract-test",
            "decided_at": "2026-05-25",
            "notes": "",
        },
        "required_artifacts": ["LICENSE"],
        "required_when": {},
        "record_gate_effect": {
            "effect": "records_owner_choice_only",
            "clears_release_blocker": False,
            "next_check": "rerun release-check after required artifacts or publish-scope changes are complete",
        },
        "gate_unblock_requirements": {
            "status": "blocked_until_requirements_clear",
            "requirements": [
                {"kind": "required_artifacts", "values": ["LICENSE"]},
            ],
        },
        "gate_note": "Recording the owner decision is necessary but may not make release-check pass until required artifacts or publish-scope changes are also present.",
    }


def valid_publish_scope_record_decision_report() -> dict:
    report = valid_record_decision_report()
    report["decision"] = "publish_scope_boundary"
    report["selected_option"] = "keep_private_maturity_audit"
    report["allowed_options"] = ["split_clean_source_repository", "keep_private_maturity_audit"]
    report["required_artifacts"] = []
    report["required_when"] = {
        "private_tracked_paths": 175,
        "unclassified_tracked_paths": 0,
    }
    report["gate_unblock_requirements"] = {
        "status": "blocked_until_requirements_clear",
        "requirements": [
            {
                "kind": "required_conditions",
                "values": {
                    "private_tracked_paths": 175,
                    "unclassified_tracked_paths": 0,
                },
            },
        ],
    }
    for key in ("record", "proposed_record"):
        report[key]["selected_option"] = "keep_private_maturity_audit"
        report[key]["decided_at"] = "2026-05-26"
    return report


def valid_orphan_scan_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "orphan_script_scan",
        "verdict": "ok",
        "scanned_root": "D:\\global-memory\\harness",
        "registry": "D:\\global-memory\\docs\\scripts-registry.md",
        "totals": {
            "actual_scripts": 136,
            "mentioned_in_registry": 140,
            "literal_entries": 140,
            "glob_patterns": 0,
            "unregistered": 0,
            "orphan_listed": 0,
            "stale_in_registry": 0,
        },
        "summary": {
            "actual_scripts": 136,
            "unregistered": 0,
            "orphan_listed": 0,
            "stale_in_registry": 0,
        },
        "unregistered": [],
        "orphan_listed": [],
        "stale_in_registry": [],
    }


def valid_dual_storage_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "dual_storage_scan",
        "verdict": "ok",
        "roots": {
            "active": "C:\\Users\\XINDONG\\.claude\\tasks\\active",
            "archived": "C:\\Users\\XINDONG\\.claude\\tasks\\archived",
            "projects": "D:\\global-memory\\projects",
        },
        "summary": {
            "active_dirs": 0,
            "archived_dirs": 0,
            "project_dirs": 0,
            "dual_count": 0,
        },
        "duplicates": [],
    }


def valid_capability_manifest_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "capability_manifest_check",
        "manifest": "D:\\global-memory\\harness\\capability_manifest.json",
        "summary": {
            "capabilities": 18,
            "release_scope": 9,
            "ERROR": 0,
            "WARNING": 0,
            "status_counts": {
                "core": 6,
                "deprecated": 0,
                "experimental": 1,
                "legacy": 2,
                "optional": 9,
            },
            "actual_scripts": 136,
            "assigned_scripts": 136,
            "coverage_exemptions": 0,
            "unassigned_scripts": 0,
            "stale_coverage_exemptions": 0,
            "documented_capabilities": 18,
        },
        "coverage": {
            "required": True,
            "unassigned": [],
            "stale_exemptions": [],
        },
        "findings": [],
        "verdict": "ok",
    }


def valid_client_remediation_plan() -> dict:
    return {
        "decision": "client_portability_scope",
        "owner": "maintainer",
        "ready": False,
        "current_constraint": "stable_full_lifecycle_clients=1, required_for_generic_oss=2",
        "next_check": "python harness/scripts/check_client_manifest.py --json",
        "options": [
            {
                "id": "keep_narrow_claim",
                "action": "keep_claude_code_harness_plus_context_cli_scope",
                "effect": "Keep external docs limited to Claude Code full lifecycle plus read-only Context Brief CLI.",
            },
            {
                "id": "add_second_full_lifecycle_client",
                "action": "implement_another_stable_full_lifecycle_client",
                "effect": "Only then claim generic full-lifecycle multi-client readiness.",
                "required_evidence": [
                    "client_manifest.json has another stable full_lifecycle client",
                ],
            },
        ],
    }


def valid_client_contracts() -> dict:
    return {
        "full_lifecycle_required_capabilities": [
            "install_or_bootstrap",
            "automatic_context_injection",
            "write_governance",
            "audit_logging",
            "rollback_or_disable",
            "release_health_check",
        ],
        "context_brief_required_capabilities": [
            "context_brief_cli",
            "json_output_contract",
        ],
    }


def valid_client_lifecycle_gaps() -> dict:
    return {
        **valid_client_contracts(),
        "clients": [
            {
                "id": "claude_code",
                "status": "stable",
                "support_level": "full_lifecycle",
                "missing_full_lifecycle_capabilities": [],
                "missing_context_brief_capabilities": [],
            },
            {
                "id": "codex_cli",
                "status": "experimental",
                "support_level": "context_brief_only",
                "missing_full_lifecycle_capabilities": [
                    "install_or_bootstrap",
                    "automatic_context_injection",
                    "write_governance",
                    "audit_logging",
                    "rollback_or_disable",
                ],
                "missing_context_brief_capabilities": [],
            },
            {
                "id": "generic_cli",
                "status": "stable",
                "support_level": "context_brief_only",
                "missing_full_lifecycle_capabilities": [
                    "install_or_bootstrap",
                    "automatic_context_injection",
                    "write_governance",
                    "audit_logging",
                    "rollback_or_disable",
                    "release_health_check",
                ],
                "missing_context_brief_capabilities": [],
            },
        ],
    }


def valid_publish_scope_gap_breakdown() -> dict:
    return {
        "private_tracked_paths": 3,
        "unclassified_tracked_paths": 0,
        "private_tracked_summary": {
            "by_reason": [
                {"key": "personal knowledge base", "count": 2},
                {"key": "local project/task context", "count": 1},
            ],
            "by_path_group": [
                {"key": "knowledge", "count": 2},
                {"key": "projects", "count": 1},
            ],
            "by_match": [
                {"key": "prefix", "count": 3},
            ],
        },
        "unclassified_tracked_summary": {"by_path_group": []},
        "samples_count": 2,
        "samples": [
            {"path": "knowledge/a.md", "match": "prefix", "reason": "personal knowledge base"},
            {"path": "projects/demo/SPEC.md", "match": "prefix", "reason": "local project/task context"},
        ],
        "manifest": "harness/publish_scope_manifest.json",
    }


def valid_client_manifest_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "client_manifest_check",
        "manifest": "D:\\global-memory\\harness\\client_manifest.json",
        "product_scope": "claude_code_harness_with_generic_context_cli",
        "multi_client_ready": False,
        "context_cli_ready": True,
        "readiness": {
            "full_lifecycle_multi_client": {
                "ready": False,
                "stable_clients": 1,
                "required_clients": 2,
            },
            "context_cli": {
                "ready": True,
                "stable_clients": 2,
                "required_clients": 2,
            },
        },
        "contracts": valid_client_contracts(),
        "clients": [
            {
                "id": "claude_code",
                "name": "Claude Code",
                "status": "stable",
                "integration": "hooks_settings",
                "support_level": "full_lifecycle",
                "entrypoint_count": 5,
                "limitations_count": 2,
                "capability_count": 8,
                "missing_full_lifecycle_capabilities": [],
                "missing_context_brief_capabilities": [],
            },
            {
                "id": "codex_cli",
                "name": "Codex CLI",
                "status": "experimental",
                "integration": "manual_cli",
                "support_level": "context_brief_only",
                "entrypoint_count": 2,
                "limitations_count": 2,
                "capability_count": 3,
                "missing_full_lifecycle_capabilities": [
                    "install_or_bootstrap",
                    "automatic_context_injection",
                    "write_governance",
                    "audit_logging",
                    "rollback_or_disable",
                ],
                "missing_context_brief_capabilities": [],
            },
            {
                "id": "generic_cli",
                "name": "Generic CLI client",
                "status": "stable",
                "integration": "manual_cli",
                "support_level": "context_brief_only",
                "entrypoint_count": 1,
                "limitations_count": 2,
                "capability_count": 2,
                "missing_full_lifecycle_capabilities": [
                    "install_or_bootstrap",
                    "automatic_context_injection",
                    "write_governance",
                    "audit_logging",
                    "rollback_or_disable",
                    "release_health_check",
                ],
                "missing_context_brief_capabilities": [],
            },
        ],
        "summary": {
            "clients": 3,
            "stable_clients": 2,
            "stable_full_lifecycle_clients": 1,
            "stable_context_clients": 2,
            "required_for_generic_oss": 2,
            "claim_policy_checked": 3,
            "ERROR": 0,
            "WARNING": 1,
            "status_counts": {
                "deprecated": 0,
                "experimental": 1,
                "planned": 0,
                "stable": 2,
            },
        },
        "claim_policy": {
            "checked": 3,
            "required": 3,
            "forbidden_checked": 3,
            "forbidden": 3,
            "findings": [],
        },
        "remediation_plan": valid_client_remediation_plan(),
        "findings": [
            {
                "level": "WARNING",
                "code": "single_full_lifecycle_client_scope",
                "message": "full_lifecycle_multi_client_ready=false; stable_full_lifecycle_clients=1, required_for_generic_oss=2; product_scope=claude_code_harness_with_generic_context_cli",
                "client_id": "",
                "path": "",
            }
        ],
        "verdict": "single_client_scope",
    }


def valid_gate_report() -> dict:
    gates = [
        {"id": "G1", "name": "dual storage = 0", "pass": True, "detail": "dual_count=0"},
        {"id": "G2", "name": "git snapshot tag", "pass": True, "detail": "tag"},
        {"id": "G3", "name": "retrieve runs", "pass": True, "detail": "rc=0"},
        {"id": "G4", "name": "trigger coverage >=90%", "pass": True, "detail": "coverage=100.00%"},
        {"id": "G5", "name": "MEMORY.md <= 4000 bytes", "pass": True, "detail": "bytes=1749"},
        {"id": "G6", "name": "plugins controlled", "pass": True, "detail": "enabled=[]"},
        {"id": "G7", "name": "test suite green", "pass": True, "detail": "ok"},
        {"id": "G8", "name": "7d audit data", "pass": True, "detail": "n/a"},
        {"id": "G9", "name": "hardcoded paths (WARN)", "pass": True, "detail": "no issues"},
    ]
    return {
        "schema_version": 1,
        "kind": "gate_check",
        "timestamp": "2026-05-26T00:00:00",
        "repo": "D:\\global-memory",
        "phase": "p2-to-p3",
        "verdict": "pass",
        "exit_code": 0,
        "summary": {"total": 9, "pass": 9, "fail": 0},
        "failures": [],
        "gates": gates,
        "report_path": None,
    }


def valid_hook_alignment_report() -> dict:
    hooks = [
        "hooks/audit_logger.py",
        "hooks/changelog_inject.py",
        "hooks/statusline.py",
    ]
    return {
        "schema_version": 1,
        "kind": "hook_alignment_check",
        "sources": {
            "manifest": "D:\\global-memory\\harness\\hook_manifest.json",
            "bootstrap": "D:\\global-memory\\bootstrap.py",
            "settings": "C:\\Users\\XINDONG\\.claude\\settings.json",
            "registry": "D:\\global-memory\\docs\\scripts-registry.md",
        },
        "totals": {
            "manifest_hooks": 3,
            "bootstrap_hooks": 3,
            "runtime_hooks": 3,
            "registry_active_hooks": 3,
            "findings": 0,
        },
        "manifest_hooks": hooks,
        "bootstrap_hooks": hooks,
        "runtime_hooks": hooks,
        "registry_active_hooks": hooks,
        "findings": [],
        "verdict": "aligned",
    }


def valid_external_safety_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "external_source_safety_scan",
        "manifest": "D:\\global-memory\\harness\\publish_scope_manifest.json",
        "verdict": "needs_review",
        "summary": {
            "planned_external_files": 10,
            "scanned_files": 9,
            "skipped_files": 1,
            "blockers": 0,
            "warnings": 2,
            "plan_exit_code": 0,
        },
        "by_code": [
            {"code": "windows_abs_path", "severity": "warning", "count": 2},
        ],
        "top_paths": [
            {
                "path": "PUBLIC_CHANGELOG.md",
                "findings": 2,
                "blockers": 0,
                "warnings": 2,
                "codes": [{"code": "windows_abs_path", "count": 2}],
                "first_locations": [
                    {"line": 4, "code": "windows_abs_path", "severity": "warning"},
                    {"line": 8, "code": "windows_abs_path", "severity": "warning"},
                ],
            },
        ],
        "remediation_groups": [
            {
                "group": "public_history",
                "findings": 2,
                "blockers": 0,
                "warnings": 2,
                "paths": ["PUBLIC_CHANGELOG.md"],
                "path_count": 1,
                "codes": [{"code": "windows_abs_path", "count": 2}],
            },
        ],
        "policy_plan": {
            "decision": "public_history_policy",
            "owner": "project_owner",
            "options": [
                {"id": "sanitize_changelog", "action": "sanitize_public_history"},
                {"id": "generate_public_changelog", "action": "replace_public_history"},
                {"id": "exclude_public_history", "action": "remove_changelog_from_external_scope"},
            ],
        },
        "findings": [
            {
                "path": "PUBLIC_CHANGELOG.md",
                "line": 4,
                "severity": "warning",
                "code": "windows_abs_path",
                "snippet": "D:\\global-memory",
            },
            {
                "path": "PUBLIC_CHANGELOG.md",
                "line": 8,
                "severity": "warning",
                "code": "windows_abs_path",
                "snippet": "C:\\Users\\XINDONG",
            },
        ],
        "skipped": [{"path": "assets/logo.png", "reason": "binary_suffix"}],
    }


def valid_publish_scope_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "publish_scope_check",
        "manifest": "D:\\global-memory\\harness\\publish_scope_manifest.json",
        "decision_doc": "docs/publish-scope.md",
        "verdict": "blocked",
        "summary": {
            "tracked_files": 4,
            "external_scope_files": 2,
            "private_tracked_paths": 2,
            "unclassified_tracked_paths": 0,
            "manifest_findings": 0,
            "git_error": False,
        },
        "manifest_findings": [],
        "private_tracked_summary": {
            "by_reason": [
                {"key": "personal memory index", "count": 1},
                {"key": "self-loop experiments and local evidence", "count": 1},
            ],
            "by_path_group": [
                {"key": "root", "count": 1},
                {"key": ".meta", "count": 1},
            ],
            "by_match": [
                {"key": "file", "count": 1},
                {"key": "prefix", "count": 1},
            ],
        },
        "private_tracked_paths": [
            {"path": "MEMORY.md", "match": "file", "reason": "personal memory index"},
            {
                "path": ".meta/optimizations/optimizations.jsonl",
                "match": "prefix",
                "reason": "self-loop experiments and local evidence",
            },
        ],
        "unclassified_tracked_summary": {
            "by_path_group": [],
        },
        "unclassified_tracked_paths": [],
        "decision_plan": {
            "decision": "publish_scope_boundary",
            "owner": "project_owner",
            "ready": False,
            "decision_doc": "docs/publish-scope.md",
            "required_when": {
                "private_tracked_paths": 2,
                "unclassified_tracked_paths": 0,
            },
            "options": [
                {"id": "split_clean_source_repository", "action": "publish_only_external_scope"},
                {"id": "move_private_data", "action": "move_private_scope_to_private_storage"},
                {"id": "convert_selected_fixtures", "action": "replace_private_context_with_anonymized_fixtures"},
                {"id": "keep_private_maturity_audit", "action": "do_not_publish_source"},
            ],
        },
        "scope": {
            "external_files": ["README.md", "VERSION"],
            "external_prefixes": ["docs/", "harness/"],
            "private_files": ["CHANGELOG.md", "MEMORY.md"],
            "private_prefixes": [".meta/", "knowledge/"],
        },
    }


def valid_export_source_report() -> dict:
    return {
        "schema_version": 1,
        "kind": "source_export_scope_plan",
        "manifest": "D:\\global-memory\\harness\\publish_scope_manifest.json",
        "decision_doc": "docs/publish-scope.md",
        "verdict": "ready_with_warnings",
        "summary": {
            "tracked_files": 3,
            "worktree_files": 3,
            "export_included_paths": 2,
            "untracked_included_paths": 1,
            "excluded_private_paths": 1,
            "unclassified_paths": 0,
            "missing_external_files": 0,
            "manifest_findings": 0,
            "git_errors": 0,
        },
        "untracked_included_summary": {
            "by_reason": [
                {"reason": "public documentation", "count": 1, "paths": ["docs/new.md"]},
            ],
            "by_path_group": [
                {"group": "docs", "count": 1, "paths": ["docs/new.md"]},
            ],
            "by_match": [
                {"match": "prefix", "count": 1},
            ],
        },
        "tracking_plan": {
            "action": "git_add_external_untracked",
            "ready": True,
            "path_count": 1,
            "paths": ["docs/new.md"],
            "command": ["git", "add", "--", "docs/new.md"],
            "safety": {
                "excluded_private_paths": 1,
                "unclassified_paths": 0,
                "missing_external_files": 0,
            },
        },
        "included_paths": [
            {"path": "README.md", "match": "file", "reason": "project overview", "git_state": "tracked"},
            {"path": "docs/new.md", "match": "prefix", "reason": "public documentation", "git_state": "untracked"},
        ],
        "untracked_included_paths": [
            {"path": "docs/new.md", "match": "prefix", "reason": "public documentation", "git_state": "untracked"},
        ],
        "excluded_private_paths": [
            {"path": "MEMORY.md", "match": "file", "reason": "personal memory index", "git_state": "tracked"},
        ],
        "unclassified_paths": [],
        "missing_external_files": [],
        "manifest_findings": [],
        "git_errors": [],
    }


def codes(findings) -> set[str]:
    return {finding.code for finding in findings}


class TestMaintainStatusContract(unittest.TestCase):
    def test_valid_status_exposes_release_capabilities(self) -> None:
        findings = validate_maintain_status_contract(status_case(), valid_status_report())

        self.assertEqual(findings, [])

    def test_status_must_expose_release_gaps_capability(self) -> None:
        report = valid_status_report()
        del report["capabilities"]["release-gaps"]

        findings = validate_maintain_status_contract(status_case(), report)

        self.assertIn("maintain_status_capability_release_gaps_missing", codes(findings))


class TestReleaseCheckpointContract(unittest.TestCase):
    def test_valid_checkpoint_groups_release_evidence(self) -> None:
        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint", ["maintain.py", "release-checkpoint", "--json"]),
            valid_release_checkpoint_report(),
        )

        self.assertEqual(findings, [])

    def test_checkpoint_requires_external_safety_check(self) -> None:
        report = valid_release_checkpoint_report()
        report["checks"] = [item for item in report["checks"] if item["id"] != "external_source_safety"]

        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint", ["maintain.py", "release-checkpoint", "--json"]),
            report,
        )

        self.assertIn("release_checkpoint_missing_checks", codes(findings))

    def test_checkpoint_verdict_must_mirror_release_check(self) -> None:
        report = valid_release_checkpoint_report()
        report["release_verdict"] = "ready"

        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint", ["maintain.py", "release-checkpoint", "--json"]),
            report,
        )

        self.assertIn("release_checkpoint_verdict_mismatch", codes(findings))

    def test_checkpoint_declares_release_check_output_contract_mode(self) -> None:
        report = valid_release_checkpoint_report()
        report["summary"]["release_check_output_contracts_included"] = True

        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint", ["maintain.py", "release-checkpoint", "--json"]),
            report,
        )

        self.assertIn("release_checkpoint_output_contracts_mode", codes(findings))

    def test_checkpoint_release_gaps_keeps_owner_record_commands(self) -> None:
        report = valid_release_checkpoint_report()
        release_gaps = next(item for item in report["checks"] if item["id"] == "release_gaps")
        owner_gap = release_gaps["payload"]["remaining_gap_table"]["owner_decisions"][0]
        owner_gap.pop("record_dry_run_command")

        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint", ["maintain.py", "release-checkpoint", "--json"]),
            report,
        )

        self.assertIn("gap_table_record_dry_run_command", codes(findings))

    def test_checkpoint_keeps_owner_decision_template(self) -> None:
        report = valid_release_checkpoint_report()
        template = next(item for item in report["checks"] if item["id"] == "release_decision_template")
        template["payload"].pop("state_patch_template")

        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint", ["maintain.py", "release-checkpoint", "--json"]),
            report,
        )

        self.assertIn("owner_decision_template_patch_type", codes(findings))

    def test_checkpoint_template_summary_must_match_payload(self) -> None:
        report = valid_release_checkpoint_report()
        report["summary"]["owner_decision_templates"] = 0

        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint", ["maintain.py", "release-checkpoint", "--json"]),
            report,
        )

        self.assertIn("release_checkpoint_owner_decision_templates_mismatch", codes(findings))

    def test_strict_checkpoint_uses_same_json_contract(self) -> None:
        report = valid_release_checkpoint_report()
        report["strict"] = True
        report["exit_code"] = 1

        findings = validate_release_checkpoint_contract(
            ContractCase("maintain_release_checkpoint_strict", ["maintain.py", "release-checkpoint", "--strict", "--json"]),
            report,
        )

        self.assertEqual(findings, [])


class TestOrphanScriptScanContract(unittest.TestCase):
    def test_valid_scan_has_no_findings(self) -> None:
        findings = validate_orphan_script_scan_contract(orphan_scan_case(), valid_orphan_scan_report())

        self.assertEqual(findings, [])

    def test_scan_verdict_must_reflect_registry_drift(self) -> None:
        report = valid_orphan_scan_report()
        report["unregistered"] = ["scripts/new_tool.py"]
        report["summary"]["unregistered"] = 1
        report["totals"]["unregistered"] = 1

        findings = validate_orphan_script_scan_contract(orphan_scan_case(), report)

        self.assertIn("orphan_scan_verdict_mismatch", codes(findings))


class TestDualStorageScanContract(unittest.TestCase):
    def test_valid_scan_has_no_findings(self) -> None:
        findings = validate_dual_storage_scan_contract(dual_storage_case(), valid_dual_storage_report())

        self.assertEqual(findings, [])

    def test_duplicate_count_must_match_rows(self) -> None:
        report = valid_dual_storage_report()
        report["summary"]["dual_count"] = 1
        report["verdict"] = "dual_storage_found"

        findings = validate_dual_storage_scan_contract(dual_storage_case(), report)

        self.assertIn("dual_storage_duplicate_count_mismatch", codes(findings))

    def test_verdict_must_match_dual_count(self) -> None:
        report = valid_dual_storage_report()
        report["duplicates"].append({
            "name": "task-a",
            "active": True,
            "archived": False,
            "projects": True,
        })
        report["summary"]["dual_count"] = 1
        report["verdict"] = "ok"

        findings = validate_dual_storage_scan_contract(dual_storage_case(), report)

        self.assertIn("dual_storage_verdict_mismatch", codes(findings))


class TestCapabilityManifestContract(unittest.TestCase):
    def test_valid_manifest_has_no_findings(self) -> None:
        findings = validate_capability_manifest_contract(
            capability_manifest_case(),
            valid_capability_manifest_report(),
        )

        self.assertEqual(findings, [])

    def test_status_counts_must_match_capability_total(self) -> None:
        report = valid_capability_manifest_report()
        report["summary"]["status_counts"]["optional"] = 8

        findings = validate_capability_manifest_contract(capability_manifest_case(), report)

        self.assertIn("capability_manifest_status_counts_total", codes(findings))

    def test_coverage_counts_must_match_rows(self) -> None:
        report = valid_capability_manifest_report()
        report["summary"]["unassigned_scripts"] = 1

        findings = validate_capability_manifest_contract(capability_manifest_case(), report)

        self.assertIn("capability_manifest_unassigned_scripts_mismatch", codes(findings))


class TestClientManifestContract(unittest.TestCase):
    def test_valid_manifest_has_no_findings(self) -> None:
        findings = validate_client_manifest_contract(client_manifest_case(), valid_client_manifest_report())

        self.assertEqual(findings, [])

    def test_stable_count_must_match_status_counts(self) -> None:
        report = valid_client_manifest_report()
        report["summary"]["status_counts"]["stable"] = 1

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_stable_count_mismatch", codes(findings))

    def test_ready_cannot_be_true_below_minimum(self) -> None:
        report = valid_client_manifest_report()
        report["multi_client_ready"] = True

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_ready_below_minimum", codes(findings))

    def test_context_ready_cannot_be_true_below_minimum(self) -> None:
        report = valid_client_manifest_report()
        report["summary"]["stable_context_clients"] = 1

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_context_ready_below_minimum", codes(findings))

    def test_readiness_counts_must_match_summary(self) -> None:
        report = valid_client_manifest_report()
        report["readiness"]["context_cli"]["stable_clients"] = 1

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_readiness_context_stable_mismatch", codes(findings))

    def test_client_rows_must_match_summary_counts(self) -> None:
        report = valid_client_manifest_report()
        report["clients"][2]["support_level"] = "planned"

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_context_count_mismatch", codes(findings))

    def test_client_contracts_must_be_present(self) -> None:
        report = valid_client_manifest_report()
        report.pop("contracts")

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_contracts_type", codes(findings))

    def test_full_lifecycle_clients_must_have_capability_matrix(self) -> None:
        report = valid_client_manifest_report()
        report["clients"][0]["missing_full_lifecycle_capabilities"] = ["write_governance"]

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_full_lifecycle_missing_capabilities", codes(findings))

    def test_context_clients_must_have_context_brief_capabilities(self) -> None:
        report = valid_client_manifest_report()
        report["clients"][2]["missing_context_brief_capabilities"] = ["json_output_contract"]

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_context_brief_missing_capabilities", codes(findings))

    def test_claim_policy_must_be_checked(self) -> None:
        report = valid_client_manifest_report()
        report["claim_policy"] = {"checked": 2, "required": 3, "forbidden_checked": 3, "forbidden": 3, "findings": []}

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_claim_policy_checked", codes(findings))
        self.assertIn("client_manifest_claim_policy_checked_mismatch", codes(findings))

    def test_claim_policy_must_check_forbidden_overclaims(self) -> None:
        report = valid_client_manifest_report()
        report["claim_policy"]["forbidden_checked"] = 2

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_claim_policy_forbidden_checked", codes(findings))

    def test_claim_policy_findings_must_be_empty(self) -> None:
        report = valid_client_manifest_report()
        report["claim_policy"]["findings"] = [{"level": "ERROR", "code": "claim_policy_missing_phrase"}]

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_claim_policy_findings_nonempty", codes(findings))

    def test_client_warning_must_have_remediation_plan(self) -> None:
        report = valid_client_manifest_report()
        report.pop("remediation_plan")

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_remediation_plan", codes(findings))

    def test_client_remediation_plan_must_have_required_options(self) -> None:
        report = valid_client_manifest_report()
        report["remediation_plan"]["options"] = [report["remediation_plan"]["options"][0]]

        findings = validate_client_manifest_contract(client_manifest_case(), report)

        self.assertIn("client_manifest_remediation_options", codes(findings))
        self.assertIn("client_manifest_remediation_required_options", codes(findings))


class TestGateCheckContract(unittest.TestCase):
    def test_valid_gate_report_has_no_findings(self) -> None:
        findings = validate_gate_check_contract(gate_case(), valid_gate_report())

        self.assertEqual(findings, [])

    def test_gate_summary_must_match_gates(self) -> None:
        report = valid_gate_report()
        report["summary"]["pass"] = 8

        findings = validate_gate_check_contract(gate_case(), report)

        self.assertIn("gate_check_summary_pass_mismatch", codes(findings))

    def test_failures_must_match_failed_gate_rows(self) -> None:
        report = valid_gate_report()
        report["gates"][2]["pass"] = False
        report["summary"] = {"total": 9, "pass": 8, "fail": 1}
        report["verdict"] = "blocked"
        report["exit_code"] = 1

        findings = validate_gate_check_contract(gate_case(), report)

        self.assertIn("gate_check_failures_mismatch", codes(findings))

    def test_g9_must_keep_warn_label(self) -> None:
        report = valid_gate_report()
        report["gates"][8]["name"] = "hardcoded paths"

        findings = validate_gate_check_contract(gate_case(), report)

        self.assertIn("gate_check_g9_warn", codes(findings))


class TestHookAlignmentContract(unittest.TestCase):
    def test_valid_hook_alignment_has_no_findings(self) -> None:
        findings = validate_hook_alignment_contract(hook_alignment_case(), valid_hook_alignment_report())

        self.assertEqual(findings, [])

    def test_totals_must_match_hook_lists(self) -> None:
        report = valid_hook_alignment_report()
        report["totals"]["manifest_hooks"] = 2

        findings = validate_hook_alignment_contract(hook_alignment_case(), report)

        self.assertIn("hook_alignment_manifest_hooks_count_mismatch", codes(findings))

    def test_finding_count_must_match_relpaths(self) -> None:
        report = valid_hook_alignment_report()
        report["findings"] = [
            {
                "kind": "manifest_not_in_runtime",
                "severity": "high",
                "count": 2,
                "relpaths": ["hooks/retrieve_inject.py"],
                "detail": "missing from runtime",
            }
        ]
        report["totals"]["findings"] = 1
        report["verdict"] = "drift"

        findings = validate_hook_alignment_contract(hook_alignment_case(), report)

        self.assertIn("hook_alignment_finding_count_mismatch", codes(findings))

    def test_verdict_must_reflect_findings(self) -> None:
        report = valid_hook_alignment_report()
        report["findings"] = [
            {
                "kind": "manifest_not_in_runtime",
                "severity": "high",
                "count": 1,
                "relpaths": ["hooks/retrieve_inject.py"],
                "detail": "missing from runtime",
            }
        ]
        report["totals"]["findings"] = 1

        findings = validate_hook_alignment_contract(hook_alignment_case(), report)

        self.assertIn("hook_alignment_verdict_mismatch", codes(findings))


class TestExternalSourceSafetyContract(unittest.TestCase):
    def test_valid_scan_aggregates_have_no_findings(self) -> None:
        findings = validate_external_source_safety_contract(
            external_safety_case(),
            valid_external_safety_report(),
        )

        self.assertEqual(findings, [])

    def test_scan_counts_must_match_summary(self) -> None:
        report = valid_external_safety_report()
        report["summary"]["scanned_files"] = 8

        findings = validate_external_source_safety_contract(external_safety_case(), report)

        self.assertIn("external_safety_scan_count_mismatch", codes(findings))

    def test_by_code_total_must_match_findings(self) -> None:
        report = valid_external_safety_report()
        report["by_code"][0]["count"] = 1

        findings = validate_external_source_safety_contract(external_safety_case(), report)

        self.assertIn("external_safety_by_code_total_mismatch", codes(findings))

    def test_remediation_group_total_must_match_findings(self) -> None:
        report = valid_external_safety_report()
        report["remediation_groups"][0]["findings"] = 1

        findings = validate_external_source_safety_contract(external_safety_case(), report)

        self.assertIn("external_safety_group_count_mismatch", codes(findings))
        self.assertIn("external_safety_group_total_mismatch", codes(findings))

    def test_verdict_must_match_blocker_warning_counts(self) -> None:
        report = valid_external_safety_report()
        report["verdict"] = "ok"

        findings = validate_external_source_safety_contract(external_safety_case(), report)

        self.assertIn("external_safety_verdict_mismatch", codes(findings))

    def test_public_history_warning_requires_policy_plan(self) -> None:
        report = valid_external_safety_report()
        report["policy_plan"] = {}

        findings = validate_external_source_safety_contract(external_safety_case(), report)

        self.assertIn("external_safety_policy_plan_missing", codes(findings))


class TestSmokeTestContract(unittest.TestCase):
    def test_valid_smoke_report_has_no_findings(self) -> None:
        findings = validate_smoke_test_contract(smoke_case(), valid_smoke_report())

        self.assertEqual(findings, [])

    def test_summary_counts_must_match_result_rows(self) -> None:
        report = valid_smoke_report()
        report["summary"]["PASS"] = 3

        findings = validate_smoke_test_contract(smoke_case(), report)

        self.assertIn("smoke_summary_pass_count_mismatch", codes(findings))
        self.assertIn("smoke_summary_total_mismatch", codes(findings))

    def test_fail_count_is_contract_error(self) -> None:
        report = valid_smoke_report()
        report["summary"]["PASS"] = 1
        report["summary"]["FAIL"] = 1
        report["results"][1]["status"] = "FAIL"

        findings = validate_smoke_test_contract(smoke_case(), report)

        self.assertIn("smoke_failures_present", codes(findings))

    def test_skip_rows_must_use_skip_exit_code_and_detail(self) -> None:
        report = valid_smoke_report()
        report["results"][2]["exit_code"] = 0
        report["results"][2]["detail"] = ""

        findings = validate_smoke_test_contract(smoke_case(), report)

        self.assertIn("smoke_skip_exit_code", codes(findings))
        self.assertIn("smoke_skip_detail_missing", codes(findings))

    def test_result_rows_need_stable_identity_fields(self) -> None:
        report = valid_smoke_report()
        report["results"][0]["script"] = ""
        report["results"][0]["category"] = ""
        report["results"][0]["status"] = "BROKEN"

        findings = validate_smoke_test_contract(smoke_case(), report)

        self.assertIn("smoke_result_script_missing", codes(findings))
        self.assertIn("smoke_result_category_missing", codes(findings))
        self.assertIn("smoke_result_status_invalid", codes(findings))


class TestHarnessTasksContract(unittest.TestCase):
    def test_valid_tasks_report_has_no_findings(self) -> None:
        findings = validate_harness_tasks_contract(harness_tasks_case(), valid_harness_tasks_report())

        self.assertEqual(findings, [])

    def test_summary_counts_must_match_rows(self) -> None:
        report = valid_harness_tasks_report()
        report["summary"]["active"] = 2

        findings = validate_harness_tasks_contract(harness_tasks_case(), report)

        self.assertIn("harness_tasks_summary_active_mismatch", codes(findings))

    def test_stage_counts_must_match_rows(self) -> None:
        report = valid_harness_tasks_report()
        report["summary"]["active_by_stage"]["missing"] = 2

        findings = validate_harness_tasks_contract(harness_tasks_case(), report)

        self.assertIn("harness_tasks_summary_active_by_stage_mismatch", codes(findings))

    def test_rows_need_identity_fields(self) -> None:
        report = valid_harness_tasks_report()
        report["active"][0]["name"] = ""
        report["active"][0]["stage"] = ""
        report["active"][0]["path"] = ""

        findings = validate_harness_tasks_contract(harness_tasks_case(), report)

        self.assertIn("harness_tasks_name", codes(findings))
        self.assertIn("harness_tasks_stage", codes(findings))
        self.assertIn("harness_tasks_path", codes(findings))

    def test_missing_and_unknown_active_counts_are_explicit(self) -> None:
        report = valid_harness_tasks_report()
        report["summary"]["missing_active"] = 0
        report["summary"]["unknown_active"] = 0

        findings = validate_harness_tasks_contract(harness_tasks_case(), report)

        self.assertIn("harness_tasks_summary_missing_active_mismatch", codes(findings))
        self.assertIn("harness_tasks_summary_unknown_active_mismatch", codes(findings))


class TestSelfLoopReportContract(unittest.TestCase):
    def test_valid_self_loop_report_has_no_findings(self) -> None:
        findings = validate_self_loop_report_contract(self_loop_case(), valid_self_loop_report())

        self.assertEqual(findings, [])

    def test_candidate_summary_counts_must_match_groups(self) -> None:
        report = valid_self_loop_report()
        report["fallback_candidates"]["summary"]["candidate_tasks"] = 4

        findings = validate_self_loop_report_contract(self_loop_case(), report)

        self.assertIn("self_loop_candidates_count_mismatch", codes(findings))

    def test_ledger_latest_cannot_exceed_count(self) -> None:
        report = valid_self_loop_report()
        report["optimization_ledger"]["count"] = 0

        findings = validate_self_loop_report_contract(self_loop_case(), report)

        self.assertIn("self_loop_ledger_latest_exceeds_count", codes(findings))

    def test_nested_reports_keep_schema(self) -> None:
        report = valid_self_loop_report()
        report["fallback_cost"]["schema_version"] = 2
        report["fallback_candidates"]["schema_version"] = 2

        findings = validate_self_loop_report_contract(self_loop_case(), report)

        self.assertIn("self_loop_fallback_cost_schema", codes(findings))
        self.assertIn("self_loop_candidates_schema", codes(findings))


class TestMetaOptimizeContract(unittest.TestCase):
    def test_valid_meta_optimize_report_has_no_findings(self) -> None:
        findings = validate_meta_optimize_contract(meta_optimize_case(), valid_meta_optimize_report())

        self.assertEqual(findings, [])

    def test_summary_counts_must_match_findings(self) -> None:
        report = valid_meta_optimize_report()
        report["summary"]["finding_count"] = 1
        report["summary"]["by_severity"]["high"] = 2

        findings = validate_meta_optimize_contract(meta_optimize_case(), report)

        self.assertIn("meta_optimize_finding_count_mismatch", codes(findings))
        self.assertIn("meta_optimize_by_severity_mismatch", codes(findings))

    def test_user_visible_decision_fields_are_required(self) -> None:
        report = valid_meta_optimize_report()
        report["user_visible"]["verdict"] = ""
        report["user_visible"]["recommended_first_action"] = ""

        findings = validate_meta_optimize_contract(meta_optimize_case(), report)

        self.assertIn("meta_optimize_visible_verdict", codes(findings))
        self.assertIn("meta_optimize_visible_recommended_first_action", codes(findings))

    def test_finding_rows_need_actionable_identity(self) -> None:
        report = valid_meta_optimize_report()
        report["findings"][0]["id"] = ""
        report["findings"][0]["priority_rank"] = 0
        report["findings"][0]["evidence"] = ""

        findings = validate_meta_optimize_contract(meta_optimize_case(), report)

        self.assertIn("meta_optimize_finding_id", codes(findings))
        self.assertIn("meta_optimize_finding_priority", codes(findings))
        self.assertIn("meta_optimize_finding_evidence_type", codes(findings))


class TestClientContextContract(unittest.TestCase):
    def test_valid_context_brief_has_no_findings(self) -> None:
        findings = validate_client_context_contract(client_context_case(), valid_client_context_report())

        self.assertEqual(findings, [])

    def test_failed_context_brief_allows_empty_query_shape(self) -> None:
        findings = validate_client_context_contract(client_context_case(), failed_client_context_report())

        self.assertEqual(findings, [])

    def test_successful_payload_needs_brief_and_empty_error(self) -> None:
        report = valid_client_context_report()
        report["error"] = "stale"
        report["brief"] = None

        findings = validate_client_context_contract(client_context_case(), report)

        self.assertIn("client_context_ok_error", codes(findings))
        self.assertIn("client_context_brief_type", codes(findings))

    def test_brief_must_match_top_level_task_and_stage(self) -> None:
        report = valid_client_context_report()
        report["brief"]["task"] = "other"
        report["brief"]["stage"] = "draft"

        findings = validate_client_context_contract(client_context_case(), report)

        self.assertIn("client_context_task_mismatch", codes(findings))
        self.assertIn("client_context_stage_mismatch", codes(findings))

    def test_client_id_must_match_generic_cli_contract(self) -> None:
        report = valid_client_context_report()
        report["client_id"] = "other_client"

        findings = validate_client_context_contract(client_context_case(), report)

        self.assertIn("client_context_client_id_generic", codes(findings))

    def test_pointer_rows_need_path_and_why(self) -> None:
        report = valid_client_context_report()
        report["brief"]["relevant_pointers"][0]["path"] = ""
        report["brief"]["relevant_pointers"][0]["why"] = ""

        findings = validate_client_context_contract(client_context_case(), report)

        self.assertIn("client_context_pointer_path", codes(findings))
        self.assertIn("client_context_pointer_why", codes(findings))

    def test_brief_text_must_keep_external_context_shape(self) -> None:
        report = valid_client_context_report()
        report["brief_text"] = "schema_version: v2\n"

        findings = validate_client_context_contract(client_context_case(), report)

        self.assertIn("client_context_brief_text_shape", codes(findings))


class TestGenerateCatalogContract(unittest.TestCase):
    def test_valid_catalog_report_has_no_findings(self) -> None:
        findings = validate_generate_catalog_contract(generate_catalog_case(), valid_generate_catalog_report())

        self.assertEqual(findings, [])

    def test_summary_counts_must_match_target_rows(self) -> None:
        report = valid_generate_catalog_report()
        report["summary"]["fresh"] = 2

        findings = validate_generate_catalog_contract(generate_catalog_case(), report)

        self.assertIn("catalog_fresh_count_mismatch", codes(findings))

    def test_finding_rows_must_drive_verdict(self) -> None:
        report = valid_generate_catalog_report()
        report["verdict"] = "ok"
        report["summary"]["findings"] = 1
        report["summary"]["stale"] = 1
        report["summary"]["fresh"] = 2
        report["targets"][0]["fresh"] = False
        report["findings"] = [{"path": "agents/README.md", "issue": "stale_catalog"}]

        findings = validate_generate_catalog_contract(generate_catalog_case(), report)

        self.assertIn("catalog_verdict_mismatch", codes(findings))


class TestSkillAuditContract(unittest.TestCase):
    def test_valid_skill_audit_has_no_findings(self) -> None:
        findings = validate_skill_audit_contract(skill_audit_case(), valid_skill_audit_report())

        self.assertEqual(findings, [])

    def test_checked_count_must_match_skill_rows(self) -> None:
        report = valid_skill_audit_report()
        report["summary"]["checked_skills"] = 2

        findings = validate_skill_audit_contract(skill_audit_case(), report)

        self.assertIn("skill_audit_checked_count_mismatch", codes(findings))

    def test_level_must_aggregate_skill_rows(self) -> None:
        report = valid_skill_audit_report()
        report["level"] = "PASS"

        findings = validate_skill_audit_contract(skill_audit_case(), report)

        self.assertIn("skill_audit_level_mismatch", codes(findings))

    def test_issue_counts_must_match_issue_rows(self) -> None:
        report = valid_skill_audit_report()
        report["summary"]["issue_counts"]["WARNING"] = 1

        findings = validate_skill_audit_contract(skill_audit_case(), report)

        self.assertIn("skill_audit_issue_count_mismatch", codes(findings))

    def test_issue_code_summary_must_match_issue_rows(self) -> None:
        report = valid_skill_audit_report()
        report["summary"]["by_issue_code"][0]["count"] = 2

        findings = validate_skill_audit_contract(skill_audit_case(), report)

        self.assertIn("skill_audit_by_issue_code_mismatch", codes(findings))

    def test_skill_rows_need_identity_and_issue_messages(self) -> None:
        report = valid_skill_audit_report()
        report["skills"][1]["name"] = ""
        report["skills"][1]["issues"][0]["message"] = ""

        findings = validate_skill_audit_contract(skill_audit_case(), report)

        self.assertIn("skill_audit_skill_name", codes(findings))
        self.assertIn("skill_audit_issue_message", codes(findings))


class TestAnalyzeRetrieveLogContract(unittest.TestCase):
    def test_valid_report_has_no_findings(self) -> None:
        findings = validate_analyze_retrieve_log_contract(
            analyze_retrieve_log_case(),
            valid_analyze_retrieve_log_report(),
        )

        self.assertEqual(findings, [])

    def test_hit_distribution_must_sum_to_total(self) -> None:
        report = valid_analyze_retrieve_log_report()
        report["hit_count_distribution"]["3"] = 2

        findings = validate_analyze_retrieve_log_contract(analyze_retrieve_log_case(), report)

        self.assertIn("retrieve_log_distribution_total", codes(findings))

    def test_zero_hit_rate_must_match_zero_hit_count(self) -> None:
        report = valid_analyze_retrieve_log_report()
        report["zero_hit_rate"] = 0.8

        findings = validate_analyze_retrieve_log_contract(analyze_retrieve_log_case(), report)

        self.assertIn("retrieve_log_zero_hit_rate", codes(findings))

    def test_miss_sample_cannot_exceed_total(self) -> None:
        report = valid_analyze_retrieve_log_report()
        report["miss_queries_total"] = 1

        findings = validate_analyze_retrieve_log_contract(analyze_retrieve_log_case(), report)

        self.assertIn("retrieve_log_miss_sample_total", codes(findings))


class TestCheckPrepareContract(unittest.TestCase):
    def test_unresolved_task_shape_has_no_findings(self) -> None:
        findings = validate_check_prepare_contract(check_prepare_case(), unresolved_check_prepare_report())

        self.assertEqual(findings, [])

    def test_valid_resolved_report_has_no_findings(self) -> None:
        findings = validate_check_prepare_contract(check_prepare_case(), valid_check_prepare_report())

        self.assertEqual(findings, [])

    def test_unresolved_task_must_not_claim_pass(self) -> None:
        report = unresolved_check_prepare_report()
        report["level"] = "PASS"

        findings = validate_check_prepare_contract(check_prepare_case(), report)

        self.assertIn("check_prepare_unresolved_level", codes(findings))

    def test_doc_scan_count_must_match_review_docs(self) -> None:
        report = valid_check_prepare_report()
        report["doc_scans"] = []

        findings = validate_check_prepare_contract(check_prepare_case(), report)

        self.assertIn("check_prepare_doc_scan_count_mismatch", codes(findings))

    def test_doc_scan_path_must_be_in_review_docs(self) -> None:
        report = valid_check_prepare_report()
        report["doc_scans"][0]["path"] = "tasks/active/alpha/OTHER.md"

        findings = validate_check_prepare_contract(check_prepare_case(), report)

        self.assertIn("check_prepare_doc_scan_path_not_reviewed", codes(findings))

    def test_level_must_match_docs_and_warnings(self) -> None:
        report = valid_check_prepare_report()
        report["level"] = "PASS"

        findings = validate_check_prepare_contract(check_prepare_case(), report)

        self.assertIn("check_prepare_level_mismatch", codes(findings))

    def test_prompt_inputs_must_include_review_docs(self) -> None:
        report = valid_check_prepare_report()
        report["prompt_inputs"] = ["【任务名】：alpha"]

        findings = validate_check_prepare_contract(check_prepare_case(), report)

        self.assertIn("check_prepare_prompt_missing_doc", codes(findings))


class TestWorkContextPackContract(unittest.TestCase):
    def test_valid_resolved_report_has_no_findings(self) -> None:
        findings = validate_work_context_pack_contract(work_context_case(), valid_work_context_report())

        self.assertEqual(findings, [])

    def test_unresolved_task_shape_has_no_findings(self) -> None:
        report = {
            "schema_version": 1,
            "kind": "work_context",
            "level": "WARNING",
            "task": None,
            "confidence": 0.0,
            "summary": "No active task resolved from argument or cwd.",
            "in_watched_paths": False,
            "candidates": ["alpha"],
            "required_reads": [],
            "recommended_next_step": "Confirm whether this is a new task or specify task name.",
        }

        findings = validate_work_context_pack_contract(work_context_case(), report)

        self.assertEqual(findings, [])

    def test_pass_cannot_have_missing_required_docs(self) -> None:
        report = valid_work_context_report()
        report["missing_required_docs"] = ["core/HANDOFF.md"]

        findings = validate_work_context_pack_contract(work_context_case(), report)

        self.assertIn("work_context_pass_with_missing_docs", codes(findings))

    def test_required_reads_must_be_strings(self) -> None:
        report = valid_work_context_report()
        report["required_reads"] = [123]

        findings = validate_work_context_pack_contract(work_context_case(), report)

        self.assertIn("work_context_required_reads", codes(findings))

    def test_valid_intent_guard_shape_has_no_findings(self) -> None:
        report = valid_work_context_report()
        report["level"] = "WARNING"
        report["summary"] += "; intent_guard=new_task_requires_create_task_or_confirm"
        report["recommended_next_step"] = "Intent looks like a new task. Run create_task.py first."
        report["intent_guard"] = {
            "kind": "new_task_intent",
            "trigger": "维护 task",
            "action": "create_task_or_confirm",
            "message": "Intent looks like a new task; run create_task.py first or explicitly confirm continuing the current task.",
            "resolved_task": "demo-task",
            "resolution": "current_task_file",
        }

        findings = validate_work_context_pack_contract(work_context_intent_case(), report)

        self.assertEqual(findings, [])

    def test_intent_guard_action_is_constrained(self) -> None:
        report = valid_work_context_report()
        report["level"] = "WARNING"
        report["intent_guard"] = {
            "kind": "new_task_intent",
            "trigger": "维护 task",
            "action": "continue_anyway",
            "message": "bad",
        }

        findings = validate_work_context_pack_contract(work_context_intent_case(), report)

        self.assertIn("work_context_intent_guard_action", codes(findings))


class TestPublishScopeContract(unittest.TestCase):
    def test_valid_publish_scope_report_has_no_findings(self) -> None:
        findings = validate_publish_scope_contract(publish_scope_case(), valid_publish_scope_report())

        self.assertEqual(findings, [])

    def test_summary_counts_must_match_classified_totals(self) -> None:
        report = valid_publish_scope_report()
        report["summary"]["tracked_files"] = 5

        findings = validate_publish_scope_contract(publish_scope_case(), report)

        self.assertIn("publish_scope_tracked_count_mismatch", codes(findings))

    def test_manifest_finding_count_must_match_rows(self) -> None:
        report = valid_publish_scope_report()
        report["summary"]["manifest_findings"] = 1

        findings = validate_publish_scope_contract(publish_scope_case(), report)

        self.assertIn("publish_scope_manifest_findings_count_mismatch", codes(findings))

    def test_private_summary_must_match_private_count(self) -> None:
        report = valid_publish_scope_report()
        report["private_tracked_summary"]["by_match"][0]["count"] = 2

        findings = validate_publish_scope_contract(publish_scope_case(), report)

        self.assertIn("publish_scope_private_tracked_summary_by_match_total_mismatch", codes(findings))

    def test_required_when_must_match_summary_counts(self) -> None:
        report = valid_publish_scope_report()
        report["decision_plan"]["required_when"]["private_tracked_paths"] = 1

        findings = validate_publish_scope_contract(publish_scope_case(), report)

        self.assertIn("publish_scope_required_when_mismatch", codes(findings))

    def test_scope_lists_must_be_sorted_unique(self) -> None:
        report = valid_publish_scope_report()
        report["scope"]["external_files"] = ["VERSION", "README.md"]

        findings = validate_publish_scope_contract(publish_scope_case(), report)

        self.assertIn("publish_scope_scope_external_files_sorted_unique", codes(findings))

    def test_verdict_must_block_private_tracked_paths(self) -> None:
        report = valid_publish_scope_report()
        report["verdict"] = "ok"

        findings = validate_publish_scope_contract(publish_scope_case(), report)

        self.assertIn("publish_scope_verdict_mismatch", codes(findings))


class TestExportSourceScopeContract(unittest.TestCase):
    def test_valid_export_plan_has_no_findings(self) -> None:
        findings = validate_export_source_scope_contract(export_source_case(), valid_export_source_report())

        self.assertEqual(findings, [])

    def test_worktree_count_must_match_classified_paths(self) -> None:
        report = valid_export_source_report()
        report["summary"]["worktree_files"] = 4

        findings = validate_export_source_scope_contract(export_source_case(), report)

        self.assertIn("export_plan_worktree_count_mismatch", codes(findings))

    def test_untracked_summary_must_match_untracked_count(self) -> None:
        report = valid_export_source_report()
        report["untracked_included_summary"]["by_match"][0]["count"] = 2

        findings = validate_export_source_scope_contract(export_source_case(), report)

        self.assertIn("export_plan_untracked_summary_by_match_total_mismatch", codes(findings))

    def test_tracking_plan_safety_must_match_summary(self) -> None:
        report = valid_export_source_report()
        report["tracking_plan"]["safety"]["excluded_private_paths"] = 0

        findings = validate_export_source_scope_contract(export_source_case(), report)

        self.assertIn("export_plan_tracking_safety_mismatch", codes(findings))

    def test_verdict_must_reflect_invalid_conditions(self) -> None:
        report = valid_export_source_report()
        report["summary"]["missing_external_files"] = 1
        report["missing_external_files"] = ["MISSING.md"]

        findings = validate_export_source_scope_contract(export_source_case(), report)

        self.assertIn("export_plan_verdict_mismatch", codes(findings))

    def test_tracking_command_must_match_untracked_paths(self) -> None:
        report = valid_export_source_report()
        report["tracking_plan"]["command"] = ["git", "add", "--", "other.md"]

        findings = validate_export_source_scope_contract(export_source_case(), report)

        self.assertIn("export_plan_tracking_command_invalid", codes(findings))


class TestOssReadinessContract(unittest.TestCase):
    def check_by_id(self, report: dict, check_id: str) -> dict:
        for check in report["checks"]:
            if check.get("id") == check_id:
                return check
        raise AssertionError(f"missing check {check_id}")

    def test_valid_report_has_no_findings(self) -> None:
        findings = validate_oss_readiness_contract(case(), valid_oss_report())

        self.assertEqual(findings, [])

    def test_docs_entrypoint_coverage_must_include_checkpoint_doc(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        self.check_by_id(report, "docs_entrypoints")["summary"] = "checked=5, frontmatter_checked=5, findings=0"

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_docs_entrypoints_checked_low", codes(findings))

    def test_docs_entrypoint_coverage_must_include_frontmatter(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        self.check_by_id(report, "docs_entrypoints")["summary"] = "checked=6, frontmatter_checked=4, findings=0"
        self.check_by_id(report, "docs_entrypoints")["evidence"]["frontmatter_checked"] = 4

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_docs_entrypoints_frontmatter_low", codes(findings))
        self.assertIn("oss_readiness_docs_entrypoints_frontmatter_evidence", codes(findings))

    def test_docs_entrypoint_findings_must_be_empty(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        self.check_by_id(report, "docs_entrypoints")["evidence"]["findings"] = [{"id": "capability_gap_checkpoint"}]

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_docs_entrypoints_findings", codes(findings))

    def test_owner_blockers_must_keep_decision_plans(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        self.check_by_id(report, "project_metadata")["evidence"] = {}

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_project_metadata_decision_plan_missing", codes(findings))

    def test_publish_scope_decision_id_must_match_contract(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        self.check_by_id(report, "publish_scope")["evidence"]["decision_plan"]["decision"] = "other"

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_publish_scope_decision", codes(findings))

    def test_ci_workflow_must_expose_required_commands(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        self.check_by_id(report, "ci_workflow")["evidence"]["findings"] = [{"issue": "missing_command"}]

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_ci_workflow_findings", codes(findings))

    def test_ci_workflow_must_be_parseable_yaml(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        self.check_by_id(report, "ci_workflow")["evidence"]["yaml_valid"] = False

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_ci_workflow_yaml_valid", codes(findings))

    def test_catalog_freshness_must_have_no_findings(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        catalog = self.check_by_id(report, "catalog_freshness")
        catalog["evidence"]["summary"]["stale"] = 1
        catalog["evidence"]["findings"] = [{"path": "harness/README.md", "issue": "stale_catalog"}]

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_catalog_freshness_stale", codes(findings))
        self.assertIn("oss_readiness_catalog_freshness_findings", codes(findings))

    def test_client_portability_must_preserve_readiness_and_clients(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        client = self.check_by_id(report, "client_portability")
        client["evidence"].pop("readiness")
        client["evidence"].pop("clients")

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_client_portability_readiness", codes(findings))
        self.assertIn("oss_readiness_client_portability_clients", codes(findings))

    def test_client_portability_must_preserve_lifecycle_contracts(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        client = self.check_by_id(report, "client_portability")
        client["evidence"].pop("contracts")

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_client_portability_contracts", codes(findings))

    def test_client_portability_must_preserve_remediation_plan(self) -> None:
        report = copy.deepcopy(valid_oss_report())
        client = self.check_by_id(report, "client_portability")
        client["evidence"].pop("remediation_plan")

        findings = validate_oss_readiness_contract(case(), report)

        self.assertIn("oss_readiness_client_portability_remediation_plan", codes(findings))


class TestReleaseLedgerContract(unittest.TestCase):
    def client_portability_issue(self) -> dict:
        return {
            "issue_id": "oss-client_portability",
            "source": "oss_readiness",
            "check_id": "client_portability",
            "state": "open",
            "severity": "warning",
            "title": "Client support scope is explicit",
            "gap": {
                "type": "verified_capability",
                "owner": "maintainer",
                "resolution": "Keep the external claim narrow or add another full-lifecycle stable client.",
            },
            "summary": "stable_full_lifecycle=1, stable_context=2",
            "next_action": "Keep the external claim narrow.",
            "command": ["python", r"harness\scripts\check_client_manifest.py", "--json"],
            "evidence": {
                "summary": {"clients": 3},
                "readiness": {"full_lifecycle_multi_client": {"ready": False}},
                "contracts": valid_client_contracts(),
                "clients": [{"id": "claude_code", "status": "stable", "support_level": "full_lifecycle"}],
                "claim_policy": {"checked": 3, "required": 3, "findings": []},
                "remediation_plan": valid_client_remediation_plan(),
            },
        }

    def client_portability_gap_row(self, include_evidence: bool = True) -> dict:
        row = {
            "issue_id": "oss-client_portability",
            "check_id": "client_portability",
            "severity": "warning",
            "gap_type": "verified_capability",
            "owner": "maintainer",
            "title": "Client support scope is explicit",
            "summary": "stable_full_lifecycle=1, stable_context=2",
            "resolution": "Keep the external claim narrow or add another full-lifecycle stable client.",
            "next_action": "Keep the external claim narrow.",
            "command": ["python", r"harness\scripts\check_client_manifest.py", "--json"],
        }
        if include_evidence:
            row["evidence"] = {
                "readiness": {"full_lifecycle_multi_client": {"ready": False}},
                "contracts": valid_client_contracts(),
                "clients": [{"id": "claude_code", "status": "stable", "support_level": "full_lifecycle"}],
                "claim_policy": {"checked": 3, "required": 3, "findings": []},
                "remediation_plan": valid_client_remediation_plan(),
            }
            row["client_lifecycle_gaps"] = valid_client_lifecycle_gaps()
        return row

    def publish_scope_gap_row(self) -> dict:
        return {
            "issue_id": "oss-publish_scope",
            "check_id": "publish_scope",
            "severity": "blocker",
            "gap_type": "publish_scope_governance",
            "owner": "project_owner",
            "title": "Tracked files fit the external publish scope",
            "summary": "tracked_private_paths=3, unclassified_tracked_paths=0",
            "resolution": "Decide whether private tracked paths are split, excluded, redacted, or fixture-replaced.",
            "next_action": "Split, redact, or explicitly approve private data paths.",
            "decision": "publish_scope_boundary",
            "record_status": "undecided",
            "decision_doc": "docs/publish-scope.md",
            "required_artifacts": [],
            "required_when": {"private_tracked_paths": 3, "unclassified_tracked_paths": 0},
            "allowed_options": ["split_clean_source_repository"],
            "publish_scope_breakdown": valid_publish_scope_gap_breakdown(),
            "record_dry_run_command": [
                "python",
                r"harness\maintain.py",
                "release-record-decision",
                "--dry-run",
                "--decision",
                "publish_scope_boundary",
                "--selected-option",
                "<option>",
                "--decided-by",
                "<owner>",
                "--decided-at",
                "YYYY-MM-DD",
                "--json",
            ],
            "record_write_command": [
                "python",
                r"harness\maintain.py",
                "release-record-decision",
                "--write",
                "--decision",
                "publish_scope_boundary",
                "--selected-option",
                "<option>",
                "--decided-by",
                "<owner>",
                "--decided-at",
                "YYYY-MM-DD",
                "--json",
            ],
            "record_gate_effect": {
                "effect": "records_owner_choice_only",
                "clears_release_blocker": False,
                "next_check": "rerun release-check after required artifacts or publish-scope changes are complete",
            },
            "gate_unblock_requirements": {
                "status": "blocked_until_requirements_clear",
                "requirements": [
                    {
                        "kind": "required_conditions",
                        "values": {"private_tracked_paths": 3, "unclassified_tracked_paths": 0},
                    },
                ],
            },
        }

    def test_valid_ledger_has_remaining_gap_table(self) -> None:
        findings = validate_release_issue_ledger_contract(ledger_case(), valid_ledger_report())

        self.assertEqual(findings, [])

    def test_remaining_gap_table_must_match_issue_list(self) -> None:
        report = valid_ledger_report()
        report["remaining_gap_table"]["owner_decisions"] = []

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_remaining_gap_table_owner_decisions_mismatch", codes(findings))

    def test_remaining_gap_table_owner_decisions_must_keep_decision_doc(self) -> None:
        report = valid_ledger_report()
        report["remaining_gap_table"]["owner_decisions"][0]["decision_doc"] = ""

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_remaining_gap_table_decision_doc", codes(findings))

    def test_ledger_owner_decision_ready_must_mirror_gate_ready(self) -> None:
        report = valid_ledger_report()
        report["owner_decisions"][0]["ready"] = True

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_owner_decision_ready_gate_ready_mismatch", codes(findings))

    def test_ledger_owner_decision_record_ready_must_match_record_state(self) -> None:
        report = valid_ledger_report()
        report["owner_decisions"][0]["record_ready"] = True

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_owner_decision_record_ready_mismatch", codes(findings))

    def test_ledger_owner_decision_gate_unblock_must_match_requirements(self) -> None:
        report = valid_ledger_report()
        report["owner_decisions"][0]["gate_unblock_requirements"]["requirements"] = [
            {"kind": "required_conditions", "values": {"private_tracked_paths": 1}},
        ]

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_owner_decision_gate_unblock_requirements_mismatch", codes(findings))

    def test_ledger_client_portability_issue_must_keep_scan_evidence(self) -> None:
        report = valid_ledger_report()
        issue = self.client_portability_issue()
        issue["evidence"] = {"summary": {"clients": 3}}
        report["issues"].append(issue)

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_client_portability_readiness", codes(findings))
        self.assertIn("ledger_client_portability_clients", codes(findings))

    def test_ledger_client_portability_issue_must_keep_lifecycle_contracts(self) -> None:
        report = valid_ledger_report()
        issue = self.client_portability_issue()
        issue["evidence"].pop("contracts")
        report["issues"].append(issue)

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_client_portability_contracts", codes(findings))

    def test_ledger_client_portability_issue_must_keep_remediation_plan(self) -> None:
        report = valid_ledger_report()
        issue = self.client_portability_issue()
        issue["evidence"].pop("remediation_plan")
        report["issues"].append(issue)

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_client_portability_remediation_plan", codes(findings))

    def test_ledger_docs_entrypoints_issue_must_keep_frontmatter_evidence(self) -> None:
        report = valid_ledger_report()
        report["issues"].append({
            "issue_id": "oss-docs_entrypoints",
            "check_id": "docs_entrypoints",
            "state": "resolved",
            "severity": "info",
            "gap": {
                "type": "verified_capability",
                "owner": "maintainer",
                "resolution": "Keep this check green.",
            },
            "evidence": {"findings": []},
        })

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_docs_entrypoints_frontmatter_checked", codes(findings))

    def test_remaining_gap_table_client_portability_must_keep_scan_evidence(self) -> None:
        report = valid_ledger_report()
        report["issues"].append(self.client_portability_issue())
        report["remaining_gap_table"]["docs_publish_scope_governance"].append(
            self.client_portability_gap_row(include_evidence=False)
        )
        report["summary"]["open_by_gap_type"] = {"owner_decision": 1, "verified_capability": 1}
        report["summary"]["open_by_owner"] = {"project_owner": 1, "maintainer": 1}

        findings = validate_release_issue_ledger_contract(ledger_case(), report)

        self.assertIn("ledger_remaining_gap_table_client_portability_evidence", codes(findings))

    def test_owner_decisions_view_summarizes_gate_and_record_readiness(self) -> None:
        report = valid_ledger_report()
        view = {
            "schema_version": 1,
            "kind": "release_owner_decisions",
            "summary": {
                "owner_decisions": 1,
                "ready": 0,
                "not_ready": 1,
                "gate_ready": 0,
                "gate_not_ready": 1,
                "record_ready": 0,
                "record_not_ready": 1,
                "decision_state_findings": 0,
                "owner_decision_records": report["summary"]["owner_decision_records"],
            },
            "owner_decisions": report["owner_decisions"],
            "decision_state_findings": [],
        }

        findings = validate_release_owner_decisions_contract(owner_decisions_case(), view)

        self.assertEqual(findings, [])

    def test_valid_gap_table_has_no_findings(self) -> None:
        report = valid_ledger_report()
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 0,
                "deferred": 1,
                "open_by_gap_type": {"owner_decision": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertEqual(findings, [])

    def test_gap_table_summary_must_match_rows(self) -> None:
        report = valid_ledger_report()
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 0,
                "code_remediation": 0,
                "docs_publish_scope_governance": 0,
                "deferred": 1,
                "open_by_gap_type": {"owner_decision": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertIn("gap_table_owner_decisions_summary_mismatch", codes(findings))

    def test_gap_table_owner_decisions_must_keep_decision_doc(self) -> None:
        report = valid_ledger_report()
        report["remaining_gap_table"]["owner_decisions"][0]["decision_doc"] = ""
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 0,
                "deferred": 1,
                "open_by_gap_type": {"owner_decision": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertIn("gap_table_decision_doc", codes(findings))

    def test_gap_table_publish_scope_must_keep_private_breakdown(self) -> None:
        report = valid_ledger_report()
        report["remaining_gap_table"]["owner_decisions"] = [self.publish_scope_gap_row()]
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 0,
                "deferred": 1,
                "open_by_gap_type": {"publish_scope_governance": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertEqual(findings, [])

    def test_gap_table_publish_scope_breakdown_totals_must_match(self) -> None:
        report = valid_ledger_report()
        row = self.publish_scope_gap_row()
        row["publish_scope_breakdown"]["private_tracked_summary"]["by_path_group"][0]["count"] = 1
        report["remaining_gap_table"]["owner_decisions"] = [row]
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 0,
                "deferred": 1,
                "open_by_gap_type": {"publish_scope_governance": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertIn("gap_table_publish_scope_private_by_path_group_total", codes(findings))

    def test_gap_table_gap_type_summary_must_match_rows(self) -> None:
        report = valid_ledger_report()
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 0,
                "deferred": 1,
                "open_by_gap_type": {"code_remediation": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertIn("gap_table_gap_type_summary_mismatch", codes(findings))

    def test_gap_table_client_portability_must_keep_scan_evidence(self) -> None:
        report = valid_ledger_report()
        report["remaining_gap_table"]["docs_publish_scope_governance"].append(
            self.client_portability_gap_row(include_evidence=False)
        )
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 1,
                "deferred": 1,
                "open_by_gap_type": {"owner_decision": 1, "verified_capability": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertIn("gap_table_client_portability_evidence", codes(findings))

    def test_gap_table_client_portability_must_keep_lifecycle_contracts(self) -> None:
        report = valid_ledger_report()
        row = self.client_portability_gap_row()
        row["evidence"].pop("contracts")
        report["remaining_gap_table"]["docs_publish_scope_governance"].append(row)
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 1,
                "deferred": 1,
                "open_by_gap_type": {"owner_decision": 1, "verified_capability": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertIn("gap_table_client_portability_contracts", codes(findings))

    def test_gap_table_client_portability_must_keep_lifecycle_gap_summary(self) -> None:
        report = valid_ledger_report()
        row = self.client_portability_gap_row()
        row.pop("client_lifecycle_gaps")
        report["remaining_gap_table"]["docs_publish_scope_governance"].append(row)
        gap_table = {
            "schema_version": 1,
            "kind": "release_gap_table",
            "summary": {
                "owner_decisions": 1,
                "code_remediation": 0,
                "docs_publish_scope_governance": 1,
                "deferred": 1,
                "open_by_gap_type": {"owner_decision": 1, "verified_capability": 1},
            },
            "remaining_gap_table": report["remaining_gap_table"],
        }

        findings = validate_release_gap_table_contract(gap_table_case(), gap_table)

        self.assertIn("gap_table_client_portability_lifecycle_gaps", codes(findings))

    def test_valid_owner_decision_template_has_no_findings(self) -> None:
        findings = validate_release_owner_decision_template_contract(
            decision_template_case(),
            valid_decision_template_report(),
        )

        self.assertEqual(findings, [])

    def test_owner_decision_template_requires_top_level_patch_entry(self) -> None:
        report = valid_decision_template_report()
        report["state_patch_template"]["decisions"] = {}

        findings = validate_release_owner_decision_template_contract(decision_template_case(), report)

        self.assertIn("owner_decision_template_patch_missing_decision", codes(findings))

    def test_owner_decision_template_requires_record_gate_effect(self) -> None:
        report = valid_decision_template_report()
        report["templates"][0]["record_gate_effect"]["clears_release_blocker"] = True

        findings = validate_release_owner_decision_template_contract(decision_template_case(), report)

        self.assertIn("owner_decision_template_record_gate_effect_clears_release_blocker", codes(findings))

    def test_valid_owner_decision_record_dry_run_has_no_findings(self) -> None:
        findings = validate_release_owner_decision_record_contract(
            record_decision_case(),
            valid_record_decision_report(),
        )

        self.assertEqual(findings, [])

    def test_valid_publish_scope_record_dry_run_has_no_findings(self) -> None:
        findings = validate_release_owner_decision_record_contract(
            publish_scope_record_decision_case(),
            valid_publish_scope_record_decision_report(),
        )

        self.assertEqual(findings, [])

    def test_owner_decision_record_requires_dry_run_in_contract(self) -> None:
        report = valid_record_decision_report()
        report["dry_run"] = False

        findings = validate_release_owner_decision_record_contract(record_decision_case(), report)

        self.assertIn("owner_decision_record_dry_run", codes(findings))

    def test_owner_decision_record_requires_record_gate_effect(self) -> None:
        report = valid_record_decision_report()
        report["record_gate_effect"]["effect"] = "clears_release_blocker"

        findings = validate_release_owner_decision_record_contract(record_decision_case(), report)

        self.assertIn("owner_decision_record_record_gate_effect_effect", codes(findings))


if __name__ == "__main__":
    unittest.main()
