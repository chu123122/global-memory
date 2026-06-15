#!/usr/bin/env python3
"""Register a harness script in both registry Markdown and capability manifest.

Default mode is dry-run. Use --apply to write files.
"""
import argparse
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = SCRIPT_DIR.parents[1]
REGISTRY_REL = Path("docs/scripts-registry.md")
MANIFEST_REL = Path("harness/capability_manifest.json")
GENERAL_TOOLS_HEADING = "## 3. Manual 治理脚本"
ALLOWED_TRIGGERS = {
    "Hook",
    "Gate",
    "Smoke",
    "Manual",
    "CronOrDaemon",
    "Library",
    "ORPHAN",
    "DEPRECATED",
}
ALLOWED_FAILURES = {"BLOCK", "WARN", "REPORT", "NONE"}


class RegisterError(Exception):
    """User-facing registration error."""


@dataclass(frozen=True)
class Registration:
    script: str
    capability: str
    purpose: str
    trigger: str
    failure: str


def normalize_harness_rel(path_text: str, harness_dir: Path) -> str:
    """Return POSIX harness-relative .py path after boundary/existence checks."""
    path_text = path_text.replace("\\", "/")
    rel = Path(path_text)
    if rel.is_absolute():
        raise RegisterError("script path must be relative to harness/")
    if ".." in rel.parts:
        raise RegisterError("script path cannot contain ..")
    if rel.suffix != ".py":
        raise RegisterError("script path must point to a .py file")
    script_path = (harness_dir / rel).resolve()
    harness_resolved = harness_dir.resolve()
    try:
        script_path.relative_to(harness_resolved)
    except ValueError as exc:
        raise RegisterError("script path escapes harness/") from exc
    if not script_path.is_file():
        raise RegisterError(f"script does not exist under harness/: {rel.as_posix()}")
    return rel.as_posix()


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RegisterError(f"capability manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegisterError(f"capability manifest is invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RegisterError("capability manifest root must be an object")
    if not isinstance(data.get("capabilities"), list):
        raise RegisterError("capability manifest must contain capabilities[]")
    return data


def update_manifest(data: dict[str, Any], reg: Registration) -> tuple[dict[str, Any], list[dict[str, str]], bool]:
    capabilities = data.get("capabilities", [])
    target = None
    for capability in capabilities:
        if isinstance(capability, dict) and capability.get("id") == reg.capability:
            target = capability
            break
    if target is None:
        raise RegisterError(f"capability id not found: {reg.capability}")
    scripts = target.get("scripts")
    if not isinstance(scripts, list):
        raise RegisterError(f"capability {reg.capability} scripts must be a list")

    normalized = [str(item).replace("\\", "/") for item in scripts]
    deduped = list(dict.fromkeys(normalized))
    changed = deduped != normalized
    actions: list[dict[str, str]] = []
    if reg.script not in deduped:
        deduped.append(reg.script)
        changed = True
        actions.append({
            "kind": "manifest_add_script",
            "capability": reg.capability,
            "script": reg.script,
        })
    elif changed:
        actions.append({
            "kind": "manifest_dedupe_scripts",
            "capability": reg.capability,
            "script": reg.script,
        })
    target["scripts"] = deduped
    return data, actions, changed


def markdown_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def registry_row(reg: Registration) -> str:
    return (
        f"| `{reg.script}` | {markdown_escape(reg.purpose)} | "
        f"{markdown_escape(reg.trigger)} | {markdown_escape(reg.failure)} |"
    )


def find_general_table(lines: list[str]) -> tuple[int, int, int]:
    heading_idx = None
    for idx, line in enumerate(lines):
        if line.startswith(GENERAL_TOOLS_HEADING):
            heading_idx = idx
            break
    if heading_idx is None:
        raise RegisterError(f"registry heading not found: {GENERAL_TOOLS_HEADING}")

    header_idx = None
    sep_idx = None
    for idx in range(heading_idx + 1, len(lines)):
        line = lines[idx]
        if idx != heading_idx + 1 and line.startswith("## "):
            break
        if line.startswith("| 脚本 |") and idx + 1 < len(lines) and lines[idx + 1].startswith("|---"):
            header_idx = idx
            sep_idx = idx + 1
            break
    if header_idx is None or sep_idx is None:
        raise RegisterError("registry general tools table header not found")

    end_idx = sep_idx + 1
    while end_idx < len(lines) and lines[end_idx].startswith("|"):
        end_idx += 1
    return header_idx, sep_idx, end_idx


def update_registry(text: str, reg: Registration) -> tuple[str, list[dict[str, str]], bool]:
    lines = text.splitlines()
    _header_idx, sep_idx, end_idx = find_general_table(lines)
    new_row = registry_row(reg)
    script_token = f"`{reg.script}`"
    matching_indices = [idx for idx in range(sep_idx + 1, end_idx) if script_token in lines[idx]]
    actions: list[dict[str, str]] = []
    changed = False
    if not matching_indices:
        lines.insert(end_idx, new_row)
        actions.append({"kind": "registry_add_row", "script": reg.script})
        changed = True
    else:
        first = matching_indices[0]
        if lines[first] != new_row:
            lines[first] = new_row
            actions.append({"kind": "registry_update_row", "script": reg.script})
            changed = True
        for idx in reversed(matching_indices[1:]):
            del lines[idx]
            changed = True
        if len(matching_indices) > 1:
            actions.append({"kind": "registry_dedupe_rows", "script": reg.script})

    trailing_newline = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + trailing_newline, actions, changed


def build_plan(repo_root: Path, reg: Registration) -> tuple[dict[str, Any], dict[Path, str]]:
    repo_root = repo_root.resolve()
    manifest_path = repo_root / MANIFEST_REL
    registry_path = repo_root / REGISTRY_REL
    if not registry_path.is_file():
        raise RegisterError(f"scripts registry not found: {registry_path}")

    manifest_data = load_manifest(manifest_path)
    updated_manifest, manifest_actions, manifest_changed = update_manifest(manifest_data, reg)
    old_manifest_text = manifest_path.read_text(encoding="utf-8")
    new_manifest_text = json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n"
    manifest_changed = manifest_changed or new_manifest_text != old_manifest_text

    old_registry_text = registry_path.read_text(encoding="utf-8")
    new_registry_text, registry_actions, registry_changed = update_registry(old_registry_text, reg)

    writes: dict[Path, str] = {}
    changed_files: list[str] = []
    if manifest_changed:
        writes[manifest_path] = new_manifest_text
        changed_files.append(MANIFEST_REL.as_posix())
    if registry_changed:
        writes[registry_path] = new_registry_text
        changed_files.append(REGISTRY_REL.as_posix())

    actions = manifest_actions + registry_actions
    warnings: list[str] = []
    if not actions and not changed_files:
        warnings.append("script is already registered with matching metadata")

    result = {
        "schema_version": 1,
        "kind": "script_registration",
        "script": reg.script,
        "capability": reg.capability,
        "dry_run": True,
        "would_change": bool(changed_files),
        "changed_files": changed_files,
        "actions": actions,
        "warnings": warnings,
    }
    return result, writes


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def emit_text(payload: dict[str, Any]) -> None:
    mode = "DRY-RUN" if payload.get("dry_run") else "APPLIED"
    print(f"{mode} register_script: {payload.get('script', '')}")
    if payload.get("error"):
        print(f"ERROR: {payload['error']}", file=sys.stderr)
        return
    print(f"would_change={payload.get('would_change')}")
    for path in payload.get("changed_files", []):
        print(f"changed_file: {path}")
    for action in payload.get("actions", []):
        print(f"action: {action.get('kind')} {action.get('script', '')}")
    for warning in payload.get("warnings", []):
        print(f"warning: {warning}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", help="harness-relative Python script path, e.g. scripts/foo.py")
    parser.add_argument("--capability", required=True, help="capability id in harness/capability_manifest.json")
    parser.add_argument("--purpose", required=True, help="human-readable purpose for docs/scripts-registry.md")
    parser.add_argument("--trigger", required=True, choices=sorted(ALLOWED_TRIGGERS), help="registry trigger category")
    parser.add_argument("--failure", required=True, choices=sorted(ALLOWED_FAILURES), help="registry failure action")
    parser.add_argument("--apply", action="store_true", help="write registry and manifest; default is dry-run")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT, help=f"repository root (default {DEFAULT_REPO_ROOT})")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        script = normalize_harness_rel(args.script, repo_root / "harness")
        reg = Registration(
            script=script,
            capability=args.capability,
            purpose=args.purpose,
            trigger=args.trigger,
            failure=args.failure,
        )
        payload, writes = build_plan(repo_root, reg)
        payload["dry_run"] = not args.apply
        if args.apply:
            for path, text in writes.items():
                path.write_text(text, encoding="utf-8")
        if args.json:
            emit_json(payload)
        else:
            emit_text(payload)
        return 0
    except RegisterError as exc:
        payload = {
            "schema_version": 1,
            "kind": "script_registration",
            "dry_run": not args.apply,
            "would_change": False,
            "changed_files": [],
            "actions": [],
            "warnings": [],
            "error": str(exc),
        }
        if args.json:
            emit_json(payload)
        else:
            emit_text(payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
