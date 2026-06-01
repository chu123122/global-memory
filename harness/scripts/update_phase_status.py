#!/usr/bin/env python
"""update_phase_status.py — 一键三同步 Phase 状态。

复盘踩坑：每 Phase done 要改 3 处：
  ① design/设计文档.md 「Phase 拆分」表对应行 status
  ② design/设计文档.md 「验收」清单对应 [ ] → [x]
  ③ design/Phase<N>-*.md frontmatter status

漏改一处 → STATUS.md 抓到不一致。

用法：
  python update_phase_status.py <task_dir> <N> <new_status>
  python update_phase_status.py harness-governance-followup 1 done

  task_dir 可为：
    - 完整路径 $env:CLAUDE_TASKS_ACTIVE/<task>
    - 任务 id（自动拼到 $env:CLAUDE_TASKS_ACTIVE/<id>）
    - "."（当前目录）

  new_status: pending | in_progress | done | blocked

退出码：
  0 = 全部更新成功
  1 = 部分或全部失败（详情打印到 stderr）
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib import record_tool_invocation  # noqa: E402

VALID_STATUS = {"pending", "in_progress", "done", "blocked"}
DEFAULT_TASKS_ACTIVE = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(Path.home() / ".claude" / "tasks" / "active")))


def resolve_task_dir(arg: str) -> Path:
    """task 参数解析：路径 / id / `.`"""
    if arg == ".":
        return Path.cwd().resolve()
    p = Path(arg)
    if p.is_absolute() and p.exists():
        return p.resolve()
    # 视为 task id
    candidate = DEFAULT_TASKS_ACTIVE / arg
    if candidate.exists():
        return candidate.resolve()
    return p.resolve()


def find_phase_card(design_dir: Path, n: int) -> Path | None:
    matches = sorted(design_dir.glob(f"Phase{n}-*.md"))
    return matches[0] if matches else None


def update_phase_card(card: Path, new_status: str) -> bool:
    """改 frontmatter status 字段。返回是否真改了。"""
    content = card.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n)(.*?\n)(---\s*\n)", content, re.DOTALL)
    if not m:
        print(f"  [card] no frontmatter: {card.name}", file=sys.stderr)
        return False
    fm = m.group(2)
    new_fm, count = re.subn(
        r"^(status:\s*)\S+", lambda mm: f"{mm.group(1)}{new_status}",
        fm, count=1, flags=re.MULTILINE,
    )
    if count == 0:
        # 无 status 字段则追加
        new_fm = fm.rstrip() + f"\nstatus: {new_status}\n"
    if new_fm == fm:
        return True  # already at target
    new_content = m.group(1) + new_fm + m.group(3) + content[m.end():]
    card.write_text(new_content, encoding="utf-8")
    return True


def update_design_table(design_doc: Path, n: int, new_status: str) -> bool:
    """改「Phase 拆分」表第 N 行末列 status。"""
    if not design_doc.exists():
        print(f"  [table] design doc missing: {design_doc}", file=sys.stderr)
        return False
    lines = design_doc.read_text(encoding="utf-8").splitlines()
    hit = False
    for i, line in enumerate(lines):
        # 匹配以 | <N> | 开头的表行（前后可含空格）
        if re.match(rf"^\|\s*{n}\s*\|", line):
            cells = [c for c in line.split("|")]
            # 末列前是状态列（去掉末尾空 cell）
            # 形如 |  | a | b | c | status |  → cells = ['', '  ', ' a ', ' b ', ' c ', ' status ', '']
            if len(cells) >= 3:
                cells[-2] = f" {new_status} "
                lines[i] = "|".join(cells)
                hit = True
                break
    if not hit:
        print(f"  [table] no Phase {n} row in design doc", file=sys.stderr)
        return False
    design_doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def update_acceptance_list(design_doc: Path, n: int, new_status: str) -> bool:
    """改「验收」清单 P<N> 行 [ ] ↔ [x]。"""
    if not design_doc.exists():
        return False
    content = design_doc.read_text(encoding="utf-8")
    box = "[x]" if new_status == "done" else "[ ]"
    pattern = re.compile(rf"^(- )\[[ x]\](\s*P{n}[：:\s])", re.MULTILINE)
    new_content, count = pattern.subn(rf"\g<1>{box}\g<2>", content, count=1)
    if count == 0:
        print(f"  [accept] no `- [ ] P{n}` line found", file=sys.stderr)
        return False
    if new_content != content:
        design_doc.write_text(new_content, encoding="utf-8")
    return True


def main() -> int:
    record_tool_invocation("update_phase_status.py")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task", help="task id / path / .")
    ap.add_argument("n", type=int, help="Phase number")
    ap.add_argument("status", choices=sorted(VALID_STATUS))
    args = ap.parse_args()

    task_dir = resolve_task_dir(args.task)
    design_dir = task_dir / "design"
    if not design_dir.is_dir():
        print(f"ERROR: design/ not under {task_dir}", file=sys.stderr)
        return 1
    design_doc = design_dir / "设计文档.md"
    card = find_phase_card(design_dir, args.n)
    if card is None:
        print(f"ERROR: no Phase{args.n}-*.md under {design_dir}", file=sys.stderr)
        return 1

    print(f"task: {task_dir.name}")
    print(f"phase: {args.n} → {args.status}")
    print(f"card: {card.name}")

    ok_card = update_phase_card(card, args.status)
    ok_table = update_design_table(design_doc, args.n, args.status)
    ok_accept = update_acceptance_list(design_doc, args.n, args.status)

    results = [
        ("phase card frontmatter", ok_card),
        ("design table row", ok_table),
        ("acceptance list", ok_accept),
    ]
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
