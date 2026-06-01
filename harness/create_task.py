#!/usr/bin/env python3
"""Create or register a work task in the shared Claude/Codex task layout."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CLAUDE_TASKS_ACTIVE  # noqa: E402


CLAUDE_DIR = Path.home() / ".claude"
DEFAULT_REGISTRY = CLAUDE_DIR / "projects" / "project_registry.json"
DEFAULT_DISPLAY_NAMES = CLAUDE_DIR / "projects" / "task_display_names.json"
DEFAULT_CURRENT_TASK = CLAUDE_DIR / ".current_task"
DEFAULT_SESSION_TASKS_DIR = CLAUDE_DIR / ".session_tasks"
DEFAULT_TASKS_ROOT = CLAUDE_TASKS_ACTIVE  # 单一来源：config（env CLAUDE_TASKS_ROOT 驱动）
WORK_CONTEXT_PACK = CLAUDE_DIR / "scripts" / "work_context_pack.py"

REQUIRED_DIRS = ("core", "design", "ops", "test", "_archive")
REQUIRED_FILES = (
    "core/背景.md",
    "core/HANDOFF.md",
    "core/INDEX.md",
    "design/设计文档.md",
    "design/进度.md",
    "ops/CHANGELOG.md",
)


def load_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def task_path_string(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def validate_task_id(task_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,80}", task_id):
        raise SystemExit(
            "task_id must be kebab-case ASCII, for example: codex-work-skill-mvp"
        )


def title_from_task_id(task_id: str) -> str:
    return " ".join(part.capitalize() for part in task_id.split("-"))


def template_files(task_id: str, title: str, summary: str) -> dict[str, str]:
    today = datetime.now().strftime("%Y-%m-%d")
    summary_line = summary or "待补充：任务背景、目标和边界。"
    phase_slug = re.sub(r"[^a-z0-9]+", "-", task_id.lower()).strip("-")[:40] or "phase1"
    return {
        "core/背景.md": f"""# {title} 背景

## 目标

{summary_line}

## 边界

- 优先保持任务可继续执行，而不是一次性写完所有设计细节。
- 新增事实、决策和验证结果必须落到对应文档。

## 当前状态

- 任务创建日期：{today}
- 任务 ID：`{task_id}`
""",
        "core/HANDOFF.md": f"""# {title} Handoff

## 当前目标

{summary_line}

## 已确认事实

- 任务目录采用 v2 结构：`core/`、`design/`、`ops/`、`test/`、`_archive/`。

## 下次开始

1. 读取 `core/STATUS.md` 和本文。
2. 读取 `design/设计文档.md` 和当前 Phase 卡。
3. 继续执行最近的未完成验收项。

## 风险

- 任务刚创建，具体实现细节需要在推进中补齐。
""",
        "core/INDEX.md": f"""# {title} Index

- `core/背景.md`：背景、目标、边界
- `core/HANDOFF.md`：交接状态和下次开始
- `core/STATUS.md`：由 `work_context_pack.py` 生成的状态快照
- `design/设计文档.md`：方案、Phase、验收
- `design/进度.md`：过程记录
- `ops/CHANGELOG.md`：变更记录
- `ops/决策队列.md`：待决策和已关闭决策
- `ops/坑点.md`：任务内坑点
- `test/测试.md`：验证命令和结果
""",
        "design/设计文档.md": f"""# {title} 设计文档

## 需求

{summary_line}

## 方案

先建立最小可继续执行的任务骨架，再按证据逐步细化设计、实现和验证。

## Phase

| Phase | 状态 | 做什么 | 不做会怎样？ | 验收 |
|---|---|---|---|---|
| Phase 1 | pending | 明确任务入口、关键文件和第一轮验证 | 后续上下文会漂移，无法可靠续跑 | `core/HANDOFF.md`、`design/进度.md`、`test/测试.md` 已更新 |

## 验收清单

- [ ] 关键结论已落到对应文档。
- [ ] 验证命令和结果已记录到 `test/测试.md`。
- [ ] `work_context_pack.py` 可识别该任务且 `missing_required_docs=[]`。
""",
        f"design/Phase1-{phase_slug}.md": f"""---
status: pending
---

# Phase 1 - {title}

## 目标

明确任务入口、第一轮行动和验证方式。

## 不做会怎样？

任务会只剩目录骨架，后续接手仍然需要重新判断上下文。

## 验收

- [ ] `core/HANDOFF.md` 写清下次开始。
- [ ] `design/进度.md` 记录执行进展。
- [ ] `test/测试.md` 记录实际验证。

## TDD 记录

代码改动前先把验收转成测试；无法先写测试时，在这里写明原因和替代验证。

| 验收项 | 测试文件/命令 | Red 结果 | Green 结果 | 证据 |
|---|---|---|---|---|
| 待补 | 待补 | 待运行 | 待运行 | 待补 |
""",
        "design/进度.md": f"""# 进度

## {today}

- 创建任务 `{task_id}`。
""",
        "ops/CHANGELOG.md": f"""# Changelog

## {today}

- 创建 v2 任务骨架。
""",
        "ops/决策队列.md": """# 决策队列

## 待决

- [ ] 补充任务的关键边界和验收口径。

## 已关闭

- [x] 使用 v2 任务结构。
""",
        "ops/坑点.md": """# 坑点

- 新任务不要只建目录；必须同步 registry/current task/display name，并跑 context pack。
""",
        "test/测试.md": """# 测试

| 时间 | 命令 | 结果 | 备注 |
|---|---|---|---|
| 待运行 | `work_context_pack.py --task <task-id> --json --write-status` | 待验证 | 创建后补跑 |
""",
        "_archive/.gitkeep": "",
    }


def ensure_registry_shape(registry: dict, tasks_root: Path) -> dict:
    registry.setdefault("active_tasks", [])
    registry.setdefault("task_paths", {})
    registry.setdefault("tasks_root", task_path_string(tasks_root))
    registry.setdefault("task_structure_v2", {})
    registry["task_structure_v2"].setdefault("required_files", list(REQUIRED_FILES))
    return registry


def sync_registry(registry: dict, tasks_root: Path, prune: bool = False) -> dict:
    ensure_registry_shape(registry, tasks_root)
    active_dirs = sorted(
        p.name for p in tasks_root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ) if tasks_root.is_dir() else []
    active = list(registry.get("active_tasks", []))
    for task_id in active_dirs:
        if task_id not in active:
            active.append(task_id)
        paths = registry.setdefault("task_paths", {}).setdefault(task_id, [])
        raw = task_path_string(tasks_root / task_id)
        if raw not in [str(p).rstrip("/") for p in paths]:
            paths.append(raw)
    if prune:
        active = [task_id for task_id in active if task_id in active_dirs]
    registry["active_tasks"] = active
    registry["tasks_root"] = task_path_string(tasks_root)
    return registry


def create_or_adopt_task(task_dir: Path, task_id: str, title: str, summary: str, adopt: bool) -> list[str]:
    created: list[str] = []
    if task_dir.exists() and not adopt:
        raise SystemExit(f"task already exists: {task_dir}. Use --adopt-existing to register it.")
    task_dir.mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_DIRS:
        path = task_dir / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")
    for rel, content in template_files(task_id, title, summary).items():
        if adopt and rel.startswith("design/Phase") and list((task_dir / "design").glob("Phase*.md")):
            continue
        path = task_dir / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(rel)
    return created


def run_context_pack(task_id: str, write_status: bool) -> None:
    if not WORK_CONTEXT_PACK.is_file():
        return
    args = [sys.executable, str(WORK_CONTEXT_PACK), "--task", task_id, "--json"]
    if write_status:
        args.append("--write-status")
    subprocess.run(args, check=False, text=True)


def write_session_task_marker(task_id: str, session_id: str | None = None) -> Path | None:
    """Write current task for this Claude Code session when a session id exists."""
    sid = (session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", "")).strip()
    if not sid:
        return None
    marker = DEFAULT_SESSION_TASKS_DIR / sid
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(task_id, encoding="utf-8")
    return marker


def main() -> int:
    parser = argparse.ArgumentParser(description="create/register a shared Claude/Codex work task")
    parser.add_argument("task_id", nargs="?", help="kebab-case task id")
    parser.add_argument("display_name", nargs="?", help="human display name")
    parser.add_argument("--summary", default="", help="one-line task summary")
    parser.add_argument("--tasks-root", type=Path, help="active tasks root")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--display-names", type=Path, default=DEFAULT_DISPLAY_NAMES)
    parser.add_argument("--current-task", type=Path, default=DEFAULT_CURRENT_TASK)
    parser.add_argument("--adopt-existing", action="store_true", help="register and fill missing files if task dir exists")
    parser.add_argument("--sync-only", action="store_true", help="only sync registry from active task directories")
    parser.add_argument("--prune", action="store_true", help="with --sync-only, remove registry active tasks missing from tasks root")
    parser.add_argument("--no-status", action="store_true", help="do not run context pack to write STATUS.md")
    parser.add_argument("--dry-run", action="store_true", help="show planned changes without writing files")
    args = parser.parse_args()

    registry = load_json(args.registry, {})
    if not isinstance(registry, dict):
        raise SystemExit(f"registry must be a JSON object: {args.registry}")

    configured_root = Path(registry.get("tasks_root") or DEFAULT_TASKS_ROOT)
    tasks_root = args.tasks_root or configured_root

    if args.sync_only:
        registry = sync_registry(registry, tasks_root, prune=args.prune)
        if not args.dry_run:
            write_json(args.registry, registry)
        print(json.dumps({"synced": True, "tasks_root": task_path_string(tasks_root), "active_tasks": len(registry.get("active_tasks", []))}, ensure_ascii=False, indent=2))
        return 0

    if not args.task_id:
        parser.error("task_id is required unless --sync-only is used")
    task_id = args.task_id.strip()
    validate_task_id(task_id)
    display_name = (args.display_name or title_from_task_id(task_id)).strip()
    task_dir = tasks_root / task_id

    registry = sync_registry(registry, tasks_root, prune=False)
    display_names = load_json(args.display_names, {})
    if not isinstance(display_names, dict):
        raise SystemExit(f"display names must be a JSON object: {args.display_names}")

    planned = {
        "task_id": task_id,
        "display_name": display_name,
        "task_dir": task_path_string(task_dir),
        "adopt_existing": args.adopt_existing,
        "write_status": not args.no_status,
    }
    if args.dry_run:
        print(json.dumps(planned, ensure_ascii=False, indent=2))
        return 0

    created = create_or_adopt_task(task_dir, task_id, display_name, args.summary, args.adopt_existing)
    registry = sync_registry(registry, tasks_root, prune=False)
    if task_id not in registry["active_tasks"]:
        registry["active_tasks"].append(task_id)
    paths = registry.setdefault("task_paths", {}).setdefault(task_id, [])
    raw_task_path = task_path_string(task_dir)
    if raw_task_path not in [str(p).rstrip("/") for p in paths]:
        paths.append(raw_task_path)
    display_names[task_id] = display_name

    write_json(args.registry, registry)
    write_json(args.display_names, display_names)
    args.current_task.parent.mkdir(parents=True, exist_ok=True)
    args.current_task.write_text(task_id, encoding="utf-8")
    write_session_task_marker(task_id)

    if not args.no_status:
        run_context_pack(task_id, write_status=True)

    print(json.dumps({**planned, "created": created, "status": "ok"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
