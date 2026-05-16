#!/usr/bin/env python3
"""
check_doc_status.py — Work Mode Step 0 入口校验（v3.1 阶段感知）

1. 读 ~/.claude/projects/project_registry.json，跑 sanity check（漂移 → 阻断输出）
2. 列出每个 active_task 的阶段标记 + 当前阶段必填文档状态
3. 检查 cwd 是否在 watched_paths 下
4. cwd 下 glob HANDOFF.md / SPEC.md → 输出摘要 + 「上次进度」字段
5. 给出"新任务 / 继续老任务"判定建议

阶段标记：
    🟢 discussion / 🔵 implementation / ⚫ archived / ⚪ unknown / 🔴 missing-status
"""

import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 让 stage_lib 可被 import；active 单仓库中脚本统一在 harness/。
REPO_DIR = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_DIR / "harness"))
from stage_lib import detect_stage, sanity_check_registry, sanity_check_task_paths  # noqa: E402

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
REGISTRY_FILE = PROJECTS_DIR / "project_registry.json"

UNFILLED_MARKERS = [
    "（待填写）",
    "[必填]",
    "[YYYY-MM-DD]",
    "[任务名称]",
    "[项目名]",
    "## 使用方式",
    "## 模板",
]

PROGRESS_SECTION_RE = re.compile(
    r"^##\s*.*(进度|下次开始|待办|TODO|下一步|next).*$",
    re.IGNORECASE | re.MULTILINE,
)

STAGE_BADGE = {
    "discussion": "🟢 discussion",
    "implementation": "🔵 implementation",
    "archived": "⚫ archived",
    "unknown": "⚪ unknown",
    "missing-status": "🔴 missing-status",
}


def get_tasks_root(registry: dict) -> Path:
    custom = registry.get("tasks_root")
    if custom:
        return Path(custom)
    return PROJECTS_DIR


def load_registry() -> dict:
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [registry 读取失败] {e}")
        return {}


def check_doc_filled(filepath: Path) -> bool:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    for marker in UNFILLED_MARKERS:
        if marker in content:
            return False
    return True


def fmt_mtime(filepath: Path) -> str:
    try:
        ts = filepath.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return "?"


def normalize(p: str) -> str:
    return p.replace("\\", "/")


def is_in_watched(cwd: str, watched: list) -> bool:
    n = normalize(cwd)
    for w in watched:
        if w in n:
            return True
    return False


def find_project_docs(cwd: Path) -> list:
    candidates = [
        cwd / "HANDOFF.md",
        cwd / "docs" / "HANDOFF.md",
        cwd / "SPEC.md",
        cwd / "docs" / "SPEC.md",
        cwd / "DESIGN.md",
        cwd / "docs" / "DESIGN.md",
    ]
    return [p for p in candidates if p.exists()]


def extract_progress_section(content: str, max_lines: int = 20) -> str:
    m = PROGRESS_SECTION_RE.search(content)
    if not m:
        return ""
    start = m.start()
    after = content[start:]
    lines = after.split("\n")
    out = [lines[0]]
    for line in lines[1: max_lines + 1]:
        if line.startswith("## "):
            break
        out.append(line)
    return "\n".join(out).strip()


def render_task_docs(task: str, task_dir: Path, registry: dict):
    """按阶段渲染单个任务的文档清单。"""
    stage, diag = detect_stage(task_dir, registry)
    badge = STAGE_BADGE.get(stage, stage)
    print(f"  📌 {task}")
    print(f"     阶段: {badge}")
    if diag:
        print(f"     诊断: {diag}")

    if not task_dir.exists():
        print(f"     [任务目录不存在] {task_dir}")
        return

    if stage == "archived":
        print(f"     （已归档，跳过文档检查）")
        return

    if stage == "missing-status":
        # 仍列出已存在的人类文档帮用户定位
        for p in registry.get("human_doc_patterns", []):
            doc = task_dir / p
            mark = "[存在]" if doc.exists() else "[缺失]"
            print(f"     - {p:25s} {mark}")
        return

    # 决定本阶段必填清单
    by_stage = registry.get("required_docs_by_stage", {})
    if stage in by_stage:
        stage_required = by_stage[stage]
    else:
        stage_required = registry.get("required_docs", ["SPEC.md"])

    # 同时显示所有可能涉及的文档（人类文档 + AI 文档 union）
    union = list(stage_required)
    for extra in registry.get("required_docs", []):
        if extra not in union:
            union.append(extra)
    for hp in registry.get("human_doc_patterns", []):
        if hp not in union:
            union.append(hp)

    for doc in union:
        doc_path = task_dir / doc
        is_required = doc in stage_required
        if not doc_path.exists():
            if is_required:
                print(f"     - {doc:25s} [缺失]  ⚠️ doc_gate 会拦截编辑")
            else:
                print(f"     - {doc:25s} [当前阶段不要求]")
        elif not check_doc_filled(doc_path):
            tag = "⚠️" if is_required else "(当前阶段不要求)"
            print(f"     - {doc:25s} [模板未填充] {tag}")
        else:
            tag = "" if is_required else "(当前阶段不要求)"
            print(f"     - {doc:25s} [已填充] mtime: {fmt_mtime(doc_path)} {tag}")


def main():
    print("[文档状态检查]\n")

    registry = load_registry()
    if not registry:
        print("⚠️ project_registry.json 不存在或读取失败")
        print("→ 流程降级：跳过 active_task 校验，仅检查 cwd 项目文档\n")
    else:
        # v3.1 启动期 sanity check
        sanity_diag = sanity_check_registry(registry)
        if sanity_diag:
            print("🔴 registry 配置漂移（doc_gate 将阻断所有受监控编辑）：")
            for line in sanity_diag.split("\n"):
                print(f"   {line}")
            print()

        # v3.2 task_paths 一致性检查
        task_paths_diag = sanity_check_task_paths(registry)
        if task_paths_diag:
            print("🔴 task_paths 配置错误（doc_gate 将阻断所有受监控编辑）：")
            for line in task_paths_diag.split("\n"):
                print(f"   {line}")
            print()

        active_tasks = registry.get("active_tasks", [])
        watched = registry.get("watched_paths", [])
        tasks_root = get_tasks_root(registry)

        print(f"活跃任务（来自 project_registry.json，tasks_root={tasks_root}）：")
        if not active_tasks:
            print("  (无 active_tasks，doc_gate 会拦截 watched_paths 下的所有编辑)\n")
        else:
            for task in active_tasks:
                task_dir = tasks_root / task
                render_task_docs(task, task_dir, registry)
            print()

        cwd = os.getcwd()
        if watched:
            in_watched = is_in_watched(cwd, watched)
            print(f"cwd 监控状态：")
            print(f"  cwd: {cwd}")
            if in_watched:
                print(f"  ✅ 在 watched_paths 内，编辑代码将触发 doc_gate 校验\n")
            else:
                print(f"  ⚪ 不在 watched_paths 内（{watched}），doc_gate 不拦截\n")

    # cwd 项目文档（独立于 registry）
    cwd_path = Path(os.getcwd())
    project_docs = find_project_docs(cwd_path)
    print("cwd 项目文档（自动检测）：")
    has_handoff = False
    progress_text = ""
    if not project_docs:
        print("  (未发现 HANDOFF.md / SPEC.md)\n")
    else:
        for doc in project_docs:
            print(f"  - {doc}  mtime: {fmt_mtime(doc)}")
            if doc.name == "HANDOFF.md":
                has_handoff = True
                try:
                    content = doc.read_text(encoding="utf-8", errors="replace")
                    progress_text = extract_progress_section(content)
                    if progress_text:
                        print("    上次进度章节：")
                        for line in progress_text.split("\n"):
                            print(f"      {line}")
                except Exception as e:
                    print(f"    [读取失败] {e}")
        print()

    print("判定建议：")
    if has_handoff and progress_text:
        print("  - 任务类型：[继续]（HANDOFF 存在 + 包含进度章节）")
        print("  - 推荐动作：先读 HANDOFF.md 完整内容 → 与用户确认上次做到哪 → 再写代码")
    elif has_handoff:
        print("  - 任务类型：[继续?]（HANDOFF 存在但未找到进度章节）")
        print("  - 推荐动作：读 HANDOFF.md 全文 + 询问用户上次进度")
    else:
        print("  - 任务类型：[新任务] 或 [无文档项目]")
        if registry:
            cwd = os.getcwd()
            watched = registry.get("watched_paths", [])
            if watched and is_in_watched(cwd, watched):
                print("  - ⚠️ cwd 在监控范围且无 HANDOFF，建议：先创建 REQUIREMENTS + DESIGN（讨论期）或全套文档（实现期）")
            else:
                print("  - 推荐动作：直接进入 Step 2 输出方案")
        else:
            print("  - 推荐动作：直接进入 Step 2 输出方案")


if __name__ == "__main__":
    main()
