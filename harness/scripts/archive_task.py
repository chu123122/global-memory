#!/usr/bin/env python
"""archive_task.py — 三模式归档辅助 (P8)

D8 / D10：
  - 只产候选不自动写 global-memory（--extract 输出 _archive/extract_candidates.md）
  - 物理归档不自动触发（--commit 显式 + 默认要 --yes）

模式：
  --check <task_dir>     扫 design/Phase*.md frontmatter status + 设计文档 Phase 表 + 验收清单；
                          三者一致完成 → ready_to_archive=true
  --extract <task_dir>   扫 HANDOFF.md / 复盘.md / 坑点.md 抽 fixes/knowledge 候选；
                          同时 lint 复盘.md（P6 5 护栏 self_check 锚 + 引用计数 + 自检节）
  --commit <task_dir>    物理归档 active/<task> → archived/<task>；
                          删 display_names 条目；追加全局 CHANGELOG；
                          仅在 --check PASS 后允许；必须带 --yes

用法：
  python archive_task.py --check harness-governance-followup
  python archive_task.py --extract harness-governance-followup
  python archive_task.py --commit  harness-governance-followup --yes

退出码：
  0 = 成功（check: ready；extract: 输出 candidates；commit: 已移动）
  1 = 未通过 / 错误
  2 = lint FAIL（仅 extract 模式）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib import record_tool_invocation, CHANGELOG_MD  # noqa: E402
from config import CLAUDE_TASKS_ROOT, CLAUDE_TASKS_ACTIVE, CLAUDE_TASKS_ARCHIVED  # noqa: E402


DEFAULT_TASKS_ROOT = CLAUDE_TASKS_ROOT
ACTIVE_ROOT = CLAUDE_TASKS_ACTIVE
ARCHIVED_ROOT = CLAUDE_TASKS_ARCHIVED
DISPLAY_NAMES = Path.home() / ".claude" / "projects" / "task_display_names.json"
SELF_CHECK_RE = re.compile(
    r"^self_check:\s*rails=\{\s*1\s*,\s*2\s*,\s*3\s*,\s*4\s*,\s*5\s*\}\s+reasoned=(true|false)",
    re.MULTILINE,
)
FILE_LINE_RE = re.compile(r"\b[\w\-./]+\.(py|md|yaml|yml|json|cpp|h|hpp|ts|tsx|js)(:\d+)?\b")
SELF_CHECK_SECTION_RE = re.compile(r"(下次可能踩|不打算修)")


def resolve_task_dir(arg: str) -> Path:
    if arg == ".":
        return Path.cwd().resolve()
    p = Path(arg)
    if p.is_absolute() and p.exists():
        return p.resolve()
    candidate = ACTIVE_ROOT / arg
    if candidate.exists():
        return candidate.resolve()
    return p.resolve()


def parse_frontmatter(text: str) -> dict:
    """轻量 frontmatter 解析（k: v 行）。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    out: dict = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$", line)
        if mm:
            out[mm.group(1)] = mm.group(2)
    return out


# ─────────── --check ───────────

def phase_number_from_name(path: Path) -> str | None:
    m = re.match(r"Phase(\d+)", path.name)
    return m.group(1) if m else None


def design_phase_statuses(design_doc: Path) -> dict[str, str]:
    """Read simple Phase table rows from design/设计文档.md.

    Supports both template shapes:
      | Phase 1 | done | ... |
      | 1 | ... | done |
    """
    if not design_doc.exists():
        return {}
    statuses: dict[str, str] = {}
    status_index: int | None = None
    in_phase_section = False
    for line in design_doc.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip().lower()
            in_phase_section = "phase" in heading
            status_index = None
            continue
        if not in_phase_section:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        normalized = [c.lower() for c in cells]
        if "状态" in cells:
            status_index = cells.index("状态")
            continue
        if "status" in normalized:
            status_index = normalized.index("status")
            continue
        m = re.match(r"Phase\s+(\d+)$", cells[0], re.IGNORECASE)
        if m:
            idx = status_index if status_index is not None and status_index < len(cells) else 1
            statuses[m.group(1)] = cells[idx].lower()
            continue
        if cells[0].isdigit():
            if status_index is not None and status_index < len(cells):
                statuses[cells[0]] = cells[status_index].lower()
                continue
            for cell in reversed(cells[1:]):
                lower = cell.lower()
                if lower in {"pending", "in_progress", "implementing", "done", "blocked", "deferred", "dropped"}:
                    statuses[cells[0]] = lower
                    break
    return statuses


def unchecked_acceptance_items(design_doc: Path) -> list[str]:
    if not design_doc.exists():
        return []
    return [
        line.strip()
        for line in design_doc.read_text(encoding="utf-8", errors="replace").splitlines()
        if re.match(r"^-\s*\[\s\]", line)
    ]


def is_done_status(status: str) -> bool:
    return status.strip().lower().startswith("done")


def cmd_check(task_dir: Path) -> int:
    design = task_dir / "design"
    if not design.is_dir():
        print(f"ERROR: {task_dir}/design not a directory", file=sys.stderr)
        return 1
    design_doc = design / "设计文档.md"
    cards = sorted(design.glob("Phase*.md"))
    if not cards:
        print(f"ERROR: no Phase*.md under {design}", file=sys.stderr)
        return 1
    pending = []
    done_count = 0
    table_statuses = design_phase_statuses(design_doc)
    for c in cards:
        meta = parse_frontmatter(c.read_text(encoding="utf-8", errors="replace"))
        status = (meta.get("status") or "").strip().lower()
        if is_done_status(status):
            done_count += 1
        else:
            pending.append((c.name, status or "<missing>"))
        n = phase_number_from_name(c)
        table_status = table_statuses.get(n or "")
        if table_status and not is_done_status(table_status):
            pending.append((f"design/设计文档.md Phase {n}", table_status))
    unchecked = unchecked_acceptance_items(design_doc)
    print(f"task: {task_dir.name}")
    print(f"phases: {done_count}/{len(cards)} done")
    if unchecked:
        print(f"unchecked_acceptance: {len(unchecked)}")
    if pending:
        print("ready_to_archive: false")
        for name, st in pending:
            print(f"  ❌ {name} status={st}")
    if unchecked:
        if not pending:
            print("ready_to_archive: false")
        for item in unchecked:
            print(f"  ❌ unchecked acceptance: {item}")
    if pending or unchecked:
        return 1
    print("ready_to_archive: true")
    return 0


# ─────────── --extract ───────────

def lint_retro(retro: Path) -> tuple[bool, list[str]]:
    """复盘.md 5 护栏 lint。返回 (ok, errors)。

    检查：
      1) self_check 锚行 `self_check: rails={...} reasoned=true`
      2) 自检节：「下次可能踩」+「不打算修」二者至少出现（关键词命中）
      3) 引用密度：≥1 file:line 或 file.ext 引用（否则视为空话）
    """
    if not retro.exists():
        return False, ["复盘.md 不存在（P6 5 护栏要求归档前产出）"]
    text = retro.read_text(encoding="utf-8", errors="replace")
    if "本任务无重大踩点" in text or "跳过复盘" in text:
        # 5 护栏「跳过权」：合法终结
        return True, []
    errors: list[str] = []
    m = SELF_CHECK_RE.search(text)
    if not m:
        errors.append("缺 self_check 锚行：`self_check: rails={1,2,3,4,5}  reasoned=true`")
    elif m.group(1) != "true":
        errors.append("self_check 锚 reasoned=false（AI 自承认未充分推理）")
    sect_hits = SELF_CHECK_SECTION_RE.findall(text)
    if len(set(sect_hits)) < 2:
        errors.append("自检节缺失：必须同时含「下次可能踩」+「不打算修」（护栏 5）")
    refs = FILE_LINE_RE.findall(text)
    if len(refs) < 1:
        errors.append("引用密度=0：无任何 file.ext 或 file.ext:line 引用（护栏 3）")
    return (len(errors) == 0), errors


def extract_section_blocks(md_text: str) -> list[tuple[str, str]]:
    """按 ## 标题切块，返回 [(heading, body)]。"""
    blocks: list[tuple[str, str]] = []
    cur_h = ""
    cur_body: list[str] = []
    for line in md_text.splitlines():
        if line.startswith("## "):
            if cur_h or cur_body:
                blocks.append((cur_h, "\n".join(cur_body).strip()))
            cur_h = line[3:].strip()
            cur_body = []
        else:
            cur_body.append(line)
    if cur_h or cur_body:
        blocks.append((cur_h, "\n".join(cur_body).strip()))
    return blocks


def classify_candidate(heading: str, body: str) -> str | None:
    """关键词分类：返回 fixes/knowledge/decisions/feedback 或 None（跳过）。"""
    h = heading.lower()
    b = body.lower()
    text = f"{h} {b}"
    if any(k in text for k in ("踩坑", "bug", "fix", "崩", "error", "崩溃", "失败")):
        return "fixes"
    if any(k in text for k in ("决策", "选型", "权衡", "trade-off", "trade off")):
        return "decisions"
    if any(k in text for k in ("风格", "约定", "习惯", "feedback", "纠正")):
        return "feedback"
    if any(k in text for k in ("知识", "原理", "机制", "理解", "结论", "经验")):
        return "knowledge"
    return None


def cmd_extract(task_dir: Path) -> int:
    handoff = task_dir / "core" / "HANDOFF.md"
    retro = task_dir / "core" / "复盘.md"
    pitfalls = task_dir / "ops" / "坑点.md"
    archive_dir = task_dir / "_archive"
    archive_dir.mkdir(exist_ok=True)
    out_path = archive_dir / "extract_candidates.md"

    # lint 复盘.md（gating extract 产出）
    ok, retro_errors = lint_retro(retro)
    print(f"task: {task_dir.name}")
    print(f"retro lint: {'PASS' if ok else 'FAIL'}")
    for e in retro_errors:
        print(f"  ❌ {e}")
    if not ok:
        print("extract 拒绝产出：先修复复盘.md 5 护栏 lint", file=sys.stderr)
        return 2

    candidates: list[dict] = []
    for src, src_name in [(handoff, "HANDOFF.md"), (retro, "复盘.md"), (pitfalls, "ops/坑点.md")]:
        if not src or not src.exists():
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        for heading, body in extract_section_blocks(text):
            if not body.strip():
                continue
            cat = classify_candidate(heading, body)
            if cat is None:
                continue
            refs = FILE_LINE_RE.findall(body)
            candidates.append({
                "source": src_name,
                "category": cat,
                "heading": heading,
                "body_excerpt": body[:240].replace("\n", " "),
                "ref_count": len(refs),
            })

    # 产物
    lines = [
        "# 抽取候选 · " + task_dir.name,
        "",
        f"> 自动产出 {datetime.now().strftime('%Y-%m-%d %H:%M')}（archive_task.py --extract）",
        f"> 共 {len(candidates)} 条候选；**人工判定是否入库**（D8：不自动写 global-memory）",
        "",
        "| # | source | category | heading | refs | excerpt |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(candidates, 1):
        excerpt = c["body_excerpt"].replace("|", "\\|")
        lines.append(f"| {i} | {c['source']} | {c['category']} | {c['heading']} | {c['ref_count']} | {excerpt} |")
    if not candidates:
        lines.append("| — | — | — | （无候选；HANDOFF/复盘/坑点 未匹配分类关键词） | — | — |")
    lines += [
        "",
        "## 人工处置建议",
        "",
        "- **fixes/** ← 踩坑现场（必含错误消息 + 复现路径）",
        "- **knowledge/** ← 跨任务可复用结论",
        "- **decisions/** ← 架构/选型决策（含弃用替代方案）",
        "- **feedback/** ← 行为/风格纠正",
        "- 跳过：纯任务流水、临时状态、不打算修的（护栏 5 自检节内容）",
        "",
        "## 关联",
        "- P6 5 护栏（lint 来源）：`docs/task-lifecycle.md` § 4",
        "- D8（不自动写）：`design/设计文档.md`",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"candidates: {len(candidates)}")
    print(f"output: {out_path}")
    return 0


# ─────────── --commit ───────────

def cmd_commit(task_dir: Path, yes: bool, reason: str) -> int:
    if not yes:
        print("ERROR: --commit 必须带 --yes（D10 不可逆操作不自动化）", file=sys.stderr)
        return 1
    # check 必须 PASS
    rc = cmd_check(task_dir)
    if rc != 0:
        print("ERROR: --check 未通过，refuse to commit", file=sys.stderr)
        return 1
    # 物理归档前的元数据
    name = task_dir.name
    dest = archive_destination(task_dir)
    if dest.exists():
        print(f"ERROR: {dest} already exists, abort", file=sys.stderr)
        return 1
    ARCHIVED_ROOT.mkdir(parents=True, exist_ok=True)

    # display_names 处置（D10 安全：保留映射，不删；与 task-lifecycle.md § 4 一致）
    # 仅当用户显式 --drop-display 才删，此处不实现，保守留映射

    # 移动
    shutil.move(str(task_dir), str(dest))
    print(f"moved: {task_dir} → {dest}")

    # 全局 CHANGELOG 追加
    today = datetime.now().strftime("%Y-%m-%d")
    entry = (
        f"\n### [{today}] [ARCHIVE] {name} 归档\n"
        f"- **来源任务**：{dest}\n"
        f"- **归档原因**：{reason}\n"
        f"- **物理位置**：active → archived\n"
        f"- **抽取候选**：见 `{dest}/_archive/extract_candidates.md`（人工判定入库）\n"
    )
    try:
        CHANGELOG_MD.write_text(
            CHANGELOG_MD.read_text(encoding="utf-8").replace(
                "---\n", "---\n" + entry, 1
            ),
            encoding="utf-8",
        )
        print(f"changelog: appended to {CHANGELOG_MD}")
    except Exception as e:
        print(f"WARN: 全局 CHANGELOG 追加失败：{e}", file=sys.stderr)
    return 0


def archive_destination(task_dir: Path) -> Path:
    """Return the archive target for a task.

    Absolute active task paths should archive to their sibling `../archived`
    directory even when shell env vars are not populated. This prevents an
    explicit active task path from being moved to another configured fallback.
    """
    if task_dir.parent.name.lower() == "active":
        return task_dir.parent.parent / "archived" / task_dir.name
    return ARCHIVED_ROOT / task_dir.name


def main() -> int:
    record_tool_invocation("archive_task.py")
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--extract", action="store_true")
    mode.add_argument("--commit", action="store_true")
    ap.add_argument("task", help="task id / path / .")
    ap.add_argument("--yes", action="store_true", help="--commit 必须")
    ap.add_argument("--reason", default="完成", help="--commit 时写入全局 CHANGELOG")
    args = ap.parse_args()

    task_dir = resolve_task_dir(args.task)
    if not task_dir.is_dir():
        print(f"ERROR: {task_dir} not a directory", file=sys.stderr)
        return 1

    if args.check:
        return cmd_check(task_dir)
    if args.extract:
        return cmd_extract(task_dir)
    if args.commit:
        return cmd_commit(task_dir, args.yes, args.reason)
    return 1


if __name__ == "__main__":
    sys.exit(main())
