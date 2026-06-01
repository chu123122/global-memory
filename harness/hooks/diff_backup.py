#!/usr/bin/env python3
"""
diff_backup.py — PreToolUse(Write|Edit) hook v2

按 active_task 隔离备份原文件到 <task>/.diff/now/。
归属解析委托给 _task_resolver.resolve_task_owner（单一权威 = task_paths）。

v2 与 v1 的关键差异：
- 删除 WHITELIST + in_whitelist（D-9：单一权威 = task_paths）
- 备份位置从全局任务根 .diff_backup/ 改为按 task 隔离
- 备份失败 print 到 stderr（之前是静默 pass，定位困难）

设计参见 $env:CLAUDE_TASKS_ACTIVE/diff-workflow-redesign/{DESIGN,SPEC}.md
"""

import sys
import json
import hashlib
import shutil
from pathlib import Path

# 复用项目 hook 共享库
sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, allow
from _task_resolver import load_registry, resolve_task_owner


def backup_path_for_task(file_path: str, task: str, tasks_root: Path) -> Path:
    """返回 <tasks_root>/<task>/.diff/now/<basename>.<sha8(file_path)>.bak"""
    h = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:8]
    name = Path(file_path).name
    return tasks_root / task / ".diff" / "now" / f"{name}.{h}.bak"


def update_paths_map(now_dir: Path, bak_name: str, original_path: str):
    """读 now_dir/_paths.json，设 data[bak_name] = original_path，写回。"""
    pmap = now_dir / "_paths.json"
    data = {}
    if pmap.exists():
        try:
            data = json.loads(pmap.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[bak_name] = original_path
    pmap.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    data = read_hook_input()
    file_path = data.get("tool_input", {}).get("file_path", "")

    if not file_path:
        allow()
    if not Path(file_path).exists():
        allow()  # 新建文件无原内容可备份

    registry = load_registry()
    if not registry:
        allow()  # registry 缺失/解析失败 → 跳过备份（与 D-3 一致）

    task = resolve_task_owner(file_path, registry)
    if not task:
        allow()  # 不归属任何 active_task → 跳过

    tasks_root_raw = registry.get("tasks_root", "")
    tasks_root = (
        Path(tasks_root_raw)
        if tasks_root_raw
        else Path.home() / ".claude" / "projects"
    )

    try:
        bak = backup_path_for_task(file_path, task, tasks_root)
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, bak)
        update_paths_map(bak.parent, bak.name, file_path)
        print(f"[diff_backup] ✓ {bak.name}", file=sys.stderr)
    except Exception as e:
        # 备份失败打印 stderr（audit_logger 可抓），不阻塞 Edit
        print(f"[diff_backup] backup failed for {file_path}: {e}", file=sys.stderr)

    allow()


if __name__ == "__main__":
    main()
