#!/usr/bin/env python3
"""Verify CLI output contracts for harness scripts.

Default mode runs read-only JSON entrypoints and checks that stdout is exact JSON,
stderr is clean on success, and machine JSON does not embed large human console
transcripts. Mutating commands are not executed unless explicitly requested.
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
from pathlib import Path
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent


@dataclass(frozen=True)
class ContractCase:
    id: str
    cmd: list[str]
    cwd: Path = REPO_DIR
    expect_json: bool = True
    mutating: bool = False
    allow_returncodes: tuple[int, ...] = (0, 1)
    allow_raw_output_keys: bool = False


@dataclass
class Finding:
    level: str
    case_id: str
    code: str
    message: str
    path: str = ""


def py(script: str, *args: str) -> list[str]:
    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = HARNESS_DIR / script
    return [sys.executable, str(script_path), *args]


def default_cases() -> list[ContractCase]:
    return [
        ContractCase("maintain_status", py("maintain.py", "status", "--json")),
        ContractCase(
            "maintain_sync_preview",
            py("maintain.py", "sync", "--preview", "--source", "manual", "--json"),
        ),
        ContractCase("maintain_log", py("maintain.py", "log", "--json", "--limit", "8")),
        ContractCase("maintain_daemon_status", py("maintain.py", "daemon", "status", "--json")),
        ContractCase("maintain_doctor", py("maintain.py", "doctor", "--json")),
        ContractCase("harness_tasks", py("harness_status.py", "--tasks", "--json")),
        ContractCase("check_health", [sys.executable, str(REPO_DIR / "check_health.py"), "--json"]),
        ContractCase("verify_prompt_system", py("verify_prompt_system.py", "--json")),
        ContractCase("smoke_test", py("smoke_test.py", "--json")),
        ContractCase("audit_skill_all", py("audit_skill.py", "--all", "--json")),
        ContractCase("check_prepare", py("check_prepare.py", "--json")),
    ]


def mutating_cases() -> list[ContractCase]:
    return [
        ContractCase(
            "maintain_fix",
            py("maintain.py", "fix", "--json"),
            mutating=True,
        ),
    ]


def run_case(case: ContractCase, timeout: int) -> tuple[subprocess.CompletedProcess[str] | None, float, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    start = time.time()
    try:
        proc = subprocess.run(
            case.cmd,
            cwd=str(case.cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc, time.time() - start, ""
    except subprocess.TimeoutExpired as exc:
        return None, time.time() - start, f"timeout after {exc.timeout}s"
    except Exception as exc:  # noqa: BLE001 - checker must keep going
        return None, time.time() - start, f"{type(exc).__name__}: {exc}"


def validate_case(case: ContractCase, proc: subprocess.CompletedProcess[str] | None, error: str) -> tuple[Any, list[Finding]]:
    findings: list[Finding] = []
    if proc is None:
        findings.append(Finding("ERROR", case.id, "command_failed", error))
        return None, findings

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if proc.returncode not in case.allow_returncodes:
        findings.append(Finding(
            "ERROR",
            case.id,
            "unexpected_returncode",
            f"returncode={proc.returncode}, allowed={case.allow_returncodes}",
        ))
    if proc.returncode == 0 and stderr.strip():
        findings.append(Finding("WARNING", case.id, "stderr_on_success", stderr.strip()[:300]))

    data = None
    if case.expect_json:
        stripped = stdout.strip()
        if not stripped:
            findings.append(Finding("ERROR", case.id, "empty_stdout", "expected JSON on stdout"))
        else:
            if not stripped.startswith(("{", "[")):
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    "json_prefix_noise",
                    f"stdout starts with non-JSON text: {stripped[:120]!r}",
                ))
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError as exc:
                findings.append(Finding(
                    "ERROR",
                    case.id,
                    "invalid_json",
                    f"{exc.msg} at line {exc.lineno} column {exc.colno}",
                ))
            else:
                findings.extend(validate_json_payload(case, data))
    return data, findings


def validate_json_payload(case: ContractCase, data: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(data, (dict, list)):
        findings.append(Finding("ERROR", case.id, "json_root_type", f"root is {type(data).__name__}"))
        return findings

    for path, key, value in walk_json(data):
        if isinstance(value, str):
            if len(value) > 8000:
                findings.append(Finding("WARNING", case.id, "large_string_field", f"{len(value)} chars", path))
            if looks_like_console_transcript(value):
                findings.append(Finding(
                    "WARNING",
                    case.id,
                    "console_transcript_in_json",
                    "machine JSON contains human console transcript",
                    path,
                ))
            if key in {"stdout", "stderr"} and value.strip() and not case.allow_raw_output_keys:
                findings.append(Finding(
                    "WARNING",
                    case.id,
                    "raw_output_field",
                    f"non-empty {key} should be omitted from successful machine JSON unless requested",
                    path,
                ))
    return findings


def walk_json(value: Any, path: str = "$", key: str = ""):
    yield path, key, value
    if isinstance(value, dict):
        for child_key, child in value.items():
            child_path = f"{path}.{child_key}"
            yield from walk_json(child, child_path, str(child_key))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk_json(child, f"{path}[{idx}]", key)


def looks_like_console_transcript(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    markers = (
        "✅", "❌", "⚠", "====", "----", "[1/", "[2/", "扫描", "当前环境", "模式:",
    )
    if any(marker in text for marker in markers):
        return True
    return bool(re.search(r"(?m)^\s*(PASS|ERROR|WARNING|WARN|INFO)[:\]]", text))


def render_text(results: list[dict]) -> str:
    lines = ["verify_output_contracts.py — script output contract check", ""]
    total_errors = 0
    total_warnings = 0
    for item in results:
        errors = [f for f in item["findings"] if f["level"] == "ERROR"]
        warnings = [f for f in item["findings"] if f["level"] == "WARNING"]
        total_errors += len(errors)
        total_warnings += len(warnings)
        status = "PASS" if not errors and not warnings else ("ERROR" if errors else "WARNING")
        lines.append(f"[{status}] {item['case_id']} exit={item['returncode']} duration={item['duration']:.2f}s")
        for finding in item["findings"]:
            suffix = f" @ {finding['path']}" if finding.get("path") else ""
            lines.append(f"  - {finding['level']} {finding['code']}{suffix}: {finding['message']}")
    lines.extend(["", f"summary: ERROR={total_errors} WARNING={total_warnings} CASES={len(results)}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="verify harness script output contracts")
    parser.add_argument("--json", action="store_true", help="emit machine-readable report")
    parser.add_argument("--include-mutating", action="store_true", help="also run mutating contract cases")
    parser.add_argument("--case", action="append", dest="case_ids", help="run only selected case id; repeatable")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    cases = default_cases()
    if args.include_mutating:
        cases.extend(mutating_cases())
    if args.case_ids:
        selected = set(args.case_ids)
        cases = [case for case in cases if case.id in selected]

    results = []
    for case in cases:
        proc, duration, error = run_case(case, args.timeout)
        _data, findings = validate_case(case, proc, error)
        results.append({
            "case_id": case.id,
            "cmd": case.cmd,
            "cwd": str(case.cwd),
            "mutating": case.mutating,
            "returncode": proc.returncode if proc else None,
            "duration": round(duration, 3),
            "findings": [asdict(finding) for finding in findings],
        })

    summary = {
        "ERROR": sum(1 for item in results for finding in item["findings"] if finding["level"] == "ERROR"),
        "WARNING": sum(1 for item in results for finding in item["findings"] if finding["level"] == "WARNING"),
        "CASES": len(results),
    }
    report = {
        "schema_version": 1,
        "kind": "output_contract_check",
        "summary": summary,
        "results": results,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(results), end="")
    return 1 if summary["ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
