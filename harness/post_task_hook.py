#!/usr/bin/env python3
"""
post_task_hook.py — 任务后自动拦截检查 + semantic 前台刷新

设计目的：
  防止 AI 完成任务后忘记更新进度文档、索引、CHANGELOG。
  Stop 热路径同步执行 semantic check + 必要时 sync；Git 提交/推送必须人工显式执行。

工作流程：
  1. 检测进度文档是否过期（PROGRESS.md / HANDOFF.md 最后修改时间 > 24h）
  2. 检测 MEMORY.md 自动索引区是否和实际 topic 文件同步
  3. 检测 semantic 主索引是否 stale；stale 时在 Stop hook 内前台刷新并写事件日志
  4. 检测 CHANGELOG 是否在本次变更后有新记录
  5. 如果有问题：自动修复可修复项（索引同步/统计更新），不可修复项生成提醒
  6. 不自动 git add / commit / push；需要保存时手动跑 maintain.py sync --preview + sync --source manual

用法：
  python post_task_hook.py                         # 检查全部仓库
  python post_task_hook.py --project <dir>         # 额外检查项目进度
  python post_task_hook.py --auto-fix              # 自动修复本地索引/统计；不提交不推送
  python post_task_hook.py --pre-commit            # 作为 git pre-commit hook
  python post_task_hook.py --install-hook <repo>   # 安装为 git pre-commit hook

退出码：
  0 = 全部通过或已修复
  1 = 有不可自动修复的问题（pre-commit 模式下阻止提交）
"""

import io
import json
import os
import re
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import CLAUDE_DIR, MEMORY_DIR, TOPIC_DIRS  # noqa: E402

STALE_HOURS = 24  # 超过多少小时视为过期
SEMANTIC_REFRESH_EVENTS_FILE = SCRIPTS_DIR / "data" / "semantic_refresh_events.jsonl"
SEMANTIC_SYNC_QUEUE_FILE = SCRIPTS_DIR / "data" / "semantic_sync_queue.json"
SEMANTIC_CHECK_TIMEOUT_SECONDS = int(os.environ.get("SEMANTIC_STOP_HOOK_CHECK_TIMEOUT_SECONDS", "60"))
SEMANTIC_SYNC_TIMEOUT_SECONDS = int(os.environ.get("SEMANTIC_STOP_HOOK_SYNC_TIMEOUT_SECONDS", "900"))
ACTIVE_TASKS_DIR = Path(os.environ.get("CLAUDE_TASKS_ACTIVE_DIR", Path.home() / ".claude" / "tasks" / "active"))


class HookResult:
    def __init__(self):
        self.errors = []     # 不可自动修复
        self.warnings = []   # 提醒
        self.fixed = []      # 已自动修复
        self.passed = []     # 通过


def extract_indexed_topic_paths(content):
    """只读取 MEMORY.md 的 AUTO-INDEX 区块，避免把项目文档/系统索引误判成 topic 链接。"""
    referenced = set()
    in_auto_block = False

    for line in content.splitlines():
        if "<!-- AUTO-INDEX:BEGIN" in line:
            in_auto_block = True
            continue
        if "<!-- AUTO-INDEX:END" in line:
            in_auto_block = False
            continue
        if not in_auto_block or not line.strip().startswith("|"):
            continue
        for match in re.finditer(r'\[.*?\]\((.*?\.md)\)', line):
            rel_path = match.group(1)
            if rel_path.split("/", 1)[0] in TOPIC_DIRS:
                referenced.add(rel_path)

    return referenced


def check_index_sync(result):
    """检查 MEMORY.md 自动索引区是否和 topic 文件同步"""
    memory_md = MEMORY_DIR / "MEMORY.md"
    if not memory_md.exists():
        result.errors.append("MEMORY.md 不存在")
        return

    content = memory_md.read_text(encoding="utf-8", errors="replace")
    referenced = extract_indexed_topic_paths(content)

    actual = set()
    for subdir in TOPIC_DIRS:
        d = MEMORY_DIR / subdir
        if d.exists():
            for f in d.glob("*.md"):
                if f.name != ".gitkeep":
                    actual.add(f"{subdir}/{f.name}")

    missing_from_index = actual - referenced
    dead_links = referenced - actual

    if missing_from_index or dead_links:
        msgs = []
        if missing_from_index:
            msgs.append(f"索引缺少 {len(missing_from_index)} 个文件")
        if dead_links:
            msgs.append(f"索引有 {len(dead_links)} 个死链")
        result.warnings.append(f"索引不同步: {'; '.join(msgs)}")
        return False
    else:
        result.passed.append("索引同步完整")
        return True


def check_changelog_freshness(result):
    """检查 CHANGELOG 是否有近期记录（和 git 变更时间对比）"""
    changelog = MEMORY_DIR / "CHANGELOG.md"
    if not changelog.exists():
        result.passed.append("CHANGELOG.md 不存在（已降级为可选）")
        return

    content = changelog.read_text(encoding="utf-8", errors="replace")
    today = datetime.now().strftime("%Y-%m-%d")

    if today in content:
        result.passed.append(f"CHANGELOG 有今天的记录")
    else:
        # 检查是否有今天的 git 变更
        try:
            r = subprocess.run(
                ["git", "log", "--since=today", "--oneline"],
                capture_output=True, text=True, cwd=str(MEMORY_DIR), encoding="utf-8"
            )
            if r.stdout.strip():
                result.passed.append(
                    f"今天有 git 变更，CHANGELOG 可选更新（版本级变更记 README Release Notes）")
            else:
                result.passed.append("今天无 git 变更，CHANGELOG 无需更新")
        except Exception:
            result.passed.append("CHANGELOG 检查完成")


def check_progress_freshness(result, project_dir):
    """检查项目进度文档是否过期"""
    if not project_dir:
        return

    docs = Path(project_dir).resolve() / "docs"
    if not docs.exists():
        return

    progress = docs / "PROGRESS.md"
    handoff = docs / "HANDOFF.md"

    stale_threshold = datetime.now() - timedelta(hours=STALE_HOURS)

    for doc, name in [(progress, "PROGRESS.md"), (handoff, "HANDOFF.md")]:
        if doc.exists():
            mtime = datetime.fromtimestamp(doc.stat().st_mtime)
            if mtime < stale_threshold:
                result.warnings.append(
                    f"{name} 最后修改 {mtime.strftime('%Y-%m-%d %H:%M')}，可能需要更新")
            else:
                result.passed.append(f"{name} 已更新")


def infer_task_name(project_dir: str | None = None) -> str:
    """Infer the user-facing task name for Stop hook semantic refresh messages."""
    if project_dir:
        try:
            name = Path(project_dir).resolve().name
        except Exception:  # noqa: BLE001
            name = Path(project_dir).name
        if name:
            return name

    try:
        cwd = Path.cwd().resolve()
    except Exception:  # noqa: BLE001
        cwd = Path.cwd()

    try:
        rel = cwd.relative_to(ACTIVE_TASKS_DIR)
        if rel.parts:
            return rel.parts[0]
    except ValueError:
        cwd_text = str(cwd).replace("/", "\\").rstrip("\\")
        active_text = str(ACTIVE_TASKS_DIR).replace("/", "\\").rstrip("\\")
        prefix = active_text.lower() + "\\"
        if cwd_text.lower().startswith(prefix):
            remainder = cwd_text[len(prefix):]
            name = remainder.split("\\", 1)[0]
            if name:
                return name
    except Exception:  # noqa: BLE001
        pass

    return "unknown"


def semantic_report_needs_sync(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    return bool(data.get("needsSync") or data.get("missing_count") or data.get("dirty_count") or data.get("stale_count"))


def _semantic_count(data: dict[str, Any] | None, key: str) -> int | None:
    if not data:
        return None
    value = data.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def write_semantic_refresh_event(
    *,
    task_name: str,
    phase: str,
    ok: bool,
    command: list[str] | None = None,
    exit_code: int | None = None,
    duration_ms: int | None = None,
    report: dict[str, Any] | None = None,
    error: str | None = None,
    trigger: str = "stop-hook",
) -> None:
    """Append one visible structured event for Stop hook semantic refresh."""
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "taskName": task_name or "unknown",
        "trigger": trigger,
        "phase": phase,
        "ok": bool(ok),
        "needsSync": semantic_report_needs_sync(report) if report is not None else None,
        "missing_count": _semantic_count(report, "missing_count"),
        "dirty_count": _semantic_count(report, "dirty_count"),
        "stale_count": _semantic_count(report, "stale_count"),
        "command": command,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "error": error,
    }
    SEMANTIC_REFRESH_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SEMANTIC_REFRESH_EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_semantic_maintain_command(args: list[str], *, timeout: int) -> tuple[int, dict[str, Any] | None, str | None, list[str], int]:
    """Run maintain.py semantic-sync and parse its JSON stdout."""
    maintain = SCRIPTS_DIR / "maintain.py"
    cmd = [sys.executable, str(maintain), "semantic-sync", *args]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(MEMORY_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return 124, None, f"timeout after {exc.timeout}s", cmd, duration_ms
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started) * 1000)
        return 1, None, f"{type(exc).__name__}: {exc}", cmd, duration_ms

    duration_ms = int((time.perf_counter() - started) * 1000)
    stdout = (proc.stdout or "").strip()
    if not stdout:
        error = (proc.stderr or "").strip() or "no_json_stdout"
        return proc.returncode, None, error, cmd, duration_ms
    try:
        return proc.returncode, json.loads(stdout), (proc.stderr or "").strip() or None, cmd, duration_ms
    except json.JSONDecodeError:
        tail = " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-3:])
        return proc.returncode, None, tail or "invalid_json_stdout", cmd, duration_ms


def _semantic_failure_reason(stage: str, exit_code: int, report: dict[str, Any] | None, error: str | None) -> str:
    if report:
        if report.get("skipped"):
            return f"{stage}_skipped:{report.get('skipped_reason') or 'unknown'}"
        if semantic_report_needs_sync(report):
            return (
                f"{stage}_after仍needsSync "
                f"missing={report.get('missing_count')} dirty={report.get('dirty_count')} stale={report.get('stale_count')}"
            )
        if report.get("error"):
            return f"{stage}_error:{report.get('error')}"
    if error:
        return f"{stage}_error:{error}"
    if exit_code != 0:
        return f"{stage}_exit={exit_code}"
    return f"{stage}_unknown_failure"


def _clear_semantic_queue_after_success() -> None:
    try:
        SEMANTIC_SYNC_QUEUE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def check_semantic_index_stale(result, project_dir: str | None = None) -> bool:
    """Stop hook synchronously checks and refreshes semantic index through maintain.py."""
    task_name = infer_task_name(project_dir)
    check_args = ["--check-only", "--trigger", "stop-hook", "--json"]
    write_semantic_refresh_event(task_name=task_name, phase="check_start", ok=True, command=[sys.executable, str(SCRIPTS_DIR / "maintain.py"), "semantic-sync", *check_args])
    check_code, check_report, check_error, check_cmd, check_duration = run_semantic_maintain_command(
        check_args,
        timeout=SEMANTIC_CHECK_TIMEOUT_SECONDS,
    )
    check_ok = check_report is not None and (check_code == 0 or semantic_report_needs_sync(check_report)) and not check_report.get("error")
    write_semantic_refresh_event(
        task_name=task_name,
        phase="check_result",
        ok=check_ok,
        command=check_cmd,
        exit_code=check_code,
        duration_ms=check_duration,
        report=check_report,
        error=None if check_ok else _semantic_failure_reason("check", check_code, check_report, check_error),
    )

    if not check_ok:
        reason = _semantic_failure_reason("check", check_code, check_report, check_error)
        message = f"当前{task_name}RAG库更新失败：{reason}"
        result.warnings.append(message)
        write_semantic_refresh_event(task_name=task_name, phase="final_message", ok=False, report=check_report, error=message)
        return False

    if not semantic_report_needs_sync(check_report):
        message = f"当前{task_name}RAG库无需更新"
        result.passed.append(message)
        write_semantic_refresh_event(task_name=task_name, phase="final_message", ok=True, report=check_report, error=None)
        return True

    sync_args = ["--trigger", "stop-hook", "--force", "--json"]
    write_semantic_refresh_event(task_name=task_name, phase="sync_start", ok=True, command=[sys.executable, str(SCRIPTS_DIR / "maintain.py"), "semantic-sync", *sync_args], report=check_report)
    sync_code, sync_report, sync_error, sync_cmd, sync_duration = run_semantic_maintain_command(
        sync_args,
        timeout=SEMANTIC_SYNC_TIMEOUT_SECONDS,
    )
    sync_ok = (
        sync_code == 0
        and sync_report is not None
        and bool(sync_report.get("ok"))
        and not sync_report.get("skipped")
        and not semantic_report_needs_sync(sync_report)
    )
    reason = None if sync_ok else _semantic_failure_reason("sync", sync_code, sync_report, sync_error)
    write_semantic_refresh_event(
        task_name=task_name,
        phase="sync_result",
        ok=sync_ok,
        command=sync_cmd,
        exit_code=sync_code,
        duration_ms=sync_duration,
        report=sync_report,
        error=reason,
    )

    if sync_ok:
        _clear_semantic_queue_after_success()
        message = f"当前{task_name}RAG库已更新"
        result.passed.append(message)
        write_semantic_refresh_event(task_name=task_name, phase="final_message", ok=True, report=sync_report, error=None)
        return True

    message = f"当前{task_name}RAG库更新失败：{reason}"
    result.warnings.append(message)
    write_semantic_refresh_event(task_name=task_name, phase="final_message", ok=False, report=sync_report, error=message)
    return False

def check_git_staged_memory_has_changelog(result):
    """pre-commit 模式：检查暂存区中的记忆文件变更是否有对应 CHANGELOG 记录"""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=str(MEMORY_DIR), encoding="utf-8"
        )
        staged = [f for f in r.stdout.strip().splitlines() if f.endswith(".md")]
        staged = [f for f in staged if f not in ("CHANGELOG.md", "MEMORY.md", "README.md")]

        if not staged:
            result.passed.append("暂存区无记忆文件变更")
            return True

        # 检查 CHANGELOG.md 是否也在暂存区
        r2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--", "CHANGELOG.md"],
            capture_output=True, text=True, cwd=str(MEMORY_DIR), encoding="utf-8"
        )
        if "CHANGELOG.md" in r2.stdout:
            result.passed.append(f"暂存区有 {len(staged)} 个记忆文件变更，CHANGELOG 已同步更新")
            return True
        else:
            result.errors.append(
                f"暂存区有 {len(staged)} 个记忆文件变更，但 CHANGELOG.md 未更新！"
                f"\n     变更文件: {', '.join(staged[:5])}"
                f"\n     修复: 运行 python append_changelog.py UPDATE <文件> ...")
            return False
    except Exception:
        return True


def auto_fix_index(result):
    """自动修复索引同步"""
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from sync_index import sync_index
        sync_index(dry_run=False)
        result.fixed.append("索引已自动重建")
        return True
    except Exception as e:
        result.warnings.append(f"索引自动修复失败: {e}")
        return False


def auto_fix_stats(result):
    """自动修复统计数字"""
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from update_stats import update_stats
        update_stats(dry_run=False)
        result.fixed.append("统计数字已自动更新")
        return True
    except Exception as e:
        result.warnings.append(f"统计更新失败: {e}")
        return False


def git_sync_repo(repo_path):
    """同步指定仓库。返回 (ok, message)。Git 行为委托给 maintain.py。"""
    if not (repo_path / ".git").is_dir():
        return (False, f"{repo_path.name}: 不是 git 仓库")
    try:
        maintain = SCRIPTS_DIR / "maintain.py"
        result = subprocess.run(
            [sys.executable, str(maintain), "sync", "--source", "stop-hook", "--json"],
            cwd=str(repo_path), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        # 优先解析 JSON —— maintain.py 即使非 0 也输出完整 JSON。
        # JSON.summary / JSON.stderr 比 raw stdout splitlines tail 干净得多。
        data = None
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            data = None

        if data is not None:
            summary = str(data.get("summary") or "(无 summary)").strip()
            if data.get("synced"):
                return (True, f"{repo_path.name} 已同步: {data.get('commit')}")
            if result.returncode == 0:
                return (True, f"{repo_path.name} 无需同步: {summary}")
            stderr_tail = (str(data.get("stderr") or "")).strip().splitlines()
            hint = f"; {stderr_tail[-1]}" if stderr_tail else ""
            return (False, f"{repo_path.name} sync 失败: {summary}{hint}")

        # JSON 解析不出来才回退到 raw 输出
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip().splitlines()
            tail = " | ".join(err[-3:]) if err else "(无输出)"
            return (False, f"{repo_path.name} sync 失败: {tail}")
        return (True, f"{repo_path.name} sync 完成（无 JSON）")
    except subprocess.TimeoutExpired:
        return (False, f"{repo_path.name} sync 超时（凭证未配？）")
    except Exception as e:
        return (False, f"{repo_path.name} 异常: {e}")


def install_hook(repo_dir):
    """安装为 git pre-commit hook"""
    hook_dir = Path(repo_dir) / ".git" / "hooks"
    hook_file = hook_dir / "pre-commit"
    hook_dir.mkdir(parents=True, exist_ok=True)

    hook_content = f"""#!/bin/sh
# Auto-generated by post_task_hook.py
python "{Path(__file__).resolve()}" --pre-commit
"""
    hook_file.write_text(hook_content, encoding="utf-8")
    # Windows 不需要 chmod，Git for Windows 自动处理
    print(f"  ✅ pre-commit hook 已安装到 {hook_file}")


def main():
    is_pre_commit = "--pre-commit" in sys.argv
    auto_fix = "--auto-fix" in sys.argv
    project_dir = None

    # 安装 hook 模式
    if "--install-hook" in sys.argv:
        idx = sys.argv.index("--install-hook")
        if idx + 1 < len(sys.argv):
            install_hook(sys.argv[idx + 1])
        else:
            print("用法: python post_task_hook.py --install-hook <repo_dir>")
        return

    # 解析项目目录
    if "--project" in sys.argv:
        idx = sys.argv.index("--project")
        if idx + 1 < len(sys.argv):
            project_dir = sys.argv[idx + 1]

    print("=" * 50)
    mode = "pre-commit" if is_pre_commit else ("auto-fix" if auto_fix else "检查")
    print(f"  post_task_hook.py [{mode} 模式]")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    result = HookResult()

    # ── 检查 ──
    index_ok = check_index_sync(result)
    check_semantic_index_stale(result, project_dir)
    check_changelog_freshness(result)

    if project_dir:
        check_progress_freshness(result, project_dir)

    if is_pre_commit:
        check_git_staged_memory_has_changelog(result)

    # ── 自动修复 ──
    if auto_fix and not index_ok:
        print("\n  🔧 执行自动修复...")
        auto_fix_index(result)
        auto_fix_stats(result)

    # ── 输出 ──
    print()
    if result.passed:
        for msg in result.passed:
            print(f"  ✅ {msg}")
    if result.fixed:
        for msg in result.fixed:
            print(f"  🔧 {msg}")
    if result.warnings:
        for msg in result.warnings:
            print(f"  ⚠️  {msg}")
    if result.errors:
        for msg in result.errors:
            print(f"  ❌ {msg}")

    # ── Git 同步 ──
    # Phase4-B: Stop hook 不再自动 commit/push。Git 同步必须由人显式预览后触发。
    if auto_fix or not is_pre_commit:
        print("\n  📤 Git 同步：已停用自动提交/推送")
        print(r"  ℹ️  如需保存当前改动：python harness\maintain.py sync --preview --json")
        print(r"  ℹ️  确认后再运行：python harness\maintain.py sync --source manual")

    # ── 健康检测 ──
    # 每次 stop-hook 跑一遍 health runner，结果 append 到 health_checks.jsonl，
    # 给下一次会话 / 控制面板 / AI 拿到最新快照。critical 的列出来。
    print("\n  🏥 健康检测...")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "harness.health.runner", "--json"],
            cwd=str(MEMORY_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if proc.returncode in (0, 1) and proc.stdout.strip():
            signals = (json.loads(proc.stdout).get("signals") or [])
            crits = [s for s in signals if s.get("status") == "critical"]
            warns = sum(1 for s in signals if s.get("status") == "warning")
            print(f"  📊 {len(crits)} critical / {warns} warning / {len(signals)} total")
            for s in crits:
                print(f"      🔴 {s.get('check_id')}: {s.get('headline')}")
        else:
            print(f"  ⚠️  health runner exit={proc.returncode}; stderr 前 80 字: {proc.stderr[:80]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  health 检测失败: {type(exc).__name__}: {exc}")

    # ── 问题闭环 ETL（feedback-loop-v1 D5）──
    # 健康检测之后立即跑 issue_tracker --extract，把新的 non-ok signal
    # 派生为 detected/reopened；自动 fixed 已消失的 issue。
    # 增量 ETL 让控制面板「问题闭环」tab 始终拿到最新状态。
    print("\n  🔄 问题闭环 ETL...")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "harness.issue_tracker", "--extract", "--json"],
            cwd=str(MEMORY_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if proc.returncode in (0, 1) and proc.stdout.strip():
            payload = json.loads(proc.stdout)
            new_issues = payload.get("issues") or []
            count = payload.get("new_count", 0)
            if count == 0:
                print("  📦 无新事件（issues.jsonl 不变）")
            else:
                by_event: dict[str, int] = {}
                for i in new_issues:
                    ev = i.get("event", "?")
                    by_event[ev] = by_event.get(ev, 0) + 1
                summary = " / ".join(f"{ev} {n}" for ev, n in by_event.items())
                print(f"  📦 新增 {count} 条事件：{summary}")
        else:
            print(f"  ⚠️  issue_tracker exit={proc.returncode}; stderr: {proc.stderr[:80]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  issue_tracker 失败: {type(exc).__name__}: {exc}")

    # ── 汇总 ──
    print(f"\n{'─'*50}")
    print(f"  ✅ {len(result.passed)} PASS | 🔧 {len(result.fixed)} FIXED "
          f"| ⚠️ {len(result.warnings)} WARNING | ❌ {len(result.errors)} ERROR")

    if result.errors:
        print("  ❌ 存在不可自动修复的问题！")
        # 写 stderr 让 Claude Code hook runner 能展示具体原因
        for msg in result.errors:
            print(msg, file=sys.stderr)
        if is_pre_commit:
            print("  → commit 被阻止，请先修复上述 ERROR")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
