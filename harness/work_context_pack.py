#!/usr/bin/env python3
"""work_context_pack.py — 把 /work 上下文压缩为短确定性摘要"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
CLAUDE_DIR = Path.home() / ".claude"
REGISTRY_PATH = CLAUDE_DIR / "projects" / "project_registry.json"
DISPLAY_NAMES_PATH = CLAUDE_DIR / "projects" / "task_display_names.json"
SESSION_TASKS_DIR = CLAUDE_DIR / ".session_tasks"
MEMORY_MD = REPO_DIR / "MEMORY.md"
NEW_TASK_INTENT_PATTERNS = [
    r"(?:新\s*(?:开|建)|开\s*(?:一个|个)?\s*新|创建|建立)\s*(?:一个|个)?[^，。；\n]{0,80}?(?:task|任务)",
    r"开\s*(?:一个|个)?\s*新\s*(?:task|任务)",
    r"(?:另开|单独|独立).*?(?:task|任务)",
    r"(?:迁移|治理|同步)[^，。；\n]{0,40}?(?:成|到|为)\s*新\s*(?:task|任务)",
    r"(?:进入|走)\s*work\s*(?:路径|流程)",
    r"\b(?:new|create|separate)\s+task\b",
]

sys.path.insert(0, str(HARNESS_DIR))
sys.path.insert(0, str(HARNESS_DIR / "hooks"))
from _lib import record_tool_invocation  # noqa: E402
from stage_lib import detect_stage  # noqa: E402
from _task_resolver import resolve_task_owner, normalize as _tr_normalize  # noqa: E402


def _task_path_string(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _sync_registry_from_active_dirs(registry: dict) -> bool:
    """Add active task directories to registry without pruning older entries."""
    tasks_root = Path(registry.get("tasks_root", CLAUDE_DIR / "projects"))
    if not tasks_root.is_dir():
        return False
    changed = False
    active = list(registry.get("active_tasks", []))
    task_paths = registry.setdefault("task_paths", {})
    for task_dir_path in sorted(p for p in tasks_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        task_id = task_dir_path.name
        if task_id not in active:
            active.append(task_id)
            changed = True
        paths = task_paths.setdefault(task_id, [])
        normalized_existing = [str(p).rstrip("/") for p in paths]
        raw = _task_path_string(task_dir_path)
        if raw not in normalized_existing:
            paths.append(raw)
            changed = True
    if registry.get("active_tasks") != active:
        registry["active_tasks"] = active
        changed = True
    return changed


def load_registry() -> dict:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    try:
        if _sync_registry_from_active_dirs(registry):
            REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    return registry


def detect_new_task_intent(intent: str | None) -> dict | None:
    """Detect explicit high-confidence requests that should not silently reuse current_task."""
    if not intent:
        return None
    text = " ".join(intent.strip().split())
    if not text:
        return None
    for pattern in NEW_TASK_INTENT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                "kind": "new_task_intent",
                "trigger": match.group(0),
                "action": "create_task_or_confirm",
                "message": "Intent looks like a new task; run create_task.py first or explicitly confirm continuing the current task.",
            }
    return None


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


def read_session_task_file(session_id: str | None) -> str | None:
    """Read ~/.claude/.session_tasks/<session_id> for multi-terminal work."""
    if not session_id:
        return None
    try:
        marker = SESSION_TASKS_DIR / session_id
        if marker.is_file():
            name = marker.read_text(encoding="utf-8").strip()
            return name or None
    except Exception:
        pass
    return None


def resolve_task(registry: dict, task_arg: str | None, cwd: Path, session_id: str | None = None) -> tuple[str | None, Path | None, float, list[str], str]:
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
        # fallback: try tasks_root/<task_arg> even if not in active_tasks
        td = task_dir(registry, task_arg)
        if td.exists() and td.is_dir():
            return task_arg, td, 0.95, [], "tasks_root"
        return None, None, 0.0, prefix or active, "ambiguous-or-missing"

    # Primary: session-scoped marker avoids cross-terminal task pointer drift.
    st = read_session_task_file(session_id)
    if st:
        td = task_dir(registry, st)
        if td.exists():
            return st, td, 1.0, [t for t in active if t != st], "session_task_file"
        if st in active:
            return st, td, 0.9, [t for t in active if t != st], "session_task_file"

    # .current_task is intentionally NOT consulted here: it is a single global
    # marker any terminal can overwrite, so using it as a fallback leaks one
    # terminal's task into another's resolution. The cwd-based resolution below
    # is per-terminal and safe.

    # Secondary: use shared _task_resolver (same logic as doc_gate) for consistency
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
    if stage == "v2-active":
        v2_cfg = registry.get("task_structure_v2") or {}
        required = list(v2_cfg.get("required_files", []))
        existing = [name for name in required if (task_path / name).exists()]
        missing = [name for name in required if not (task_path / name).exists()]
        snippets = {name: extract_title_or_first_para(read_text(task_path / name)) for name in existing}
        return existing, missing, required, snippets

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


def load_display_name(task_id: str) -> str:
    """Look up Chinese display name; fallback to raw id."""
    if not task_id:
        return ""
    try:
        if DISPLAY_NAMES_PATH.is_file():
            data = json.loads(DISPLAY_NAMES_PATH.read_text(encoding="utf-8"))
            name = data.get(task_id)
            if isinstance(name, str) and name.strip():
                return name.strip()
    except Exception:
        pass
    return task_id


def count_git_changes(task_dir: Path) -> tuple[int, int]:
    """Return (modified, untracked) count from git status --short. (0,0) if no git."""
    try:
        r = subprocess.run(
            ["git", "-C", str(task_dir), "status", "--short"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode != 0:
            return (0, 0)
        mod = unt = 0
        for line in r.stdout.splitlines():
            if not line:
                continue
            code = line[:2]
            if code.startswith("??"):
                unt += 1
            else:
                mod += 1
        return (mod, unt)
    except Exception:
        return (0, 0)


def read_decision_queue(task_dir: Path) -> list[str]:
    """Open '决策' / decisions items from ops/决策队列.md or 决策队列.md."""
    for rel in ("ops/决策队列.md", "决策队列.md"):
        p = task_dir / rel
        if p.exists():
            text = read_text(p, 8000)
            items = []
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("- [ ]") or s.startswith("* [ ]"):
                    items.append(s[5:].strip("] ").strip())
                elif re.match(r"^[-*]\s+(待决|未决|TODO|🚨)", s):
                    items.append(s.lstrip("-* ").strip())
            return items[:5]
    return []


def detect_phase_card(task_dir: Path) -> str:
    """Find current active Phase card by globbing Phase*.md and reading status."""
    matches = sorted(task_dir.glob("Phase*-*.md"))
    if not matches:
        matches = sorted(task_dir.glob("design/Phase*-*.md"))
    for p in matches:
        text = read_text(p, 2000)
        m = re.search(r"^status:\s*(\S+)", text, re.MULTILINE)
        if m and m.group(1).lower() in ("implementing", "active", "in_progress", "进行中"):
            return p.name
    return matches[0].name if matches else ""


def render_status_md(task: str, display_name: str, report: dict, task_dir: Path) -> str:
    """Render 7-field STATUS.md snapshot."""
    stage = report.get("stage", "?")
    progress = report.get("progress") or "-"
    required = report.get("required_reads", [])
    decisions = read_decision_queue(task_dir)
    mod, unt = count_git_changes(task_dir)
    phase_card = detect_phase_card(task_dir)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    reads_block = "\n".join(f"- `{Path(r).name}`" for r in required[:5]) or "- (无)"
    decisions_block = "\n".join(f"- {d}" for d in decisions) or "- (无)"

    if decisions:
        first_step = f"答复待决策: {decisions[0][:60]}"
    elif (task_dir / "HANDOFF.md").exists():
        first_step = "读 HANDOFF.md → 确认上次「下一步」"
    elif phase_card:
        first_step = f"读 {phase_card} → 进入实施"
    else:
        first_step = "确认任务起点"

    git_line = f"修改 {mod} / 未跟踪 {unt}" if (mod or unt) else "(干净)"
    phase_line = f"{stage}" + (f" · 当前卡 `{phase_card}`" if phase_card else "")

    return f"""<!-- AUTO-GENERATED by work_context_pack.py — 勿手改 -->
# STATUS · {display_name}

> 生成时间: {now}
> 任务 ID: `{task}`

## 🎯 当前任务
{display_name}

## 📊 阶段
{phase_line}

## 📖 必读
{reads_block}

## ⏭ 上次下一步
{progress}

## 🚨 风险/待决
{decisions_block}

## ✅ 推荐第一步
{first_step}

## 🔧 未提交改动
{git_line}
"""


def write_status_md(report: dict, task_dir: Path, display_name: str) -> Path | None:
    """Write STATUS.md to <task_dir>/core/STATUS.md if core/ exists, else <task_dir>/STATUS.md."""
    task = report.get("task")
    if not task:
        return None
    target_dir = task_dir / "core" if (task_dir / "core").is_dir() else task_dir
    target = target_dir / "STATUS.md"
    try:
        content = render_status_md(task, display_name, report, task_dir)
        target.write_text(content, encoding="utf-8")
        return target
    except Exception:
        return None


def build_report(task_arg: str | None, cwd: Path, update_session: bool = True, intent: str | None = None) -> dict:
    registry = load_registry()
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    task, resolved_dir, confidence, candidates, reason = resolve_task(registry, task_arg, cwd, session_id=session_id)
    intent_guard = detect_new_task_intent(intent)
    # An explicit --task is an intent to pin THIS terminal to that task, even
    # under --json (the skill's primary call). Without this, continuing/switching
    # a task never writes the per-session marker and every terminal falls back to
    # the shared global .current_task. Auto-resolved (no task_arg) runs only pin
    # when update_session is on.
    pin_session = bool(session_id) and (update_session or bool(task_arg))
    if not task or not resolved_dir:
        # Only clear on a genuine no-resolve auto run; never let a read-only or
        # explicit-but-missing query delete another terminal's marker.
        if update_session and session_id and not task_arg:
            marker = SESSION_TASKS_DIR / session_id
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
        report = {
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
        if intent_guard:
            report["intent_guard"] = intent_guard
            report["recommended_next_step"] = (
                "Intent looks like a new task. Run create_task.py first, or explicitly confirm continuing without a task."
            )
        return report

    if pin_session:
        session_tasks_dir = SESSION_TASKS_DIR
        session_tasks_dir.mkdir(exist_ok=True)
        try:
            (session_tasks_dir / session_id).write_text(task, encoding="utf-8")
        except Exception:
            pass

    stage, diag = detect_stage(resolved_dir, registry)
    existing, missing, required, snippets = docs_for_task(resolved_dir, registry, stage)
    is_v2 = (resolved_dir / "core").is_dir()
    handoff_path = resolved_dir / ("core/HANDOFF.md" if is_v2 else "HANDOFF.md")
    design_path = resolved_dir / ("design/设计文档.md" if is_v2 else "设计文档.md")
    handoff_progress = extract_progress(read_text(handoff_path))
    design_progress = extract_progress(read_text(design_path))
    required_reads = []
    for name in required:
        path = resolved_dir / name
        if path.exists():
            required_reads.append(str(path))
    if stage == "implementation" and handoff_path.exists():
        required_reads.insert(0, str(handoff_path))
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

    report = {
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
    if intent_guard and not task_arg:
        guard = dict(intent_guard)
        guard["resolved_task"] = task
        guard["resolution"] = reason
        report["intent_guard"] = guard
        report["level"] = "WARNING"
        report["summary"] += "; intent_guard=new_task_requires_create_task_or_confirm"
        report["recommended_next_step"] = (
            "Intent looks like a new task. Run create_task.py first, or explicitly confirm continuing current task "
            f"`{task}`."
        )
    return report


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
    if stage == "v2-active":
        return "Read core/HANDOFF.md → confirm 下次开始 → ack with user before coding."
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
    parser = argparse.ArgumentParser(description="build compact /work context")
    parser.add_argument("--task", help="task name, prefix, or absolute task directory")
    parser.add_argument("--cwd", default=os.getcwd(), help="cwd used for task inference")
    parser.add_argument("--json", action="store_true", help="emit JSON for skill consumption")
    parser.add_argument("--verbose", action="store_true", help="emit legacy full text render")
    parser.add_argument("--no-status", action="store_true", help="skip writing STATUS.md")
    parser.add_argument("--write-status", action="store_true", help="write STATUS.md even with --json")
    parser.add_argument("--match", help="match description against active tasks' DESIGN.md steps")
    parser.add_argument("--intent", help="original user request; warns when new-task intent would reuse current_task")
    args = parser.parse_args()

    if not args.json:
        record_tool_invocation("work_context_pack.py", source="work-context-pack")

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

    report = build_report(args.task, Path(args.cwd), update_session=not args.json, intent=args.intent)

    if args.json:
        if args.write_status and not args.no_status and report.get("task"):
            display = load_display_name(report["task"])
            write_status_md(report, Path(report["task_dir"]), display)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["level"] != "ERROR" else 1

    if args.verbose:
        print(render_text(report))
        return 0 if report["level"] != "ERROR" else 1

    # 默认模式：写 STATUS.md + 单行 echo
    task = report.get("task")
    if not task:
        print(f"⚠ 未识别任务：{report.get('summary', '')}")
        return 0
    display = load_display_name(task)
    task_dir_path = Path(report["task_dir"])
    if not args.no_status:
        write_status_md(report, task_dir_path, display)
    print(f"📋 任务 {display} 已加载")
    return 0 if report["level"] != "ERROR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
