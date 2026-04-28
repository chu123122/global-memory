"""扫描关键文档中提到的本地文件引用，验证文件实际存在。

只扫指定的"枢纽"文档以控制误报：
  - README.md / MAINTENANCE.md / RULE_ENFORCEMENT_MATRIX.md
  - projects/*/需求分析.md / 设计文档.md（最近活跃任务）

抽取模式：
  - markdown 链接：[text](path/to/file.ext)
  - 带后缀的裸路径：harness/foo.py / projects/bar/baz.md

过滤：跳过 http://、外部 URL、以 ~ 开头的家路径、不带 / 的纯文件名。
"""
from __future__ import annotations

import re
from pathlib import Path

from ..registry import Signal, register

REPO_DIR = Path(__file__).resolve().parents[3]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
TOP_DIRS = "harness|projects|skills|knowledge|feedback|decisions|fixes|archives|retrospectives|interview|templates|agents|_bootstrap"
BARE_PATH_RE = re.compile(
    rf"(?<![A-Za-z0-9_./~-])((?:{TOP_DIRS})/[A-Za-z0-9_./-]+\.(?:md|py|json|sh|bat|toml|yaml|yml))(?![A-Za-z0-9_./-])"
)
SKIP_PREFIX = ("http://", "https://", "mailto:", "#", "~", "/", "C:", "D:", "E:")
SKIP_SUFFIX = (".png", ".jpg", ".gif", ".svg", ".jpeg")


def _hub_docs() -> list[Path]:
    docs: list[Path] = []
    for name in ("README.md", "MAINTENANCE.md", "RULE_ENFORCEMENT_MATRIX.md", "CONTROL_PANEL.md"):
        p = REPO_DIR / name
        if p.exists():
            docs.append(p)
    for proj in (REPO_DIR / "projects").glob("*"):
        if not proj.is_dir():
            continue
        for fname in ("需求分析.md", "设计文档.md", "SPEC.md"):
            p = proj / fname
            if p.exists():
                docs.append(p)
    return docs


def _extract_refs(text: str) -> set[str]:
    refs: set[str] = set()
    for m in LINK_RE.finditer(text):
        refs.add(m.group(1))
    for m in BARE_PATH_RE.finditer(text):
        refs.add(m.group(1))
    return refs


PLANNED_MARKERS = ("待建", "待实现", "未实现", "TBD", "后续实现", "建议放在", "规划中")


def _is_planned(text: str, ref: str) -> bool:
    """Skip refs marked as future/planned in surrounding 40 chars."""
    idx = text.find(ref)
    if idx < 0:
        return False
    prefix = text[max(0, idx - 40) : idx]
    return any(m in prefix for m in PLANNED_MARKERS)


@register("ghost_refs")
def check() -> list[Signal]:
    docs = _hub_docs()
    if not docs:
        return [Signal("ghost_refs", "info", "无枢纽文档可扫")]

    ghosts: list[tuple[str, str]] = []  # (doc_relpath, missing_ref)
    checked = 0
    for doc in docs:
        text = doc.read_text(encoding="utf-8", errors="replace")
        for ref in _extract_refs(text):
            ref = ref.split("#", 1)[0].strip()  # strip markdown anchors
            if not ref or ref.startswith(SKIP_PREFIX) or ref.endswith(SKIP_SUFFIX):
                continue
            target = (REPO_DIR / ref).resolve()
            if str(target).startswith(str(REPO_DIR.resolve())) and not target.exists():
                if _is_planned(text, ref):
                    continue
                ghosts.append((doc.relative_to(REPO_DIR).as_posix(), ref))
            checked += 1

    n = len(ghosts)
    if n == 0:
        return [
            Signal(
                check_id="ghost_refs",
                status="ok",
                headline=f"枢纽文档 {len(docs)} 篇引用 {checked} 处文件全部存在",
                value=f"{checked} refs / {len(docs)} docs",
            )
        ]
    status = "critical" if n >= 8 else "warning"
    seen: set[str] = set()
    evidence: list[str] = []
    for doc, ref in ghosts:
        key = f"{doc} -> {ref}"
        if key in seen:
            continue
        seen.add(key)
        evidence.append(key)
        if len(evidence) >= 8:
            break
    return [
        Signal(
            check_id="ghost_refs",
            status=status,
            headline=f"{n} 处文档引用指向不存在的文件",
            value=f"{n}/{checked}",
            evidence=evidence,
            fix_hint="补缺失文件，或从枢纽文档删除引用，或改为外部链接",
        )
    ]
