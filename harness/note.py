#!/usr/bin/env python3
"""note.py — 便利签 CLI。skill 直接调，极省 token。"""

import io
import sys
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

NOTES_FILE = Path("D:/global-memory/notes.md")


def load_lines():
    if not NOTES_FILE.exists():
        return []
    return [l.rstrip("\n") for l in NOTES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]


def save_lines(lines):
    NOTES_FILE.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def max_id(lines):
    m = 0
    for l in lines:
        dot = l.find(".")
        if dot > 0:
            try:
                m = max(m, int(l[:dot]))
            except ValueError:
                pass
    return m


def cmd_show():
    lines = load_lines()
    if not lines:
        print("便签为空")
    else:
        print("\n".join(lines))


def cmd_add(content):
    lines = load_lines()
    n = max_id(lines) + 1
    date = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"{n}. {content}（{date}）")
    save_lines(lines)
    print(f"✓ #{n} 已记录")


def cmd_del(num):
    lines = load_lines()
    prefix = f"{num}."
    found = False
    new_lines = []
    for l in lines:
        if l.startswith(prefix):
            found = True
        else:
            new_lines.append(l)
    if found:
        save_lines(new_lines)
        print(f"✓ #{num} 已删除")
    else:
        print(f"#{num} 不存在")


def cmd_clear():
    save_lines([])
    print("✓ 已清空")


def main():
    args = sys.argv[1:]
    if not args:
        cmd_show()
    elif args[0] == "del" and len(args) >= 2:
        cmd_del(int(args[1]))
    elif args[0] == "clear":
        cmd_clear()
    else:
        cmd_add(" ".join(args))


if __name__ == "__main__":
    main()
