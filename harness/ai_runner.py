#!/usr/bin/env python3
"""
ai_runner.py - AI adapter layer for the harness desktop control panel.

First implementation:
- Claude CLI non-interactive runs via `claude --print`.
- Codex CLI and API providers are explicit placeholders.
- V1 disables execute mode; only diagnose/plan are allowed.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
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
LOG_FILE = Path.home() / ".claude" / "logs" / "ai_runner.jsonl"


@dataclass
class AIRun:
    provider: str
    mode: str
    returncode: int
    duration: float
    command: list[str]
    prompt: str
    stdout: str
    stderr: str
    timestamp: str


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_jsonl(record: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def run_cmd(cmd: list[str], prompt: str, timeout: int) -> AIRun:
    t0 = time.time()
    try:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            cmd,
            input=prompt,
            cwd=str(REPO_DIR),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return AIRun("", "", proc.returncode, time.time() - t0, cmd, prompt, proc.stdout or "", proc.stderr or "", now_iso())
    except subprocess.TimeoutExpired as exc:
        return AIRun("", "", 124, time.time() - t0, cmd, prompt, exc.stdout or "", exc.stderr or "timeout", now_iso())


def git_diff_context() -> str:
    proc = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=str(REPO_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout.strip()


def doctor_context() -> str:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(HARNESS_DIR / "maintain.py"), "doctor", "--json"],
        cwd=str(REPO_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return proc.stdout.strip()


def doc_context() -> str:
    parts = []
    for name in ("README.md", "MAINTENANCE.md"):
        path = REPO_DIR / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"# {name}\n{text[:8000]}")
    return "\n\n".join(parts)


def build_prompt(args: argparse.Namespace) -> str:
    chunks = [
        "You are assisting with the global-memory harness control plane.",
        f"Task mode: {args.mode}.",
    ]
    if args.context_doctor:
        chunks.append("## Doctor Report\n" + doctor_context())
    if args.context_diff:
        chunks.append("## Git Diff Stat\n" + (git_diff_context() or "(clean)"))
    if args.context_docs:
        chunks.append("## Repository Docs\n" + doc_context())
    chunks.append("## User Request\n" + args.prompt)
    return "\n\n".join(chunks)


def run_claude(args: argparse.Namespace, prompt: str) -> AIRun:
    exe = shutil.which("claude")
    if not exe:
        return AIRun("claude", args.mode, 127, 0.0, ["claude"], prompt, "", "claude executable not found", now_iso())
    cmd = [
        exe,
        "--print",
        "--output-format",
        args.output_format,
        "--permission-mode",
        args.permission_mode,
        "--add-dir",
        str(REPO_DIR),
    ]
    if args.model:
        cmd.extend(["--model", args.model])
    if args.dry_run:
        return AIRun("claude", args.mode, 0, 0.0, cmd, prompt, json.dumps({
            "dry_run": True,
            "provider": "claude",
            "command": cmd,
            "prompt_preview": prompt[:1200],
        }, ensure_ascii=False, indent=2), "", now_iso())
    run = run_cmd(cmd, prompt, args.timeout)
    run.provider = "claude"
    run.mode = args.mode
    run.prompt = prompt
    return run


def run_placeholder(provider: str, args: argparse.Namespace, prompt: str) -> AIRun:
    msg = f"{provider} adapter is reserved but not enabled in this implementation."
    return AIRun(provider, args.mode, 2, 0.0, [provider], prompt, "", msg, now_iso())


def reject_execute(args: argparse.Namespace) -> AIRun:
    msg = "execute mode is disabled in AI Harness Desktop V1; use diagnose or plan."
    return AIRun(args.provider, args.mode, 2, 0.0, ["ai_runner", "--mode", "execute"], args.prompt, "", msg, now_iso())


def main() -> int:
    parser = argparse.ArgumentParser(description="AI adapter for harness control panel")
    parser.add_argument("prompt", help="prompt to send")
    parser.add_argument("--provider", default="claude", choices=["claude", "codex", "api"])
    parser.add_argument("--mode", default="diagnose", choices=["diagnose", "plan", "execute"])
    parser.add_argument("--permission-mode", default="plan", choices=["plan", "default", "acceptEdits", "dontAsk"])
    parser.add_argument("--output-format", default="json", choices=["json", "stream-json", "text"])
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--context-doctor", action="store_true")
    parser.add_argument("--context-diff", action="store_true")
    parser.add_argument("--context-docs", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.mode == "execute":
        run = reject_execute(args)
        record = asdict(run)
        write_jsonl({"type": "ai_run", **record})
        if args.json:
            print(json.dumps(record, ensure_ascii=False, indent=2))
        else:
            print(run.stderr, file=sys.stderr)
        return run.returncode

    prompt = build_prompt(args)
    if args.provider == "claude":
        run = run_claude(args, prompt)
    else:
        run = run_placeholder(args.provider, args, prompt)

    record = asdict(run)
    write_jsonl({"type": "ai_run", **record})
    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        if run.stdout:
            print(run.stdout)
        if run.stderr:
            print(run.stderr, file=sys.stderr)
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
