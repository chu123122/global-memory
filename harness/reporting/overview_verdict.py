#!/usr/bin/env python3
"""控制面板「当前结论」的唯一数据源。

UX-REVIEW-2026-04-28.md Top 1 / D1 修复点：
原 status.py 的 _set_decision 被 _update_timeline_card 劫持
（status.py:367），导致首屏结论卡的红字总是 token saver 子问题——
99% 用户根本不知道 token saver 是什么。

本模块把结论的数据源**收口**到 4 个真实健康源：
  1. git    （来源 harness_status.py --json）
  2. daemon （同上）
  3. doctor （maintain.py fix --json 的 summary）
  4. health （harness.health.runner 的 signals）

**铁律**：timeline / token saver / AI 调用证据**永远不参与 severity**。
它们是诊断材料，应隔离到诊断 tab。

dict in / dict out，零 dataclass：
  - 输入直接吃 panel_api 的 JSON，view 不必转换
  - 输出可序列化，可作 JSONL 落盘 / 测试断言

severity 合并：取所有子系统最严级。
  ok < info < warning < error
  health 的 critical → error（统一到 4 级）
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# 4 级，数字越大越严。critical 在合并前已映射到 error。
_SEVERITY_RANK = {"ok": 0, "info": 1, "warning": 2, "error": 3}
_RANK_TO_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}


def _as_dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list:
    return v if isinstance(v, list) else []


def _normalize_severity(s: str) -> str:
    """health 用 critical，本模块统一用 error。其它原样保留。"""
    s = (s or "ok").lower()
    if s == "critical":
        return "error"
    if s in _SEVERITY_RANK:
        return s
    return "ok"


def _max_severity(severities: list[str]) -> str:
    if not severities:
        return "ok"
    rank = max(_SEVERITY_RANK[_normalize_severity(s)] for s in severities)
    return _RANK_TO_SEVERITY[rank]


# ---------- 子系统提取 ----------


def _git_subsystem(status_json: dict) -> dict:
    git = _as_dict(status_json.get("git"))
    dirty = bool(git.get("dirty"))
    behind = int(git.get("behind") or 0)
    ahead = int(git.get("ahead") or 0)
    change_count = int(git.get("change_count") or 0)

    if behind:
        # 落后远端最严：可能 push 被拒
        sev = "warning"
        summary = f"落后远端 {behind} 个提交"
    elif dirty:
        sev = "warning"
        summary = f"{change_count} 个未提交变更"
    else:
        sev = "ok"
        summary = "干净" if not ahead else f"clean，本地领先 {ahead}"
    return {"name": "Git", "severity": sev, "summary": summary}


def _daemon_subsystem(status_json: dict) -> dict:
    daemon = _as_dict(status_json.get("daemon"))
    running = bool(daemon.get("running"))
    procs = int(daemon.get("process_count") or 0)
    if running:
        return {"name": "Daemon", "severity": "ok", "summary": f"运行中（{procs} 进程）"}
    return {"name": "Daemon", "severity": "warning", "summary": "未运行"}


def _doctor_subsystem(doctor_summary: dict) -> dict:
    summary = _as_dict(doctor_summary.get("summary"))
    err = int(summary.get("ERROR") or 0)
    warn = int(summary.get("WARNING") or 0)
    passed = int(summary.get("PASS") or 0)
    if err:
        return {"name": "Doctor", "severity": "error",
                "summary": f"ERR {err} / WARN {warn}"}
    if warn:
        return {"name": "Doctor", "severity": "warning",
                "summary": f"WARN {warn}（{passed} 项通过）"}
    if passed:
        return {"name": "Doctor", "severity": "ok",
                "summary": f"{passed} 项全过"}
    # 空 summary 不算问题，只是没跑过
    return {"name": "Doctor", "severity": "info", "summary": "未运行"}


def _health_subsystem(health_signals: list) -> dict:
    """聚合 health runner 的 signals 为单条 subsystem 摘要。

    单独每条 signal 的细节由「健康信号」区块展示，本函数只负责
    给「当前结论」喂一个聚合 severity + 一句话计数。
    """
    signals = _as_list(health_signals)
    if not signals:
        return {"name": "Health", "severity": "info", "summary": "未运行"}

    crit = warn = info = ok = 0
    for s in signals:
        if not isinstance(s, dict):
            continue
        st = _normalize_severity(s.get("status", "ok"))
        # 注意：normalize 后 critical→error
        if st == "error":
            crit += 1
        elif st == "warning":
            warn += 1
        elif st == "info":
            info += 1
        else:
            ok += 1

    total = crit + warn + info + ok
    if crit:
        return {"name": "Health", "severity": "error",
                "summary": f"{total} 项中 {crit} 严重 / {warn} 警告"}
    if warn:
        return {"name": "Health", "severity": "warning",
                "summary": f"{total} 项中 {warn} 警告"}
    return {"name": "Health", "severity": "ok", "summary": f"{total} 项全过"}


# ---------- 文案合成 ----------


def _build_headline(severity: str, subsystems: list[dict]) -> str:
    if severity == "ok":
        return "一切正常"
    # 找出第一个最严级子系统作为头条
    rank = _SEVERITY_RANK[severity]
    worst = next(
        (s for s in subsystems if _SEVERITY_RANK[_normalize_severity(s["severity"])] == rank),
        None,
    )
    if worst is None:
        return {"warning": "需要注意", "error": "出错了", "info": "等待数据"}.get(severity, "")
    glyph = {"info": "·", "warning": "⚠", "error": "✗"}.get(severity, "·")
    return f"{glyph} {worst['summary']}"


def _build_reason(subsystems: list[dict]) -> str:
    return " · ".join(f"{s['name']} {s['summary']}" for s in subsystems)


def _build_next_action(severity: str, subsystems: list[dict]) -> str:
    """给用户一句**可直接照做**的下一步——优先给具体 CLI，其次指向 tab。

    设计原则：用户是观察者，不操作面板按钮（Q7）；面板的工作是
    告诉他下一步要做什么，他打开终端复制粘贴跑一行命令。
    """
    if severity == "ok":
        return "无需操作"
    rank = _SEVERITY_RANK[severity]
    for s in subsystems:
        if _SEVERITY_RANK[_normalize_severity(s["severity"])] != rank:
            continue
        if s["name"] == "Git":
            return "终端跑：python -m harness.maintain sync"
        if s["name"] == "Daemon":
            return "终端跑：python -m harness.maintain daemon start"
        if s["name"] == "Doctor":
            return "切「健康」tab 看具体哪项警告"
        if s["name"] == "Health":
            return "切「健康」tab 看 signal 列表"
    return "查看明细"


# ---------- 主入口 ----------


def build_overview_verdict(
    status_json: dict | None,
    doctor_summary: dict | None,
    health_signals: list | None,
    *,
    last_checked: str | None = None,
) -> dict:
    """聚合 4 个子系统为一条「当前结论」。

    Args:
        status_json: harness_status.py --json 的输出，含 git / daemon。
            None 或空 dict 也可，按"未运行"处理。
        doctor_summary: maintain.py fix --json 的输出，含 summary{PASS,WARNING,ERROR}。
            None 或空 dict 也可。
        health_signals: harness.health.runner 的 signals 列表。
            每条 signal 是 dict，至少有 status 字段。
            **本参数是 timeline 唯一不参与的硬保证**——传 timeline 进来不会污染。
        last_checked: ISO 时间戳；None 时取当前 UTC 时间。

    Returns:
        OverviewVerdict dict，结构见模块 docstring。
    """
    status_json = _as_dict(status_json)
    doctor_summary = _as_dict(doctor_summary)
    health_signals = _as_list(health_signals)

    subsystems = [
        _git_subsystem(status_json),
        _daemon_subsystem(status_json),
        _doctor_subsystem(doctor_summary),
        _health_subsystem(health_signals),
    ]

    severity = _max_severity([s["severity"] for s in subsystems])
    headline = _build_headline(severity, subsystems)
    reason = _build_reason(subsystems)
    next_action = _build_next_action(severity, subsystems)

    return {
        "severity": severity,
        "headline": headline,
        "reason": reason,
        "next_action": next_action,
        "primary_button": None,  # Q7 决策：面板纯只读，无动作按钮
        "subsystems": subsystems,
        "last_checked": last_checked or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "debug": {
            "input_has_status": bool(status_json),
            "input_has_doctor": bool(doctor_summary),
            "input_signal_count": len(health_signals),
        },
    }
