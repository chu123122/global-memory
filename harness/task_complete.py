#!/usr/bin/env python3
"""
task_complete.py — 任务收尾一键脚本

在项目任务完成后，一键执行所有收尾动作：
  1. 项目规范检查（verify_conventions.py）
  2. 记忆系统检查（verify_conventions.py --memory）
  3. 系统基础设施检查（verify_all.py）
  4. 记忆索引同步（sync_index.py）
  5. 统计更新（update_stats.py）
  6. 汇总报告 + 建议

用法：
  python task_complete.py <project_dir>           # 完整收尾
  python task_complete.py <project_dir> --fix     # 检查并自动修复可修复项
  python task_complete.py <project_dir> --strict-assurance  # assurance FAIL/BLOCKED/ERROR/STALE 阻断收尾声明
  python task_complete.py --memory-only           # 只做记忆系统收尾
  python task_complete.py --infra-only            # 只做基础设施检查

设计原则：
  - ERROR 阻止同步（打印修复建议）
  - WARNING 列出但不阻止
  - 全 PASS 时自动提示 git sync
"""

import io
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SCRIPTS_DIR))


def run_script(script_name, args=None, label=None):
    """运行一个脚本，返回 (return_code, stdout)"""
    script = SCRIPTS_DIR / script_name
    if not script.is_file():
        print(f"  ⚠️  脚本不存在: {script}")
        return 1, ""

    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)

    if label:
        print(f"\n{'─'*50}")
        print(f"  📋 {label}")
        print(f"{'─'*50}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode, result.stdout
    except Exception as e:
        print(f"  ❌ 执行失败: {e}")
        return 1, ""


def run_module(module_name, func_name, label=None):
    """直接导入并调用同目录脚本的函数"""
    if label:
        print(f"\n{'─'*50}")
        print(f"  🔧 {label}")
        print(f"{'─'*50}")
    try:
        mod = __import__(module_name)
        func = getattr(mod, func_name)
        func()
        return 0
    except Exception as e:
        print(f"  ⚠️  {module_name}.{func_name} 失败: {e}")
        return 1


def run_assurance_gate(project_dir):
    """Run task-handoff-ready and return its verdict.

    Default task_complete behavior still treats non-PASS as advisory. Callers can
    opt into strict handling when they need a hard completion claim gate.
    """
    print(f"\n{'─'*50}")
    print("  🧭 Assurance: task-handoff-ready")
    print(f"{'─'*50}")

    script = SCRIPTS_DIR / "scripts" / "assurance_gate.py"
    if not script.is_file():
        print(f"  ⚠️  assurance 脚本不存在: {script}")
        return "ERROR"

    cmd = [
        sys.executable,
        str(script),
        "--gate",
        "task-handoff-ready",
        "--task",
        str(project_dir),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except Exception as e:
        print(f"  ⚠️  assurance 执行失败: {e}")
        return "ERROR"

    try:
        data = json.loads(result.stdout)
    except Exception:
        print("  ⚠️  assurance 输出不是合法 JSON")
        if result.stdout.strip():
            print(result.stdout.strip()[:1000])
        if result.stderr.strip():
            print(result.stderr.strip()[:1000], file=sys.stderr)
        return "ERROR"

    verdict = data.get("verdict", "ERROR")
    summary = data.get("summary", "")
    print(f"  Verdict: {verdict}")
    print(f"  Summary: {summary}")
    for item in data.get("evidence", [])[:5]:
        print(f"  - {item}")
    if data.get("next_action"):
        print(f"  Next: {data['next_action']}")

    if verdict in {"PASS", "NOT_APPLICABLE"}:
        return verdict
    return verdict


def run_archive_readiness(project_dir):
    """Run archive_task --check as an advisory next-action detector."""
    print(f"\n{'─'*50}")
    print("  🗄️  Archive readiness")
    print(f"{'─'*50}")

    script = SCRIPTS_DIR / "scripts" / "archive_task.py"
    if not script.is_file():
        print(f"  ⚠️  archive 脚本不存在: {script}")
        return "ERROR"

    try:
        result = subprocess.run(
            [sys.executable, str(script), "--check", str(project_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except Exception as e:
        print(f"  ⚠️  archive readiness 执行失败: {e}")
        return "ERROR"

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode == 0:
        print("  Next: run archive_task.py --extract <task> before --commit.")
        return "READY"
    print("  Next: finish/sync Phase status and acceptance before archive.")
    return "NOT_READY"


def main():
    print("=" * 60)
    print("  task_complete.py — 任务收尾一键脚本")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    project_dir = None
    do_fix = "--fix" in sys.argv
    memory_only = "--memory-only" in sys.argv
    infra_only = "--infra-only" in sys.argv
    strict_assurance = "--strict-assurance" in sys.argv

    # 解析 project_dir
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            project_dir = arg
            break

    total_errors = 0
    total_warnings = 0
    steps_done = 0

    # ── Step 1: 项目规范检查 ──
    if project_dir and not memory_only and not infra_only:
        rc, out = run_script("verify/verify_conventions.py", [project_dir, "--all"],
                             "Step 1/5: 项目规范 + 记忆系统检查")
        if rc != 0:
            total_errors += 1
        total_warnings += out.count("WARNING")
        steps_done += 1
    elif not infra_only:
        rc, out = run_script("verify/verify_conventions.py", ["--memory"],
                             "Step 1/5: 记忆系统规范检查")
        total_warnings += out.count("WARNING")
        steps_done += 1

    # ── Step 2: 系统基础设施检查 ──
    if not memory_only:
        rc, out = run_script("verify/verify_all.py", [],
                             "Step 2/5: 系统基础设施检查")
        if rc != 0:
            total_errors += 1
        total_warnings += out.count("WARNING")
        steps_done += 1

    # ── Step 3: 索引同步 ──
    if do_fix:
        run_module("sync_index", "sync_index",
                   "Step 3/5: 自动修复 — 索引同步")
    else:
        print(f"\n{'─'*50}")
        print(f"  ℹ️  Step 3/5: 索引同步（加 --fix 自动执行）")
        print(f"{'─'*50}")
    steps_done += 1

    # ── Step 4: 统计更新 ──
    if do_fix:
        run_module("update_stats", "update_stats",
                   "Step 4/5: 自动修复 — 统计更新")
    else:
        print(f"\n{'─'*50}")
        print(f"  ℹ️  Step 4/5: 统计更新（加 --fix 自动执行）")
        print(f"{'─'*50}")
    steps_done += 1

    # ── Step 5: 进度文档检查（你要求的核心功能）──
    if project_dir:
        print(f"\n{'─'*50}")
        print(f"  📊 Step 5/5: 进度文档完整性检查")
        print(f"{'─'*50}")
        pdir = Path(project_dir).resolve()
        if (pdir / "core").is_dir() and (pdir / "design").is_dir():
            print("  v2 进度文档完整性检查")
            checks = {
                "design/进度.md": pdir / "design" / "进度.md",
                "core/HANDOFF.md": pdir / "core" / "HANDOFF.md",
            }
        else:
            docs = pdir / "docs"
            checks = {
                "PROGRESS.md": docs / "PROGRESS.md",
                "HANDOFF.md": docs / "HANDOFF.md",
            }
        for name, path in checks.items():
            if path.exists():
                # 检查最后修改时间是否是今天
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                today = datetime.now().date()
                if mtime.date() == today:
                    print(f"  ✅ {name} 已更新（{mtime.strftime('%H:%M')}）")
                else:
                    print(f"  ⚠️  {name} 最后修改 {mtime.strftime('%Y-%m-%d')}，可能需要更新")
                    total_warnings += 1
            else:
                if name in {"PROGRESS.md", "design/进度.md"}:
                    print(f"  ⚠️  {name} 不存在（多 Phase 项目建议创建）")
                else:
                    print(f"  ℹ️  {name} 不存在（交接时需要）")
        steps_done += 1

        assurance_verdict = run_assurance_gate(project_dir)
        if strict_assurance and assurance_verdict in {"FAIL", "BLOCKED", "ERROR", "STALE"}:
            print("  ❌ strict assurance 阻止任务收尾声明")
            total_errors += 1
        elif assurance_verdict not in {"PASS", "NOT_APPLICABLE"}:
            total_warnings += 1
        steps_done += 1

        archive_verdict = run_archive_readiness(project_dir)
        if archive_verdict == "READY":
            total_warnings += 1
        elif archive_verdict == "ERROR":
            total_warnings += 1
        steps_done += 1

    # ── 汇总 ──
    print(f"\n{'='*60}")
    print(f"  📊 收尾汇总")
    print(f"{'='*60}")
    print(f"  完成步骤: {steps_done}")
    print(f"  ERROR: {total_errors}")
    print(f"  WARNING: {total_warnings}")
    print()

    if total_errors > 0:
        print("  ❌ 存在 ERROR，请修复后再同步")
        print("     建议: 先修复 ERROR，然后重新运行 task_complete.py")
        return 1
    elif total_warnings > 0:
        print("  ⚠️  存在 WARNING（非阻塞），建议检查")
        print("  💡 可以运行: python auto_sync_daemon.py --once  手动同步")
        return 0
    else:
        print("  ✅ 全部通过！")
        print("  💡 可以运行: python auto_sync_daemon.py --once  手动同步")
        return 0


if __name__ == "__main__":
    sys.exit(main())
