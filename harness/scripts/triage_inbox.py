#!/usr/bin/env python
"""Read-only inbox scanner for the `/triage` skill.

MVP scope:
  - issues/ISSUE-*.md with frontmatter status: open
  - feedback/*.md with frontmatter status: active

The script does not create or update any ledger; it only reports candidates for
AI proposal + user-confirmed action.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
EVIDENCE_KEYWORDS = [
    "关闭记录",
    "验证证据",
    "验证命令",
    "关闭原因",
    "drop reason",
    "superseded",
    "partial fix 进展",
    "已修复",
    "已关闭",
]
REASON_KEYWORDS = [
    "reason",
    "drop",
    "defer",
    "supersede",
    "superseded",
    "关闭原因",
    "丢弃原因",
    "废弃原因",
    "取代",
]
DROP_LIKE_STATUSES = {
    "drop",
    "dropped",
    "defer",
    "deferred",
    "supersede",
    "superseded",
}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        meta[key.strip()] = value
    return meta, text[match.end():]


def rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def first_heading(body: str) -> str | None:
    match = H1_RE.search(body)
    if not match:
        return None
    return match.group(1).strip()


def first_paragraph(body: str) -> str:
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith("#"):
            continue
        lines.append(line)
    return " ".join(lines)[:240]


def item_summary(meta: dict[str, str], body: str, title: str) -> str:
    description = meta.get("description")
    if description:
        return description[:240]
    paragraph = first_paragraph(body)
    return paragraph or title


def issue_lane(severity: str, title: str, summary: str) -> str:
    sev = severity.strip().lower()
    if sev in {"critical", "blocker", "high", "major"}:
        return "work"
    text = f"{title} {summary}".lower()
    if any(keyword in text for keyword in ("bug", "fix", "修复", "错误", "失败")):
        return "修"
    return "task"


def feedback_lane(priority: str, title: str, summary: str) -> str:
    pri = priority.strip().lower()
    if pri in {"high", "critical", "blocker"}:
        return "task"
    text = f"{title} {summary}"
    if any(keyword in text for keyword in ("必须", "强制", "不可", "禁止", "规则")):
        return "task"
    return "drop"


def scan_issues(repo_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    issues_dir = repo_root / "issues"
    if not issues_dir.is_dir():
        return items
    for path in sorted(issues_dir.glob("ISSUE-*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        status = meta.get("status", "").strip().lower()
        if status != "open":
            continue
        title = first_heading(body) or meta.get("title") or path.stem
        severity = meta.get("severity", "")
        summary = item_summary(meta, body, title)
        item_id = meta.get("id") or meta.get("issue_id") or path.stem
        items.append({
            "id": f"issue:{item_id}",
            "source_type": "issue",
            "path": rel_path(path, repo_root),
            "title": title,
            "status": status,
            "suggested_lane": issue_lane(severity, title, summary),
            "summary": summary,
        })
    return items


def scan_feedback(repo_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    feedback_dir = repo_root / "feedback"
    if not feedback_dir.is_dir():
        return items
    for path in sorted(feedback_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        status = meta.get("status", "").strip().lower()
        if status != "active":
            continue
        title = first_heading(body) or meta.get("description") or path.stem
        priority = meta.get("priority", "")
        summary = item_summary(meta, body, title)
        items.append({
            "id": f"feedback:{path.stem}",
            "source_type": "feedback",
            "path": rel_path(path, repo_root),
            "title": title,
            "status": status,
            "suggested_lane": feedback_lane(priority, title, summary),
            "summary": summary,
        })
    return items


def count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get(field, ""))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def build_payload(repo_root: Path) -> dict[str, Any]:
    items = scan_issues(repo_root) + scan_feedback(repo_root)
    items.sort(key=lambda item: (item["source_type"], item["path"], item["id"]))
    return {
        "kind": "triage_inbox.v1",
        "items": items,
        "summary": {
            "total": len(items),
            "counts": {
                "source_type": count_by(items, "source_type"),
                "suggested_lane": count_by(items, "suggested_lane"),
            },
        },
    }


def check(name: str, passed: bool, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "pass": passed,
        "message": message,
    }


def resolve_verify_path(repo_root: Path, path_text: str) -> tuple[Path, str]:
    repo_root = repo_root.resolve()
    raw_path = Path(path_text)
    path = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(repo_root).as_posix()
    except ValueError:
        rel = raw_path.as_posix()
    return resolved, rel


def source_type_for_relpath(rel: str) -> str:
    parts = Path(rel.replace("\\", "/")).parts
    if parts and parts[0] == "issues":
        return "issue"
    if parts and parts[0] == "feedback":
        return "feedback"
    return "unsupported"


def contains_any_keyword(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def build_close_verification(repo_root: Path, path_text: str) -> dict[str, Any]:
    path, rel = resolve_verify_path(repo_root, path_text)
    source_type = source_type_for_relpath(rel)
    checks: list[dict[str, Any]] = []

    supported = source_type in {"issue", "feedback"}
    checks.append(check(
        "path_supported",
        supported,
        "path is under issues/ or feedback/" if supported else "path must be under issues/ or feedback/",
    ))

    exists = path.is_file()
    checks.append(check(
        "file_exists",
        exists,
        "source file exists" if exists else "source file does not exist",
    ))

    meta: dict[str, str] = {}
    body = ""
    if exists:
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
    status = meta.get("status", "").strip().lower()

    if source_type == "issue":
        status_closed = bool(status) and status != "open"
        status_message = "issue status has left open" if status_closed else "issue status must not be empty/open"
    elif source_type == "feedback":
        status_closed = bool(status) and status != "active"
        status_message = "feedback status has left active" if status_closed else "feedback status must not be empty/active"
    else:
        status_closed = False
        status_message = "unsupported source path"
    checks.append(check("status_closed", status_closed, status_message))

    evidence_present = contains_any_keyword(body, EVIDENCE_KEYWORDS)
    checks.append(check(
        "evidence_present",
        evidence_present,
        "body contains close/verification evidence keyword"
        if evidence_present else "body must contain close/verification evidence keyword",
    ))

    reason_required = status in DROP_LIKE_STATUSES
    reason_present = (not reason_required) or contains_any_keyword(body, REASON_KEYWORDS)
    checks.append(check(
        "reason_present",
        reason_present,
        "drop/defer/supersede reason present or not required"
        if reason_present else "drop/defer/supersede status requires reason/drop/defer/supersede keyword",
    ))

    verdict = "PASS" if all(item["pass"] for item in checks) else "FAIL"
    return {
        "kind": "triage_close_verification.v1",
        "verdict": verdict,
        "path": rel,
        "source_type": source_type,
        "status": status,
        "checks": checks,
    }


def print_text(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print(f"triage inbox: {summary['total']} item(s)")
    for item in payload["items"]:
        print(
            f"- [{item['suggested_lane']}] {item['source_type']} {item['id']} "
            f"{item['path']} — {item['title']}"
        )


def print_close_verification_text(payload: dict[str, Any]) -> None:
    print(f"triage close verification: {payload['verdict']} {payload['path']}")
    print(f"source_type={payload['source_type']} status={payload['status']}")
    for item in payload["checks"]:
        marker = "PASS" if item["pass"] else "FAIL"
        print(f"- {marker} {item['name']}: {item['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="global-memory repo root")
    parser.add_argument("--json", action="store_true", help="emit stable JSON")
    parser.add_argument("--verify-close", help="read-only verify that an issue/feedback source is closed with evidence")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if args.verify_close:
        payload = build_close_verification(repo_root, args.verify_close)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print_close_verification_text(payload)
        return 0 if payload["verdict"] == "PASS" else 1

    payload = build_payload(repo_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
