#!/usr/bin/env python3
"""Validate harness/capability_manifest.json.

This check keeps capability boundaries machine-readable:
- every capability has a status and external story
- experimental/legacy/deprecated capabilities stay out of the release scope
- referenced scripts exist under harness/
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import json
import re
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

MANIFEST_PATH = HARNESS_DIR / "capability_manifest.json"
CAPABILITIES_DOC_PATH = REPO_DIR / "docs" / "capabilities.md"
README_PATH = REPO_DIR / "README.md"
ALLOWED_STATUSES = {"core", "optional", "experimental", "legacy", "deprecated"}
NON_RELEASE_STATUSES = {"experimental", "legacy", "deprecated"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", "tests", "test"}
SKIP_FILES = {"__init__.py"}


def finding(level: str, code: str, message: str, capability_id: str = "", path: str = "") -> dict[str, str]:
    return {
        "level": level,
        "code": code,
        "message": message,
        "capability_id": capability_id,
        "path": path,
    }


def safe_relpath(path_text: str) -> tuple[Path | None, str | None]:
    rel = Path(path_text.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        return None, "path must be relative to harness/ and cannot contain .."
    if rel.suffix != ".py":
        return None, "path must point to a .py file"
    return rel, None


def collect_actual_scripts(root: Path) -> set[str]:
    scripts: set[str] = set()
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        scripts.add(rel.as_posix())
    return scripts


def matches_any_glob(path_text: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_text, pattern) for pattern in patterns)


def validate_capability_doc(capabilities: list[dict[str, Any]], doc_path: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not doc_path.exists():
        return [finding("ERROR", "missing_capability_doc", "docs/capabilities.md is required", path=str(doc_path))]
    text = doc_path.read_text(encoding="utf-8", errors="replace")
    expected_ids = {
        str(capability.get("id", ""))
        for capability in capabilities
        if isinstance(capability, dict) and str(capability.get("id", "")).strip()
    }
    documented_ids = set(re.findall(r"capability:([a-z0-9_]+)", text))
    for capability_id in sorted(expected_ids - documented_ids):
        findings.append(finding(
            "ERROR",
            "missing_capability_doc_entry",
            "capability is missing from docs/capabilities.md",
            capability_id=capability_id,
        ))
    for capability_id in sorted(documented_ids - expected_ids):
        findings.append(finding(
            "WARNING",
            "stale_capability_doc_entry",
            "docs/capabilities.md documents a capability id not present in capability_manifest.json",
            capability_id=capability_id,
        ))
    return findings


def validate_readme_script_count(readme_path: Path, actual_script_count: int) -> list[dict[str, str]]:
    if not readme_path.exists():
        return [finding("ERROR", "missing_readme", "README.md is required", path=str(readme_path))]
    text = readme_path.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, str]] = []
    for match in re.finditer(r"(\d+)\s*个\s*harness\s*脚本", text, flags=re.IGNORECASE):
        documented = int(match.group(1))
        if documented != actual_script_count:
            findings.append(finding(
                "ERROR",
                "stale_readme_script_count",
                f"README.md documents {documented} harness scripts, actual count is {actual_script_count}",
                path=str(readme_path),
            ))
    return findings


def validate_capability(capability: dict[str, Any], seen_ids: set[str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    capability_id = str(capability.get("id", ""))
    status = str(capability.get("status", ""))
    release_scope = bool(capability.get("release_scope", False))
    scripts = capability.get("scripts", [])

    if not capability_id:
        findings.append(finding("ERROR", "missing_id", "capability id is required"))
    elif capability_id in seen_ids:
        findings.append(finding("ERROR", "duplicate_id", "capability id is duplicated", capability_id))
    seen_ids.add(capability_id)

    if status not in ALLOWED_STATUSES:
        findings.append(finding("ERROR", "invalid_status", f"status must be one of {sorted(ALLOWED_STATUSES)}", capability_id))
    if release_scope and status in NON_RELEASE_STATUSES:
        findings.append(finding("ERROR", "invalid_release_scope", f"{status} capabilities cannot be in release_scope", capability_id))

    for field in ["title", "boundary", "external_story"]:
        if not str(capability.get(field, "")).strip():
            findings.append(finding("ERROR", f"missing_{field}", f"{field} is required", capability_id))

    if not isinstance(scripts, list) or not scripts:
        findings.append(finding("ERROR", "missing_scripts", "scripts must be a non-empty list", capability_id))
        return findings

    seen_scripts: set[str] = set()
    for script in scripts:
        script_text = str(script).replace("\\", "/")
        if script_text in seen_scripts:
            findings.append(finding("WARNING", "duplicate_script", "script is listed more than once in this capability", capability_id, script_text))
            continue
        seen_scripts.add(script_text)
        rel, error = safe_relpath(script_text)
        if error or rel is None:
            findings.append(finding("ERROR", "invalid_script_path", error or "invalid script path", capability_id, script_text))
            continue
        if not (HARNESS_DIR / rel).is_file():
            findings.append(finding("ERROR", "missing_script", "script does not exist under harness/", capability_id, script_text))

    return findings


def build_report(manifest_path: Path) -> dict[str, Any]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    findings: list[dict[str, str]] = []
    capabilities = data.get("capabilities", [])
    if data.get("schema_version") != 1:
        findings.append(finding("ERROR", "invalid_schema_version", "schema_version must be 1"))
    if not isinstance(capabilities, list) or not capabilities:
        findings.append(finding("ERROR", "missing_capabilities", "capabilities must be a non-empty list"))
        capabilities = []
    findings.extend(validate_capability_doc(capabilities, CAPABILITIES_DOC_PATH))

    seen_ids: set[str] = set()
    assigned_scripts: set[str] = set()
    status_counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    release_scope_count = 0
    for capability in capabilities:
        if not isinstance(capability, dict):
            findings.append(finding("ERROR", "invalid_capability", "capability entries must be objects"))
            continue
        status = str(capability.get("status", ""))
        if status in status_counts:
            status_counts[status] += 1
        if capability.get("release_scope", False):
            release_scope_count += 1
        findings.extend(validate_capability(capability, seen_ids))
        for script in capability.get("scripts", []) if isinstance(capability.get("scripts", []), list) else []:
            script_text = str(script).replace("\\", "/")
            if safe_relpath(script_text)[1] is None:
                assigned_scripts.add(script_text)

    coverage = data.get("script_coverage", {})
    coverage_required = bool(coverage.get("require_all_harness_scripts", False))
    exemptions = [str(item).replace("\\", "/") for item in coverage.get("exemptions", []) or []]
    actual_scripts = collect_actual_scripts(HARNESS_DIR)
    unassigned = sorted(
        script for script in actual_scripts
        if script not in assigned_scripts and not matches_any_glob(script, exemptions)
    )
    stale_exemptions = sorted(
        pattern for pattern in exemptions
        if not any(fnmatch.fnmatch(script, pattern) for script in actual_scripts)
    )
    if coverage_required and unassigned:
        for script in unassigned[:50]:
            findings.append(finding(
                "ERROR",
                "unassigned_script",
                "script is present under harness/ but is not assigned to a capability or coverage exemption",
                path=script,
            ))
        if len(unassigned) > 50:
            findings.append(finding(
                "ERROR",
                "unassigned_script_overflow",
                f"{len(unassigned) - 50} additional scripts are unassigned",
            ))
    if stale_exemptions:
        for pattern in stale_exemptions[:20]:
            findings.append(finding(
                "WARNING",
                "stale_coverage_exemption",
                "coverage exemption matches no current harness script",
                path=pattern,
            ))
    findings.extend(validate_readme_script_count(README_PATH, len(actual_scripts)))

    errors = [item for item in findings if item["level"] == "ERROR"]
    warnings = [item for item in findings if item["level"] == "WARNING"]
    return {
        "schema_version": 1,
        "kind": "capability_manifest_check",
        "manifest": str(manifest_path),
        "summary": {
            "capabilities": len(capabilities),
            "release_scope": release_scope_count,
            "ERROR": len(errors),
            "WARNING": len(warnings),
            "status_counts": status_counts,
            "actual_scripts": len(actual_scripts),
            "assigned_scripts": len(assigned_scripts),
            "coverage_exemptions": len(exemptions),
            "unassigned_scripts": len(unassigned),
            "stale_coverage_exemptions": len(stale_exemptions),
            "documented_capabilities": len(capabilities) - len([
                item for item in findings
                if item["code"] == "missing_capability_doc_entry"
            ]),
        },
        "coverage": {
            "required": coverage_required,
            "unassigned": unassigned,
            "stale_exemptions": stale_exemptions,
        },
        "findings": findings,
        "verdict": "ok" if not errors else "invalid",
    }


def emit_text(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=" * 60)
    print("  check_capability_manifest")
    print("=" * 60)
    print(f"  capabilities:  {summary['capabilities']}")
    print(f"  release_scope: {summary['release_scope']}")
    print(f"  errors:        {summary['ERROR']}")
    print(f"  warnings:      {summary['WARNING']}")
    print(f"  scripts:       {summary['assigned_scripts']} assigned / {summary['actual_scripts']} actual")
    print(f"  unassigned:    {summary['unassigned_scripts']}")
    print(f"  verdict:       {report['verdict']}")
    for item in report["findings"]:
        where = f" {item['capability_id']}" if item.get("capability_id") else ""
        path = f" {item['path']}" if item.get("path") else ""
        print(f"[{item['level']}] {item['code']}{where}{path}: {item['message']}")
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
