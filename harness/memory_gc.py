#!/usr/bin/env python3
"""
memory_gc.py — global-memory 周期性垃圾回收

职责:扫 feedback/ knowledge/ fixes/ decisions/ interview/ 各分类,
按规则识别归档候选,移到 archive/<YYYY-MM-DD>/。
不动 knowledge/docs/(深度文档库)。

规则(任一命中即候选):
- R1: 文件最后 git 修改 > N 天(默认 30)
- R2: 文件 frontmatter / 内容头部含 [已废弃] / [已合入] / superseded
- R3: 文件大小 < 200 字节(几乎空)

用法:
  python memory_gc.py --dry-run         # 列候选,不执行
  python memory_gc.py --commit          # 实际归档
  python memory_gc.py --days 60 --dry-run    # 自定义天数

归档到 ~/.claude/global-memory/archive/<today>/<original-relpath>;原文件删除。
归档保留期 7 天后允许真删(本脚本不做真删,需手动)。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import MEMORY_DIR, TOPIC_DIRS, today_str  # noqa: E402

ARCHIVE_DIR = MEMORY_DIR / "archive"
DEPRECATED_PATTERNS = [
    r"\[已废弃\]",
    r"\[已合入\s+\w+\]",
    r"superseded by",
    r"已被\s*\w+\s*替代",
]
DEFAULT_DAYS_THRESHOLD = 30
SMALL_FILE_BYTES = 200


def git_last_modified_days(filepath: Path) -> int | None:
    """返回文件最后 git 修改距今天数;无 git 历史返回 None"""
    try:
        rel = filepath.resolve().relative_to(MEMORY_DIR.resolve())
    except ValueError:
        return None
    result = subprocess.run(
        ["git", "log", "-1", "--format=%aI", "--", str(rel)],
        cwd=str(MEMORY_DIR),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        last = datetime.fromisoformat(result.stdout.strip().split("+")[0].rstrip("Z"))
        return (datetime.now() - last).days
    except Exception:
        return None


def has_deprecated_marker(filepath: Path) -> str | None:
    """返回命中的废弃标记字符串,无则 None"""
    try:
        head = filepath.read_text(encoding="utf-8", errors="replace")[:2000]
    except Exception:
        return None
    for pat in DEPRECATED_PATTERNS:
        m = re.search(pat, head)
        if m:
            return m.group(0)
    return None


def scan_candidates(days_threshold: int) -> list[dict]:
    """扫所有 TOPIC_DIRS 下的 .md(不含 knowledge/docs/),返回候选清单"""
    candidates = []
    for cat in TOPIC_DIRS:
        cat_dir = MEMORY_DIR / cat
        if not cat_dir.is_dir():
            continue
        for f in sorted(cat_dir.glob("*.md")):
            if f.name == ".gitkeep":
                continue
            reasons = []
            # R1: 旧
            days = git_last_modified_days(f)
            if days is not None and days > days_threshold:
                reasons.append(f"R1: git log {days} days old (> {days_threshold})")
            # R2: 已废弃标记
            marker = has_deprecated_marker(f)
            if marker:
                reasons.append(f"R2: deprecated marker '{marker}'")
            # R3: 几乎空
            try:
                size = f.stat().st_size
                if size < SMALL_FILE_BYTES:
                    reasons.append(f"R3: size {size}B < {SMALL_FILE_BYTES}B")
            except Exception:
                pass

            if reasons:
                candidates.append({
                    "path": str(f.relative_to(MEMORY_DIR)),
                    "category": cat,
                    "size": f.stat().st_size,
                    "days_old": days,
                    "reasons": reasons,
                })
    return candidates


def archive_one(filepath: Path, archive_root: Path) -> Path:
    """把 filepath 移到 archive_root/<YYYY-MM-DD>/<原相对路径>"""
    rel = filepath.relative_to(MEMORY_DIR)
    dst = archive_root / today_str() / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(filepath), str(dst))
    return dst


def main() -> int:
    p = argparse.ArgumentParser(description="memory_gc — global-memory garbage collection")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS_THRESHOLD,
                   help=f"R1 天数阈值,默认 {DEFAULT_DAYS_THRESHOLD}")
    p.add_argument("--dry-run", action="store_true", help="只列候选,不执行")
    p.add_argument("--commit", action="store_true", help="实际归档候选到 archive/")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    if not args.dry_run and not args.commit:
        print("error: 必须指定 --dry-run 或 --commit", file=sys.stderr)
        return 2

    candidates = scan_candidates(args.days)

    if args.json:
        report = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "days_threshold": args.days,
            "candidates_count": len(candidates),
            "candidates": candidates,
            "executed": args.commit,
        }
        if args.commit:
            archived = []
            for c in candidates:
                src = MEMORY_DIR / c["path"]
                dst = archive_one(src, ARCHIVE_DIR)
                archived.append(str(dst.relative_to(MEMORY_DIR)))
            report["archived"] = archived
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"[memory_gc] threshold = {args.days} days  /  candidates = {len(candidates)}")
    print()
    if not candidates:
        print("  ✅ 无归档候选(所有文件均活跃 / 无废弃标记 / 非空)")
        return 0

    for c in candidates:
        days_str = f"{c['days_old']}d" if c['days_old'] is not None else "?"
        print(f"  📄 {c['path']:50s} ({c['size']}B, {days_str} old)")
        for r in c["reasons"]:
            print(f"      - {r}")

    if args.commit:
        print()
        print("[archiving...]")
        for c in candidates:
            src = MEMORY_DIR / c["path"]
            dst = archive_one(src, ARCHIVE_DIR)
            print(f"  ✅ {c['path']}  →  {dst.relative_to(MEMORY_DIR)}")
        print(f"\n[done] archived {len(candidates)} files to {ARCHIVE_DIR}/{today_str()}/")
    else:
        print()
        print(f"[dry-run] {len(candidates)} candidates would be archived. Use --commit to execute.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
