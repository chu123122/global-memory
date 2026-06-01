#!/usr/bin/env python3
"""
show_diffs.py — 手动 diff 入口（/diff skill 调用）

按 active_task 隔离的 diff 备份，提供两个无状态子命令供 SKILL 编排：

    python show_diffs.py --list [<task>]
        扫每个目标 task 的 <task>/.diff/now/_paths.json，输出 JSON 一行：
            {"items":[{"idx":1,"task":"...","bak":"...","orig":"..."}, ...]}
        idx 从 1 开始全局递增（跨 task）。空时输出 {"items":[]}。
        不开 GUI，不动文件。退出码 0。

    python show_diffs.py --open <task> <bak_name> <ts>
        1. 校验 <task>/.diff/now/<bak_name> 存在
        2. 查 _paths.json[bak_name] 拿 original_path
        3. Popen([Code.exe, "--diff", bak, original]) 异步弹 VS Code
        4. 把 bak mv 到 <task>/.diff/history/<ts>/<bak_name>
        5. 从 now/_paths.json 删该条目
        6. 把该 (bak,orig) 条目追加到 history/<ts>/_paths.json
        退出码 0 = 成功 / bak 已不存在；1 = Code.exe 找不到 / original 缺失

设计参见 $env:CLAUDE_TASKS_ACTIVE/diff-workflow-redesign/{REQUIREMENTS,DESIGN,SPEC}.md
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# 复用 hooks/_task_resolver
sys.path.insert(0, str(Path(__file__).parent / "hooks"))
from _task_resolver import load_registry  # noqa: E402


def find_code_exe() -> Optional[str]:
    """code.cmd → parent.parent / Code.exe；找不到返回 None。"""
    code_cmd = shutil.which("code")
    if not code_cmd:
        return None
    if code_cmd.lower().endswith(".cmd"):
        candidate = Path(code_cmd).parent.parent / "Code.exe"
        if candidate.exists():
            return str(candidate)
    elif code_cmd.lower().endswith(".exe"):
        return code_cmd
    return None


def resolve_task_arg(arg: Optional[str], registry: dict) -> List[str]:
    """
    无参 / "all" → active_tasks 全集
    单 task → 精确 / 前缀模糊匹配
    歧义 / 无匹配 → 空列表 + stderr 提示
    """
    active_tasks = registry.get("active_tasks", []) or []
    if not arg or arg.lower() == "all":
        return active_tasks
    if arg in active_tasks:
        return [arg]
    matches = [t for t in active_tasks if t.startswith(arg)]
    if len(matches) == 1:
        return matches
    if len(matches) > 1:
        print(f"[diff] ambiguous task prefix '{arg}': {matches}", file=sys.stderr)
        return []
    print(f"[diff] no task matched '{arg}'. Active tasks: {active_tasks}", file=sys.stderr)
    return []


def cmd_list(target_tasks: List[str], tasks_root: Path) -> int:
    """扫每个 task 的 _paths.json，输出 JSON 一行。"""
    items = []
    idx = 1
    for task in target_tasks:
        pmap = tasks_root / task / ".diff" / "now" / "_paths.json"
        if not pmap.exists():
            continue
        try:
            paths = json.loads(pmap.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[diff] task={task} _paths.json parse failed: {e}", file=sys.stderr)
            continue
        for bak_name, orig_path in paths.items():
            bak = tasks_root / task / ".diff" / "now" / bak_name
            if not bak.exists():
                continue
            items.append({
                "idx": idx,
                "task": task,
                "bak": bak_name,
                "orig": orig_path,
            })
            idx += 1
    print(json.dumps({"items": items}, ensure_ascii=False))
    return 0


def cmd_open(task: str, bak_name: str, ts: str, tasks_root: Path) -> int:
    """开单个 diff + 文件级归档到 history/<ts>/。"""
    now_dir = tasks_root / task / ".diff" / "now"
    bak = now_dir / bak_name
    if not bak.exists():
        # 已被另一个 session 处理过，幂等静默
        return 0

    pmap_path = now_dir / "_paths.json"
    if not pmap_path.exists():
        print(f"[diff] open failed: {pmap_path} missing", file=sys.stderr)
        return 1
    try:
        paths = json.loads(pmap_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[diff] open failed: _paths.json parse: {e}", file=sys.stderr)
        return 1

    orig_path = paths.get(bak_name)
    if not orig_path:
        print(f"[diff] open failed: no _paths.json entry for {bak_name}", file=sys.stderr)
        return 1
    if not Path(orig_path).exists():
        print(f"[diff] open failed: original missing {orig_path}", file=sys.stderr)
        return 1

    code_exe = find_code_exe()
    if not code_exe:
        print(
            "[diff] open failed: Code.exe not found via 'code' CLI. "
            "Check that VS Code 'code' is in PATH.",
            file=sys.stderr,
        )
        return 1

    try:
        subprocess.Popen(
            [code_exe, "--diff", str(bak), orig_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except Exception as e:
        print(f"[diff] open failed: Popen: {e}", file=sys.stderr)
        return 1

    # 文件级归档：bak + _paths.json 条目都搬到 history/<ts>/
    history_dir = tasks_root / task / ".diff" / "history" / ts
    history_dir.mkdir(parents=True, exist_ok=True)

    # bak 文件名冲突时加 -1/-2 后缀
    target_bak = history_dir / bak_name
    suffix = 0
    while target_bak.exists():
        suffix += 1
        target_bak = history_dir / f"{bak_name}-{suffix}"

    try:
        shutil.move(str(bak), str(target_bak))
    except Exception as e:
        print(f"[diff] open: archive bak failed (VS Code 已开): {e}", file=sys.stderr)
        return 1

    # 写 history/<ts>/_paths.json（追加模式）
    hist_pmap = history_dir / "_paths.json"
    hist_data = {}
    if hist_pmap.exists():
        try:
            hist_data = json.loads(hist_pmap.read_text(encoding="utf-8"))
        except Exception:
            hist_data = {}
    hist_data[target_bak.name] = orig_path
    hist_pmap.write_text(
        json.dumps(hist_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 从 now/_paths.json 删条目（写回；空 dict 也保留文件，下次 Edit 复用）
    paths.pop(bak_name, None)
    pmap_path.write_text(
        json.dumps(paths, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("[diff] usage: --list [<task>] | --open <task> <bak> <ts>", file=sys.stderr)
        return 1

    registry = load_registry()
    if not registry:
        print("[diff] failed to load project_registry.json", file=sys.stderr)
        return 1

    tasks_root_raw = registry.get("tasks_root", "")
    tasks_root = Path(tasks_root_raw) if tasks_root_raw else Path.home() / ".claude" / "projects"

    sub = args[0]
    if sub == "--list":
        task_arg = args[1] if len(args) >= 2 else None
        targets = resolve_task_arg(task_arg, registry)
        if not targets:
            return 1
        return cmd_list(targets, tasks_root)

    if sub == "--open":
        if len(args) < 4:
            print("[diff] --open requires <task> <bak_name> <ts>", file=sys.stderr)
            return 1
        return cmd_open(args[1], args[2], args[3], tasks_root)

    print(f"[diff] unknown subcommand '{sub}'. Use --list or --open.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
