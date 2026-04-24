#!/usr/bin/env python3
"""
harness_status.py - Phase 2-A: harness 全景状态聚合 CLI

一行命令出全景:
- 8 hooks installed + last_triggered(从 audit jsonl)
- memory 计数 / 状态
- 2 repo git 状态(global-memory + skills-repo,如存在)
- active_tasks 数 / 各任务 stage
- last post_task_hook 时间
- next_action 推荐

输出:
- STDOUT: 人类可读 / --json 机器可读
- 落盘:STATUS_SNAPSHOT.md(默认 D:/global-memory/STATUS_SNAPSHOT.md)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    MEMORY_DIR, CLAUDE_DIR, LOG_DIR, MAX_FILES,
    count_all_memory_files, today_str,
)

REGISTRY_PATH = CLAUDE_DIR / "projects" / "project_registry.json"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
STATUS_SNAPSHOT = MEMORY_DIR / "STATUS_SNAPSHOT.md"

HOOK_NAMES = [
    "audit_logger", "dangerous_command_blocker", "memory_file_protector",
    "doc_gate", "diff_backup", "diff_show", "subagent_logger",
    "post_task_hook",
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_registry() -> dict:
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def installed_hooks(settings: dict) -> dict[str, bool]:
    """从 settings.json 提取每个 hook 的安装状态(命令字符串包含 hook 名)"""
    text = json.dumps(settings)
    return {name: name in text for name in HOOK_NAMES}


def last_triggered_from_audit(hook_name: str) -> str | None:
    """读 audit jsonl 倒序找最近触发(按命令字符串匹配 hook 名)"""
    audit_paths = [
        LOG_DIR / "tool_audit.jsonl",
        LOG_DIR / "subagent_audit.jsonl",
    ]
    for path in audit_paths:
        if not path.exists():
            continue
        try:
            # 倒序读最后 200 行避免大文件
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-200:]
            for line in reversed(lines):
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                # 简单匹配:hook 名出现在 record 任意字段
                if hook_name in json.dumps(obj):
                    return obj.get("timestamp") or obj.get("ts") or "unknown"
        except Exception:
            continue
    return None


def git_status(repo_dir: Path) -> dict:
    if not (repo_dir / ".git").exists() and not (repo_dir / ".git").is_file():
        return {"exists": False}
    try:
        proc = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=str(repo_dir), capture_output=True, text=True, encoding="utf-8",
        )
        out = proc.stdout
        head_line = out.splitlines()[0] if out else ""
        dirty_lines = [l for l in out.splitlines()[1:] if l.strip()]
        return {
            "exists": True,
            "branch_status": head_line,
            "dirty_count": len(dirty_lines),
            "clean": len(dirty_lines) == 0,
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}


def active_tasks_summary(registry: dict) -> dict:
    tasks = registry.get("active_tasks", [])
    tasks_root = Path(registry.get("tasks_root", ""))
    return {
        "count": len(tasks),
        "names": tasks,
        "tasks_root": str(tasks_root) if tasks_root else None,
    }


def memory_summary() -> dict:
    count = count_all_memory_files()
    return {
        "count": count,
        "max": MAX_FILES,
        "ratio": round(count / MAX_FILES, 2) if MAX_FILES else None,
        "level": "OK" if count <= MAX_FILES * 0.8 else ("WARN" if count <= MAX_FILES else "OVER"),
    }


def last_post_task_hook() -> str | None:
    log_path = LOG_DIR / "post_task_hook.log"
    if not log_path.exists():
        return None
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            if line.strip():
                # 期待 [YYYY-MM-DD HH:MM] message 格式
                if line.startswith("["):
                    return line.split("]")[0].lstrip("[")
                return line[:40]
    except Exception:
        pass
    return None


def derive_next_action(memory: dict, repo_git: dict, hooks: dict[str, bool]) -> list[str]:
    actions = []
    if memory["level"] == "OVER":
        actions.append("memory 超 MAX_FILES,跑 memory_gc.py --dry-run 看候选")
    elif memory["level"] == "WARN":
        actions.append("memory 接近上限(80%),近期跑 memory_gc.py 检查")
    if repo_git.get("dirty_count", 0) > 5:
        actions.append(f"global-memory 工作区 dirty {repo_git['dirty_count']} 项,review 后 commit")
    not_installed = [h for h, ok in hooks.items() if not ok]
    if not_installed:
        actions.append(f"hooks 未安装: {','.join(not_installed)} → 检查 settings.json")
    if not actions:
        actions.append("✅ 系统状态良好,可继续推进任务")
    return actions


def collect() -> dict:
    settings = load_settings()
    registry = load_registry()
    hooks = installed_hooks(settings)
    memory = memory_summary()
    gm_git = git_status(MEMORY_DIR)
    skills_repo = Path("D:/skills-repo")
    skills_git = git_status(skills_repo) if skills_repo.exists() else {"exists": False}

    last_triggered = {h: last_triggered_from_audit(h) for h in HOOK_NAMES}

    report = {
        "timestamp": now_iso(),
        "hooks": {
            "installed": hooks,
            "last_triggered": last_triggered,
        },
        "memory": memory,
        "repos": {
            "global_memory": gm_git,
            "skills_repo": skills_git,
        },
        "active_tasks": active_tasks_summary(registry),
        "last_post_task_hook": last_post_task_hook(),
    }
    report["next_action"] = derive_next_action(memory, gm_git, hooks)
    return report


def render_markdown(report: dict) -> str:
    lines = [
        "# Harness Status Snapshot",
        f"> Generated: {report['timestamp']}",
        "",
        "## Hooks",
        "",
        "| hook | installed | last triggered |",
        "|---|---|---|",
    ]
    for h in HOOK_NAMES:
        ok = "✅" if report["hooks"]["installed"][h] else "❌"
        last = report["hooks"]["last_triggered"].get(h) or "—"
        lines.append(f"| {h} | {ok} | {last} |")
    mem = report["memory"]
    lines.extend([
        "",
        "## Memory",
        f"- count: **{mem['count']} / {mem['max']}** ({mem['level']})",
        "",
        "## Repos",
    ])
    for name, g in report["repos"].items():
        if not g.get("exists"):
            lines.append(f"- {name}: not present")
        elif g.get("clean"):
            lines.append(f"- {name}: ✅ clean (`{g.get('branch_status', '')}`)")
        else:
            lines.append(f"- {name}: ⚠️ dirty {g.get('dirty_count', '?')} items (`{g.get('branch_status', '')}`)")
    at = report["active_tasks"]
    lines.extend([
        "",
        "## Active Tasks",
        f"- count: {at['count']}",
        f"- names: {', '.join(at['names'])}",
        "",
        "## Last post_task_hook",
        f"- {report['last_post_task_hook'] or '— (no log yet)'}",
        "",
        "## Next Action",
    ])
    for a in report["next_action"]:
        lines.append(f"- {a}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="harness_status — full-stack harness state aggregator (Phase 2-A)")
    p.add_argument("--json", action="store_true", help="emit JSON to stdout")
    p.add_argument("--no-snapshot", action="store_true", help="skip writing STATUS_SNAPSHOT.md")
    args = p.parse_args()

    report = collect()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))

    if not args.no_snapshot:
        STATUS_SNAPSHOT.write_text(render_markdown(report), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
