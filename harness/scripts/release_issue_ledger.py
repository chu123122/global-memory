#!/usr/bin/env python3
"""Render OSS readiness checks as a machine-readable issue ledger."""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HARNESS_DIR, REPO_DIR  # noqa: E402

PY = sys.executable
OWNER_DECISIONS_PATH = HARNESS_DIR / "release_owner_decisions.json"

GAP_CLASSIFICATIONS: dict[str, dict[str, str]] = {
    "project_metadata": {
        "type": "owner_decision",
        "owner": "project_owner",
        "resolution": "Choose the project license and add LICENSE/LICENSE.md/COPYING.",
    },
    "publish_scope": {
        "type": "publish_scope_governance",
        "owner": "project_owner",
        "resolution": "Decide whether private tracked paths are split, excluded, redacted, or fixture-replaced.",
    },
    "source_export_plan": {
        "type": "code_remediation",
        "owner": "maintainer",
        "resolution": "Track external-scope files or narrow the publish-scope manifest.",
    },
    "external_source_safety": {
        "type": "docs_publish_scope_governance",
        "owner": "project_owner_or_maintainer",
        "resolution": "Sanitize public history or exclude/replace it in the source export.",
    },
    "client_portability": {
        "type": "verified_capability",
        "owner": "maintainer",
        "resolution": "Keep the external claim narrow as Claude Code plus Context Brief CLI, or add a second full-lifecycle stable client before claiming generic multi-client readiness.",
    },
    "legacy_health": {
        "type": "content_hygiene",
        "owner": "maintainer",
        "resolution": "Run only when cleaning personal memory content/frontmatter.",
    },
    "release_check_json": {
        "type": "code_remediation",
        "owner": "maintainer",
        "resolution": "Restore parseable JSON output from release-check.",
    },
}

DEFAULT_GAP_CLASSIFICATION = {
    "type": "verified_capability",
    "owner": "maintainer",
    "resolution": "Keep this check green.",
}
ALLOWED_OWNER_RECORD_STATUSES = {"undecided", "decided", "deferred"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def run_release_check(include_output_contracts: bool, include_legacy_health: bool) -> tuple[dict[str, Any], str]:
    cmd = [PY, str(HARNESS_DIR / "scripts" / "oss_readiness_check.py"), "--json"]
    if not include_output_contracts:
        cmd.append("--skip-output-contracts")
    if include_legacy_health:
        cmd.append("--include-legacy-health")
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )
    try:
        return json.loads(proc.stdout), ""
    except json.JSONDecodeError as exc:
        detail = proc.stderr.strip() or proc.stdout[:300]
        return {}, f"release-check JSON parse failed: {exc}; {detail}"


def gap_for_check(check_id: str) -> dict[str, str]:
    return dict(GAP_CLASSIFICATIONS.get(check_id, DEFAULT_GAP_CLASSIFICATION))


def load_owner_decision_state(path: Path = OWNER_DECISIONS_PATH) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    decisions = data.get("decisions")
    return decisions if isinstance(decisions, dict) else {}


def load_owner_decision_document(path: Path = OWNER_DECISIONS_PATH) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "schema_version": 1,
            "kind": "release_owner_decision_state",
            "description": "Owner-editable decision state for release blockers. This file records decisions; it does not make the gate green by itself.",
            "decisions": {},
        }
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_owner_decision_document(data: dict[str, Any], path: Path = OWNER_DECISIONS_PATH) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel_state_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_DIR).as_posix())
    except ValueError:
        return str(path)


def count_open_by_gap(issues: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        if issue.get("state") != "open":
            continue
        gap = issue.get("gap")
        if not isinstance(gap, dict):
            continue
        value = str(gap.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def compact_evidence(evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in evidence.items():
        if key in {"samples", "untracked_included_samples", "unclassified_samples"} and isinstance(value, list):
            out[f"{key}_count"] = len(value)
            out[key] = value[:5]
        elif key in {"findings", "missing_external_files", "unclassified_paths"} and isinstance(value, list):
            out[f"{key}_count"] = len(value)
            out[key] = value[:10]
        elif key in {"by_code", "top_paths", "remediation_groups"} and isinstance(value, list):
            out[f"{key}_count"] = len(value)
            out[key] = value[:10]
        elif key in {
            "summary",
            "readiness",
            "contracts",
            "clients",
            "claim_policy",
            "remediation_plan",
            "private_tracked_summary",
            "unclassified_tracked_summary",
            "untracked_included_summary",
            "tracking_plan",
            "policy_plan",
            "decision_plan",
            "tracked_private_paths",
            "unclassified_tracked_paths",
            "frontmatter_checked",
            "manifest",
            "decision_doc",
        }:
            out[key] = value
    return out


def issue_from_check(check: dict[str, Any], state: str) -> dict[str, Any]:
    check_id = str(check.get("id", "unknown"))
    status = str(check.get("status", "UNKNOWN"))
    if status == "BLOCKER":
        severity = "blocker"
    elif status == "WARNING":
        severity = "warning"
    else:
        severity = "info"
    return {
        "issue_id": f"oss-{check_id}",
        "source": "oss_readiness",
        "check_id": check_id,
        "state": state,
        "severity": severity,
        "title": check.get("title", check_id),
        "gap": gap_for_check(check_id),
        "summary": check.get("summary", ""),
        "next_action": check.get("next_action", ""),
        "command": check.get("command", []),
        "evidence": compact_evidence(check.get("evidence", {})),
    }


def issue_from_deferred(check: dict[str, Any]) -> dict[str, Any]:
    check_id = str(check.get("id", "unknown"))
    return {
        "issue_id": f"oss-{check_id}",
        "source": "oss_readiness",
        "check_id": check_id,
        "state": "deferred",
        "severity": "info",
        "title": check.get("title", check_id),
        "gap": gap_for_check(check_id),
        "summary": check.get("reason", ""),
        "next_action": "Run the deferred check explicitly when that scope matters.",
        "command": check.get("command", []),
        "evidence": {},
    }


def validate_owner_record(record: dict[str, Any], option_ids: set[str]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    status = str(record.get("status", "undecided") or "undecided")
    selected = str(record.get("selected_option", "") or "")
    if status not in ALLOWED_OWNER_RECORD_STATUSES:
        findings.append(f"invalid_status:{status}")
    if status == "decided":
        if not selected:
            findings.append("missing_selected_option")
        elif selected not in option_ids:
            findings.append(f"unknown_selected_option:{selected}")
        if not str(record.get("decided_by", "") or "").strip():
            findings.append("missing_decided_by")
        if not str(record.get("decided_at", "") or "").strip():
            findings.append("missing_decided_at")
    elif selected and selected not in option_ids:
        findings.append(f"unknown_selected_option:{selected}")
    return not findings, findings


def owner_decisions_from_issues(issues: list[dict[str, Any]], decision_state: dict[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for issue in issues:
        if issue.get("state") != "open":
            continue
        gap = issue.get("gap")
        if not isinstance(gap, dict):
            continue
        if gap.get("type") not in {"owner_decision", "publish_scope_governance"}:
            continue
        evidence = issue.get("evidence")
        decision_plan = evidence.get("decision_plan") if isinstance(evidence, dict) else None
        if not isinstance(decision_plan, dict) or not decision_plan:
            continue
        decision_id = str(decision_plan.get("decision", ""))
        record_present = isinstance(decision_state.get(decision_id), dict)
        record = decision_state.get(decision_id) if record_present else {}
        options = decision_plan.get("options", [])
        option_ids = {
            str(option.get("id"))
            for option in options
            if isinstance(option, dict) and option.get("id")
        }
        record_valid, record_findings = validate_owner_record(record, option_ids)
        if not record_present:
            record_valid = False
            record_findings = ["missing_decision_state_record", *record_findings]
        gate_ready = bool(decision_plan.get("ready", False))
        record_status = str(record.get("status", "undecided") or "undecided")
        record_ready = bool(record_valid and record_status == "decided")
        required_artifacts = decision_plan.get("required_artifacts", [])
        required_when = decision_plan.get("required_when", {})
        decisions.append({
            "issue_id": issue.get("issue_id"),
            "check_id": issue.get("check_id"),
            "severity": issue.get("severity"),
            "owner": decision_plan.get("owner") or gap.get("owner"),
            "decision": decision_id,
            "ready": gate_ready,
            "gate_ready": gate_ready,
            "record_ready": record_ready,
            "record_status": record_status,
            "selected_option": record.get("selected_option", ""),
            "decided_by": record.get("decided_by", ""),
            "decided_at": record.get("decided_at", ""),
            "record_present": record_present,
            "record_valid": record_valid,
            "record_findings": record_findings,
            "decision_state_file": str(OWNER_DECISIONS_PATH.relative_to(REPO_DIR).as_posix()),
            "decision_doc": decision_plan.get("decision_doc"),
            "summary": issue.get("summary", ""),
            "resolution": gap.get("resolution", ""),
            "required_artifacts": required_artifacts,
            "required_when": required_when,
            "record_gate_effect": owner_record_gate_effect(),
            "gate_unblock_requirements": owner_gate_unblock_requirements(required_artifacts, required_when),
            "options": options,
        })
    return decisions


def decision_state_findings(owner_decisions: list[dict[str, Any]], decision_state: dict[str, Any]) -> list[dict[str, Any]]:
    active_decisions = {
        str(item.get("decision"))
        for item in owner_decisions
        if isinstance(item, dict) and item.get("decision")
    }
    findings: list[dict[str, Any]] = []
    for decision_id in sorted(str(key) for key in decision_state):
        if decision_id not in active_decisions:
            findings.append({
                "code": "stale_decision_state_record",
                "decision": decision_id,
                "message": "decision state record has no matching open owner decision",
                "decision_state_file": str(OWNER_DECISIONS_PATH.relative_to(REPO_DIR).as_posix()),
            })
    return findings


def owner_decision_record_summary(
    owner_decisions: list[dict[str, Any]],
    state_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for item in owner_decisions:
        if not isinstance(item, dict):
            continue
        status = str(item.get("record_status", "unknown") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "valid_records": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("record_valid") is True),
        "invalid_records": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("record_valid") is not True),
        "missing_records": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("record_present") is not True),
        "stale_records": len(state_findings),
        "record_status_counts": dict(sorted(status_counts.items())),
    }


def owner_record_command(decision_id: str, mode: str) -> list[str]:
    return [
        "python",
        r"harness\maintain.py",
        "release-record-decision",
        mode,
        "--decision",
        decision_id,
        "--selected-option",
        "<option>",
        "--decided-by",
        "<owner>",
        "--decided-at",
        "YYYY-MM-DD",
        "--json",
    ]


def owner_record_gate_effect() -> dict[str, Any]:
    return {
        "effect": "records_owner_choice_only",
        "clears_release_blocker": False,
        "next_check": "rerun release-check after required artifacts or publish-scope changes are complete",
    }


def owner_gate_unblock_requirements(required_artifacts: Any, required_when: Any) -> dict[str, Any]:
    artifacts = [str(value) for value in required_artifacts] if isinstance(required_artifacts, list) else []
    conditions = dict(required_when) if isinstance(required_when, dict) else {}
    requirements: list[dict[str, Any]] = []
    if artifacts:
        requirements.append({"kind": "required_artifacts", "values": artifacts})
    if conditions:
        requirements.append({"kind": "required_conditions", "values": conditions})
    if not requirements:
        requirements.append({"kind": "rerun_release_check", "values": {}})
    return {
        "status": "blocked_until_requirements_clear",
        "requirements": requirements,
    }


def client_lifecycle_gap_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    contracts = evidence.get("contracts") if isinstance(evidence.get("contracts"), dict) else {}
    clients = evidence.get("clients") if isinstance(evidence.get("clients"), list) else []
    rows: list[dict[str, Any]] = []
    for client in clients:
        if not isinstance(client, dict):
            continue
        missing_full = client.get("missing_full_lifecycle_capabilities")
        missing_context = client.get("missing_context_brief_capabilities")
        rows.append({
            "id": client.get("id", ""),
            "status": client.get("status", ""),
            "support_level": client.get("support_level", ""),
            "missing_full_lifecycle_capabilities": missing_full if isinstance(missing_full, list) else [],
            "missing_context_brief_capabilities": missing_context if isinstance(missing_context, list) else [],
        })
    return {
        "full_lifecycle_required_capabilities": contracts.get("full_lifecycle_required_capabilities", []),
        "context_brief_required_capabilities": contracts.get("context_brief_required_capabilities", []),
        "clients": rows,
    }


def publish_scope_gap_breakdown(evidence: dict[str, Any]) -> dict[str, Any]:
    private_summary = evidence.get("private_tracked_summary")
    unclassified_summary = evidence.get("unclassified_tracked_summary")
    samples = evidence.get("samples")
    return {
        "private_tracked_paths": evidence.get("tracked_private_paths", 0),
        "unclassified_tracked_paths": evidence.get("unclassified_tracked_paths", 0),
        "private_tracked_summary": private_summary if isinstance(private_summary, dict) else {},
        "unclassified_tracked_summary": unclassified_summary if isinstance(unclassified_summary, dict) else {},
        "samples_count": evidence.get("samples_count", 0),
        "samples": samples if isinstance(samples, list) else [],
        "manifest": evidence.get("manifest", ""),
    }


def license_option_summary(decision: dict[str, Any]) -> list[dict[str, Any]]:
    options = decision.get("options")
    if not isinstance(options, list):
        return []
    rows: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        rows.append({
            "id": option.get("id", ""),
            "action": option.get("action", ""),
            "effect": option.get("effect", ""),
        })
    return rows


def remaining_gap_item(issue: dict[str, Any], owner_decision_by_issue: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gap = issue.get("gap") if isinstance(issue.get("gap"), dict) else {}
    item = {
        "issue_id": issue.get("issue_id"),
        "check_id": issue.get("check_id"),
        "severity": issue.get("severity"),
        "gap_type": gap.get("type", "unknown"),
        "owner": gap.get("owner", "unknown"),
        "title": issue.get("title", ""),
        "summary": issue.get("summary", ""),
        "resolution": gap.get("resolution", ""),
        "next_action": issue.get("next_action", ""),
        "command": issue.get("command", []),
    }
    evidence = compact_evidence(issue.get("evidence", {}))
    decision = owner_decision_by_issue.get(str(issue.get("issue_id", "")))
    if decision:
        decision_id = str(decision.get("decision", "") or "")
        allowed_options = [
            str(option.get("id"))
            for option in decision.get("options", [])
            if isinstance(option, dict) and option.get("id")
        ]
        item["decision"] = decision.get("decision", "")
        item["record_status"] = decision.get("record_status", "")
        item["selected_option"] = decision.get("selected_option", "")
        item["decision_doc"] = decision.get("decision_doc", "")
        item["required_artifacts"] = decision.get("required_artifacts", [])
        item["required_when"] = decision.get("required_when", {})
        item["allowed_options"] = allowed_options
        item["record_dry_run_command"] = owner_record_command(decision_id, "--dry-run")
        item["record_write_command"] = owner_record_command(decision_id, "--write")
        item["record_gate_effect"] = owner_record_gate_effect()
        item["gate_unblock_requirements"] = decision.get("gate_unblock_requirements", owner_gate_unblock_requirements(item["required_artifacts"], item["required_when"]))
        if issue.get("check_id") == "project_metadata":
            item["license_option_summary"] = license_option_summary(decision)
        if issue.get("check_id") == "publish_scope" and evidence:
            item["publish_scope_breakdown"] = publish_scope_gap_breakdown(evidence)
    elif evidence:
        item["evidence"] = evidence
        if issue.get("check_id") == "client_portability":
            item["client_lifecycle_gaps"] = client_lifecycle_gap_summary(evidence)
    return item


def build_remaining_gap_table(
    issues: list[dict[str, Any]],
    owner_decisions: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    owner_decision_by_issue = {
        str(item.get("issue_id", "")): item
        for item in owner_decisions
        if isinstance(item, dict) and item.get("issue_id")
    }
    table: dict[str, list[dict[str, Any]]] = {
        "owner_decisions": [],
        "code_remediation": [],
        "docs_publish_scope_governance": [],
        "deferred": [],
    }
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        state = issue.get("state")
        gap = issue.get("gap") if isinstance(issue.get("gap"), dict) else {}
        gap_type = str(gap.get("type", "unknown"))
        item = remaining_gap_item(issue, owner_decision_by_issue)
        if state == "deferred":
            table["deferred"].append(item)
        elif state != "open":
            continue
        elif gap_type in {"owner_decision", "publish_scope_governance"}:
            table["owner_decisions"].append(item)
        elif gap_type == "code_remediation":
            table["code_remediation"].append(item)
        else:
            table["docs_publish_scope_governance"].append(item)
    return table


def ledger_exit_code(summary: dict[str, Any]) -> int:
    if int(summary.get("blockers", 0) or 0) > 0:
        return 1
    if int(summary.get("decision_state_findings", 0) or 0) > 0:
        return 1
    record_summary = summary.get("owner_decision_records", {})
    if isinstance(record_summary, dict):
        for key in ("invalid_records", "missing_records", "stale_records"):
            if int(record_summary.get(key, 0) or 0) > 0:
                return 1
    return 0


def owner_decisions_exit_code(view: dict[str, Any]) -> int:
    summary = view.get("summary", {}) if isinstance(view.get("summary"), dict) else {}
    if int(summary.get("not_ready", 0) or 0) > 0:
        return 1
    if int(summary.get("decision_state_findings", 0) or 0) > 0:
        return 1
    record_summary = summary.get("owner_decision_records", {})
    if isinstance(record_summary, dict):
        for key in ("invalid_records", "missing_records", "stale_records"):
            if int(record_summary.get(key, 0) or 0) > 0:
                return 1
    return 0


def build_ledger(include_output_contracts: bool, include_legacy_health: bool) -> tuple[dict[str, Any], int]:
    report, error = run_release_check(include_output_contracts, include_legacy_health)
    if error:
        return {
            "schema_version": 1,
            "kind": "release_issue_ledger",
            "timestamp": datetime.now().replace(microsecond=0).isoformat(),
            "repo": str(REPO_DIR),
            "verdict": "invalid",
            "summary": {
                "open": 1,
                "resolved": 0,
                "deferred": 0,
                "blockers": 1,
                "warnings": 0,
            },
            "issues": [{
                "issue_id": "oss-release-check-json",
                "source": "oss_readiness",
                "check_id": "release_check_json",
                "state": "open",
                "severity": "blocker",
                "title": "Release check JSON is parseable",
                "gap": gap_for_check("release_check_json"),
                "summary": error,
                "next_action": "Fix oss_readiness_check JSON output.",
                "command": [PY, str(HARNESS_DIR / "scripts" / "oss_readiness_check.py"), "--json"],
                "evidence": {},
            }],
        }, 1

    issues: list[dict[str, Any]] = []
    for check in report.get("checks", []):
        status = check.get("status")
        if status in {"BLOCKER", "WARNING"}:
            issues.append(issue_from_check(check, "open"))
        elif status == "PASS":
            issues.append(issue_from_check(check, "resolved"))
    for check in report.get("deferred_checks", []):
        issues.append(issue_from_deferred(check))

    summary = {
        "open": sum(1 for issue in issues if issue["state"] == "open"),
        "resolved": sum(1 for issue in issues if issue["state"] == "resolved"),
        "deferred": sum(1 for issue in issues if issue["state"] == "deferred"),
        "blockers": sum(1 for issue in issues if issue["state"] == "open" and issue["severity"] == "blocker"),
        "warnings": sum(1 for issue in issues if issue["state"] == "open" and issue["severity"] == "warning"),
        "open_by_gap_type": count_open_by_gap(issues, "type"),
        "open_by_owner": count_open_by_gap(issues, "owner"),
    }
    owner_decision_state = load_owner_decision_state()
    owner_decisions = owner_decisions_from_issues(issues, owner_decision_state)
    state_findings = decision_state_findings(owner_decisions, owner_decision_state)
    summary["owner_decisions"] = len(owner_decisions)
    summary["decision_state_findings"] = len(state_findings)
    summary["owner_decision_records"] = owner_decision_record_summary(owner_decisions, state_findings)
    remaining_gap_table = build_remaining_gap_table(issues, owner_decisions)
    ledger = {
        "schema_version": 1,
        "kind": "release_issue_ledger",
        "timestamp": datetime.now().replace(microsecond=0).isoformat(),
        "repo": str(REPO_DIR),
        "release_verdict": report.get("verdict"),
        "summary": summary,
        "remaining_gap_table": remaining_gap_table,
        "owner_decisions": owner_decisions,
        "decision_state_findings": state_findings,
        "issues": issues,
    }
    return ledger, ledger_exit_code(summary)


def render_text(ledger: dict[str, Any]) -> str:
    summary = ledger["summary"]
    lines = [
        "release_issue_ledger.py - OSS readiness issue ledger",
        f"release_verdict={ledger.get('release_verdict', ledger.get('verdict'))}",
        f"open={summary['open']} blockers={summary['blockers']} warnings={summary['warnings']} resolved={summary['resolved']} deferred={summary['deferred']}",
        "",
    ]
    for issue in ledger["issues"]:
        if issue["state"] != "open":
            continue
        gap = issue.get("gap") if isinstance(issue.get("gap"), dict) else {}
        gap_type = gap.get("type", "unknown")
        owner = gap.get("owner", "unknown")
        lines.append(f"[{issue['severity']}] {issue['issue_id']} ({gap_type}/{owner}): {issue['summary']}")
        if issue.get("next_action"):
            lines.append(f"  next: {issue['next_action']}")
    owner_decisions = ledger.get("owner_decisions", [])
    if owner_decisions:
        lines.append("")
        lines.append("[owner_decisions]")
        for item in owner_decisions:
            options = item.get("options") if isinstance(item, dict) else []
            option_ids = [
                str(option.get("id"))
                for option in options
                if isinstance(option, dict) and option.get("id")
            ]
            lines.append(
                f"- {item.get('issue_id')}: decision={item.get('decision')} "
                f"owner={item.get('owner')} status={item.get('record_status')} "
                f"selected={item.get('selected_option') or '-'} "
                f"valid={item.get('record_valid')} options={','.join(option_ids)}"
            )
    remaining_gap_table = ledger.get("remaining_gap_table", {})
    if isinstance(remaining_gap_table, dict):
        lines.append("")
        lines.append("[remaining_gap_table]")
        for key in ("owner_decisions", "code_remediation", "docs_publish_scope_governance", "deferred"):
            items = remaining_gap_table.get(key, [])
            if isinstance(items, list):
                lines.append(f"- {key}: {len(items)}")
    return "\n".join(lines)


def owner_decisions_view(ledger: dict[str, Any]) -> dict[str, Any]:
    owner_decisions = ledger.get("owner_decisions", [])
    if not isinstance(owner_decisions, list):
        owner_decisions = []
    return {
        "schema_version": 1,
        "kind": "release_owner_decisions",
        "timestamp": ledger.get("timestamp"),
        "repo": ledger.get("repo"),
        "release_verdict": ledger.get("release_verdict", ledger.get("verdict")),
        "summary": {
            "owner_decisions": len(owner_decisions),
            "ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("ready") is True),
            "not_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("ready") is not True),
            "gate_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("gate_ready") is True),
            "gate_not_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("gate_ready") is not True),
            "record_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("record_ready") is True),
            "record_not_ready": sum(1 for item in owner_decisions if isinstance(item, dict) and item.get("record_ready") is not True),
            "decision_state_findings": len(ledger.get("decision_state_findings", [])) if isinstance(ledger.get("decision_state_findings"), list) else 0,
            "owner_decision_records": ledger.get("summary", {}).get("owner_decision_records", {}) if isinstance(ledger.get("summary"), dict) else {},
        },
        "owner_decisions": owner_decisions,
        "decision_state_findings": ledger.get("decision_state_findings", []),
    }


def owner_decision_template_view(ledger: dict[str, Any]) -> dict[str, Any]:
    owner_decisions = ledger.get("owner_decisions", [])
    if not isinstance(owner_decisions, list):
        owner_decisions = []
    templates: list[dict[str, Any]] = []
    patch: dict[str, Any] = {}
    for item in owner_decisions:
        if not isinstance(item, dict):
            continue
        decision_id = str(item.get("decision", "") or "")
        if not decision_id:
            continue
        options = item.get("options") if isinstance(item.get("options"), list) else []
        allowed_options = [
            {
                "id": option.get("id"),
                "action": option.get("action", ""),
                "effect": option.get("effect", ""),
            }
            for option in options
            if isinstance(option, dict) and option.get("id")
        ]
        patch[decision_id] = {
            "status": "decided",
            "selected_option": "<one of allowed_options.id>",
            "decided_by": "<owner>",
            "decided_at": "YYYY-MM-DD",
            "notes": "",
        }
        templates.append({
            "decision": decision_id,
            "issue_id": item.get("issue_id"),
            "check_id": item.get("check_id"),
            "owner": item.get("owner"),
            "record_status": item.get("record_status", "undecided"),
            "current_selected_option": item.get("selected_option", ""),
            "record_valid": item.get("record_valid"),
            "record_findings": item.get("record_findings", []),
            "decision_doc": item.get("decision_doc"),
            "decision_state_file": item.get("decision_state_file"),
            "summary": item.get("summary", ""),
            "resolution": item.get("resolution", ""),
            "allowed_options": allowed_options,
            "required_update_fields": ["status", "selected_option", "decided_by", "decided_at"],
            "state_patch_template": patch[decision_id],
            "required_artifacts": item.get("required_artifacts", []),
            "required_when": item.get("required_when", {}),
            "record_gate_effect": owner_record_gate_effect(),
            "gate_unblock_requirements": item.get("gate_unblock_requirements", owner_gate_unblock_requirements(item.get("required_artifacts", []), item.get("required_when", {}))),
            "gate_note": "Recording the owner decision is necessary but may not make release-check pass until required artifacts or publish-scope changes are also present.",
        })
    return {
        "schema_version": 1,
        "kind": "release_owner_decision_template",
        "timestamp": ledger.get("timestamp"),
        "repo": ledger.get("repo"),
        "release_verdict": ledger.get("release_verdict", ledger.get("verdict")),
        "decision_state_file": str(OWNER_DECISIONS_PATH.relative_to(REPO_DIR).as_posix()),
        "summary": {
            "templates": len(templates),
            "owner_decisions": len(owner_decisions),
        },
        "state_patch_template": {
            "decisions": patch,
        },
        "templates": templates,
        "decision_state_findings": ledger.get("decision_state_findings", []),
    }


def owner_decision_record_payload(
    *,
    selected_option: str,
    decided_by: str,
    decided_at: str,
    notes: str,
) -> dict[str, str]:
    return {
        "status": "decided",
        "selected_option": selected_option,
        "decided_by": decided_by,
        "decided_at": decided_at,
        "notes": notes,
    }


def build_owner_decision_record_report(
    ledger: dict[str, Any],
    *,
    decision_id: str,
    selected_option: str,
    decided_by: str,
    decided_at: str,
    notes: str = "",
    dry_run: bool = True,
    state_doc: dict[str, Any] | None = None,
    state_path: Path = OWNER_DECISIONS_PATH,
) -> tuple[dict[str, Any], int]:
    template_view = owner_decision_template_view(ledger)
    templates = template_view.get("templates", [])
    active_templates = {
        str(item.get("decision")): item
        for item in templates
        if isinstance(item, dict) and item.get("decision")
    }
    record = owner_decision_record_payload(
        selected_option=selected_option,
        decided_by=decided_by,
        decided_at=decided_at,
        notes=notes,
    )
    findings: list[dict[str, str]] = []
    template = active_templates.get(decision_id)
    if not template:
        findings.append({
            "code": "unknown_or_inactive_decision",
            "message": "decision is not in the current open owner decision queue",
        })
        allowed_options: list[str] = []
    else:
        allowed_options = [
            str(option.get("id"))
            for option in template.get("allowed_options", [])
            if isinstance(option, dict) and option.get("id")
        ]
        valid, record_findings = validate_owner_record(record, set(allowed_options))
        for finding in record_findings:
            findings.append({"code": finding, "message": "owner decision record is invalid"})
        if not DATE_RE.match(decided_at):
            findings.append({"code": "invalid_decided_at_format", "message": "expected YYYY-MM-DD"})
        if not valid and selected_option not in allowed_options:
            pass
    if not decided_by.strip():
        findings.append({"code": "missing_decided_by", "message": "decided_by is required"})
    if not dry_run and findings:
        action = "not_written"
    elif dry_run:
        action = "dry_run"
    else:
        action = "written"

    current_doc = state_doc if isinstance(state_doc, dict) else load_owner_decision_document()
    proposed_doc = dict(current_doc) if isinstance(current_doc, dict) else {}
    decisions = proposed_doc.get("decisions")
    if not isinstance(decisions, dict):
        decisions = {}
    proposed_decisions = dict(decisions)
    existing_record = proposed_decisions.get(decision_id)
    if not isinstance(existing_record, dict):
        existing_record = {}
    merged_record = dict(existing_record)
    merged_record.update(record)
    proposed_decisions[decision_id] = merged_record
    proposed_doc["decisions"] = proposed_decisions

    report = {
        "schema_version": 1,
        "kind": "release_owner_decision_record",
        "timestamp": ledger.get("timestamp"),
        "repo": ledger.get("repo"),
        "release_verdict": ledger.get("release_verdict", ledger.get("verdict")),
        "dry_run": dry_run,
        "action": action,
        "decision_state_file": rel_state_path(state_path),
        "decision": decision_id,
        "selected_option": selected_option,
        "allowed_options": allowed_options,
        "valid": not findings,
        "findings": findings,
        "record": record,
        "previous_record": existing_record,
        "proposed_record": merged_record,
        "required_artifacts": template.get("required_artifacts", []) if isinstance(template, dict) else [],
        "required_when": template.get("required_when", {}) if isinstance(template, dict) else {},
        "record_gate_effect": template.get("record_gate_effect", owner_record_gate_effect()) if isinstance(template, dict) else owner_record_gate_effect(),
        "gate_unblock_requirements": template.get("gate_unblock_requirements", owner_gate_unblock_requirements(template.get("required_artifacts", []), template.get("required_when", {}))) if isinstance(template, dict) else owner_gate_unblock_requirements([], {}),
        "gate_note": template.get("gate_note", "") if isinstance(template, dict) else "",
    }
    return report, 0 if not findings else 1


def record_owner_decision(
    ledger: dict[str, Any],
    *,
    decision_id: str,
    selected_option: str,
    decided_by: str,
    decided_at: str,
    notes: str = "",
    dry_run: bool = True,
    state_path: Path = OWNER_DECISIONS_PATH,
) -> tuple[dict[str, Any], int]:
    state_doc = load_owner_decision_document(state_path)
    report, exit_code = build_owner_decision_record_report(
        ledger,
        decision_id=decision_id,
        selected_option=selected_option,
        decided_by=decided_by,
        decided_at=decided_at,
        notes=notes,
        dry_run=dry_run,
        state_doc=state_doc,
        state_path=state_path,
    )
    if exit_code == 0 and not dry_run:
        proposed_doc = dict(state_doc)
        decisions = proposed_doc.get("decisions")
        if not isinstance(decisions, dict):
            decisions = {}
        merged_decisions = dict(decisions)
        previous = merged_decisions.get(decision_id)
        previous_record = previous if isinstance(previous, dict) else {}
        next_record = dict(previous_record)
        next_record.update(report["record"])
        merged_decisions[decision_id] = next_record
        proposed_doc["decisions"] = merged_decisions
        write_owner_decision_document(proposed_doc, state_path)
    return report, exit_code


def gap_table_view(ledger: dict[str, Any]) -> dict[str, Any]:
    table = ledger.get("remaining_gap_table", {})
    if not isinstance(table, dict):
        table = {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    for key in ("owner_decisions", "code_remediation", "docs_publish_scope_governance", "deferred"):
        items = table.get(key, [])
        normalized[key] = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    open_by_gap_type: dict[str, int] = {}
    for key in ("owner_decisions", "code_remediation", "docs_publish_scope_governance"):
        for item in normalized[key]:
            gap_type = str(item.get("gap_type", "unknown") or "unknown")
            open_by_gap_type[gap_type] = open_by_gap_type.get(gap_type, 0) + 1
    return {
        "schema_version": 1,
        "kind": "release_gap_table",
        "timestamp": ledger.get("timestamp"),
        "repo": ledger.get("repo"),
        "release_verdict": ledger.get("release_verdict", ledger.get("verdict")),
        "summary": {
            "owner_decisions": len(normalized["owner_decisions"]),
            "code_remediation": len(normalized["code_remediation"]),
            "docs_publish_scope_governance": len(normalized["docs_publish_scope_governance"]),
            "deferred": len(normalized["deferred"]),
            "open_by_gap_type": dict(sorted(open_by_gap_type.items())),
        },
        "remaining_gap_table": normalized,
    }


def render_owner_decisions_text(view: dict[str, Any]) -> str:
    summary = view.get("summary", {}) if isinstance(view.get("summary"), dict) else {}
    lines = [
        "release_issue_ledger.py - owner decision queue",
        f"release_verdict={view.get('release_verdict')}",
        f"owner_decisions={summary.get('owner_decisions', 0)} ready={summary.get('ready', 0)} not_ready={summary.get('not_ready', 0)} state_findings={summary.get('decision_state_findings', 0)}",
        f"gate_ready={summary.get('gate_ready', 0)} gate_not_ready={summary.get('gate_not_ready', 0)} record_ready={summary.get('record_ready', 0)} record_not_ready={summary.get('record_not_ready', 0)}",
        "",
    ]
    record_summary = summary.get("owner_decision_records", {}) if isinstance(summary.get("owner_decision_records"), dict) else {}
    if record_summary:
        lines.append(
            f"records valid={record_summary.get('valid_records', 0)} "
            f"invalid={record_summary.get('invalid_records', 0)} "
            f"missing={record_summary.get('missing_records', 0)} "
            f"stale={record_summary.get('stale_records', 0)}"
        )
        lines.append("")
    for item in view.get("owner_decisions", []):
        if not isinstance(item, dict):
            continue
        options = item.get("options") if isinstance(item.get("options"), list) else []
        option_ids = [
            str(option.get("id"))
            for option in options
            if isinstance(option, dict) and option.get("id")
        ]
        lines.append(
            f"- {item.get('issue_id')}: decision={item.get('decision')} "
            f"owner={item.get('owner')} status={item.get('record_status')} "
            f"selected={item.get('selected_option') or '-'} "
            f"valid={item.get('record_valid')} gate_ready={item.get('gate_ready')} "
            f"record_ready={item.get('record_ready')} options={','.join(option_ids)}"
        )
        if item.get("decision_doc"):
            lines.append(f"  doc: {item.get('decision_doc')}")
        if item.get("decision_state_file"):
            lines.append(f"  state: {item.get('decision_state_file')}")
        required_artifacts = item.get("required_artifacts")
        if isinstance(required_artifacts, list) and required_artifacts:
            lines.append(f"  required_artifacts: {', '.join(str(value) for value in required_artifacts)}")
        required_when = item.get("required_when")
        if isinstance(required_when, dict) and required_when:
            pairs = ", ".join(f"{key}={value}" for key, value in sorted(required_when.items()))
            lines.append(f"  required_when: {pairs}")
        record_gate_effect = item.get("record_gate_effect")
        if isinstance(record_gate_effect, dict) and record_gate_effect:
            lines.append(
                f"  record_gate_effect: effect={record_gate_effect.get('effect')} "
                f"clears_release_blocker={record_gate_effect.get('clears_release_blocker')}"
            )
        gate_unblock = item.get("gate_unblock_requirements")
        if isinstance(gate_unblock, dict):
            kinds = [
                str(requirement.get("kind"))
                for requirement in gate_unblock.get("requirements", [])
                if isinstance(requirement, dict) and requirement.get("kind")
            ]
            lines.append(f"  gate_unblock_requirements: {', '.join(kinds)}")
        decision_id = str(item.get("decision", "") or "")
        if decision_id:
            lines.append(f"  dry_run: {' '.join(owner_record_command(decision_id, '--dry-run'))}")
            lines.append(f"  write: {' '.join(owner_record_command(decision_id, '--write'))}")
    return "\n".join(lines)


def render_owner_decision_template_text(view: dict[str, Any]) -> str:
    summary = view.get("summary", {}) if isinstance(view.get("summary"), dict) else {}
    lines = [
        "release_issue_ledger.py - owner decision template",
        f"release_verdict={view.get('release_verdict')}",
        f"templates={summary.get('templates', 0)} state={view.get('decision_state_file')}",
        "",
    ]
    for item in view.get("templates", []):
        if not isinstance(item, dict):
            continue
        option_ids = [
            str(option.get("id"))
            for option in item.get("allowed_options", [])
            if isinstance(option, dict) and option.get("id")
        ]
        lines.append(
            f"- {item.get('decision')}: owner={item.get('owner')} "
            f"status={item.get('record_status')} options={','.join(option_ids)}"
        )
        if item.get("decision_doc"):
            lines.append(f"  doc: {item.get('decision_doc')}")
        required_artifacts = item.get("required_artifacts")
        if isinstance(required_artifacts, list) and required_artifacts:
            lines.append(f"  required_artifacts: {', '.join(str(value) for value in required_artifacts)}")
        required_when = item.get("required_when")
        if isinstance(required_when, dict) and required_when:
            pairs = ", ".join(f"{key}={value}" for key, value in sorted(required_when.items()))
            lines.append(f"  required_when: {pairs}")
        record_gate_effect = item.get("record_gate_effect")
        if isinstance(record_gate_effect, dict) and record_gate_effect:
            lines.append(
                f"  record_gate_effect: effect={record_gate_effect.get('effect')} "
                f"clears_release_blocker={record_gate_effect.get('clears_release_blocker')}"
            )
        gate_unblock = item.get("gate_unblock_requirements")
        if isinstance(gate_unblock, dict):
            kinds = [
                str(requirement.get("kind"))
                for requirement in gate_unblock.get("requirements", [])
                if isinstance(requirement, dict) and requirement.get("kind")
            ]
            lines.append(f"  gate_unblock_requirements: {', '.join(kinds)}")
        lines.append("  update: status=decided selected_option=<option> decided_by=<owner> decided_at=YYYY-MM-DD")
    return "\n".join(lines)


def render_gap_table_text(view: dict[str, Any]) -> str:
    summary = view.get("summary", {}) if isinstance(view.get("summary"), dict) else {}
    table = view.get("remaining_gap_table", {}) if isinstance(view.get("remaining_gap_table"), dict) else {}
    lines = [
        "release_issue_ledger.py - remaining gap table",
        f"release_verdict={view.get('release_verdict')}",
        (
            f"owner_decisions={summary.get('owner_decisions', 0)} "
            f"code_remediation={summary.get('code_remediation', 0)} "
            f"docs_publish_scope_governance={summary.get('docs_publish_scope_governance', 0)} "
            f"deferred={summary.get('deferred', 0)}"
        ),
    ]
    open_by_gap_type = summary.get("open_by_gap_type")
    if isinstance(open_by_gap_type, dict) and open_by_gap_type:
        pairs = ", ".join(f"{key}={value}" for key, value in sorted(open_by_gap_type.items()))
        lines.append(f"open_by_gap_type: {pairs}")
    for key in ("owner_decisions", "code_remediation", "docs_publish_scope_governance", "deferred"):
        items = table.get(key, [])
        if not isinstance(items, list):
            items = []
        lines.append("")
        lines.append(f"[{key}]")
        if not items:
            lines.append("- none")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('issue_id')}: owner={item.get('owner')} "
                f"severity={item.get('severity')} status={item.get('record_status', '-')}"
            )
            if item.get("summary"):
                lines.append(f"  summary: {item.get('summary')}")
            if item.get("decision_doc"):
                lines.append(f"  doc: {item.get('decision_doc')}")
            publish_breakdown = item.get("publish_scope_breakdown")
            if isinstance(publish_breakdown, dict):
                private_summary = publish_breakdown.get("private_tracked_summary")
                if isinstance(private_summary, dict):
                    for section_name, label in (
                        ("by_path_group", "private_by_path_group"),
                        ("by_reason", "private_by_reason"),
                    ):
                        rows = private_summary.get(section_name)
                        if isinstance(rows, list) and rows:
                            pairs = [
                                f"{row.get('key')}={row.get('count')}"
                                for row in rows[:8]
                                if isinstance(row, dict)
                            ]
                            if pairs:
                                lines.append(f"  {label}: {', '.join(pairs)}")
                samples_count = publish_breakdown.get("samples_count")
                if isinstance(samples_count, int) and samples_count:
                    lines.append(f"  private_samples_count: {samples_count}")
            evidence = item.get("evidence")
            if isinstance(evidence, dict):
                readiness = evidence.get("readiness")
                if isinstance(readiness, dict):
                    full_lifecycle = readiness.get("full_lifecycle_multi_client", {})
                    context_cli = readiness.get("context_cli", {})
                    if isinstance(full_lifecycle, dict) or isinstance(context_cli, dict):
                        lines.append(
                            "  readiness: "
                            f"full_lifecycle={full_lifecycle.get('stable_clients', '?')}/{full_lifecycle.get('required_clients', '?')} "
                            f"context_cli={context_cli.get('stable_clients', '?')}/{context_cli.get('required_clients', '?')}"
                        )
                clients = evidence.get("clients")
                if isinstance(clients, list) and clients:
                    client_bits = []
                    for client in clients:
                        if not isinstance(client, dict):
                            continue
                        client_bits.append(
                            f"{client.get('id')}:{client.get('status')}/{client.get('support_level')}"
                        )
                    if client_bits:
                        lines.append(f"  clients: {', '.join(client_bits)}")
            lifecycle_gaps = item.get("client_lifecycle_gaps")
            if isinstance(lifecycle_gaps, dict):
                required = lifecycle_gaps.get("full_lifecycle_required_capabilities")
                if isinstance(required, list) and required:
                    lines.append(f"  full_lifecycle_required: {', '.join(str(value) for value in required)}")
                lifecycle_clients = lifecycle_gaps.get("clients")
                if isinstance(lifecycle_clients, list):
                    for client in lifecycle_clients:
                        if not isinstance(client, dict):
                            continue
                        missing_full = client.get("missing_full_lifecycle_capabilities")
                        if isinstance(missing_full, list) and missing_full:
                            lines.append(
                                f"  missing_full_lifecycle[{client.get('id')}]: "
                                f"{', '.join(str(value) for value in missing_full)}"
                            )
                        missing_context = client.get("missing_context_brief_capabilities")
                        if isinstance(missing_context, list) and missing_context:
                            lines.append(
                                f"  missing_context_brief[{client.get('id')}]: "
                                f"{', '.join(str(value) for value in missing_context)}"
                            )
            if item.get("required_artifacts"):
                lines.append(f"  required_artifacts: {', '.join(str(value) for value in item.get('required_artifacts', []))}")
            required_when = item.get("required_when")
            if isinstance(required_when, dict) and required_when:
                pairs = ", ".join(f"{key}={value}" for key, value in sorted(required_when.items()))
                lines.append(f"  required_when: {pairs}")
            allowed_options = item.get("allowed_options")
            if isinstance(allowed_options, list) and allowed_options:
                lines.append(f"  allowed_options: {', '.join(str(value) for value in allowed_options)}")
            record_gate_effect = item.get("record_gate_effect")
            if isinstance(record_gate_effect, dict) and record_gate_effect:
                lines.append(
                    f"  record_gate_effect: effect={record_gate_effect.get('effect')} "
                    f"clears_release_blocker={record_gate_effect.get('clears_release_blocker')}"
                )
            gate_unblock = item.get("gate_unblock_requirements")
            if isinstance(gate_unblock, dict):
                kinds = [
                    str(requirement.get("kind"))
                    for requirement in gate_unblock.get("requirements", [])
                    if isinstance(requirement, dict) and requirement.get("kind")
                ]
                lines.append(f"  gate_unblock_requirements: {', '.join(kinds)}")
            dry_run_command = item.get("record_dry_run_command")
            if isinstance(dry_run_command, list) and dry_run_command:
                lines.append(f"  dry_run: {' '.join(str(value) for value in dry_run_command)}")
            write_command = item.get("record_write_command")
            if isinstance(write_command, list) and write_command:
                lines.append(f"  write: {' '.join(str(value) for value in write_command)}")
            if item.get("next_action"):
                lines.append(f"  next: {item.get('next_action')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--owner-decisions-only", action="store_true", help="emit only unresolved owner decision queue")
    parser.add_argument("--decision-template", action="store_true", help="emit owner-editable decision state template")
    parser.add_argument("--gap-table-only", action="store_true", help="emit only the categorized remaining gap table")
    parser.add_argument("--record-decision", metavar="DECISION", help="record an owner decision in release_owner_decisions.json")
    parser.add_argument("--selected-option", help="selected owner decision option")
    parser.add_argument("--decided-by", help="owner identity for a recorded decision")
    parser.add_argument("--decided-at", help="decision date in YYYY-MM-DD")
    parser.add_argument("--notes", default="", help="optional owner decision note")
    parser.add_argument("--dry-run", action="store_true", help="validate record-decision input without writing")
    parser.add_argument("--write", action="store_true", help="write a valid record-decision update")
    parser.add_argument("--strict", action="store_true", help="return non-zero when the selected release view is not ready")
    parser.add_argument("--include-output-contracts", action="store_true", help="include recursive output-contract check")
    parser.add_argument("--include-legacy-health", action="store_true", help="include deprecated legacy health check")
    args = parser.parse_args(argv)

    ledger, exit_code = build_ledger(args.include_output_contracts, args.include_legacy_health)
    selected_views = sum(bool(value) for value in (args.owner_decisions_only, args.decision_template, args.gap_table_only, args.record_decision))
    if selected_views > 1:
        parser.error("--owner-decisions-only, --decision-template, --gap-table-only, and --record-decision are mutually exclusive")
    if args.dry_run and args.write:
        parser.error("--dry-run and --write are mutually exclusive")
    if args.owner_decisions_only:
        output = owner_decisions_view(ledger)
    elif args.decision_template:
        output = owner_decision_template_view(ledger)
    elif args.gap_table_only:
        output = gap_table_view(ledger)
    elif args.record_decision:
        missing = [
            name
            for name, value in {
                "--selected-option": args.selected_option,
                "--decided-by": args.decided_by,
                "--decided-at": args.decided_at,
            }.items()
            if not value
        ]
        if missing:
            parser.error(f"--record-decision requires {', '.join(missing)}")
        output, record_exit_code = record_owner_decision(
            ledger,
            decision_id=args.record_decision,
            selected_option=args.selected_option,
            decided_by=args.decided_by,
            decided_at=args.decided_at,
            notes=args.notes,
            dry_run=args.dry_run or not args.write,
        )
    else:
        output = ledger
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif args.owner_decisions_only:
        print(render_owner_decisions_text(output))
    elif args.decision_template:
        print(render_owner_decision_template_text(output))
    elif args.gap_table_only:
        print(render_gap_table_text(output))
    elif args.record_decision:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(render_text(ledger))
    if args.record_decision:
        return record_exit_code
    if not args.strict:
        return 0
    if args.owner_decisions_only:
        return owner_decisions_exit_code(output)
    if args.decision_template:
        return owner_decisions_exit_code(owner_decisions_view(ledger))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
