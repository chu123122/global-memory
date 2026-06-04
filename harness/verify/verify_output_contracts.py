#!/usr/bin/env python3
"""Verify CLI output contracts for harness scripts.

Default mode runs read-only JSON entrypoints and checks that stdout is exact JSON,
stderr is clean on success, and machine JSON does not embed large human console
transcripts. Mutating commands are not executed unless explicitly requested.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = HARNESS_DIR.parent


@dataclass(frozen=True)
class ContractCase:
    id: str
    cmd: list[str]
    cwd: Path = REPO_DIR
    expect_json: bool = True
    mutating: bool = False
    allow_returncodes: tuple[int, ...] = (0, 1)
    allow_raw_output_keys: bool = False


@dataclass
class Finding:
    level: str
    case_id: str
    code: str
    message: str
    path: str = ""


def py(script: str, *args: str) -> list[str]:
    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = HARNESS_DIR / script
    return [sys.executable, str(script_path), *args]


def default_cases() -> list[ContractCase]:
    return [
        ContractCase("maintain_status", py("maintain.py", "status", "--json")),
        ContractCase(
            "maintain_sync_preview",
            py("maintain.py", "sync", "--preview", "--source", "manual", "--json"),
        ),
        ContractCase("maintain_log", py("maintain.py", "log", "--json", "--limit", "8")),
        ContractCase("maintain_daemon_status", py("maintain.py", "daemon", "status", "--json")),
        ContractCase("maintain_doctor", py("maintain.py", "doctor", "--json")),
        ContractCase("maintain_release_check", py("maintain.py", "release-check", "--json", "--skip-output-contracts")),
        ContractCase("maintain_release_checkpoint", py("maintain.py", "release-checkpoint", "--json")),
        ContractCase("maintain_release_checkpoint_strict", py("maintain.py", "release-checkpoint", "--strict", "--json")),
        ContractCase("maintain_release_gaps", py("maintain.py", "release-gaps", "--json")),
        ContractCase("maintain_release_gaps_strict", py("maintain.py", "release-gaps", "--strict", "--json")),
        ContractCase("maintain_release_decisions", py("maintain.py", "release-decisions", "--json")),
        ContractCase("maintain_release_decisions_strict", py("maintain.py", "release-decisions", "--strict", "--json")),
        ContractCase("maintain_release_decisions_template", py("maintain.py", "release-decisions", "--template", "--json")),
        ContractCase(
            "maintain_release_record_decision_dry_run",
            py(
                "maintain.py",
                "release-record-decision",
                "--dry-run",
                "--decision",
                "license_policy",
                "--selected-option",
                "no_public_license",
                "--decided-by",
                "contract-test",
                "--decided-at",
                "2026-05-25",
                "--json",
            ),
        ),
        ContractCase(
            "maintain_release_record_publish_scope_dry_run",
            py(
                "maintain.py",
                "release-record-decision",
                "--dry-run",
                "--decision",
                "publish_scope_boundary",
                "--selected-option",
                "keep_private_maturity_audit",
                "--decided-by",
                "contract-test",
                "--decided-at",
                "2026-05-26",
                "--json",
            ),
        ),
        ContractCase("harness_tasks", py("reporting/harness_status.py", "--tasks", "--json")),
        ContractCase("verify_prompt_system", py("verify/verify_prompt_system.py", "--json")),
        ContractCase("smoke_test", py("verify/smoke_test.py", "--json")),
        ContractCase("oss_readiness_check", py("scripts/oss_readiness_check.py", "--json", "--skip-output-contracts")),
        ContractCase("gate_check", py("scripts/gate_check.py", "--json")),
        ContractCase("scan_dual_storage", py("scripts/scan_dual_storage.py", "--json")),
        ContractCase("scan_orphan_scripts", py("scripts/scan_orphan_scripts.py", "--strict", "--json")),
        ContractCase("check_capability_manifest", py("scripts/check_capability_manifest.py", "--json")),
        ContractCase("check_client_manifest", py("scripts/check_client_manifest.py", "--json")),
        ContractCase("check_hook_alignment", py("scripts/check_hook_alignment.py", "--strict", "--json")),
        ContractCase("check_publish_scope", py("scripts/check_publish_scope.py", "--json")),
        ContractCase("export_source_scope", py("scripts/export_source_scope.py", "--json")),
        ContractCase("scan_external_safety", py("scripts/scan_external_safety.py", "--json")),
        ContractCase("release_issue_ledger", py("scripts/release_issue_ledger.py", "--json")),
        ContractCase("release_gap_table", py("scripts/release_issue_ledger.py", "--gap-table-only", "--json")),
        ContractCase("release_owner_decisions", py("scripts/release_issue_ledger.py", "--owner-decisions-only", "--json")),
        ContractCase("release_owner_decision_template", py("scripts/release_issue_ledger.py", "--decision-template", "--json")),
        ContractCase("client_context", py("scripts/client_context.py", "--json", "--task", "unknown", "--query", "test")),
        ContractCase("client_context_generic_cli", py("scripts/client_context.py", "--client", "generic_cli", "--task", "unknown", "--query", "test", "--json")),
        ContractCase("generate_catalog_check", py("generate_catalog.py", "--check", "--json")),
        ContractCase("audit_skill_all", py("audit_skill.py", "--all", "--json")),
        ContractCase("analyze_retrieve_log", py("scripts/analyze_retrieve_log.py", "--json")),
        ContractCase("work_context_pack", py("work_context_pack.py", "--json")),
        ContractCase("work_context_pack_intent_guard", py("work_context_pack.py", "--intent", "新开一个维护 task", "--json")),
        ContractCase("check_prepare", py("check_prepare.py", "--json")),
        ContractCase("self_loop_report", py("scripts/self_loop_report.py", "--json")),
        ContractCase("meta_optimize", py("scripts/meta_optimize.py", "--json")),
    ]


def mutating_cases() -> list[ContractCase]:
    return [
        ContractCase(
            "maintain_fix",
            py("maintain.py", "fix", "--json"),
            mutating=True,
        ),
    ]


def run_case(case: ContractCase, timeout: int) -> tuple[subprocess.CompletedProcess[str] | None, float, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    start = time.time()
    try:
        proc = subprocess.run(
            case.cmd,
            cwd=str(case.cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc, time.time() - start, ""
    except subprocess.TimeoutExpired as exc:
        return None, time.time() - start, f"timeout after {exc.timeout}s"
    except Exception as exc:  # noqa: BLE001 - checker must keep going
        return None, time.time() - start, f"{type(exc).__name__}: {exc}"


def validate_case(case: ContractCase, proc: subprocess.CompletedProcess[str] | None, error: str) -> tuple[Any, list[Finding]]:
    findings: list[Finding] = []
    if proc is None:
        findings.append(Finding("ERROR", case.id, "command_failed", error))
        return None, findings

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if proc.returncode not in case.allow_returncodes:
        findings.append(Finding(
            "ERROR",
            case.id,
            "unexpected_returncode",
            f"returncode={proc.returncode}, allowed={case.allow_returncodes}",
        ))
    if proc.returncode == 0 and stderr.strip():
        findings.append(Finding("WARNING", case.id, "stderr_on_success", stderr.strip()[:300]))

    data = None
    if case.expect_json:
        stripped = stdout.strip()
        if not stripped:
            findings.append(Finding("ERROR", case.id, "empty_stdout", "expected JSON on stdout"))
        else:
            if not stripped.startswith(("{", "[")):
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    "json_prefix_noise",
                    f"stdout starts with non-JSON text: {stripped[:120]!r}",
                ))
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError as exc:
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    "invalid_json",
                    f"{exc.msg} at line {exc.lineno} column {exc.colno}",
                ))
            else:
                findings.extend(validate_json_payload(case, data))
                findings.extend(validate_case_specific_payload(case, data))
    return data, findings


def validate_case_specific_payload(case: ContractCase, data: Any) -> list[Finding]:
    if case.id == "maintain_status":
        return validate_maintain_status_contract(case, data)
    if case.id == "harness_tasks":
        return validate_harness_tasks_contract(case, data)
    if case.id in {"oss_readiness_check", "maintain_release_check"}:
        return validate_oss_readiness_contract(case, data)
    if case.id in {"maintain_release_checkpoint", "maintain_release_checkpoint_strict"}:
        return validate_release_checkpoint_contract(case, data)
    if case.id == "smoke_test":
        return validate_smoke_test_contract(case, data)
    if case.id == "release_issue_ledger":
        return validate_release_issue_ledger_contract(case, data)
    if case.id in {"release_gap_table", "maintain_release_gaps", "maintain_release_gaps_strict"}:
        return validate_release_gap_table_contract(case, data)
    if case.id in {"release_owner_decisions", "maintain_release_decisions", "maintain_release_decisions_strict"}:
        return validate_release_owner_decisions_contract(case, data)
    if case.id in {"release_owner_decision_template", "maintain_release_decisions_template"}:
        return validate_release_owner_decision_template_contract(case, data)
    if case.id in {"maintain_release_record_decision_dry_run", "maintain_release_record_publish_scope_dry_run"}:
        return validate_release_owner_decision_record_contract(case, data)
    if case.id == "gate_check":
        return validate_gate_check_contract(case, data)
    if case.id == "check_hook_alignment":
        return validate_hook_alignment_contract(case, data)
    if case.id == "check_publish_scope":
        return validate_publish_scope_contract(case, data)
    if case.id == "export_source_scope":
        return validate_export_source_scope_contract(case, data)
    if case.id == "scan_external_safety":
        return validate_external_source_safety_contract(case, data)
    if case.id == "scan_dual_storage":
        return validate_dual_storage_scan_contract(case, data)
    if case.id == "scan_orphan_scripts":
        return validate_orphan_script_scan_contract(case, data)
    if case.id == "check_capability_manifest":
        return validate_capability_manifest_contract(case, data)
    if case.id == "check_client_manifest":
        return validate_client_manifest_contract(case, data)
    if case.id in {"client_context", "client_context_generic_cli"}:
        return validate_client_context_contract(case, data)
    if case.id == "generate_catalog_check":
        return validate_generate_catalog_contract(case, data)
    if case.id == "audit_skill_all":
        return validate_skill_audit_contract(case, data)
    if case.id == "analyze_retrieve_log":
        return validate_analyze_retrieve_log_contract(case, data)
    if case.id.startswith("work_context_pack"):
        return validate_work_context_pack_contract(case, data)
    if case.id == "check_prepare":
        return validate_check_prepare_contract(case, data)
    if case.id == "self_loop_report":
        return validate_self_loop_report_contract(case, data)
    if case.id == "meta_optimize":
        return validate_meta_optimize_contract(case, data)
    return []


def validate_maintain_status_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "maintain_status_root_type", "expected object root", "$"))
        return findings
    if data.get("mode") != "status":
        findings.append(Finding("ERROR", case.id, "maintain_status_mode", "expected mode=status", "$.mode"))
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict):
        findings.append(Finding("ERROR", case.id, "maintain_status_capabilities_type", "expected object", "$.capabilities"))
        return findings
    for capability in ("status", "doctor", "release-check", "release-checkpoint", "release-gaps", "release-decisions"):
        require_nonempty_string(
            findings,
            case,
            capabilities.get(capability),
            f"maintain_status_capability_{capability.replace('-', '_')}_missing",
            f"$.capabilities.{capability}",
        )
    return findings


def validate_release_checkpoint_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "release_checkpoint_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "release_checkpoint":
        findings.append(Finding("ERROR", case.id, "release_checkpoint_kind", "expected kind=release_checkpoint", "$.kind"))
    require_nonempty_string(findings, case, data.get("release_verdict"), "release_checkpoint_verdict", "$.release_verdict")
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "release_checkpoint_summary_type", "expected object", "$.summary"))
        summary = {}
    for key in (
        "release_pass",
        "release_warnings",
        "release_blockers",
        "owner_decisions",
        "code_remediation",
        "docs_publish_scope_governance",
        "deferred",
        "external_source_blockers",
        "external_source_warnings",
        "owner_decision_templates",
    ):
        value = summary.get(key)
        if not isinstance(value, int) or value < 0:
            findings.append(Finding("ERROR", case.id, f"release_checkpoint_summary_{key}", "expected non-negative integer", f"$.summary.{key}"))
    if not isinstance(summary.get("owner_decision_records"), dict):
        findings.append(Finding("ERROR", case.id, "release_checkpoint_owner_records_type", "expected object", "$.summary.owner_decision_records"))
    require_nonempty_string(findings, case, summary.get("release_check_mode"), "release_checkpoint_check_mode", "$.summary.release_check_mode")
    if summary.get("release_check_output_contracts_included") is not False:
        findings.append(Finding("ERROR", case.id, "release_checkpoint_output_contracts_mode", "expected false because checkpoint release_check uses --skip-output-contracts", "$.summary.release_check_output_contracts_included"))

    checks = data.get("checks")
    if not isinstance(checks, list):
        findings.append(Finding("ERROR", case.id, "release_checkpoint_checks_type", "expected list", "$.checks"))
        checks = []
    required_ids = {
        "external_source_safety",
        "release_check",
        "release_issue_ledger",
        "release_gaps",
        "release_decisions",
        "release_decision_template",
        "capability_manifest",
        "client_manifest",
        "publish_scope_manifest",
    }
    by_id = {item.get("id"): item for item in checks if isinstance(item, dict)}
    missing = sorted(required_ids - set(by_id))
    if missing:
        findings.append(Finding("ERROR", case.id, "release_checkpoint_missing_checks", f"missing={missing}", "$.checks"))
    for check_id in required_ids & set(by_id):
        item = by_id[check_id]
        path = f"$.checks[{check_id}]"
        if item.get("parsed") is not True:
            findings.append(Finding("ERROR", case.id, f"release_checkpoint_{check_id}_parsed", "expected parsed=true", f"{path}.parsed"))
        if not isinstance(item.get("returncode"), int):
            findings.append(Finding("ERROR", case.id, f"release_checkpoint_{check_id}_returncode", "expected integer", f"{path}.returncode"))
        payload = item.get("payload")
        if not isinstance(payload, dict):
            findings.append(Finding("ERROR", case.id, f"release_checkpoint_{check_id}_payload", "expected object", f"{path}.payload"))
            continue
        if not isinstance(payload.get("summary"), dict):
            findings.append(Finding("ERROR", case.id, f"release_checkpoint_{check_id}_summary", "expected object", f"{path}.payload.summary"))
        if check_id == "release_gaps":
            findings.extend(validate_release_gap_table_contract(case, payload))
        if check_id == "release_decision_template":
            findings.extend(validate_release_owner_decision_template_contract(case, payload))
    release_payload = by_id.get("release_check", {}).get("payload", {}) if isinstance(by_id.get("release_check"), dict) else {}
    if isinstance(release_payload, dict) and release_payload.get("verdict") != data.get("release_verdict"):
        findings.append(Finding("ERROR", case.id, "release_checkpoint_verdict_mismatch", "release_verdict must mirror release_check payload verdict", "$.release_verdict"))
    template_payload = by_id.get("release_decision_template", {}).get("payload", {}) if isinstance(by_id.get("release_decision_template"), dict) else {}
    template_summary = template_payload.get("summary", {}) if isinstance(template_payload, dict) and isinstance(template_payload.get("summary"), dict) else {}
    if summary.get("owner_decision_templates") != template_summary.get("templates"):
        findings.append(Finding(
            "ERROR",
            case.id,
            "release_checkpoint_owner_decision_templates_mismatch",
            f"expected={template_summary.get('templates')}, actual={summary.get('owner_decision_templates')}",
            "$.summary.owner_decision_templates",
        ))
    return findings


def validate_harness_tasks_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "harness_tasks_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "harness_tasks_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("kind") != "harness_tasks":
        findings.append(Finding("ERROR", case.id, "harness_tasks_kind", "expected kind=harness_tasks", "$.kind"))
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "harness_tasks_summary_type", "expected object", "$.summary"))
        return findings
    active = data.get("active")
    archived = data.get("archived")
    if not isinstance(active, list):
        findings.append(Finding("ERROR", case.id, "harness_tasks_active_type", "expected list", "$.active"))
        active = []
    if not isinstance(archived, list):
        findings.append(Finding("ERROR", case.id, "harness_tasks_archived_type", "expected list", "$.archived"))
        archived = []

    def validate_task_rows(rows: list[Any], field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        names: set[str] = set()
        duplicates: set[str] = set()
        for idx, row in enumerate(rows):
            path = f"$.{field}[{idx}]"
            if not isinstance(row, dict):
                findings.append(Finding("ERROR", case.id, "harness_tasks_row_type", "expected object", path))
                continue
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                findings.append(Finding("ERROR", case.id, "harness_tasks_name", "expected non-empty string", f"{path}.name"))
            elif name in names:
                duplicates.add(name)
            else:
                names.add(name)
            stage = row.get("stage")
            if not isinstance(stage, str) or not stage.strip():
                findings.append(Finding("ERROR", case.id, "harness_tasks_stage", "expected non-empty string", f"{path}.stage"))
                stage = "unknown"
            counts[stage] = counts.get(stage, 0) + 1
            brief = row.get("brief")
            if not isinstance(brief, str):
                findings.append(Finding("ERROR", case.id, "harness_tasks_brief_type", "expected string", f"{path}.brief"))
            task_path = row.get("path")
            if not isinstance(task_path, str) or not task_path.strip():
                findings.append(Finding("ERROR", case.id, "harness_tasks_path", "expected non-empty string", f"{path}.path"))
        if duplicates:
            findings.append(Finding("WARNING", case.id, f"harness_tasks_{field}_duplicate_names", f"duplicates={sorted(duplicates)[:10]}", f"$.{field}"))
        return dict(sorted(counts.items()))

    active_counts = validate_task_rows(active, "active")
    archived_counts = validate_task_rows(archived, "archived")
    expected_counts = {
        "active": len(active),
        "archived": len(archived),
        "total": len(active) + len(archived),
        "missing_active": active_counts.get("missing", 0),
        "unknown_active": active_counts.get("unknown", 0),
    }
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            findings.append(Finding("ERROR", case.id, f"harness_tasks_summary_{key}_mismatch", f"summary={summary.get(key)}, rows={expected}", f"$.summary.{key}"))
    for key, expected in (("active_by_stage", active_counts), ("archived_by_stage", archived_counts)):
        value = summary.get(key)
        if not isinstance(value, dict):
            findings.append(Finding("ERROR", case.id, f"harness_tasks_summary_{key}_type", "expected object", f"$.summary.{key}"))
            continue
        normalized = normalize_int_map(value)
        if normalized != expected:
            findings.append(Finding("ERROR", case.id, f"harness_tasks_summary_{key}_mismatch", f"summary={normalized}, rows={expected}", f"$.summary.{key}"))
    return findings


def validate_self_loop_report_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "self_loop_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "self_loop_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("mode") != "self-loop-overview":
        findings.append(Finding("ERROR", case.id, "self_loop_mode", "expected self-loop-overview", "$.mode"))

    for key in ("inputs", "optimization_ledger", "fallback_cost", "fallback_candidates"):
        if not isinstance(data.get(key), dict):
            findings.append(Finding("ERROR", case.id, f"self_loop_{key}_type", "expected object", f"$.{key}"))
    for key in ("enabled_task_fallbacks", "assurance"):
        if not isinstance(data.get(key), list):
            findings.append(Finding("ERROR", case.id, f"self_loop_{key}_type", "expected list", f"$.{key}"))

    ledger = data.get("optimization_ledger")
    if isinstance(ledger, dict):
        count = ledger.get("count")
        latest = ledger.get("latest")
        if not isinstance(count, int) or count < 0:
            findings.append(Finding("ERROR", case.id, "self_loop_ledger_count", "expected non-negative integer", "$.optimization_ledger.count"))
        if not isinstance(latest, list):
            findings.append(Finding("ERROR", case.id, "self_loop_ledger_latest", "expected list", "$.optimization_ledger.latest"))
        elif isinstance(count, int) and len(latest) > count:
            findings.append(Finding("ERROR", case.id, "self_loop_ledger_latest_exceeds_count", f"latest={len(latest)}, count={count}", "$.optimization_ledger.latest"))

    fallback_cost = data.get("fallback_cost")
    if isinstance(fallback_cost, dict):
        if fallback_cost.get("schema_version") != 1:
            findings.append(Finding("ERROR", case.id, "self_loop_fallback_cost_schema", "expected schema_version=1", "$.fallback_cost.schema_version"))
        if not isinstance(fallback_cost.get("summary"), dict):
            findings.append(Finding("ERROR", case.id, "self_loop_fallback_cost_summary", "expected object", "$.fallback_cost.summary"))

    candidates = data.get("fallback_candidates")
    if isinstance(candidates, dict):
        if candidates.get("schema_version") != 1:
            findings.append(Finding("ERROR", case.id, "self_loop_candidates_schema", "expected schema_version=1", "$.fallback_candidates.schema_version"))
        summary = candidates.get("summary")
        candidate_rows = candidates.get("candidates")
        if not isinstance(summary, dict):
            findings.append(Finding("ERROR", case.id, "self_loop_candidates_summary", "expected object", "$.fallback_candidates.summary"))
        if not isinstance(candidate_rows, list):
            findings.append(Finding("ERROR", case.id, "self_loop_candidates_rows", "expected list", "$.fallback_candidates.candidates"))
            candidate_rows = []
        if isinstance(summary, dict):
            required = ("candidate_tasks", "accept", "already_enabled", "review", "reject")
            counts: dict[str, int] = {}
            for key in required:
                value = summary.get(key)
                if not isinstance(value, int) or value < 0:
                    findings.append(Finding("ERROR", case.id, f"self_loop_candidates_{key}", "expected non-negative integer", f"$.fallback_candidates.summary.{key}"))
                else:
                    counts[key] = value
            if len(counts) == len(required):
                total = counts["accept"] + counts["already_enabled"] + counts["review"] + counts["reject"]
                if counts["candidate_tasks"] != total:
                    findings.append(Finding("ERROR", case.id, "self_loop_candidates_count_mismatch", f"candidate_tasks={counts['candidate_tasks']}, groups={total}", "$.fallback_candidates.summary"))
                if len(candidate_rows) > counts["candidate_tasks"]:
                    findings.append(Finding("ERROR", case.id, "self_loop_candidates_rows_exceed_summary", f"rows={len(candidate_rows)}, candidate_tasks={counts['candidate_tasks']}", "$.fallback_candidates.candidates"))
    return findings


def validate_meta_optimize_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "meta_optimize_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "meta_optimize_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("mode") != "read-only":
        findings.append(Finding("ERROR", case.id, "meta_optimize_mode", "expected read-only", "$.mode"))
    require_nonempty_string(findings, case, data.get("generated_at"), "meta_optimize_generated_at", "$.generated_at")
    for key in ("inputs", "summary", "user_visible"):
        if not isinstance(data.get(key), dict):
            findings.append(Finding("ERROR", case.id, f"meta_optimize_{key}_type", "expected object", f"$.{key}"))
    findings_rows = data.get("findings")
    if not isinstance(findings_rows, list):
        findings.append(Finding("ERROR", case.id, "meta_optimize_findings_type", "expected list", "$.findings"))
        findings_rows = []

    summary = data.get("summary")
    if isinstance(summary, dict):
        count = summary.get("finding_count")
        if count != len(findings_rows):
            findings.append(Finding("ERROR", case.id, "meta_optimize_finding_count_mismatch", f"summary={count}, rows={len(findings_rows)}", "$.summary.finding_count"))
        by_severity = summary.get("by_severity")
        if not isinstance(by_severity, dict):
            findings.append(Finding("ERROR", case.id, "meta_optimize_by_severity_type", "expected object", "$.summary.by_severity"))
        else:
            expected: dict[str, int] = {}
            for row in findings_rows:
                if isinstance(row, dict) and isinstance(row.get("severity"), str):
                    expected[row["severity"]] = expected.get(row["severity"], 0) + 1
            normalized = normalize_int_map(by_severity)
            if normalized != expected:
                findings.append(Finding("ERROR", case.id, "meta_optimize_by_severity_mismatch", f"summary={normalized}, rows={expected}", "$.summary.by_severity"))

    visible = data.get("user_visible")
    if isinstance(visible, dict):
        for key in ("verdict", "conclusion", "recommended_first_action", "do_not_do_now"):
            require_nonempty_string(findings, case, visible.get(key), f"meta_optimize_visible_{key}", f"$.user_visible.{key}")
        if not isinstance(visible.get("experience_snapshot"), dict):
            findings.append(Finding("ERROR", case.id, "meta_optimize_experience_snapshot_type", "expected object", "$.user_visible.experience_snapshot"))
        if not isinstance(visible.get("top_opportunities"), list):
            findings.append(Finding("ERROR", case.id, "meta_optimize_top_opportunities_type", "expected list", "$.user_visible.top_opportunities"))

    for index, row in enumerate(findings_rows):
        path = f"$.findings[{index}]"
        if not isinstance(row, dict):
            findings.append(Finding("ERROR", case.id, "meta_optimize_finding_row_type", "expected object", path))
            continue
        for key in ("id", "severity", "area", "symptom", "suggested_change", "consumer", "risk_if_ignored", "source"):
            require_nonempty_string(findings, case, row.get(key), f"meta_optimize_finding_{key}", f"{path}.{key}")
        evidence = row.get("evidence")
        if not isinstance(evidence, list):
            findings.append(Finding("ERROR", case.id, "meta_optimize_finding_evidence_type", "expected list", f"{path}.evidence"))
        priority = row.get("priority_rank")
        if not isinstance(priority, int) or priority <= 0:
            findings.append(Finding("ERROR", case.id, "meta_optimize_finding_priority", "expected positive integer", f"{path}.priority_rank"))
    return findings


def validate_smoke_test_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "smoke_root_type", "expected object root", "$"))
        return findings

    require_nonempty_string(findings, case, data.get("timestamp"), "smoke_timestamp_missing", "$.timestamp")
    duration = data.get("duration")
    if not isinstance(duration, (int, float)) or duration < 0:
        findings.append(Finding("ERROR", case.id, "smoke_duration_invalid", "expected non-negative number", "$.duration"))

    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "smoke_summary_type", "expected object", "$.summary"))
        return findings
    results = data.get("results")
    if not isinstance(results, list):
        findings.append(Finding("ERROR", case.id, "smoke_results_type", "expected list", "$.results"))
        return findings

    statuses = ("PASS", "WARN", "FAIL", "SKIP")
    summary_counts: dict[str, int] = {}
    for status in statuses:
        value = summary.get(status)
        if not isinstance(value, int) or value < 0:
            findings.append(Finding(
                "ERROR",
                case.id,
                f"smoke_summary_{status.lower()}_invalid",
                "expected non-negative integer",
                f"$.summary.{status}",
            ))
        else:
            summary_counts[status] = value

    unexpected_summary_keys = sorted(str(key) for key in summary if key not in statuses)
    if unexpected_summary_keys:
        findings.append(Finding(
            "WARNING",
            case.id,
            "smoke_summary_unexpected_keys",
            f"unexpected={unexpected_summary_keys}",
            "$.summary",
        ))

    actual_counts = {status: 0 for status in statuses}
    seen_scripts: set[str] = set()
    duplicate_scripts: list[str] = []
    for idx, row in enumerate(results):
        path = f"$.results[{idx}]"
        if not isinstance(row, dict):
            findings.append(Finding("ERROR", case.id, "smoke_result_row_type", "expected object", path))
            continue
        script = row.get("script")
        if not isinstance(script, str) or not script.strip():
            findings.append(Finding("ERROR", case.id, "smoke_result_script_missing", "expected non-empty string", f"{path}.script"))
        elif script in seen_scripts:
            duplicate_scripts.append(script)
        else:
            seen_scripts.add(script)
        category = row.get("category")
        if not isinstance(category, str) or not category.strip():
            findings.append(Finding("ERROR", case.id, "smoke_result_category_missing", "expected non-empty string", f"{path}.category"))
        status = row.get("status")
        if status not in statuses:
            findings.append(Finding("ERROR", case.id, "smoke_result_status_invalid", f"expected one of {statuses}", f"{path}.status"))
        else:
            actual_counts[status] += 1
        exit_code = row.get("exit_code")
        if not isinstance(exit_code, int):
            findings.append(Finding("ERROR", case.id, "smoke_result_exit_code_invalid", "expected integer", f"{path}.exit_code"))
        row_duration = row.get("duration")
        if not isinstance(row_duration, (int, float)) or row_duration < 0:
            findings.append(Finding("ERROR", case.id, "smoke_result_duration_invalid", "expected non-negative number", f"{path}.duration"))
        detail = row.get("detail")
        if not isinstance(detail, str):
            findings.append(Finding("ERROR", case.id, "smoke_result_detail_type", "expected string", f"{path}.detail"))
        if status == "SKIP" and exit_code != -1:
            findings.append(Finding("ERROR", case.id, "smoke_skip_exit_code", "SKIP rows should use exit_code=-1", f"{path}.exit_code"))
        if status == "SKIP" and isinstance(detail, str) and not detail.strip():
            findings.append(Finding("ERROR", case.id, "smoke_skip_detail_missing", "SKIP rows should explain why they were skipped", f"{path}.detail"))

    if duplicate_scripts:
        findings.append(Finding(
            "WARNING",
            case.id,
            "smoke_duplicate_scripts",
            f"duplicates={sorted(set(duplicate_scripts))[:10]}",
            "$.results",
        ))

    for status, expected in summary_counts.items():
        actual = actual_counts[status]
        if expected != actual:
            findings.append(Finding(
                "ERROR",
                case.id,
                f"smoke_summary_{status.lower()}_count_mismatch",
                f"summary={expected}, rows={actual}",
                f"$.summary.{status}",
            ))

    if all(status in summary_counts for status in statuses):
        total = sum(summary_counts.values())
        if total != len(results):
            findings.append(Finding(
                "ERROR",
                case.id,
                "smoke_summary_total_mismatch",
                f"summary_total={total}, rows={len(results)}",
                "$.summary",
            ))

    if summary_counts.get("FAIL", 0) > 0:
        findings.append(Finding("ERROR", case.id, "smoke_failures_present", f"fail={summary_counts['FAIL']}", "$.summary.FAIL"))
    return findings


def validate_client_context_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "client_context_root_type", "expected object root", "$"))
        return findings

    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "client_context_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("kind") != "client_context":
        findings.append(Finding("ERROR", case.id, "client_context_kind", "expected kind=client_context", "$.kind"))
    require_nonempty_string(findings, case, data.get("client_id"), "client_context_client_id", "$.client_id")
    if case.id in {"client_context", "client_context_generic_cli"} and data.get("client_id") != "generic_cli":
        findings.append(Finding("ERROR", case.id, "client_context_client_id_generic", "expected client_id=generic_cli", "$.client_id"))
    if data.get("contract") != "global-memory.context-brief.v1":
        findings.append(Finding(
            "ERROR",
            case.id,
            "client_context_contract",
            "expected contract=global-memory.context-brief.v1",
            "$.contract",
        ))
    require_nonempty_string(findings, case, data.get("task"), "client_context_task", "$.task")
    if data.get("stage") is not None and not isinstance(data.get("stage"), str):
        findings.append(Finding("ERROR", case.id, "client_context_stage_type", "expected string or null", "$.stage"))
    ok = data.get("ok")
    if not isinstance(ok, bool):
        findings.append(Finding("ERROR", case.id, "client_context_ok_type", "expected boolean", "$.ok"))
    error = data.get("error")
    if not isinstance(error, str):
        findings.append(Finding("ERROR", case.id, "client_context_error_type", "expected string", "$.error"))
    elapsed_ms = data.get("elapsed_ms")
    if not isinstance(elapsed_ms, (int, float)) or elapsed_ms < 0:
        findings.append(Finding("ERROR", case.id, "client_context_elapsed_ms", "expected non-negative number", "$.elapsed_ms"))

    brief = data.get("brief")
    brief_text = data.get("brief_text")
    if ok is False:
        if not isinstance(error, str) or not error.strip():
            findings.append(Finding("ERROR", case.id, "client_context_error_missing", "failed payloads need non-empty error", "$.error"))
        if brief is not None:
            findings.append(Finding("ERROR", case.id, "client_context_failed_brief", "failed payloads should use brief=null", "$.brief"))
        if brief_text != "":
            findings.append(Finding("ERROR", case.id, "client_context_failed_brief_text", "failed payloads should use empty brief_text", "$.brief_text"))
        return findings

    if ok is True and error not in ("", None):
        findings.append(Finding("ERROR", case.id, "client_context_ok_error", "successful payloads should use empty error", "$.error"))
    if not isinstance(brief, dict):
        findings.append(Finding("ERROR", case.id, "client_context_brief_type", "successful payloads need object brief", "$.brief"))
        return findings
    if not isinstance(brief_text, str) or not brief_text.strip():
        findings.append(Finding("ERROR", case.id, "client_context_brief_text", "successful payloads need non-empty brief_text", "$.brief_text"))

    if not isinstance(brief.get("schema_version"), str) or not brief.get("schema_version"):
        findings.append(Finding("ERROR", case.id, "client_context_brief_schema_version", "expected non-empty string", "$.brief.schema_version"))
    if brief.get("task") != data.get("task"):
        findings.append(Finding("ERROR", case.id, "client_context_task_mismatch", "brief.task must match top-level task", "$.brief.task"))
    if brief.get("stage") != data.get("stage"):
        findings.append(Finding("ERROR", case.id, "client_context_stage_mismatch", "brief.stage must match top-level stage", "$.brief.stage"))
    if not isinstance(brief.get("handoff_path"), str):
        findings.append(Finding("ERROR", case.id, "client_context_handoff_path_type", "expected string", "$.brief.handoff_path"))
    if brief.get("load_strategy") != "just_in_time":
        findings.append(Finding("ERROR", case.id, "client_context_load_strategy", "expected just_in_time", "$.brief.load_strategy"))

    pointers = brief.get("relevant_pointers")
    if not isinstance(pointers, list):
        findings.append(Finding("ERROR", case.id, "client_context_relevant_pointers_type", "expected list", "$.brief.relevant_pointers"))
    else:
        for idx, pointer in enumerate(pointers):
            path = f"$.brief.relevant_pointers[{idx}]"
            if not isinstance(pointer, dict):
                findings.append(Finding("ERROR", case.id, "client_context_pointer_type", "expected object", path))
                continue
            require_nonempty_string(findings, case, pointer.get("path"), "client_context_pointer_path", f"{path}.path")
            require_nonempty_string(findings, case, pointer.get("why"), "client_context_pointer_why", f"{path}.why")
            summary = pointer.get("summary")
            if summary is not None and not isinstance(summary, str):
                findings.append(Finding("ERROR", case.id, "client_context_pointer_summary_type", "expected string when present", f"{path}.summary"))

    warnings = brief.get("warnings")
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        findings.append(Finding("ERROR", case.id, "client_context_warnings_type", "expected list of strings", "$.brief.warnings"))

    if isinstance(brief_text, str):
        required_fragments = ("schema_version:", "task:", "relevant_pointers:", "load_strategy:")
        missing = [fragment for fragment in required_fragments if fragment not in brief_text]
        if missing:
            findings.append(Finding("ERROR", case.id, "client_context_brief_text_shape", f"missing={missing}", "$.brief_text"))
    return findings


def validate_generate_catalog_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "catalog_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "catalog_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("kind") != "catalog_freshness_check":
        findings.append(Finding("ERROR", case.id, "catalog_kind", "expected kind=catalog_freshness_check", "$.kind"))
    if data.get("verdict") not in {"ok", "stale"}:
        findings.append(Finding("ERROR", case.id, "catalog_verdict", "expected ok or stale", "$.verdict"))
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "catalog_summary_type", "expected object", "$.summary"))
        summary = {}
    for key in ("targets", "fresh", "stale", "missing", "findings"):
        if not isinstance(summary.get(key), int):
            findings.append(Finding("ERROR", case.id, f"catalog_summary_{key}", "expected int", f"$.summary.{key}"))
    targets = data.get("targets")
    if not isinstance(targets, list):
        findings.append(Finding("ERROR", case.id, "catalog_targets_type", "expected list", "$.targets"))
        targets = []
    findings_rows = data.get("findings")
    if not isinstance(findings_rows, list):
        findings.append(Finding("ERROR", case.id, "catalog_findings_type", "expected list", "$.findings"))
        findings_rows = []
    if isinstance(summary.get("targets"), int) and summary.get("targets") != len(targets):
        findings.append(Finding("ERROR", case.id, "catalog_targets_count_mismatch", f"summary={summary.get('targets')}, rows={len(targets)}", "$.targets"))
    if isinstance(summary.get("findings"), int) and summary.get("findings") != len(findings_rows):
        findings.append(Finding("ERROR", case.id, "catalog_findings_count_mismatch", f"summary={summary.get('findings')}, rows={len(findings_rows)}", "$.findings"))
    fresh_rows = 0
    stale_rows = 0
    missing_rows = 0
    seen_paths: set[str] = set()
    for index, item in enumerate(targets):
        item_path = f"$.targets[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "catalog_target_type", "expected object", item_path))
            continue
        relpath = item.get("path")
        require_nonempty_string(findings, case, relpath, "catalog_target_path", f"{item_path}.path")
        if isinstance(relpath, str):
            if relpath in seen_paths:
                findings.append(Finding("ERROR", case.id, "catalog_target_duplicate", relpath, f"{item_path}.path"))
            seen_paths.add(relpath)
        if not isinstance(item.get("exists"), bool):
            findings.append(Finding("ERROR", case.id, "catalog_target_exists", "expected bool", f"{item_path}.exists"))
        if not isinstance(item.get("fresh"), bool):
            findings.append(Finding("ERROR", case.id, "catalog_target_fresh", "expected bool", f"{item_path}.fresh"))
        for key in ("expected_lines", "actual_lines"):
            if not isinstance(item.get(key), int):
                findings.append(Finding("ERROR", case.id, f"catalog_target_{key}", "expected int", f"{item_path}.{key}"))
        if item.get("fresh") is True:
            fresh_rows += 1
        elif item.get("exists") is False:
            missing_rows += 1
        else:
            stale_rows += 1
    expected_pairs = (
        ("fresh", fresh_rows, "catalog_fresh_count_mismatch"),
        ("stale", stale_rows, "catalog_stale_count_mismatch"),
        ("missing", missing_rows, "catalog_missing_count_mismatch"),
    )
    for key, actual, code in expected_pairs:
        if isinstance(summary.get(key), int) and summary.get(key) != actual:
            findings.append(Finding("ERROR", case.id, code, f"summary={summary.get(key)}, rows={actual}", f"$.summary.{key}"))
    for index, item in enumerate(findings_rows):
        item_path = f"$.findings[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "catalog_finding_type", "expected object", item_path))
            continue
        require_nonempty_string(findings, case, item.get("path"), "catalog_finding_path", f"{item_path}.path")
        if item.get("issue") not in {"missing_catalog", "stale_catalog"}:
            findings.append(Finding("ERROR", case.id, "catalog_finding_issue", "expected missing_catalog or stale_catalog", f"{item_path}.issue"))
    expected_verdict = "stale" if findings_rows else "ok"
    if data.get("verdict") != expected_verdict:
        findings.append(Finding("ERROR", case.id, "catalog_verdict_mismatch", f"expected {expected_verdict}", "$.verdict"))
    return findings


def validate_skill_audit_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "skill_audit_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "skill_audit_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("kind") != "skill_audit":
        findings.append(Finding("ERROR", case.id, "skill_audit_kind", "expected kind=skill_audit", "$.kind"))

    skills = data.get("skills")
    if not isinstance(skills, list):
        findings.append(Finding("ERROR", case.id, "skill_audit_skills_type", "expected list", "$.skills"))
        return findings
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "skill_audit_summary_type", "expected object", "$.summary"))
        return findings

    valid_levels = {"PASS", "WARNING", "CONDITIONAL", "FAIL"}
    level_counts = {level: 0 for level in valid_levels}
    issue_counts = {"ERROR": 0, "WARNING": 0}
    issue_code_counts: dict[tuple[str, str], int] = {}
    deployed_extras = 0
    for idx, skill in enumerate(skills):
        path = f"$.skills[{idx}]"
        if not isinstance(skill, dict):
            findings.append(Finding("ERROR", case.id, "skill_audit_skill_row_type", "expected object", path))
            continue
        require_nonempty_string(findings, case, skill.get("name"), "skill_audit_skill_name", f"{path}.name")
        require_nonempty_string(findings, case, skill.get("path"), "skill_audit_skill_path", f"{path}.path")
        level = skill.get("level")
        if level not in valid_levels:
            findings.append(Finding("ERROR", case.id, "skill_audit_skill_level", f"expected one of {sorted(valid_levels)}", f"{path}.level"))
        else:
            level_counts[level] += 1
        for key in ("line_count", "estimated_tokens"):
            value = skill.get(key)
            if value is not None and (not isinstance(value, int) or value < 0):
                findings.append(Finding("ERROR", case.id, f"skill_audit_skill_{key}", "expected non-negative integer", f"{path}.{key}"))
        issues = skill.get("issues")
        if not isinstance(issues, list):
            findings.append(Finding("ERROR", case.id, "skill_audit_skill_issues_type", "expected list", f"{path}.issues"))
            continue
        has_deployed_extra = False
        for issue_idx, issue in enumerate(issues):
            issue_path = f"{path}.issues[{issue_idx}]"
            if not isinstance(issue, dict):
                findings.append(Finding("ERROR", case.id, "skill_audit_issue_type", "expected object", issue_path))
                continue
            issue_level = issue.get("level")
            if issue_level not in issue_counts:
                findings.append(Finding("ERROR", case.id, "skill_audit_issue_level", "expected ERROR or WARNING", f"{issue_path}.level"))
            else:
                issue_counts[issue_level] += 1
            code = issue.get("code")
            if not isinstance(code, str) or not code.strip():
                findings.append(Finding("ERROR", case.id, "skill_audit_issue_code", "expected non-empty string", f"{issue_path}.code"))
            elif isinstance(issue_level, str):
                issue_code_counts[(issue_level, code)] = issue_code_counts.get((issue_level, code), 0) + 1
                if code == "deployed-extra":
                    has_deployed_extra = True
            require_nonempty_string(findings, case, issue.get("message"), "skill_audit_issue_message", f"{issue_path}.message")
        if has_deployed_extra:
            deployed_extras += 1

    expected_level = "FAIL" if level_counts["FAIL"] else (
        "CONDITIONAL" if level_counts["CONDITIONAL"] else (
            "WARNING" if level_counts["WARNING"] else "PASS"
        )
    )
    if data.get("level") != expected_level:
        findings.append(Finding("ERROR", case.id, "skill_audit_level_mismatch", f"expected={expected_level}, actual={data.get('level')}", "$.level"))

    checked = summary.get("checked_skills")
    if checked != len(skills):
        findings.append(Finding("ERROR", case.id, "skill_audit_checked_count_mismatch", f"summary={checked}, rows={len(skills)}", "$.summary.checked_skills"))

    summary_level_counts = summary.get("level_counts")
    if not isinstance(summary_level_counts, dict):
        findings.append(Finding("ERROR", case.id, "skill_audit_level_counts_type", "expected object", "$.summary.level_counts"))
    else:
        for level in sorted(valid_levels):
            if summary_level_counts.get(level) != level_counts[level]:
                findings.append(Finding("ERROR", case.id, "skill_audit_level_count_mismatch", f"{level}: summary={summary_level_counts.get(level)}, rows={level_counts[level]}", f"$.summary.level_counts.{level}"))

    summary_issue_counts = summary.get("issue_counts")
    if not isinstance(summary_issue_counts, dict):
        findings.append(Finding("ERROR", case.id, "skill_audit_issue_counts_type", "expected object", "$.summary.issue_counts"))
    else:
        for level in ("ERROR", "WARNING"):
            if summary_issue_counts.get(level) != issue_counts[level]:
                findings.append(Finding("ERROR", case.id, "skill_audit_issue_count_mismatch", f"{level}: summary={summary_issue_counts.get(level)}, rows={issue_counts[level]}", f"$.summary.issue_counts.{level}"))

    if summary.get("deployed_extras") != deployed_extras:
        findings.append(Finding("ERROR", case.id, "skill_audit_deployed_extra_count_mismatch", f"summary={summary.get('deployed_extras')}, rows={deployed_extras}", "$.summary.deployed_extras"))

    by_issue_code = summary.get("by_issue_code")
    if not isinstance(by_issue_code, list):
        findings.append(Finding("ERROR", case.id, "skill_audit_by_issue_code_type", "expected list", "$.summary.by_issue_code"))
    else:
        seen: dict[tuple[str, str], int] = {}
        for idx, row in enumerate(by_issue_code):
            path = f"$.summary.by_issue_code[{idx}]"
            if not isinstance(row, dict):
                findings.append(Finding("ERROR", case.id, "skill_audit_by_issue_code_row_type", "expected object", path))
                continue
            level = row.get("level")
            code = row.get("code")
            count = row.get("count")
            if level not in issue_counts:
                findings.append(Finding("ERROR", case.id, "skill_audit_by_issue_code_level", "expected ERROR or WARNING", f"{path}.level"))
                continue
            if not isinstance(code, str) or not code.strip():
                findings.append(Finding("ERROR", case.id, "skill_audit_by_issue_code_code", "expected non-empty string", f"{path}.code"))
                continue
            if not isinstance(count, int) or count <= 0:
                findings.append(Finding("ERROR", case.id, "skill_audit_by_issue_code_count", "expected positive integer", f"{path}.count"))
                continue
            seen[(level, code)] = count
        if seen != issue_code_counts:
            findings.append(Finding("ERROR", case.id, "skill_audit_by_issue_code_mismatch", f"summary={seen}, rows={issue_code_counts}", "$.summary.by_issue_code"))
    return findings


def validate_analyze_retrieve_log_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "retrieve_log_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != "v2":
        findings.append(Finding("ERROR", case.id, "retrieve_log_schema_version", "expected schema_version=v2", "$.schema_version"))
    total = data.get("total_calls")
    if not isinstance(total, int) or total < 0:
        findings.append(Finding("ERROR", case.id, "retrieve_log_total_calls", "expected non-negative int", "$.total_calls"))
        total = 0
    if total == 0:
        require_nonempty_string(findings, case, data.get("note"), "retrieve_log_empty_note", "$.note")
        return findings
    zero_hit = data.get("zero_hit_calls")
    if not isinstance(zero_hit, int) or zero_hit < 0 or zero_hit > total:
        findings.append(Finding("ERROR", case.id, "retrieve_log_zero_hit_calls", "expected 0 <= zero_hit_calls <= total_calls", "$.zero_hit_calls"))
        zero_hit = 0
    zero_rate = data.get("zero_hit_rate")
    expected_zero_rate = round(zero_hit / total, 3) if total else 0
    if not isinstance(zero_rate, (int, float)) or abs(float(zero_rate) - expected_zero_rate) > 0.001:
        findings.append(Finding("ERROR", case.id, "retrieve_log_zero_hit_rate", f"expected={expected_zero_rate}, actual={zero_rate}", "$.zero_hit_rate"))
    avg = data.get("avg_elapsed_ms")
    if not isinstance(avg, (int, float)) or avg < 0:
        findings.append(Finding("ERROR", case.id, "retrieve_log_avg_elapsed_ms", "expected non-negative number", "$.avg_elapsed_ms"))
    distribution = data.get("hit_count_distribution")
    if not isinstance(distribution, dict):
        findings.append(Finding("ERROR", case.id, "retrieve_log_distribution_type", "expected object", "$.hit_count_distribution"))
    else:
        dist_total = 0
        for key, value in distribution.items():
            if not str(key).isdigit() or not isinstance(value, int) or value < 0:
                findings.append(Finding("ERROR", case.id, "retrieve_log_distribution_row", "expected numeric string keys and non-negative int values", "$.hit_count_distribution"))
                continue
            dist_total += value
        if dist_total != total:
            findings.append(Finding("ERROR", case.id, "retrieve_log_distribution_total", f"total_calls={total}, distribution={dist_total}", "$.hit_count_distribution"))
        if isinstance(zero_hit, int) and distribution.get("0") != zero_hit:
            findings.append(Finding("ERROR", case.id, "retrieve_log_distribution_zero_hit", "hit_count_distribution['0'] must match zero_hit_calls", "$.hit_count_distribution.0"))
    top_rows = data.get("top1_path_top10")
    if not isinstance(top_rows, list) or len(top_rows) > 10:
        findings.append(Finding("ERROR", case.id, "retrieve_log_top1_type", "expected top1_path_top10 list of up to 10 rows", "$.top1_path_top10"))
    else:
        for index, row in enumerate(top_rows):
            path = f"$.top1_path_top10[{index}]"
            if not isinstance(row, list) or len(row) != 2:
                findings.append(Finding("ERROR", case.id, "retrieve_log_top1_row_type", "expected [path, count]", path))
                continue
            require_nonempty_string(findings, case, row[0], "retrieve_log_top1_path", f"{path}[0]")
            if not isinstance(row[1], int) or row[1] <= 0:
                findings.append(Finding("ERROR", case.id, "retrieve_log_top1_count", "expected positive int", f"{path}[1]"))
    noisy = data.get("noisy_kw_candidates")
    if not isinstance(noisy, list):
        findings.append(Finding("ERROR", case.id, "retrieve_log_noisy_type", "expected list", "$.noisy_kw_candidates"))
    else:
        for index, row in enumerate(noisy):
            path = f"$.noisy_kw_candidates[{index}]"
            if not isinstance(row, dict):
                findings.append(Finding("ERROR", case.id, "retrieve_log_noisy_row_type", "expected object", path))
                continue
            require_nonempty_string(findings, case, row.get("why"), "retrieve_log_noisy_why", f"{path}.why")
            if not isinstance(row.get("freq"), int) or row.get("freq") <= 0:
                findings.append(Finding("ERROR", case.id, "retrieve_log_noisy_freq", "expected positive int", f"{path}.freq"))
            share = row.get("share")
            if not isinstance(share, (int, float)) or share < 0 or share > 1:
                findings.append(Finding("ERROR", case.id, "retrieve_log_noisy_share", "expected number between 0 and 1", f"{path}.share"))
    namespace = data.get("namespace_distribution")
    if not isinstance(namespace, dict) or not all(isinstance(key, str) and isinstance(value, int) and value >= 0 for key, value in namespace.items()):
        findings.append(Finding("ERROR", case.id, "retrieve_log_namespace_distribution", "expected string to non-negative int map", "$.namespace_distribution"))
    miss_total = data.get("miss_queries_total")
    miss_sample = data.get("miss_queries_sample")
    if not isinstance(miss_total, int) or miss_total < 0:
        findings.append(Finding("ERROR", case.id, "retrieve_log_miss_total", "expected non-negative int", "$.miss_queries_total"))
        miss_total = 0
    if not isinstance(miss_sample, list) or len(miss_sample) > 20:
        findings.append(Finding("ERROR", case.id, "retrieve_log_miss_sample_type", "expected list of up to 20 rows", "$.miss_queries_sample"))
    else:
        if len(miss_sample) > miss_total:
            findings.append(Finding("ERROR", case.id, "retrieve_log_miss_sample_total", "sample rows exceed miss_queries_total", "$.miss_queries_sample"))
        for index, row in enumerate(miss_sample):
            path = f"$.miss_queries_sample[{index}]"
            if not isinstance(row, dict):
                findings.append(Finding("ERROR", case.id, "retrieve_log_miss_row_type", "expected object", path))
                continue
            if not isinstance(row.get("query"), (str, type(None))):
                findings.append(Finding("ERROR", case.id, "retrieve_log_miss_query", "expected string or null", f"{path}.query"))
    return findings


def validate_check_prepare_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "check_prepare_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "check_prepare_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("kind") != "check_prepare":
        findings.append(Finding("ERROR", case.id, "check_prepare_kind", "expected kind=check_prepare", "$.kind"))
    if data.get("level") not in {"PASS", "WARNING", "ERROR"}:
        findings.append(Finding("ERROR", case.id, "check_prepare_level", "expected PASS/WARNING/ERROR", "$.level"))
    require_nonempty_string(findings, case, data.get("summary"), "check_prepare_summary", "$.summary")

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not all(isinstance(item, str) and item for item in candidates):
        findings.append(Finding("ERROR", case.id, "check_prepare_candidates_type", "expected list of non-empty strings", "$.candidates"))
    review_docs = data.get("review_docs")
    if not isinstance(review_docs, list) or not all(isinstance(item, str) and item for item in review_docs):
        findings.append(Finding("ERROR", case.id, "check_prepare_review_docs_type", "expected list of non-empty strings", "$.review_docs"))
        review_docs = []

    task = data.get("task")
    if task is None:
        if data.get("level") != "WARNING":
            findings.append(Finding("ERROR", case.id, "check_prepare_unresolved_level", "unresolved task should be WARNING", "$.level"))
        if review_docs:
            findings.append(Finding("ERROR", case.id, "check_prepare_unresolved_review_docs", "unresolved task should not include review_docs", "$.review_docs"))
        return findings

    if not isinstance(task, str) or not task.strip():
        findings.append(Finding("ERROR", case.id, "check_prepare_task", "expected non-empty string or null", "$.task"))
    require_nonempty_string(findings, case, data.get("task_dir"), "check_prepare_task_dir", "$.task_dir")
    resolution = data.get("resolution")
    if resolution not in {"absolute-path", "exact", "prefix"}:
        findings.append(Finding("ERROR", case.id, "check_prepare_resolution", "expected absolute-path/exact/prefix", "$.resolution"))
    stage = data.get("stage")
    if not isinstance(stage, str) or not stage.strip():
        findings.append(Finding("ERROR", case.id, "check_prepare_stage", "expected non-empty string", "$.stage"))
    diagnostic = data.get("diagnostic")
    if diagnostic is not None and not isinstance(diagnostic, str):
        findings.append(Finding("ERROR", case.id, "check_prepare_diagnostic_type", "expected string or null", "$.diagnostic"))

    for field in ("required_docs", "missing_required_docs", "warnings", "prompt_inputs"):
        value = data.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            findings.append(Finding("ERROR", case.id, f"check_prepare_{field}_type", "expected list of strings", f"$.{field}"))

    doc_scans = data.get("doc_scans")
    if not isinstance(doc_scans, list):
        findings.append(Finding("ERROR", case.id, "check_prepare_doc_scans_type", "expected list", "$.doc_scans"))
        doc_scans = []
    if isinstance(review_docs, list) and len(doc_scans) != len(review_docs):
        findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_count_mismatch", f"doc_scans={len(doc_scans)}, review_docs={len(review_docs)}", "$.doc_scans"))
    review_doc_set = set(review_docs) if isinstance(review_docs, list) else set()
    for idx, scan in enumerate(doc_scans):
        path = f"$.doc_scans[{idx}]"
        if not isinstance(scan, dict):
            findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_type", "expected object", path))
            continue
        scan_path = scan.get("path")
        if not isinstance(scan_path, str) or not scan_path:
            findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_path", "expected non-empty string", f"{path}.path"))
        elif scan_path not in review_doc_set:
            findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_path_not_reviewed", "scan path must be present in review_docs", f"{path}.path"))
        require_nonempty_string(findings, case, scan.get("name"), "check_prepare_doc_scan_name", f"{path}.name")
        for key in ("bytes", "line_count"):
            value = scan.get(key)
            if not isinstance(value, int) or value < 0:
                findings.append(Finding("ERROR", case.id, f"check_prepare_doc_scan_{key}", "expected non-negative integer", f"{path}.{key}"))
        if not isinstance(scan.get("too_long"), bool):
            findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_too_long_type", "expected boolean", f"{path}.too_long"))
        todo_rows = scan.get("todo_or_placeholders")
        if not isinstance(todo_rows, list):
            findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_todo_type", "expected list", f"{path}.todo_or_placeholders"))
        else:
            for todo_idx, todo in enumerate(todo_rows):
                todo_path = f"{path}.todo_or_placeholders[{todo_idx}]"
                if not isinstance(todo, dict):
                    findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_todo_row_type", "expected object", todo_path))
                    continue
                if not isinstance(todo.get("line"), int) or todo.get("line") <= 0:
                    findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_todo_line", "expected positive integer", f"{todo_path}.line"))
                require_nonempty_string(findings, case, todo.get("text"), "check_prepare_doc_scan_todo_text", f"{todo_path}.text")
        empty_headings = scan.get("empty_headings")
        if not isinstance(empty_headings, list) or not all(isinstance(item, str) for item in empty_headings):
            findings.append(Finding("ERROR", case.id, "check_prepare_doc_scan_empty_headings_type", "expected list of strings", f"{path}.empty_headings"))

    warnings = data.get("warnings")
    expected_level = "ERROR" if not review_docs else ("WARNING" if warnings else "PASS")
    if data.get("level") != expected_level:
        findings.append(Finding("ERROR", case.id, "check_prepare_level_mismatch", f"expected={expected_level}, actual={data.get('level')}", "$.level"))
    prompt_inputs = data.get("prompt_inputs")
    if isinstance(prompt_inputs, list):
        joined = "\n".join(prompt_inputs)
        if isinstance(task, str) and task not in joined:
            findings.append(Finding("ERROR", case.id, "check_prepare_prompt_missing_task", "prompt_inputs should include task name", "$.prompt_inputs"))
        for doc in review_docs:
            if doc not in joined:
                findings.append(Finding("ERROR", case.id, "check_prepare_prompt_missing_doc", f"missing {doc}", "$.prompt_inputs"))
                break
    return findings


def validate_work_context_pack_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "work_context_root_type", "expected object root", "$"))
        return findings
    if data.get("schema_version") != 1:
        findings.append(Finding("ERROR", case.id, "work_context_schema_version", "expected schema_version=1", "$.schema_version"))
    if data.get("kind") != "work_context":
        findings.append(Finding("ERROR", case.id, "work_context_kind", "expected kind=work_context", "$.kind"))
    if data.get("level") not in ("PASS", "WARNING", "ERROR", "INFO"):
        findings.append(Finding("ERROR", case.id, "work_context_level", "expected PASS/WARNING/ERROR/INFO", "$.level"))
    require_nonempty_string(findings, case, data.get("summary"), "work_context_summary", "$.summary")
    require_nonempty_string(findings, case, data.get("recommended_next_step"), "work_context_recommended_next_step", "$.recommended_next_step")
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        findings.append(Finding("ERROR", case.id, "work_context_confidence", "expected number between 0 and 1", "$.confidence"))
    for field in ("candidates", "required_reads"):
        values = data.get(field)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            findings.append(Finding("ERROR", case.id, f"work_context_{field}", "expected list of strings", f"$.{field}"))
    intent_guard = data.get("intent_guard")
    if intent_guard is not None:
        if not isinstance(intent_guard, dict):
            findings.append(Finding("ERROR", case.id, "work_context_intent_guard_type", "expected object", "$.intent_guard"))
        else:
            if intent_guard.get("kind") != "new_task_intent":
                findings.append(Finding("ERROR", case.id, "work_context_intent_guard_kind", "expected new_task_intent", "$.intent_guard.kind"))
            if intent_guard.get("action") != "create_task_or_confirm":
                findings.append(Finding("ERROR", case.id, "work_context_intent_guard_action", "expected create_task_or_confirm", "$.intent_guard.action"))
            require_nonempty_string(findings, case, intent_guard.get("trigger"), "work_context_intent_guard_trigger", "$.intent_guard.trigger")
            require_nonempty_string(findings, case, intent_guard.get("message"), "work_context_intent_guard_message", "$.intent_guard.message")
            if "resolved_task" in intent_guard and not isinstance(intent_guard.get("resolved_task"), str):
                findings.append(Finding("ERROR", case.id, "work_context_intent_guard_resolved_task", "expected string when present", "$.intent_guard.resolved_task"))
            if "resolution" in intent_guard and not isinstance(intent_guard.get("resolution"), str):
                findings.append(Finding("ERROR", case.id, "work_context_intent_guard_resolution", "expected string when present", "$.intent_guard.resolution"))
        if data.get("level") == "PASS":
            findings.append(Finding("ERROR", case.id, "work_context_intent_guard_level", "intent_guard should not be PASS", "$.level"))
    task = data.get("task")
    if task is None:
        if data.get("level") not in ("WARNING", "INFO", "ERROR"):
            findings.append(Finding("ERROR", case.id, "work_context_unresolved_level", "unresolved task should be INFO/WARNING/ERROR", "$.level"))
        if not isinstance(data.get("in_watched_paths"), bool):
            findings.append(Finding("ERROR", case.id, "work_context_in_watched_paths", "expected bool for unresolved task", "$.in_watched_paths"))
        return findings
    if not isinstance(task, str) or not task:
        findings.append(Finding("ERROR", case.id, "work_context_task", "expected non-empty string or null", "$.task"))
        return findings
    require_nonempty_string(findings, case, data.get("task_dir"), "work_context_task_dir", "$.task_dir")
    require_nonempty_string(findings, case, data.get("resolution"), "work_context_resolution", "$.resolution")
    require_nonempty_string(findings, case, data.get("stage"), "work_context_stage", "$.stage")
    if not isinstance(data.get("diagnostic"), (str, type(None))):
        findings.append(Finding("ERROR", case.id, "work_context_diagnostic", "expected string or null", "$.diagnostic"))
    for field in ("existing_docs", "missing_required_docs"):
        values = data.get(field)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            findings.append(Finding("ERROR", case.id, f"work_context_{field}", "expected list of strings", f"$.{field}"))
    snippets = data.get("doc_snippets")
    if not isinstance(snippets, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in snippets.items()):
        findings.append(Finding("ERROR", case.id, "work_context_doc_snippets", "expected string map", "$.doc_snippets"))
    if data.get("level") == "PASS" and data.get("missing_required_docs"):
        findings.append(Finding("ERROR", case.id, "work_context_pass_with_missing_docs", "PASS cannot include missing required docs", "$.missing_required_docs"))
    return findings


def require_nonempty_string(
    findings: list[Finding],
    case: ContractCase,
    value: Any,
    code: str,
    path: str,
) -> None:
    if not isinstance(value, str) or not value.strip():
        findings.append(Finding("ERROR", case.id, code, "expected non-empty string", path))


def validate_gate_check_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "gate_check_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "gate_check":
        findings.append(Finding("ERROR", case.id, "gate_check_kind", "expected kind=gate_check", "$.kind"))
    if data.get("verdict") not in {"pass", "blocked"}:
        findings.append(Finding("ERROR", case.id, "gate_check_verdict", "expected pass or blocked", "$.verdict"))
    if data.get("exit_code") not in {0, 1}:
        findings.append(Finding("ERROR", case.id, "gate_check_exit_code", "expected 0 or 1", "$.exit_code"))
    require_nonempty_string(findings, case, data.get("phase"), "gate_check_phase", "$.phase")

    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "gate_check_summary_type", "expected object", "$.summary"))
        summary = {}
    for key in ("total", "pass", "fail"):
        if not isinstance(summary.get(key), int):
            findings.append(Finding("ERROR", case.id, f"gate_check_summary_{key}", "expected int", f"$.summary.{key}"))

    gates = data.get("gates")
    if not isinstance(gates, list):
        findings.append(Finding("ERROR", case.id, "gate_check_gates_type", "expected list", "$.gates"))
        gates = []
    failures = data.get("failures")
    if not isinstance(failures, list):
        findings.append(Finding("ERROR", case.id, "gate_check_failures_type", "expected list", "$.failures"))
        failures = []

    expected_ids = [f"G{index}" for index in range(1, 10)]
    gate_ids: list[str] = []
    failed_ids: list[str] = []
    for index, gate in enumerate(gates):
        item_path = f"$.gates[{index}]"
        if not isinstance(gate, dict):
            findings.append(Finding("ERROR", case.id, "gate_check_gate_type", "expected object", item_path))
            continue
        gate_id = gate.get("id")
        require_nonempty_string(findings, case, gate_id, "gate_check_gate_id", f"{item_path}.id")
        if isinstance(gate_id, str):
            gate_ids.append(gate_id)
        require_nonempty_string(findings, case, gate.get("name"), "gate_check_gate_name", f"{item_path}.name")
        if not isinstance(gate.get("pass"), bool):
            findings.append(Finding("ERROR", case.id, "gate_check_gate_pass", "expected bool", f"{item_path}.pass"))
        elif gate.get("pass") is False and isinstance(gate_id, str):
            failed_ids.append(gate_id)
        if not isinstance(gate.get("detail"), str):
            findings.append(Finding("ERROR", case.id, "gate_check_gate_detail", "expected string", f"{item_path}.detail"))

    if gate_ids != expected_ids:
        findings.append(Finding(
            "ERROR",
            case.id,
            "gate_check_gate_ids",
            f"expected={expected_ids}, actual={gate_ids}",
            "$.gates",
        ))
    by_id = {gate.get("id"): gate for gate in gates if isinstance(gate, dict)}
    g9 = by_id.get("G9")
    if not isinstance(g9, dict):
        findings.append(Finding("ERROR", case.id, "gate_check_g9_missing", "expected G9", "$.gates"))
    elif "WARN" not in str(g9.get("name", "")):
        findings.append(Finding("ERROR", case.id, "gate_check_g9_warn", "G9 must advertise WARN mode", "$.gates.G9.name"))

    failure_ids = [
        str(item.get("id"))
        for item in failures
        if isinstance(item, dict) and item.get("id")
    ]
    if failure_ids != failed_ids:
        findings.append(Finding(
            "ERROR",
            case.id,
            "gate_check_failures_mismatch",
            f"expected={failed_ids}, actual={failure_ids}",
            "$.failures",
        ))

    pass_count = len(gates) - len(failed_ids)
    expected_summary = {
        "total": len(gates),
        "pass": pass_count,
        "fail": len(failed_ids),
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            findings.append(Finding(
                "ERROR",
                case.id,
                f"gate_check_summary_{key}_mismatch",
                f"expected={value}, actual={summary.get(key)}",
                f"$.summary.{key}",
            ))
    expected_verdict = "blocked" if failed_ids else "pass"
    if data.get("verdict") != expected_verdict:
        findings.append(Finding("ERROR", case.id, "gate_check_verdict_mismatch", f"expected {expected_verdict}", "$.verdict"))
    expected_exit = 1 if failed_ids else 0
    if data.get("exit_code") != expected_exit:
        findings.append(Finding("ERROR", case.id, "gate_check_exit_code_mismatch", f"expected {expected_exit}", "$.exit_code"))
    return findings


def validate_hook_alignment_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "hook_alignment_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "hook_alignment_check":
        findings.append(Finding("ERROR", case.id, "hook_alignment_kind", "expected kind=hook_alignment_check", "$.kind"))
    if data.get("verdict") not in {"aligned", "drift"}:
        findings.append(Finding("ERROR", case.id, "hook_alignment_verdict", "expected aligned or drift", "$.verdict"))

    sources = data.get("sources")
    if not isinstance(sources, dict):
        findings.append(Finding("ERROR", case.id, "hook_alignment_sources_type", "expected object", "$.sources"))
        sources = {}
    for key in ("manifest", "bootstrap", "settings", "registry"):
        require_nonempty_string(findings, case, sources.get(key), f"hook_alignment_source_{key}", f"$.sources.{key}")

    totals = data.get("totals")
    if not isinstance(totals, dict):
        findings.append(Finding("ERROR", case.id, "hook_alignment_totals_type", "expected object", "$.totals"))
        totals = {}
    for key in ("manifest_hooks", "bootstrap_hooks", "runtime_hooks", "registry_active_hooks", "findings"):
        if not isinstance(totals.get(key), int):
            findings.append(Finding("ERROR", case.id, f"hook_alignment_totals_{key}", "expected int", f"$.totals.{key}"))

    list_fields = {
        "manifest_hooks": "manifest_hooks",
        "bootstrap_hooks": "bootstrap_hooks",
        "runtime_hooks": "runtime_hooks",
        "registry_active_hooks": "registry_active_hooks",
    }
    for field, total_key in list_fields.items():
        rows = data.get(field)
        if not isinstance(rows, list):
            findings.append(Finding("ERROR", case.id, f"hook_alignment_{field}_type", "expected list", f"$.{field}"))
            rows = []
        if rows != sorted(rows):
            findings.append(Finding("ERROR", case.id, f"hook_alignment_{field}_sorted", "expected sorted list", f"$.{field}"))
        if len(rows) != len(set(str(row) for row in rows)):
            findings.append(Finding("ERROR", case.id, f"hook_alignment_{field}_duplicates", "expected unique rows", f"$.{field}"))
        if isinstance(totals.get(total_key), int) and totals.get(total_key) != len(rows):
            findings.append(Finding(
                "ERROR",
                case.id,
                f"hook_alignment_{field}_count_mismatch",
                f"totals={totals.get(total_key)}, rows={len(rows)}",
                f"$.{field}",
            ))

    findings_list = data.get("findings")
    if not isinstance(findings_list, list):
        findings.append(Finding("ERROR", case.id, "hook_alignment_findings_type", "expected list", "$.findings"))
        findings_list = []
    if isinstance(totals.get("findings"), int) and totals.get("findings") != len(findings_list):
        findings.append(Finding(
            "ERROR",
            case.id,
            "hook_alignment_findings_count_mismatch",
            f"totals={totals.get('findings')}, rows={len(findings_list)}",
            "$.findings",
        ))
    for index, item in enumerate(findings_list):
        item_path = f"$.findings[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "hook_alignment_finding_type", "expected object", item_path))
            continue
        require_nonempty_string(findings, case, item.get("kind"), "hook_alignment_finding_kind", f"{item_path}.kind")
        if item.get("severity") not in {"high", "medium", "low"}:
            findings.append(Finding("ERROR", case.id, "hook_alignment_finding_severity", "expected high, medium, or low", f"{item_path}.severity"))
        relpaths = item.get("relpaths")
        if not isinstance(relpaths, list):
            findings.append(Finding("ERROR", case.id, "hook_alignment_finding_relpaths", "expected list", f"{item_path}.relpaths"))
            relpaths = []
        if item.get("count") != len(relpaths):
            findings.append(Finding(
                "ERROR",
                case.id,
                "hook_alignment_finding_count_mismatch",
                f"count={item.get('count')}, relpaths={len(relpaths)}",
                f"{item_path}.count",
            ))
        require_nonempty_string(findings, case, item.get("detail"), "hook_alignment_finding_detail", f"{item_path}.detail")
    expected_verdict = "drift" if findings_list else "aligned"
    if data.get("verdict") != expected_verdict:
        findings.append(Finding("ERROR", case.id, "hook_alignment_verdict_mismatch", f"expected {expected_verdict}", "$.verdict"))
    return findings


def validate_oss_readiness_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "oss_readiness_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "oss_readiness_check":
        findings.append(Finding("ERROR", case.id, "oss_readiness_kind", "expected kind=oss_readiness_check", "$.kind"))

    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "oss_readiness_summary_type", "expected object", "$.summary"))
    checks = data.get("checks")
    if not isinstance(checks, list):
        findings.append(Finding("ERROR", case.id, "oss_readiness_checks_type", "expected list", "$.checks"))
        return findings

    by_id: dict[str, dict[str, Any]] = {}
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_check_type", "expected object", f"$.checks[{index}]"))
            continue
        check_id = check.get("id")
        if isinstance(check_id, str) and check_id:
            by_id[check_id] = check

    docs_check = by_id.get("docs_entrypoints")
    if not isinstance(docs_check, dict):
        findings.append(Finding("ERROR", case.id, "oss_readiness_docs_entrypoints_missing", "expected docs_entrypoints check", "$.checks"))
    else:
        if docs_check.get("status") != "PASS":
            findings.append(Finding("ERROR", case.id, "oss_readiness_docs_entrypoints_status", "expected PASS", "$.checks.docs_entrypoints.status"))
        text_summary = str(docs_check.get("summary", ""))
        match = re.search(r"checked=(\d+)", text_summary)
        if not match:
            findings.append(Finding("ERROR", case.id, "oss_readiness_docs_entrypoints_checked_missing", "expected checked=N", "$.checks.docs_entrypoints.summary"))
        elif int(match.group(1)) < 6:
            findings.append(Finding(
                "ERROR",
                case.id,
                "oss_readiness_docs_entrypoints_checked_low",
                f"expected checked>=6, actual={match.group(1)}",
                "$.checks.docs_entrypoints.summary",
            ))
        frontmatter_match = re.search(r"frontmatter_checked=(\d+)", text_summary)
        if not frontmatter_match:
            findings.append(Finding("ERROR", case.id, "oss_readiness_docs_entrypoints_frontmatter_missing", "expected frontmatter_checked=N", "$.checks.docs_entrypoints.summary"))
        elif int(frontmatter_match.group(1)) < 5:
            findings.append(Finding(
                "ERROR",
                case.id,
                "oss_readiness_docs_entrypoints_frontmatter_low",
                f"expected frontmatter_checked>=5, actual={frontmatter_match.group(1)}",
                "$.checks.docs_entrypoints.summary",
            ))
        evidence = docs_check.get("evidence")
        frontmatter_checked = evidence.get("frontmatter_checked") if isinstance(evidence, dict) else None
        if not isinstance(frontmatter_checked, int) or frontmatter_checked < 5:
            findings.append(Finding("ERROR", case.id, "oss_readiness_docs_entrypoints_frontmatter_evidence", "expected frontmatter_checked>=5", "$.checks.docs_entrypoints.evidence.frontmatter_checked"))
        doc_findings = evidence.get("findings") if isinstance(evidence, dict) else None
        if doc_findings != []:
            findings.append(Finding("ERROR", case.id, "oss_readiness_docs_entrypoints_findings", "expected empty findings", "$.checks.docs_entrypoints.evidence.findings"))

    ci_check = by_id.get("ci_workflow")
    if not isinstance(ci_check, dict):
        findings.append(Finding("ERROR", case.id, "oss_readiness_ci_workflow_missing", "expected ci_workflow check", "$.checks"))
    else:
        if ci_check.get("status") != "PASS":
            findings.append(Finding("ERROR", case.id, "oss_readiness_ci_workflow_status", "expected PASS", "$.checks.ci_workflow.status"))
        evidence = ci_check.get("evidence")
        if not isinstance(evidence, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_ci_workflow_evidence", "expected object", "$.checks.ci_workflow.evidence"))
            evidence = {}
        if evidence.get("yaml_valid") is not True:
            findings.append(Finding("ERROR", case.id, "oss_readiness_ci_workflow_yaml_valid", "expected yaml_valid=true", "$.checks.ci_workflow.evidence.yaml_valid"))
        step_count = evidence.get("step_count")
        if not isinstance(step_count, int) or step_count < 5:
            findings.append(Finding("ERROR", case.id, "oss_readiness_ci_workflow_steps", "expected at least five workflow steps", "$.checks.ci_workflow.evidence.step_count"))
        required_commands = evidence.get("required_commands")
        if not isinstance(required_commands, list) or len(required_commands) < 5:
            findings.append(Finding("ERROR", case.id, "oss_readiness_ci_workflow_commands", "expected at least five required commands", "$.checks.ci_workflow.evidence.required_commands"))
        ci_findings = evidence.get("findings")
        if ci_findings != []:
            findings.append(Finding("ERROR", case.id, "oss_readiness_ci_workflow_findings", "expected empty findings", "$.checks.ci_workflow.evidence.findings"))

    manifest_check = by_id.get("maintenance_manifest")
    if not isinstance(manifest_check, dict):
        findings.append(Finding("ERROR", case.id, "oss_readiness_maintenance_manifest_missing", "expected maintenance_manifest check", "$.checks"))
    else:
        if manifest_check.get("status") != "PASS":
            findings.append(Finding("ERROR", case.id, "oss_readiness_maintenance_manifest_status", "expected PASS", "$.checks.maintenance_manifest.status"))
        evidence = manifest_check.get("evidence")
        if not isinstance(evidence, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_maintenance_manifest_evidence", "expected object", "$.checks.maintenance_manifest.evidence"))
            evidence = {}
        manifest_summary = evidence.get("summary")
        if not isinstance(manifest_summary, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_maintenance_manifest_summary", "expected object", "$.checks.maintenance_manifest.evidence.summary"))
            manifest_summary = {}
        for key in ("commands", "scripts", "required_commands", "findings"):
            if not isinstance(manifest_summary.get(key), int):
                findings.append(Finding("ERROR", case.id, f"oss_readiness_maintenance_manifest_{key}", "expected int", f"$.checks.maintenance_manifest.evidence.summary.{key}"))
        if isinstance(manifest_summary.get("required_commands"), int) and manifest_summary.get("required_commands") < 5:
            findings.append(Finding("ERROR", case.id, "oss_readiness_maintenance_manifest_required_low", "expected at least five required commands", "$.checks.maintenance_manifest.evidence.summary.required_commands"))
        manifest_findings = evidence.get("findings")
        if manifest_findings != []:
            findings.append(Finding("ERROR", case.id, "oss_readiness_maintenance_manifest_findings", "expected empty findings", "$.checks.maintenance_manifest.evidence.findings"))

    catalog_check = by_id.get("catalog_freshness")
    if not isinstance(catalog_check, dict):
        findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_missing", "expected catalog_freshness check", "$.checks"))
    else:
        if catalog_check.get("status") != "PASS":
            findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_status", "expected PASS", "$.checks.catalog_freshness.status"))
        evidence = catalog_check.get("evidence")
        if not isinstance(evidence, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_evidence", "expected object", "$.checks.catalog_freshness.evidence"))
            evidence = {}
        catalog_summary = evidence.get("summary")
        if not isinstance(catalog_summary, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_summary", "expected object", "$.checks.catalog_freshness.evidence.summary"))
            catalog_summary = {}
        for key in ("targets", "fresh", "stale", "missing", "findings"):
            if not isinstance(catalog_summary.get(key), int):
                findings.append(Finding("ERROR", case.id, f"oss_readiness_catalog_freshness_{key}", "expected int", f"$.checks.catalog_freshness.evidence.summary.{key}"))
        if isinstance(catalog_summary.get("targets"), int) and catalog_summary.get("targets") < 3:
            findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_targets_low", "expected at least three generated catalogs", "$.checks.catalog_freshness.evidence.summary.targets"))
        if catalog_summary.get("stale") not in {0, None}:
            findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_stale", "expected stale=0", "$.checks.catalog_freshness.evidence.summary.stale"))
        if catalog_summary.get("missing") not in {0, None}:
            findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_missing_count", "expected missing=0", "$.checks.catalog_freshness.evidence.summary.missing"))
        catalog_findings = evidence.get("findings")
        if catalog_findings != []:
            findings.append(Finding("ERROR", case.id, "oss_readiness_catalog_freshness_findings", "expected empty findings", "$.checks.catalog_freshness.evidence.findings"))

    client_check = by_id.get("client_portability")
    if not isinstance(client_check, dict):
        findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_missing", "expected client_portability check", "$.checks"))
    else:
        evidence = client_check.get("evidence")
        if not isinstance(evidence, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_evidence", "expected object", "$.checks.client_portability.evidence"))
            evidence = {}
        client_summary = evidence.get("summary")
        if not isinstance(client_summary, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_summary", "expected object", "$.checks.client_portability.evidence.summary"))
        else:
            for key in ("clients", "stable_full_lifecycle_clients", "stable_context_clients", "claim_policy_checked"):
                if not isinstance(client_summary.get(key), int):
                    findings.append(Finding("ERROR", case.id, f"oss_readiness_client_portability_{key}", "expected int", f"$.checks.client_portability.evidence.summary.{key}"))
        readiness = evidence.get("readiness")
        if not isinstance(readiness, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_readiness", "expected object", "$.checks.client_portability.evidence.readiness"))
            readiness = {}
        for key in ("full_lifecycle_multi_client", "context_cli"):
            item = readiness.get(key)
            if not isinstance(item, dict):
                findings.append(Finding("ERROR", case.id, f"oss_readiness_client_portability_readiness_{key}", "expected object", f"$.checks.client_portability.evidence.readiness.{key}"))
                continue
            if not isinstance(item.get("ready"), bool):
                findings.append(Finding("ERROR", case.id, f"oss_readiness_client_portability_readiness_{key}_ready", "expected bool", f"$.checks.client_portability.evidence.readiness.{key}.ready"))
            for count_key in ("stable_clients", "required_clients"):
                if not isinstance(item.get(count_key), int):
                    findings.append(Finding("ERROR", case.id, f"oss_readiness_client_portability_readiness_{key}_{count_key}", "expected int", f"$.checks.client_portability.evidence.readiness.{key}.{count_key}"))
        validate_client_contract_evidence(
            findings,
            case,
            evidence.get("contracts"),
            "$.checks.client_portability.evidence.contracts",
            "oss_readiness_client_portability",
        )
        client_rows = evidence.get("clients")
        if not isinstance(client_rows, list) or not client_rows:
            findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_clients", "expected non-empty list", "$.checks.client_portability.evidence.clients"))
        else:
            for index, row in enumerate(client_rows):
                row_path = f"$.checks.client_portability.evidence.clients[{index}]"
                if not isinstance(row, dict):
                    findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_client_type", "expected object", row_path))
                    continue
                for field in ("id", "status", "integration", "support_level"):
                    require_nonempty_string(findings, case, row.get(field), f"oss_readiness_client_portability_client_{field}", f"{row_path}.{field}")
        claim_policy = evidence.get("claim_policy")
        if not isinstance(claim_policy, dict):
            findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_claim_policy", "expected claim_policy evidence", "$.checks.client_portability.evidence.claim_policy"))
        elif not isinstance(claim_policy.get("checked"), int) or claim_policy.get("checked") < 3:
            findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_claim_policy_checked", "expected checked>=3", "$.checks.client_portability.evidence.claim_policy.checked"))
        validate_client_remediation_plan(
            findings,
            case,
            evidence.get("remediation_plan"),
            "$.checks.client_portability.evidence.remediation_plan",
            "oss_readiness_client_portability",
        )
        client_findings = evidence.get("findings")
        if not isinstance(client_findings, list):
            findings.append(Finding("ERROR", case.id, "oss_readiness_client_portability_findings", "expected list", "$.checks.client_portability.evidence.findings"))

    for expected_id, expected_decision in {
        "project_metadata": "license_policy",
        "publish_scope": "publish_scope_boundary",
    }.items():
        check = by_id.get(expected_id)
        if not isinstance(check, dict):
            findings.append(Finding("ERROR", case.id, f"oss_readiness_{expected_id}_missing", "expected check", f"$.checks.{expected_id}"))
            continue
        evidence = check.get("evidence")
        decision_plan = evidence.get("decision_plan") if isinstance(evidence, dict) else None
        if not isinstance(decision_plan, dict) or not decision_plan:
            findings.append(Finding("ERROR", case.id, f"oss_readiness_{expected_id}_decision_plan_missing", "expected decision_plan", f"$.checks.{expected_id}.evidence.decision_plan"))
            continue
        if decision_plan.get("decision") != expected_decision:
            findings.append(Finding(
                "ERROR",
                case.id,
                f"oss_readiness_{expected_id}_decision",
                f"expected {expected_decision}, actual={decision_plan.get('decision')}",
                f"$.checks.{expected_id}.evidence.decision_plan.decision",
            ))
        require_nonempty_string(findings, case, decision_plan.get("owner"), f"oss_readiness_{expected_id}_decision_owner", f"$.checks.{expected_id}.evidence.decision_plan.owner")
        options = decision_plan.get("options")
        if not isinstance(options, list) or not options:
            findings.append(Finding("ERROR", case.id, f"oss_readiness_{expected_id}_decision_options", "expected non-empty options", f"$.checks.{expected_id}.evidence.decision_plan.options"))
    return findings


def validate_orphan_script_scan_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "orphan_scan_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "orphan_script_scan":
        findings.append(Finding("ERROR", case.id, "orphan_scan_kind", "expected kind=orphan_script_scan", "$.kind"))
    if data.get("verdict") not in {"ok", "registry_drift"}:
        findings.append(Finding("ERROR", case.id, "orphan_scan_verdict", "expected ok or registry_drift", "$.verdict"))
    totals = data.get("totals")
    if not isinstance(totals, dict):
        findings.append(Finding("ERROR", case.id, "orphan_scan_totals_type", "expected object", "$.totals"))
        totals = {}
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "orphan_scan_summary_type", "expected object", "$.summary"))
        summary = {}
    for key in ("actual_scripts", "unregistered", "orphan_listed", "stale_in_registry"):
        value = summary.get(key)
        if not isinstance(value, int):
            findings.append(Finding("ERROR", case.id, f"orphan_scan_summary_{key}", "expected int", f"$.summary.{key}"))
    for key in ("unregistered", "orphan_listed", "stale_in_registry"):
        rows = data.get(key)
        if not isinstance(rows, list):
            findings.append(Finding("ERROR", case.id, f"orphan_scan_{key}_type", "expected list", f"$.{key}"))
            rows = []
        if isinstance(summary.get(key), int) and summary.get(key) != len(rows):
            findings.append(Finding(
                "ERROR",
                case.id,
                f"orphan_scan_{key}_count_mismatch",
                f"summary={summary.get(key)}, rows={len(rows)}",
                f"$.{key}",
            ))
        if isinstance(totals.get(key), int) and totals.get(key) != len(rows):
            findings.append(Finding(
                "ERROR",
                case.id,
                f"orphan_scan_{key}_totals_mismatch",
                f"totals={totals.get(key)}, rows={len(rows)}",
                f"$.totals.{key}",
            ))
    drift = bool(data.get("unregistered")) or bool(data.get("stale_in_registry"))
    expected_verdict = "registry_drift" if drift else "ok"
    if data.get("verdict") != expected_verdict:
        findings.append(Finding(
            "ERROR",
            case.id,
            "orphan_scan_verdict_mismatch",
            f"expected {expected_verdict}",
            "$.verdict",
        ))
    return findings


def validate_dual_storage_scan_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "dual_storage_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "dual_storage_scan":
        findings.append(Finding("ERROR", case.id, "dual_storage_kind", "expected kind=dual_storage_scan", "$.kind"))
    if data.get("verdict") not in ("ok", "dual_storage_found"):
        findings.append(Finding("ERROR", case.id, "dual_storage_verdict", "expected ok or dual_storage_found", "$.verdict"))
    roots = data.get("roots")
    if not isinstance(roots, dict):
        findings.append(Finding("ERROR", case.id, "dual_storage_roots_type", "expected object", "$.roots"))
    else:
        for key in ("active", "archived", "projects"):
            require_nonempty_string(findings, case, roots.get(key), f"dual_storage_root_{key}", f"$.roots.{key}")
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "dual_storage_summary_type", "expected object", "$.summary"))
        return findings
    for key in ("active_dirs", "archived_dirs", "project_dirs", "dual_count"):
        value = summary.get(key)
        if not isinstance(value, int) or value < 0:
            findings.append(Finding("ERROR", case.id, f"dual_storage_summary_{key}", "expected non-negative int", f"$.summary.{key}"))
    duplicates = data.get("duplicates")
    if not isinstance(duplicates, list):
        findings.append(Finding("ERROR", case.id, "dual_storage_duplicates_type", "expected list", "$.duplicates"))
        return findings
    dual_count = summary.get("dual_count")
    if isinstance(dual_count, int) and len(duplicates) != dual_count:
        findings.append(Finding("ERROR", case.id, "dual_storage_duplicate_count_mismatch", f"summary={dual_count}, duplicates={len(duplicates)}", "$.duplicates"))
    for index, row in enumerate(duplicates):
        path = f"$.duplicates[{index}]"
        if not isinstance(row, dict):
            findings.append(Finding("ERROR", case.id, "dual_storage_duplicate_type", "expected object", path))
            continue
        require_nonempty_string(findings, case, row.get("name"), "dual_storage_duplicate_name", f"{path}.name")
        for key in ("active", "archived", "projects"):
            if not isinstance(row.get(key), bool):
                findings.append(Finding("ERROR", case.id, f"dual_storage_duplicate_{key}", "expected bool", f"{path}.{key}"))
        if row.get("projects") is not True:
            findings.append(Finding("ERROR", case.id, "dual_storage_duplicate_projects_true", "expected projects=true", f"{path}.projects"))
    expected_verdict = "dual_storage_found" if isinstance(dual_count, int) and dual_count else "ok"
    if data.get("verdict") != expected_verdict:
        findings.append(Finding("ERROR", case.id, "dual_storage_verdict_mismatch", f"expected={expected_verdict}, actual={data.get('verdict')}", "$.verdict"))
    return findings


def validate_capability_manifest_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "capability_manifest_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "capability_manifest_check":
        findings.append(Finding("ERROR", case.id, "capability_manifest_kind", "expected kind=capability_manifest_check", "$.kind"))
    if data.get("verdict") not in {"ok", "invalid"}:
        findings.append(Finding("ERROR", case.id, "capability_manifest_verdict", "expected ok or invalid", "$.verdict"))
    require_nonempty_string(findings, case, data.get("manifest"), "capability_manifest_path", "$.manifest")

    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "capability_manifest_summary_type", "expected object", "$.summary"))
        summary = {}
    for key in (
        "capabilities",
        "release_scope",
        "ERROR",
        "WARNING",
        "actual_scripts",
        "assigned_scripts",
        "coverage_exemptions",
        "unassigned_scripts",
        "stale_coverage_exemptions",
        "documented_capabilities",
    ):
        if not isinstance(summary.get(key), int):
            findings.append(Finding("ERROR", case.id, f"capability_manifest_summary_{key}", "expected int", f"$.summary.{key}"))

    status_counts = normalize_int_map(summary.get("status_counts"))
    expected_statuses = {"core", "optional", "experimental", "legacy", "deprecated"}
    if set(status_counts) != expected_statuses:
        findings.append(Finding(
            "ERROR",
            case.id,
            "capability_manifest_status_counts_keys",
            f"expected={sorted(expected_statuses)}, actual={sorted(status_counts)}",
            "$.summary.status_counts",
        ))
    if isinstance(summary.get("capabilities"), int) and sum(status_counts.values()) != summary.get("capabilities"):
        findings.append(Finding(
            "ERROR",
            case.id,
            "capability_manifest_status_counts_total",
            f"expected={summary.get('capabilities')}, actual={sum(status_counts.values())}",
            "$.summary.status_counts",
        ))
    for lhs, rhs, code in (
        ("release_scope", "capabilities", "capability_manifest_release_scope_total"),
        ("assigned_scripts", "actual_scripts", "capability_manifest_assigned_scripts_total"),
        ("documented_capabilities", "capabilities", "capability_manifest_documented_total"),
    ):
        left = summary.get(lhs)
        right = summary.get(rhs)
        if isinstance(left, int) and isinstance(right, int) and left > right:
            findings.append(Finding("ERROR", case.id, code, f"{lhs} cannot exceed {rhs}", f"$.summary.{lhs}"))

    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        findings.append(Finding("ERROR", case.id, "capability_manifest_coverage_type", "expected object", "$.coverage"))
        coverage = {}
    if not isinstance(coverage.get("required"), bool):
        findings.append(Finding("ERROR", case.id, "capability_manifest_coverage_required", "expected bool", "$.coverage.required"))
    for key, summary_key in (("unassigned", "unassigned_scripts"), ("stale_exemptions", "stale_coverage_exemptions")):
        rows = coverage.get(key)
        if not isinstance(rows, list):
            findings.append(Finding("ERROR", case.id, f"capability_manifest_coverage_{key}", "expected list", f"$.coverage.{key}"))
            rows = []
        if isinstance(summary.get(summary_key), int) and summary.get(summary_key) != len(rows):
            findings.append(Finding(
                "ERROR",
                case.id,
                f"capability_manifest_{summary_key}_mismatch",
                f"summary={summary.get(summary_key)}, rows={len(rows)}",
                f"$.coverage.{key}",
            ))

    findings_list = data.get("findings")
    if not isinstance(findings_list, list):
        findings.append(Finding("ERROR", case.id, "capability_manifest_findings_type", "expected list", "$.findings"))
        findings_list = []
    error_count = sum(1 for item in findings_list if isinstance(item, dict) and item.get("level") == "ERROR")
    warning_count = sum(1 for item in findings_list if isinstance(item, dict) and item.get("level") == "WARNING")
    if summary.get("ERROR") != error_count:
        findings.append(Finding("ERROR", case.id, "capability_manifest_error_count_mismatch", f"summary={summary.get('ERROR')}, findings={error_count}", "$.summary.ERROR"))
    if summary.get("WARNING") != warning_count:
        findings.append(Finding("ERROR", case.id, "capability_manifest_warning_count_mismatch", f"summary={summary.get('WARNING')}, findings={warning_count}", "$.summary.WARNING"))
    expected_verdict = "invalid" if error_count else "ok"
    if data.get("verdict") != expected_verdict:
        findings.append(Finding("ERROR", case.id, "capability_manifest_verdict_mismatch", f"expected {expected_verdict}", "$.verdict"))
    return findings


def validate_client_manifest_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "client_manifest_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "client_manifest_check":
        findings.append(Finding("ERROR", case.id, "client_manifest_kind", "expected kind=client_manifest_check", "$.kind"))
    if data.get("verdict") not in {"ok", "single_client_scope", "invalid"}:
        findings.append(Finding("ERROR", case.id, "client_manifest_verdict", "expected ok, single_client_scope, or invalid", "$.verdict"))
    require_nonempty_string(findings, case, data.get("manifest"), "client_manifest_path", "$.manifest")
    require_nonempty_string(findings, case, data.get("product_scope"), "client_manifest_product_scope", "$.product_scope")
    if not isinstance(data.get("multi_client_ready"), bool):
        findings.append(Finding("ERROR", case.id, "client_manifest_multi_client_ready", "expected bool", "$.multi_client_ready"))
    if not isinstance(data.get("context_cli_ready"), bool):
        findings.append(Finding("ERROR", case.id, "client_manifest_context_cli_ready", "expected bool", "$.context_cli_ready"))

    readiness = data.get("readiness")
    if not isinstance(readiness, dict):
        findings.append(Finding("ERROR", case.id, "client_manifest_readiness_type", "expected object", "$.readiness"))
        readiness = {}
    for key in ("full_lifecycle_multi_client", "context_cli"):
        row = readiness.get(key)
        if not isinstance(row, dict):
            findings.append(Finding("ERROR", case.id, f"client_manifest_readiness_{key}", "expected object", f"$.readiness.{key}"))
            continue
        if not isinstance(row.get("ready"), bool):
            findings.append(Finding("ERROR", case.id, f"client_manifest_readiness_{key}_ready", "expected bool", f"$.readiness.{key}.ready"))
        for count_key in ("stable_clients", "required_clients"):
            if not isinstance(row.get(count_key), int):
                findings.append(Finding("ERROR", case.id, f"client_manifest_readiness_{key}_{count_key}", "expected int", f"$.readiness.{key}.{count_key}"))

    contracts = data.get("contracts")
    if not isinstance(contracts, dict):
        findings.append(Finding("ERROR", case.id, "client_manifest_contracts_type", "expected object", "$.contracts"))
        contracts = {}
    full_lifecycle_required = contracts.get("full_lifecycle_required_capabilities")
    context_brief_required = contracts.get("context_brief_required_capabilities")
    if not isinstance(full_lifecycle_required, list) or not all(isinstance(item, str) and item.strip() for item in full_lifecycle_required):
        findings.append(Finding("ERROR", case.id, "client_manifest_full_lifecycle_contract", "expected non-empty string list", "$.contracts.full_lifecycle_required_capabilities"))
        full_lifecycle_required = []
    if not isinstance(context_brief_required, list) or not all(isinstance(item, str) and item.strip() for item in context_brief_required):
        findings.append(Finding("ERROR", case.id, "client_manifest_context_brief_contract", "expected non-empty string list", "$.contracts.context_brief_required_capabilities"))
        context_brief_required = []

    clients = data.get("clients")
    if not isinstance(clients, list):
        findings.append(Finding("ERROR", case.id, "client_manifest_clients_type", "expected list", "$.clients"))
        clients = []
    allowed_statuses = {"stable", "experimental", "planned", "deprecated"}
    allowed_integrations = {"hooks_settings", "manual_cli", "api", "none"}
    allowed_support_levels = {"full_lifecycle", "context_brief_only", "planned"}
    for idx, client in enumerate(clients):
        path = f"$.clients[{idx}]"
        if not isinstance(client, dict):
            findings.append(Finding("ERROR", case.id, "client_manifest_client_type", "expected object", path))
            continue
        require_nonempty_string(findings, case, client.get("id"), "client_manifest_client_id", f"{path}.id")
        require_nonempty_string(findings, case, client.get("name"), "client_manifest_client_name", f"{path}.name")
        if client.get("status") not in allowed_statuses:
            findings.append(Finding("ERROR", case.id, "client_manifest_client_status", f"expected one of {sorted(allowed_statuses)}", f"{path}.status"))
        if client.get("integration") not in allowed_integrations:
            findings.append(Finding("ERROR", case.id, "client_manifest_client_integration", f"expected one of {sorted(allowed_integrations)}", f"{path}.integration"))
        if client.get("support_level") not in allowed_support_levels:
            findings.append(Finding("ERROR", case.id, "client_manifest_client_support_level", f"expected one of {sorted(allowed_support_levels)}", f"{path}.support_level"))
        for count_key in ("entrypoint_count", "limitations_count"):
            if not isinstance(client.get(count_key), int) or client.get(count_key) < 0:
                findings.append(Finding("ERROR", case.id, f"client_manifest_client_{count_key}", "expected non-negative int", f"{path}.{count_key}"))
        if not isinstance(client.get("capability_count"), int) or client.get("capability_count") < 0:
            findings.append(Finding("ERROR", case.id, "client_manifest_client_capability_count", "expected non-negative int", f"{path}.capability_count"))
        missing_full = client.get("missing_full_lifecycle_capabilities")
        missing_context = client.get("missing_context_brief_capabilities")
        if not isinstance(missing_full, list) or not all(isinstance(item, str) for item in missing_full):
            findings.append(Finding("ERROR", case.id, "client_manifest_client_missing_full_lifecycle", "expected string list", f"{path}.missing_full_lifecycle_capabilities"))
            missing_full = []
        if not isinstance(missing_context, list) or not all(isinstance(item, str) for item in missing_context):
            findings.append(Finding("ERROR", case.id, "client_manifest_client_missing_context_brief", "expected string list", f"{path}.missing_context_brief_capabilities"))
            missing_context = []
        if client.get("support_level") == "full_lifecycle" and missing_full:
            findings.append(Finding("ERROR", case.id, "client_manifest_full_lifecycle_missing_capabilities", "full_lifecycle client must have no missing full lifecycle capabilities", f"{path}.missing_full_lifecycle_capabilities"))
        if client.get("support_level") == "context_brief_only" and missing_context:
            findings.append(Finding("ERROR", case.id, "client_manifest_context_brief_missing_capabilities", "context_brief_only client must have no missing context brief capabilities", f"{path}.missing_context_brief_capabilities"))

    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "client_manifest_summary_type", "expected object", "$.summary"))
        summary = {}
    for key in (
        "clients",
        "stable_clients",
        "stable_full_lifecycle_clients",
        "stable_context_clients",
        "required_for_generic_oss",
        "claim_policy_checked",
        "ERROR",
        "WARNING",
    ):
        if not isinstance(summary.get(key), int):
            findings.append(Finding("ERROR", case.id, f"client_manifest_summary_{key}", "expected int", f"$.summary.{key}"))

    claim_policy = data.get("claim_policy")
    if not isinstance(claim_policy, dict):
        findings.append(Finding("ERROR", case.id, "client_manifest_claim_policy", "expected object", "$.claim_policy"))
        claim_policy = {}
    if not isinstance(claim_policy.get("checked"), int) or claim_policy.get("checked") < 3:
        findings.append(Finding("ERROR", case.id, "client_manifest_claim_policy_checked", "expected checked>=3", "$.claim_policy.checked"))
    if not isinstance(claim_policy.get("forbidden_checked"), int) or claim_policy.get("forbidden_checked") < 3:
        findings.append(Finding("ERROR", case.id, "client_manifest_claim_policy_forbidden_checked", "expected forbidden_checked>=3", "$.claim_policy.forbidden_checked"))
    if summary.get("claim_policy_checked") != claim_policy.get("checked"):
        findings.append(Finding("ERROR", case.id, "client_manifest_claim_policy_checked_mismatch", "summary must match claim_policy.checked", "$.summary.claim_policy_checked"))
    claim_findings = claim_policy.get("findings")
    if not isinstance(claim_findings, list):
        findings.append(Finding("ERROR", case.id, "client_manifest_claim_policy_findings", "expected list", "$.claim_policy.findings"))
    elif claim_findings:
        findings.append(Finding("ERROR", case.id, "client_manifest_claim_policy_findings_nonempty", "claim policy findings must be empty", "$.claim_policy.findings"))

    validate_client_remediation_plan(
        findings,
        case,
        data.get("remediation_plan"),
        "$.remediation_plan",
        "client_manifest",
    )

    status_counts = normalize_int_map(summary.get("status_counts"))
    expected_statuses = {"stable", "experimental", "planned", "deprecated"}
    if set(status_counts) != expected_statuses:
        findings.append(Finding(
            "ERROR",
            case.id,
            "client_manifest_status_counts_keys",
            f"expected={sorted(expected_statuses)}, actual={sorted(status_counts)}",
            "$.summary.status_counts",
        ))
    if isinstance(summary.get("clients"), int) and sum(status_counts.values()) != summary.get("clients"):
        findings.append(Finding(
            "ERROR",
            case.id,
            "client_manifest_status_counts_total",
            f"expected={summary.get('clients')}, actual={sum(status_counts.values())}",
            "$.summary.status_counts",
        ))
    if isinstance(summary.get("clients"), int) and len(clients) != summary.get("clients"):
        findings.append(Finding(
            "ERROR",
            case.id,
            "client_manifest_clients_count_mismatch",
            f"summary={summary.get('clients')}, clients={len(clients)}",
            "$.clients",
        ))
    client_status_counts = {status: 0 for status in expected_statuses}
    for client in clients:
        if isinstance(client, dict) and client.get("status") in client_status_counts:
            client_status_counts[str(client.get("status"))] += 1
    if clients and client_status_counts != status_counts:
        findings.append(Finding(
            "ERROR",
            case.id,
            "client_manifest_client_status_counts_mismatch",
            f"summary={status_counts}, clients={client_status_counts}",
            "$.clients",
        ))
    if isinstance(summary.get("stable_clients"), int) and status_counts.get("stable") != summary.get("stable_clients"):
        findings.append(Finding(
            "ERROR",
            case.id,
            "client_manifest_stable_count_mismatch",
            f"summary={summary.get('stable_clients')}, status_counts={status_counts.get('stable')}",
            "$.summary.stable_clients",
        ))
    for lhs, rhs, code in (
        ("stable_full_lifecycle_clients", "stable_clients", "client_manifest_full_lifecycle_exceeds_stable"),
        ("stable_context_clients", "stable_clients", "client_manifest_context_exceeds_stable"),
        ("stable_full_lifecycle_clients", "stable_context_clients", "client_manifest_full_lifecycle_exceeds_context"),
    ):
        left = summary.get(lhs)
        right = summary.get(rhs)
        if isinstance(left, int) and isinstance(right, int) and left > right:
            findings.append(Finding("ERROR", case.id, code, f"{lhs} cannot exceed {rhs}", f"$.summary.{lhs}"))
    client_stable_full_lifecycle = sum(
        1
        for client in clients
        if isinstance(client, dict)
        and client.get("status") == "stable"
        and client.get("support_level") == "full_lifecycle"
    )
    client_stable_context = sum(
        1
        for client in clients
        if isinstance(client, dict)
        and client.get("status") == "stable"
        and client.get("support_level") in {"full_lifecycle", "context_brief_only"}
    )
    if clients and isinstance(summary.get("stable_full_lifecycle_clients"), int) and client_stable_full_lifecycle != summary.get("stable_full_lifecycle_clients"):
        findings.append(Finding("ERROR", case.id, "client_manifest_full_lifecycle_count_mismatch", f"summary={summary.get('stable_full_lifecycle_clients')}, clients={client_stable_full_lifecycle}", "$.summary.stable_full_lifecycle_clients"))
    if clients and isinstance(summary.get("stable_context_clients"), int) and client_stable_context != summary.get("stable_context_clients"):
        findings.append(Finding("ERROR", case.id, "client_manifest_context_count_mismatch", f"summary={summary.get('stable_context_clients')}, clients={client_stable_context}", "$.summary.stable_context_clients"))

    findings_list = data.get("findings")
    if not isinstance(findings_list, list):
        findings.append(Finding("ERROR", case.id, "client_manifest_findings_type", "expected list", "$.findings"))
        findings_list = []
    error_count = sum(1 for item in findings_list if isinstance(item, dict) and item.get("level") == "ERROR")
    warning_count = sum(1 for item in findings_list if isinstance(item, dict) and item.get("level") == "WARNING")
    if summary.get("ERROR") != error_count:
        findings.append(Finding("ERROR", case.id, "client_manifest_error_count_mismatch", f"summary={summary.get('ERROR')}, findings={error_count}", "$.summary.ERROR"))
    if summary.get("WARNING") != warning_count:
        findings.append(Finding("ERROR", case.id, "client_manifest_warning_count_mismatch", f"summary={summary.get('WARNING')}, findings={warning_count}", "$.summary.WARNING"))

    stable_full_lifecycle = summary.get("stable_full_lifecycle_clients")
    stable_context = summary.get("stable_context_clients")
    minimum = summary.get("required_for_generic_oss")
    ready = data.get("multi_client_ready")
    context_ready = data.get("context_cli_ready")
    if isinstance(stable_full_lifecycle, int) and isinstance(minimum, int) and ready is True and stable_full_lifecycle < minimum:
        findings.append(Finding("ERROR", case.id, "client_manifest_ready_below_minimum", "multi_client_ready cannot be true below stable full-lifecycle minimum", "$.multi_client_ready"))
    if isinstance(stable_context, int) and isinstance(minimum, int) and context_ready is True and stable_context < minimum:
        findings.append(Finding("ERROR", case.id, "client_manifest_context_ready_below_minimum", "context_cli_ready cannot be true below stable context minimum", "$.context_cli_ready"))
    full_lifecycle_readiness = readiness.get("full_lifecycle_multi_client") if isinstance(readiness, dict) else None
    if isinstance(full_lifecycle_readiness, dict):
        if full_lifecycle_readiness.get("ready") != ready:
            findings.append(Finding("ERROR", case.id, "client_manifest_readiness_full_lifecycle_ready_mismatch", "must match multi_client_ready", "$.readiness.full_lifecycle_multi_client.ready"))
        if full_lifecycle_readiness.get("stable_clients") != stable_full_lifecycle:
            findings.append(Finding("ERROR", case.id, "client_manifest_readiness_full_lifecycle_stable_mismatch", "must match summary.stable_full_lifecycle_clients", "$.readiness.full_lifecycle_multi_client.stable_clients"))
        if full_lifecycle_readiness.get("required_clients") != minimum:
            findings.append(Finding("ERROR", case.id, "client_manifest_readiness_full_lifecycle_required_mismatch", "must match summary.required_for_generic_oss", "$.readiness.full_lifecycle_multi_client.required_clients"))
    context_cli_readiness = readiness.get("context_cli") if isinstance(readiness, dict) else None
    if isinstance(context_cli_readiness, dict):
        if context_cli_readiness.get("ready") != context_ready:
            findings.append(Finding("ERROR", case.id, "client_manifest_readiness_context_ready_mismatch", "must match context_cli_ready", "$.readiness.context_cli.ready"))
        if context_cli_readiness.get("stable_clients") != stable_context:
            findings.append(Finding("ERROR", case.id, "client_manifest_readiness_context_stable_mismatch", "must match summary.stable_context_clients", "$.readiness.context_cli.stable_clients"))
        if context_cli_readiness.get("required_clients") != minimum:
            findings.append(Finding("ERROR", case.id, "client_manifest_readiness_context_required_mismatch", "must match summary.required_for_generic_oss", "$.readiness.context_cli.required_clients"))
    expected_verdict = "invalid" if error_count else ("single_client_scope" if warning_count else "ok")
    if data.get("verdict") != expected_verdict:
        findings.append(Finding("ERROR", case.id, "client_manifest_verdict_mismatch", f"expected {expected_verdict}", "$.verdict"))
    return findings


def validate_owner_decision_record_summary(
    findings: list[Finding],
    case: ContractCase,
    summary: Any,
    owner_decisions: list[Any],
    decision_state_findings: list[Any],
    path: str,
) -> None:
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "owner_decision_record_summary_type", "expected object", path))
        return
    expected_status_counts: dict[str, int] = {}
    valid_records = 0
    invalid_records = 0
    missing_records = 0
    for item in owner_decisions:
        if not isinstance(item, dict):
            continue
        status = str(item.get("record_status", "unknown") or "unknown")
        expected_status_counts[status] = expected_status_counts.get(status, 0) + 1
        if item.get("record_valid") is True:
            valid_records += 1
        else:
            invalid_records += 1
        if item.get("record_present") is not True:
            missing_records += 1
    expected = {
        "valid_records": valid_records,
        "invalid_records": invalid_records,
        "missing_records": missing_records,
        "stale_records": len(decision_state_findings),
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            findings.append(Finding(
                "ERROR",
                case.id,
                f"owner_decision_record_summary_{key}_mismatch",
                f"expected={value}, actual={summary.get(key)}",
                f"{path}.{key}",
            ))
    if normalize_int_map(summary.get("record_status_counts", {})) != dict(sorted(expected_status_counts.items())):
        findings.append(Finding(
            "ERROR",
            case.id,
            "owner_decision_record_status_counts_mismatch",
            f"expected={dict(sorted(expected_status_counts.items()))}, actual={summary.get('record_status_counts')}",
            f"{path}.record_status_counts",
        ))


def validate_owner_gap_record_commands(
    findings: list[Finding],
    case: ContractCase,
    item: dict[str, Any],
    item_path: str,
    code_prefix: str,
) -> None:
    if not isinstance(item.get("allowed_options"), list) or not item.get("allowed_options"):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_allowed_options", "expected non-empty list", f"{item_path}.allowed_options"))
    for field in ("record_dry_run_command", "record_write_command"):
        command = item.get(field)
        if not isinstance(command, list) or not command:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_{field}", "expected non-empty command list", f"{item_path}.{field}"))
            continue
        command_values = [str(value) for value in command]
        if "release-record-decision" not in command_values:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_{field}_missing_entrypoint", "expected release-record-decision command", f"{item_path}.{field}"))
        if "--decision" not in command_values:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_{field}_missing_decision", "expected --decision", f"{item_path}.{field}"))
        if "<option>" not in command_values:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_{field}_missing_option_placeholder", "expected <option>", f"{item_path}.{field}"))
        if "<owner>" not in command_values:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_{field}_missing_owner_placeholder", "expected <owner>", f"{item_path}.{field}"))
        if "YYYY-MM-DD" not in command_values:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_{field}_missing_date_placeholder", "expected YYYY-MM-DD", f"{item_path}.{field}"))
    dry_run_command = item.get("record_dry_run_command")
    if isinstance(dry_run_command, list) and "--dry-run" not in dry_run_command:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_dry_run_flag", "expected --dry-run", f"{item_path}.record_dry_run_command"))
    write_command = item.get("record_write_command")
    if isinstance(write_command, list) and "--write" not in write_command:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_write_flag", "expected --write", f"{item_path}.record_write_command"))


def validate_owner_record_gate_effect(
    findings: list[Finding],
    case: ContractCase,
    value: Any,
    item_path: str,
    code_prefix: str,
) -> None:
    if not isinstance(value, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_record_gate_effect", "expected object", f"{item_path}.record_gate_effect"))
        return
    if value.get("effect") != "records_owner_choice_only":
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_record_gate_effect_effect", "expected records_owner_choice_only", f"{item_path}.record_gate_effect.effect"))
    if value.get("clears_release_blocker") is not False:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_record_gate_effect_clears_release_blocker", "expected false", f"{item_path}.record_gate_effect.clears_release_blocker"))
    require_nonempty_string(findings, case, value.get("next_check"), f"{code_prefix}_record_gate_effect_next_check", f"{item_path}.record_gate_effect.next_check")


def validate_gate_unblock_requirements(
    findings: list[Finding],
    case: ContractCase,
    item: dict[str, Any],
    item_path: str,
    code_prefix: str,
) -> None:
    value = item.get("gate_unblock_requirements")
    if not isinstance(value, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_gate_unblock_requirements", "expected object", f"{item_path}.gate_unblock_requirements"))
        return
    if value.get("status") != "blocked_until_requirements_clear":
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_gate_unblock_status", "expected blocked_until_requirements_clear", f"{item_path}.gate_unblock_requirements.status"))
    requirements = value.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_gate_unblock_requirements_list", "expected non-empty list", f"{item_path}.gate_unblock_requirements.requirements"))
        return
    actual: dict[str, Any] = {}
    for index, requirement in enumerate(requirements):
        req_path = f"{item_path}.gate_unblock_requirements.requirements[{index}]"
        if not isinstance(requirement, dict):
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_gate_unblock_requirement_type", "expected object", req_path))
            continue
        kind = requirement.get("kind")
        require_nonempty_string(findings, case, kind, f"{code_prefix}_gate_unblock_requirement_kind", f"{req_path}.kind")
        actual[str(kind)] = requirement.get("values")
    expected: dict[str, Any] = {}
    required_artifacts = item.get("required_artifacts")
    required_when = item.get("required_when")
    if isinstance(required_artifacts, list) and required_artifacts:
        expected["required_artifacts"] = [str(value) for value in required_artifacts]
    if isinstance(required_when, dict) and required_when:
        expected["required_conditions"] = required_when
    if not expected:
        expected["rerun_release_check"] = {}
    if actual != expected:
        findings.append(Finding(
            "ERROR",
            case.id,
            f"{code_prefix}_gate_unblock_requirements_mismatch",
            f"expected={expected}, actual={actual}",
            f"{item_path}.gate_unblock_requirements.requirements",
        ))


def validate_gap_client_portability_evidence(
    findings: list[Finding],
    case: ContractCase,
    item: dict[str, Any],
    item_path: str,
    code_prefix: str,
) -> None:
    if item.get("check_id") != "client_portability":
        return
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_client_portability_evidence", "expected object", f"{item_path}.evidence"))
        return
    readiness = evidence.get("readiness")
    if not isinstance(readiness, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_client_portability_readiness", "expected readiness evidence", f"{item_path}.evidence.readiness"))
    validate_client_contract_evidence(
        findings,
        case,
        evidence.get("contracts"),
        f"{item_path}.evidence.contracts",
        f"{code_prefix}_client_portability",
    )
    clients = evidence.get("clients")
    if not isinstance(clients, list) or not clients:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_client_portability_clients", "expected non-empty clients evidence", f"{item_path}.evidence.clients"))
    claim_policy = evidence.get("claim_policy")
    if not isinstance(claim_policy, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_client_portability_claim_policy", "expected claim_policy evidence", f"{item_path}.evidence.claim_policy"))
    elif not isinstance(claim_policy.get("checked"), int) or claim_policy.get("checked") < 3:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_client_portability_claim_policy_checked", "expected checked>=3", f"{item_path}.evidence.claim_policy.checked"))
    validate_client_remediation_plan(
        findings,
        case,
        evidence.get("remediation_plan"),
        f"{item_path}.evidence.remediation_plan",
        f"{code_prefix}_client_portability",
    )
    validate_client_lifecycle_gap_summary(
        findings,
        case,
        item.get("client_lifecycle_gaps"),
        f"{item_path}.client_lifecycle_gaps",
        f"{code_prefix}_client_portability",
    )


def validate_client_contract_evidence(
    findings: list[Finding],
    case: ContractCase,
    contracts: Any,
    path: str,
    code_prefix: str,
) -> None:
    if not isinstance(contracts, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_contracts", "expected contracts evidence", path))
        return
    required = {
        "full_lifecycle_required_capabilities": "install_or_bootstrap",
        "context_brief_required_capabilities": "context_brief_cli",
    }
    for key, expected_member in required.items():
        rows = contracts.get(key)
        if not isinstance(rows, list) or not all(isinstance(item, str) and item.strip() for item in rows):
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_contracts_{key}", "expected non-empty string list", f"{path}.{key}"))
            continue
        if expected_member not in rows:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_contracts_{key}_member", f"expected {expected_member}", f"{path}.{key}"))


def validate_client_lifecycle_gap_summary(
    findings: list[Finding],
    case: ContractCase,
    lifecycle_gaps: Any,
    path: str,
    code_prefix: str,
) -> None:
    if not isinstance(lifecycle_gaps, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_lifecycle_gaps", "expected client_lifecycle_gaps object", path))
        return
    full_required = lifecycle_gaps.get("full_lifecycle_required_capabilities")
    context_required = lifecycle_gaps.get("context_brief_required_capabilities")
    if not isinstance(full_required, list) or "install_or_bootstrap" not in full_required:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_lifecycle_full_required", "expected full lifecycle requirements", f"{path}.full_lifecycle_required_capabilities"))
    if not isinstance(context_required, list) or "context_brief_cli" not in context_required:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_lifecycle_context_required", "expected context brief requirements", f"{path}.context_brief_required_capabilities"))
    clients = lifecycle_gaps.get("clients")
    if not isinstance(clients, list) or not clients:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_lifecycle_clients", "expected client rows", f"{path}.clients"))
        return
    for index, client in enumerate(clients):
        row_path = f"{path}.clients[{index}]"
        if not isinstance(client, dict):
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_lifecycle_client_type", "expected object", row_path))
            continue
        require_nonempty_string(findings, case, client.get("id"), f"{code_prefix}_lifecycle_client_id", f"{row_path}.id")
        for key in ("missing_full_lifecycle_capabilities", "missing_context_brief_capabilities"):
            rows = client.get(key)
            if not isinstance(rows, list) or not all(isinstance(item, str) for item in rows):
                findings.append(Finding("ERROR", case.id, f"{code_prefix}_lifecycle_client_{key}", "expected string list", f"{row_path}.{key}"))


def validate_publish_scope_gap_breakdown(
    findings: list[Finding],
    case: ContractCase,
    item: dict[str, Any],
    item_path: str,
    code_prefix: str,
) -> None:
    if item.get("check_id") != "publish_scope":
        return
    breakdown = item.get("publish_scope_breakdown")
    if not isinstance(breakdown, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_breakdown", "expected publish_scope_breakdown object", f"{item_path}.publish_scope_breakdown"))
        return
    private_count = breakdown.get("private_tracked_paths")
    unclassified_count = breakdown.get("unclassified_tracked_paths")
    if not isinstance(private_count, int) or private_count < 0:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_private_count", "expected non-negative integer", f"{item_path}.publish_scope_breakdown.private_tracked_paths"))
        private_count = 0
    if not isinstance(unclassified_count, int) or unclassified_count < 0:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_unclassified_count", "expected non-negative integer", f"{item_path}.publish_scope_breakdown.unclassified_tracked_paths"))
    private_summary = breakdown.get("private_tracked_summary")
    if not isinstance(private_summary, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_private_summary", "expected private_tracked_summary object", f"{item_path}.publish_scope_breakdown.private_tracked_summary"))
        private_summary = {}
    for key in ("by_reason", "by_path_group", "by_match"):
        rows = private_summary.get(key)
        if not isinstance(rows, list):
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_private_{key}", "expected list", f"{item_path}.publish_scope_breakdown.private_tracked_summary.{key}"))
            continue
        total = 0
        for index, row in enumerate(rows):
            row_path = f"{item_path}.publish_scope_breakdown.private_tracked_summary.{key}[{index}]"
            if not isinstance(row, dict):
                findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_private_{key}_row", "expected object", row_path))
                continue
            require_nonempty_string(findings, case, row.get("key"), f"{code_prefix}_publish_scope_private_{key}_key", f"{row_path}.key")
            count = row.get("count")
            if not isinstance(count, int) or count <= 0:
                findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_private_{key}_count", "expected positive integer", f"{row_path}.count"))
                continue
            total += count
        if isinstance(private_count, int) and rows and total != private_count:
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_publish_scope_private_{key}_total", f"private_tracked_paths={private_count}, summary={total}", f"{item_path}.publish_scope_breakdown.private_tracked_summary.{key}"))


def validate_client_remediation_plan(
    findings: list[Finding],
    case: ContractCase,
    plan: Any,
    path: str,
    code_prefix: str,
) -> None:
    if not isinstance(plan, dict):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_remediation_plan", "expected remediation_plan object", path))
        return
    if plan.get("decision") != "client_portability_scope":
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_remediation_decision", "expected client_portability_scope", f"{path}.decision"))
    require_nonempty_string(findings, case, plan.get("owner"), f"{code_prefix}_remediation_owner", f"{path}.owner")
    if not isinstance(plan.get("ready"), bool):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_remediation_ready", "expected bool", f"{path}.ready"))
    require_nonempty_string(findings, case, plan.get("current_constraint"), f"{code_prefix}_remediation_constraint", f"{path}.current_constraint")
    require_nonempty_string(findings, case, plan.get("next_check"), f"{code_prefix}_remediation_next_check", f"{path}.next_check")
    options = plan.get("options")
    if not isinstance(options, list):
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_remediation_options", "expected at least two options", f"{path}.options"))
        return
    if len(options) < 2:
        findings.append(Finding("ERROR", case.id, f"{code_prefix}_remediation_options", "expected at least two options", f"{path}.options"))
    option_ids: set[str] = set()
    for index, option in enumerate(options):
        option_path = f"{path}.options[{index}]"
        if not isinstance(option, dict):
            findings.append(Finding("ERROR", case.id, f"{code_prefix}_remediation_option_type", "expected object", option_path))
            continue
        option_id = option.get("id")
        require_nonempty_string(findings, case, option_id, f"{code_prefix}_remediation_option_id", f"{option_path}.id")
        if isinstance(option_id, str):
            option_ids.add(option_id)
        require_nonempty_string(findings, case, option.get("action"), f"{code_prefix}_remediation_option_action", f"{option_path}.action")
        require_nonempty_string(findings, case, option.get("effect"), f"{code_prefix}_remediation_option_effect", f"{option_path}.effect")
    required = {"keep_narrow_claim", "add_second_full_lifecycle_client"}
    if not required.issubset(option_ids):
        findings.append(Finding(
            "ERROR",
            case.id,
            f"{code_prefix}_remediation_required_options",
            f"missing={sorted(required - option_ids)}",
            f"{path}.options",
        ))


def validate_remaining_gap_table(
    findings: list[Finding],
    case: ContractCase,
    table: Any,
    issues: list[Any],
) -> None:
    if not isinstance(table, dict):
        findings.append(Finding("ERROR", case.id, "ledger_remaining_gap_table_missing", "expected object", "$.remaining_gap_table"))
        return
    expected: dict[str, list[str]] = {
        "owner_decisions": [],
        "code_remediation": [],
        "docs_publish_scope_governance": [],
        "deferred": [],
    }
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("issue_id", ""))
        state = issue.get("state")
        gap = issue.get("gap") if isinstance(issue.get("gap"), dict) else {}
        gap_type = str(gap.get("type", "unknown"))
        if state == "deferred":
            expected["deferred"].append(issue_id)
        elif state != "open":
            continue
        elif gap_type in {"owner_decision", "publish_scope_governance"}:
            expected["owner_decisions"].append(issue_id)
        elif gap_type == "code_remediation":
            expected["code_remediation"].append(issue_id)
        else:
            expected["docs_publish_scope_governance"].append(issue_id)

    for key, expected_ids in expected.items():
        items = table.get(key)
        if not isinstance(items, list):
            findings.append(Finding("ERROR", case.id, f"ledger_remaining_gap_table_{key}_type", "expected list", f"$.remaining_gap_table.{key}"))
            continue
        actual_ids: list[str] = []
        for index, item in enumerate(items):
            item_path = f"$.remaining_gap_table.{key}[{index}]"
            if not isinstance(item, dict):
                findings.append(Finding("ERROR", case.id, "ledger_remaining_gap_table_item_type", "expected object", item_path))
                continue
            issue_id = item.get("issue_id")
            actual_ids.append(str(issue_id or ""))
            require_nonempty_string(findings, case, issue_id, "ledger_remaining_gap_table_issue_id", f"{item_path}.issue_id")
            require_nonempty_string(findings, case, item.get("check_id"), "ledger_remaining_gap_table_check_id", f"{item_path}.check_id")
            require_nonempty_string(findings, case, item.get("gap_type"), "ledger_remaining_gap_table_gap_type", f"{item_path}.gap_type")
            require_nonempty_string(findings, case, item.get("owner"), "ledger_remaining_gap_table_owner", f"{item_path}.owner")
            require_nonempty_string(findings, case, item.get("resolution"), "ledger_remaining_gap_table_resolution", f"{item_path}.resolution")
            validate_gap_client_portability_evidence(findings, case, item, item_path, "ledger_remaining_gap_table")
            if key == "owner_decisions":
                require_nonempty_string(findings, case, item.get("decision"), "ledger_remaining_gap_table_decision", f"{item_path}.decision")
                require_nonempty_string(findings, case, item.get("decision_doc"), "ledger_remaining_gap_table_decision_doc", f"{item_path}.decision_doc")
                require_nonempty_string(findings, case, item.get("record_status"), "ledger_remaining_gap_table_record_status", f"{item_path}.record_status")
                validate_publish_scope_gap_breakdown(findings, case, item, item_path, "ledger_remaining_gap_table")
                validate_owner_gap_record_commands(findings, case, item, item_path, "ledger_remaining_gap_table")
                validate_owner_record_gate_effect(findings, case, item.get("record_gate_effect"), item_path, "ledger_remaining_gap_table")
                validate_gate_unblock_requirements(findings, case, item, item_path, "ledger_remaining_gap_table")
                if not isinstance(item.get("required_artifacts"), list):
                    findings.append(Finding("ERROR", case.id, "ledger_remaining_gap_table_required_artifacts", "expected list", f"{item_path}.required_artifacts"))
                if not isinstance(item.get("required_when"), dict):
                    findings.append(Finding("ERROR", case.id, "ledger_remaining_gap_table_required_when", "expected object", f"{item_path}.required_when"))
        if actual_ids != expected_ids:
            findings.append(Finding(
                "ERROR",
                case.id,
                f"ledger_remaining_gap_table_{key}_mismatch",
                f"expected={expected_ids}, actual={actual_ids}",
                f"$.remaining_gap_table.{key}",
            ))


def validate_release_issue_ledger_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "ledger_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "release_issue_ledger":
        findings.append(Finding("ERROR", case.id, "ledger_kind", "expected kind=release_issue_ledger", "$.kind"))

    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "ledger_summary_type", "expected object", "$.summary"))
        return findings

    issues = data.get("issues")
    if not isinstance(issues, list):
        findings.append(Finding("ERROR", case.id, "ledger_issues_type", "expected list", "$.issues"))
        return findings

    open_by_gap_type = summary.get("open_by_gap_type")
    open_by_owner = summary.get("open_by_owner")
    owner_decisions = data.get("owner_decisions")
    decision_state_findings = data.get("decision_state_findings")
    if not isinstance(open_by_gap_type, dict):
        findings.append(Finding("ERROR", case.id, "ledger_gap_type_summary_missing", "expected object", "$.summary.open_by_gap_type"))
        open_by_gap_type = {}
    if not isinstance(open_by_owner, dict):
        findings.append(Finding("ERROR", case.id, "ledger_owner_summary_missing", "expected object", "$.summary.open_by_owner"))
        open_by_owner = {}
    if not isinstance(owner_decisions, list):
        findings.append(Finding("ERROR", case.id, "ledger_owner_decisions_missing", "expected list", "$.owner_decisions"))
        owner_decisions = []
    if not isinstance(decision_state_findings, list):
        findings.append(Finding("ERROR", case.id, "ledger_decision_state_findings_type", "expected list", "$.decision_state_findings"))
        decision_state_findings = []
    elif decision_state_findings:
        findings.append(Finding("ERROR", case.id, "ledger_decision_state_findings_nonempty", "decision state findings must be empty", "$.decision_state_findings"))

    expected_by_type: dict[str, int] = {}
    expected_by_owner: dict[str, int] = {}
    expected_owner_decision_ids: set[str] = set()
    for index, issue in enumerate(issues):
        issue_path = f"$.issues[{index}]"
        if not isinstance(issue, dict):
            findings.append(Finding("ERROR", case.id, "ledger_issue_type", "expected object", issue_path))
            continue
        gap = issue.get("gap")
        if not isinstance(gap, dict):
            findings.append(Finding("ERROR", case.id, "ledger_issue_gap_missing", "expected object", f"{issue_path}.gap"))
            continue
        require_nonempty_string(findings, case, gap.get("type"), "ledger_issue_gap_type", f"{issue_path}.gap.type")
        require_nonempty_string(findings, case, gap.get("owner"), "ledger_issue_gap_owner", f"{issue_path}.gap.owner")
        require_nonempty_string(findings, case, gap.get("resolution"), "ledger_issue_gap_resolution", f"{issue_path}.gap.resolution")
        if issue.get("check_id") == "client_portability":
            evidence = issue.get("evidence")
            if not isinstance(evidence, dict):
                findings.append(Finding("ERROR", case.id, "ledger_client_portability_evidence", "expected object", f"{issue_path}.evidence"))
                evidence = {}
            if not isinstance(evidence.get("readiness"), dict):
                findings.append(Finding("ERROR", case.id, "ledger_client_portability_readiness", "expected readiness evidence", f"{issue_path}.evidence.readiness"))
            validate_client_contract_evidence(
                findings,
                case,
                evidence.get("contracts"),
                f"{issue_path}.evidence.contracts",
                "ledger_client_portability",
            )
            clients = evidence.get("clients")
            if not isinstance(clients, list) or not clients:
                findings.append(Finding("ERROR", case.id, "ledger_client_portability_clients", "expected non-empty clients evidence", f"{issue_path}.evidence.clients"))
            claim_policy = evidence.get("claim_policy")
            if not isinstance(claim_policy, dict):
                findings.append(Finding("ERROR", case.id, "ledger_client_portability_claim_policy", "expected claim_policy evidence", f"{issue_path}.evidence.claim_policy"))
            elif not isinstance(claim_policy.get("checked"), int) or claim_policy.get("checked") < 3:
                findings.append(Finding("ERROR", case.id, "ledger_client_portability_claim_policy_checked", "expected checked>=3", f"{issue_path}.evidence.claim_policy.checked"))
            validate_client_remediation_plan(
                findings,
                case,
                evidence.get("remediation_plan"),
                f"{issue_path}.evidence.remediation_plan",
                "ledger_client_portability",
            )
        if issue.get("check_id") == "docs_entrypoints":
            evidence = issue.get("evidence")
            if not isinstance(evidence, dict):
                findings.append(Finding("ERROR", case.id, "ledger_docs_entrypoints_evidence", "expected object", f"{issue_path}.evidence"))
                evidence = {}
            frontmatter_checked = evidence.get("frontmatter_checked")
            if not isinstance(frontmatter_checked, int) or frontmatter_checked < 5:
                findings.append(Finding("ERROR", case.id, "ledger_docs_entrypoints_frontmatter_checked", "expected frontmatter_checked>=5", f"{issue_path}.evidence.frontmatter_checked"))
        if issue.get("state") == "open":
            gap_type = str(gap.get("type", "unknown"))
            owner = str(gap.get("owner", "unknown"))
            expected_by_type[gap_type] = expected_by_type.get(gap_type, 0) + 1
            expected_by_owner[owner] = expected_by_owner.get(owner, 0) + 1
            if gap_type in {"owner_decision", "publish_scope_governance"}:
                expected_owner_decision_ids.add(str(issue.get("issue_id", "")))
                evidence = issue.get("evidence")
                decision_plan = evidence.get("decision_plan") if isinstance(evidence, dict) else None
                if not isinstance(decision_plan, dict) or not decision_plan:
                    findings.append(Finding(
                        "ERROR",
                        case.id,
                        "ledger_owner_issue_decision_plan_missing",
                        "open owner-governed issue must include evidence.decision_plan",
                        f"{issue_path}.evidence.decision_plan",
                    ))

    actual_owner_decision_ids: set[str] = set()
    for index, item in enumerate(owner_decisions):
        item_path = f"$.owner_decisions[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_type", "expected object", item_path))
            continue
        issue_id = item.get("issue_id")
        require_nonempty_string(findings, case, issue_id, "ledger_owner_decision_issue_id", f"{item_path}.issue_id")
        actual_owner_decision_ids.add(str(issue_id or ""))
        require_nonempty_string(findings, case, item.get("owner"), "ledger_owner_decision_owner", f"{item_path}.owner")
        require_nonempty_string(findings, case, item.get("decision"), "ledger_owner_decision_name", f"{item_path}.decision")
        require_nonempty_string(findings, case, item.get("record_status"), "ledger_owner_decision_record_status", f"{item_path}.record_status")
        require_nonempty_string(findings, case, item.get("decision_state_file"), "ledger_owner_decision_state_file", f"{item_path}.decision_state_file")
        if item.get("record_present") is not True:
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_record_missing", "owner decision record must be present", f"{item_path}.record_present"))
        if not isinstance(item.get("record_valid"), bool):
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_record_valid", "expected bool", f"{item_path}.record_valid"))
        elif item.get("record_valid") is not True:
            findings.append(Finding(
                "ERROR",
                case.id,
                "ledger_owner_decision_record_invalid",
                "owner decision record must be valid",
                f"{item_path}.record_valid",
            ))
        if not isinstance(item.get("record_findings"), list):
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_record_findings", "expected list", f"{item_path}.record_findings"))
        elif item.get("record_findings"):
            findings.append(Finding(
                "ERROR",
                case.id,
                "ledger_owner_decision_record_findings_nonempty",
                "owner decision record findings must be empty",
                f"{item_path}.record_findings",
            ))
        if not isinstance(item.get("gate_ready"), bool):
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_gate_ready", "expected bool", f"{item_path}.gate_ready"))
        elif item.get("ready") != item.get("gate_ready"):
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_ready_gate_ready_mismatch", "ready must mirror gate_ready", f"{item_path}.ready"))
        expected_record_ready = bool(item.get("record_valid") is True and item.get("record_status") == "decided")
        if not isinstance(item.get("record_ready"), bool):
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_record_ready", "expected bool", f"{item_path}.record_ready"))
        elif item.get("record_ready") != expected_record_ready:
            findings.append(Finding(
                "ERROR",
                case.id,
                "ledger_owner_decision_record_ready_mismatch",
                f"expected={expected_record_ready}, actual={item.get('record_ready')}",
                f"{item_path}.record_ready",
            ))
        validate_owner_record_gate_effect(findings, case, item.get("record_gate_effect"), item_path, "ledger_owner_decision")
        validate_gate_unblock_requirements(findings, case, item, item_path, "ledger_owner_decision")
        options = item.get("options")
        if not isinstance(options, list) or not options:
            findings.append(Finding("ERROR", case.id, "ledger_owner_decision_options", "expected non-empty list", f"{item_path}.options"))
    if actual_owner_decision_ids != expected_owner_decision_ids:
        findings.append(Finding(
            "ERROR",
            case.id,
            "ledger_owner_decisions_mismatch",
            f"expected={sorted(expected_owner_decision_ids)}, actual={sorted(actual_owner_decision_ids)}",
            "$.owner_decisions",
        ))
    if summary.get("owner_decisions") != len(owner_decisions):
        findings.append(Finding(
            "ERROR",
            case.id,
            "ledger_owner_decisions_summary_mismatch",
            f"expected={len(owner_decisions)}, actual={summary.get('owner_decisions')}",
            "$.summary.owner_decisions",
        ))
    if summary.get("decision_state_findings") != len(decision_state_findings):
        findings.append(Finding(
            "ERROR",
            case.id,
            "ledger_decision_state_findings_summary_mismatch",
            f"expected={len(decision_state_findings)}, actual={summary.get('decision_state_findings')}",
            "$.summary.decision_state_findings",
        ))
    validate_owner_decision_record_summary(
        findings,
        case,
        summary.get("owner_decision_records"),
        owner_decisions,
        decision_state_findings,
        "$.summary.owner_decision_records",
    )
    validate_remaining_gap_table(
        findings,
        case,
        data.get("remaining_gap_table"),
        issues,
    )

    if normalize_int_map(open_by_gap_type) != expected_by_type:
        findings.append(Finding(
            "ERROR",
            case.id,
            "ledger_gap_type_summary_mismatch",
            f"expected={expected_by_type}, actual={open_by_gap_type}",
            "$.summary.open_by_gap_type",
        ))
    if normalize_int_map(open_by_owner) != expected_by_owner:
        findings.append(Finding(
            "ERROR",
            case.id,
            "ledger_owner_summary_mismatch",
            f"expected={expected_by_owner}, actual={open_by_owner}",
            "$.summary.open_by_owner",
        ))
    return findings


def validate_release_owner_decisions_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "owner_decisions_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "release_owner_decisions":
        findings.append(Finding("ERROR", case.id, "owner_decisions_kind", "expected kind=release_owner_decisions", "$.kind"))
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "owner_decisions_summary_type", "expected object", "$.summary"))
        return findings
    owner_decisions = data.get("owner_decisions")
    if not isinstance(owner_decisions, list):
        findings.append(Finding("ERROR", case.id, "owner_decisions_list_type", "expected list", "$.owner_decisions"))
        return findings
    decision_state_findings = data.get("decision_state_findings")
    if not isinstance(decision_state_findings, list):
        findings.append(Finding("ERROR", case.id, "owner_decision_state_findings_type", "expected list", "$.decision_state_findings"))
        decision_state_findings = []
    elif decision_state_findings:
        findings.append(Finding("ERROR", case.id, "owner_decision_state_findings_nonempty", "decision state findings must be empty", "$.decision_state_findings"))
    ready = 0
    not_ready = 0
    for index, item in enumerate(owner_decisions):
        item_path = f"$.owner_decisions[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "owner_decision_type", "expected object", item_path))
            continue
        require_nonempty_string(findings, case, item.get("issue_id"), "owner_decision_issue_id", f"{item_path}.issue_id")
        require_nonempty_string(findings, case, item.get("owner"), "owner_decision_owner", f"{item_path}.owner")
        require_nonempty_string(findings, case, item.get("decision"), "owner_decision_name", f"{item_path}.decision")
        require_nonempty_string(findings, case, item.get("record_status"), "owner_decision_record_status", f"{item_path}.record_status")
        require_nonempty_string(findings, case, item.get("decision_state_file"), "owner_decision_state_file", f"{item_path}.decision_state_file")
        if item.get("record_present") is not True:
            findings.append(Finding("ERROR", case.id, "owner_decision_record_missing", "owner decision record must be present", f"{item_path}.record_present"))
        if not isinstance(item.get("record_valid"), bool):
            findings.append(Finding("ERROR", case.id, "owner_decision_record_valid", "expected bool", f"{item_path}.record_valid"))
        elif item.get("record_valid") is not True:
            findings.append(Finding(
                "ERROR",
                case.id,
                "owner_decision_record_invalid",
                "owner decision record must be valid",
                f"{item_path}.record_valid",
            ))
        if not isinstance(item.get("record_findings"), list):
            findings.append(Finding("ERROR", case.id, "owner_decision_record_findings", "expected list", f"{item_path}.record_findings"))
        elif item.get("record_findings"):
            findings.append(Finding(
                "ERROR",
                case.id,
                "owner_decision_record_findings_nonempty",
                "owner decision record findings must be empty",
                f"{item_path}.record_findings",
            ))
        if not isinstance(item.get("gate_ready"), bool):
            findings.append(Finding("ERROR", case.id, "owner_decision_gate_ready", "expected bool", f"{item_path}.gate_ready"))
        elif item.get("ready") != item.get("gate_ready"):
            findings.append(Finding("ERROR", case.id, "owner_decision_ready_gate_ready_mismatch", "ready must mirror gate_ready", f"{item_path}.ready"))
        expected_record_ready = bool(item.get("record_valid") is True and item.get("record_status") == "decided")
        if not isinstance(item.get("record_ready"), bool):
            findings.append(Finding("ERROR", case.id, "owner_decision_record_ready", "expected bool", f"{item_path}.record_ready"))
        elif item.get("record_ready") != expected_record_ready:
            findings.append(Finding(
                "ERROR",
                case.id,
                "owner_decision_record_ready_mismatch",
                f"expected={expected_record_ready}, actual={item.get('record_ready')}",
                f"{item_path}.record_ready",
            ))
        validate_owner_record_gate_effect(findings, case, item.get("record_gate_effect"), item_path, "owner_decision")
        validate_gate_unblock_requirements(findings, case, item, item_path, "owner_decision")
        options = item.get("options")
        if not isinstance(options, list) or not options:
            findings.append(Finding("ERROR", case.id, "owner_decision_options", "expected non-empty list", f"{item_path}.options"))
        if item.get("ready") is True:
            ready += 1
        else:
            not_ready += 1
    expected_summary = {
        "owner_decisions": len(owner_decisions),
        "ready": ready,
        "not_ready": not_ready,
        "gate_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("gate_ready") is True),
        "gate_not_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("gate_ready") is not True),
        "record_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("record_ready") is True),
        "record_not_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("record_ready") is not True),
        "decision_state_findings": len(decision_state_findings),
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            findings.append(Finding(
                "ERROR",
                case.id,
                f"owner_decisions_summary_{key}_mismatch",
                f"expected={expected}, actual={summary.get(key)}",
                f"$.summary.{key}",
            ))
    validate_owner_decision_record_summary(
        findings,
        case,
        summary.get("owner_decision_records"),
        owner_decisions,
        decision_state_findings,
        "$.summary.owner_decision_records",
    )
    return findings


def validate_release_owner_decision_template_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "owner_decision_template_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "release_owner_decision_template":
        findings.append(Finding("ERROR", case.id, "owner_decision_template_kind", "expected kind=release_owner_decision_template", "$.kind"))
    require_nonempty_string(findings, case, data.get("decision_state_file"), "owner_decision_template_state_file", "$.decision_state_file")
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "owner_decision_template_summary_type", "expected object", "$.summary"))
        summary = {}
    templates = data.get("templates")
    if not isinstance(templates, list):
        findings.append(Finding("ERROR", case.id, "owner_decision_template_list_type", "expected list", "$.templates"))
        return findings
    if summary.get("templates") != len(templates):
        findings.append(Finding(
            "ERROR",
            case.id,
            "owner_decision_template_summary_mismatch",
            f"expected={len(templates)}, actual={summary.get('templates')}",
            "$.summary.templates",
        ))
    patch_root = data.get("state_patch_template")
    patch_decisions = patch_root.get("decisions") if isinstance(patch_root, dict) else None
    if not isinstance(patch_decisions, dict):
        findings.append(Finding("ERROR", case.id, "owner_decision_template_patch_type", "expected decisions object", "$.state_patch_template.decisions"))
        patch_decisions = {}
    for index, item in enumerate(templates):
        item_path = f"$.templates[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "owner_decision_template_item_type", "expected object", item_path))
            continue
        decision = item.get("decision")
        require_nonempty_string(findings, case, decision, "owner_decision_template_decision", f"{item_path}.decision")
        require_nonempty_string(findings, case, item.get("issue_id"), "owner_decision_template_issue_id", f"{item_path}.issue_id")
        require_nonempty_string(findings, case, item.get("owner"), "owner_decision_template_owner", f"{item_path}.owner")
        require_nonempty_string(findings, case, item.get("record_status"), "owner_decision_template_record_status", f"{item_path}.record_status")
        require_nonempty_string(findings, case, item.get("decision_doc"), "owner_decision_template_doc", f"{item_path}.decision_doc")
        require_nonempty_string(findings, case, item.get("decision_state_file"), "owner_decision_template_item_state_file", f"{item_path}.decision_state_file")
        allowed_options = item.get("allowed_options")
        if not isinstance(allowed_options, list) or not allowed_options:
            findings.append(Finding("ERROR", case.id, "owner_decision_template_options", "expected non-empty list", f"{item_path}.allowed_options"))
        else:
            for option_index, option in enumerate(allowed_options):
                option_path = f"{item_path}.allowed_options[{option_index}]"
                if not isinstance(option, dict):
                    findings.append(Finding("ERROR", case.id, "owner_decision_template_option_type", "expected object", option_path))
                    continue
                require_nonempty_string(findings, case, option.get("id"), "owner_decision_template_option_id", f"{option_path}.id")
        fields = item.get("required_update_fields")
        if not isinstance(fields, list):
            findings.append(Finding("ERROR", case.id, "owner_decision_template_required_fields", "expected list", f"{item_path}.required_update_fields"))
        else:
            for required in ("status", "selected_option", "decided_by", "decided_at"):
                if required not in fields:
                    findings.append(Finding("ERROR", case.id, f"owner_decision_template_missing_{required}", f"expected {required}", f"{item_path}.required_update_fields"))
        patch = item.get("state_patch_template")
        if not isinstance(patch, dict):
            findings.append(Finding("ERROR", case.id, "owner_decision_template_item_patch", "expected object", f"{item_path}.state_patch_template"))
        else:
            for key in ("status", "selected_option", "decided_by", "decided_at"):
                require_nonempty_string(findings, case, patch.get(key), f"owner_decision_template_patch_{key}", f"{item_path}.state_patch_template.{key}")
        if isinstance(decision, str) and decision and decision not in patch_decisions:
            findings.append(Finding("ERROR", case.id, "owner_decision_template_patch_missing_decision", "expected top-level patch entry", f"$.state_patch_template.decisions.{decision}"))
        if not isinstance(item.get("required_artifacts"), list):
            findings.append(Finding("ERROR", case.id, "owner_decision_template_required_artifacts", "expected list", f"{item_path}.required_artifacts"))
        if not isinstance(item.get("required_when"), dict):
            findings.append(Finding("ERROR", case.id, "owner_decision_template_required_when", "expected object", f"{item_path}.required_when"))
        validate_owner_record_gate_effect(findings, case, item.get("record_gate_effect"), item_path, "owner_decision_template")
        validate_gate_unblock_requirements(findings, case, item, item_path, "owner_decision_template")
        require_nonempty_string(findings, case, item.get("gate_note"), "owner_decision_template_gate_note", f"{item_path}.gate_note")
    return findings


def validate_release_owner_decision_record_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "owner_decision_record_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "release_owner_decision_record":
        findings.append(Finding("ERROR", case.id, "owner_decision_record_kind", "expected kind=release_owner_decision_record", "$.kind"))
    if data.get("dry_run") is not True:
        findings.append(Finding("ERROR", case.id, "owner_decision_record_dry_run", "expected dry_run=true", "$.dry_run"))
    if data.get("action") != "dry_run":
        findings.append(Finding("ERROR", case.id, "owner_decision_record_action", "expected action=dry_run", "$.action"))
    if data.get("valid") is not True:
        findings.append(Finding("ERROR", case.id, "owner_decision_record_valid", "expected valid=true", "$.valid"))
    require_nonempty_string(findings, case, data.get("decision_state_file"), "owner_decision_record_state_file", "$.decision_state_file")
    require_nonempty_string(findings, case, data.get("decision"), "owner_decision_record_decision", "$.decision")
    require_nonempty_string(findings, case, data.get("selected_option"), "owner_decision_record_selected_option", "$.selected_option")
    allowed_options = data.get("allowed_options")
    if not isinstance(allowed_options, list) or not allowed_options:
        findings.append(Finding("ERROR", case.id, "owner_decision_record_allowed_options", "expected non-empty list", "$.allowed_options"))
    elif data.get("selected_option") not in allowed_options:
        findings.append(Finding("ERROR", case.id, "owner_decision_record_selected_option_allowed", "selected option must be allowed", "$.selected_option"))
    findings_list = data.get("findings")
    if findings_list != []:
        findings.append(Finding("ERROR", case.id, "owner_decision_record_findings", "expected empty findings", "$.findings"))
    for key in ("record", "previous_record", "proposed_record"):
        if not isinstance(data.get(key), dict):
            findings.append(Finding("ERROR", case.id, f"owner_decision_record_{key}_type", "expected object", f"$.{key}"))
    proposed = data.get("proposed_record")
    if isinstance(proposed, dict):
        for key in ("status", "selected_option", "decided_by", "decided_at"):
            require_nonempty_string(findings, case, proposed.get(key), f"owner_decision_record_proposed_{key}", f"$.proposed_record.{key}")
    if not isinstance(data.get("required_artifacts"), list):
        findings.append(Finding("ERROR", case.id, "owner_decision_record_required_artifacts", "expected list", "$.required_artifacts"))
    if not isinstance(data.get("required_when"), dict):
        findings.append(Finding("ERROR", case.id, "owner_decision_record_required_when", "expected object", "$.required_when"))
    validate_owner_record_gate_effect(findings, case, data.get("record_gate_effect"), "$", "owner_decision_record")
    validate_gate_unblock_requirements(findings, case, data, "$", "owner_decision_record")
    require_nonempty_string(findings, case, data.get("gate_note"), "owner_decision_record_gate_note", "$.gate_note")
    return findings


def validate_release_gap_table_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "gap_table_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "release_gap_table":
        findings.append(Finding("ERROR", case.id, "gap_table_kind", "expected kind=release_gap_table", "$.kind"))
    summary = data.get("summary")
    table = data.get("remaining_gap_table")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "gap_table_summary_type", "expected object", "$.summary"))
        summary = {}
    if not isinstance(table, dict):
        findings.append(Finding("ERROR", case.id, "gap_table_table_type", "expected object", "$.remaining_gap_table"))
        return findings
    for key in ("owner_decisions", "code_remediation", "docs_publish_scope_governance", "deferred"):
        items = table.get(key)
        if not isinstance(items, list):
            findings.append(Finding("ERROR", case.id, f"gap_table_{key}_type", "expected list", f"$.remaining_gap_table.{key}"))
            continue
        if summary.get(key) != len(items):
            findings.append(Finding(
                "ERROR",
                case.id,
                f"gap_table_{key}_summary_mismatch",
                f"expected={len(items)}, actual={summary.get(key)}",
                f"$.summary.{key}",
            ))
        for index, item in enumerate(items):
            item_path = f"$.remaining_gap_table.{key}[{index}]"
            if not isinstance(item, dict):
                findings.append(Finding("ERROR", case.id, "gap_table_item_type", "expected object", item_path))
                continue
            require_nonempty_string(findings, case, item.get("issue_id"), "gap_table_issue_id", f"{item_path}.issue_id")
            require_nonempty_string(findings, case, item.get("check_id"), "gap_table_check_id", f"{item_path}.check_id")
            require_nonempty_string(findings, case, item.get("gap_type"), "gap_table_gap_type", f"{item_path}.gap_type")
            require_nonempty_string(findings, case, item.get("owner"), "gap_table_owner", f"{item_path}.owner")
            require_nonempty_string(findings, case, item.get("resolution"), "gap_table_resolution", f"{item_path}.resolution")
            validate_gap_client_portability_evidence(findings, case, item, item_path, "gap_table")
            if key == "owner_decisions":
                require_nonempty_string(findings, case, item.get("decision"), "gap_table_decision", f"{item_path}.decision")
                require_nonempty_string(findings, case, item.get("decision_doc"), "gap_table_decision_doc", f"{item_path}.decision_doc")
                require_nonempty_string(findings, case, item.get("record_status"), "gap_table_record_status", f"{item_path}.record_status")
                validate_publish_scope_gap_breakdown(findings, case, item, item_path, "gap_table")
                validate_owner_gap_record_commands(findings, case, item, item_path, "gap_table")
                validate_owner_record_gate_effect(findings, case, item.get("record_gate_effect"), item_path, "gap_table")
                validate_gate_unblock_requirements(findings, case, item, item_path, "gap_table")
                if not isinstance(item.get("required_artifacts"), list):
                    findings.append(Finding("ERROR", case.id, "gap_table_required_artifacts", "expected list", f"{item_path}.required_artifacts"))
                if not isinstance(item.get("required_when"), dict):
                    findings.append(Finding("ERROR", case.id, "gap_table_required_when", "expected object", f"{item_path}.required_when"))
    expected_by_type: dict[str, int] = {}
    for key in ("owner_decisions", "code_remediation", "docs_publish_scope_governance"):
        items = table.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            gap_type = str(item.get("gap_type", "unknown") or "unknown")
            expected_by_type[gap_type] = expected_by_type.get(gap_type, 0) + 1
    open_by_gap_type = summary.get("open_by_gap_type")
    if not isinstance(open_by_gap_type, dict):
        findings.append(Finding("ERROR", case.id, "gap_table_gap_type_summary_missing", "expected object", "$.summary.open_by_gap_type"))
    elif normalize_int_map(open_by_gap_type) != expected_by_type:
        findings.append(Finding(
            "ERROR",
            case.id,
            "gap_table_gap_type_summary_mismatch",
            f"expected={expected_by_type}, actual={open_by_gap_type}",
            "$.summary.open_by_gap_type",
        ))
    return findings


def validate_publish_scope_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "publish_scope_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "publish_scope_check":
        findings.append(Finding("ERROR", case.id, "publish_scope_kind", "expected kind=publish_scope_check", "$.kind"))
    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "publish_scope_summary_type", "expected object", "$.summary"))
        return findings

    def summary_int(key: str) -> int:
        value = summary.get(key)
        if not isinstance(value, int) or value < 0:
            findings.append(Finding("ERROR", case.id, f"publish_scope_summary_{key}_type", "expected non-negative integer", f"$.summary.{key}"))
            return 0
        return value

    tracked_count = summary_int("tracked_files")
    external_count = summary_int("external_scope_files")
    private_count = summary_int("private_tracked_paths")
    unclassified_count = summary_int("unclassified_tracked_paths")
    manifest_finding_count = summary_int("manifest_findings")
    git_error = summary.get("git_error")
    if not isinstance(git_error, bool):
        findings.append(Finding("ERROR", case.id, "publish_scope_git_error_type", "expected boolean", "$.summary.git_error"))

    manifest_findings = data.get("manifest_findings")
    private_paths = data.get("private_tracked_paths")
    unclassified_paths = data.get("unclassified_tracked_paths")
    private_summary = data.get("private_tracked_summary")
    unclassified_summary = data.get("unclassified_tracked_summary")
    scope = data.get("scope")

    list_fields = {
        "manifest_findings": manifest_findings,
        "private_tracked_paths": private_paths,
        "unclassified_tracked_paths": unclassified_paths,
    }
    for key, rows in list_fields.items():
        if not isinstance(rows, list):
            findings.append(Finding("ERROR", case.id, f"publish_scope_{key}_type", "expected list", f"$.{key}"))

    if isinstance(manifest_findings, list) and manifest_finding_count != len(manifest_findings):
        findings.append(Finding(
            "ERROR",
            case.id,
            "publish_scope_manifest_findings_count_mismatch",
            f"summary={manifest_finding_count}, rows={len(manifest_findings)}",
            "$.manifest_findings",
        ))

    if not git_error and tracked_count != external_count + private_count + unclassified_count:
        findings.append(Finding(
            "ERROR",
            case.id,
            "publish_scope_tracked_count_mismatch",
            f"tracked={tracked_count}, external={external_count}, private={private_count}, unclassified={unclassified_count}",
            "$.summary",
        ))

    if isinstance(private_paths, list):
        if len(private_paths) > private_count:
            findings.append(Finding("ERROR", case.id, "publish_scope_private_rows_exceed_summary", f"summary={private_count}, rows={len(private_paths)}", "$.private_tracked_paths"))
        for index, item in enumerate(private_paths):
            item_path = f"$.private_tracked_paths[{index}]"
            if not isinstance(item, dict):
                findings.append(Finding("ERROR", case.id, "publish_scope_private_path_item_type", "expected object", item_path))
                continue
            require_nonempty_string(findings, case, item.get("path"), "publish_scope_private_path", f"{item_path}.path")
            if item.get("match") not in ("file", "prefix"):
                findings.append(Finding("ERROR", case.id, "publish_scope_private_match", "expected file|prefix", f"{item_path}.match"))
            require_nonempty_string(findings, case, item.get("reason"), "publish_scope_private_reason", f"{item_path}.reason")

    if isinstance(unclassified_paths, list):
        if len(unclassified_paths) > unclassified_count:
            findings.append(Finding("ERROR", case.id, "publish_scope_unclassified_rows_exceed_summary", f"summary={unclassified_count}, rows={len(unclassified_paths)}", "$.unclassified_tracked_paths"))
        for index, item in enumerate(unclassified_paths):
            if not isinstance(item, str) or not item:
                findings.append(Finding("ERROR", case.id, "publish_scope_unclassified_path_type", "expected non-empty string", f"$.unclassified_tracked_paths[{index}]"))

    def validate_summary_rows(
        section: Any,
        expected_total: int,
        section_name: str,
        required_keys: tuple[str, ...],
    ) -> None:
        if not isinstance(section, dict):
            findings.append(Finding("ERROR", case.id, f"publish_scope_{section_name}_type", "expected object", f"$.{section_name}"))
            return
        for key in required_keys:
            rows = section.get(key)
            path = f"$.{section_name}.{key}"
            if not isinstance(rows, list):
                findings.append(Finding("ERROR", case.id, f"publish_scope_{section_name}_{key}_type", "expected list", path))
                continue
            total = 0
            for index, row in enumerate(rows):
                row_path = f"{path}[{index}]"
                if not isinstance(row, dict):
                    findings.append(Finding("ERROR", case.id, f"publish_scope_{section_name}_{key}_row_type", "expected object", row_path))
                    continue
                require_nonempty_string(findings, case, row.get("key"), f"publish_scope_{section_name}_{key}_key", f"{row_path}.key")
                count = row.get("count")
                if not isinstance(count, int) or count <= 0:
                    findings.append(Finding("ERROR", case.id, f"publish_scope_{section_name}_{key}_count", "expected positive integer", f"{row_path}.count"))
                    continue
                total += count
            if total != expected_total:
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    f"publish_scope_{section_name}_{key}_total_mismatch",
                    f"summary={expected_total}, rows={total}",
                    path,
                ))

    validate_summary_rows(
        private_summary,
        private_count,
        "private_tracked_summary",
        ("by_reason", "by_path_group", "by_match"),
    )
    validate_summary_rows(
        unclassified_summary,
        unclassified_count,
        "unclassified_tracked_summary",
        ("by_path_group",),
    )

    if not isinstance(scope, dict):
        findings.append(Finding("ERROR", case.id, "publish_scope_scope_type", "expected object", "$.scope"))
    else:
        for key in ("external_files", "external_prefixes", "private_files", "private_prefixes"):
            rows = scope.get(key)
            path = f"$.scope.{key}"
            if not isinstance(rows, list):
                findings.append(Finding("ERROR", case.id, f"publish_scope_scope_{key}_type", "expected list", path))
                continue
            if rows != sorted(rows) or len(rows) != len(set(rows)):
                findings.append(Finding("ERROR", case.id, f"publish_scope_scope_{key}_sorted_unique", "expected sorted unique list", path))

    if (manifest_finding_count or git_error or private_count) and data.get("verdict") != "blocked":
        findings.append(Finding(
            "ERROR",
            case.id,
            "publish_scope_verdict_mismatch",
            f"expected=blocked, actual={data.get('verdict')}",
            "$.verdict",
        ))

    decision_plan = data.get("decision_plan")
    if private_count or unclassified_count:
        if not isinstance(decision_plan, dict) or not decision_plan:
            findings.append(Finding("ERROR", case.id, "publish_scope_decision_plan_missing", "expected decision plan for blockers", "$.decision_plan"))
            return findings
        if decision_plan.get("decision") != "publish_scope_boundary":
            findings.append(Finding("ERROR", case.id, "publish_scope_decision", "expected publish_scope_boundary", "$.decision_plan.decision"))
        require_nonempty_string(findings, case, decision_plan.get("owner"), "publish_scope_decision_owner", "$.decision_plan.owner")
        required_when = decision_plan.get("required_when")
        if not isinstance(required_when, dict):
            findings.append(Finding("ERROR", case.id, "publish_scope_required_when_type", "expected object", "$.decision_plan.required_when"))
        else:
            expected_required_when = {
                "private_tracked_paths": private_count,
                "unclassified_tracked_paths": unclassified_count,
            }
            if required_when != expected_required_when:
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    "publish_scope_required_when_mismatch",
                    f"expected={expected_required_when}, actual={required_when}",
                    "$.decision_plan.required_when",
                ))
        options = decision_plan.get("options")
        if not isinstance(options, list) or len(options) < 4:
            findings.append(Finding("ERROR", case.id, "publish_scope_decision_options", "expected at least four options", "$.decision_plan.options"))
        else:
            option_ids = {
                str(option.get("id"))
                for option in options
                if isinstance(option, dict)
            }
            required_options = {
                "split_clean_source_repository",
                "move_private_data",
                "convert_selected_fixtures",
                "keep_private_maturity_audit",
            }
            if not required_options.issubset(option_ids):
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    "publish_scope_decision_option_ids",
                    f"missing={sorted(required_options - option_ids)}",
                    "$.decision_plan.options",
                ))
    elif decision_plan not in ({}, None):
        findings.append(Finding("WARNING", case.id, "publish_scope_unexpected_decision_plan", "decision_plan is expected only when blockers exist", "$.decision_plan"))
    return findings


def validate_export_source_scope_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "export_plan_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "source_export_scope_plan":
        findings.append(Finding("ERROR", case.id, "export_plan_kind", "expected kind=source_export_scope_plan", "$.kind"))

    summary = data.get("summary")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "export_plan_summary_type", "expected object", "$.summary"))
        return findings

    def summary_int(key: str) -> int:
        value = summary.get(key)
        if not isinstance(value, int) or value < 0:
            findings.append(Finding("ERROR", case.id, f"export_plan_summary_{key}_type", "expected non-negative integer", f"$.summary.{key}"))
            return 0
        return value

    tracked_count = summary_int("tracked_files")
    worktree_count = summary_int("worktree_files")
    included_count = summary_int("export_included_paths")
    untracked_count = summary_int("untracked_included_paths")
    excluded_private_count = summary_int("excluded_private_paths")
    unclassified_count = summary_int("unclassified_paths")
    missing_external_count = summary_int("missing_external_files")
    manifest_finding_count = summary_int("manifest_findings")
    git_error_count = summary_int("git_errors")

    list_fields = {
        "included_paths": data.get("included_paths"),
        "untracked_included_paths": data.get("untracked_included_paths"),
        "excluded_private_paths": data.get("excluded_private_paths"),
        "unclassified_paths": data.get("unclassified_paths"),
        "missing_external_files": data.get("missing_external_files"),
        "manifest_findings": data.get("manifest_findings"),
        "git_errors": data.get("git_errors"),
    }
    for key, rows in list_fields.items():
        if not isinstance(rows, list):
            findings.append(Finding("ERROR", case.id, f"export_plan_{key}_type", "expected list", f"$.{key}"))

    if any(not isinstance(rows, list) for rows in list_fields.values()):
        return findings

    included_rows: list[Any] = list_fields["included_paths"]
    untracked_rows: list[Any] = list_fields["untracked_included_paths"]
    excluded_rows: list[Any] = list_fields["excluded_private_paths"]
    unclassified_rows: list[Any] = list_fields["unclassified_paths"]
    missing_rows: list[Any] = list_fields["missing_external_files"]
    manifest_finding_rows: list[Any] = list_fields["manifest_findings"]
    git_error_rows: list[Any] = list_fields["git_errors"]

    if len(manifest_finding_rows) != manifest_finding_count:
        findings.append(Finding("ERROR", case.id, "export_plan_manifest_findings_count_mismatch", f"summary={manifest_finding_count}, rows={len(manifest_finding_rows)}", "$.manifest_findings"))
    if len(git_error_rows) != git_error_count:
        findings.append(Finding("ERROR", case.id, "export_plan_git_errors_count_mismatch", f"summary={git_error_count}, rows={len(git_error_rows)}", "$.git_errors"))
    if len(included_rows) > included_count:
        findings.append(Finding("ERROR", case.id, "export_plan_included_rows_exceed_summary", f"summary={included_count}, rows={len(included_rows)}", "$.included_paths"))
    if len(untracked_rows) > untracked_count:
        findings.append(Finding("ERROR", case.id, "export_plan_untracked_rows_exceed_summary", f"summary={untracked_count}, rows={len(untracked_rows)}", "$.untracked_included_paths"))
    if len(excluded_rows) > excluded_private_count:
        findings.append(Finding("ERROR", case.id, "export_plan_excluded_rows_exceed_summary", f"summary={excluded_private_count}, rows={len(excluded_rows)}", "$.excluded_private_paths"))
    if len(unclassified_rows) > unclassified_count:
        findings.append(Finding("ERROR", case.id, "export_plan_unclassified_rows_exceed_summary", f"summary={unclassified_count}, rows={len(unclassified_rows)}", "$.unclassified_paths"))
    if len(missing_rows) > missing_external_count:
        findings.append(Finding("ERROR", case.id, "export_plan_missing_rows_exceed_summary", f"summary={missing_external_count}, rows={len(missing_rows)}", "$.missing_external_files"))

    if not git_error_count and worktree_count != included_count + excluded_private_count + unclassified_count:
        findings.append(Finding(
            "ERROR",
            case.id,
            "export_plan_worktree_count_mismatch",
            f"worktree={worktree_count}, included={included_count}, excluded_private={excluded_private_count}, unclassified={unclassified_count}",
            "$.summary",
        ))
    if tracked_count > worktree_count:
        findings.append(Finding("ERROR", case.id, "export_plan_tracked_exceeds_worktree", f"tracked={tracked_count}, worktree={worktree_count}", "$.summary.tracked_files"))

    def validate_classified_rows(rows: list[Any], field_name: str, require_untracked: bool = False) -> None:
        for index, item in enumerate(rows):
            item_path = f"$.{field_name}[{index}]"
            if not isinstance(item, dict):
                findings.append(Finding("ERROR", case.id, f"export_plan_{field_name}_item_type", "expected object", item_path))
                continue
            require_nonempty_string(findings, case, item.get("path"), f"export_plan_{field_name}_path", f"{item_path}.path")
            if item.get("match") not in ("file", "prefix"):
                findings.append(Finding("ERROR", case.id, f"export_plan_{field_name}_match", "expected file|prefix", f"{item_path}.match"))
            require_nonempty_string(findings, case, item.get("reason"), f"export_plan_{field_name}_reason", f"{item_path}.reason")
            git_state = item.get("git_state")
            if git_state not in ("tracked", "untracked"):
                findings.append(Finding("ERROR", case.id, f"export_plan_{field_name}_git_state", "expected tracked|untracked", f"{item_path}.git_state"))
            if require_untracked and git_state != "untracked":
                findings.append(Finding("ERROR", case.id, f"export_plan_{field_name}_not_untracked", "expected git_state=untracked", f"{item_path}.git_state"))

    validate_classified_rows(included_rows, "included_paths")
    validate_classified_rows(untracked_rows, "untracked_included_paths", require_untracked=True)
    validate_classified_rows(excluded_rows, "excluded_private_paths")

    for field_name, rows in (
        ("unclassified_paths", unclassified_rows),
        ("missing_external_files", missing_rows),
    ):
        for index, item in enumerate(rows):
            if not isinstance(item, str) or not item:
                findings.append(Finding("ERROR", case.id, f"export_plan_{field_name}_item_type", "expected non-empty string", f"$.{field_name}[{index}]"))

    expected_verdict = "invalid" if (
        manifest_finding_count or git_error_count or missing_external_count or unclassified_count
    ) else ("ready_with_warnings" if untracked_count else "ready")
    if data.get("verdict") != expected_verdict:
        findings.append(Finding(
            "ERROR",
            case.id,
            "export_plan_verdict_mismatch",
            f"expected={expected_verdict}, actual={data.get('verdict')}",
            "$.verdict",
        ))

    untracked_summary = data.get("untracked_included_summary")
    if not isinstance(untracked_summary, dict):
        findings.append(Finding("ERROR", case.id, "export_plan_untracked_summary_type", "expected object", "$.untracked_included_summary"))
    else:
        grouped_specs = {
            "by_reason": ("reason", "paths"),
            "by_path_group": ("group", "paths"),
            "by_match": ("match", ""),
        }
        for key, (name_field, paths_field) in grouped_specs.items():
            rows = untracked_summary.get(key)
            path = f"$.untracked_included_summary.{key}"
            if not isinstance(rows, list):
                findings.append(Finding("ERROR", case.id, f"export_plan_untracked_summary_{key}_type", "expected list", path))
                continue
            total = 0
            for index, row in enumerate(rows):
                row_path = f"{path}[{index}]"
                if not isinstance(row, dict):
                    findings.append(Finding("ERROR", case.id, f"export_plan_untracked_summary_{key}_row_type", "expected object", row_path))
                    continue
                require_nonempty_string(findings, case, row.get(name_field), f"export_plan_untracked_summary_{key}_name", f"{row_path}.{name_field}")
                count = row.get("count")
                if not isinstance(count, int) or count <= 0:
                    findings.append(Finding("ERROR", case.id, f"export_plan_untracked_summary_{key}_count", "expected positive integer", f"{row_path}.count"))
                    continue
                total += count
                if paths_field:
                    paths = row.get(paths_field)
                    if not isinstance(paths, list) or len(paths) > count:
                        findings.append(Finding("ERROR", case.id, f"export_plan_untracked_summary_{key}_paths", "expected paths list no longer than count", f"{row_path}.{paths_field}"))
            if total != untracked_count:
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    f"export_plan_untracked_summary_{key}_total_mismatch",
                    f"summary={untracked_count}, rows={total}",
                    path,
                ))

    tracking_plan = data.get("tracking_plan")
    if not isinstance(tracking_plan, dict):
        findings.append(Finding("ERROR", case.id, "export_plan_tracking_plan_missing", "expected object", "$.tracking_plan"))
        return findings

    paths = tracking_plan.get("paths")
    if not isinstance(paths, list):
        findings.append(Finding("ERROR", case.id, "export_plan_tracking_paths_type", "expected list", "$.tracking_plan.paths"))
        paths = []
    elif not all(isinstance(path, str) and path for path in paths):
        findings.append(Finding("ERROR", case.id, "export_plan_tracking_paths_items", "expected non-empty string paths", "$.tracking_plan.paths"))
    path_count = tracking_plan.get("path_count")
    if path_count != len(paths) or path_count != untracked_count:
        findings.append(Finding(
            "ERROR",
            case.id,
            "export_plan_tracking_count_mismatch",
            f"summary={untracked_count}, path_count={path_count}, paths={len(paths)}",
            "$.tracking_plan",
        ))

    if tracking_plan.get("action") != "git_add_external_untracked":
        findings.append(Finding("ERROR", case.id, "export_plan_tracking_action", "expected git_add_external_untracked", "$.tracking_plan.action"))
    expected_ready = bool(paths) and not unclassified_count and not missing_external_count
    if tracking_plan.get("ready") != expected_ready:
        findings.append(Finding("ERROR", case.id, "export_plan_tracking_ready_mismatch", f"expected={expected_ready}, actual={tracking_plan.get('ready')}", "$.tracking_plan.ready"))

    command = tracking_plan.get("command")
    expected_command = ["git", "add", "--", *paths] if paths else []
    if command != expected_command:
        findings.append(Finding(
            "ERROR",
            case.id,
            "export_plan_tracking_command_invalid",
            "expected ['git', 'add', '--', *paths]",
            "$.tracking_plan.command",
        ))

    safety = tracking_plan.get("safety")
    if not isinstance(safety, dict):
        findings.append(Finding("ERROR", case.id, "export_plan_tracking_safety_missing", "expected object", "$.tracking_plan.safety"))
    else:
        expected_safety = {
            "excluded_private_paths": excluded_private_count,
            "unclassified_paths": unclassified_count,
            "missing_external_files": missing_external_count,
        }
        if safety != expected_safety:
            findings.append(Finding(
                "ERROR",
                case.id,
                "export_plan_tracking_safety_mismatch",
                f"expected={expected_safety}, actual={safety}",
                "$.tracking_plan.safety",
            ))
    return findings


def validate_external_source_safety_contract(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, dict):
        findings.append(Finding("ERROR", case.id, "external_safety_root_type", "expected object root", "$"))
        return findings
    if data.get("kind") != "external_source_safety_scan":
        findings.append(Finding("ERROR", case.id, "external_safety_kind", "expected kind=external_source_safety_scan", "$.kind"))

    summary = data.get("summary")
    by_code = data.get("by_code")
    top_paths = data.get("top_paths")
    remediation_groups = data.get("remediation_groups")
    visible_findings = data.get("findings")
    skipped = data.get("skipped")
    if not isinstance(summary, dict):
        findings.append(Finding("ERROR", case.id, "external_safety_summary_type", "expected object", "$.summary"))
        return findings

    aggregate_lists = {
        "by_code": by_code,
        "top_paths": top_paths,
        "remediation_groups": remediation_groups,
        "findings": visible_findings,
        "skipped": skipped,
    }
    for key, rows in aggregate_lists.items():
        if not isinstance(rows, list):
            findings.append(Finding("ERROR", case.id, f"external_safety_{key}_type", "expected list", f"$.{key}"))

    if any(not isinstance(rows, list) for rows in aggregate_lists.values()):
        return findings

    by_code_rows: list[Any] = by_code
    top_path_rows: list[Any] = top_paths
    remediation_group_rows: list[Any] = remediation_groups
    visible_finding_rows: list[Any] = visible_findings
    skipped_rows: list[Any] = skipped

    def summary_int(key: str) -> int:
        value = summary.get(key)
        if not isinstance(value, int) or value < 0:
            findings.append(Finding("ERROR", case.id, f"external_safety_summary_{key}_type", "expected non-negative integer", f"$.summary.{key}"))
            return 0
        return value

    planned = summary_int("planned_external_files")
    scanned = summary_int("scanned_files")
    skipped_count = summary_int("skipped_files")
    blockers = summary_int("blockers")
    warnings = summary_int("warnings")
    total_findings = blockers + warnings

    if planned != scanned + skipped_count:
        findings.append(Finding(
            "ERROR",
            case.id,
            "external_safety_scan_count_mismatch",
            f"planned={planned}, scanned={scanned}, skipped={skipped_count}",
            "$.summary",
        ))

    if len(skipped_rows) > skipped_count:
        findings.append(Finding(
            "ERROR",
            case.id,
            "external_safety_skipped_count_mismatch",
            f"summary={skipped_count}, rows={len(skipped_rows)}",
            "$.skipped",
        ))

    expected_verdict = "blocked" if blockers else ("needs_review" if warnings else "ok")
    if data.get("verdict") != expected_verdict:
        findings.append(Finding(
            "ERROR",
            case.id,
            "external_safety_verdict_mismatch",
            f"expected={expected_verdict}, actual={data.get('verdict')}",
            "$.verdict",
        ))

    visible_severities: dict[str, int] = {}
    for index, item in enumerate(visible_finding_rows):
        path = f"$.findings[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "external_safety_finding_type", "expected object", path))
            continue
        severity = item.get("severity")
        if severity not in ("blocker", "warning"):
            findings.append(Finding("ERROR", case.id, "external_safety_finding_severity", "expected blocker|warning", f"{path}.severity"))
            continue
        visible_severities[severity] = visible_severities.get(severity, 0) + 1
        require_nonempty_string(findings, case, item.get("path"), "external_safety_finding_path", f"{path}.path")
        require_nonempty_string(findings, case, item.get("code"), "external_safety_finding_code", f"{path}.code")

    if visible_severities.get("blocker", 0) > blockers:
        findings.append(Finding("ERROR", case.id, "external_safety_visible_blockers_exceed_summary", "visible blocker rows exceed summary", "$.findings"))
    if visible_severities.get("warning", 0) > warnings:
        findings.append(Finding("ERROR", case.id, "external_safety_visible_warnings_exceed_summary", "visible warning rows exceed summary", "$.findings"))
    if len(visible_finding_rows) == total_findings:
        if visible_severities.get("blocker", 0) != blockers:
            findings.append(Finding("ERROR", case.id, "external_safety_visible_blockers_mismatch", f"summary={blockers}, rows={visible_severities.get('blocker', 0)}", "$.findings"))
        if visible_severities.get("warning", 0) != warnings:
            findings.append(Finding("ERROR", case.id, "external_safety_visible_warnings_mismatch", f"summary={warnings}, rows={visible_severities.get('warning', 0)}", "$.findings"))

    by_code_total = 0
    by_code_severities: dict[str, int] = {}
    for index, item in enumerate(by_code_rows):
        path = f"$.by_code[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "external_safety_by_code_item_type", "expected object", path))
            continue
        require_nonempty_string(findings, case, item.get("code"), "external_safety_by_code_code", f"{path}.code")
        severity = item.get("severity")
        if severity not in ("blocker", "warning"):
            findings.append(Finding("ERROR", case.id, "external_safety_by_code_severity", "expected blocker|warning", f"{path}.severity"))
        count = item.get("count")
        if not isinstance(count, int) or count <= 0:
            findings.append(Finding("ERROR", case.id, "external_safety_by_code_count", "expected positive integer", f"{path}.count"))
            continue
        by_code_total += count
        if isinstance(severity, str):
            by_code_severities[severity] = by_code_severities.get(severity, 0) + count

    if by_code_total != total_findings:
        findings.append(Finding("ERROR", case.id, "external_safety_by_code_total_mismatch", f"summary={total_findings}, by_code={by_code_total}", "$.by_code"))
    if by_code_severities.get("blocker", 0) != blockers:
        findings.append(Finding("ERROR", case.id, "external_safety_by_code_blockers_mismatch", f"summary={blockers}, by_code={by_code_severities.get('blocker', 0)}", "$.by_code"))
    if by_code_severities.get("warning", 0) != warnings:
        findings.append(Finding("ERROR", case.id, "external_safety_by_code_warnings_mismatch", f"summary={warnings}, by_code={by_code_severities.get('warning', 0)}", "$.by_code"))

    top_path_total = 0
    for index, item in enumerate(top_path_rows):
        path = f"$.top_paths[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "external_safety_top_path_item_type", "expected object", path))
            continue
        require_nonempty_string(findings, case, item.get("path"), "external_safety_top_path_path", f"{path}.path")
        path_findings = item.get("findings")
        path_blockers = item.get("blockers")
        path_warnings = item.get("warnings")
        if not all(isinstance(value, int) and value >= 0 for value in (path_findings, path_blockers, path_warnings)):
            findings.append(Finding("ERROR", case.id, "external_safety_top_path_counts", "expected non-negative integer counts", path))
            continue
        if path_findings != path_blockers + path_warnings:
            findings.append(Finding("ERROR", case.id, "external_safety_top_path_count_mismatch", f"findings={path_findings}, blockers={path_blockers}, warnings={path_warnings}", path))
        codes_rows = item.get("codes")
        if not isinstance(codes_rows, list):
            findings.append(Finding("ERROR", case.id, "external_safety_top_path_codes_type", "expected list", f"{path}.codes"))
        else:
            codes_total = sum(row.get("count", 0) for row in codes_rows if isinstance(row, dict) and isinstance(row.get("count"), int))
            if codes_total != path_findings:
                findings.append(Finding("ERROR", case.id, "external_safety_top_path_codes_total", f"findings={path_findings}, codes={codes_total}", f"{path}.codes"))
        first_locations = item.get("first_locations")
        if not isinstance(first_locations, list) or len(first_locations) > min(3, path_findings):
            findings.append(Finding("ERROR", case.id, "external_safety_top_path_locations", "expected up to first three locations", f"{path}.first_locations"))
        top_path_total += path_findings
    if top_path_total > total_findings:
        findings.append(Finding("ERROR", case.id, "external_safety_top_paths_exceed_summary", f"summary={total_findings}, top_paths={top_path_total}", "$.top_paths"))

    group_total = 0
    group_names: set[str] = set()
    for index, item in enumerate(remediation_group_rows):
        path = f"$.remediation_groups[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("ERROR", case.id, "external_safety_group_item_type", "expected object", path))
            continue
        group = item.get("group")
        require_nonempty_string(findings, case, group, "external_safety_group_name", f"{path}.group")
        if isinstance(group, str):
            group_names.add(group)
        group_findings = item.get("findings")
        group_blockers = item.get("blockers")
        group_warnings = item.get("warnings")
        if not all(isinstance(value, int) and value >= 0 for value in (group_findings, group_blockers, group_warnings)):
            findings.append(Finding("ERROR", case.id, "external_safety_group_counts", "expected non-negative integer counts", path))
            continue
        if group_findings != group_blockers + group_warnings:
            findings.append(Finding("ERROR", case.id, "external_safety_group_count_mismatch", f"findings={group_findings}, blockers={group_blockers}, warnings={group_warnings}", path))
        paths = item.get("paths")
        path_count = item.get("path_count")
        if not isinstance(paths, list) or not isinstance(path_count, int) or path_count < len(paths):
            findings.append(Finding("ERROR", case.id, "external_safety_group_path_count", "expected path_count >= len(paths)", path))
        codes_rows = item.get("codes")
        if not isinstance(codes_rows, list):
            findings.append(Finding("ERROR", case.id, "external_safety_group_codes_type", "expected list", f"{path}.codes"))
        else:
            codes_total = sum(row.get("count", 0) for row in codes_rows if isinstance(row, dict) and isinstance(row.get("count"), int))
            if codes_total != group_findings:
                findings.append(Finding("ERROR", case.id, "external_safety_group_codes_total", f"findings={group_findings}, codes={codes_total}", f"{path}.codes"))
        group_total += group_findings

    if group_total != total_findings:
        findings.append(Finding("ERROR", case.id, "external_safety_group_total_mismatch", f"summary={total_findings}, groups={group_total}", "$.remediation_groups"))

    if total_findings == 0 and (by_code_rows or top_path_rows or remediation_group_rows or visible_finding_rows):
        findings.append(Finding("ERROR", case.id, "external_safety_empty_aggregates_mismatch", "expected empty finding aggregates when summary findings are zero", "$"))

    group_names = {
        str(item.get("group"))
        for item in remediation_group_rows
        if isinstance(item, dict)
    }
    policy_plan = data.get("policy_plan")
    if blockers == 0 and warnings > 0 and group_names == {"public_history"}:
        if not isinstance(policy_plan, dict) or not policy_plan:
            findings.append(Finding("ERROR", case.id, "external_safety_policy_plan_missing", "expected public history policy plan", "$.policy_plan"))
            return findings
        if policy_plan.get("decision") != "public_history_policy":
            findings.append(Finding("ERROR", case.id, "external_safety_policy_decision", "expected public_history_policy", "$.policy_plan.decision"))
        require_nonempty_string(findings, case, policy_plan.get("owner"), "external_safety_policy_owner", "$.policy_plan.owner")
        options = policy_plan.get("options")
        if not isinstance(options, list) or len(options) < 3:
            findings.append(Finding("ERROR", case.id, "external_safety_policy_options", "expected at least three options", "$.policy_plan.options"))
        else:
            option_ids = {
                str(option.get("id"))
                for option in options
                if isinstance(option, dict)
            }
            required = {"sanitize_changelog", "generate_public_changelog", "exclude_public_history"}
            if not required.issubset(option_ids):
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    "external_safety_policy_option_ids",
                    f"missing={sorted(required - option_ids)}",
                    "$.policy_plan.options",
                ))
    elif policy_plan not in ({}, None):
        findings.append(Finding(
            "WARNING",
            case.id,
            "external_safety_unexpected_policy_plan",
            "policy_plan is expected only for public_history-only warnings",
            "$.policy_plan",
        ))
    return findings


def normalize_int_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = int(raw)
        except (TypeError, ValueError):
            continue
    return out


def validate_json_payload(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, (dict, list)):
        findings.append(Finding("ERROR", case.id, "json_root_type", f"root is {type(data).__name__}"))
        return findings

    for path, key, value in walk_json(data):
        if isinstance(value, str):
            if len(value) > 8000:
                findings.append(Finding("WARNING", case.id, "large_string_field", f"{len(value)} chars", path))
            if looks_like_console_transcript(value):
                findings.append(Finding(
                    "WARNING",
                    case.id,
                    "console_transcript_in_json",
                    "machine JSON contains human console transcript",
                    path,
                ))
            if key in {"stdout", "stderr"} and value.strip() and not case.allow_raw_output_keys:
                findings.append(Finding(
                    "WARNING",
                    case.id,
                    "raw_output_field",
                    f"non-empty {key} should be omitted from successful machine JSON unless requested",
                    path,
                ))
    return findings


def walk_json(value: Any, path: str = "$", key: str = ""):
    yield path, key, value
    if isinstance(value, dict):
        for child_key, child in value.items():
            child_path = f"{path}.{child_key}"
            yield from walk_json(child, child_path, str(child_key))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk_json(child, f"{path}[{idx}]", key)


def looks_like_console_transcript(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    markers = (
        "✅", "❌", "⚠", "====", "----", "[1/", "[2/", "扫描", "当前环境", "模式:",
    )
    if any(marker in text for marker in markers):
        return True
    return bool(re.search(r"(?m)^\s*(PASS|ERROR|WARNING|WARN|INFO)[:\]]", text))


def render_text(results: list[dict]) -> str:
    lines = ["verify_output_contracts.py — script output contract check", ""]
    total_errors = 0
    total_warnings = 0
    for item in results:
        errors = [f for f in item["findings"] if f["level"] == "ERROR"]
        warnings = [f for f in item["findings"] if f["level"] == "WARNING"]
        total_errors += len(errors)
        total_warnings += len(warnings)
        status = "PASS" if not errors and not warnings else ("ERROR" if errors else "WARNING")
        lines.append(f"[{status}] {item['case_id']} exit={item['returncode']} duration={item['duration']:.2f}s")
        for finding in item["findings"]:
            suffix = f" @ {finding['path']}" if finding.get("path") else ""
            lines.append(f"  - {finding['level']} {finding['code']}{suffix}: {finding['message']}")
    lines.extend(["", f"summary: ERROR={total_errors} WARNING={total_warnings} CASES={len(results)}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="verify harness script output contracts")
    parser.add_argument("--json", action="store_true", help="emit machine-readable report")
    parser.add_argument("--include-mutating", action="store_true", help="also run mutating contract cases")
    parser.add_argument("--case", action="append", dest="case_ids", help="run only selected case id; repeatable")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    cases = default_cases()
    if args.include_mutating:
        cases.extend(mutating_cases())
    if args.case_ids:
        selected = set(args.case_ids)
        cases = [case for case in cases if case.id in selected]

    results = []
    for case in cases:
        proc, duration, error = run_case(case, args.timeout)
        _data, findings = validate_case(case, proc, error)
        results.append({
            "case_id": case.id,
            "cmd": case.cmd,
            "cwd": str(case.cwd),
            "mutating": case.mutating,
            "returncode": proc.returncode if proc else None,
            "duration": round(duration, 3),
            "findings": [asdict(finding) for finding in findings],
        })

    summary = {
        "ERROR": sum(1 for item in results for finding in item["findings"] if finding["level"] == "ERROR"),
        "WARNING": sum(1 for item in results for finding in item["findings"] if finding["level"] == "WARNING"),
        "CASES": len(results),
    }
    report = {
        "schema_version": 1,
        "kind": "output_contract_check",
        "summary": summary,
        "results": results,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(results), end="")
    return 1 if summary["ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
