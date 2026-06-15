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


def print_text(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print(f"triage inbox: {summary['total']} item(s)")
    for item in payload["items"]:
        print(
            f"- [{item['suggested_lane']}] {item['source_type']} {item['id']} "
            f"{item['path']} — {item['title']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="global-memory repo root")
    parser.add_argument("--json", action="store_true", help="emit stable JSON")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    payload = build_payload(repo_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
