#!/usr/bin/env python3
"""Scan planned external source files for obvious local paths and secrets."""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))

from check_publish_scope import DEFAULT_MANIFEST  # noqa: E402
from config import REPO_DIR  # noqa: E402
from export_source_scope import build_plan  # noqa: E402

BINARY_SUFFIXES = {
    ".7z", ".bmp", ".dll", ".exe", ".gif", ".ico", ".jpg", ".jpeg", ".pdf",
    ".png", ".pyc", ".pyd", ".qm", ".ttf", ".webp", ".zip",
}

PATTERNS = [
    {
        "id": "private_key_block",
        "severity": "blocker",
        "regex": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    },
    {
        "id": "openai_api_key",
        "severity": "blocker",
        "regex": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    },
    {
        "id": "aws_access_key",
        "severity": "blocker",
        "regex": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    },
    {
        "id": "assigned_secret_like_value",
        "severity": "blocker",
        "regex": re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]?(?!"
            r"\$\{|%|<|your-|example|changeme|os\.environ|getenv|env\[)"
            r"[A-Za-z0-9_./+=-]{24,}"
        ),
    },
    {
        "id": "local_absolute_path",
        "severity": "warning",
        "regex": re.compile(
            r"(?i)\b(?:[A-Z]:[\\/](?:Users[\\/]XINDONG|global-memory|ClaudeTasks)"
            r"|D:[\\/]global-memory|D:[\\/]ClaudeTasks|C:[\\/]Users[\\/]XINDONG)\b"
        ),
    },
]


def is_binary_or_large(path: Path, max_bytes: int) -> tuple[bool, str]:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True, "binary_suffix"
    try:
        size = path.stat().st_size
    except OSError as exc:
        return True, f"stat_failed:{type(exc).__name__}"
    if size > max_bytes:
        return True, f"large_file:{size}"
    try:
        chunk = path.read_bytes()[:4096]
    except OSError as exc:
        return True, f"read_failed:{type(exc).__name__}"
    if b"\0" in chunk:
        return True, "binary_nul"
    return False, ""


def safe_snippet(line: str) -> str:
    text = line.strip()
    text = re.sub(r"(sk-)[A-Za-z0-9_-]{8,}", r"\1<redacted>", text)
    text = re.sub(r"((?:AKIA|ASIA)[A-Z0-9]{4})[A-Z0-9]{12}", r"\1<redacted>", text)
    return text[:180]


def scan_file(path: Path, rel: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in PATTERNS:
            if pattern["regex"].search(line):
                findings.append({
                    "path": rel,
                    "line": line_no,
                    "severity": pattern["severity"],
                    "code": pattern["id"],
                    "snippet": safe_snippet(line),
                })
    return findings


def classify_remediation(path: str) -> str:
    if path == "CHANGELOG.md":
        return "public_history"
    if path.startswith("docs/") or path in {"README.md", "CONTRIBUTING.md", "MAINTENANCE.md"}:
        return "public_docs"
    if path.startswith("skills/") or path.startswith("agents/") or path.startswith("templates/"):
        return "examples_and_prompts"
    if path.startswith("harness/"):
        return "runtime_source"
    return "other_external_source"


def summarize_findings(findings: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    by_code_counter: Counter[tuple[str, str]] = Counter()
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for finding in findings:
        severity = str(finding.get("severity", "unknown"))
        code = str(finding.get("code", "unknown"))
        path = str(finding.get("path", ""))
        by_code_counter[(code, severity)] += 1
        by_path[path].append(finding)
        by_group[classify_remediation(path)].append(finding)

    by_code = [
        {
            "code": code,
            "severity": severity,
            "count": count,
        }
        for (code, severity), count in sorted(
            by_code_counter.items(),
            key=lambda item: (-item[1], item[0][1], item[0][0]),
        )
    ]

    top_paths = []
    for path, path_findings in by_path.items():
        severity_counts = Counter(str(item.get("severity", "unknown")) for item in path_findings)
        code_counts = Counter(str(item.get("code", "unknown")) for item in path_findings)
        first = sorted(path_findings, key=lambda item: int(item.get("line", 0) or 0))[:3]
        top_paths.append({
            "path": path,
            "findings": len(path_findings),
            "blockers": severity_counts.get("blocker", 0),
            "warnings": severity_counts.get("warning", 0),
            "codes": [
                {"code": code, "count": count}
                for code, count in sorted(code_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            "first_locations": [
                {"line": item.get("line"), "code": item.get("code"), "severity": item.get("severity")}
                for item in first
            ],
        })
    top_paths.sort(key=lambda item: (-int(item["blockers"]), -int(item["findings"]), str(item["path"])))

    remediation_groups = []
    for group, group_findings in by_group.items():
        paths = sorted({str(item.get("path", "")) for item in group_findings})
        severity_counts = Counter(str(item.get("severity", "unknown")) for item in group_findings)
        code_counts = Counter(str(item.get("code", "unknown")) for item in group_findings)
        remediation_groups.append({
            "group": group,
            "findings": len(group_findings),
            "blockers": severity_counts.get("blocker", 0),
            "warnings": severity_counts.get("warning", 0),
            "paths": paths[:limit],
            "path_count": len(paths),
            "codes": [
                {"code": code, "count": count}
                for code, count in sorted(code_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
        })
    remediation_groups.sort(key=lambda item: (-int(item["blockers"]), -int(item["findings"]), str(item["group"])))

    return {
        "by_code": by_code,
        "top_paths": top_paths[:limit],
        "remediation_groups": remediation_groups,
    }


def build_public_history_policy_plan(grouped: dict[str, Any], blockers: int, warnings: int) -> dict[str, Any]:
    groups = grouped.get("remediation_groups", [])
    group_names = {
        str(item.get("group"))
        for item in groups
        if isinstance(item, dict)
    }
    if blockers or warnings <= 0 or group_names != {"public_history"}:
        return {}
    paths = sorted({
        path
        for item in groups
        if isinstance(item, dict)
        for path in item.get("paths", [])
        if isinstance(path, str)
    })
    return {
        "decision": "public_history_policy",
        "owner": "project_owner_or_maintainer",
        "ready": False,
        "paths": paths,
        "warning_count": warnings,
        "options": [
            {
                "id": "sanitize_changelog",
                "action": "replace_local_paths_with_public_placeholders",
                "effect": "Keep CHANGELOG.md in the external source scope after removing local-machine paths.",
            },
            {
                "id": "generate_public_changelog",
                "action": "publish_public_changelog_replacement",
                "effect": "Keep private provenance in the workspace and publish a sanitized public history file.",
            },
            {
                "id": "exclude_public_history",
                "action": "remove_changelog_from_external_scope",
                "effect": "Exclude CHANGELOG.md from the default external source export.",
            },
        ],
    }


def build_scan(manifest: Path, max_bytes: int, limit: int) -> tuple[dict[str, Any], int]:
    plan, plan_exit = build_plan(manifest, 100000)
    included = plan.get("included_paths", [])
    findings: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for item in included:
        rel = item.get("path")
        if not isinstance(rel, str):
            continue
        path = REPO_DIR / rel
        skip, reason = is_binary_or_large(path, max_bytes)
        if skip:
            skipped.append({"path": rel, "reason": reason})
            continue
        try:
            findings.extend(scan_file(path, rel))
        except OSError as exc:
            skipped.append({"path": rel, "reason": f"read_failed:{type(exc).__name__}"})

    blockers = [f for f in findings if f["severity"] == "blocker"]
    warnings = [f for f in findings if f["severity"] == "warning"]
    verdict = "blocked" if blockers else ("needs_review" if warnings else "ok")
    grouped = summarize_findings(findings, limit)
    policy_plan = build_public_history_policy_plan(grouped, len(blockers), len(warnings))
    result = {
        "schema_version": 1,
        "kind": "external_source_safety_scan",
        "manifest": str(manifest),
        "verdict": verdict,
        "summary": {
            "planned_external_files": len(included),
            "scanned_files": len(included) - len(skipped),
            "skipped_files": len(skipped),
            "blockers": len(blockers),
            "warnings": len(warnings),
            "plan_exit_code": plan_exit,
        },
        "by_code": grouped["by_code"],
        "top_paths": grouped["top_paths"],
        "remediation_groups": grouped["remediation_groups"],
        "policy_plan": policy_plan,
        "findings": findings[:limit],
        "skipped": skipped[:limit],
    }
    return result, 1 if blockers else 0


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "scan_external_safety.py - external source safety scan",
        f"verdict={result['verdict']}",
        f"planned_external_files={summary['planned_external_files']}",
        f"blockers={summary['blockers']}",
        f"warnings={summary['warnings']}",
    ]
    for item in result.get("top_paths", [])[:10]:
        lines.append(f"- path {item['path']}: findings={item['findings']} blockers={item['blockers']} warnings={item['warnings']}")
    policy_plan = result.get("policy_plan", {})
    if policy_plan:
        lines.append("")
        lines.append("[policy_plan]")
        lines.append(f"decision={policy_plan.get('decision')}")
        lines.append(f"owner={policy_plan.get('owner')}")
        for option in policy_plan.get("options", []):
            lines.append(f"- {option.get('id')}: {option.get('action')}")
    for finding in result["findings"]:
        lines.append(f"- {finding['severity']} {finding['code']} {finding['path']}:{finding['line']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--strict", action="store_true", help="return non-zero when blockers exist")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="publish scope manifest")
    parser.add_argument("--max-bytes", type=int, default=1_000_000, help="skip files larger than this")
    parser.add_argument("--limit", type=int, default=120, help="sample limit for findings and skipped files")
    args = parser.parse_args(argv)

    result, exit_code = build_scan(args.manifest, args.max_bytes, max(0, args.limit))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return exit_code if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
