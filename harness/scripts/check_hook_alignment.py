#!/usr/bin/env python3
"""
check_hook_alignment.py — compare hook source-of-truth surfaces.

Read-only drift check across:
- harness/hook_manifest.json source of truth
- bootstrap.py hooks_json() install template
- current Claude settings.json runtime hooks
- docs/scripts-registry.md Hook section

Use --strict to fail when drift is found.
"""
from __future__ import annotations

import argparse
import importlib.util
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
from config import CLAUDE_SETTINGS, HARNESS_DIR, REPO_DIR  # noqa: E402

BOOTSTRAP_PATH = REPO_DIR / "bootstrap.py"
MANIFEST_PATH = HARNESS_DIR / "hook_manifest.json"
REGISTRY_PATH = REPO_DIR / "docs" / "scripts-registry.md"
ALLOWED_FAILURE_ACTIONS = {"BLOCK", "WARN", "REPORT", "NONE"}


def default_settings_path() -> Path:
    return CLAUDE_SETTINGS


def load_bootstrap_sources(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not path.exists():
        return {}, None
    spec = importlib.util.spec_from_file_location("_global_memory_bootstrap_for_hook_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import bootstrap: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hooks_json = getattr(module, "hooks_json", None)
    if not callable(hooks_json):
        raise RuntimeError(f"bootstrap has no callable hooks_json(): {path}")
    status_line_json = getattr(module, "status_line_json", None)
    status_line = status_line_json() if callable(status_line_json) else None
    return hooks_json(), status_line


def load_runtime_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_hook_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def command_to_relpath(command: str) -> str | None:
    normalized = command.replace("\\", "/").strip()
    match = re.search(r"/harness/(.+?\.py)(?:\s|$|\"|')", normalized)
    if match:
        return match.group(1).lstrip("./")
    match = re.search(r"(?:^|\s)harness/(.+?\.py)(?:\s|$|\"|')", normalized)
    if match:
        return match.group(1).lstrip("./")
    return None


def collect_hook_entries(hooks: dict[str, Any], status_line: dict[str, Any] | None = None) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for event, groups in sorted(hooks.items()):
        if not isinstance(groups, list):
            continue
        for group_index, group in enumerate(groups):
            if not isinstance(group, dict):
                continue
            matcher = str(group.get("matcher", ""))
            hook_items = group.get("hooks", [])
            if not isinstance(hook_items, list):
                continue
            for hook_index, hook in enumerate(hook_items):
                if not isinstance(hook, dict):
                    continue
                command = str(hook.get("command", ""))
                relpath = command_to_relpath(command)
                if relpath:
                    entries.append({
                        "event": event,
                        "matcher": matcher,
                        "relpath": relpath,
                        "order": f"{group_index}.{hook_index}",
                        "command": command,
                    })

    if isinstance(status_line, dict):
        command = str(status_line.get("command", ""))
        relpath = command_to_relpath(command)
        if relpath:
            entries.append({
                "event": "statusLine",
                "matcher": "",
                "relpath": relpath,
                "order": "0.0",
                "command": command,
            })
    return entries


def collect_manifest_entries(manifest: dict[str, Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    hooks = manifest.get("hooks", {})
    if isinstance(hooks, dict):
        for event, groups in sorted(hooks.items()):
            if not isinstance(groups, list):
                continue
            for group_index, group in enumerate(groups):
                if not isinstance(group, dict):
                    continue
                matcher = str(group.get("matcher", ""))
                hook_items = group.get("hooks", [])
                if not isinstance(hook_items, list):
                    continue
                for hook_index, hook in enumerate(hook_items):
                    if not isinstance(hook, dict) or not hook.get("path"):
                        continue
                    entries.append({
                        "event": event,
                        "matcher": matcher,
                        "relpath": str(hook["path"]).replace("\\", "/").lstrip("./"),
                        "order": f"{group_index}.{hook_index}",
                        "command": "",
                    })
    status_line = manifest.get("statusLine")
    if isinstance(status_line, dict) and status_line.get("path"):
        entries.append({
            "event": "statusLine",
            "matcher": "",
            "relpath": str(status_line["path"]).replace("\\", "/").lstrip("./"),
            "order": "0.0",
            "command": "",
        })
    return entries


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    invalid_paths: set[str] = set()
    missing_files: set[str] = set()
    invalid_actions: set[str] = set()
    duplicate_entries: set[str] = set()
    seen: set[tuple[str, str, str]] = set()

    if not isinstance(manifest.get("hooks"), dict):
        findings.append({
            "kind": "manifest_schema",
            "severity": "high",
            "count": 1,
            "relpaths": [],
            "detail": "hook_manifest.json must contain a hooks object.",
        })
    if not isinstance(manifest.get("statusLine"), dict):
        findings.append({
            "kind": "manifest_schema",
            "severity": "high",
            "count": 1,
            "relpaths": [],
            "detail": "hook_manifest.json must contain a statusLine object.",
        })

    for entry in collect_manifest_entries(manifest):
        relpath = entry["relpath"]
        rel = Path(relpath)
        key = (entry["event"], entry["matcher"], relpath)
        if key in seen:
            duplicate_entries.add(f"{entry['event']}:{entry['matcher']}:{relpath}")
        seen.add(key)
        if rel.is_absolute() or ".." in rel.parts or rel.suffix != ".py":
            invalid_paths.add(relpath)
            continue
        if not (HARNESS_DIR / rel).is_file():
            missing_files.add(relpath)

    hooks = manifest.get("hooks", {})
    if isinstance(hooks, dict):
        for groups in hooks.values():
            if not isinstance(groups, list):
                continue
            for group in groups:
                if not isinstance(group, dict):
                    continue
                for hook in group.get("hooks", []):
                    if not isinstance(hook, dict):
                        continue
                    action = str(hook.get("failure_action", ""))
                    if action not in ALLOWED_FAILURE_ACTIONS:
                        invalid_actions.add(str(hook.get("path", "<missing path>")))
    status_line = manifest.get("statusLine")
    if isinstance(status_line, dict):
        action = str(status_line.get("failure_action", ""))
        if action not in ALLOWED_FAILURE_ACTIONS:
            invalid_actions.add(str(status_line.get("path", "<statusLine>")))

    for kind, relpaths, detail in [
        ("manifest_invalid_path", invalid_paths, "Hook manifest contains absolute, parent-relative, or non-.py paths."),
        ("manifest_missing_file", missing_files, "Hook manifest points to files that do not exist under harness/."),
        ("manifest_invalid_failure_action", invalid_actions, "Hook manifest failure_action must be BLOCK, WARN, REPORT, or NONE."),
        ("manifest_duplicate_entry", duplicate_entries, "Hook manifest repeats the same event/matcher/path entry."),
    ]:
        finding = make_finding(kind, "high", relpaths, detail)
        if finding:
            findings.append(finding)
    return findings


def registry_hook_relpaths(path: Path) -> set[str]:
    if not path.exists():
        return set()

    text = path.read_text(encoding="utf-8", errors="replace")
    in_hooks_section = False
    relpaths: set[str] = set()
    code_path = re.compile(r"`([^`]+?\.py)`")

    for line in text.splitlines():
        if line.startswith("## 1. Hooks"):
            in_hooks_section = True
            continue
        if in_hooks_section and line.startswith("## "):
            break
        if not in_hooks_section or "ORPHAN" in line or "DEPRECATED" in line:
            continue
        for relpath in code_path.findall(line):
            relpath = relpath.lstrip("./").replace("\\", "/")
            if relpath.startswith("hooks/"):
                relpaths.add(relpath)

    return relpaths


def relpath_set(entries: list[dict[str, str]]) -> set[str]:
    return {entry["relpath"] for entry in entries}


def make_finding(kind: str, severity: str, relpaths: set[str], detail: str) -> dict[str, Any] | None:
    if not relpaths:
        return None
    return {
        "kind": kind,
        "severity": severity,
        "count": len(relpaths),
        "relpaths": sorted(relpaths),
        "detail": detail,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 when drift is found")
    ap.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    ap.add_argument("--bootstrap", type=Path, default=BOOTSTRAP_PATH)
    ap.add_argument("--settings", type=Path, default=default_settings_path())
    ap.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    args = ap.parse_args(argv)

    manifest = load_hook_manifest(args.manifest)
    bootstrap_hooks, bootstrap_status_line = load_bootstrap_sources(args.bootstrap)
    settings = load_runtime_settings(args.settings)

    manifest_entries = collect_manifest_entries(manifest)
    bootstrap_entries = collect_hook_entries(bootstrap_hooks, bootstrap_status_line)
    runtime_entries = collect_hook_entries(settings.get("hooks", {}), settings.get("statusLine"))
    registry_hooks = registry_hook_relpaths(args.registry)

    manifest_set = relpath_set(manifest_entries)
    bootstrap_set = relpath_set(bootstrap_entries)
    runtime_set = relpath_set(runtime_entries)

    findings = validate_manifest(manifest) + [
        make_finding(
            "manifest_not_in_bootstrap",
            "high",
            manifest_set - bootstrap_set,
            "Hook manifest lists hooks that bootstrap.py would not install.",
        ),
        make_finding(
            "bootstrap_not_in_manifest",
            "high",
            bootstrap_set - manifest_set,
            "bootstrap.py contains hooks missing from hook_manifest.json.",
        ),
        make_finding(
            "manifest_not_in_runtime",
            "high",
            manifest_set - runtime_set,
            "Hook manifest lists hooks missing from current runtime settings.",
        ),
        make_finding(
            "runtime_not_in_bootstrap",
            "high",
            runtime_set - bootstrap_set,
            "Runtime settings contain hooks that bootstrap.py would not install.",
        ),
        make_finding(
            "bootstrap_not_in_runtime",
            "high",
            bootstrap_set - runtime_set,
            "bootstrap.py contains hooks missing from the current runtime settings.",
        ),
        make_finding(
            "registry_not_in_runtime",
            "medium",
            registry_hooks - runtime_set,
            "Hook registry lists active hooks missing from current runtime settings.",
        ),
        make_finding(
            "registry_not_in_manifest",
            "medium",
            registry_hooks - manifest_set,
            "Hook registry lists active hooks missing from hook_manifest.json.",
        ),
    ]
    findings = [finding for finding in findings if finding is not None]

    result = {
        "schema_version": 1,
        "kind": "hook_alignment_check",
        "sources": {
            "manifest": str(args.manifest),
            "bootstrap": str(args.bootstrap),
            "settings": str(args.settings),
            "registry": str(args.registry),
        },
        "totals": {
            "manifest_hooks": len(manifest_set),
            "bootstrap_hooks": len(bootstrap_set),
            "runtime_hooks": len(runtime_set),
            "registry_active_hooks": len(registry_hooks),
            "findings": len(findings),
        },
        "manifest_hooks": sorted(manifest_set),
        "bootstrap_hooks": sorted(bootstrap_set),
        "runtime_hooks": sorted(runtime_set),
        "registry_active_hooks": sorted(registry_hooks),
        "findings": findings,
        "verdict": "aligned" if not findings else "drift",
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("  check_hook_alignment")
        print("=" * 60)
        print(f"  manifest hooks:  {len(manifest_set)}")
        print(f"  bootstrap hooks: {len(bootstrap_set)}")
        print(f"  runtime hooks:   {len(runtime_set)}")
        print(f"  registry hooks:  {len(registry_hooks)}")
        print(f"  findings:        {len(findings)}")
        print()
        if findings:
            for finding in findings:
                print(f"[{finding['severity'].upper()}] {finding['kind']} ({finding['count']})")
                print(f"  {finding['detail']}")
                for relpath in finding["relpaths"]:
                    print(f"  - {relpath}")
                print()
        else:
            print("[OK] hook sources are aligned")
            print()
        print(f"hook_alignment={result['verdict']} findings={len(findings)}")
        print("=" * 60)

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
