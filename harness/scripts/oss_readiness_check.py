#!/usr/bin/env python3
"""
oss_readiness_check.py — read-only OSS/private-audit readiness profile.

This is not a release tool. It aggregates the checks that answer:
"what still prevents this local global-memory system from being a stable,
documented, externally installable project?"
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
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
from generate_catalog import build_check_report as build_catalog_check_report  # noqa: E402

PY = sys.executable
PUBLISH_SCOPE_MANIFEST = HARNESS_DIR / "publish_scope_manifest.json"
MAINTENANCE_MANIFEST = HARNESS_DIR / "maintenance_manifest.json"
CI_WORKFLOW = REPO_DIR / ".github" / "workflows" / "oss-readiness.yml"
REQUIRED_CI_COMMANDS = [
    "python -m unittest harness.tests.test_release_issue_ledger harness.tests.test_verify_output_contracts harness.tests.test_oss_readiness_check harness.tests.test_governance_pulse",
    r"python harness\generate_catalog.py --check --json",
    r"python harness\verify\verify_output_contracts.py --json",
    r"python harness\maintain.py release-checkpoint --json",
    r"python harness\maintain.py release-gaps --json",
    r"python harness\maintain.py release-decisions --json",
    r"python harness\maintain.py release-check --profile oss --json",
]

DOC_ENTRYPOINTS = [
    {
        "id": "getting_started",
        "path": REPO_DIR / "docs" / "getting-started.md",
        "readme_link": "docs/getting-started.md",
        "required_text": [
            "client_context.py",
            "bootstrap.py install",
            "release-check --profile oss",
            "CLAUDE_HOME",
        ],
    },
    {
        "id": "capabilities",
        "path": REPO_DIR / "docs" / "capabilities.md",
        "readme_link": "docs/capabilities.md",
        "required_text": [
            "capability:core_memory_retrieval",
            "capability:runtime_hook_governance",
            "capability:release_readiness",
        ],
    },
    {
        "id": "capability_gap_checkpoint",
        "path": REPO_DIR / "docs" / "capability-map-and-oss-gap.md",
        "readme_link": "docs/capability-map-and-oss-gap.md",
        "required_text": [
            "当前 checkpoint",
            "license_policy",
            "publish_scope_boundary",
            "release_issue_ledger.py --owner-decisions-only --json",
        ],
    },
    {
        "id": "contributing",
        "path": REPO_DIR / "docs" / "guide" / "CONTRIBUTING.md",
        "readme_link": "docs/guide/CONTRIBUTING.md",
        "required_text": [
            "加 Hook",
            "加 Skill",
            "加 Script",
            "验证",
        ],
    },
    {
        "id": "license_decision",
        "path": REPO_DIR / "docs" / "license-decision.md",
        "readme_link": "docs/license-decision.md",
        "required_text": [
            "Status: undecided",
            "LICENSE",
            "project-owner decision",
            "Do not add a license just to make the gate green",
        ],
    },
    {
        "id": "publish_scope",
        "path": REPO_DIR / "docs" / "publish-scope.md",
        "readme_link": "docs/publish-scope.md",
        "required_text": [
            "Default External Scope",
            "Not Default External Scope",
            "publish_scope_manifest.json",
            "tracked_private_paths",
            "source-only external MVP",
        ],
    },
]
DOC_FRONTMATTER_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

PROJECT_METADATA_FILES = {
    "readme": ["README.md"],
    "contributing": ["docs/guide/CONTRIBUTING.md"],
    "version": ["VERSION"],
    "dev_requirements": ["requirements-dev.txt"],
    "ci_workflow": [".github/workflows/oss-readiness.yml"],
    "license": ["LICENSE", "LICENSE.md", "COPYING"],
}

REQUIRED_MAINTENANCE_COMMANDS = {
    ("report", "maintain_report"): {
        "path": "maintain.py",
        "args": ["report", "--markdown"],
        "category": "read_only",
    },
    ("output_contracts", "verify_output_contracts"): {
        "path": "verify/verify_output_contracts.py",
        "args": ["--json"],
        "category": "read_only",
    },
    ("open_source_readiness", "maintain_release_check"): {
        "path": "maintain.py",
        "args": ["release-check", "--profile", "oss", "--json"],
        "category": "read_only",
    },
    ("open_source_readiness", "maintain_release_checkpoint_strict"): {
        "path": "maintain.py",
        "args": ["release-checkpoint", "--strict", "--json"],
        "category": "read_only",
    },
    ("open_source_readiness", "maintain_release_gaps"): {
        "path": "maintain.py",
        "args": ["release-gaps", "--json"],
        "category": "read_only",
    },
    ("open_source_readiness", "maintain_release_decisions"): {
        "path": "maintain.py",
        "args": ["release-decisions", "--json"],
        "category": "read_only",
    },
    ("capability_audit", "generate_catalog_check"): {
        "path": "generate_catalog.py",
        "args": ["--check", "--json"],
        "category": "read_only",
    },
    ("capability_audit", "scan_dual_storage"): {
        "path": "scripts/scan_dual_storage.py",
        "args": ["--json"],
        "category": "read_only",
    },
    ("self_loop", "self_loop_report"): {
        "path": "scripts/self_loop_report.py",
        "args": ["--json"],
        "category": "read_only",
    },
    ("self_loop", "meta_optimize"): {
        "path": "scripts/meta_optimize.py",
        "args": ["--json"],
        "category": "read_only",
    },
    ("side_effects", "maintain_release_record_decision_dry_run"): {
        "path": "maintain.py",
        "args": ["release-record-decision", "--dry-run"],
        "category": "owner_state_write",
    },
    ("governance_pulse", "governance_pulse_once"): {
        "path": "governance_pulse.py",
        "args": ["--once"],
        "category": "local_log_write",
    },
}

PATH_CONFIG_SURFACES = [
    REPO_DIR / "bootstrap.py",
    HARNESS_DIR / "_lib.py",
    HARNESS_DIR / "hooks" / "_hook_lib.py",
    HARNESS_DIR / "hooks" / "_task_resolver.py",
    HARNESS_DIR / "hooks" / "route_check.py",
    HARNESS_DIR / "scripts" / "harness_retrieve.py",
    HARNESS_DIR / "scripts" / "gate_check.py",
    HARNESS_DIR / "scripts" / "check_hook_alignment.py",
    HARNESS_DIR / "scripts" / "check_client_manifest.py",
    HARNESS_DIR / "scripts" / "check_capability_manifest.py",
    HARNESS_DIR / "scripts" / "client_context.py",
    HARNESS_DIR / "scripts" / "check_publish_scope.py",
    HARNESS_DIR / "scripts" / "export_source_scope.py",
    HARNESS_DIR / "scripts" / "scan_external_safety.py",
]
DISALLOWED_PATH_SNIPPETS = [
    'Path.home() / ".claude"',
    "Path.home() / '.claude'",
    'os.environ.get("GLOBAL_MEMORY_DIR"',
    "os.environ.get('GLOBAL_MEMORY_DIR'",
    'os.environ.get("CLAUDE_HOME"',
    "os.environ.get('CLAUDE_HOME'",
    'os.environ.get("CLAUDE_DIR"',
    "os.environ.get('CLAUDE_DIR'",
]
PRIVATE_AUDIT_PUBLICATION_CHECKS = {
    "project_metadata": "Private maturity audit: owner explicitly chose not to publish; missing LICENSE remains an OSS blocker only.",
    "publish_scope": "Private maturity audit: owner explicitly chose not to publish; private tracked paths remain an OSS blocker only.",
    "source_export_plan": "Private maturity audit: no clean external source export is required unless publication is resumed.",
}


def run(cmd: list[str], timeout: int = 90) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
        return {
            "command": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
        }


def extract_json(text: str) -> Any:
    raw = text.strip()
    if not raw:
        raise ValueError("empty stdout")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def make_result(
    check_id: str,
    title: str,
    status: str,
    command: list[str],
    returncode: int,
    summary: str,
    evidence: dict[str, Any] | None = None,
    next_action: str = "",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": status,
        "returncode": returncode,
        "summary": summary,
        "evidence": evidence or {},
        "next_action": next_action,
        "command": command,
    }


def check_registry() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "scripts" / "scan_orphan_scripts.py"), "--strict", "--json"]
    r = run(cmd)
    try:
        data = extract_json(r["stdout"])
        totals = data.get("totals", {})
        unregistered = totals.get("unregistered", 0)
        stale = totals.get("stale_in_registry", 0)
        orphan = totals.get("orphan_listed", 0)
        if r["returncode"] != 0 or unregistered or stale:
            return make_result(
                "capability_registry",
                "Scripts are absorbed by registry",
                "BLOCKER",
                cmd,
                r["returncode"],
                f"unregistered={unregistered}, stale={stale}, orphan={orphan}",
                {"totals": totals, "unregistered": data.get("unregistered", []), "stale": data.get("stale_in_registry", [])},
                "Register new scripts or remove stale registry entries.",
            )
        status = "WARNING" if orphan else "PASS"
        return make_result(
            "capability_registry",
            "Scripts are absorbed by registry",
            status,
            cmd,
            r["returncode"],
            f"unregistered=0, stale=0, orphan={orphan}",
            {"totals": totals, "orphan_listed": data.get("orphan_listed", [])},
            "Resolve or explicitly deprecate ORPHAN scripts." if orphan else "",
        )
    except Exception as exc:
        return make_result("capability_registry", "Scripts are absorbed by registry", "BLOCKER", cmd, r["returncode"], f"parse failed: {exc}", {"stderr": r["stderr"]}, "Fix scan_orphan_scripts JSON output.")


def check_hook_alignment() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "scripts" / "check_hook_alignment.py"), "--strict", "--json"]
    r = run(cmd)
    try:
        data = extract_json(r["stdout"])
        verdict = data.get("verdict")
        findings = data.get("totals", {}).get("findings", 0)
        status = "PASS" if r["returncode"] == 0 and verdict == "aligned" else "BLOCKER"
        return make_result(
            "hook_alignment",
            "Hook runtime, bootstrap, and registry are aligned",
            status,
            cmd,
            r["returncode"],
            f"verdict={verdict}, findings={findings}",
            {"findings": data.get("findings", [])},
            "Align bootstrap.py, settings.json, and docs/scripts-registry.md." if status == "BLOCKER" else "",
        )
    except Exception as exc:
        return make_result("hook_alignment", "Hook runtime, bootstrap, and registry are aligned", "BLOCKER", cmd, r["returncode"], f"parse failed: {exc}", {"stderr": r["stderr"]}, "Fix check_hook_alignment JSON output.")


def check_capability_manifest() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "scripts" / "check_capability_manifest.py"), "--json"]
    r = run(cmd)
    try:
        data = extract_json(r["stdout"])
        summary = data.get("summary", {})
        errors = summary.get("ERROR", 0)
        warnings = summary.get("WARNING", 0)
        status = "BLOCKER" if errors or r["returncode"] != 0 else ("WARNING" if warnings else "PASS")
        return make_result(
            "capability_manifest",
            "Capability boundaries are machine-readable",
            status,
            cmd,
            r["returncode"],
            (
                f"capabilities={summary.get('capabilities', 0)}, "
                f"release_scope={summary.get('release_scope', 0)}, "
                f"assigned_scripts={summary.get('assigned_scripts', 0)}/{summary.get('actual_scripts', 0)}, "
                f"documented_capabilities={summary.get('documented_capabilities', 0)}, "
                f"unassigned={summary.get('unassigned_scripts', 0)}, "
                f"errors={errors}, warnings={warnings}"
            ),
            {
                "summary": summary,
                "readiness": data.get("readiness", {}),
                "clients": data.get("clients", []),
                "findings": data.get("findings", []),
            },
            "Fix capability_manifest.json status, release_scope, and script path issues." if status != "PASS" else "",
        )
    except Exception as exc:
        return make_result("capability_manifest", "Capability boundaries are machine-readable", "BLOCKER", cmd, r["returncode"], f"parse failed: {exc}", {"stderr": r["stderr"]}, "Fix check_capability_manifest JSON output.")


def evaluate_maintenance_manifest_data(
    data: Any,
    harness_dir: Path = HARNESS_DIR,
    required_commands: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    required = dict(required_commands or REQUIRED_MAINTENANCE_COMMANDS)
    findings: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return {
            "summary": {"commands": 0, "scripts": 0, "required_commands": len(required), "findings": 1},
            "findings": [{"id": "manifest_root", "path": "harness/maintenance_manifest.json", "issue": "root_not_object"}],
        }

    commands = data.get("commands")
    if not isinstance(commands, dict):
        return {
            "summary": {"commands": 0, "scripts": 0, "required_commands": len(required), "findings": 1},
            "findings": [{"id": "manifest_commands", "path": "harness/maintenance_manifest.json", "issue": "commands_not_object"}],
        }

    script_count = 0
    seen_ids: dict[str, str] = {}
    scripts_by_group_id: dict[tuple[str, str], dict[str, Any]] = {}
    for group_id, group in commands.items():
        group_path = f"commands.{group_id}"
        if not isinstance(group, dict):
            findings.append({"id": "manifest_group", "path": group_path, "issue": "group_not_object"})
            continue
        scripts = group.get("scripts")
        if not isinstance(scripts, list):
            findings.append({"id": "manifest_group_scripts", "path": f"{group_path}.scripts", "issue": "scripts_not_list"})
            continue
        for index, script in enumerate(scripts):
            script_count += 1
            item_path = f"{group_path}.scripts[{index}]"
            if not isinstance(script, dict):
                findings.append({"id": "manifest_script", "path": item_path, "issue": "script_not_object"})
                continue
            script_id = script.get("id")
            if not isinstance(script_id, str) or not script_id.strip():
                findings.append({"id": "manifest_script_id", "path": item_path, "issue": "missing_script_id"})
                continue
            scripts_by_group_id[(str(group_id), script_id)] = script
            if script_id in seen_ids:
                findings.append({
                    "id": "manifest_script_id",
                    "path": item_path,
                    "issue": "duplicate_script_id",
                    "script_id": script_id,
                    "first_path": seen_ids[script_id],
                })
            else:
                seen_ids[script_id] = item_path
            category = script.get("category")
            if not isinstance(category, str) or not category.strip():
                findings.append({"id": script_id, "path": f"{item_path}.category", "issue": "missing_category"})
            args = script.get("args", [])
            if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
                findings.append({"id": script_id, "path": f"{item_path}.args", "issue": "args_not_string_list"})
            relpath = script.get("path")
            if relpath is not None:
                if not isinstance(relpath, str) or not relpath.strip():
                    findings.append({"id": script_id, "path": f"{item_path}.path", "issue": "invalid_path"})
                else:
                    target = (harness_dir / relpath).resolve()
                    try:
                        target.relative_to(harness_dir.parent.resolve())
                    except ValueError:
                        findings.append({"id": script_id, "path": f"{item_path}.path", "issue": "path_outside_repo", "target": str(target)})
                    if not target.exists():
                        findings.append({"id": script_id, "path": f"{item_path}.path", "issue": "missing_target", "target": str(target)})

    for (group_id, script_id), expected in required.items():
        script = scripts_by_group_id.get((group_id, script_id))
        item_path = f"commands.{group_id}.scripts.{script_id}"
        if script is None:
            findings.append({"id": script_id, "path": item_path, "issue": "missing_required_script", "group": group_id})
            continue
        for key in ("path", "args", "category"):
            if script.get(key) != expected.get(key):
                findings.append({
                    "id": script_id,
                    "path": f"{item_path}.{key}",
                    "issue": f"required_{key}_mismatch",
                    "expected": expected.get(key),
                    "actual": script.get(key),
                })

    return {
        "summary": {
            "commands": len(commands),
            "scripts": script_count,
            "required_commands": len(required),
            "findings": len(findings),
        },
        "findings": findings,
    }


def check_maintenance_manifest() -> dict[str, Any]:
    if not MAINTENANCE_MANIFEST.exists():
        evidence = {
            "summary": {"commands": 0, "scripts": 0, "required_commands": len(REQUIRED_MAINTENANCE_COMMANDS), "findings": 1},
            "findings": [{"id": "maintenance_manifest", "path": "harness/maintenance_manifest.json", "issue": "missing_manifest"}],
        }
    else:
        try:
            data = json.loads(MAINTENANCE_MANIFEST.read_text(encoding="utf-8"))
            evidence = evaluate_maintenance_manifest_data(data)
        except Exception as exc:
            evidence = {
                "summary": {"commands": 0, "scripts": 0, "required_commands": len(REQUIRED_MAINTENANCE_COMMANDS), "findings": 1},
                "findings": [{"id": "maintenance_manifest", "path": "harness/maintenance_manifest.json", "issue": "parse_failed", "message": str(exc)}],
            }
    summary = evidence["summary"]
    findings = evidence["findings"]
    status = "PASS" if not findings else "BLOCKER"
    return make_result(
        "maintenance_manifest",
        "Maintenance command manifest is internally consistent",
        status,
        ["internal", "maintenance_manifest_scan"],
        0 if not findings else 1,
        f"commands={summary.get('commands', 0)}, scripts={summary.get('scripts', 0)}, required={summary.get('required_commands', 0)}, findings={summary.get('findings', 0)}",
        evidence,
        "Fix maintenance_manifest.json command groups, paths, categories, or required JSON entrypoints." if findings else "",
    )


def _catalog_text_equal(expected: str, actual: str) -> bool:
    return expected.replace("\r\n", "\n").replace("\r", "\n") == actual.replace("\r\n", "\n").replace("\r", "\n")


def evaluate_catalog_freshness_data(items: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    fresh = 0
    stale = 0
    missing = 0
    for item in items:
        relpath = str(item.get("path", ""))
        expected = item.get("expected")
        actual = item.get("actual")
        exists = bool(item.get("exists", actual is not None))
        if not relpath:
            findings.append({"id": "catalog_target", "path": "", "issue": "missing_path"})
            continue
        if not exists or actual is None:
            missing += 1
            findings.append({"id": "catalog_missing", "path": relpath, "issue": "missing_catalog"})
            continue
        if not isinstance(expected, str) or not isinstance(actual, str):
            stale += 1
            findings.append({"id": "catalog_invalid", "path": relpath, "issue": "invalid_catalog_text"})
            continue
        if _catalog_text_equal(expected, actual):
            fresh += 1
            continue
        stale += 1
        findings.append({
            "id": "catalog_stale",
            "path": relpath,
            "issue": "stale_catalog",
            "expected_lines": len(expected.splitlines()),
            "actual_lines": len(actual.splitlines()),
        })
    return {
        "summary": {
            "targets": len(items),
            "fresh": fresh,
            "stale": stale,
            "missing": missing,
            "findings": len(findings),
        },
        "findings": findings,
    }


def check_catalog_freshness() -> dict[str, Any]:
    report = build_catalog_check_report()
    evidence = {
        "summary": report.get("summary", {}),
        "targets": report.get("targets", []),
        "findings": report.get("findings", []),
    }
    summary = evidence["summary"]
    findings = evidence["findings"]
    status = "PASS" if not findings else "BLOCKER"
    return make_result(
        "catalog_freshness",
        "Generated component catalogs are fresh",
        status,
        ["internal", "catalog_freshness_scan"],
        0 if not findings else 1,
        f"targets={summary.get('targets', 0)}, stale={summary.get('stale', 0)}, missing={summary.get('missing', 0)}, findings={summary.get('findings', 0)}",
        evidence,
        "Run python harness/generate_catalog.py after adding scripts, agents, or skills." if findings else "",
    )


def check_client_manifest() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "scripts" / "check_client_manifest.py"), "--json"]
    r = run(cmd)
    try:
        data = extract_json(r["stdout"])
        summary = data.get("summary", {})
        errors = summary.get("ERROR", 0)
        warnings = summary.get("WARNING", 0)
        status = "BLOCKER" if errors or r["returncode"] != 0 else ("WARNING" if warnings else "PASS")
        return make_result(
            "client_portability",
            "Client support scope is explicit",
            status,
            cmd,
            r["returncode"],
            (
                f"scope={data.get('product_scope')}, "
                f"stable_full_lifecycle={summary.get('stable_full_lifecycle_clients', 0)}, "
                f"stable_context={summary.get('stable_context_clients', 0)}, "
                f"claim_policy_checked={summary.get('claim_policy_checked', 0)}, "
                f"warnings={warnings}, errors={errors}"
            ),
            {
                "summary": summary,
                "readiness": data.get("readiness", {}),
                "contracts": data.get("contracts", {}),
                "clients": data.get("clients", []),
                "claim_policy": data.get("claim_policy", {}),
                "remediation_plan": data.get("remediation_plan", {}),
                "findings": data.get("findings", []),
            },
            "Keep the external claim narrow, or add another full-lifecycle stable client before claiming generic multi-client readiness." if status == "WARNING" else ("Fix client_manifest.json schema and entrypoints." if status == "BLOCKER" else ""),
        )
    except Exception as exc:
        return make_result("client_portability", "Client support scope is explicit", "BLOCKER", cmd, r["returncode"], f"parse failed: {exc}", {"stderr": r["stderr"]}, "Fix check_client_manifest JSON output.")


def check_docs_entrypoints() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    frontmatter_checked = 0
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8", errors="replace")
    for item in DOC_ENTRYPOINTS:
        path = item["path"]
        rel = str(path.relative_to(REPO_DIR)).replace("\\", "/")
        if not path.exists():
            findings.append({"id": item["id"], "path": rel, "issue": "missing_doc"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if item["readme_link"] not in readme:
            findings.append({"id": item["id"], "path": rel, "issue": "missing_readme_link"})
        if rel.startswith("docs/"):
            frontmatter_checked += 1
        findings.extend(validate_doc_entrypoint_frontmatter(item["id"], rel, text))
        for required in item["required_text"]:
            if required not in text:
                findings.append({
                    "id": item["id"],
                    "path": rel,
                    "issue": "missing_required_text",
                    "text": required,
                })
    status = "PASS" if not findings else "BLOCKER"
    return make_result(
        "docs_entrypoints",
        "External entrypoint docs exist and are linked",
        status,
        ["internal", "docs_entrypoints_scan"],
        0 if not findings else 1,
        f"checked={len(DOC_ENTRYPOINTS)}, frontmatter_checked={frontmatter_checked}, findings={len(findings)}",
        {"frontmatter_checked": frontmatter_checked, "findings": findings},
        "Add or link getting-started, capabilities, and contributing docs with required external-use commands." if findings else "",
    )


def validate_doc_entrypoint_frontmatter(entry_id: str, rel: str, text: str) -> list[dict[str, Any]]:
    if not rel.startswith("docs/"):
        return []
    findings: list[dict[str, Any]] = []
    if not text.startswith("---\n"):
        return [{"id": entry_id, "path": rel, "issue": "missing_frontmatter"}]
    end = text.find("\n---", 4)
    if end < 0:
        return [{"id": entry_id, "path": rel, "issue": "unterminated_frontmatter"}]
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    for field in ("status", "last_updated"):
        if not fields.get(field):
            findings.append({"id": entry_id, "path": rel, "issue": "missing_frontmatter_field", "field": field})
    last_updated = fields.get("last_updated", "")
    if last_updated and not DOC_FRONTMATTER_DATE_RE.match(last_updated):
        findings.append({"id": entry_id, "path": rel, "issue": "invalid_last_updated", "value": last_updated})
    return findings


def evaluate_ci_workflow_text(
    text: str,
    rel: str,
    required_commands: list[str] | None = None,
) -> dict[str, Any]:
    commands = list(required_commands or REQUIRED_CI_COMMANDS)
    findings: list[dict[str, Any]] = []
    yaml_valid = False
    step_count = 0
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            findings.append({"id": "workflow_yaml", "path": rel, "issue": "root_not_object"})
        else:
            steps = parsed.get("jobs", {}).get("readiness", {}).get("steps", [])
            if not isinstance(steps, list) or not steps:
                findings.append({"id": "workflow_yaml", "path": rel, "issue": "missing_readiness_steps"})
            else:
                yaml_valid = True
                step_count = len(steps)
    except Exception as exc:
        findings.append({
            "id": "workflow_yaml",
            "path": rel,
            "issue": "parse_failed",
            "message": str(exc),
        })
    for command in commands:
        if command not in text:
            findings.append({
                "id": "required_ci_command",
                "path": rel,
                "issue": "missing_command",
                "command": command,
            })
    return {
        "workflow": rel,
        "yaml_valid": yaml_valid,
        "step_count": step_count,
        "required_commands": commands,
        "findings": findings,
    }


def check_ci_workflow() -> dict[str, Any]:
    rel = str(CI_WORKFLOW.relative_to(REPO_DIR)).replace("\\", "/")
    if not CI_WORKFLOW.exists():
        evidence = {
            "workflow": rel,
            "yaml_valid": False,
            "step_count": 0,
            "required_commands": REQUIRED_CI_COMMANDS,
            "findings": [{"id": "oss_readiness_workflow", "path": rel, "issue": "missing_workflow"}],
        }
    else:
        text = CI_WORKFLOW.read_text(encoding="utf-8", errors="replace")
        evidence = evaluate_ci_workflow_text(text, rel)
    findings = evidence["findings"]
    yaml_valid = evidence["yaml_valid"]
    step_count = evidence["step_count"]
    status = "PASS" if not findings else "BLOCKER"
    return make_result(
        "ci_workflow",
        "CI exposes release evidence before final OSS gate",
        status,
        ["internal", "ci_workflow_scan"],
        0 if not findings else 1,
        f"yaml_valid={str(yaml_valid).lower()}, steps={step_count}, required_commands={len(REQUIRED_CI_COMMANDS)}, findings={len(findings)}",
        evidence,
        "Restore parseable OSS readiness workflow YAML and commands for output contracts, release checkpoint, gap table, owner queue, and final release-check." if findings else "",
    )


def check_project_metadata() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for item_id, candidates in PROJECT_METADATA_FILES.items():
        if not any((REPO_DIR / candidate).exists() for candidate in candidates):
            item = {
                "id": item_id,
                "issue": "missing_required_metadata",
                "candidates": candidates,
            }
            if item_id == "license":
                item["decision_doc"] = "docs/license-decision.md"
            findings.append(item)
    status = "PASS" if not findings else "BLOCKER"
    license_missing = any(item.get("id") == "license" for item in findings)
    decision_plan = {
        "decision": "license_policy",
        "owner": "project_owner",
        "ready": not license_missing,
        "decision_doc": "docs/license-decision.md",
        "required_artifacts": ["LICENSE", "LICENSE.md", "COPYING"],
        "selected": "mit" if not license_missing else None,
        "options": [
            {
                "id": "mit",
                "action": "add_mit_license",
                "effect": "Permissive reuse with minimal obligations.",
            },
            {
                "id": "apache_2_0",
                "action": "add_apache_2_0_license",
                "effect": "Permissive reuse with explicit patent grant.",
            },
            {
                "id": "bsd_3_clause",
                "action": "add_bsd_3_clause_license",
                "effect": "Permissive reuse with attribution and no endorsement.",
            },
            {
                "id": "agpl_3_0",
                "action": "add_agpl_3_0_license",
                "effect": "Strong copyleft including network use.",
            },
            {
                "id": "no_public_license",
                "action": "keep_source_visible_but_not_open_source_reusable",
                "effect": "Keep the project from claiming open-source reuse until the license is decided.",
            },
        ],
    }
    return make_result(
        "project_metadata",
        "Open-source project metadata is explicit",
        status,
        ["internal", "project_metadata_scan"],
        0 if not findings else 1,
        f"checked={len(PROJECT_METADATA_FILES)}, findings={len(findings)}",
        {"findings": findings, "decision_plan": decision_plan},
        "Add missing metadata. For license, read docs/license-decision.md; project owner must select it." if findings else "",
    )


def check_publish_scope() -> dict[str, Any]:
    cmd = [
        PY,
        str(HARNESS_DIR / "scripts" / "check_publish_scope.py"),
        "--strict",
        "--json",
        "--manifest",
        str(PUBLISH_SCOPE_MANIFEST),
    ]
    r = run(cmd, timeout=45)
    try:
        data = json.loads(r["stdout"])
    except Exception as exc:
        return make_result(
            "publish_scope",
            "Tracked files fit the external publish scope",
            "BLOCKER",
            cmd,
            r["returncode"],
            f"parse failed: {exc}",
            {},
            "Fix check_publish_scope JSON output.",
        )
    summary_data = data.get("summary", {}) if isinstance(data, dict) else {}
    status = "PASS" if r["returncode"] == 0 and data.get("verdict") == "ok" else "BLOCKER"
    private_count = int(summary_data.get("private_tracked_paths", 0) or 0)
    unclassified_count = int(summary_data.get("unclassified_tracked_paths", 0) or 0)
    return make_result(
        "publish_scope",
        "Tracked files fit the external publish scope",
        status,
        cmd,
        r["returncode"],
        f"tracked_private_paths={private_count}, unclassified_tracked_paths={unclassified_count}",
        {
            "tracked_private_paths": private_count,
            "unclassified_tracked_paths": unclassified_count,
            "private_tracked_summary": data.get("private_tracked_summary", {}),
            "samples": data.get("private_tracked_paths", [])[:40],
            "unclassified_tracked_summary": data.get("unclassified_tracked_summary", {}),
            "unclassified_samples": data.get("unclassified_tracked_paths", [])[:40],
            "decision_plan": data.get("decision_plan", {}),
            "manifest": "harness/publish_scope_manifest.json",
            "decision_doc": data.get("decision_doc", "docs/publish-scope.md"),
        },
        "Split, redact, or explicitly approve private data paths before public release. See docs/publish-scope.md." if status == "BLOCKER" else "",
    )


def check_source_export_plan() -> dict[str, Any]:
    cmd = [
        PY,
        str(HARNESS_DIR / "scripts" / "export_source_scope.py"),
        "--strict",
        "--json",
        "--manifest",
        str(PUBLISH_SCOPE_MANIFEST),
    ]
    r = run(cmd, timeout=45)
    try:
        data = json.loads(r["stdout"])
    except Exception as exc:
        return make_result(
            "source_export_plan",
            "Clean source export plan is reproducible",
            "BLOCKER",
            cmd,
            r["returncode"],
            f"parse failed: {exc}",
            {},
            "Fix export_source_scope JSON output.",
        )
    summary_data = data.get("summary", {}) if isinstance(data, dict) else {}
    if r["returncode"] != 0 or data.get("verdict") == "invalid":
        status = "BLOCKER"
    elif data.get("verdict") == "ready_with_warnings":
        status = "WARNING"
    else:
        status = "PASS"
    untracked_count = int(summary_data.get("untracked_included_paths", 0) or 0)
    included_count = int(summary_data.get("export_included_paths", 0) or 0)
    private_count = int(summary_data.get("excluded_private_paths", 0) or 0)
    return make_result(
        "source_export_plan",
        "Clean source export plan is reproducible",
        status,
        cmd,
        r["returncode"],
        f"included={included_count}, excluded_private={private_count}, untracked_included={untracked_count}",
        {
            "summary": summary_data,
            "untracked_included_summary": data.get("untracked_included_summary", {}),
            "tracking_plan": data.get("tracking_plan", {}),
            "untracked_included_samples": data.get("untracked_included_paths", [])[:40],
            "missing_external_files": data.get("missing_external_files", [])[:40],
            "unclassified_paths": data.get("unclassified_paths", [])[:40],
            "manifest": "harness/publish_scope_manifest.json",
        },
        "Track external-scope files before export, or fix missing/unclassified paths." if status != "PASS" else "",
    )


def check_external_source_safety() -> dict[str, Any]:
    cmd = [
        PY,
        str(HARNESS_DIR / "scripts" / "scan_external_safety.py"),
        "--strict",
        "--json",
        "--manifest",
        str(PUBLISH_SCOPE_MANIFEST),
    ]
    r = run(cmd, timeout=90)
    try:
        data = json.loads(r["stdout"])
    except Exception as exc:
        return make_result(
            "external_source_safety",
            "Planned external source has no obvious secrets or local-machine paths",
            "BLOCKER",
            cmd,
            r["returncode"],
            f"parse failed: {exc}",
            {},
            "Fix scan_external_safety JSON output.",
        )
    summary_data = data.get("summary", {}) if isinstance(data, dict) else {}
    blockers = int(summary_data.get("blockers", 0) or 0)
    warnings = int(summary_data.get("warnings", 0) or 0)
    if blockers or r["returncode"] != 0:
        status = "BLOCKER"
    elif warnings:
        status = "WARNING"
    else:
        status = "PASS"
    remediation_groups = data.get("remediation_groups", [])
    group_names = {
        str(item.get("group"))
        for item in remediation_groups
        if isinstance(item, dict)
    }
    if status == "PASS":
        next_action = ""
    elif blockers:
        next_action = "Remove high-confidence secrets before any external export."
    elif group_names == {"public_history"}:
        next_action = "Choose a public history policy: sanitize CHANGELOG.md or exclude/replace it in the external source export."
    else:
        next_action = "Replace local-machine paths in public docs, examples, and runtime source with configurable variables."
    return make_result(
        "external_source_safety",
        "Planned external source has no obvious secrets or local-machine paths",
        status,
        cmd,
        r["returncode"],
        f"blockers={blockers}, warnings={warnings}, scanned={summary_data.get('scanned_files', 0)}",
        {
            "summary": summary_data,
            "by_code": data.get("by_code", []),
            "top_paths": data.get("top_paths", [])[:20],
            "remediation_groups": remediation_groups,
            "policy_plan": data.get("policy_plan", {}),
            "findings": data.get("findings", [])[:10],
        },
        next_action,
    )


def check_bootstrap() -> dict[str, Any]:
    cmd = [PY, str(REPO_DIR / "bootstrap.py"), "check"]
    r = run(cmd, timeout=45)
    status = "PASS" if r["returncode"] == 0 else "BLOCKER"
    summary = "bootstrap check passed" if status == "PASS" else "bootstrap check failed"
    return make_result(
        "bootstrap_runtime",
        "Bootstrap runtime wiring is valid",
        status,
        cmd,
        r["returncode"],
        summary,
        {},
        "Run bootstrap.py install or fix missing runtime links." if status == "BLOCKER" else "",
    )


def evaluate_codex_work_skill_render_data(
    content: str,
    render_returncode: int,
    check_returncode: int,
) -> dict[str, Any]:
    required_snippets = {
        "codex_frontmatter": "name: codex-work",
        "generated_notice": "AUTO-GENERATED from global-memory/skills/work/SKILL.md",
        "shared_source": "Shared Work Mode Source",
        "codex_adapter": "Codex Adapter",
        "intent_guard_rule": "intent_guard",
    }
    findings: list[dict[str, Any]] = []
    if render_returncode != 0:
        findings.append({
            "id": "codex_work_skill_render",
            "issue": "render_failed",
            "returncode": render_returncode,
        })
    if check_returncode != 0:
        findings.append({
            "id": "codex_work_skill_drift_check",
            "issue": "drift_check_failed",
            "returncode": check_returncode,
        })
    if not content:
        findings.append({
            "id": "codex_work_skill_render",
            "issue": "missing_rendered_skill",
        })
    for snippet_id, snippet in required_snippets.items():
        if snippet not in content:
            findings.append({
                "id": snippet_id,
                "issue": "missing_required_snippet",
                "snippet": snippet,
            })
    return {
        "summary": {
            "bytes": len(content.encode("utf-8")),
            "required_snippets": len(required_snippets),
            "findings": len(findings),
        },
        "required_snippets": sorted(required_snippets),
        "findings": findings,
    }


def check_codex_work_skill_render() -> dict[str, Any]:
    script = HARNESS_DIR / "scripts" / "render_codex_work_skill.py"
    cmd = [PY, str(script), "--dest", "<temp>/codex-work/SKILL.md"]
    if not script.exists():
        evidence = evaluate_codex_work_skill_render_data("", render_returncode=1, check_returncode=1)
        return make_result(
            "codex_work_skill_render",
            "Codex work skill can be generated from shared source",
            "BLOCKER",
            cmd,
            1,
            "renderer missing",
            evidence,
            "Restore harness/scripts/render_codex_work_skill.py or remove the Codex work skill release claim.",
        )

    with tempfile.TemporaryDirectory(prefix="codex-work-skill-") as tmpdir:
        dest = Path(tmpdir) / "codex-work" / "SKILL.md"
        render_cmd = [PY, str(script), "--dest", str(dest)]
        render = run(render_cmd, timeout=30)
        content = ""
        if dest.exists():
            content = dest.read_text(encoding="utf-8", errors="replace")
        check_cmd = [PY, str(script), "--dest", str(dest), "--check"]
        check = run(check_cmd, timeout=30)
        evidence = evaluate_codex_work_skill_render_data(
            content,
            render_returncode=int(render.get("returncode", 1)),
            check_returncode=int(check.get("returncode", 1)),
        )
        evidence["render"] = {
            "command": render_cmd,
            "returncode": render.get("returncode"),
        }
        if render.get("returncode") != 0 or str(render.get("stderr", "")).strip():
            evidence["render"]["stdout"] = str(render.get("stdout", ""))[-1000:]
            evidence["render"]["stderr"] = str(render.get("stderr", ""))[-1000:]
        evidence["check"] = {
            "command": check_cmd,
            "returncode": check.get("returncode"),
        }
        if check.get("returncode") != 0 or str(check.get("stderr", "")).strip():
            evidence["check"]["stdout"] = str(check.get("stdout", ""))[-1000:]
            evidence["check"]["stderr"] = str(check.get("stderr", ""))[-1000:]

    findings = evidence["findings"]
    status = "PASS" if not findings else "BLOCKER"
    return make_result(
        "codex_work_skill_render",
        "Codex work skill can be generated from shared source",
        status,
        cmd,
        0 if status == "PASS" else 1,
        (
            f"bytes={evidence['summary'].get('bytes', 0)}, "
            f"required_snippets={evidence['summary'].get('required_snippets', 0)}, "
            f"findings={evidence['summary'].get('findings', 0)}"
        ),
        evidence,
        "Fix render_codex_work_skill.py, shared work skill source, or Codex adapter drift." if findings else "",
    )


def check_hardcoded_paths() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "fix_hardcoded_paths.py")]
    r = run(cmd, timeout=120)
    text = r["stdout"]
    if "未发现硬编码路径问题" in text:
        issues = 0
    else:
        matches = re.findall(r"发现\s*(\d+)\s*个问题", text)
        issues = int(matches[-1]) if matches else None
    issue_samples = [
        line.strip()
        for line in text.splitlines()
        if ":L" in line and "[" in line
    ][:10]
    status = "PASS" if r["returncode"] == 0 and issues == 0 else "BLOCKER"
    summary = "issues=0" if issues == 0 else f"issues={issues if issues is not None else 'unknown'}"
    return make_result(
        "hardcoded_paths",
        "Core files avoid machine-specific absolute paths",
        status,
        cmd,
        r["returncode"],
        summary,
        {"issue_count": issues, "issue_samples": issue_samples},
        "Remove or parameterize hardcoded local paths; do not leave this as WARN in OSS profile." if status == "BLOCKER" else "",
    )


def check_path_config() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in PATH_CONFIG_SURFACES:
        if not path.exists():
            findings.append({
                "path": str(path.relative_to(REPO_DIR)),
                "line": 0,
                "snippet": "missing_file",
            })
            continue
        rel = str(path.relative_to(REPO_DIR)).replace("\\", "/")
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for snippet in DISALLOWED_PATH_SNIPPETS:
                if snippet in line:
                    findings.append({
                        "path": rel,
                        "line": lineno,
                        "snippet": snippet,
                    })
    status = "PASS" if not findings else "BLOCKER"
    return make_result(
        "path_config",
        "Release-facing path defaults use harness/config.py",
        status,
        ["internal", "path_config_scan"],
        0 if not findings else 1,
        f"checked={len(PATH_CONFIG_SURFACES)}, duplicated_path_roots={len(findings)}",
        {"findings": findings},
        "Move release-facing root/path defaults into harness/config.py instead of repeating Path.home/env fallback logic." if findings else "",
    )


def check_governance_gate() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "scripts" / "gate_check.py"), "--json"]
    r = run(cmd, timeout=360)
    try:
        data = extract_json(r["stdout"])
        summary = data.get("summary", {})
        failures = summary.get("fail", 0)
        status = "BLOCKER" if failures or r["returncode"] != 0 else "PASS"
        return make_result(
            "governance_gate",
            "Governance gate is machine-readable and passing",
            status,
            cmd,
            r["returncode"],
            f"verdict={data.get('verdict')}, pass={summary.get('pass', 0)}, fail={failures}",
            {"summary": summary, "failures": data.get("failures", [])},
            "Fix failing G1-G9 checks or gate_check JSON output before using it as a release gate." if status == "BLOCKER" else "",
        )
    except Exception as exc:
        return make_result("governance_gate", "Governance gate is machine-readable and passing", "BLOCKER", cmd, r["returncode"], f"parse failed: {exc}", {"stderr": r["stderr"]}, "Fix gate_check JSON output.")


def check_output_contracts() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "verify" / "verify_output_contracts.py"), "--json"]
    r = run(cmd, timeout=180)
    try:
        data = extract_json(r["stdout"])
        summary = data.get("summary", {})
        errors = summary.get("ERROR", 0)
        warnings = summary.get("WARNING", 0)
        status = "BLOCKER" if errors or r["returncode"] != 0 else ("WARNING" if warnings else "PASS")
        return make_result(
            "output_contracts",
            "Machine-readable outputs remain parseable",
            status,
            cmd,
            r["returncode"],
            f"errors={errors}, warnings={warnings}, cases={summary.get('CASES', 0)}",
            {"summary": summary},
            "Fix JSON/stdout/stderr hygiene before external automation." if status != "PASS" else "",
        )
    except Exception as exc:
        return make_result("output_contracts", "Machine-readable outputs remain parseable", "BLOCKER", cmd, r["returncode"], f"parse failed: {exc}", {"stderr": r["stderr"]}, "Fix verify_output_contracts JSON output.")


def check_smoke() -> dict[str, Any]:
    cmd = [PY, str(HARNESS_DIR / "verify" / "smoke_test.py"), "--json"]
    r = run(cmd, timeout=120)
    try:
        data = extract_json(r["stdout"])
        summary = data.get("summary", {})
        fail = summary.get("FAIL", 0)
        warn = summary.get("WARN", 0)
        status = "BLOCKER" if fail else ("WARNING" if warn or r["returncode"] != 0 else "PASS")
        return make_result(
            "smoke_test",
            "Smoke test has no failures",
            status,
            cmd,
            r["returncode"],
            f"pass={summary.get('PASS', 0)}, warn={warn}, fail={fail}, skip={summary.get('SKIP', 0)}",
            {"summary": summary},
            "Convert persistent smoke warnings into explicit accepted debt or fix them." if status == "WARNING" else ("Fix smoke failures." if status == "BLOCKER" else ""),
        )
    except Exception as exc:
        return make_result("smoke_test", "Smoke test has no failures", "BLOCKER", cmd, r["returncode"], f"parse failed: {exc}", {"stderr": r["stderr"]}, "Fix smoke_test JSON output.")


def apply_private_audit_profile(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for check in checks:
        check_id = str(check.get("id", ""))
        if check_id in PRIVATE_AUDIT_PUBLICATION_CHECKS and check.get("status") == "BLOCKER":
            clone = dict(check)
            evidence = dict(clone.get("evidence") or {})
            evidence["private_audit"] = {
                "accepted_private_publication_gap": True,
                "oss_status": "BLOCKER",
                "reason": PRIVATE_AUDIT_PUBLICATION_CHECKS[check_id],
            }
            clone["evidence"] = evidence
            clone["status"] = "WARNING"
            clone["summary"] = f"{clone.get('summary', '')}; private_audit=accepted_publication_gap"
            clone["next_action"] = "No action for private maturity audit. Re-enable OSS publication work before claiming external release readiness."
            adjusted.append(clone)
            continue
        adjusted.append(check)
    return adjusted


def build_report(
    strict: bool,
    skip_output_contracts: bool = False,
    include_legacy_health: bool = False,
    profile: str = "oss",
) -> dict[str, Any]:
    checks = [
        check_registry(),
        check_capability_manifest(),
        check_maintenance_manifest(),
        check_catalog_freshness(),
        check_client_manifest(),
        check_docs_entrypoints(),
        check_ci_workflow(),
        check_project_metadata(),
        check_publish_scope(),
        check_source_export_plan(),
        check_external_source_safety(),
        check_hook_alignment(),
        check_bootstrap(),
        check_codex_work_skill_render(),
        check_hardcoded_paths(),
        check_path_config(),
        check_governance_gate(),
    ]
    if not skip_output_contracts:
        checks.append(check_output_contracts())
    checks.extend([
        check_smoke(),
    ])
    if profile == "private-audit":
        checks = apply_private_audit_profile(checks)
    counts = {"PASS": 0, "WARNING": 0, "BLOCKER": 0}
    for check in checks:
        counts[check["status"]] = counts.get(check["status"], 0) + 1
    if counts["BLOCKER"]:
        verdict = "blocked"
    elif counts["WARNING"]:
        verdict = "needs_cleanup"
    else:
        verdict = "ready"
    exit_code = 1 if counts["BLOCKER"] or (strict and counts["WARNING"]) else 0
    return {
        "schema_version": 1,
        "kind": "oss_readiness_check",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO_DIR),
        "profile": profile,
        "strict": strict,
        "skip_output_contracts": skip_output_contracts,
        "include_legacy_health": include_legacy_health,
        "verdict": verdict,
        "exit_code": exit_code,
        "summary": counts,
        "blockers": [c for c in checks if c["status"] == "BLOCKER"],
        "warnings": [c for c in checks if c["status"] == "WARNING"],
        "deferred_checks": [],
        "checks": checks,
    }


def emit_text(report: dict[str, Any]) -> None:
    print("=" * 60)
    print("  oss_readiness_check")
    print("=" * 60)
    print(f"  verdict:  {report['verdict']}")
    print(f"  blockers: {report['summary'].get('BLOCKER', 0)}")
    print(f"  warnings: {report['summary'].get('WARNING', 0)}")
    print()
    for check in report["checks"]:
        print(f"[{check['status']}] {check['id']}: {check['summary']}")
        if check.get("next_action"):
            print(f"  next: {check['next_action']}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--profile", choices=["oss", "private-audit"], default="oss", help="readiness profile to evaluate")
    ap.add_argument("--strict", action="store_true", help="return non-zero on warnings as well as blockers")
    ap.add_argument("--skip-output-contracts", action="store_true", help="avoid recursive output-contract checks")
    ap.add_argument("--include-legacy-health", action="store_true", help="include deprecated check_health.py content hygiene warnings")
    args = ap.parse_args(argv)

    report = build_report(
        strict=args.strict,
        skip_output_contracts=args.skip_output_contracts,
        include_legacy_health=args.include_legacy_health,
        profile=args.profile,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit_text(report)
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
