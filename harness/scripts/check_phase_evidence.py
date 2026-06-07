#!/usr/bin/env python
"""check_phase_evidence.py — 机械强制 work「② 验收契约 + done 打回」规则。

规则（来自 work 四契约模板）：
  Phase 卡 frontmatter `status: done` 时，其「## 验收契约（验收项 ↔ 验证方式
  ↔ 证据，1:1）」表的**每一数据行**，Green 列与 证据指针 列都必须非空。
  任一为空 = 「done 缺证据」，应被打回。

边界：
  - 仅检查 `status: done` 的卡；pending / implementing 跳过（还没到要证据的时候）。
  - 无「验收契约」标题的 done 老卡（旧格式：验收清单 + TDD 记录）→ 跳过 + 一行提示，
    不误报（新规则不追溯旧卡）。
  - 硬化：有「验收契约」标题却定位不到 Green/证据指针列（或标题在但无表）→ 判 fail，
    不静默跳过（silence is not success）。

用法：
  python check_phase_evidence.py                      # 扫 $CLAUDE_TASKS_ACTIVE 下所有任务
  python check_phase_evidence.py --task <task-id>     # 单任务（id）
  python check_phase_evidence.py --task <绝对路径>     # 单任务（任务目录绝对路径）

退出码：
  0 = 全部通过（含「全部跳过」）
  1 = 至少一行 done 缺证据
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CLAUDE_TASKS_ACTIVE  # noqa: E402
from _lib import record_tool_invocation  # noqa: E402

# 「验收契约」表的标题锚点（容忍标点 / 空格差异，只认前缀「验收契约」）
CONTRACT_HEADING_RE = re.compile(r"^#{1,6}\s*验收契约")
# 表内列名：验收项 | 验证方式 | Red | Green | 证据指针
COL_GREEN = "Green"
COL_EVIDENCE = "证据指针"


def resolve_task_dirs(arg: str | None) -> list[Path]:
    """--task 解析：路径 / id / 缺省（扫 active 下所有任务）。"""
    if arg is None:
        if not CLAUDE_TASKS_ACTIVE.is_dir():
            return []
        return sorted(p for p in CLAUDE_TASKS_ACTIVE.iterdir() if p.is_dir())
    p = Path(arg)
    if p.is_absolute() and p.exists():
        return [p.resolve()]
    candidate = CLAUDE_TASKS_ACTIVE / arg
    if candidate.exists():
        return [candidate.resolve()]
    return [p.resolve()]


def read_status(card: Path) -> str | None:
    """读 frontmatter 的 status 字段。无 frontmatter / 无字段 → None。"""
    try:
        content = card.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("status:"):
            val = line[len("status:"):].strip()
            if val and val[0] in ('"', "'") and len(val) > 1 and val[-1] == val[0]:
                val = val[1:-1]
            return val or None
    return None


def _split_row(line: str) -> list[str]:
    """切分 markdown 表行为单元格列表（去掉首尾边框空 cell）。"""
    cells = line.split("|")
    # 形如 `| a | b |` → ['', ' a ', ' b ', '']；去首尾空 cell
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _is_separator_row(cells: list[str]) -> bool:
    """判定是否为表头分隔行（形如 ---|---|---）。"""
    if not cells:
        return False
    return all(re.fullmatch(r":?-{1,}:?", c) for c in cells if c != "")


def find_contract_table(content: str) -> tuple[bool, list[str]]:
    """定位「验收契约」表。返回 (是否存在验收契约标题, 表行含表头)。"""
    lines = content.splitlines()
    in_section = False
    heading_present = False
    table: list[str] = []
    for line in lines:
        if CONTRACT_HEADING_RE.match(line):
            in_section = True
            heading_present = True
            continue
        if in_section:
            # 遇到下一个标题 → 区段结束
            if re.match(r"^#{1,6}\s", line):
                break
            if line.lstrip().startswith("|"):
                table.append(line)
            elif table:
                # 表已开始又遇到非表行 → 表结束
                break
    return heading_present, table


def check_contract_table(table: list[str]) -> list[dict]:
    """逐数据行查 Green / 证据指针 非空。返回违规行列表。

    每个违规 dict: {item, missing: [列名...]}。
    """
    if not table:
        return []
    header = _split_row(table[0])
    # 列定位（容忍大小写 / 周边空白）
    try:
        idx_green = next(i for i, h in enumerate(header) if h == COL_GREEN)
    except StopIteration:
        idx_green = None
    try:
        idx_evidence = next(i for i, h in enumerate(header) if h == COL_EVIDENCE)
    except StopIteration:
        idx_evidence = None
    idx_item = 0  # 验收项恒为第一列

    # 硬化：表头定位不到 Green / 证据指针 = 无法校验 → 判 fail（silence is not success）
    header_missing: list[str] = []
    if idx_green is None:
        header_missing.append(COL_GREEN)
    if idx_evidence is None:
        header_missing.append(COL_EVIDENCE)
    if header_missing:
        return [{"item": "(表头不规范)",
                 "missing": [f"列定位失败:{'+'.join(header_missing)}（验收契约表头须含 Green 与 证据指针）"]}]

    violations: list[dict] = []
    for line in table[1:]:
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        if not any(cells):  # 空行
            continue
        item = cells[idx_item] if len(cells) > idx_item else ""
        missing: list[str] = []
        if idx_green is not None:
            green = cells[idx_green] if len(cells) > idx_green else ""
            if not green.strip():
                missing.append(COL_GREEN)
        if idx_evidence is not None:
            ev = cells[idx_evidence] if len(cells) > idx_evidence else ""
            if not ev.strip():
                missing.append(COL_EVIDENCE)
        if missing:
            violations.append({"item": item or "(空验收项)", "missing": missing})
    return violations


def check_card(card: Path) -> dict:
    """检查单卡。返回 {state, ...}。

    state ∈ {skip_status, skip_legacy, pass, fail}
      - skip_status：非 done，跳过
      - skip_legacy：done 但无验收契约表（旧格式），跳过 + 提示
      - pass：done + 表全行合规
      - fail：done + 至少一行缺证据（含 violations）
    """
    status = read_status(card)
    if status != "done":
        return {"state": "skip_status", "status": status}
    content = card.read_text(encoding="utf-8", errors="replace")
    heading_present, table = find_contract_table(content)
    if not heading_present:
        return {"state": "skip_legacy"}
    # 硬化：有「验收契约」标题就必须可校验；标题在却无表 → fail
    if not table:
        return {"state": "fail",
                "violations": [{"item": "(无表)",
                                "missing": ["有「验收契约」标题但无 markdown 表"]}]}
    violations = check_contract_table(table)
    if violations:
        return {"state": "fail", "violations": violations}
    return {"state": "pass"}


def main(argv: list[str] | None = None) -> int:
    record_tool_invocation("check_phase_evidence.py")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default=None,
                    help="task id / 任务目录绝对路径；缺省扫 active 下所有任务")
    args = ap.parse_args(argv)

    task_dirs = resolve_task_dirs(args.task)
    if not task_dirs:
        print("ERROR: 未找到任务目录（--task 指定有误或 active 为空）", file=sys.stderr)
        return 1

    total_done = 0
    total_pass = 0
    total_fail = 0
    total_skip_legacy = 0
    fail_lines: list[str] = []

    for task_dir in task_dirs:
        design_dir = task_dir / "design"
        if not design_dir.is_dir():
            continue
        for card in sorted(design_dir.glob("Phase*.md")):
            res = check_card(card)
            state = res["state"]
            if state == "skip_status":
                continue
            total_done += 1
            tag = f"{task_dir.name} / {card.name}"
            if state == "skip_legacy":
                total_skip_legacy += 1
                print(f"⏭️  SKIP（旧格式 done 卡，无「验收契约」表）：{tag}")
            elif state == "pass":
                total_pass += 1
                print(f"✅ PASS：{tag}")
            elif state == "fail":
                total_fail += 1
                print(f"🔴 FAIL（done 缺证据）：{tag}")
                for v in res["violations"]:
                    cols = " + ".join(v["missing"])
                    line = f"     验收项「{v['item']}」缺：{cols}"
                    print(line)
                    fail_lines.append(f"{tag} | {v['item']} | 缺 {cols}")

    print("")
    print(f"汇总：done 卡 {total_done}　通过 {total_pass}　打回 {total_fail}　"
          f"跳过旧卡 {total_skip_legacy}")
    if total_fail:
        print("判定：BLOCKED — 以下 done 卡缺证据，应打回：")
        for fl in fail_lines:
            print(f"  - {fl}")
        return 1
    print("判定：PASS — 无 done 缺证据")
    return 0


if __name__ == "__main__":
    sys.exit(main())
