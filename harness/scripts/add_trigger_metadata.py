#!/usr/bin/env python
"""add_trigger_metadata.py — Half-automatic trigger frontmatter proposal.

Reads existing feedback/knowledge/fixes md files, infers candidate
keywords/tags from filename + body, writes a `.proposed` sidecar
for human review. Never edits the original file.

v2 (2026-05-20): pulls triggers_aliases.yaml so any alias pattern found
in filename or body's first 80 lines contributes a keyword. Tags now
multi-valued. Description extracted from first H1 if available.

Usage:
    python add_trigger_metadata.py --root "$env:GLOBAL_MEMORY_DIR" [--apply]
                                   [--regenerate]   # delete .proposed first

--apply: merges accepted .proposed files into originals (only those
         whose .proposed has been edited to remove the `# TODO review`
         marker).
--regenerate: delete existing .proposed files first, then re-propose.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2])))
SUBS = ("feedback", "knowledge", "fixes")
ALIASES_PATH = Path(__file__).resolve().parent / "triggers_aliases.yaml"

# 文件名/正文出现的硬词 → 推 tag（多 tag 允许）
HARD_TAGS = {
    "diff": "workflow",
    "compile": "build",
    "build": "build",
    "skill": "skill",
    "ui": "ui",
    "qt": "ui",
    "pyside": "ui",
    "qss": "ui",
    "stylesheet": "ui",
    "windows": "infra",
    "junction": "infra",
    "cpp": "cpp",
    "c++": "cpp",
    "thread": "cpp",
    "mutex": "cpp",
    "ue": "ue",
    "unreal": "ue",
    "unity": "unity",
    "lua": "lua",
    "code_style": "doc",
    "output_format": "doc",
    "learning": "interview",
    "interview": "interview",
    "p4": "workflow",
    "checkpoint": "workflow",
    "memory": "memory",
    "shader": "build",
    "lnk": "build",
    "linker": "build",
    "system_design": "design",
    "skill_design": "design",
    "ai_summary": "doc",
    "collaboration": "doc",
    "visual_aesthetic": "doc",
    "doc_only": "doc",
    "infra_ops": "infra",
}

# 文件名子串 → 默认 stages
STAGE_HINTS = {
    "diff": ["debug", "implementation"],
    "compile": ["debug"],
    "build": ["debug"],
    "shader": ["debug"],
    "lnk": ["debug"],
    "code_style": ["implementation", "delivery"],
    "output_format": ["delivery"],
    "learning": ["discussion"],
    "interview": ["discussion"],
    "skill_design": ["discussion", "implementation"],
    "system_design": ["discussion", "implementation"],
    "collaboration": ["discussion"],
    "ai_summary": ["delivery"],
    "visual_aesthetic": ["delivery"],
}


def _load_aliases() -> list[tuple[list[str], str]]:
    if not ALIASES_PATH.exists():
        return []
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(ALIASES_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    out: list[tuple[list[str], str]] = []
    for item in data.get("aliases", []) or []:
        pats = item.get("patterns") or []
        target = item.get("map_to") or ""
        if pats and target:
            out.append(([str(p).lower() for p in pats], str(target)))
    return out


def _extract_h1(body: str) -> str:
    for ln in body.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", ln)
        if m:
            return m.group(1).strip()
    return ""


def _body_after_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip("\n")


def infer(md: Path, text: str, aliases: list[tuple[list[str], str]]) -> dict:
    name = md.stem
    lname = name.lower()
    body = _body_after_frontmatter(text)
    body_head = "\n".join(body.splitlines()[:80]).lower()
    search_pool = f"{lname}\n{body_head}"

    keywords: list[str] = []
    seen_kw: set[str] = set()
    for patterns, target in aliases:
        for pat in patterns:
            if pat and pat in search_pool:
                if target not in seen_kw:
                    keywords.append(target)
                    seen_kw.add(target)
                break

    tags: list[str] = []
    seen_tag: set[str] = set()
    for hint, tag in HARD_TAGS.items():
        if hint in lname or hint in body_head:
            if tag not in seen_tag:
                tags.append(tag)
                seen_tag.add(tag)
    if not tags:
        tags = ["tooling"]

    stages: list[str] = []
    for hint, sts in STAGE_HINTS.items():
        if hint in lname:
            for s in sts:
                if s not in stages:
                    stages.append(s)
    if not stages:
        stages = ["implementation"]

    description = _extract_h1(body) or name

    return {
        "description": description,
        "keywords": keywords,
        "tags": tags,
        "stages": stages,
    }


def build_proposal(info: dict) -> str:
    lines = [
        "---",
        "# TODO review — human must approve before --apply merges this",
        f"description: {info['description']}",
        "priority: medium",
        "status: active",
        "trigger:",
        "  keywords:",
    ]
    for k in info["keywords"]:
        lines.append(f"    - {k}")
    if not info["keywords"]:
        lines.append("    - []")
    lines.append("  tags:")
    for t in info["tags"]:
        lines.append(f"    - {t}")
    lines.append("  stages:")
    for s in info["stages"]:
        lines.append(f"    - {s}")
    lines.append("last_updated: 2026-05-20")
    lines.append("---")
    return "\n".join(lines) + "\n"


def has_trigger(text: str) -> bool:
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    head = text[:end]
    return "trigger:" in head


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--regenerate", action="store_true",
                   help="delete existing .proposed files first")
    args = p.parse_args(argv)

    root = Path(args.root)
    aliases = _load_aliases()
    proposed = 0
    skipped = 0
    applied = 0
    regenerated = 0

    for sub in SUBS:
        d = root / sub
        if not d.exists():
            continue

        if args.regenerate and not args.apply:
            for sc in sorted(d.glob("*.md.proposed")):
                sc.unlink()
                regenerated += 1

        for md in sorted(d.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            sidecar = md.with_suffix(".md.proposed")

            if has_trigger(text):
                skipped += 1
                continue

            if not args.apply:
                if not sidecar.exists():
                    info = infer(md, text, aliases)
                    sidecar.write_text(build_proposal(info), encoding="utf-8")
                    proposed += 1
                continue

            if sidecar.exists():
                sc_text = sidecar.read_text(encoding="utf-8")
                if "# TODO review" in sc_text:
                    continue
                merged = sc_text.rstrip() + "\n\n" + text.lstrip()
                md.write_text(merged, encoding="utf-8")
                sidecar.unlink()
                applied += 1

    print(f"proposed={proposed} skipped={skipped} applied={applied} regenerated_deleted={regenerated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
