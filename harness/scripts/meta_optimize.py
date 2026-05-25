#!/usr/bin/env python3
"""meta_optimize.py — read-only suggestions for improving the harness.

This is intentionally a reporter, not a fixer. It reads existing logs and task
artifacts, then emits evidence-backed findings about places where the system is
still consuming manual steering or producing weak completion signals.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCHEMA_VERSION = 1
DEFAULT_LOGS = Path.home() / ".claude" / "logs"
DEFAULT_REPO = Path("D:/global-memory")
DEFAULT_TASKS = Path("D:/ClaudeTasks/active")

STATUS_RANK = {
    "critical": 3,
    "error": 3,
    "fail": 3,
    "failed": 3,
    "warning": 2,
    "warn": 2,
    "blocked": 2,
    "info": 1,
    "ok": 0,
}

AREA_BY_CHECK = {
    "retrieve_pointer_consumption": "retrieve",
    "retrieve_hitrate": "retrieve",
    "knowledge_unread": "memory",
    "lint_failure_rate": "memory",
    "memory_usage": "memory",
    "ghost_refs": "docs",
    "wip_age": "sync",
    "sync_failures": "sync",
    "traffic_imbalance": "skills",
    "log_liveness": "observability",
    "invocation_freq": "tools",
    "changelog_drift": "docs",
}

CONSUMER_BY_AREA = {
    "retrieve": "harness_retrieve.py / retrieve_inject.py",
    "memory": "memory_lint_gate.py / harness_retrieve.py",
    "docs": "task_complete.py / maintain.py doctor",
    "sync": "maintain.py sync / stop-hook summary",
    "skills": "skills/*/SKILL.md and prompt-system verification",
    "observability": "health runner / maintain.py report",
    "tools": "maintenance_manifest.json / scripts-registry.md",
    "work": "work_context_pack.py / task_complete.py",
}

AREA_PRIORITY = {
    "retrieve": 0,
    "work": 1,
    "sync": 2,
    "observability": 3,
    "docs": 4,
    "memory": 5,
    "skills": 6,
    "tools": 7,
}

SEVERITY_PRIORITY = {"high": 0, "medium": 1, "low": 2}


def parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def load_jsonl(path: Path, days: int | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days) if days else None
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if cutoff:
                    ts = parse_ts(row.get("ts") or row.get("timestamp"))
                    if ts and ts < cutoff:
                        continue
                rows.append(row)
    except OSError:
        return []
    return rows[-limit:] if limit else rows


def severity_from_status(status: str) -> str:
    rank = STATUS_RANK.get(str(status).lower(), 1)
    if rank >= 3:
        return "high"
    if rank == 2:
        return "medium"
    return "low"


def add_finding(
    findings: list[dict[str, Any]],
    *,
    area: str,
    severity: str,
    symptom: str,
    evidence: list[str] | None = None,
    suggested_change: str,
    consumer: str | None = None,
    risk_if_ignored: str,
    source: str,
) -> None:
    idx = len(findings) + 1
    findings.append({
        "id": f"MO-{idx:03d}",
        "severity": severity,
        "area": area,
        "symptom": symptom,
        "evidence": evidence or [],
        "suggested_change": suggested_change,
        "consumer": consumer or CONSUMER_BY_AREA.get(area, "unknown"),
        "risk_if_ignored": risk_if_ignored,
        "source": source,
    })


def latest_health_findings(logs: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(logs / "health_checks.jsonl", limit=1)
    if not rows:
        return []
    out: list[dict[str, Any]] = []
    latest = rows[-1]
    for signal in latest.get("signals", []):
        status = str(signal.get("status", "info")).lower()
        if STATUS_RANK.get(status, 0) < 2:
            continue
        check_id = str(signal.get("check_id", "unknown"))
        area = AREA_BY_CHECK.get(check_id, "observability")
        evidence = [str(x) for x in signal.get("evidence", [])[:5]]
        headline = str(signal.get("headline") or check_id)
        hint = str(signal.get("fix_hint") or "Turn this health signal into an owner-visible next action.")
        out.append({
            "area": area,
            "severity": severity_from_status(status),
            "symptom": headline,
            "evidence": evidence,
            "suggested_change": hint,
            "consumer": CONSUMER_BY_AREA.get(area),
            "risk_if_ignored": "Health signals remain as passive diagnostics and keep requiring manual interpretation.",
            "source": f"{logs / 'health_checks.jsonl'} latest:{check_id}",
        })
    return out


def retrieve_findings(logs: Path, days: int) -> list[dict[str, Any]]:
    rows = load_jsonl(logs / "retrieve_calls.jsonl", days=days)
    if not rows:
        return []
    total = len(rows)
    zero = sum(1 for r in rows if int(r.get("hit_count") or 0) == 0)
    by_task: Counter[str] = Counter(str(r.get("task") or "<no-task>") for r in rows if int(r.get("hit_count") or 0) == 0)
    findings: list[dict[str, Any]] = []
    zero_rate = zero / total if total else 0
    if zero_rate >= 0.3:
        evidence = [f"{total} retrieve calls in {days}d", f"zero_hit={zero} ({zero_rate:.1%})"]
        evidence += [f"{task}: {count} zero-hit" for task, count in by_task.most_common(5)]
        add_finding(
            findings,
            area="retrieve",
            severity="medium",
            symptom=f"Retrieve zero-hit rate is {zero_rate:.1%}",
            evidence=evidence,
            suggested_change="Add aliases/frontmatter for high zero-hit task queries, or reduce automatic injection when query text is not task-specific.",
            risk_if_ignored="Memory keeps existing but fails to participate in actual decisions.",
            source=str(logs / "retrieve_calls.jsonl"),
        )
    return findings


def maintain_findings(logs: Path, days: int) -> list[dict[str, Any]]:
    rows = load_jsonl(logs / "maintain.jsonl", days=days)
    if not rows:
        return []
    skipped = [r for r in rows if r.get("skipped_reason") == "user_wip"]
    if not skipped:
        return []
    last = skipped[-1]
    wip_count = int(last.get("wip_count") or 0)
    if wip_count < 20:
        return []
    evidence = [str(last.get("summary", "user_wip"))]
    evidence += [str(x) for x in (last.get("wip_files") or [])[:5]]
    return [{
        "area": "sync",
        "severity": "high" if wip_count >= 100 else "medium",
        "symptom": f"Sync is repeatedly skipped by large WIP set ({wip_count} files)",
        "evidence": evidence,
        "suggested_change": "Expose a checkpoint-splitting next action and make sync-ready assurance fail until WIP is classified or explicitly allowed.",
        "consumer": CONSUMER_BY_AREA["sync"],
        "risk_if_ignored": "Stop-hook sync appears active but never produces durable checkpoints.",
        "source": str(logs / "maintain.jsonl"),
    }]


def task_findings(tasks_root: Path) -> list[dict[str, Any]]:
    if not tasks_root.exists():
        return []
    missing_handoff: list[str] = []
    stale_handoff: list[str] = []
    for task in sorted(p for p in tasks_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        handoff = task / "core" / "HANDOFF.md" if (task / "core").exists() else task / "HANDOFF.md"
        if not handoff.exists():
            missing_handoff.append(task.name)
            continue
        text = handoff.read_text(encoding="utf-8", errors="replace")[:6000]
        if not re.search(r"下次开始|下一步|current goal|当前目标", text, re.IGNORECASE):
            stale_handoff.append(task.name)
    findings: list[dict[str, Any]] = []
    if missing_handoff:
        add_finding(
            findings,
            area="work",
            severity="medium",
            symptom=f"{len(missing_handoff)} active tasks lack HANDOFF",
            evidence=missing_handoff[:8],
            suggested_change="Add task-handoff-ready assurance before claiming task completion or switching sessions.",
            consumer=CONSUMER_BY_AREA["work"],
            risk_if_ignored="New sessions lose the real next action and ask the user to restate context.",
            source=str(tasks_root),
        )
    if stale_handoff:
        add_finding(
            findings,
            area="work",
            severity="low",
            symptom=f"{len(stale_handoff)} active tasks have weak HANDOFF next-step text",
            evidence=stale_handoff[:8],
            suggested_change="Require HANDOFF to include current goal plus next start command or first action.",
            consumer=CONSUMER_BY_AREA["work"],
            risk_if_ignored="HANDOFF exists but is not operational enough for agent continuation.",
            source=str(tasks_root),
        )
    return findings


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    logs = Path(args.logs_root)
    tasks_root = Path(args.tasks_root)
    findings: list[dict[str, Any]] = []

    for item in latest_health_findings(logs):
        add_finding(findings, **item)
    findings.extend(retrieve_findings(logs, args.days))
    findings.extend(maintain_findings(logs, args.days))
    findings.extend(task_findings(tasks_root))

    # De-duplicate obvious repeats by area+symptom, keeping first evidence-rich item.
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for f in findings:
        key = (f.get("area", ""), f.get("symptom", ""))
        if key in seen:
            continue
        seen.add(key)
        f["id"] = f"MO-{len(deduped) + 1:03d}"
        deduped.append(f)

    ranked = rank_findings(deduped)
    counts = Counter(f["severity"] for f in ranked)
    user_visible = build_user_visible_assessment(ranked, days=args.days, repo_root=Path(args.repo_root))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "read-only",
        "inputs": {
            "logs_root": str(logs),
            "tasks_root": str(tasks_root),
            "days": args.days,
        },
        "summary": {
            "finding_count": len(ranked),
            "by_severity": dict(counts),
        },
        "user_visible": user_visible,
        "findings": ranked,
    }


def rank_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(f: dict[str, Any]) -> tuple[int, int, int, str]:
        severity = SEVERITY_PRIORITY.get(str(f.get("severity", "low")).lower(), 9)
        area = AREA_PRIORITY.get(str(f.get("area", "")), 9)
        evidence_penalty = 0 if f.get("evidence") else 1
        return (severity, area, evidence_penalty, str(f.get("id", "")))

    ranked = sorted(findings, key=key)
    for idx, finding in enumerate(ranked, 1):
        finding["priority_rank"] = idx
        finding["actionability"] = actionability(finding)
    return ranked


def actionability(finding: dict[str, Any]) -> str:
    if not finding.get("evidence"):
        return "needs_evidence"
    if finding.get("consumer") and finding.get("suggested_change"):
        return "actionable"
    return "needs_owner"


def build_user_visible_assessment(findings: list[dict[str, Any]], days: int, repo_root: Path) -> dict[str, Any]:
    actionable = [f for f in findings if f.get("actionability") == "actionable"]
    top = actionable[0] if actionable else (findings[0] if findings else None)
    high_count = sum(1 for f in findings if f.get("severity") == "high")
    hidden_count = max(0, len(findings) - 3)
    retrieve_proposal = repo_root / ".meta" / "proposals" / "OP-2026-05-25-retrieve-pointer-consumption.md"
    zero_hit_proposal = repo_root / ".meta" / "proposals" / "OP-2026-05-25-human-query-zero-hit.md"
    experiment_config = repo_root / ".meta" / "experiments" / "retrieve_downrank_0_5.json"
    task_context_runtime_config = repo_root / ".meta" / "experiments" / "retrieve_task_context_fallback_review.json"
    simulation = load_retrieve_simulation()
    evaluation = load_latest_retrieve_evaluation(repo_root)
    zero_hit_analysis = load_zero_hit_analysis()
    task_context_evaluation = load_latest_task_context_evaluation(repo_root)
    task_context_review = load_latest_task_context_review(repo_root)
    task_context_trial = load_latest_task_context_trial(repo_root)

    if not findings:
        conclusion = "当前没有足够证据触发自优化。"
        recommended = "继续收集事件，不要为了优化而优化。"
        verdict = "NOT_READY"
        do_not = "不要修改 skill、hook 或 retrieve 参数。"
    elif (
        retrieve_proposal.exists()
        and experiment_config.exists()
        and evaluation
        and zero_hit_proposal.exists()
        and zero_hit_analysis
        and task_context_evaluation
        and task_context_runtime_config.exists()
        and task_context_review
        and task_context_trial
    ):
        review = task_context_review.get("summary", {})
        trial = task_context_trial.get("summary", {})
        verdict = "TASK_CONTEXT_TRIAL_PACK_READY"
        conclusion = (
            "task-scoped opt-in 已生成可复现试用包："
            f"{trial.get('task')} new_hits={trial.get('new_hits')}/{trial.get('compared')}，"
            f"accepted_tasks={review.get('accepted_tasks')}/{review.get('reviewed_tasks')}；"
            "默认仍不启用。"
        )
        recommended = "用 trial pack 直接评估体感；继续 task-scoped opt-in 观察，不扩到全局。"
        do_not = "不要默认启用；不要跳过 trial/relevance evidence 扩大 allowlist。"
    elif (
        retrieve_proposal.exists()
        and experiment_config.exists()
        and evaluation
        and zero_hit_proposal.exists()
        and zero_hit_analysis
        and task_context_evaluation
        and task_context_runtime_config.exists()
        and task_context_review
    ):
        sim = task_context_evaluation.get("summary", {})
        review = task_context_review.get("summary", {})
        verdict = "TASK_CONTEXT_TASK_SCOPED_READY"
        conclusion = (
            "task-context fallback 已完成相关性评审并收窄为 task-scoped opt-in："
            f"accepted_tasks={review.get('accepted_tasks')}/{review.get('reviewed_tasks')}，"
            f"new_hits={sim.get('new_hits')}/{sim.get('compared')}；"
            "默认仍不启用。"
        )
        recommended = "只在已接受任务上显式试用；继续收集用户可感知样本，不扩到全局。"
        do_not = "不要默认启用；不要把 rejected task 加回 allowlist；不要设置全局环境变量。"
    elif (
        retrieve_proposal.exists()
        and experiment_config.exists()
        and evaluation
        and zero_hit_proposal.exists()
        and zero_hit_analysis
        and task_context_evaluation
        and task_context_runtime_config.exists()
    ):
        summary = task_context_evaluation.get("summary", {})
        verdict = "TASK_CONTEXT_OPT_IN_READY"
        conclusion = (
            "task-context fallback 已有显式 opt-in runtime 配置："
            f"new_hits={summary.get('new_hits')}/{summary.get('compared')}，"
            f"still_empty={summary.get('still_empty')}；"
            "可单次试用，但新 pointer 相关性仍需人工评审。"
        )
        recommended = "用 --task-context-fallback-config 做单次 retrieve 对照；若样本相关性差，立即停留在 simulation/proposal。"
        do_not = "不要设置全局环境变量；不要默认启用 fallback；不要只用 new_hits=10/10 判定优化成功。"
    elif (
        retrieve_proposal.exists()
        and experiment_config.exists()
        and evaluation
        and zero_hit_proposal.exists()
        and zero_hit_analysis
        and task_context_evaluation
    ):
        summary = task_context_evaluation.get("summary", {})
        verdict = "TASK_CONTEXT_SIMULATION_REVIEW"
        conclusion = (
            "task-context fallback simulation 已完成："
            f"new_hits={summary.get('new_hits')}/{summary.get('compared')}，"
            f"still_empty={summary.get('still_empty')}；"
            "外显变化强，但新 pointer 相关性仍需人工评审。"
        )
        recommended = "人工查看 task-context simulation 的 changed 样本；若接受，只做 opt-in/task-scoped fallback。"
        do_not = "不要默认启用 fallback；不要只用 new_hits=10/10 判定优化成功。"
    elif retrieve_proposal.exists() and experiment_config.exists() and evaluation and zero_hit_proposal.exists() and zero_hit_analysis:
        assessment = zero_hit_analysis.get("external_assessment", {})
        summary = zero_hit_analysis.get("summary", {})
        verdict = "ZERO_HIT_PROPOSAL_READY"
        rate = summary.get("human_zero_hit_rate")
        rate_text = f"{float(rate) * 100:.1f}%" if isinstance(rate, (int, float)) else str(rate)
        conclusion = (
            "downrank 已被外显评估限制为 opt-in；新的 zero-hit proposal 已就绪："
            f"human_zero_hit={summary.get('human_zero_hit')}/{summary.get('human_calls')} "
            f"({rate_text}), "
            f"short_followup={summary.get('short_followup_zero_hit')}/{summary.get('human_zero_hit')}。"
        )
        recommended = "评审 human-query zero-hit proposal；下一步只做 task-context fallback simulation，不改默认行为。"
        do_not = assessment.get(
            "do_not_do_now",
            "不要降低 min_score、扩大 MAX_POINTERS 或默认启用 fallback。",
        )
    elif retrieve_proposal.exists() and experiment_config.exists() and evaluation:
        assessment = evaluation.get("external_assessment", {})
        summary = evaluation.get("summary", {})
        compared = summary.get("compared", assessment.get("compared"))
        changed = summary.get("changed", assessment.get("changed"))
        both_empty = assessment.get("both_empty")
        verdict = "EVALUATED_KEEP_OPT_IN"
        conclusion = (
            "retrieve downrank 已做 human-only 外显对照："
            f"{changed}/{compared} 条真实用户 query 改变首屏，"
            f"{both_empty}/{compared} 条优化前后都没有 memory pointer；"
            "外显收益不足以默认启用。"
        )
        recommended = (
            "保留显式 opt-in；下一步开新 proposal 处理 human query zero-hit，让用户先能看见 memory 参与。"
        )
        do_not = (
            "不要默认启用 downrank；不要继续只调 penalty；不要把内部 top2_changed 当成优化成功。"
        )
    elif retrieve_proposal.exists() and experiment_config.exists() and simulation:
        verdict = "READY_FOR_OPT_IN_EXPERIMENT"
        s = simulation.get("summary", {})
        conclusion = (
            "retrieve 温和 downrank 的 opt-in 实验已就绪："
            f"penalty=0.5 模拟 top2_changed={s.get('topn_changed')}，"
            f"zero_hit_delta={s.get('zero_hit_delta')}，guardrail={s.get('guardrail_status')}。"
        )
        recommended = (
            "只在单次 retrieve 或小范围任务中显式传 --downrank-config 试用，观察首屏结果是否更贴近任务。"
        )
        do_not = (
            "不要设置全局 HARNESS_RETRIEVE_DOWNRANK_CONFIG；不要默认启用；不要使用 0.2 强惩罚方案。"
        )
    elif retrieve_proposal.exists() and simulation:
        verdict = "READY_FOR_REVIEW"
        s = simulation.get("summary", {})
        conclusion = (
            "retrieve 优化 proposal 与只读模拟已就绪："
            f"penalty=0.5 时 top2_changed={s.get('topn_changed')}，"
            f"zero_hit_delta={s.get('zero_hit_delta')}，guardrail={s.get('guardrail_status')}。"
        )
        recommended = (
            "人工评审 retrieve proposal 和 simulation；若接受，下一步仍应先做小范围可回滚改动。"
        )
        do_not = (
            "不要跳过评审直接 apply；不要把 0.2 强惩罚方案上线，因为已观察到 zero-hit guardrail 风险。"
        )
    elif top:
        verdict = "READY_FOR_PROPOSAL"
        conclusion = f"当前最值得处理的是 {top.get('area')}：{top.get('symptom')}"
        recommended = (
            "先生成只读 proposal，不自动 apply；proposal 必须声明目标指标、风险、回滚和验证窗口。"
        )
        do_not = (
            "不要直接自动修改 frontmatter、skill、hook、sync 逻辑；当前阶段只允许 proposal。"
        )
    else:
        verdict = "INSUFFICIENT_DATA"
        conclusion = "有信号但缺少可执行证据。"
        recommended = "先补事件/evidence，不进入优化。"
        do_not = "不要把无证据 finding 升级为优化任务。"

    return {
        "verdict": verdict,
        "conclusion": conclusion,
        "recommended_first_action": recommended,
        "do_not_do_now": do_not,
        "experience_snapshot": {
            "window_days": days,
            "default_findings_shown": min(3, len(findings)),
            "raw_findings_hidden": hidden_count,
            "has_single_recommended_action": bool(findings),
            "high_severity_count": high_count,
            "top_area": top.get("area") if top else None,
            "top_consumer": top.get("consumer") if top else None,
            "user_can_decide_from_first_screen": bool(findings),
            "proposal_exists": retrieve_proposal.exists(),
            "zero_hit_proposal_exists": zero_hit_proposal.exists(),
            "experiment_config_exists": experiment_config.exists(),
            "simulation_available": bool(simulation),
            "external_evaluation_available": bool(evaluation),
            "external_compared": (evaluation.get("summary") or {}).get("compared") if evaluation else None,
            "external_changed": (evaluation.get("summary") or {}).get("changed") if evaluation else None,
            "external_both_empty": (evaluation.get("external_assessment") or {}).get("both_empty") if evaluation else None,
            "default_enable_ready": (evaluation.get("external_assessment") or {}).get("default_enable_ready") if evaluation else None,
            "zero_hit_analysis_available": bool(zero_hit_analysis),
            "human_zero_hit_rate": (zero_hit_analysis.get("summary") or {}).get("human_zero_hit_rate") if zero_hit_analysis else None,
            "task_context_evaluation_available": bool(task_context_evaluation),
            "task_context_new_hits": (task_context_evaluation.get("summary") or {}).get("new_hits") if task_context_evaluation else None,
            "task_context_compared": (task_context_evaluation.get("summary") or {}).get("compared") if task_context_evaluation else None,
            "task_context_runtime_config_exists": task_context_runtime_config.exists(),
            "task_context_review_available": bool(task_context_review),
            "task_context_accepted_tasks": (task_context_review.get("summary") or {}).get("accepted_tasks") if task_context_review else None,
            "task_context_rejected_tasks": (task_context_review.get("summary") or {}).get("rejected_tasks") if task_context_review else None,
            "task_context_trial_available": bool(task_context_trial),
            "task_context_trial_new_hits": (task_context_trial.get("summary") or {}).get("new_hits") if task_context_trial else None,
            "task_context_trial_compared": (task_context_trial.get("summary") or {}).get("compared") if task_context_trial else None,
        },
        "simulation_summary": simulation.get("summary", {}) if simulation else {},
        "external_evaluation_summary": evaluation.get("external_assessment", {}) if evaluation else {},
        "zero_hit_summary": zero_hit_analysis.get("summary", {}) if zero_hit_analysis else {},
        "task_context_evaluation_summary": task_context_evaluation.get("summary", {}) if task_context_evaluation else {},
        "task_context_review_summary": task_context_review.get("summary", {}) if task_context_review else {},
        "task_context_trial_summary": task_context_trial.get("summary", {}) if task_context_trial else {},
        "top_opportunities": [
            {
                "id": f.get("id"),
                "area": f.get("area"),
                "severity": f.get("severity"),
                "symptom": f.get("symptom"),
                "signal": (f.get("evidence") or [f.get("source", "")])[0],
                "proposed_change": f.get("suggested_change"),
                "consumer": f.get("consumer"),
                "risk": f.get("risk_if_ignored"),
                "actionability": f.get("actionability"),
            }
            for f in findings[:3]
        ],
    }


def load_retrieve_simulation() -> dict[str, Any] | None:
    script = Path(__file__).resolve().parent / "retrieve_downrank_simulation.py"
    if not script.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--penalty-factor",
                "0.5",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_latest_retrieve_evaluation(repo_root: Path) -> dict[str, Any] | None:
    eval_dir = repo_root / ".meta" / "evaluations"
    if not eval_dir.is_dir():
        return None
    candidates = sorted(eval_dir.glob("EV-*-retrieve-downrank-human-visible.json"))
    if not candidates:
        return None
    for path in reversed(candidates):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict):
            data.setdefault("artifact_path", str(path))
            return data
    return None


def load_latest_task_context_evaluation(repo_root: Path) -> dict[str, Any] | None:
    eval_dir = repo_root / ".meta" / "evaluations"
    if not eval_dir.is_dir():
        return None
    candidates = sorted(eval_dir.glob("EV-*-task-context-simulation.json"))
    if not candidates:
        return None
    for path in reversed(candidates):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict):
            data.setdefault("artifact_path", str(path))
            return data
    return None


def load_latest_task_context_review(repo_root: Path) -> dict[str, Any] | None:
    eval_dir = repo_root / ".meta" / "evaluations"
    if not eval_dir.is_dir():
        return None
    candidates = sorted(eval_dir.glob("EV-*-task-context-relevance-review.json"))
    if not candidates:
        return None
    for path in reversed(candidates):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict):
            data.setdefault("artifact_path", str(path))
            return data
    return None


def load_latest_task_context_trial(repo_root: Path) -> dict[str, Any] | None:
    trial_dir = repo_root / ".meta" / "trials"
    if not trial_dir.is_dir():
        return None
    candidates = sorted(trial_dir.glob("TR-*-task-context-*.json"))
    if not candidates:
        return None
    for path in reversed(candidates):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict):
            data.setdefault("artifact_path", str(path))
            return data
    return None


def load_zero_hit_analysis() -> dict[str, Any] | None:
    script = Path(__file__).resolve().parent / "retrieve_zero_hit_analysis.py"
    if not script.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def render_markdown(report: dict[str, Any]) -> str:
    visible = report.get("user_visible", {})
    snapshot = visible.get("experience_snapshot", {})
    lines = [
        "# Meta-Optimize Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- mode: `{report['mode']}`",
        f"- findings: `{report['summary']['finding_count']}`",
        "",
        "## Current Decision",
        "",
        f"- Verdict: `{visible.get('verdict', 'UNKNOWN')}`",
        f"- Conclusion: {visible.get('conclusion', '')}",
        f"- Recommended first action: {visible.get('recommended_first_action', '')}",
        f"- Do not do now: {visible.get('do_not_do_now', '')}",
        "",
        "## Experience Snapshot",
        "",
        f"- default_findings_shown: `{snapshot.get('default_findings_shown', 0)}`",
        f"- raw_findings_hidden: `{snapshot.get('raw_findings_hidden', 0)}`",
        f"- has_single_recommended_action: `{snapshot.get('has_single_recommended_action', False)}`",
        f"- top_area: `{snapshot.get('top_area')}`",
        f"- external_evaluation_available: `{snapshot.get('external_evaluation_available', False)}`",
        f"- default_enable_ready: `{snapshot.get('default_enable_ready')}`",
        f"- zero_hit_analysis_available: `{snapshot.get('zero_hit_analysis_available', False)}`",
        f"- human_zero_hit_rate: `{snapshot.get('human_zero_hit_rate')}`",
        f"- task_context_evaluation_available: `{snapshot.get('task_context_evaluation_available', False)}`",
        f"- task_context_new_hits: `{snapshot.get('task_context_new_hits')}/{snapshot.get('task_context_compared')}`",
        f"- task_context_runtime_config_exists: `{snapshot.get('task_context_runtime_config_exists', False)}`",
        f"- task_context_review_available: `{snapshot.get('task_context_review_available', False)}`",
        f"- task_context_review: `accepted={snapshot.get('task_context_accepted_tasks')}, rejected={snapshot.get('task_context_rejected_tasks')}`",
        f"- task_context_trial_available: `{snapshot.get('task_context_trial_available', False)}`",
        f"- task_context_trial_new_hits: `{snapshot.get('task_context_trial_new_hits')}/{snapshot.get('task_context_trial_compared')}`",
        "",
    ]
    for f in report["findings"]:
        lines.append(f"## {f['id']} [{f['severity']}] {f['area']}")
        lines.append("")
        lines.append(f"- Symptom: {f['symptom']}")
        lines.append(f"- Suggested change: {f['suggested_change']}")
        lines.append(f"- Consumer: {f['consumer']}")
        lines.append(f"- Risk if ignored: {f['risk_if_ignored']}")
        lines.append(f"- Source: `{f['source']}`")
        if f.get("evidence"):
            lines.append("- Evidence:")
            for item in f["evidence"][:8]:
                lines.append(f"  - `{item}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only meta-optimization report for global-memory harness.")
    parser.add_argument("--logs-root", default=str(DEFAULT_LOGS))
    parser.add_argument("--tasks-root", default=str(DEFAULT_TASKS))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO), help="Reserved for future source scans; not modified.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

