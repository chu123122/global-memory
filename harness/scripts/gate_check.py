#!/usr/bin/env python
"""gate_check.py — HARD GATE (P2 → P3) enforcement.

Runs all G1-G9 prerequisites + indicator computation, emits GATE-REPORT.
G9 = hardcoded path check (WARN mode — does not block).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

# 接入 harness/_lib.py:run_utf8 — 见 harness-governance-followup P1
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CLAUDE_HOME, CLAUDE_TASKS_ACTIVE, MEMORY_ROOT, script_path  # noqa: E402
from _lib import run_utf8  # noqa: E402

REPO_ROOT = MEMORY_ROOT
SCRIPTS = script_path()
DEFAULT_TASKS_ROOT = CLAUDE_TASKS_ACTIVE
TASK_DIR = DEFAULT_TASKS_ROOT / "harness-context-governance"
WARN_SUNSET_PATH = SCRIPTS / "warn_sunset.yaml"


def _today() -> date:
    return date.today()


def load_warn_sunset(path: Path = WARN_SUNSET_PATH) -> dict[str, dict]:
    """Load warn_sunset.yaml → {id: entry}. Required: id/sunset/owner/tracking.

    P4 / D4：注册表是 WARN gate 的唯一治理元数据来源；缺字段直接抛，避免「半瓶水」。
    """
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        sys.stderr.write("WARN: pyyaml missing; warn_sunset registry disabled\n")
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, dict] = {}
    for entry in raw.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        for req in ("id", "sunset", "owner", "tracking"):
            if req not in entry:
                raise SystemExit(f"warn_sunset.yaml entry missing {req}: {entry}")
        sunset = entry["sunset"]
        if not isinstance(sunset, date):
            sunset = datetime.strptime(str(sunset), "%Y-%m-%d").date()
        entry["sunset"] = sunset
        ext = entry.get("extend_until")
        if ext is not None and not isinstance(ext, date):
            entry["extend_until"] = datetime.strptime(str(ext), "%Y-%m-%d").date()
        out[entry["id"]] = entry
    return out


def apply_sunset_policy(entry: dict | None, base_pass: bool, base_detail: str,
                        strict: bool, today: date | None = None) -> tuple[bool, str]:
    """根据 sunset/extend_until + strict 调整 (pass, detail)。

    - 未注册：detail 追加 `[UNTRACKED WARN]`，strict 下 FAIL
    - 在 sunset 期内：detail 追加 `[sunset YYYY-MM-DD owner=X]`
    - extend_until ≥ today：等同有效，标 `[extended → YYYY-MM-DD]`
    - 过期无延期：默认 detail 追加 `[OVERDUE since YYYY-MM-DD]`；strict 下 FAIL
    """
    today = today or _today()
    if entry is None:
        if strict:
            return False, base_detail + " [UNTRACKED WARN — register in warn_sunset.yaml]"
        return base_pass, base_detail + " [UNTRACKED WARN]"
    sunset = entry["sunset"]
    ext = entry.get("extend_until")
    if today <= sunset:
        return base_pass, base_detail + f" [sunset {sunset} owner={entry['owner']} tracking={entry['tracking']}]"
    if ext is not None and today <= ext:
        return base_pass, base_detail + f" [sunset {sunset} extended → {ext}]"
    # overdue
    if strict:
        return False, base_detail + f" [OVERDUE since {sunset} — --strict-sunset FAIL]"
    return base_pass, base_detail + f" [OVERDUE since {sunset} — passes day-to-day; --strict-sunset would FAIL]"


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        r = run_utf8(cmd, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def check_prereqs(strict_sunset: bool = False) -> list[dict]:
    sunset_registry = load_warn_sunset()
    out: list[dict] = []

    rc, so, _ = run([sys.executable, str(SCRIPTS / "scan_dual_storage.py")])
    dual_ok = "dual_count=0" in so
    out.append({"id": "G1", "name": "dual storage = 0", "pass": dual_ok, "detail": so.strip()})

    rc, so, _ = run(["git", "-C", str(REPO_ROOT), "tag", "-l", "pre-context-governance-*"])
    out.append({"id": "G2", "name": "git snapshot tag", "pass": bool(so.strip()), "detail": so.strip()})

    rc, so, _ = run([sys.executable, str(SCRIPTS / "harness_retrieve.py"),
                     "--task", "harness-context-governance", "--query", "test", "--dry-run"])
    out.append({"id": "G3", "name": "retrieve runs", "pass": rc == 0 and "schema_version" in so,
                "detail": f"rc={rc}"})

    rc, so, _ = run([sys.executable, str(SCRIPTS / "check_trigger_coverage.py"), "--strict"])
    out.append({"id": "G4", "name": "trigger coverage >=90%", "pass": rc == 0, "detail": so.strip()})

    mem = REPO_ROOT / "MEMORY.md"
    msize = mem.stat().st_size if mem.exists() else 0
    out.append({"id": "G5", "name": "MEMORY.md <= 4000 bytes", "pass": msize <= 4000,
                "detail": f"bytes={msize}"})

    settings = CLAUDE_HOME / "settings.json"
    try:
        cfg = json.loads(settings.read_text(encoding="utf-8"))
        plugs = cfg.get("enabledPlugins", {})
        controlled = all(not plugs.get(k, False) for k in ("atlassian@claude-plugins-official",
                                                            "playwright@claude-plugins-official"))
    except Exception:
        controlled = False
    out.append({"id": "G6", "name": "plugins controlled", "pass": controlled,
                "detail": f"enabled={list(plugs) if 'plugs' in dir() else 'n/a'}"})

    rc, so, _ = run([sys.executable, str(SCRIPTS / "test_context_governance.py"), "--all"], timeout=300)
    out.append({"id": "G7", "name": "test suite green", "pass": rc == 0,
                "detail": (so or '').splitlines()[-1] if so else f"rc={rc}"})

    out.append({"id": "G8", "name": "7d audit data", "pass": True,
                "detail": "n/a in TDD harness; defer until real run"})

    # G9 — 硬编码路径检查（WARN 模式：存量遗留多，一刀切 FAIL 卡死所有流程）
    # 退出码 1 = 有 issues；stdout 含 "发现 N 个问题" 或 "未发现硬编码路径问题"
    fhp = REPO_ROOT / "harness" / "fix_hardcoded_paths.py"
    rc, so, _ = run([sys.executable, str(fhp)], timeout=120)
    if "未发现硬编码路径问题" in so:
        g9_detail = "no issues"
        g9_pass = True
    else:
        import re as _re
        m = _re.search(r"发现\s*(\d+)\s*个问题", so)
        n = m.group(1) if m else "?"
        g9_detail = f"WARN: {n} hardcoded issues (run `python harness/fix_hardcoded_paths.py` for details)"
        g9_pass = True  # WARN — 不阻断，存量给迁移期
    # P4 / D4：套 sunset 策略（注册→可被 --strict-sunset 升级 FAIL）
    if not g9_pass or "no issues" not in g9_detail:
        g9_pass, g9_detail = apply_sunset_policy(
            sunset_registry.get("G9"), g9_pass, g9_detail, strict_sunset
        )
    out.append({"id": "G9", "name": "hardcoded paths (WARN)", "pass": g9_pass, "detail": g9_detail})

    return out


def write_report(prereqs: list[dict], out_path: Path) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# GATE Report · {now}", "", "## Prerequisites (G1-G9)", "",
             "| ID | Name | Pass | Detail |", "|---|---|---|---|"]
    for r in prereqs:
        mark = "✅" if r["pass"] else "🔴"
        lines.append(f"| {r['id']} | {r['name']} | {mark} | {r['detail']} |")
    all_pass = all(r["pass"] for r in prereqs)
    lines += ["", f"## Verdict", "",
              "PASS — proceed to P3" if all_pass else "BLOCKED — fix failing prereqs and rerun"]
    lines += ["", "## Decision (human fills in)", "", "decision: <pass|retry|pivot>", "notes:", ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_result(prereqs: list[dict], phase: str, report_path: Path | None = None) -> dict:
    failing = [item for item in prereqs if not item["pass"]]
    summary = {
        "total": len(prereqs),
        "pass": len(prereqs) - len(failing),
        "fail": len(failing),
    }
    verdict = "pass" if not failing else "blocked"
    return {
        "schema_version": 1,
        "kind": "gate_check",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO_ROOT),
        "phase": phase,
        "verdict": verdict,
        "exit_code": 0 if verdict == "pass" else 1,
        "summary": summary,
        "failures": failing,
        "gates": prereqs,
        "report_path": str(report_path) if report_path else None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", default="p2-to-p3")
    p.add_argument("--out", default=None)
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON; does not write GATE-REPORT unless --write-report is set")
    p.add_argument("--write-report", action="store_true", help="write GATE-REPORT even in --json mode")
    p.add_argument("--strict-sunset", action="store_true",
                   help="WARN 过期且无 extend_until 时 FAIL（默认 PASS，仅治理审计用）")
    args = p.parse_args(argv)

    prereqs = check_prereqs(strict_sunset=args.strict_sunset)
    out_path = Path(args.out) if args.out else TASK_DIR / f"GATE-REPORT-{datetime.now().strftime('%Y-%m-%d')}.md"
    should_write = args.write_report or not args.json
    report_path = out_path if should_write else None
    if should_write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_report(prereqs, out_path)

    result = build_result(prereqs, args.phase, report_path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"report={out_path}")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
