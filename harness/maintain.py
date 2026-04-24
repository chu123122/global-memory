#!/usr/bin/env python3
"""
maintain.py - single control-plane entrypoint for global-memory harness ops.

Design rules:
- doctor is read-only for tracked files.
- fix may update tracked files locally but never commits or pushes.
- sync is the only command allowed to commit/push.
- daemon controls the background auto-sync process.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
MANIFEST_FILE = HARNESS_DIR / "maintenance_manifest.json"
CLAUDE_DIR = Path.home() / ".claude"
LOG_FILE = CLAUDE_DIR / "logs" / "maintain.jsonl"


@dataclass
class CommandResult:
    id: str
    command: list[str]
    cwd: str
    returncode: int
    duration: float
    level: str
    summary: str
    stdout: str = ""
    stderr: str = ""


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_jsonl(record: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_manifest() -> dict:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def rel_script_path(path_text: str) -> Path:
    p = Path(path_text)
    if p.is_absolute():
        return p
    if path_text.startswith("../"):
        return (HARNESS_DIR / p).resolve()
    return HARNESS_DIR / p


def run_cmd(
    check_id: str,
    cmd: list[str],
    cwd: Path = REPO_DIR,
    timeout: int = 90,
    parse_json: bool = False,
) -> tuple[CommandResult, object | None]:
    t0 = time.time()
    parsed = None
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        duration = time.time() - t0
        out = proc.stdout or ""
        err = proc.stderr or ""
        level = "PASS" if proc.returncode == 0 else "ERROR"
        summary = summarize_output(out, err, proc.returncode)
        if parse_json and out.strip():
            parsed = json.loads(extract_json(out))
            level = level_from_json(check_id, parsed, proc.returncode)
            summary = summary_from_json(check_id, parsed, summary)
        result = CommandResult(check_id, cmd, str(cwd), proc.returncode, duration, level, summary, out, err)
        return result, parsed
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - t0
        result = CommandResult(
            check_id, cmd, str(cwd), 124, duration, "ERROR",
            f"timeout after {timeout}s",
            exc.stdout or "", exc.stderr or "",
        )
        return result, None
    except Exception as exc:
        duration = time.time() - t0
        result = CommandResult(check_id, cmd, str(cwd), 1, duration, "ERROR", str(exc))
        return result, None


def extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last >= first:
        return stripped[first:last + 1]
    return stripped


def summarize_output(stdout: str, stderr: str, returncode: int) -> str:
    combined = (stdout or stderr or "").strip()
    if not combined:
        return f"exit {returncode}"
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    return lines[-1][:220] if lines else f"exit {returncode}"


def level_from_json(check_id: str, data: object, returncode: int) -> str:
    if check_id == "check_health" and isinstance(data, dict):
        if data.get("errors"):
            return "ERROR"
        if data.get("warnings"):
            return "WARNING"
        return "PASS"
    if check_id == "verify_prompt_system" and isinstance(data, dict):
        summary = data.get("summary", {})
        if summary.get("error", 0):
            return "ERROR"
        if summary.get("warning", 0):
            return "WARNING"
        return "PASS"
    if check_id == "smoke_test" and isinstance(data, dict):
        summary = data.get("summary", {})
        if summary.get("FAIL", 0):
            return "ERROR"
        if summary.get("WARN", 0):
            return "WARNING"
        return "PASS"
    return "PASS" if returncode == 0 else "ERROR"


def summary_from_json(check_id: str, data: object, fallback: str) -> str:
    if check_id == "check_health" and isinstance(data, dict):
        return f"{len(data.get('errors', []))} errors, {len(data.get('warnings', []))} warnings, {len(data.get('infos', []))} infos"
    if check_id == "verify_prompt_system" and isinstance(data, dict):
        summary = data.get("summary", {})
        return f"{summary.get('pass', 0)} pass, {summary.get('warning', 0)} warnings, {summary.get('error', 0)} errors"
    if check_id == "smoke_test" and isinstance(data, dict):
        summary = data.get("summary", {})
        return f"{summary.get('PASS', 0)} pass, {summary.get('WARN', 0)} warn, {summary.get('FAIL', 0)} fail, {summary.get('SKIP', 0)} skip"
    return fallback


def git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(REPO_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def git_status_short() -> str:
    return git(["status", "--short"]).stdout


def git_branch_status() -> dict:
    status = git(["status", "--branch", "--porcelain"]).stdout.strip()
    ahead = re.search(r"ahead (\d+)", status)
    behind = re.search(r"behind (\d+)", status)
    return {
        "raw": status,
        "ahead": int(ahead.group(1)) if ahead else 0,
        "behind": int(behind.group(1)) if behind else 0,
        "dirty": bool(git_status_short().strip()),
    }


def parse_status_entries(status_text: str | None = None) -> list[dict]:
    text = git_status_short() if status_text is None else status_text
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        code = line[:2].strip() or "?"
        raw_path = line[3:].strip() if len(line) > 3 else line.strip()
        path = raw_path.split(" -> ")[-1].replace("\\", "/")
        entries.append({"code": code, "path": path, "raw": line})
    return entries


def command_from_manifest(entry: dict) -> tuple[list[str], bool]:
    script = rel_script_path(entry["path"])
    args = entry.get("args", [])
    cmd = [sys.executable, str(script), *args]
    parse_json = "--json" in args
    return cmd, parse_json


def run_doctor(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    before = git_status_short()
    results: list[CommandResult] = []
    parsed: dict[str, object] = {}

    branch_status = git_branch_status()
    git_level = "WARNING" if branch_status["dirty"] or branch_status["behind"] else "PASS"
    results.append(CommandResult(
        "git_status",
        ["git", "status", "--short"],
        str(REPO_DIR),
        0,
        0.0,
        git_level,
        f"dirty={branch_status['dirty']} ahead={branch_status['ahead']} behind={branch_status['behind']}",
        git_status_short(),
        "",
    ))

    for entry in manifest["commands"]["doctor"]["scripts"]:
        if entry["id"] == "git_status":
            continue
        cmd, parse_json = command_from_manifest(entry)
        result, data = run_cmd(entry["id"], cmd, parse_json=parse_json)
        results.append(result)
        if data is not None:
            parsed[entry["id"]] = data

    after = git_status_short()
    if before != after:
        results.append(CommandResult(
            "doctor_readonly_guard",
            ["git", "status", "--short"],
            str(REPO_DIR),
            1,
            0.0,
            "ERROR",
            "doctor changed tracked working tree state",
            f"before:\n{before}\nafter:\n{after}",
            "",
        ))

    counts = count_levels(results)
    exit_code = 1 if counts["ERROR"] or (args.strict and counts["WARNING"]) else 0
    report = {
        "timestamp": now_iso(),
        "repo": str(REPO_DIR),
        "mode": "doctor",
        "strict": args.strict,
        "summary": counts,
        "exit_code": exit_code,
        "results": [asdict(r) for r in results],
        "parsed": parsed if args.include_parsed else {},
    }
    write_jsonl({"type": "doctor", **report})
    emit_report(report, args.json)
    return exit_code


def count_levels(results: list[CommandResult]) -> dict[str, int]:
    counts = {"PASS": 0, "WARNING": 0, "ERROR": 0}
    for result in results:
        counts[result.level] = counts.get(result.level, 0) + 1
    return counts


def emit_report(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"maintain.py {report['mode']} - {report['timestamp']}")
    print(f"repo: {report['repo']}")
    print(f"summary: {report['summary']}")
    for result in report.get("results", []):
        print(f"[{result['level']}] {result['id']}: {result['summary']}")


def run_fix(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    before = git_status_short()
    results = []
    for entry in manifest["commands"]["fix"]["scripts"]:
        cmd, parse_json = command_from_manifest(entry)
        result, _ = run_cmd(entry["id"], cmd, parse_json=parse_json)
        results.append(result)
    after = git_status_short()
    counts = count_levels(results)
    report = {
        "timestamp": now_iso(),
        "repo": str(REPO_DIR),
        "mode": "fix",
        "summary": counts,
        "changed": before != after,
        "before_status": before,
        "after_status": after,
        "results": [asdict(r) for r in results],
    }
    write_jsonl({"type": "fix", **report})
    emit_report(report, args.json)
    return 1 if counts["ERROR"] else 0


def group_files(files: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "memory": [],
        "harness": [],
        "agents": [],
        "skills": [],
        "templates": [],
        "docs": [],
        "other": [],
    }
    for file in files:
        if file == "MEMORY.md" or file.startswith(("feedback/", "knowledge/", "fixes/", "decisions/", "interview/", "projects/")):
            groups["memory"].append(file)
        elif file.startswith("harness/") or file in {"bootstrap.py", "check_health.py"}:
            groups["harness"].append(file)
        elif file.startswith("agents/"):
            groups["agents"].append(file)
        elif file.startswith("skills/"):
            groups["skills"].append(file)
        elif file.startswith("templates/"):
            groups["templates"].append(file)
        elif file.endswith(".md") or file in {"README.md", "MAINTENANCE.md", "CHANGELOG.md", "FIXLIST.md"}:
            groups["docs"].append(file)
        else:
            groups["other"].append(file)
    return {k: v for k, v in groups.items() if v}


def build_checkpoint_payload(source: str, files: list[str]) -> dict:
    groups = group_files(files)
    msg = f"checkpoint: {now_stamp()} [{source}]"
    body_lines = [
        f"source: {source}",
        f"files: {len(files)}",
        "",
        "groups:",
    ]
    for group, paths in groups.items():
        body_lines.append(f"- {group}: {len(paths)}")
        for path in paths[:12]:
            body_lines.append(f"  - {path}")
        if len(paths) > 12:
            body_lines.append(f"  - ... {len(paths) - 12} more")
    return {
        "commit": msg,
        "body": "\n".join(body_lines),
        "files": files,
        "groups": groups,
        "file_count": len(files),
    }


def staged_files() -> list[str]:
    out = git(["diff", "--cached", "--name-only"]).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def run_safe_fix_for_sync() -> list[CommandResult]:
    results = []
    for script_name in ("sync_index.py", "update_stats.py"):
        result, _ = run_cmd(script_name.replace(".py", ""), [sys.executable, str(HARNESS_DIR / script_name)], cwd=HARNESS_DIR)
        results.append(result)
    return results


def get_recent_commit_entries(limit: int = 30) -> list[dict]:
    fmt = "%h%x09%ad%x09%s"
    proc = git(["log", f"-{limit}", "--date=short", f"--pretty=format:{fmt}"])
    entries = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        sha, date, subject = parts
        kind = "checkpoint" if subject.startswith(("checkpoint:", "auto-fix:", "auto-sync:")) else "semantic"
        entries.append({"sha": sha, "date": date, "subject": subject, "kind": kind})
    return entries


def summarize_commits(entries: list[dict]) -> dict:
    return {
        "checkpoint": sum(1 for e in entries if e["kind"] == "checkpoint"),
        "semantic": sum(1 for e in entries if e["kind"] == "semantic"),
        "total": len(entries),
    }


def read_log_tail(limit: int = 8) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    records = []
    for line in lines[-limit:]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append({
            "type": data.get("type"),
            "timestamp": data.get("timestamp"),
            "mode": data.get("mode"),
            "summary": data.get("summary"),
            "source": data.get("source"),
        })
    return records


def build_status_report() -> dict:
    status_text = git_status_short()
    changes = parse_status_entries(status_text)
    files = [entry["path"] for entry in changes]
    commits = get_recent_commit_entries(12)
    processes = find_daemon_processes()
    branch = git_branch_status()
    return {
        "timestamp": now_iso(),
        "repo": str(REPO_DIR),
        "mode": "status",
        "git": {
            **branch,
            "change_count": len(files),
            "status": status_text,
            "changes": changes,
            "groups": group_files(files),
        },
        "daemon": {
            "running": bool(processes),
            "process_count": len(processes),
            "processes": processes,
        },
        "recent_commits": {
            "summary": summarize_commits(commits),
            "entries": commits,
        },
        "logs": {
            "maintain_tail": read_log_tail(),
        },
        "capabilities": {
            "doctor": "read-only aggregate health check",
            "fix": "local safe fixes only; no commit or push",
            "sync": "checkpoint commit and push",
            "ai": "diagnose/plan only in V1; execute is disabled",
        },
    }


def run_status(args: argparse.Namespace) -> int:
    report = build_status_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        git_info = report["git"]
        daemon_info = report["daemon"]
        recent = report["recent_commits"]["summary"]
        print(f"maintain.py status - {report['timestamp']}")
        print(f"repo: {report['repo']}")
        print(f"git: dirty={git_info['dirty']} ahead={git_info['ahead']} behind={git_info['behind']} changes={git_info['change_count']}")
        print(f"daemon: running={daemon_info['running']} processes={daemon_info['process_count']}")
        print(f"recent commits: semantic={recent['semantic']} checkpoint={recent['checkpoint']}")
    return 0


def build_sync_preview(source: str, no_fix: bool) -> dict:
    changes = parse_status_entries()
    files = [entry["path"] for entry in changes]
    payload = build_checkpoint_payload(source, files)
    branch = git_branch_status()
    return {
        "timestamp": now_iso(),
        "repo": str(REPO_DIR),
        "mode": "sync-preview",
        "source": source,
        "preview_only": True,
        "synced": False,
        "summary": "no changes" if not files else f"{len(files)} changed file(s)",
        "git": branch,
        "changes": changes,
        "would_run_safe_fix_on_real_sync": not no_fix,
        "would_pull_rebase_on_real_sync": bool(files),
        **payload,
    }


def run_sync(args: argparse.Namespace) -> int:
    if args.preview:
        report = build_sync_preview(args.source, args.no_fix)
        emit_sync_report(report, args.json)
        return 0

    fix_results = [] if args.no_fix else run_safe_fix_for_sync()

    initial = git_status_short()
    if not initial.strip():
        report = {
            "timestamp": now_iso(),
            "repo": str(REPO_DIR),
            "mode": "sync",
            "source": args.source,
            "synced": False,
            "summary": "no changes",
            "fix_results": [asdict(r) for r in fix_results],
        }
        write_jsonl({"type": "sync", **report})
        emit_sync_report(report, args.json)
        return 0

    pull = git(["pull", "--rebase"], timeout=90)
    if pull.returncode != 0:
        report = {
            "timestamp": now_iso(),
            "repo": str(REPO_DIR),
            "mode": "sync",
            "source": args.source,
            "synced": False,
            "summary": "pull --rebase failed; aborting push",
            "stdout": pull.stdout,
            "stderr": pull.stderr,
            "fix_results": [asdict(r) for r in fix_results],
        }
        write_jsonl({"type": "sync", **report})
        emit_sync_report(report, args.json)
        return 1

    git(["add", "-A"])
    files = staged_files()
    if not files:
        report = {
            "timestamp": now_iso(),
            "repo": str(REPO_DIR),
            "mode": "sync",
            "source": args.source,
            "synced": False,
            "summary": "no staged changes after safe fixes",
            "fix_results": [asdict(r) for r in fix_results],
        }
        write_jsonl({"type": "sync", **report})
        emit_sync_report(report, args.json)
        return 0

    payload = build_checkpoint_payload(args.source, files)
    groups = payload["groups"]
    msg = payload["commit"]
    body = payload["body"]

    commit = git(["commit", "-m", msg, "-m", body], timeout=90)
    if commit.returncode != 0:
        report = {
            "timestamp": now_iso(),
            "repo": str(REPO_DIR),
            "mode": "sync",
            "source": args.source,
            "synced": False,
            "summary": "commit failed",
            "stdout": commit.stdout,
            "stderr": commit.stderr,
            "files": files,
            "groups": groups,
        }
        write_jsonl({"type": "sync", **report})
        emit_sync_report(report, args.json)
        return 1

    push = git(["push"], timeout=120)
    ok = push.returncode == 0
    report = {
        "timestamp": now_iso(),
        "repo": str(REPO_DIR),
        "mode": "sync",
        "source": args.source,
        "synced": ok,
        "summary": "pushed" if ok else "push failed",
        "commit": msg,
        "files": files,
        "groups": groups,
        "stdout": push.stdout,
        "stderr": push.stderr,
        "fix_results": [asdict(r) for r in fix_results],
    }
    write_jsonl({"type": "sync", **report})
    emit_sync_report(report, args.json)
    return 0 if ok else 1


def emit_sync_report(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"maintain.py sync - {report['timestamp']}")
    print(f"source: {report.get('source')}")
    print(f"summary: {report.get('summary')}")
    if report.get("commit"):
        print(report["commit"])
    for group, paths in report.get("groups", {}).items():
        print(f"{group}: {len(paths)}")


def find_daemon_processes() -> list[dict]:
    if sys.platform == "win32":
        ps = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"name='python.exe' or name='pythonw.exe'\" | "
                "Where-Object { $_.CommandLine -match 'auto_sync_daemon.py' } | "
                "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        raw = ps.stdout.strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]
        return data
    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    rows = []
    for line in ps.stdout.splitlines():
        if "auto_sync_daemon.py" in line and "grep" not in line:
            rows.append({"CommandLine": line})
    return rows


def run_daemon(args: argparse.Namespace) -> int:
    if args.action == "status":
        procs = find_daemon_processes()
        report = {"timestamp": now_iso(), "running": bool(procs), "processes": procs}
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else daemon_text(report))
        return 0
    if args.action == "start":
        procs = find_daemon_processes()
        if procs and not args.force:
            report = {"timestamp": now_iso(), "started": False, "summary": "already running", "processes": procs}
            print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else daemon_text(report))
            return 0
        exe = Path(sys.executable)
        if sys.platform == "win32":
            pythonw = exe.with_name("pythonw.exe")
            runner = str(pythonw if pythonw.exists() else exe)
            subprocess.Popen([runner, str(HARNESS_DIR / "auto_sync_daemon.py")], cwd=str(REPO_DIR))
        else:
            subprocess.Popen([sys.executable, str(HARNESS_DIR / "auto_sync_daemon.py")], cwd=str(REPO_DIR))
        report = {"timestamp": now_iso(), "started": True, "summary": "daemon start requested"}
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else daemon_text(report))
        return 0
    if args.action == "stop":
        procs = find_daemon_processes()
        if sys.platform == "win32":
            for proc in procs:
                pid = str(proc.get("ProcessId"))
                subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"], capture_output=True)
        else:
            for proc in procs:
                m = re.search(r"^\S+\s+(\d+)\s+", proc.get("CommandLine", ""))
                if m:
                    subprocess.run(["kill", m.group(1)], capture_output=True)
        report = {"timestamp": now_iso(), "stopped": len(procs), "summary": f"stopped {len(procs)} process(es)"}
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else daemon_text(report))
        return 0
    return 1


def daemon_text(report: dict) -> str:
    lines = [f"daemon - {report.get('timestamp')}", report.get("summary", "")]
    if "running" in report:
        lines.append(f"running: {report['running']}")
    for proc in report.get("processes", []) or []:
        lines.append(str(proc))
    return "\n".join(line for line in lines if line)


def build_maintenance_report() -> dict:
    status = build_status_report()
    git_info = status["git"]
    daemon_info = status["daemon"]
    issues = []
    if git_info["dirty"]:
        issues.append(f"当前有 {git_info['change_count']} 个工作区变更，需要预览后同步或继续编辑。")
    if git_info["behind"]:
        issues.append(f"当前分支落后远端 {git_info['behind']} 个提交，真正同步前会先 pull --rebase。")
    if not daemon_info["running"]:
        issues.append("自动同步守护进程未运行；如果依赖空闲自动 checkpoint，需要从 GUI 或 maintain.py 启动。")
    if not issues:
        issues.append("未发现 V1 主控台层面的阻塞问题。")

    return {
        "timestamp": now_iso(),
        "repo": str(REPO_DIR),
        "mode": "report",
        "status": status,
        "capability_boundary": [
            "maintain.py 是唯一主控 CLI：doctor/status/preview 为只读，fix 只做本地安全修复，sync 才允许 commit/push。",
            "GUI 是人类入口：展示状态、同步预览、daemon 状态、日志、维护报告和 AI 诊断/计划。",
            "Stop hook 与 auto-sync daemon 只负责触发，实际 Git 同步统一委托 maintain.py sync。",
            "AI Runner V1 只允许 diagnose/plan；execute 模式明确禁用，不自动改文件。",
        ],
        "issues": issues,
        "next_steps": [
            "先运行 status 或 doctor 确认健康状态。",
            "有工作区变更时先运行 sync --preview 查看 checkpoint 候选摘要。",
            "确认分组无误后再从 GUI 或 CLI 执行 sync。",
        ],
    }


def format_markdown_report(report: dict) -> str:
    status = report["status"]
    git_info = status["git"]
    daemon_info = status["daemon"]
    recent = status["recent_commits"]
    lines = [
        "# global-memory Harness 维护报告",
        "",
        f"- 生成时间：{report['timestamp']}",
        f"- 仓库：{report['repo']}",
        "",
        "## 当前状态",
        "",
        f"- Git：dirty={git_info['dirty']}，ahead={git_info['ahead']}，behind={git_info['behind']}，变更数={git_info['change_count']}",
        f"- Daemon：running={daemon_info['running']}，processes={daemon_info['process_count']}",
        f"- 最近提交：semantic={recent['summary']['semantic']}，checkpoint={recent['summary']['checkpoint']}",
        "",
        "## 变更分组",
        "",
    ]
    groups = git_info.get("groups", {})
    if groups:
        for group, paths in groups.items():
            lines.append(f"- {group}: {len(paths)}")
            for path in paths[:10]:
                lines.append(f"  - {path}")
            if len(paths) > 10:
                lines.append(f"  - ... {len(paths) - 10} more")
    else:
        lines.append("- 当前无工作区变更")
    lines.extend(["", "## 能力边界", ""])
    lines.extend(f"- {item}" for item in report["capability_boundary"])
    lines.extend(["", "## 暴露问题", ""])
    lines.extend(f"- {item}" for item in report["issues"])
    lines.extend(["", "## 建议下一步", ""])
    lines.extend(f"- {item}" for item in report["next_steps"])
    return "\n".join(lines) + "\n"


def run_report(args: argparse.Namespace) -> int:
    report = build_maintenance_report()
    as_json = args.json and not args.markdown
    content = json.dumps(report, ensure_ascii=False, indent=2) if as_json else format_markdown_report(report)
    if args.save:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        suffix = "json" if as_json else "md"
        save_path = LOG_FILE.parent / f"harness_report_{now_stamp()}.{suffix}"
        save_path.write_text(content, encoding="utf-8")
        if as_json:
            report["saved_to"] = str(save_path)
            content = json.dumps(report, ensure_ascii=False, indent=2)
        else:
            content += f"\n保存位置：{save_path}\n"
    print(content)
    return 0


def run_log(args: argparse.Namespace) -> int:
    entries = get_recent_commit_entries(args.limit)
    report = {
        "timestamp": now_iso(),
        "entries": entries,
        "summary": summarize_commits(entries),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"recent commits - checkpoints={report['summary']['checkpoint']} semantic={report['summary']['semantic']}")
        for e in entries:
            print(f"{e['sha']} {e['date']} [{e['kind']}] {e['subject']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="global-memory harness control plane")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doctor = sub.add_parser("doctor", help="read-only health overview")
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.add_argument("--strict", action="store_true")
    p_doctor.add_argument("--include-parsed", action="store_true")
    p_doctor.set_defaults(func=run_doctor)

    p_fix = sub.add_parser("fix", help="safe local fixes, no commit/push")
    p_fix.add_argument("--json", action="store_true")
    p_fix.set_defaults(func=run_fix)

    p_sync = sub.add_parser("sync", help="checkpoint commit and push")
    p_sync.add_argument("--json", action="store_true")
    p_sync.add_argument("--source", default="manual", choices=["manual", "gui", "stop-hook", "daemon"])
    p_sync.add_argument("--no-fix", action="store_true")
    p_sync.add_argument("--preview", action="store_true", help="read-only checkpoint preview; no fix/stage/commit/push")
    p_sync.set_defaults(func=run_sync)

    p_status = sub.add_parser("status", help="quick read-only status snapshot")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=run_status)

    p_daemon = sub.add_parser("daemon", help="auto-sync daemon control")
    p_daemon.add_argument("action", choices=["status", "start", "stop"])
    p_daemon.add_argument("--json", action="store_true")
    p_daemon.add_argument("--force", action="store_true")
    p_daemon.set_defaults(func=run_daemon)

    p_log = sub.add_parser("log", help="show checkpoint vs semantic commits")
    p_log.add_argument("--json", action="store_true")
    p_log.add_argument("--limit", type=int, default=30)
    p_log.set_defaults(func=run_log)

    p_report = sub.add_parser("report", help="generate harness maintenance report")
    p_report.add_argument("--json", action="store_true")
    p_report.add_argument("--markdown", action="store_true")
    p_report.add_argument("--save", action="store_true", help="save report under ~/.claude/logs")
    p_report.set_defaults(func=run_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
