#!/usr/bin/env python3
"""
Pure data shaping helpers for control_panel.py.

Tkinter should render decisions, not decide them.  Keeping these summaries
side-effect free makes the desktop panel easier to test while the UI evolves.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


LEVEL_ORDER = {"ok": 0, "info": 1, "warning": 2, "error": 3}


@dataclass(frozen=True)
class PanelDecision:
    level: str
    headline: str
    next_action: str
    why: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _worst(current: str, candidate: str) -> str:
    return candidate if LEVEL_ORDER[candidate] > LEVEL_ORDER[current] else current


def summarize_groups(groups: dict[str, list[str]]) -> str:
    if not groups:
        return "无变更"
    return " / ".join(f"{name} {len(paths)}" for name, paths in groups.items())


def summarize_status(data: dict) -> dict:
    git = _as_dict(data.get("git"))
    daemon = _as_dict(data.get("daemon"))
    recent = _as_dict(_as_dict(data.get("recent_commits")).get("summary"))
    logs = _as_list(_as_dict(data.get("logs")).get("maintain_tail"))

    dirty = bool(git.get("dirty"))
    change_count = int(git.get("change_count") or 0)
    ahead = int(git.get("ahead") or 0)
    behind = int(git.get("behind") or 0)
    daemon_running = bool(daemon.get("running"))
    groups = _as_dict(git.get("groups"))

    last_sync_failed = False
    for record in reversed(logs):
        if not isinstance(record, dict):
            continue
        if record.get("type") == "sync":
            last_sync_failed = "failed" in str(record.get("summary", "")).lower()
            break

    level = "ok"
    if dirty:
        level = _worst(level, "warning")
    if behind or last_sync_failed:
        level = _worst(level, "warning")

    if dirty:
        decision = PanelDecision(
            level=level,
            headline=f"有 {change_count} 个改动，先别急着同步",
            next_action="下一步：去“同步”页点“生成同步预览”",
            why=f"当前分组：{summarize_groups(groups)}",
        )
    elif behind:
        decision = PanelDecision(
            level=level,
            headline=f"本地落后远端 {behind} 个提交",
            next_action="下一步：运行同步前先检查 pull/rebase 状态",
            why="真实同步会先执行 pull --rebase。",
        )
    else:
        decision = PanelDecision(
            level=level,
            headline="当前没有待处理变更",
            next_action="下一步：如果要巡检，运行完整体检",
            why="工作区 clean，可以只观察 daemon 和最近日志。",
        )

    if last_sync_failed:
        decision = PanelDecision(
            level="warning",
            headline=decision.headline,
            next_action=decision.next_action,
            why=decision.why + "；最近一次自动同步失败，真正 push 前建议先看预览。",
        )

    cards = [
        {
            "title": "Git",
            "value": f"dirty={dirty} / ahead={ahead} / behind={behind} / 变更 {change_count}",
            "level": "warning" if dirty or behind else "ok",
        },
        {
            "title": "Daemon",
            "value": f"running={daemon_running} / processes={daemon.get('process_count', 0)}",
            "level": "ok" if daemon_running else "info",
        },
        {
            "title": "最近提交",
            "value": f"语义 {recent.get('semantic', 0)} / 检查点 {recent.get('checkpoint', 0)} / 总计 {recent.get('total', 0)}",
            "level": "info",
        },
        {
            "title": "变更分组",
            "value": summarize_groups(groups),
            "level": "warning" if dirty else "ok",
        },
    ]

    return {
        "decision": decision.to_dict(),
        "cards": cards,
        "changes": _as_list(git.get("changes")),
        "groups": groups,
        "last_sync_failed": last_sync_failed,
    }


def summarize_doctor(data: dict) -> dict:
    summary = _as_dict(data.get("summary"))
    errors = int(summary.get("ERROR") or 0)
    warnings = int(summary.get("WARNING") or 0)
    passes = int(summary.get("PASS") or 0)
    if errors:
        level = "error"
        headline = f"体检发现 {errors} 个错误"
        next_action = "下一步：先查看错误项，不要同步"
    elif warnings:
        level = "warning"
        headline = f"体检通过，但有 {warnings} 个提醒"
        next_action = "下一步：确认 warning 是否只是 dirty 工作区"
    else:
        level = "ok"
        headline = "体检全绿"
        next_action = "下一步：可以生成同步预览或继续工作"

    checks = []
    for item in _as_list(data.get("results")):
        if not isinstance(item, dict):
            continue
        checks.append({
            "id": item.get("id", ""),
            "level": item.get("level", "UNKNOWN"),
            "summary": item.get("summary", ""),
        })

    return {
        "decision": PanelDecision(level, headline, next_action, f"PASS {passes} / WARNING {warnings} / ERROR {errors}").to_dict(),
        "checks": checks,
    }


def summarize_sync_preview(data: dict) -> dict:
    changes = _as_list(data.get("changes"))
    groups = _as_dict(data.get("groups"))
    count = int(data.get("file_count") or len(changes))
    commit = str(data.get("commit") or "")
    if count:
        decision = PanelDecision(
            "warning",
            f"预览包含 {count} 个文件",
            "下一步：确认文件分组正常，再点“一键同步”",
            f"候选提交：{commit}",
        )
    else:
        decision = PanelDecision("ok", "没有需要同步的变更", "下一步：返回总览继续观察", "工作区 clean。")
    return {
        "decision": decision.to_dict(),
        "summary": data.get("summary", ""),
        "commit": commit,
        "groups_text": summarize_groups(groups),
        "groups": groups,
        "changes": changes,
    }


def summarize_log(data: dict) -> dict:
    summary = _as_dict(data.get("summary"))
    return {
        "semantic": int(summary.get("semantic") or 0),
        "checkpoint": int(summary.get("checkpoint") or 0),
        "total": int(summary.get("total") or 0),
        "entries": _as_list(data.get("entries")),
    }


def event_key(event: dict) -> str:
    return "|".join(str(event.get(k, "")) for k in ("timestamp", "source", "level", "title", "message"))


def summarize_event(event: dict) -> dict:
    timestamp = str(event.get("timestamp", ""))
    return {
        "key": event_key(event),
        "time": timestamp.replace("T", " ")[5:19] if timestamp else "",
        "level": str(event.get("level", "info")),
        "source": str(event.get("source", "external")),
        "title": str(event.get("title", "(无标题)")),
        "message": str(event.get("message", "")),
    }

