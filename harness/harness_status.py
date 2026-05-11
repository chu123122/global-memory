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
- 落盘:仅在显式传入 --write-snapshot 时写 STATUS_SNAPSHOT.md
"""

from __future__ import annotations

import argparse
import json
import os
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

def _discover_hook_names() -> list[str]:
    """扫描 harness/hooks/*.py（排除 _ 开头）+ post_task_hook。"""
    hooks_dir = Path(__file__).resolve().parent / "hooks"
    names = sorted(
        f.stem for f in hooks_dir.iterdir()
        if f.suffix == ".py" and not f.name.startswith("_")
    ) if hooks_dir.is_dir() else []
    names.append("post_task_hook")
    return names

HOOK_NAMES = _discover_hook_names()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ===== Phase 2-A.1: 任务清单 + 简介抽取 =====
import re  # noqa: E402

HUMAN_DOC_NAMES = ["需求分析.md", "设计文档.md", "REQUIREMENTS.md", "DESIGN.md"]


def _read_status_field(doc_path: Path) -> str | None:
    """从文档头部 frontmatter 提取 Status 字段(同 stage_lib 简化版)"""
    if not doc_path.exists():
        return None
    try:
        head = doc_path.read_text(encoding="utf-8", errors="replace")[:500]
    except Exception:
        return None
    m = re.search(r"^>?\s*Status:\s*(\w[\w-]*)", head, re.MULTILINE)
    return m.group(1).lower() if m else None


def _extract_first_paragraph_after_h1(text: str) -> str:
    """从 markdown 抽 # h1 之后的第一段正文(跳过 > frontmatter 块、---、## h2)"""
    lines = text.splitlines()
    in_body = False
    para_lines: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("# "):
            in_body = True
            continue
        if not in_body:
            continue
        # 跳所有 frontmatter 噪音(允许 > 单字符也跳)
        if s.startswith(">") or s.startswith("---") or s == "":
            if para_lines:
                break
            continue
        # 跳 ## h2(找正文,不要 h2 标题本身)
        if s.startswith("#"):
            if para_lines:
                break
            continue
        para_lines.append(s)
        if len(" ".join(para_lines)) > 200:
            break
    return " ".join(para_lines).strip()


def _extract_section(text: str, header_pattern: str) -> str:
    """抽指定 ## 标题下的第一段"""
    m = re.search(rf"^##\s+{header_pattern}\s*$(.*?)(?=^##\s|\Z)",
                  text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    body = m.group(1).strip()
    # 取第一段
    paras = re.split(r"\n\s*\n", body)
    return paras[0].strip() if paras else ""


def task_brief(task_dir: Path) -> tuple[str, str]:
    """返回 (stage, brief 一两句话)。从 需求分析/HANDOFF/SPEC 按规则抽"""
    if not task_dir.exists() or not task_dir.is_dir():
        return ("missing", "(任务目录不存在)")

    # 找人类向文档
    human_doc = next(
        (task_dir / n for n in HUMAN_DOC_NAMES if (task_dir / n).exists()),
        None,
    )
    handoff = task_dir / "HANDOFF.md"
    spec = task_dir / "SPEC.md"

    stage = _read_status_field(human_doc) if human_doc else None
    if stage is None:
        stage = "implementation" if handoff.exists() else "unknown"

    # 按 stage 选择来源
    brief = ""
    if stage == "implementation" and handoff.exists():
        text = handoff.read_text(encoding="utf-8", errors="replace")
        brief = _extract_section(text, r"30\s*秒速读") or _extract_first_paragraph_after_h1(text)
    if not brief and human_doc:
        text = human_doc.read_text(encoding="utf-8", errors="replace")
        # 优先 §1 这是什么 / §1 业务背景 / §1 .* — 第一个 ## 1
        brief = _extract_section(text, r"1\..*") or _extract_first_paragraph_after_h1(text)
    if not brief and spec.exists():
        brief = _extract_first_paragraph_after_h1(spec.read_text(encoding="utf-8", errors="replace"))
    if not brief:
        brief = "(无简介)"

    # 截断 200 字
    if len(brief) > 200:
        brief = brief[:200] + "…"
    return (stage, brief)


def collect_tasks() -> dict:
    """扫 active + archived 任务,返回 {active:[{name,stage,brief,path}], archived:[...]}"""
    registry = load_registry()
    tasks_root = Path(registry.get("tasks_root", ""))
    archived_root = Path(registry.get("archived_tasks_root", ""))
    active_names = registry.get("active_tasks", [])

    active: list[dict] = []
    for name in active_names:
        # 优先 tasks_root;但若该目录为空(doc_gate 自动建空目录的产物),fallback 到 task_paths
        task_dir = tasks_root / name

        def _has_any_doc(d: Path) -> bool:
            return d.exists() and any(
                (d / fn).exists() for fn in ("需求分析.md", "REQUIREMENTS.md", "HANDOFF.md", "SPEC.md")
            )

        if not _has_any_doc(task_dir):
            paths = registry.get("task_paths", {}).get(name, [])
            for p in paths:
                pd = Path(p)
                if pd.is_dir() and _has_any_doc(pd):
                    task_dir = pd
                    break
        stage, brief = task_brief(task_dir)
        active.append({
            "name": name,
            "stage": stage,
            "brief": brief,
            "path": str(task_dir),
        })

    archived: list[dict] = []
    if archived_root.exists():
        for d in sorted(archived_root.iterdir()):
            if not d.is_dir():
                continue
            stage, brief = task_brief(d)
            archived.append({
                "name": d.name,
                "stage": stage if stage != "unknown" else "archived",
                "brief": brief,
                "path": str(d),
            })

    return {"active": active, "archived": archived}


def render_tasks_text(t: dict) -> str:
    out = ["# Tasks Overview", ""]
    out.append(f"## Active ({len(t['active'])})")
    out.append("")
    for task in t["active"]:
        stage_icon = {"discussion": "🟢", "implementation": "🔵",
                      "archived": "⚪", "unknown": "⚪", "missing": "❌"}.get(task["stage"], "⚪")
        out.append(f"### {stage_icon} {task['name']}  [{task['stage']}]")
        out.append(f"  {task['brief']}")
        out.append("")
    out.append(f"## Archived ({len(t['archived'])})")
    out.append("")
    for task in t["archived"]:
        out.append(f"### ⚫ {task['name']}")
        out.append(f"  {task['brief']}")
        out.append("")
    return "\n".join(out) + "\n"


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
    skills_repo = Path(os.environ.get("LEGACY_SKILLS_REPO_DIR", str(MEMORY_DIR.parent / "skills-repo")))
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
    p.add_argument("--write-snapshot", action="store_true", help="write STATUS_SNAPSHOT.md")
    p.add_argument("--no-snapshot", action="store_true", help="deprecated no-op; snapshots are opt-in")
    p.add_argument("--tasks", action="store_true",
                   help="Phase 2-A.1: emit tasks overview (active + archived w/ briefs) instead of full status")
    args = p.parse_args()

    if args.tasks:
        t = collect_tasks()
        if args.json:
            print(json.dumps(t, ensure_ascii=False, indent=2))
        else:
            print(render_tasks_text(t))
        return 0

    report = collect()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))

    if args.write_snapshot:
        STATUS_SNAPSHOT.write_text(render_markdown(report), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
