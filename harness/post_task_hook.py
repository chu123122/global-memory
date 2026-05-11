#!/usr/bin/env python3
"""
post_task_hook.py — 任务后自动拦截检查 + 同步上传

设计目的：
  防止 AI 完成任务后忘记更新进度文档、索引、CHANGELOG。
  可以被 auto_sync_daemon 调用，也可以作为 git pre-commit hook。

工作流程：
  1. 检测进度文档是否过期（PROGRESS.md / HANDOFF.md 最后修改时间 > 24h）
  2. 检测 MEMORY.md 自动索引区是否和实际 topic 文件同步
  3. 检测 CHANGELOG 是否在本次变更后有新记录
  4. 如果有问题：自动修复可修复项（索引同步/统计更新），不可修复项生成提醒
  5. 修复后仅在检测到实际变更时 git add + commit + push

用法：
  python post_task_hook.py                         # 检查全部仓库
  python post_task_hook.py --project <dir>         # 额外检查项目进度
  python post_task_hook.py --auto-fix              # 自动修复 + 同步
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
from pathlib import Path
from datetime import datetime, timedelta

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import CLAUDE_DIR, MEMORY_DIR, TOPIC_DIRS  # noqa: E402

STALE_HOURS = 24  # 超过多少小时视为过期


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
        result.errors.append("CHANGELOG.md 不存在")
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
                result.warnings.append(
                    f"今天有 git 变更但 CHANGELOG 无今天的记录")
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

    # ── 自动同步 ──
    # 单仓库合并后只同步 active global-memory repo；legacy skills-repo 不再自动写。
    if auto_fix or not is_pre_commit:
        print("\n  📤 自动同步仓库...")
        for repo in (MEMORY_DIR,):
            ok, msg = git_sync_repo(repo)
            print(f"  {'✅' if ok else '❌'} {msg}")
            if not ok:
                # push 失败要进 errors 让上层看到（之前的静默吞错就是这里漏的）
                result.errors.append(msg)

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
        if is_pre_commit:
            print("  → commit 被阻止，请先修复上述 ERROR")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
