#!/usr/bin/env python3
"""Check tracked files against the publish-scope manifest."""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from collections import Counter
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

DEFAULT_MANIFEST = HARNESS_DIR / "publish_scope_manifest.json"


def norm(path: str) -> str:
    value = path.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def load_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [{"code": "manifest_missing", "path": str(path)}]
    except json.JSONDecodeError as exc:
        return {}, [{"code": "manifest_json_invalid", "path": str(path), "detail": str(exc)}]

    if not isinstance(data, dict):
        return {}, [{"code": "manifest_root_type", "detail": type(data).__name__}]
    if data.get("kind") != "global_memory_publish_scope_manifest":
        findings.append({"code": "manifest_kind_invalid", "detail": str(data.get("kind"))})
    for section in ("external_scope", "private_scope"):
        value = data.get(section)
        if not isinstance(value, dict):
            findings.append({"code": "manifest_section_missing", "section": section})
            continue
        for key in ("files", "prefixes"):
            if not isinstance(value.get(key), dict):
                findings.append({"code": "manifest_map_missing", "section": section, "key": key})
    for section in ("external_scope", "private_scope"):
        scope = data.get(section) if isinstance(data.get(section), dict) else {}
        for key in ("files", "prefixes"):
            entries = scope.get(key) if isinstance(scope.get(key), dict) else {}
            for raw in entries:
                item = norm(raw)
                if not item or item.startswith("/") or ":" in item:
                    findings.append({"code": "manifest_path_invalid", "section": section, "path": raw})
                if key == "prefixes" and not item.endswith("/"):
                    findings.append({"code": "manifest_prefix_invalid", "section": section, "path": raw})
    return data, findings


def git_ls_files() -> tuple[list[str], str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO_DIR), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        return [], detail or f"returncode={proc.returncode}"
    paths = [
        item.decode("utf-8", errors="replace")
        for item in proc.stdout.split(b"\0")
        if item
    ]
    return [norm(path) for path in paths], ""


def classify(path: str, files: dict[str, str], prefixes: dict[str, str]) -> tuple[str, str]:
    if path in files:
        return "file", files[path]
    for prefix, reason in prefixes.items():
        if path.startswith(prefix):
            return "prefix", reason
    return "", ""


def path_group(path: str) -> str:
    path = norm(path)
    if "/" not in path:
        return "root"
    return path.split("/", 1)[0]


def counter_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in counter.most_common()]


def summarize_classified_paths(items: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "by_reason": counter_rows(Counter(item.get("reason", "") or "(unspecified)" for item in items)),
        "by_path_group": counter_rows(Counter(path_group(item.get("path", "")) for item in items)),
        "by_match": counter_rows(Counter(item.get("match", "") or "(unknown)" for item in items)),
    }


def summarize_paths(paths: list[str]) -> dict[str, Any]:
    return {
        "by_path_group": counter_rows(Counter(path_group(path) for path in paths)),
    }


def build_decision_plan(private_hits: list[dict[str, str]], unclassified: list[str]) -> dict[str, Any]:
    if not private_hits and not unclassified:
        # No open publish-scope blocker: emit a resolved decision snapshot so the
        # output contract always carries a decision_plan.
        return {
            "decision": "publish_scope_boundary",
            "owner": "project_owner",
            "ready": True,
            "decision_doc": "docs/publish-scope.md",
            "required_when": {
                "private_tracked_paths": 0,
                "unclassified_tracked_paths": 0,
            },
            "selected": "public_showcase_with_private_split",
            "options": [
                {
                    "id": "keep_private_maturity_audit",
                    "action": "keep_private_tracked_data_in_repo",
                    "effect": "Keep using the release profile as a maturity audit, not publication readiness.",
                },
                {
                    "id": "split_clean_source_repository",
                    "action": "create_clean_public_source_repo",
                    "effect": "Separate public code assets from private memory/task data.",
                },
                {
                    "id": "move_private_data",
                    "action": "migrate_private_data_to_private_repo",
                    "effect": "Move personal memory data out of the public repo.",
                },
                {
                    "id": "convert_selected_fixtures",
                    "action": "anonymize_selected_fixtures",
                    "effect": "Convert specific private data into anonymized fixtures.",
                },
            ],
        }
    return {
        "decision": "publish_scope_boundary",
        "owner": "project_owner",
        "ready": False,
        "decision_doc": "docs/publish-scope.md",
        "required_when": {
            "private_tracked_paths": len(private_hits),
            "unclassified_tracked_paths": len(unclassified),
        },
        "options": [
            {
                "id": "split_clean_source_repository",
                "action": "publish_only_external_scope",
                "effect": "Create a clean source repository containing only the manifest external scope.",
            },
            {
                "id": "move_private_data",
                "action": "move_private_scope_to_private_storage",
                "effect": "Keep personal memory, project, experiment, archive, and report data out of the public source tree.",
            },
            {
                "id": "convert_selected_fixtures",
                "action": "replace_private_context_with_anonymized_fixtures",
                "effect": "Publish selected examples only after anonymization and explicit documentation.",
            },
            {
                "id": "keep_private_maturity_audit",
                "action": "do_not_publish_source",
                "effect": "Keep the repository private and use the OSS profile only as a readiness audit.",
            },
        ],
    }


def build_result(manifest_path: Path, limit: int) -> tuple[dict[str, Any], int]:
    manifest, manifest_findings = load_manifest(manifest_path)
    tracked, git_error = git_ls_files()

    external = manifest.get("external_scope", {}) if isinstance(manifest.get("external_scope"), dict) else {}
    private = manifest.get("private_scope", {}) if isinstance(manifest.get("private_scope"), dict) else {}
    policy = manifest.get("policy", {}) if isinstance(manifest.get("policy"), dict) else {}
    external_files = {norm(k): str(v) for k, v in (external.get("files") or {}).items()}
    external_prefixes = {norm(k): str(v) for k, v in (external.get("prefixes") or {}).items()}
    private_files = {norm(k): str(v) for k, v in (private.get("files") or {}).items()}
    private_prefixes = {norm(k): str(v) for k, v in (private.get("prefixes") or {}).items()}

    private_hits: list[dict[str, str]] = []
    external_hits: list[str] = []
    unclassified: list[str] = []

    if not git_error:
        for path in tracked:
            private_kind, private_reason = classify(path, private_files, private_prefixes)
            if private_kind:
                private_hits.append({"path": path, "match": private_kind, "reason": private_reason})
                continue
            external_kind, _ = classify(path, external_files, external_prefixes)
            if external_kind:
                external_hits.append(path)
            else:
                unclassified.append(path)

    block_private = bool(policy.get("block_on_private_tracked", True))
    block_unclassified = bool(policy.get("block_on_unclassified_tracked", False))
    blocker = bool(manifest_findings or git_error)
    blocker = blocker or (block_private and bool(private_hits))
    blocker = blocker or (block_unclassified and bool(unclassified))
    verdict = "blocked" if blocker else "ok"

    result = {
        "schema_version": 1,
        "kind": "publish_scope_check",
        "manifest": str(manifest_path),
        "decision_doc": manifest.get("decision_doc", "docs/publish-scope.md") if manifest else "docs/publish-scope.md",
        "verdict": verdict,
        "summary": {
            "tracked_files": len(tracked),
            "external_scope_files": len(external_hits),
            "private_tracked_paths": len(private_hits),
            "unclassified_tracked_paths": len(unclassified),
            "manifest_findings": len(manifest_findings),
            "git_error": bool(git_error),
        },
        "manifest_findings": manifest_findings,
        "private_tracked_summary": summarize_classified_paths(private_hits),
        "private_tracked_paths": private_hits[:limit],
        "unclassified_tracked_summary": summarize_paths(unclassified),
        "unclassified_tracked_paths": unclassified[:limit],
        "decision_plan": build_decision_plan(private_hits, unclassified),
        "scope": {
            "external_files": sorted(external_files),
            "external_prefixes": sorted(external_prefixes),
            "private_files": sorted(private_files),
            "private_prefixes": sorted(private_prefixes),
        },
    }
    if git_error:
        result["git_failure"] = git_error
    return result, 1 if blocker else 0


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "check_publish_scope.py - tracked file publish-scope audit",
        f"verdict={result['verdict']}",
        f"tracked_files={summary['tracked_files']}",
        f"external_scope_files={summary['external_scope_files']}",
        f"private_tracked_paths={summary['private_tracked_paths']}",
        f"unclassified_tracked_paths={summary['unclassified_tracked_paths']}",
    ]
    if result["private_tracked_paths"]:
        decision_plan = result.get("decision_plan", {})
        if decision_plan:
            lines.append("")
            lines.append("[decision_plan]")
            lines.append(f"decision={decision_plan.get('decision')}")
            lines.append(f"owner={decision_plan.get('owner')}")
        summary_rows = result.get("private_tracked_summary", {})
        path_groups = summary_rows.get("by_path_group", []) if isinstance(summary_rows, dict) else []
        reasons = summary_rows.get("by_reason", []) if isinstance(summary_rows, dict) else []
        if path_groups:
            lines.append("")
            lines.append("[private_tracked_summary.by_path_group]")
            for row in path_groups:
                lines.append(f"- {row['key']}: {row['count']}")
        if reasons:
            lines.append("")
            lines.append("[private_tracked_summary.by_reason]")
            for row in reasons:
                lines.append(f"- {row['key']}: {row['count']}")
        lines.append("")
        lines.append("[private_tracked_paths]")
        for item in result["private_tracked_paths"]:
            lines.append(f"- {item['path']} ({item['reason']})")
    if result["unclassified_tracked_paths"]:
        lines.append("")
        lines.append("[unclassified_tracked_paths]")
        for path in result["unclassified_tracked_paths"]:
            lines.append(f"- {path}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--strict", action="store_true", help="return non-zero on blockers")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="publish scope manifest")
    parser.add_argument("--limit", type=int, default=80, help="sample limit for path lists")
    args = parser.parse_args(argv)

    result, exit_code = build_result(args.manifest, max(0, args.limit))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return exit_code if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
