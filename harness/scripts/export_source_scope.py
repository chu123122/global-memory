#!/usr/bin/env python3
"""Build a read-only source export plan from the publish-scope manifest."""
from __future__ import annotations

import argparse
import io
import json
import subprocess
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

from check_publish_scope import DEFAULT_MANIFEST, classify, load_manifest, norm  # noqa: E402
from config import REPO_DIR  # noqa: E402


def git_files(args: list[str]) -> tuple[set[str], str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO_DIR), "ls-files", "-z", *args],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        return set(), detail or f"returncode={proc.returncode}"
    return {
        norm(item.decode("utf-8", errors="replace"))
        for item in proc.stdout.split(b"\0")
        if item
    }, ""


def path_group(path: str) -> str:
    first = path.split("/", 1)[0]
    if first in {"docs", "harness", "skills", "agents", "templates"}:
        return first
    if path.startswith(".github/"):
        return ".github"
    return "root"


def summarize_untracked(items: list[dict[str, str]], limit: int) -> dict[str, Any]:
    by_reason: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_group: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_match = Counter()

    for item in items:
        reason = item.get("reason", "unknown")
        by_reason[reason].append(item)
        by_group[path_group(item.get("path", ""))].append(item)
        by_match[item.get("match", "unknown")] += 1

    reason_summary = []
    for reason, group_items in by_reason.items():
        reason_summary.append({
            "reason": reason,
            "count": len(group_items),
            "paths": [item["path"] for item in group_items[:limit]],
        })
    reason_summary.sort(key=lambda item: (-int(item["count"]), str(item["reason"])))

    path_group_summary = []
    for group, group_items in by_group.items():
        path_group_summary.append({
            "group": group,
            "count": len(group_items),
            "paths": [item["path"] for item in group_items[:limit]],
        })
    path_group_summary.sort(key=lambda item: (-int(item["count"]), str(item["group"])))

    return {
        "by_reason": reason_summary,
        "by_path_group": path_group_summary,
        "by_match": [
            {"match": match, "count": count}
            for match, count in sorted(by_match.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def build_tracking_plan(
    untracked_included: list[dict[str, str]],
    excluded_private: list[dict[str, str]],
    unclassified: list[str],
    missing_external_files: list[str],
) -> dict[str, Any]:
    paths = [item["path"] for item in untracked_included]
    return {
        "action": "git_add_external_untracked",
        "ready": bool(paths) and not unclassified and not missing_external_files,
        "path_count": len(paths),
        "paths": paths,
        "command": ["git", "add", "--", *paths] if paths else [],
        "safety": {
            "excluded_private_paths": len(excluded_private),
            "unclassified_paths": len(unclassified),
            "missing_external_files": len(missing_external_files),
        },
    }


def build_plan(manifest_path: Path, limit: int) -> tuple[dict[str, Any], int]:
    manifest, manifest_findings = load_manifest(manifest_path)
    tracked, tracked_error = git_files([])
    worktree, worktree_error = git_files(["--cached", "--others", "--exclude-standard"])

    external = manifest.get("external_scope", {}) if isinstance(manifest.get("external_scope"), dict) else {}
    private = manifest.get("private_scope", {}) if isinstance(manifest.get("private_scope"), dict) else {}
    external_files = {norm(k): str(v) for k, v in (external.get("files") or {}).items()}
    external_prefixes = {norm(k): str(v) for k, v in (external.get("prefixes") or {}).items()}
    private_files = {norm(k): str(v) for k, v in (private.get("files") or {}).items()}
    private_prefixes = {norm(k): str(v) for k, v in (private.get("prefixes") or {}).items()}

    included: list[dict[str, str]] = []
    excluded_private: list[dict[str, str]] = []
    unclassified: list[str] = []

    if not tracked_error and not worktree_error:
        for path in sorted(worktree):
            private_kind, private_reason = classify(path, private_files, private_prefixes)
            if private_kind:
                excluded_private.append({
                    "path": path,
                    "match": private_kind,
                    "reason": private_reason,
                    "git_state": "tracked" if path in tracked else "untracked",
                })
                continue
            external_kind, external_reason = classify(path, external_files, external_prefixes)
            if external_kind:
                included.append({
                    "path": path,
                    "match": external_kind,
                    "reason": external_reason,
                    "git_state": "tracked" if path in tracked else "untracked",
                })
            else:
                unclassified.append(path)

    missing_external_files = sorted(
        path for path in external_files
        if not (REPO_DIR / path).exists()
    )
    untracked_included = [item for item in included if item["git_state"] == "untracked"]
    untracked_summary = summarize_untracked(untracked_included, limit)
    git_errors = []
    if tracked_error:
        git_errors.append({"source": "tracked", "detail": tracked_error})
    if worktree_error:
        git_errors.append({"source": "worktree", "detail": worktree_error})

    blockers = bool(manifest_findings or git_errors or missing_external_files or unclassified)
    warnings = bool(untracked_included)
    if blockers:
        verdict = "invalid"
    elif warnings:
        verdict = "ready_with_warnings"
    else:
        verdict = "ready"

    result = {
        "schema_version": 1,
        "kind": "source_export_scope_plan",
        "manifest": str(manifest_path),
        "decision_doc": manifest.get("decision_doc", "docs/publish-scope.md") if manifest else "docs/publish-scope.md",
        "verdict": verdict,
        "summary": {
            "tracked_files": len(tracked),
            "worktree_files": len(worktree),
            "export_included_paths": len(included),
            "untracked_included_paths": len(untracked_included),
            "excluded_private_paths": len(excluded_private),
            "unclassified_paths": len(unclassified),
            "missing_external_files": len(missing_external_files),
            "manifest_findings": len(manifest_findings),
            "git_errors": len(git_errors),
        },
        "untracked_included_summary": untracked_summary,
        "tracking_plan": build_tracking_plan(
            untracked_included,
            excluded_private,
            unclassified,
            missing_external_files,
        ),
        "included_paths": included[:limit],
        "untracked_included_paths": untracked_included[:limit],
        "excluded_private_paths": excluded_private[:limit],
        "unclassified_paths": unclassified[:limit],
        "missing_external_files": missing_external_files[:limit],
        "manifest_findings": manifest_findings,
        "git_errors": git_errors,
    }
    return result, 1 if blockers else 0


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "export_source_scope.py - read-only source export plan",
        f"verdict={result['verdict']}",
        f"export_included_paths={summary['export_included_paths']}",
        f"untracked_included_paths={summary['untracked_included_paths']}",
        f"excluded_private_paths={summary['excluded_private_paths']}",
        f"unclassified_paths={summary['unclassified_paths']}",
        f"missing_external_files={summary['missing_external_files']}",
    ]
    if result["untracked_included_paths"]:
        lines.append("")
        lines.append("[untracked_included_summary]")
        for item in result.get("untracked_included_summary", {}).get("by_path_group", []):
            lines.append(f"- {item['group']}: {item['count']}")
        tracking_plan = result.get("tracking_plan", {})
        if tracking_plan.get("ready"):
            lines.append("")
            lines.append("[tracking_plan]")
            lines.append(f"action={tracking_plan.get('action')}")
            lines.append(f"path_count={tracking_plan.get('path_count')}")
        lines.append("")
        lines.append("[untracked_included_paths]")
        for item in result["untracked_included_paths"]:
            lines.append(f"- {item['path']}")
    if result["missing_external_files"]:
        lines.append("")
        lines.append("[missing_external_files]")
        for path in result["missing_external_files"]:
            lines.append(f"- {path}")
    if result["unclassified_paths"]:
        lines.append("")
        lines.append("[unclassified_paths]")
        for path in result["unclassified_paths"]:
            lines.append(f"- {path}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--strict", action="store_true", help="return non-zero when the plan is invalid")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="publish scope manifest")
    parser.add_argument("--limit", type=int, default=80, help="sample limit for path lists")
    args = parser.parse_args(argv)

    result, exit_code = build_plan(args.manifest, max(0, args.limit))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return exit_code if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
