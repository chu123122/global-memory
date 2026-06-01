#!/usr/bin/env python3
"""
scan_orphan_scripts.py — harness/ 孤儿脚本巡检

扫 harness/ 下全部 *.py，跟 docs/scripts-registry.md 对账，输出：
- UNREGISTERED：在磁盘但未在 registry 提到（疑似新增未注册）
- ORPHAN_LISTED：registry 已标 ORPHAN 的脚本（待澄清/废弃）

只读，不删脚本（设计文档 D2 决策：删脚本不可逆，仅报告留人决策）。

用法：
  python scan_orphan_scripts.py             # 终端表
  python scan_orphan_scripts.py --json      # JSON 输出
  python scan_orphan_scripts.py --strict    # 有 UNREGISTERED/STALE 则 exit 1
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import json
import re
import sys
from pathlib import Path

# Windows UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

HARNESS_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = HARNESS_DIR.parent
REGISTRY_PATH = REPO_DIR / "docs" / "scripts-registry.md"

# 跳过：__pycache__ / 测试目录 / 私有 lib（_lib.py / _hook_lib.py 已是 Library）
SKIP_DIRS = {"__pycache__", ".pytest_cache", "tests", "test"}
SKIP_FILES = {"__init__.py"}


def collect_actual_scripts(root: Path) -> list[Path]:
    """返回 harness/ 下全部 .py，相对路径形式（POSIX 分隔）。"""
    out = []
    for p in sorted(root.rglob("*.py")):
        if p.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        out.append(p)
    return out


def parse_registry(path: Path) -> tuple[set[str], set[str], set[str]]:
    """解析 registry：返回 (字面提到的脚本相对路径, glob 通配模式, 标 ORPHAN 的)。

    脚本写法形如：
      - `` `hooks/foo.py` ``        字面
      - `` `scripts/bar.py` ``      字面
      - `` `top.py` ``              字面
      - `` `control_panel_pyside/**/*.py` ``  通配（含 * 或 ? 或 [）
      - `` `widgets/*.py` ``         通配

    ORPHAN 判定：行内出现 'ORPHAN' 标记。
    """
    literal: set[str] = set()
    globs: set[str] = set()
    orphans: set[str] = set()

    if not path.exists():
        return literal, globs, orphans

    # 反引号包裹的 .py 路径（允许多级目录 + glob 元字符 *、?、[]）
    pat = re.compile(r"`([A-Za-z_][\w./*?\[\]-]*?\.py)`")

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        scripts_in_line = pat.findall(line)
        if not scripts_in_line:
            continue
        for s in scripts_in_line:
            s = s.lstrip("./").replace("\\", "/")
            if any(c in s for c in "*?["):
                globs.add(s)
            else:
                literal.add(s)
            if "ORPHAN" in line:
                orphans.add(s)

    return literal, globs, orphans


def matches_any_glob(rel: str, globs: set[str]) -> bool:
    """fnmatch：`*` 匹配任意（含 /），所以 `a/**/*.py` 实际等价于 `a/*.py`。
    显式支持 `**` 写法（注册表里更清晰），匹配语义同 `*`。
    """
    for g in globs:
        if fnmatch.fnmatch(rel, g):
            return True
    return False


def relpath_from_harness(p: Path) -> str:
    """harness/ 相对路径，POSIX 分隔。"""
    return p.relative_to(HARNESS_DIR).as_posix()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--strict", action="store_true", help="有 UNREGISTERED 时 exit 1")
    ap.add_argument("--root", type=Path, default=HARNESS_DIR, help=f"扫描根（默认 {HARNESS_DIR}）")
    ap.add_argument("--registry", type=Path, default=REGISTRY_PATH, help=f"注册表路径（默认 {REGISTRY_PATH}）")
    args = ap.parse_args(argv)

    actual = collect_actual_scripts(args.root)
    actual_rel = {relpath_from_harness(p) for p in actual}

    literal, globs, orphans_listed = parse_registry(args.registry)
    mentioned = literal | globs

    # UNREGISTERED：磁盘有但 registry 未提（字面 + basename 兜底 + glob 通配）
    literal_basenames = {Path(m).name for m in literal}
    unregistered = sorted(
        rel for rel in actual_rel
        if rel not in literal
        and Path(rel).name not in literal_basenames
        and not matches_any_glob(rel, globs)
    )

    # ORPHAN_LISTED：registry 标 ORPHAN 的脚本（按 registry 写法保留原值）
    orphans_listed_sorted = sorted(orphans_listed)

    # STALE_LISTED：registry 字面提到但磁盘已不存在（glob 不参与 STALE 判定，无意义）
    actual_basenames = {Path(rel).name for rel in actual_rel}
    stale = sorted(
        m for m in literal
        if m not in actual_rel and Path(m).name not in actual_basenames
    )

    verdict = "ok" if not unregistered and not stale else "registry_drift"
    result = {
        "schema_version": 1,
        "kind": "orphan_script_scan",
        "verdict": verdict,
        "scanned_root": str(args.root),
        "registry": str(args.registry),
        "totals": {
            "actual_scripts": len(actual_rel),
            "mentioned_in_registry": len(mentioned),
            "literal_entries": len(literal),
            "glob_patterns": len(globs),
            "unregistered": len(unregistered),
            "orphan_listed": len(orphans_listed_sorted),
            "stale_in_registry": len(stale),
        },
        "summary": {
            "actual_scripts": len(actual_rel),
            "unregistered": len(unregistered),
            "orphan_listed": len(orphans_listed_sorted),
            "stale_in_registry": len(stale),
        },
        "unregistered": unregistered,
        "orphan_listed": orphans_listed_sorted,
        "stale_in_registry": stale,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print(f"  scan_orphan_scripts — {args.root}")
        print("=" * 60)
        t = result["totals"]
        print(f"  脚本总数 (实际): {t['actual_scripts']}")
        print(f"  registry 提到:   {t['mentioned_in_registry']}")
        print(f"  UNREGISTERED:    {t['unregistered']}")
        print(f"  ORPHAN (已标):    {t['orphan_listed']}")
        print(f"  STALE in registry: {t['stale_in_registry']}")
        print()

        if unregistered:
            print(f"[UNREGISTERED] ({len(unregistered)}) — 磁盘有，registry 未提：")
            for s in unregistered:
                print(f"  - {s}")
            print()
        else:
            print("[UNREGISTERED] 无")
            print()

        if orphans_listed_sorted:
            print(f"[ORPHAN_LISTED] ({len(orphans_listed_sorted)}) — registry 已标 ORPHAN，待澄清：")
            for s in orphans_listed_sorted:
                print(f"  - {s}")
            print()
        else:
            print("[ORPHAN_LISTED] 无")
            print()

        if stale:
            print(f"[STALE] ({len(stale)}) — registry 提到但磁盘缺失：")
            for s in stale:
                print(f"  - {s}")
            print()

        # 稳定结尾标志，供 gate / grep 使用
        print(f"orphan_scan={verdict} unregistered={len(unregistered)} orphan_listed={len(orphans_listed_sorted)}")
        print("=" * 60)

    if args.strict and (unregistered or stale):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
