#!/usr/bin/env python3
"""
spec_gate.py — PreToolUse Write|Edit hook (v3.2 一对一拦截)

编辑受监控路径下的文件前，按 task_paths 找出"拥有"该文件的 task，只检查这些
task 的必填文档。无关 task 文档不全不会阻断本次编辑。

task_paths 缺失时退回 v3.1 行为（所有 active_tasks 一起检查）。

阶段感知逻辑见 stage_lib.detect_stage：
- discussion       → 仅检查人类文档（REQUIREMENTS.md / DESIGN.md）
- implementation   → 检查人类文档 + AI 文档（SPEC/HANDOFF）
- archived         → 跳过
- unknown          → 退回旧 required_docs（向后兼容）
- missing-status   → 阻断 + 输出诊断（不静默退回旧规则）

启动期 sanity check 失败也阻断（与 missing-status 同策略，避免 discussion 期任务被卡死）。

配置：~/.claude/projects/project_registry.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _hook_lib import read_hook_input, allow, deny
from stage_lib import get_required_docs, sanity_check_registry, sanity_check_task_paths

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
REGISTRY_FILE = PROJECTS_DIR / "project_registry.json"

HARNESS_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATES_DIR = str(HARNESS_DIR.parent / "templates")


def get_tasks_root(registry: dict) -> Path:
    custom = registry.get("tasks_root")
    if custom:
        return Path(custom)
    return PROJECTS_DIR


def load_registry() -> dict:
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize(path: str) -> str:
    return path.replace("\\", "/")


def is_watched(normalized: str, registry: dict) -> bool:
    for fragment in registry.get("watched_paths", []):
        if fragment in normalized:
            return True
    return False


def tasks_owning_path(normalized: str, registry: dict, all_tasks: list) -> list:
    """返回"拥有"该路径的 task 列表（按 task_paths 片段匹配）。

    规则（v3.2 一对一拦截）：
    - registry 含 task_paths：只返回片段匹配的 task；空列表表示纯文档任务，永不参与代码拦截
    - registry 不含 task_paths：退回旧逻辑，所有 task 都视为相关（向后兼容）
    """
    task_paths = registry.get("task_paths")
    if task_paths is None:
        return list(all_tasks)

    owners = []
    for task in all_tasks:
        fragments = task_paths.get(task, [])
        if not fragments:
            continue
        if any(frag in normalized for frag in fragments):
            owners.append(task)
    return owners


UNFILLED_MARKERS = [
    "（待填写）",
    "[必填]",
    "[YYYY-MM-DD]",
    "[任务名称]",
    "[项目名]",
    "## 使用方式",
    "## 模板",
]


def check_doc_filled(filepath: Path) -> bool:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    for marker in UNFILLED_MARKERS:
        if marker in content:
            return False
    return True


def main():
    data = read_hook_input()
    if not data:
        allow()

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        allow()

    normalized = normalize(file_path)

    if "/.claude/" in normalized:
        allow()

    registry = load_registry()
    if not registry:
        allow()

    if not is_watched(normalized, registry):
        allow()

    sanity_diag = sanity_check_registry(registry)
    if sanity_diag:
        import sys as _sys
        print(f"[doc_gate] WARNING registry sanity: {sanity_diag}", file=_sys.stderr)

    task_paths_diag = sanity_check_task_paths(registry)
    if task_paths_diag:
        import sys as _sys
        print(f"[doc_gate] WARNING task_paths: {task_paths_diag}", file=_sys.stderr)

    active_tasks = registry.get("active_tasks", [])
    if not active_tasks:
        ct = registry.get("current_task")
        active_tasks = [ct] if ct else []

    templates_dir = registry.get("templates_dir", DEFAULT_TEMPLATES_DIR)
    tasks_root = get_tasks_root(registry)

    if not active_tasks:
        deny(
            "没有活跃任务。请先创建任务：\n"
            f"1. mkdir {tasks_root}/<任务名>/\n"
            f"2. 从模板创建人类文档: cp {templates_dir}/REQUIREMENTS.md "
            f"{tasks_root}/<任务名>/REQUIREMENTS.md\n"
            "3. 在 project_registry.json 的 active_tasks 中添加任务名"
        )

    # v3.2: 按 task_paths 过滤，只检查真正"拥有"该文件的 task
    relevant_tasks = tasks_owning_path(normalized, registry, active_tasks)
    if not relevant_tasks:
        # task_paths 已配置但无 task 匹配 → 该文件不归任何 task，放行
        allow()

    tasks_missing = {}
    tasks_unfilled = {}
    tasks_missing_status = {}

    for task in relevant_tasks:
        task_dir = tasks_root / task
        required, diag, stage = get_required_docs(task_dir, registry)

        if stage == "missing-status":
            tasks_missing_status[task] = diag
            continue

        if stage == "archived":
            continue  # 跳过

        missing = []
        unfilled = []
        for doc in required:
            doc_path = task_dir / doc
            if not doc_path.exists():
                missing.append(doc)
            elif not check_doc_filled(doc_path):
                unfilled.append(doc)
        if missing:
            tasks_missing[task] = missing
        if unfilled:
            tasks_unfilled[task] = unfilled

    if not tasks_missing and not tasks_unfilled and not tasks_missing_status:
        allow()

    lines = []
    for task, diag in tasks_missing_status.items():
        lines.append(f"  [{task}] missing-status: {diag}")
    for task, docs in tasks_missing.items():
        lines.append(f"  [{task}] 缺少: {', '.join(docs)}")
    for task, docs in tasks_unfilled.items():
        lines.append(f"  [{task}] 未填充（仍是模板）: {', '.join(docs)}")

    deny(
        "以下活跃任务的文档未就绪：\n"
        + "\n".join(lines)
        + f"\n\n模板位置: {templates_dir}/"
    )


if __name__ == "__main__":
    main()
