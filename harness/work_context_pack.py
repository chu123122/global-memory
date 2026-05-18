#!/usr/bin/env python3
"""work_context_pack.py — 把 /work 上下文压缩为短确定性摘要"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
CLAUDE_DIR = Path.home() / ".claude"
REGISTRY_PATH = CLAUDE_DIR / "projects" / "project_registry.json"
MEMORY_MD = REPO_DIR / "MEMORY.md"

sys.path.insert(0, str(HARNESS_DIR))
sys.path.insert(0, str(HARNESS_DIR / "hooks"))
from _lib import record_tool_invocation  # noqa: E402
from stage_lib import detect_stage  # noqa: E402
from _task_resolver import resolve_task_owner, normalize as _tr_normalize  # noqa: E402


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def norm_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").lower()


def task_dir(registry: dict, task: str) -> Path:
    return Path(registry.get("tasks_root", CLAUDE_DIR / "projects")) / task


def first_existing_project_path(registry: dict, task: str) -> Path | None:
    for raw in registry.get("task_paths", {}).get(task, []):
        path = Path(raw)
        if path.exists() and path.is_dir():
            return path
    return None


def score_task(registry: dict, task: str, cwd: Path) -> int:
    cwd_norm = norm_path(cwd)
    score = 0
    td = task_dir(registry, task)
    if td.exists() and cwd_norm.startswith(norm_path(td)):
        score += 100
    for raw in registry.get("task_paths", {}).get(task, []):
        path = Path(raw)
        if path.exists() and cwd_norm.startswith(norm_path(path)):
            score += 50
        elif str(raw).replace("\\", "/").lower() in cwd_norm:
            score += 10
    return score


def resolve_task(registry: dict, task_arg: str | None, cwd: Path) -> tuple[str | None, Path | None, float, list[str], str]:
    active = list(registry.get("active_tasks", []))
    if task_arg:
        candidate = Path(task_arg)
        if candidate.exists() and candidate.is_dir():
            name = candidate.name
            return name, candidate, 1.0, [], "absolute-path"
        exact = [t for t in active if t == task_arg]
        if exact:
            name = exact[0]
            return name, task_dir(registry, name), 1.0, [], "exact"
        prefix = [t for t in active if t.startswith(task_arg)]
        if len(prefix) == 1:
            name = prefix[0]
            return name, task_dir(registry, name), 0.85, [], "prefix"
        return None, None, 0.0, prefix or active, "ambiguous-or-missing"

    # Primary: use shared _task_resolver (same logic as doc_gate) for consistency
    owner = resolve_task_owner(str(cwd), registry)
    if owner and owner in active:
        return owner, task_dir(registry, owner), 0.9, [t for t in active if t != owner], "task_resolver"

    # Fallback: score-based heuristic for paths _task_resolver doesn't cover
    scored = [(score_task(registry, t, cwd), t) for t in active]
    scored = sorted((s, t) for s, t in scored if s > 0)
    if scored:
        score, name = scored[-1]
        confidence = 0.9 if score >= 100 else 0.65
        return name, task_dir(registry, name), confidence, [t for _, t in scored[:-1]], "cwd"
    return None, None, 0.0, active, "no-match"


def read_text(path: Path, limit: int = 12000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def extract_title_or_first_para(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    for para in re.split(r"\n\s*\n", text):
        stripped = " ".join(para.split())
        if stripped and not stripped.startswith(">"):
            return stripped[:180]
    return ""


def extract_progress(text: str) -> str:
    patterns = [
        r"^##\s+.*(?:进度|下次开始|下一步|TODO|待办).*$",
        r"^###\s+.*(?:进度|下次开始|下一步|TODO|待办).*$",
    ]
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if any(re.search(p, line, re.IGNORECASE) for p in patterns):
            block = [line.strip()]
            for nxt in lines[idx + 1: idx + 12]:
                if nxt.startswith("## "):
                    break
                if nxt.strip():
                    block.append(nxt.strip())
            return " ".join(block)[:300]
    return ""


def docs_for_task(task_path: Path, registry: dict, stage: str) -> tuple[list[str], list[str], list[str], dict[str, str]]:
    human = list(registry.get("human_doc_patterns", ["需求分析.md", "设计文档.md"]))
    required_by_stage = registry.get("required_docs_by_stage", {})
    required = required_by_stage.get(stage) or registry.get("required_docs", ["SPEC.md"])
    all_docs = []
    for name in list(required) + human + list(registry.get("required_docs", [])):
        if name not in all_docs:
            all_docs.append(name)
    existing = [name for name in all_docs if (task_path / name).exists()]
    missing = [name for name in required if not (task_path / name).exists()]
    snippets = {name: extract_title_or_first_para(read_text(task_path / name)) for name in existing}
    return existing, missing, required, snippets


def memory_task_line(task: str) -> str:
    text = read_text(MEMORY_MD, 20000)
    for line in text.splitlines():
        if task in line:
            return line.strip()[:220]
    return ""


def is_cwd_in_watched(cwd: Path, registry: dict) -> bool:
    cwd_norm = str(cwd.resolve()).replace("\\", "/").lower()
    for fragment in registry.get("watched_paths", []):
        if fragment.replace("\\", "/").lower() in cwd_norm:
            return True
    return False


def build_report(task_arg: str | None, cwd: Path) -> dict:
    registry = load_registry()
    task, resolved_dir, confidence, candidates, reason = resolve_task(registry, task_arg, cwd)
    if not task or not resolved_dir:
        session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        if session_id:
            marker = CLAUDE_DIR / ".session_tasks" / session_id
            try:
                marker.unlink(missing_ok=True)
            except Exception:
                pass
        in_watched = is_cwd_in_watched(cwd, registry)
        summary = "No active task resolved from argument or cwd."
        if in_watched:
            summary += " cwd is in watched_paths but no task claims this path — doc_gate will only block if a task owns the edited file."
        next_step = (
            "Proceed with work. No task-level doc requirements apply to this path."
            if in_watched
            else "Confirm whether this is a new task or specify task name."
        )
        return {
            "schema_version": 1,
            "kind": "work_context",
            "level": "INFO" if in_watched else "WARNING",
            "task": None,
            "confidence": confidence,
            "summary": summary,
            "in_watched_paths": in_watched,
            "candidates": candidates,
            "required_reads": [],
            "recommended_next_step": next_step,
        }

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if session_id:
        session_tasks_dir = CLAUDE_DIR / ".session_tasks"
        session_tasks_dir.mkdir(exist_ok=True)
        try:
            (session_tasks_dir / session_id).write_text(task, encoding="utf-8")
        except Exception:
            pass

    stage, diag = detect_stage(resolved_dir, registry)
    existing, missing, required, snippets = docs_for_task(resolved_dir, registry, stage)
    handoff_progress = extract_progress(read_text(resolved_dir / "HANDOFF.md"))
    design_progress = extract_progress(read_text(resolved_dir / "设计文档.md"))
    required_reads = []
    for name in required:
        path = resolved_dir / name
        if path.exists():
            required_reads.append(str(path))
    if stage == "implementation" and (resolved_dir / "HANDOFF.md").exists():
        required_reads.insert(0, str(resolved_dir / "HANDOFF.md"))
    required_reads = list(dict.fromkeys(required_reads))

    summary_bits = [
        f"task={task}",
        f"stage={stage}",
        f"docs={len(existing)} existing/{len(missing)} missing required",
    ]
    if diag:
        summary_bits.append(f"diag={diag}")
    if handoff_progress or design_progress:
        summary_bits.append(f"progress={(handoff_progress or design_progress)[:140]}")

    return {
        "schema_version": 1,
        "kind": "work_context",
        "level": "PASS" if not missing and stage != "missing-status" else "WARNING",
        "task": task,
        "task_dir": str(resolved_dir),
        "resolution": reason,
        "confidence": confidence,
        "stage": stage,
        "diagnostic": diag,
        "memory_line": memory_task_line(task),
        "existing_docs": existing,
        "missing_required_docs": missing,
        "doc_snippets": snippets,
        "progress": handoff_progress or design_progress,
        "summary": "; ".join(summary_bits),
        "recommended_next_step": recommended_next_step(stage, missing),
        "required_reads": required_reads,
        "candidates": candidates,
    }


def match_to_design_steps(registry: dict, description: str) -> list[dict]:
    """Match user description against DESIGN.md Step tables in active tasks."""
    if not description:
        return []
    active = list(registry.get("active_tasks", []))
    tasks_root = Path(registry.get("tasks_root", CLAUDE_DIR / "projects"))
    keywords = set(description.lower().split())
    results = []
    for task in active:
        design = tasks_root / task / "DESIGN.md"
        if not design.exists():
            continue
        text = read_text(design, 8000).lower()
        lines = text.splitlines()
        in_step_table = False
        for line in lines:
            if "|" in line and ("step" in line or "做什么" in line):
                in_step_table = True
                continue
            if in_step_table and line.strip().startswith("|"):
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2:
                    step_id = cells[0]
                    step_desc = " ".join(cells[1:])
                    hits = sum(1 for kw in keywords if kw in step_desc or kw in step_id)
                    if hits >= 1:
                        results.append({
                            "task": task,
                            "step": step_id,
                            "desc": step_desc[:120],
                            "score": hits,
                        })
            elif in_step_table and not line.strip().startswith("|"):
                in_step_table = False
    results.sort(key=lambda x: -x["score"])
    return results[:3]


def recommended_next_step(stage: str, missing: list[str]) -> str:
    if stage == "missing-status":
        return "Fix Status fields in human-facing docs before continuing."
    if missing:
        return f"Create or fill missing required docs: {', '.join(missing)}."
    if stage == "discussion":
        return "Continue discussion and keep landing decisions into 需求分析.md / 设计文档.md."
    if stage == "implementation":
        return "Read HANDOFF.md and SPEC.md first, then confirm current implementation target."
    return "Confirm whether this is a new task or a legacy task."


def render_text(report: dict) -> str:
    lines = [
        f"work context: {report['level']}",
        f"summary: {report['summary']}",
    ]
    if report.get("candidates"):
        lines.append("candidates: " + ", ".join(report["candidates"][:12]))
    if report.get("task"):
        lines.extend([
            f"task_dir: {report.get('task_dir')}",
            f"confidence: {report.get('confidence')}",
            f"memory: {report.get('memory_line') or '-'}",
            f"existing_docs: {', '.join(report.get('existing_docs', [])) or '-'}",
            f"missing_required_docs: {', '.join(report.get('missing_required_docs', [])) or '-'}",
            f"progress: {report.get('progress') or '-'}",
            f"next: {report.get('recommended_next_step')}",
            "required_reads:",
        ])
        for path in report.get("required_reads", [])[:8]:
            lines.append(f"- {path}")
    return "\n".join(lines[:120])


def main() -> int:
    record_tool_invocation("work_context_pack.py", source="work-context-pack")
    parser = argparse.ArgumentParser(description="build compact /work context")
    parser.add_argument("--task", help="task name, prefix, or absolute task directory")
    parser.add_argument("--cwd", default=os.getcwd(), help="cwd used for task inference")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--match", help="match description against active tasks' DESIGN.md steps")
    args = parser.parse_args()

    if args.match:
        registry = load_registry()
        matches = match_to_design_steps(registry, args.match)
        if args.json:
            print(json.dumps({"matches": matches}, ensure_ascii=False, indent=2))
        elif matches:
            print("匹配到的父任务 Step：")
            for m in matches:
                print(f"  → {m['task']} Step {m['step']}：{m['desc']}")
        else:
            print("未匹配到活跃任务的 DESIGN Step，建议创建独立任务文件夹。")
        return 0

    report = build_report(args.task, Path(args.cwd))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0 if report["level"] != "ERROR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
