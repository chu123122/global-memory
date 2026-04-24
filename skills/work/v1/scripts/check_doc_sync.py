#!/usr/bin/env python3
"""
check_doc_sync.py — Work Mode Step 4 收尾校验（v3.1 阶段感知）

对每个 active_task 按 Status 阶段过滤：
- discussion / archived → 跳过 AI 文档同步检查
- missing-status        → 输出诊断
- implementation        → 跑原 git mtime 比对 + 额外检查人类文档 mtime > SPEC.md mtime
- unknown               → 跑原 git mtime 比对（旧行为）
"""

import io
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_DIR = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_DIR / "harness"))
from stage_lib import detect_stage  # noqa: E402

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
REGISTRY_FILE = PROJECTS_DIR / "project_registry.json"


def load_registry() -> dict:
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_tasks_root(registry: dict) -> Path:
    custom = registry.get("tasks_root")
    if custom:
        return Path(custom)
    return PROJECTS_DIR


def fmt_mtime(filepath: Path) -> str:
    try:
        ts = filepath.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def get_mtime_iso(filepath: Path) -> str | None:
    try:
        ts = filepath.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def is_git_repo(cwd: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0 and r.stdout.strip() == "true"
    except Exception:
        return False


def git_changed_since(cwd: Path, since_iso: str) -> list:
    try:
        r = subprocess.run(
            ["git", "log", f"--since={since_iso}", "--name-only", "--pretty=format:"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return []
        files = set()
        for line in r.stdout.splitlines():
            line = line.strip()
            if line:
                files.add(line)
        return sorted(files)
    except Exception:
        return []


def check_human_vs_spec(task_dir: Path, registry: dict):
    """实现期额外检查：人类文档 mtime > SPEC.md mtime → 提示。"""
    spec = task_dir / "SPEC.md"
    if not spec.exists():
        return
    spec_mt = spec.stat().st_mtime
    for hp in registry.get("human_doc_patterns", []):
        hd = task_dir / hp
        if not hd.exists():
            continue
        if hd.stat().st_mtime > spec_mt:
            print(f"      ⚠️ 人类文档 {hp} 在 SPEC.md 之后被修改")
            print(f"         {hp} mtime: {fmt_mtime(hd)}")
            print(f"         SPEC.md mtime: {fmt_mtime(spec)}")
            print(f"         建议：要么把 {hp} 变更同步到 SPEC.md，要么把 Status 改回 discussion 重走流程")


def check_task_sync(task: str, cwd: Path, is_git: bool, tasks_root: Path, registry: dict):
    task_dir = tasks_root / task
    if not task_dir.exists():
        print(f"  [任务目录不存在] {task_dir}")
        return

    print(f"\n📌 {task}:")

    stage, diag = detect_stage(task_dir, registry)

    if stage in ("discussion", "archived"):
        print(f"  ⚪ 处于 {stage} 阶段，跳过 AI 文档同步检查")
        return

    if stage == "missing-status":
        print(f"  🔴 missing-status: {diag}")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    for doc_name in ["SPEC.md", "HANDOFF.md"]:
        doc = task_dir / doc_name
        if not doc.exists():
            print(f"  - {doc_name:15s} [不存在]")
            continue

        mtime_str = fmt_mtime(doc)
        mtime_iso = get_mtime_iso(doc)
        print(f"  - {doc_name:15s} mtime: {mtime_str}")

        if not is_git or not mtime_iso:
            continue

        changed = git_changed_since(cwd, mtime_iso)
        if not changed:
            print(f"      ✅ 该文档之后无代码改动")
            continue

        print(f"      ⚠️  该文档之后有 {len(changed)} 处代码改动：")
        for f in changed[:10]:
            print(f"         - {f}")
        if len(changed) > 10:
            print(f"         ...（共 {len(changed)}，仅展示前 10）")

        if doc_name == "SPEC.md":
            print(f"      建议在 {doc} 的「## 进度」章节追加：")
            print(f"         - {today} [本轮做了什么的简述]")
        else:
            print(f"      建议在 {doc} 的「## 下次开始」章节追加状态")

    # 实现期额外检查
    if stage == "implementation":
        check_human_vs_spec(task_dir, registry)


def main():
    print("[文档同步检查]")
    cwd = Path(os.getcwd())
    print(f"cwd: {cwd}")

    is_git = is_git_repo(cwd)
    print(f"git 仓库: {'是' if is_git else '否（无法自动检测代码改动，请手动确认文档是否同步）'}")

    registry = load_registry()
    if not registry:
        print("\n⚠️ project_registry.json 不存在")
        print("→ 跳过 active_task 同步检查")
        return

    active_tasks = registry.get("active_tasks", [])
    if not active_tasks:
        print("\n(无 active_tasks，无需检查)")
        return

    tasks_root = get_tasks_root(registry)
    print(f"tasks_root: {tasks_root}")

    for task in active_tasks:
        check_task_sync(task, cwd, is_git, tasks_root, registry)

    print("\n[完成] 按上方告警决定是否手动更新文档。")


if __name__ == "__main__":
    main()
