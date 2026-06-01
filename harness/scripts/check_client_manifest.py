#!/usr/bin/env python3
"""Validate client support scope and external claim policy.

The check deliberately distinguishes "Claude Code harness is usable" from
"generic multi-client memory system is ready".
"""
from __future__ import annotations

import argparse
import io
import json
import sys
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

MANIFEST_PATH = HARNESS_DIR / "client_manifest.json"
ALLOWED_STATUSES = {"stable", "experimental", "planned", "deprecated"}
ALLOWED_INTEGRATIONS = {"hooks_settings", "manual_cli", "api", "none"}
ALLOWED_SUPPORT_LEVELS = {"full_lifecycle", "context_brief_only", "planned"}
FULL_LIFECYCLE_INTEGRATIONS = {"hooks_settings", "api"}
GENERIC_CONTEXT_ENTRYPOINT = "harness/scripts/client_context.py"
DEFAULT_FULL_LIFECYCLE_CAPABILITIES = [
    "install_or_bootstrap",
    "automatic_context_injection",
    "write_governance",
    "audit_logging",
    "rollback_or_disable",
    "release_health_check",
]
DEFAULT_CONTEXT_BRIEF_CAPABILITIES = [
    "context_brief_cli",
    "json_output_contract",
]


def finding(level: str, code: str, message: str, client_id: str = "", path: str = "") -> dict[str, str]:
    return {
        "level": level,
        "code": code,
        "message": message,
        "client_id": client_id,
        "path": path,
    }


def entrypoint_exists(text: str) -> bool:
    first = text.split()[0].replace("\\", "/")
    path = REPO_DIR / first
    return path.exists()


def normalized_entrypoint_path(text: str) -> str:
    return text.split()[0].replace("\\", "/")


def bool_capabilities(client: dict[str, Any]) -> dict[str, bool]:
    raw = client.get("capabilities")
    if not isinstance(raw, dict):
        return {}
    return {str(key): value is True for key, value in raw.items()}


def validate_client(
    client: dict[str, Any],
    seen_ids: set[str],
    full_lifecycle_required: list[str] | None = None,
    context_brief_required: list[str] | None = None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    client_id = str(client.get("id", ""))
    status = str(client.get("status", ""))
    integration = str(client.get("integration", ""))
    support_level = str(client.get("support_level", ""))
    entrypoints = client.get("entrypoints", [])
    full_lifecycle_required = full_lifecycle_required or DEFAULT_FULL_LIFECYCLE_CAPABILITIES
    context_brief_required = context_brief_required or DEFAULT_CONTEXT_BRIEF_CAPABILITIES

    if not client_id:
        findings.append(finding("ERROR", "missing_id", "client id is required"))
    elif client_id in seen_ids:
        findings.append(finding("ERROR", "duplicate_id", "client id is duplicated", client_id))
    seen_ids.add(client_id)

    if not str(client.get("name", "")).strip():
        findings.append(finding("ERROR", "missing_name", "client name is required", client_id))
    if status not in ALLOWED_STATUSES:
        findings.append(finding("ERROR", "invalid_status", f"status must be one of {sorted(ALLOWED_STATUSES)}", client_id))
    if integration not in ALLOWED_INTEGRATIONS:
        findings.append(finding("ERROR", "invalid_integration", f"integration must be one of {sorted(ALLOWED_INTEGRATIONS)}", client_id))
    if support_level not in ALLOWED_SUPPORT_LEVELS:
        findings.append(finding("ERROR", "invalid_support_level", f"support_level must be one of {sorted(ALLOWED_SUPPORT_LEVELS)}", client_id))
    if support_level == "full_lifecycle" and integration not in FULL_LIFECYCLE_INTEGRATIONS:
        findings.append(finding("ERROR", "invalid_full_lifecycle_integration", "full_lifecycle clients must use hooks_settings or api integration", client_id))
    if support_level == "planned" and status == "stable":
        findings.append(finding("ERROR", "stable_planned_support", "stable clients cannot use planned support_level", client_id))
    capabilities = bool_capabilities(client)
    if not capabilities:
        findings.append(finding("ERROR", "missing_client_capabilities", "clients must declare capability booleans", client_id, "capabilities"))
    if support_level == "full_lifecycle":
        missing = [capability for capability in full_lifecycle_required if capabilities.get(capability) is not True]
        if missing:
            findings.append(finding(
                "ERROR",
                "missing_full_lifecycle_capability",
                f"full_lifecycle clients must satisfy required capabilities: {missing}",
                client_id,
                "capabilities",
            ))
    if support_level == "context_brief_only":
        missing = [capability for capability in context_brief_required if capabilities.get(capability) is not True]
        if missing:
            findings.append(finding(
                "ERROR",
                "missing_context_brief_capability",
                f"context_brief_only clients must satisfy required capabilities: {missing}",
                client_id,
                "capabilities",
            ))
    if not isinstance(entrypoints, list) or not entrypoints:
        findings.append(finding("ERROR", "missing_entrypoints", "entrypoints must be a non-empty list", client_id))
    else:
        normalized_entrypoints = [normalized_entrypoint_path(str(entrypoint)) for entrypoint in entrypoints]
        for entrypoint in entrypoints:
            text = str(entrypoint)
            if not entrypoint_exists(text):
                findings.append(finding("ERROR", "missing_entrypoint", "entrypoint path does not exist", client_id, text))
        if support_level == "context_brief_only" and GENERIC_CONTEXT_ENTRYPOINT not in normalized_entrypoints:
            findings.append(finding("ERROR", "missing_context_cli_entrypoint", "context_brief_only clients must expose harness/scripts/client_context.py", client_id))
    if status != "stable" and not client.get("limitations"):
        findings.append(finding("WARNING", "missing_limitations", "non-stable clients should list current limitations", client_id))
    return findings


def validate_claim_policy(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    policy = data.get("claim_policy")
    findings: list[dict[str, str]] = []
    checked = 0
    if not isinstance(policy, dict):
        return {"checked": 0, "findings": [{"level": "ERROR", "code": "missing_claim_policy"}]}, [
            finding("ERROR", "missing_claim_policy", "claim_policy is required to keep external client claims aligned")
        ]

    required = policy.get("required_phrases", [])
    if not isinstance(required, list) or not required:
        return {"checked": 0, "findings": [{"level": "ERROR", "code": "missing_required_claim_phrases"}]}, [
            finding("ERROR", "missing_required_claim_phrases", "claim_policy.required_phrases must be a non-empty list")
        ]

    for index, item in enumerate(required):
        if not isinstance(item, dict):
            findings.append(finding("ERROR", "invalid_claim_policy_row", "claim policy rows must be objects", path=f"claim_policy.required_phrases[{index}]"))
            continue
        rel = str(item.get("path", "")).replace("\\", "/")
        phrases = item.get("contains", [])
        if not rel or not isinstance(phrases, list) or not phrases:
            findings.append(finding("ERROR", "invalid_claim_policy_row", "claim policy rows require path and non-empty contains", path=f"claim_policy.required_phrases[{index}]"))
            continue
        target = REPO_DIR / rel
        if not target.exists():
            findings.append(finding("ERROR", "claim_policy_missing_file", "claim policy target file does not exist", path=rel))
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        checked += 1
        for phrase in phrases:
            phrase_text = str(phrase)
            if phrase_text not in text:
                findings.append(finding("ERROR", "claim_policy_missing_phrase", f"required phrase not found: {phrase_text}", path=rel))

    forbidden = policy.get("forbidden_phrases", [])
    forbidden_checked = 0
    if forbidden and not isinstance(forbidden, list):
        findings.append(finding("ERROR", "invalid_forbidden_claim_policy", "claim_policy.forbidden_phrases must be a list", path="claim_policy.forbidden_phrases"))
        forbidden = []
    for index, item in enumerate(forbidden):
        if not isinstance(item, dict):
            findings.append(finding("ERROR", "invalid_claim_policy_row", "claim policy rows must be objects", path=f"claim_policy.forbidden_phrases[{index}]"))
            continue
        rel = str(item.get("path", "")).replace("\\", "/")
        phrases = item.get("contains", [])
        if not rel or not isinstance(phrases, list) or not phrases:
            findings.append(finding("ERROR", "invalid_claim_policy_row", "claim policy rows require path and non-empty contains", path=f"claim_policy.forbidden_phrases[{index}]"))
            continue
        target = REPO_DIR / rel
        if not target.exists():
            findings.append(finding("ERROR", "claim_policy_missing_file", "claim policy target file does not exist", path=rel))
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        forbidden_checked += 1
        for phrase in phrases:
            phrase_text = str(phrase)
            if phrase_text in text:
                findings.append(finding("ERROR", "claim_policy_forbidden_phrase", f"forbidden overclaim found: {phrase_text}", path=rel))

    return {
        "checked": checked,
        "required": len(required),
        "forbidden_checked": forbidden_checked,
        "forbidden": len(forbidden),
        "findings": findings,
    }, findings


def validate_remediation_plan(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    plan = data.get("remediation_plan")
    findings: list[dict[str, str]] = []
    if not isinstance(plan, dict):
        return {}, [finding("ERROR", "missing_remediation_plan", "remediation_plan is required for unresolved client portability scope")]

    decision = str(plan.get("decision", "") or "")
    owner = str(plan.get("owner", "") or "")
    options = plan.get("options", [])
    if decision != "client_portability_scope":
        findings.append(finding("ERROR", "invalid_remediation_decision", "remediation_plan.decision must be client_portability_scope", path="remediation_plan.decision"))
    if not owner:
        findings.append(finding("ERROR", "missing_remediation_owner", "remediation_plan.owner is required", path="remediation_plan.owner"))
    if not isinstance(plan.get("ready"), bool):
        findings.append(finding("ERROR", "invalid_remediation_ready", "remediation_plan.ready must be a boolean", path="remediation_plan.ready"))
    if not str(plan.get("current_constraint", "") or "").strip():
        findings.append(finding("ERROR", "missing_remediation_constraint", "remediation_plan.current_constraint is required", path="remediation_plan.current_constraint"))
    if not str(plan.get("next_check", "") or "").strip():
        findings.append(finding("ERROR", "missing_remediation_next_check", "remediation_plan.next_check is required", path="remediation_plan.next_check"))
    if not isinstance(options, list) or len(options) < 2:
        findings.append(finding("ERROR", "missing_remediation_options", "remediation_plan.options must contain at least two options", path="remediation_plan.options"))
        options = []

    option_ids: set[str] = set()
    for index, option in enumerate(options):
        path = f"remediation_plan.options[{index}]"
        if not isinstance(option, dict):
            findings.append(finding("ERROR", "invalid_remediation_option", "remediation plan options must be objects", path=path))
            continue
        option_id = str(option.get("id", "") or "")
        if not option_id:
            findings.append(finding("ERROR", "missing_remediation_option_id", "remediation option id is required", path=f"{path}.id"))
        else:
            option_ids.add(option_id)
        if not str(option.get("action", "") or "").strip():
            findings.append(finding("ERROR", "missing_remediation_option_action", "remediation option action is required", path=f"{path}.action"))
        if not str(option.get("effect", "") or "").strip():
            findings.append(finding("ERROR", "missing_remediation_option_effect", "remediation option effect is required", path=f"{path}.effect"))

    required_options = {"keep_narrow_claim", "add_second_full_lifecycle_client"}
    missing = required_options - option_ids
    if missing:
        findings.append(finding("ERROR", "missing_required_remediation_options", f"missing remediation options: {sorted(missing)}", path="remediation_plan.options"))

    return {
        "decision": decision,
        "owner": owner,
        "ready": plan.get("ready", False),
        "current_constraint": plan.get("current_constraint", ""),
        "next_check": plan.get("next_check", ""),
        "options": options,
        "findings": findings,
    }, findings


def summarize_client(
    client: dict[str, Any],
    full_lifecycle_required: list[str],
    context_brief_required: list[str],
) -> dict[str, Any]:
    entrypoints = client.get("entrypoints", [])
    limitations = client.get("limitations", [])
    capabilities = bool_capabilities(client)
    return {
        "id": str(client.get("id", "")),
        "name": str(client.get("name", "")),
        "status": str(client.get("status", "")),
        "integration": str(client.get("integration", "")),
        "support_level": str(client.get("support_level", "")),
        "entrypoint_count": len(entrypoints) if isinstance(entrypoints, list) else 0,
        "limitations_count": len(limitations) if isinstance(limitations, list) else 0,
        "capability_count": sum(1 for value in capabilities.values() if value is True),
        "missing_full_lifecycle_capabilities": [
            capability for capability in full_lifecycle_required if capabilities.get(capability) is not True
        ],
        "missing_context_brief_capabilities": [
            capability for capability in context_brief_required if capabilities.get(capability) is not True
        ],
    }


def build_report(manifest_path: Path) -> dict[str, Any]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    findings: list[dict[str, str]] = []
    clients = data.get("clients", [])
    if data.get("schema_version") != 1:
        findings.append(finding("ERROR", "invalid_schema_version", "schema_version must be 1"))
    if not isinstance(clients, list) or not clients:
        findings.append(finding("ERROR", "missing_clients", "clients must be a non-empty list"))
        clients = []

    contracts = data.get("contracts", {})
    if not isinstance(contracts, dict):
        findings.append(finding("ERROR", "missing_contracts", "contracts object is required"))
        contracts = {}
    full_lifecycle_required = contracts.get("full_lifecycle_required_capabilities", DEFAULT_FULL_LIFECYCLE_CAPABILITIES)
    context_brief_required = contracts.get("context_brief_required_capabilities", DEFAULT_CONTEXT_BRIEF_CAPABILITIES)
    if not isinstance(full_lifecycle_required, list) or not all(isinstance(item, str) and item.strip() for item in full_lifecycle_required):
        findings.append(finding("ERROR", "invalid_full_lifecycle_contract", "contracts.full_lifecycle_required_capabilities must be a non-empty string list", path="contracts.full_lifecycle_required_capabilities"))
        full_lifecycle_required = DEFAULT_FULL_LIFECYCLE_CAPABILITIES
    if not isinstance(context_brief_required, list) or not all(isinstance(item, str) and item.strip() for item in context_brief_required):
        findings.append(finding("ERROR", "invalid_context_brief_contract", "contracts.context_brief_required_capabilities must be a non-empty string list", path="contracts.context_brief_required_capabilities"))
        context_brief_required = DEFAULT_CONTEXT_BRIEF_CAPABILITIES

    seen_ids: set[str] = set()
    status_counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    for client in clients:
        if not isinstance(client, dict):
            findings.append(finding("ERROR", "invalid_client", "client entries must be objects"))
            continue
        status = str(client.get("status", ""))
        if status in status_counts:
            status_counts[status] += 1
        findings.extend(validate_client(client, seen_ids, full_lifecycle_required, context_brief_required))
    claim_policy, claim_findings = validate_claim_policy(data)
    findings.extend(claim_findings)
    remediation_plan, remediation_findings = validate_remediation_plan(data)
    findings.extend(remediation_findings)

    stable = status_counts.get("stable", 0)
    stable_full_lifecycle = sum(
        1
        for client in clients
        if isinstance(client, dict)
        and client.get("status") == "stable"
        and client.get("support_level") == "full_lifecycle"
    )
    stable_context_cli = sum(
        1
        for client in clients
        if isinstance(client, dict)
        and client.get("status") == "stable"
        and client.get("support_level") in {"full_lifecycle", "context_brief_only"}
    )
    minimum = int(data.get("stable_client_minimum_for_generic_oss", 2))
    raw_multi_client_ready = data.get("multi_client_ready", False)
    raw_context_cli_ready = data.get("context_cli_ready", False)
    if not isinstance(raw_multi_client_ready, bool):
        findings.append(finding("ERROR", "invalid_multi_client_ready", "multi_client_ready must be a boolean"))
    if not isinstance(raw_context_cli_ready, bool):
        findings.append(finding("ERROR", "invalid_context_cli_ready", "context_cli_ready must be a boolean"))
    multi_client_ready = raw_multi_client_ready is True
    context_cli_ready = raw_context_cli_ready is True
    expected_constraint = f"stable_full_lifecycle_clients={stable_full_lifecycle}, required_for_generic_oss={minimum}"
    if remediation_plan.get("current_constraint") != expected_constraint:
        findings.append(finding(
            "ERROR",
            "stale_remediation_constraint",
            f"remediation_plan.current_constraint must be {expected_constraint}",
            path="remediation_plan.current_constraint",
        ))
    if stable_full_lifecycle < minimum and remediation_plan.get("ready") is True:
        findings.append(finding("ERROR", "overstated_remediation_ready", "remediation_plan.ready cannot be true while full lifecycle client coverage is below the minimum", path="remediation_plan.ready"))
    if multi_client_ready and stable_full_lifecycle < minimum:
        findings.append(finding(
            "ERROR",
            "overstated_multi_client_ready",
            f"multi_client_ready=true but stable_full_lifecycle_clients={stable_full_lifecycle}, required_for_generic_oss={minimum}",
        ))
    if stable_full_lifecycle < minimum or not multi_client_ready:
        findings.append(finding(
            "WARNING",
            "single_full_lifecycle_client_scope",
            f"full_lifecycle_multi_client_ready=false; stable_full_lifecycle_clients={stable_full_lifecycle}, required_for_generic_oss={minimum}; product_scope={data.get('product_scope', '')}",
        ))
    if context_cli_ready and stable_context_cli < minimum:
        findings.append(finding(
            "ERROR",
            "overstated_context_cli_ready",
            f"context_cli_ready=true but stable_context_clients={stable_context_cli}, required_for_generic_oss={minimum}",
        ))

    errors = [item for item in findings if item["level"] == "ERROR"]
    warnings = [item for item in findings if item["level"] == "WARNING"]
    return {
        "schema_version": 1,
        "kind": "client_manifest_check",
        "manifest": str(manifest_path),
        "product_scope": data.get("product_scope", ""),
        "multi_client_ready": multi_client_ready,
        "context_cli_ready": context_cli_ready,
        "readiness": {
            "full_lifecycle_multi_client": {
                "ready": multi_client_ready,
                "stable_clients": stable_full_lifecycle,
                "required_clients": minimum,
            },
            "context_cli": {
                "ready": context_cli_ready,
                "stable_clients": stable_context_cli,
                "required_clients": minimum,
            },
        },
        "contracts": {
            "full_lifecycle_required_capabilities": full_lifecycle_required,
            "context_brief_required_capabilities": context_brief_required,
        },
        "clients": [
            summarize_client(client, full_lifecycle_required, context_brief_required)
            for client in clients
            if isinstance(client, dict)
        ],
        "summary": {
            "clients": len(clients),
            "stable_clients": stable,
            "stable_full_lifecycle_clients": stable_full_lifecycle,
            "stable_context_clients": stable_context_cli,
            "required_for_generic_oss": minimum,
            "claim_policy_checked": int(claim_policy.get("checked", 0)),
            "ERROR": len(errors),
            "WARNING": len(warnings),
            "status_counts": status_counts,
        },
        "claim_policy": claim_policy,
        "remediation_plan": remediation_plan,
        "findings": findings,
        "verdict": "invalid" if errors else ("single_client_scope" if warnings else "ok"),
    }


def emit_text(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=" * 60)
    print("  check_client_manifest")
    print("=" * 60)
    print(f"  product_scope:  {report['product_scope']}")
    print(f"  clients:        {summary['clients']}")
    print(f"  stable_clients: {summary['stable_clients']}")
    print(f"  errors:         {summary['ERROR']}")
    print(f"  warnings:       {summary['WARNING']}")
    print(f"  verdict:        {report['verdict']}")
    for item in report["findings"]:
        who = f" {item['client_id']}" if item.get("client_id") else ""
        path = f" {item['path']}" if item.get("path") else ""
        print(f"[{item['level']}] {item['code']}{who}{path}: {item['message']}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args(argv)

    report = build_report(args.manifest)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit_text(report)
    return 1 if report["summary"]["ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
