#!/usr/bin/env python3
"""assurance_gate.py — read-only completion gates for task/harness work.

The goal is not to prove correctness globally. It provides a small, machine
readable verdict that tells an agent whether it is allowed to claim a specific
kind of completion.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCHEMA_VERSION = 1
DEFAULT_TASKS_ROOT = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(Path.home() / ".claude" / "tasks" / "active")))
WORK_CONTEXT_PACK = Path(__file__).resolve().parents[1] / "work_context_pack.py"
VERDICTS = {"PASS", "WARN", "FAIL", "BLOCKED", "ERROR", "NOT_APPLICABLE", "STALE"}


def read_text(path: Path, limit: int = 20000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def make_result(
    *,
    gate: str,
    verdict: str,
    summary: str,
    evidence: list[str] | None = None,
    files: list[Path] | None = None,
    commands: list[str] | None = None,
    next_action: str = "",
) -> dict[str, Any]:
    if verdict not in VERDICTS:
        verdict = "ERROR"
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": gate,
        "verdict": verdict,
        "summary": summary,
        "evidence": evidence or [],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "files": [str(p) for p in files or []],
            "commands": commands or [],
        },
        "next_action": next_action,
    }


def work_context_command(task_name: str) -> str:
    return f"python {WORK_CONTEXT_PACK} --task {task_name}"


def resolve_task(task_arg: str, tasks_root: Path) -> Path:
    candidate = Path(task_arg)
    if candidate.exists() and candidate.is_dir():
        return candidate
    return tasks_root / task_arg


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def resolve_audited_path(task_dir: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return task_dir / raw


def assurance_hash_check(task_dir: Path) -> dict[str, Any] | None:
    artifact = task_dir / "core" / "ASSURANCE.json" if (task_dir / "core").is_dir() else task_dir / "ASSURANCE.json"
    if not artifact.exists():
        return None
    gate = "task-handoff-ready"
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except Exception as exc:
        return make_result(
            gate=gate,
            verdict="ERROR",
            summary=f"Assurance artifact is not valid JSON: {exc}",
            files=[artifact],
            next_action="Regenerate ASSURANCE.json with audited_input_hashes.",
        )
    hashes = data.get("audited_input_hashes") if isinstance(data, dict) else None
    if not isinstance(hashes, dict) or not hashes:
        return make_result(
            gate=gate,
            verdict="WARN",
            summary="Assurance artifact has no audited_input_hashes; freshness cannot be checked.",
            files=[artifact],
            next_action="Add audited_input_hashes or remove the stale-check artifact.",
        )
    evidence: list[str] = []
    stale: list[str] = []
    missing: list[str] = []
    checked_files = [artifact]
    for raw_path, expected in hashes.items():
        target = resolve_audited_path(task_dir, str(raw_path))
        checked_files.append(target)
        if not target.exists():
            missing.append(str(raw_path))
            continue
        actual = file_sha256(target)
        if actual != str(expected):
            stale.append(f"{raw_path}: expected {expected}, actual {actual}")
        else:
            evidence.append(f"fresh: {raw_path}")
    if missing:
        return make_result(
            gate=gate,
            verdict="BLOCKED",
            summary="Assurance artifact references missing input files.",
            evidence=[f"missing: {p}" for p in missing] + evidence,
            files=checked_files,
            next_action="Restore missing files or regenerate ASSURANCE.json.",
        )
    if stale:
        return make_result(
            gate=gate,
            verdict="STALE",
            summary="Assurance evidence is stale: audited inputs changed after verification.",
            evidence=stale + evidence,
            files=checked_files,
            next_action="Rerun verification and regenerate ASSURANCE.json before claiming completion.",
        )
    return make_result(
        gate=gate,
        verdict="PASS",
        summary="Assurance artifact input hashes are current.",
        evidence=evidence,
        files=checked_files,
        next_action="Continue; freshness evidence is current.",
    )


def task_handoff_ready(task_dir: Path) -> dict[str, Any]:
    gate = "task-handoff-ready"
    if not task_dir.exists() or not task_dir.is_dir():
        return make_result(
            gate=gate,
            verdict="BLOCKED",
            summary=f"Task directory does not exist: {task_dir}",
            files=[task_dir],
            next_action="Pass an existing task id or absolute task directory.",
        )

    is_v2 = (task_dir / "core").is_dir()
    handoff = task_dir / "core" / "HANDOFF.md" if is_v2 else task_dir / "HANDOFF.md"
    status = task_dir / "core" / "STATUS.md" if is_v2 else task_dir / "STATUS.md"
    design = task_dir / "design" / "设计文档.md" if is_v2 else task_dir / "设计文档.md"

    missing = [p for p in [handoff, design] if not p.exists()]
    if missing:
        return make_result(
            gate=gate,
            verdict="FAIL",
            summary="Required handoff/design documents are missing.",
            evidence=[f"missing: {p}" for p in missing],
            files=[handoff, design, status],
            next_action="Create the missing task documents before claiming handoff-ready.",
        )

    handoff_text = read_text(handoff)
    design_text = read_text(design)
    evidence: list[str] = []
    warnings: list[str] = []
    failures: list[str] = []

    checks = [
        ("HANDOFF has current goal", r"当前目标|current goal"),
        ("HANDOFF has next-start section", r"下次开始|下一步|next start|next action"),
        ("HANDOFF mentions validation or remaining gap", r"验证|测试|剩余|风险|缺口|blocked|risk"),
    ]
    for label, pattern in checks:
        if re.search(pattern, handoff_text, re.IGNORECASE):
            evidence.append(label)
        else:
            failures.append(label)

    if not status.exists():
        warnings.append("core/STATUS.md missing; run work_context_pack.py")
    else:
        status_text = read_text(status, 4000)
        if "当前任务" in status_text or "Current" in status_text:
            evidence.append("STATUS generated")
        else:
            warnings.append("STATUS exists but does not look generated by work_context_pack.py")

    if re.search(r"验收清单|完成标准|acceptance|done", design_text, re.IGNORECASE):
        evidence.append("Design includes acceptance/done criteria")
    else:
        warnings.append("Design lacks explicit acceptance/done criteria")

    if failures:
        return make_result(
            gate=gate,
            verdict="FAIL",
            summary="Task is not handoff-ready: " + "; ".join(failures),
            evidence=evidence + ["missing check: " + x for x in failures] + warnings,
            files=[handoff, design, status],
            commands=[work_context_command(task_dir.name)],
            next_action="Update HANDOFF with current goal, next start, and verification/risk notes.",
        )

    freshness = assurance_hash_check(task_dir)
    if freshness and freshness["verdict"] in {"STALE", "BLOCKED", "ERROR"}:
        return freshness

    if warnings:
        if freshness and freshness["verdict"] == "PASS":
            evidence += freshness.get("evidence", [])
        return make_result(
            gate=gate,
            verdict="WARN",
            summary="Task is usable for handoff, but has weaker evidence.",
            evidence=evidence + warnings,
            files=[handoff, design, status],
            commands=[work_context_command(task_dir.name)],
            next_action="Address warnings before long-session handoff or final completion.",
        )

    return make_result(
        gate=gate,
        verdict="PASS",
        summary="Task has enough current context for another agent to continue.",
        evidence=evidence + (freshness.get("evidence", []) if freshness else []),
        files=[handoff, design, status],
        commands=[work_context_command(task_dir.name)],
        next_action="Continue with the current phase or run stricter gates before final completion.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a read-only assurance gate.")
    parser.add_argument("--gate", choices=["task-handoff-ready"], required=True)
    parser.add_argument("--task", required=True, help="Task id under tasks-root or absolute task directory")
    parser.add_argument("--tasks-root", default=str(DEFAULT_TASKS_ROOT))
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    try:
        task_dir = resolve_task(args.task, Path(args.tasks_root))
        if args.gate == "task-handoff-ready":
            result = task_handoff_ready(task_dir)
        else:
            result = make_result(gate=args.gate, verdict="NOT_APPLICABLE", summary="Gate is not implemented.")
    except Exception as exc:
        result = make_result(gate=args.gate, verdict="ERROR", summary=f"Unhandled gate error: {exc}")

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result["verdict"] in {"PASS", "WARN", "NOT_APPLICABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
