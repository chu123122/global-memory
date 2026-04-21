#!/usr/bin/env python3
"""
smoke_test.py — 基础设施冒烟测试

自动运行 ~/.claude/scripts/ 下所有脚本，验证无崩溃/编码错误/路径失效。
脚本清单硬编码为 manifest，不做自动发现，避免误跑新增的危险脚本。

用法：
  python smoke_test.py           # 运行测试，终端输出报告
  python smoke_test.py --log     # 同上 + 写入 ~/.claude/logs/smoke_test.log
  python smoke_test.py --json    # JSON 输出（供 Skill/其他脚本消费）

退出码：0 = 全 PASS，1 = 有 WARN，2 = 有 FAIL
"""

import io
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Windows UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 复用 _lib
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _lib import write_log, now_str
except ImportError:
    def write_log(name, msg): pass
    def now_str():
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M")

SCRIPTS_DIR = Path(__file__).parent
CLAUDE_DIR = Path.home() / ".claude"
MEMORY_DIR = CLAUDE_DIR / "global-memory"
TIMEOUT = 30  # 每个脚本最长运行秒数

# ────────────────────────────────────────────
# Manifest: (category, script_path, extra_args)
# ────────────────────────────────────────────
# category:
#   run    — 直接运行，exit 0 = PASS
#   import — 仅 import 检查
#   usage  — 无参运行，允许非零退出码，但不能崩溃
#   hook   — 空 stdin 运行，期望 exit 0
#   external — 非 scripts/ 目录的脚本
#   skip   — 有副作用，跳过

MANIFEST = [
    # ── run: 直接运行 ──
    ("run",      "verify_all.py",              []),
    ("run",      "sync_index.py",              []),
    ("run",      "update_stats.py",            []),
    ("run",      "update_readme.py",           []),
    ("run",      "verify_memory.py",           []),
    ("run",      "verify_conventions.py",      ["--memory"]),
    ("run",      "verify_prompt_system.py",    ["--report"]),
    ("run",      "extract_to_memory.py",       []),
    ("run",      "session_report.py",          []),
    ("run",      "fix_hardcoded_paths.py",     []),
    ("run",      "post_task_hook.py",          []),
    # ── import: 仅检查能否导入 ──
    ("import",   "_lib.py",                    []),
    ("import",   "hooks/_hook_lib.py",         []),
    # ── usage: 无参运行，打印用法即可 ──
    ("usage",    "append_changelog.py",        []),
    ("usage",    "baseline_compare.py",        []),
    ("usage",    "verify_workflow.py",         []),
    ("usage",    "init_project.py",            []),
    ("usage",    "close_project.py",           []),
    ("usage",    "generate_project_context.py",[]),
    # ── hook: 空输入运行 ──
    ("hook",     "hooks/dangerous_command_blocker.py", []),
    ("hook",     "hooks/memory_file_protector.py",     []),
    ("hook",     "hooks/audit_logger.py",              []),
    ("hook",     "hooks/subagent_logger.py",           []),
    ("hook",     "hooks/spec_gate.py",                 []),
    # ── external: 其他目录 ──
    ("external", str(MEMORY_DIR / "check_health.py"),  []),
    # ── skip: 有副作用 ──
    ("skip",     "auto_sync_daemon.py",        []),
    ("skip",     "changelog_archive.py",       []),
    ("skip",     "task_complete.py",           []),
]

CRASH_PATTERNS = re.compile(
    r"Traceback|UnicodeEncodeError|UnicodeDecodeError|ModuleNotFoundError|ImportError|SyntaxError|NameError",
    re.IGNORECASE,
)


@dataclass
class Result:
    script: str
    category: str
    status: str = ""       # PASS / WARN / FAIL / SKIP
    exit_code: int = -1
    duration: float = 0.0
    detail: str = ""


def resolve_path(script: str) -> Path:
    """解析脚本路径"""
    p = Path(script)
    if p.is_absolute():
        return p
    return SCRIPTS_DIR / script


def run_script(category: str, script: str, args: list[str]) -> Result:
    """运行单个脚本并返回结果"""
    r = Result(script=script, category=category)

    if category == "skip":
        r.status = "SKIP"
        r.detail = "有副作用，跳过"
        return r

    path = resolve_path(script)
    if not path.is_file():
        r.status = "FAIL"
        r.detail = f"文件不存在: {path}"
        return r

    if category == "import":
        # 用 python -c "import ..." 检查
        module = path.stem
        cmd = [sys.executable, "-c", f"import importlib.util; spec = importlib.util.spec_from_file_location('{module}', r'{path}'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)"]
        cwd = str(path.parent)
    else:
        cmd = [sys.executable, str(path)] + args
        cwd = str(path.parent)

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=cwd, timeout=TIMEOUT,
        )
        r.duration = time.time() - t0
        r.exit_code = proc.returncode
        combined = (proc.stdout or "") + (proc.stderr or "")

        # 判定
        has_crash = bool(CRASH_PATTERNS.search(combined))

        if category in ("run", "hook", "external", "import"):
            if proc.returncode == 0:
                # exit 0 优先判定为 PASS（即使 stderr 有子线程 traceback）
                if has_crash:
                    r.status = "WARN"
                    r.detail = "exit 0 但 stderr 有异常输出"
                else:
                    r.status = "PASS"
            elif has_crash:
                r.status = "FAIL"
                for line in combined.splitlines():
                    if "Error" in line or "Traceback" in line:
                        r.detail = line.strip()[:120]
                        break
            else:
                r.status = "WARN"
                r.detail = f"exit {proc.returncode}"
        elif category == "usage":
            if has_crash:
                r.status = "FAIL"
                for line in combined.splitlines():
                    if "Error" in line or "Traceback" in line:
                        r.detail = line.strip()[:120]
                        break
            else:
                r.status = "PASS"
                r.detail = "printed usage"

    except subprocess.TimeoutExpired:
        r.duration = time.time() - t0
        r.status = "FAIL"
        r.detail = f"超时 ({TIMEOUT}s)"
    except Exception as e:
        r.duration = time.time() - t0
        r.status = "FAIL"
        r.detail = str(e)[:120]

    return r


def main():
    do_log = "--log" in sys.argv
    do_json = "--json" in sys.argv

    t_start = time.time()
    results: list[Result] = []

    for category, script, args in MANIFEST:
        results.append(run_script(category, script, args))

    total_time = time.time() - t_start
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "SKIP": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    # ── JSON 输出 ──
    if do_json:
        output = {
            "timestamp": now_str(),
            "duration": round(total_time, 1),
            "summary": counts,
            "results": [asdict(r) for r in results],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # ── 终端报告 ──
        print("=" * 55)
        print("  smoke_test.py — 冒烟测试")
        print(f"  {now_str()}")
        print("=" * 55)

        for r in results:
            name = Path(r.script).name
            tag = f"[{r.category}]"
            dots = "." * max(1, 40 - len(tag) - len(name))

            if r.status == "PASS":
                icon = "✅"
                suffix = f"({r.duration:.1f}s)" if r.duration > 0 else ""
            elif r.status == "WARN":
                icon = "⚠️ "
                suffix = f"({r.detail})" if r.detail else ""
            elif r.status == "FAIL":
                icon = "❌"
                suffix = r.detail or ""
            else:
                icon = "⏭️ "
                suffix = ""

            detail_str = f" {suffix}" if suffix else ""
            print(f"  {tag:10s} {name} {dots} {icon} {r.status}{detail_str}")

        print()
        print("=" * 55)
        print(f"  📊 汇总: {counts['PASS']} PASS / {counts['WARN']} WARN / {counts['FAIL']} FAIL / {counts['SKIP']} SKIP")
        print(f"  耗时: {total_time:.1f}s")
        print("=" * 55)

    # ── 日志 ──
    if do_log:
        summary = f"PASS={counts['PASS']} WARN={counts['WARN']} FAIL={counts['FAIL']} SKIP={counts['SKIP']} ({total_time:.1f}s)"
        write_log("smoke_test", summary)
        failed = [r for r in results if r.status == "FAIL"]
        if failed:
            for r in failed:
                write_log("smoke_test", f"  FAIL: {r.script} — {r.detail}")

    # ── 退出码 ──
    if counts["FAIL"] > 0:
        return 2
    if counts["WARN"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
