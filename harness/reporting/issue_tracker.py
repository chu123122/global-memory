#!/usr/bin/env python3
"""issue_tracker · D2：4 态闭环 + CLI

设计文档：$env:CLAUDE_TASKS_ACTIVE/feedback-loop-v1/设计文档.md
SPEC：$env:CLAUDE_TASKS_ACTIVE/feedback-loop-v1/SPEC.md

D1 + D2 范围（本文件）：
  - Issue 数据模型（每行 = 1 次状态变迁，append-only）
  - compute_issue_id() 稳定 ID
  - extract_from_health() ETL：
    · non-ok signal 派生 detected（首次）
    · 已开着的同 issue_id 跳过（V2 去重）
    · 已 fixed/archived 的 issue 又被报告 → append reopened
    · 上次开着但本次 health 不再报告 → append fixed（自动；V4）
  - CLI: --extract / --archive <id> / --reopen <id>，共享 --note
  - --archive 输出沉淀建议（V5，不写文件）

D3+ 留做：
  - UI 集成（control_panel_pyside/views/issue_loop.py）
  - stop-hook 自动跑 issue_tracker --extract（增量 ETL）

Schema（每行 JSON）：
  {
    "issue_id": "health.sync_failures.a3f9c2e1",
    "ts": "2026-04-28T12:30:15+00:00",
    "event": "detected | fixed | archived | reopened",
    "source": "health",
    "severity": "critical | warning | info",
    "title": "...",
    "evidence_hash": "a3f9c2e1",
    "evidence": [...],
    "fix_hint": "...",
    "actor": "auto | user",
    "note": ""
  }

状态机（设计文档 §4，4 态简化）：
    detected ──→ fixing ──→ fixed ──→ archived
       ↑                       │          │
       └────── reopened ←──────┴──────────┘
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# 默认路径（CLI 时可覆盖）
DEFAULT_HEALTH_PATH = Path.home() / ".claude" / "logs" / "health_checks.jsonl"
DEFAULT_ISSUES_PATH = Path.home() / ".claude" / "logs" / "issues.jsonl"

# health 的 source 标识（设计文档 §3：source 是 ETL 来源类型，不含 check_id）
SOURCE_HEALTH = "health"

# health Signal.status 到 Issue.severity 的映射
_SEVERITY_MAP = {
    "critical": "critical",
    "error": "critical",
    "warning": "warning",
    "info": "info",
    "ok": "ok",
}

# "开着的"状态：detector 又报告同 issue_id 时不应重复 append detected
_OPEN_EVENTS = {"detected", "reopened", "fixing"}
# "已结的"状态：detector 又报告时应 append reopened
_CLOSED_EVENTS = {"fixed", "archived"}


# ---------- 数据模型 ----------

@dataclass
class Issue:
    """每行 issues.jsonl = 1 次状态变迁。"""
    issue_id: str
    ts: str
    event: str  # detected | fixed | archived | reopened
    source: str
    severity: str
    title: str
    evidence_hash: str
    evidence: list[str] = field(default_factory=list)
    fix_hint: str = ""
    actor: str = "auto"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ---------- 稳定 ID ----------

_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:+\-.]+")
_NM_RE = re.compile(r"\d+/\d+")
_PURE_NUM_RE = re.compile(r"\b\d+\b")


def _strip_volatile(line: str) -> str:
    """去掉 evidence 行里随时间变化的字段：ISO 时间 / N/M 计数 / 纯数字。"""
    line = _TS_RE.sub("<TS>", line)
    line = _NM_RE.sub("<N/M>", line)
    line = _PURE_NUM_RE.sub("<N>", line)
    return line.strip()


def compute_issue_id(source: str, check_id: str, evidence: list[str]) -> str:
    """稳定 issue_id = `{source}.{check_id}.{evidence_hash[:8]}`。"""
    canonical = "\n".join(_strip_volatile(e) for e in evidence[:3])
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return f"{source}.{check_id}.{h}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- IO ----------

def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _append_jsonl(path: Path, issues: list[Issue]) -> None:
    if not issues:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for issue in issues:
            f.write(issue.to_jsonl_line() + "\n")


def _last_event_by_id(issues_path: Path) -> dict[str, str]:
    """按 issue_id 取最后一条记录的 event。"""
    out: dict[str, str] = {}
    for r in _read_jsonl(issues_path):
        iid = r.get("issue_id")
        ev = r.get("event")
        if iid and ev:
            out[iid] = ev
    return out


def _last_record_by_id(issues_path: Path) -> dict[str, dict]:
    """按 issue_id 取最后一条完整记录（用于 reopened/archived 元数据继承）。"""
    out: dict[str, dict] = {}
    for r in _read_jsonl(issues_path):
        iid = r.get("issue_id")
        if iid:
            out[iid] = r
    return out


# ---------- ETL 主流程 ----------

def _signal_to_detected(signal: dict) -> Issue | None:
    """把 health Signal dict 转成 detected Issue。返回 None 表示 ok 信号或缺字段跳过。"""
    status = str(signal.get("status", "ok"))
    if status == "ok":
        return None
    check_id = str(signal.get("check_id", ""))
    if not check_id:
        return None
    evidence = signal.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = []

    issue_id = compute_issue_id(SOURCE_HEALTH, check_id, [str(e) for e in evidence])
    evidence_hash = issue_id.rsplit(".", 1)[-1]

    return Issue(
        issue_id=issue_id,
        ts=_now_iso(),
        event="detected",
        source=SOURCE_HEALTH,
        severity=_SEVERITY_MAP.get(status, status),
        title=str(signal.get("headline") or check_id),
        evidence_hash=evidence_hash,
        evidence=[str(e) for e in evidence[:8]],
        fix_hint=str(signal.get("fix_hint") or ""),
        actor="auto",
    )


def _make_event(base: dict, event: str, note: str = "", actor: str = "auto") -> Issue:
    """从已有 issue 记录派生一条新 event（同 issue_id，新 ts）。

    用于 fixed/reopened/archived 时继承 source/severity/title/evidence 等元数据。
    """
    return Issue(
        issue_id=base["issue_id"],
        ts=_now_iso(),
        event=event,
        source=base.get("source", SOURCE_HEALTH),
        severity=base.get("severity", "info"),
        title=base.get("title", ""),
        evidence_hash=base.get("evidence_hash", ""),
        evidence=base.get("evidence", []) or [],
        fix_hint=base.get("fix_hint", ""),
        actor=actor,
        note=note,
    )


def extract_from_health(
    health_path: Path = DEFAULT_HEALTH_PATH,
    issues_path: Path = DEFAULT_ISSUES_PATH,
    *,
    write: bool = True,
) -> list[Issue]:
    """ETL 主流程。三类 event 都可能产生：

    1. detected：新出现的 non-ok signal（issues.jsonl 中无该 id）
    2. reopened：health 又报告了已 fixed/archived 的 issue_id
    3. fixed（自动）：上次开着的 issue_id 本次 health 不再报告

    去重：已开着的 id 不重复 append detected（V2）。

    Returns:
        本次新增的 Issue 列表（detected + reopened + fixed 都算）。
    """
    records = _read_jsonl(health_path)
    if not records:
        return []
    last = records[-1]
    signals = last.get("signals") or []
    if not isinstance(signals, list):
        return []

    # 当前 health 报告的 (issue_id → signal_dict) 候选
    current_open: dict[str, dict] = {}
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        if str(sig.get("status", "ok")) == "ok":
            continue
        check_id = str(sig.get("check_id", ""))
        if not check_id:
            continue
        evidence = sig.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        iid = compute_issue_id(SOURCE_HEALTH, check_id, [str(e) for e in evidence])
        # 同 record 内同 id 只取第一条
        current_open.setdefault(iid, sig)

    # 历史状态
    last_event = _last_event_by_id(issues_path)
    last_record = _last_record_by_id(issues_path)

    new_issues: list[Issue] = []

    # 1. 处理当前 health 报告的每个 issue_id
    for iid, sig in current_open.items():
        prev_event = last_event.get(iid)
        if prev_event in _OPEN_EVENTS:
            # 已开着的，跳过（V2 去重）
            continue
        if prev_event in _CLOSED_EVENTS:
            # 已 fixed/archived 的复活 → reopened（state 回 detected）
            base = last_record.get(iid, {})
            # 用最新 evidence 覆盖（这次报告的内容可能比历史新）
            base = dict(base)
            evidence_list = sig.get("evidence") or []
            if isinstance(evidence_list, list):
                base["evidence"] = [str(e) for e in evidence_list[:8]]
            base["title"] = str(sig.get("headline") or base.get("title", ""))
            base["fix_hint"] = str(sig.get("fix_hint") or base.get("fix_hint", ""))
            new_issues.append(_make_event(base, event="reopened"))
            continue
        # prev_event 为空 → 首次 detected
        issue = _signal_to_detected(sig)
        if issue is not None:
            new_issues.append(issue)

    # 2. 自动 fixed：上次开着但本次未报告
    for iid, prev_event in last_event.items():
        if prev_event not in _OPEN_EVENTS:
            continue
        if iid in current_open:
            continue
        base = last_record.get(iid, {})
        if not base:
            continue
        new_issues.append(_make_event(base, event="fixed"))

    if write and new_issues:
        _append_jsonl(issues_path, new_issues)

    return new_issues


# ---------- 用户操作（archive / reopen） ----------


class IssueNotFoundError(Exception):
    pass


class IssueStateError(Exception):
    pass


def archive_issue(
    issue_id: str,
    note: str = "",
    issues_path: Path = DEFAULT_ISSUES_PATH,
    *,
    write: bool = True,
) -> tuple[Issue, str]:
    """把 issue 转 archived 状态（用户主动忽略 / 沉淀完手动归档）。

    允许的来源态：detected / reopened / fixing / fixed
    （只有 archived 不可再 archive）

    Returns:
        (新增的 archived Issue, 沉淀建议字符串)
    """
    last_event = _last_event_by_id(issues_path)
    last_record = _last_record_by_id(issues_path)
    if issue_id not in last_event:
        raise IssueNotFoundError(f"issue_id 不存在：{issue_id}")
    prev = last_event[issue_id]
    if prev == "archived":
        raise IssueStateError(f"issue 已是 archived：{issue_id}")

    base = last_record[issue_id]
    new = _make_event(base, event="archived", note=note, actor="user")

    if write:
        _append_jsonl(issues_path, [new])

    suggestion = _learning_target_suggestion(issue_id, base)
    return new, suggestion


def reopen_issue(
    issue_id: str,
    note: str = "",
    issues_path: Path = DEFAULT_ISSUES_PATH,
    *,
    write: bool = True,
) -> Issue:
    """手动 reopen（当用户认为 issue 没真修好或又出现了）。

    允许的来源态：fixed / archived（已结的才能 reopen）
    """
    last_event = _last_event_by_id(issues_path)
    last_record = _last_record_by_id(issues_path)
    if issue_id not in last_event:
        raise IssueNotFoundError(f"issue_id 不存在：{issue_id}")
    prev = last_event[issue_id]
    if prev not in _CLOSED_EVENTS:
        raise IssueStateError(f"只有 fixed/archived 的 issue 可 reopen，当前态：{prev}")

    base = last_record[issue_id]
    new = _make_event(base, event="reopened", note=note, actor="user")

    if write:
        _append_jsonl(issues_path, [new])

    return new


def _learning_target_suggestion(issue_id: str, base: dict) -> str:
    """生成沉淀目标建议（不写文件，仅 CLI 输出）。

    格式：fixes/{check_id}_{YYYY-MM-DD}.md
    """
    parts = issue_id.split(".")
    check_id = parts[1] if len(parts) >= 2 else "unknown"
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"fixes/{check_id}_{date_str}.md"


# ---------- CLI ----------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="harness.issue_tracker",
        description="issue_tracker · ETL + 4 态闭环",
    )
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument("--extract", action="store_true", help="跑 ETL：从 health_checks.jsonl 派生 detected/reopened/fixed")
    action.add_argument("--archive", metavar="ID", help="把 issue 标 archived（可选 --note）")
    action.add_argument("--reopen", metavar="ID", help="手动 reopen 已结的 issue（可选 --note）")
    action.add_argument("--list-open", action="store_true", help="列当前所有开着的 issue（detected/reopened/fixing）")

    p.add_argument("--note", default="", help="archive/reopen 时的备注，会写入 issue 记录")
    p.add_argument("--json", action="store_true", help="输出 JSON 而不是人话")
    p.add_argument("--dry-run", action="store_true", help="不写盘，只输出会发生什么")
    p.add_argument(
        "--health-path", type=Path, default=DEFAULT_HEALTH_PATH,
        help=f"health_checks.jsonl 路径（默认 {DEFAULT_HEALTH_PATH}）",
    )
    p.add_argument(
        "--issues-path", type=Path, default=DEFAULT_ISSUES_PATH,
        help=f"issues.jsonl 路径（默认 {DEFAULT_ISSUES_PATH}）",
    )
    return p


def _print_extract_human(new_issues: list[Issue], dry_run: bool) -> None:
    if not new_issues:
        print("无新事件（全 ok 或无变化）")
        return
    prefix = "(dry-run) " if dry_run else ""
    by_event: dict[str, list[Issue]] = {}
    for i in new_issues:
        by_event.setdefault(i.event, []).append(i)
    print(f"{prefix}新增 {len(new_issues)} 条事件：")
    for ev in ("detected", "reopened", "fixed"):
        if ev not in by_event:
            continue
        glyph = {"detected": "+", "reopened": "↻", "fixed": "✓"}[ev]
        print(f"  {glyph} {ev}（{len(by_event[ev])} 条）")
        for i in by_event[ev]:
            print(f"      [{i.severity:>8}] {i.issue_id}")
            print(f"               {i.title}")


def _print_extract_json(new_issues: list[Issue], dry_run: bool) -> None:
    payload = {
        "dry_run": dry_run,
        "new_count": len(new_issues),
        "issues": [i.to_dict() for i in new_issues],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_archive_human(issue: Issue, suggestion: str, dry_run: bool) -> None:
    prefix = "(dry-run) " if dry_run else ""
    print(f"{prefix}已 archive: {issue.issue_id}")
    print(f"  {issue.title}")
    if issue.note:
        print(f"  备注: {issue.note}")
    print()
    print(f"建议沉淀到：{suggestion}")
    print("（仅 CLI 提示，不写文件；如需沉淀请手动 cp/编辑）")


def _print_reopen_human(issue: Issue, dry_run: bool) -> None:
    prefix = "(dry-run) " if dry_run else ""
    print(f"{prefix}已 reopen: {issue.issue_id}")
    print(f"  {issue.title}")
    if issue.note:
        print(f"  备注: {issue.note}")


def _print_list_open(issues_path: Path) -> None:
    last_event = _last_event_by_id(issues_path)
    last_record = _last_record_by_id(issues_path)
    open_ids = [iid for iid, ev in last_event.items() if ev in _OPEN_EVENTS]
    if not open_ids:
        print("当前无开着的 issue")
        return
    print(f"开着的 issue（共 {len(open_ids)} 条）：")
    by_sev: dict[str, list[str]] = {}
    for iid in open_ids:
        rec = last_record[iid]
        by_sev.setdefault(rec.get("severity", "info"), []).append(iid)
    for sev in ("critical", "warning", "info"):
        if sev not in by_sev:
            continue
        for iid in by_sev[sev]:
            rec = last_record[iid]
            print(f"  [{sev:>8}] {iid}")
            print(f"           {rec.get('title', '')}")
            print(f"           当前态: {last_event[iid]}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = _build_parser().parse_args(argv)
    write = not args.dry_run

    if args.extract:
        new_issues = extract_from_health(
            health_path=args.health_path,
            issues_path=args.issues_path,
            write=write,
        )
        if args.json:
            _print_extract_json(new_issues, dry_run=args.dry_run)
        else:
            _print_extract_human(new_issues, dry_run=args.dry_run)
        return 1 if new_issues else 0

    if args.archive:
        try:
            issue, suggestion = archive_issue(
                args.archive,
                note=args.note,
                issues_path=args.issues_path,
                write=write,
            )
        except (IssueNotFoundError, IssueStateError) as e:
            print(f"错误：{e}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps({"issue": issue.to_dict(), "learning_target": suggestion}, ensure_ascii=False, indent=2))
        else:
            _print_archive_human(issue, suggestion, dry_run=args.dry_run)
        return 0

    if args.reopen:
        try:
            issue = reopen_issue(
                args.reopen,
                note=args.note,
                issues_path=args.issues_path,
                write=write,
            )
        except (IssueNotFoundError, IssueStateError) as e:
            print(f"错误：{e}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(issue.to_dict(), ensure_ascii=False, indent=2))
        else:
            _print_reopen_human(issue, dry_run=args.dry_run)
        return 0

    if args.list_open:
        _print_list_open(args.issues_path)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
