#!/usr/bin/env python3
"""change_packet.py -- pre-implementation intent/scope gate for global-memory.

Creates and validates Change Packets: lightweight PR-shaped artifacts that
record motivation, scope, evidence and risk before code is modified.
"""
from __future__ import annotations

import argparse
import io
import json
import re
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

HARNESS_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = HARNESS_DIR.parent
TEMPLATE_PATH = REPO_DIR / "templates" / "change_packet.md.tmpl"
DEFAULT_OUTPUT_DIR = REPO_DIR / "quality" / "change-packets"

VALID_RISK_TIERS = {0, 1, 2, 3}
VALID_STATUSES = {"draft", "submitted", "approved", "rejected"}

REQUIRED_SECTIONS = (
    "Motivation (WHY)",
    "Scope (WHAT)",
    "Approach (HOW)",
    "Evidence & Verification",
    "Risks & Rollback",
    "Intent Alignment",
)

FRONTMATTER_REQUIRED = ("packet_id", "created", "risk_tier", "status")

PLACEHOLDER_PATTERNS = [
    re.compile(r"^<.*>$"),
    re.compile(r"^\(.*\)$"),
    re.compile(r"^TODO", re.IGNORECASE),
    re.compile(r"^PLACEHOLDER", re.IGNORECASE),
]

TEMPLATE_PROMPT_PATTERNS = [
    re.compile(r"^what\b.*(\?|)$", re.IGNORECASE),
    re.compile(r"^how\b.*(\?|)$", re.IGNORECASE),
    re.compile(r"^why\b.*(\?|)$", re.IGNORECASE),
    re.compile(r"^does this\b.*(\?|)$", re.IGNORECASE),
    re.compile(r"^key design choices", re.IGNORECASE),
    re.compile(r"^alternatives considered", re.IGNORECASE),
]

SCOPE_HEADING_LINES = {
    "files to modify:",
    "files not touched:",
    "new files to create:",
    "files to modify",
    "files not touched",
    "new files to create",
}

CLAUDE_MD_PATH = "agents/CLAUDE.md"


def _is_placeholder(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped == "-" or stripped == "none":
        return True
    for pat in PLACEHOLDER_PATTERNS:
        if pat.match(stripped):
            return True
    for pat in TEMPLATE_PROMPT_PATTERNS:
        if pat.match(stripped):
            return True
    if ":" in stripped:
        _, _, after = stripped.partition(":")
        after = after.strip()
        if after and re.match(r"^<.*>$", after):
            return True
    return False


def _is_scope_heading(text: str) -> bool:
    return text.strip().lower().rstrip(":") + ":" in SCOPE_HEADING_LINES or text.strip().lower() in SCOPE_HEADING_LINES


def _section_has_substance(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip().lstrip("- ")
        if stripped and not _is_placeholder(stripped) and not _is_scope_heading(stripped):
            return True
    return False


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end].strip()
    body = content[end + 3:].strip()
    fm: dict[str, Any] = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val.isdigit():
                fm[key.strip()] = int(val)
            else:
                fm[key.strip()] = val
    return fm, body


def _extract_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        heading_match = re.match(r"^##\s+(.+)$", line)
        if heading_match:
            current = heading_match.group(1).strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _has_command_like_line(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip().lstrip("- ")
        if re.search(r"(python|pytest|bash|powershell|git|npm|cargo)\s", stripped, re.IGNORECASE):
            return True
        if re.search(r"`[^`]+`", stripped):
            return True
        if "not applicable" in stripped.lower():
            return True
    return False


def _scope_mentions_claude_md(lines: list[str]) -> bool:
    in_exclusion = False
    for line in lines:
        lower = line.lower().strip()
        if "not touched" in lower or "not modified" in lower or "exclusion" in lower:
            in_exclusion = True
            continue
        if lower.startswith("files to modify") or lower.startswith("new files"):
            in_exclusion = False
            continue
        if line.strip().startswith("#"):
            in_exclusion = False
        if not in_exclusion and (CLAUDE_MD_PATH in line or "agents/CLAUDE" in line):
            return True
    return False


def _scope_has_change_file(lines: list[str]) -> bool:
    in_change_section = False
    for line in lines:
        stripped = line.strip().lstrip("- ")
        lower = stripped.lower().strip()
        if _is_scope_heading(stripped):
            in_change_section = lower.rstrip(":") in {"files to modify", "new files to create"}
            continue
        if not in_change_section:
            continue
        if stripped and not _is_placeholder(stripped):
            return True
    return False


def _has_claude_md_justification(body: str) -> bool:
    lower = body.lower()
    patterns = [
        "justification for modifying agents/claude",
        "why agents/claude.md must change",
        "cannot be solved via agents.md alone",
        "cannot be solved via repository entry alone",
    ]
    for p in patterns:
        if p in lower:
            return True
    sections = _extract_sections(body)
    for name, lines in sections.items():
        if "justification" in name.lower() and "claude" in name.lower():
            return _section_has_substance(lines)
    return False


def validate_packet(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return {
            "kind": "change_packet_validation",
            "path": str(path),
            "verdict": "ERROR",
            "errors": [f"File not found: {path}"],
            "warnings": [],
        }

    content = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(content)

    for field in FRONTMATTER_REQUIRED:
        if field not in fm or fm[field] == "" or _is_placeholder(str(fm[field])):
            errors.append(f"Missing or placeholder frontmatter field: {field}")

    if "risk_tier" in fm:
        try:
            tier = int(fm["risk_tier"])
            if tier not in VALID_RISK_TIERS:
                errors.append(f"risk_tier must be 0-3, got: {tier}")
        except (ValueError, TypeError):
            errors.append(f"risk_tier must be integer 0-3, got: {fm['risk_tier']}")

    if "status" in fm:
        if fm["status"] not in VALID_STATUSES:
            errors.append(f"Invalid status '{fm['status']}', must be one of: {', '.join(sorted(VALID_STATUSES))}")

    sections = _extract_sections(body)

    for req in REQUIRED_SECTIONS:
        if req not in sections:
            errors.append(f"Missing required section: ## {req}")
        else:
            if not _section_has_substance(sections[req]):
                is_draft = fm.get("status") == "draft"
                if is_draft:
                    warnings.append(f"Section '## {req}' has no substantive content (allowed in draft)")
                else:
                    errors.append(f"Section '## {req}' has no substantive content")

    scope_lines = sections.get("Scope (WHAT)", [])
    if not _scope_has_change_file(scope_lines) and fm.get("status") != "draft":
        errors.append("Scope must list files to modify (or explicit 'none' only in draft)")

    if _scope_mentions_claude_md(scope_lines):
        if not _has_claude_md_justification(body):
            errors.append(
                f"Scope includes {CLAUDE_MD_PATH} but no explicit justification section found. "
                "Add a 'Justification for modifying agents/CLAUDE.md' heading or equivalent."
            )

    ev_lines = sections.get("Evidence & Verification", [])
    if ev_lines and _section_has_substance(ev_lines):
        if not _has_command_like_line(ev_lines):
            warnings.append("Evidence & Verification has no command-like line or 'not applicable' marker")

    verdict = "PASS" if not errors else "BLOCK"
    return {
        "kind": "change_packet_validation",
        "path": str(path),
        "verdict": verdict,
        "errors": errors,
        "warnings": warnings,
    }


def cmd_new(args: argparse.Namespace) -> int:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    now = datetime.now()
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:40]
    packet_id = now.strftime("%Y%m%d-%H%M%S") + "-" + slug
    created = now.strftime("%Y-%m-%dT%H:%M:%S")

    content = template
    content = content.replace("<YYYYMMDD-HHMMSS-slug>", packet_id)
    content = content.replace("<YYYY-MM-DDTHH:MM:SS>", created)
    content = content.replace("<short title>", args.title)
    if args.task:
        content = content.replace("<task-id>", args.task)
    if args.risk_tier is not None:
        content = content.replace("risk_tier: 1", f"risk_tier: {args.risk_tier}")

    out_dir = Path(args.out) if args.out else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{packet_id}.md"
    out_path.write_text(content, encoding="utf-8")

    if args.json:
        print(json.dumps({"kind": "change_packet_created", "path": str(out_path), "packet_id": packet_id}, indent=2))
    else:
        print(f"Created: {out_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    result = validate_packet(path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Packet: {result['path']}")
        print(f"Verdict: {result['verdict']}")
        if result["errors"]:
            print("\nErrors:")
            for e in result["errors"]:
                print(f"  - {e}")
        if result["warnings"]:
            print("\nWarnings:")
            for w in result["warnings"]:
                print(f"  - {w}")

    return 0 if result["verdict"] == "PASS" else 1


def cmd_status(args: argparse.Namespace) -> int:
    packet_dir = DEFAULT_OUTPUT_DIR
    if not packet_dir.exists():
        packets: list[dict[str, Any]] = []
    else:
        packets = []
        for f in sorted(packet_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            fm, _ = _parse_frontmatter(content)
            packets.append({
                "file": f.name,
                "packet_id": fm.get("packet_id", ""),
                "status": fm.get("status", "unknown"),
                "risk_tier": fm.get("risk_tier", "?"),
            })

    if args.json:
        print(json.dumps({"kind": "change_packet_status", "packets": packets, "count": len(packets)}, indent=2))
    else:
        if not packets:
            print("No change packets found.")
        else:
            print(f"Change packets ({len(packets)}):\n")
            for p in packets:
                print(f"  [{p['status']}] tier={p['risk_tier']} {p['packet_id']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="change_packet",
        description="Pre-implementation Change Packet gate for global-memory.",
    )
    sub = parser.add_subparsers(dest="command")

    p_new = sub.add_parser("new", help="Create a new Change Packet from template")
    p_new.add_argument("--title", required=True, help="Short title for the change")
    p_new.add_argument("--task", help="Parent task ID")
    p_new.add_argument("--out", help="Output directory (default: quality/change-packets/)")
    p_new.add_argument("--risk-tier", type=int, choices=[0, 1, 2, 3], dest="risk_tier")
    p_new.add_argument("--json", action="store_true")

    p_val = sub.add_parser("validate", help="Validate a Change Packet")
    p_val.add_argument("path", help="Path to the packet file")
    p_val.add_argument("--json", action="store_true")

    p_st = sub.add_parser("status", help="List all change packets")
    p_st.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "new":
        return cmd_new(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
