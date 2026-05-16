#!/usr/bin/env python3
"""check_prepare.py — /check 设计审查的确定性输入准备"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
CLAUDE_DIR = Path.home() / ".claude"
REGISTRY_PATH = CLAUDE_DIR / "projects" / "project_registry.json"

sys.path.insert(0, str(HARNESS_DIR))
from _lib import record_tool_invocation  # noqa: E402
from stage_lib import detect_stage  # noqa: E402


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def resolve_task(registry: dict, task_arg: str | None) -> tuple[str | None, Path | None, list[str], str]:
    active = list(registry.get("active_tasks", []))
    tasks_root = Path(registry.get("tasks_root", CLAUDE_DIR / "projects"))
    if not task_arg:
        return None, None, active, "missing-argument"

    candidate = Path(task_arg)
    if candidate.exists() and candidate.is_dir():
        return candidate.name, candidate, [], "absolute-path"

    if task_arg in active:
        return task_arg, tasks_root / task_arg, [], "exact"

    prefix = [t for t in active if t.startswith(task_arg)]
    if len(prefix) == 1:
        return prefix[0], tasks_root / prefix[0], [], "prefix"
    return None, None, prefix or active, "ambiguous-or-missing"


def read_text(path: Path, limit: int = 300000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def find_empty_headings(text: str) -> list[str]:
    lines = text.splitlines()
    empty: list[str] = []
    for idx, line in enumerate(lines):
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        body_seen = False
        for nxt in lines[idx + 1:]:
            if nxt.startswith("#"):
                next_level = len(nxt) - len(nxt.lstrip("#"))
                if next_level > level:
                    body_seen = True
                    break
                break
            stripped = nxt.strip()
            if stripped and not stripped.startswith("<!--"):
                body_seen = True
                break
        if not body_seen:
            empty.append(line.strip())
    return empty[:10]


def scan_doc(path: Path) -> dict:
    text = read_text(path)
    todo_matches = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if re.search(r"^\s*(?:[-*]\s*)?(?:TODO|TBD|FIXME)\s*[:：]|待填写|placeholder|<!--", line, re.IGNORECASE):
            todo_matches.append({"line": idx, "text": line.strip()[:180]})
    return {
        "path": str(path),
        "name": path.name,
        "bytes": path.stat().st_size if path.exists() else 0,
        "line_count": len(text.splitlines()),
        "todo_or_placeholders": todo_matches[:20],
        "empty_headings": find_empty_headings(text),
        "too_long": len(text.splitlines()) > 800,
    }


def build_report(task_arg: str | None) -> dict:
    registry = load_registry()
    task, task_dir, candidates, resolution = resolve_task(registry, task_arg)
    if not task or not task_dir:
        return {
            "schema_version": 1,
            "kind": "check_prepare",
            "level": "WARNING",
            "task": None,
            "summary": "No task resolved. Provide an active task name or absolute path.",
            "candidates": candidates,
            "review_docs": [],
        }

    if not task_dir.exists():
        return {
            "schema_version": 1,
            "kind": "check_prepare",
            "level": "ERROR",
            "task": task,
            "task_dir": str(task_dir),
            "summary": f"Task directory does not exist: {task_dir}",
            "candidates": [],
            "review_docs": [],
        }

    stage, diag = detect_stage(task_dir, registry)
    required = registry.get("required_docs_by_stage", {}).get(stage) or registry.get("required_docs", [])
    missing = [name for name in required if not (task_dir / name).exists()]
    md_files = sorted(p for p in task_dir.glob("*.md") if not p.name.startswith("REVIEW-"))
    review_docs = [str(p) for p in md_files]
    scans = [scan_doc(p) for p in md_files]
    warnings: list[str] = []
    if diag:
        warnings.append(diag)
    if missing:
        warnings.append("Missing required docs: " + ", ".join(missing))
    for scan in scans:
        if scan["todo_or_placeholders"]:
            warnings.append(f"{scan['name']} has TODO/TBD/placeholders")
        if scan["empty_headings"]:
            warnings.append(f"{scan['name']} has empty headings")
        if scan["too_long"]:
            warnings.append(f"{scan['name']} is long ({scan['line_count']} lines)")
    if len(md_files) > 10:
        warnings.append(f"Many markdown docs ({len(md_files)}); consider narrowing review scope")
    if not md_files:
        warnings.append("No markdown docs found for review")

    level = "ERROR" if not md_files else ("WARNING" if warnings else "PASS")
    prompt_inputs = [
        f"【任务名】：{task}",
        "【待审文档】：",
        *[f"- {p}" for p in review_docs],
        f"【项目根目录】：{task_dir}",
        "【审查维度】：需求覆盖度 / 技术风险 / 替代方案评估 / 可测试性与可维护性",
    ]

    return {
        "schema_version": 1,
        "kind": "check_prepare",
        "level": level,
        "task": task,
        "task_dir": str(task_dir),
        "resolution": resolution,
        "stage": stage,
        "diagnostic": diag,
        "required_docs": required,
        "missing_required_docs": missing,
        "review_docs": review_docs,
        "doc_scans": scans,
        "warnings": warnings,
        "summary": f"task={task}; stage={stage}; review_docs={len(review_docs)}; warnings={len(warnings)}",
        "prompt_inputs": prompt_inputs,
        "candidates": candidates,
    }


def render_text(report: dict) -> str:
    lines = [
        f"check prepare: {report['level']}",
        f"summary: {report['summary']}",
    ]
    if report.get("candidates"):
        lines.append("candidates: " + ", ".join(report["candidates"][:12]))
    if report.get("task"):
        lines.append(f"task_dir: {report.get('task_dir')}")
        lines.append("review_docs:")
        for path in report.get("review_docs", []):
            lines.append(f"- {path}")
        lines.append("warnings:")
        for warning in report.get("warnings", [])[:20]:
            lines.append(f"- {warning}")
    return "\n".join(lines[:120])


def main() -> int:
    record_tool_invocation("check_prepare.py", source="check-prepare")
    parser = argparse.ArgumentParser(description="prepare deterministic /check input")
    parser.add_argument("--task", help="task name, prefix, or absolute task directory")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    report = build_report(args.task)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if report["level"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
