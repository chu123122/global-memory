#!/usr/bin/env python3
"""audit_skill.py — 确定性 Skill 结构审计

This script intentionally checks only mechanical structure. It does not judge
whether a Skill is effective.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
SKILLS_DIR = REPO_DIR / "skills"
DEPLOYED_SKILLS_DIR = Path.home() / ".claude" / "skills"

sys.path.insert(0, str(HARNESS_DIR))
from _lib import record_tool_invocation  # noqa: E402


def canonical_skills() -> list[str]:
    sys.path.insert(0, str(REPO_DIR))
    try:
        import bootstrap  # type: ignore

        return list(getattr(bootstrap, "SKILLS"))
    except Exception:
        return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    lines = text[3:end].splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if ":" not in line:
            idx += 1
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if value in (">", "|"):
            block = []
            idx += 1
            while idx < len(lines) and (lines[idx].startswith(" ") or not lines[idx].strip()):
                block.append(lines[idx].strip())
                idx += 1
            fields[key] = " ".join(x for x in block if x)
            continue
        fields[key] = value
        idx += 1
    return fields


def has_trigger_hint(description: str) -> bool:
    lowered = description.lower()
    triggers = ["use when", "invoke", "trigger", "用户", "当", "用于", "触发", "asks"]
    return any(t in lowered for t in triggers)


def referenced_local_paths(text: str) -> set[str]:
    refs: set[str] = set()
    patterns = [r"`((?:scripts|references|assets|examples)/[^`]+)`"]
    for pat in patterns:
        for match in re.findall(pat, text):
            cleaned = match.strip().rstrip(".,;:)")
            if cleaned and not cleaned.startswith("http"):
                refs.add(cleaned)
    return refs


def skill_source_dir(name_or_path: str) -> tuple[str, Path]:
    candidate = Path(name_or_path)
    if candidate.exists():
        path = candidate
        name = path.parent.name if path.name == "v1" else path.name
        return name, path

    name = name_or_path
    path = SKILLS_DIR / name / "v1"
    return name, path


def audit_one(name_or_path: str, canonical: set[str]) -> dict:
    name, root = skill_source_dir(name_or_path)
    skill_file = root / "SKILL.md"
    issues: list[dict] = []

    def add(level: str, code: str, message: str) -> None:
        issues.append({"level": level, "code": code, "message": message})

    if not skill_file.exists():
        add("ERROR", "missing-skill-md", f"SKILL.md not found: {skill_file}")
        return {
            "name": name,
            "path": str(root),
            "level": "FAIL",
            "line_count": 0,
            "estimated_tokens": 0,
            "issues": issues,
        }

    text = skill_file.read_text(encoding="utf-8", errors="replace")
    frontmatter = parse_frontmatter(text)
    lines = text.splitlines()

    if "name" not in frontmatter:
        add("ERROR", "missing-name", "frontmatter missing name")
    if "description" not in frontmatter:
        add("ERROR", "missing-description", "frontmatter missing description")
    elif not has_trigger_hint(frontmatter["description"]):
        add("WARNING", "weak-trigger", "description does not clearly state trigger/use conditions")

    if len(lines) > 500:
        add("WARNING", "long-skill", f"SKILL.md has {len(lines)} lines; target is <= 500")

    for ref in sorted(referenced_local_paths(text)):
        ref_path = root / ref
        if not ref_path.exists():
            add("WARNING", "missing-reference", f"referenced path does not exist: {ref}")

    deployed_path = DEPLOYED_SKILLS_DIR / name
    if name in canonical:
        if not deployed_path.exists():
            add("ERROR", "missing-deployed-skill", f"deployed skill missing: {deployed_path}")
        else:
            try:
                actual = deployed_path.resolve()
                expected = root.resolve()
                if actual != expected:
                    add("ERROR", "deployed-target-mismatch", f"{deployed_path} -> {actual}, expected {expected}")
            except Exception as exc:
                add("WARNING", "deployed-target-unknown", f"could not resolve deployed target: {exc}")

    error_count = sum(1 for i in issues if i["level"] == "ERROR")
    warning_count = sum(1 for i in issues if i["level"] == "WARNING")
    if error_count:
        level = "FAIL"
    elif warning_count > 2:
        level = "CONDITIONAL"
    else:
        level = "PASS"

    return {
        "name": name,
        "path": str(root),
        "level": level,
        "line_count": len(lines),
        "estimated_tokens": int(len(text) / 4),
        "issues": issues,
    }


def audit_deployed_extras(canonical: set[str]) -> list[dict]:
    if not DEPLOYED_SKILLS_DIR.exists():
        return []
    extras = []
    for item in sorted(DEPLOYED_SKILLS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if item.name not in canonical:
            extras.append({
                "name": item.name,
                "path": str(item),
                "level": "WARNING",
                "issues": [{
                    "level": "WARNING",
                    "code": "deployed-extra",
                    "message": "deployed skill is not declared in bootstrap.SKILLS",
                }],
            })
    return extras


def aggregate_level(skills: list[dict]) -> str:
    if any(s["level"] == "FAIL" for s in skills):
        return "FAIL"
    if any(s["level"] == "CONDITIONAL" for s in skills):
        return "CONDITIONAL"
    if any(s["level"] == "WARNING" for s in skills):
        return "WARNING"
    return "PASS"


def summarize_skills(skills: list[dict]) -> dict:
    level_counts = {"PASS": 0, "WARNING": 0, "CONDITIONAL": 0, "FAIL": 0}
    issue_counts = {"ERROR": 0, "WARNING": 0}
    by_issue_code: dict[tuple[str, str], int] = {}
    deployed_extras = 0
    for skill in skills:
        level = skill.get("level")
        if level in level_counts:
            level_counts[level] += 1
        issues = skill.get("issues", [])
        if not isinstance(issues, list):
            continue
        has_deployed_extra = False
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            issue_level = issue.get("level")
            code = issue.get("code")
            if issue_level in issue_counts:
                issue_counts[issue_level] += 1
            if isinstance(issue_level, str) and isinstance(code, str) and code:
                by_issue_code[(issue_level, code)] = by_issue_code.get((issue_level, code), 0) + 1
            if code == "deployed-extra":
                has_deployed_extra = True
        if has_deployed_extra:
            deployed_extras += 1
    return {
        "checked_skills": len(skills),
        "level_counts": level_counts,
        "issue_counts": issue_counts,
        "by_issue_code": [
            {"level": level, "code": code, "count": count}
            for (level, code), count in sorted(by_issue_code.items(), key=lambda item: (item[0][0], item[0][1]))
        ],
        "deployed_extras": deployed_extras,
    }


def render_text(report: dict) -> str:
    summary = report.get("summary", {})
    issue_counts = summary.get("issue_counts", {})
    lines = [
        f"skill audit: {report['level']}",
        f"skills checked: {summary.get('checked_skills', len(report['skills']))}",
        f"issues: ERROR={issue_counts.get('ERROR', 0)} WARNING={issue_counts.get('WARNING', 0)}",
        "",
    ]
    for skill in report["skills"]:
        lines.append(f"- {skill['name']}: {skill['level']} ({skill.get('line_count', 0)} lines, ~{skill.get('estimated_tokens', 0)} tokens)")
        for issue in skill.get("issues", []):
            lines.append(f"  {issue['level']}: {issue['code']} - {issue['message']}")
    return "\n".join(lines)


def main() -> int:
    record_tool_invocation("audit_skill.py", source="skill-audit")
    parser = argparse.ArgumentParser(description="audit Skill structure without using AI context")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--skill", help="skill name or skill root path")
    group.add_argument("--all", action="store_true", help="audit all canonical skills from bootstrap.SKILLS")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    canonical = set(canonical_skills())
    if args.all:
        skills = [audit_one(name, canonical) for name in sorted(canonical)]
        skills.extend(audit_deployed_extras(canonical))
    else:
        skills = [audit_one(args.skill, canonical)]

    report = {
        "schema_version": 1,
        "kind": "skill_audit",
        "level": aggregate_level(skills),
        "summary": summarize_skills(skills),
        "skills": skills,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if report["level"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
