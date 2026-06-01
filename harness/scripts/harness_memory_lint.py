"""Memory frontmatter linter / compiler.

Validates frontmatter against triggers_vocab.yaml schema.
Exit 0 = pass, 1 = fail.

Usage:
    python harness_memory_lint.py FILE                    # one file
    python harness_memory_lint.py --batch DIR             # all .md in dir
    python harness_memory_lint.py --proposed              # all .md.proposed
    python harness_memory_lint.py FILE --json             # machine-readable
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERR: PyYAML missing. pip install pyyaml", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).parent
VOCAB_PATH = ROOT / "triggers_vocab.yaml"
MEMORY_ROOT = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2])))

REQUIRED = ("description", "priority", "status", "trigger", "last_updated")
TRIGGER_REQUIRED = ("keywords",)
MAX_KEYWORDS = 5
MAX_TAGS = 5
MAX_DESC = 100
RETRIEVE_SUMMARY_MAX = 200  # docs/ opt-in 召回摘要字数上限

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class LintResult:
    file: str
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_vocab() -> dict[str, Any]:
    if not VOCAB_PATH.exists():
        return {}
    return yaml.safe_load(VOCAB_PATH.read_text(encoding="utf-8")) or {}


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    m = FM_RE.match(text)
    if not m:
        return None, text
    raw = m.group(1)
    # strip "# TODO review" lines (sidecar marker) before parse
    cleaned = "\n".join(l for l in raw.splitlines() if "# TODO review" not in l)
    try:
        meta = yaml.safe_load(cleaned)
        if not isinstance(meta, dict):
            return None, text
        return meta, text[m.end():]
    except yaml.YAMLError:
        return None, text


def extract_h1_and_intro(body: str, n: int = 1000) -> str:
    """Get H1 + first n chars of body for over-tag check."""
    out = []
    for ln in body.splitlines()[:5]:
        if ln.startswith("#"):
            out.append(ln)
    return (" ".join(out) + " " + body[:n]).lower()


# Tag aliases: token → acceptable alt spellings in source text.
# Chinese files write "C++" not "cpp"; "Unreal Engine" or "UE" not "ue".
TAG_ALIASES: dict[str, tuple[str, ...]] = {
    "cpp":   ("cpp", "c++"),
    "ue":    ("ue", "unreal"),
    "unity": ("unity",),
    "lua":   ("lua", "unlua"),
    "qt":    ("qt", "pyside", "pyqt"),
}


def _tag_present(token: str, haystack: str) -> bool:
    aliases = TAG_ALIASES.get(token.lower(), (token.lower(),))
    return any(a in haystack for a in aliases)


def check_overtagging(file_path: Path, body: str, keywords: list[str],
                       tags: list[str], src_meta_text: str = "") -> list[str]:
    """Reject tool:X / domain:X if X absent from filename + source meta + intro.

    For .proposed sidecars, src_meta_text holds source .md's raw frontmatter
    text (description/source/etc) so aliases like 'c++' show up.
    """
    name = file_path.stem.lower()
    intro = extract_h1_and_intro(body)
    haystack = " ".join([name, src_meta_text.lower(), intro])
    bad: list[str] = []
    for kw in keywords:
        if not isinstance(kw, str) or ":" not in kw:
            continue
        ns, val = kw.split(":", 1)
        if ns == "tool" and val and not _tag_present(val, haystack):
            bad.append(f"keyword `{kw}` but '{val}' absent from source")
    for tag in tags:
        if not isinstance(tag, str):
            continue
        if tag.lower() in TAG_ALIASES and not _tag_present(tag, haystack):
            bad.append(f"tag `{tag}` but absent from source")
    return bad


def _check_retrieve_optin(meta: dict[str, Any], r: LintResult) -> None:
    """When frontmatter declares `retrieve: true`, enforce retrieve_summary contract.

    Rule (D1+D9): docs/ opt-in 召回必须配 retrieve_summary（≤200 字非空 str），
    否则 retrieve 端会拒绝入索引，等于声明无效。早 fail 早暴露。
    """
    if meta.get("retrieve") is not True:
        return
    summ = meta.get("retrieve_summary")
    if not isinstance(summ, str) or not summ.strip():
        r.ok = False
        r.errors.append("retrieve: true 但缺 retrieve_summary（必须非空 str）")
        return
    if len(summ) > RETRIEVE_SUMMARY_MAX:
        r.ok = False
        r.errors.append(f"retrieve_summary {len(summ)} 字 > {RETRIEVE_SUMMARY_MAX} 上限")


def _is_docs_file(path: Path) -> bool:
    try:
        parent = path.resolve().parent.name.lower()
    except Exception:
        parent = path.parent.name.lower()
    return parent == "docs"


def lint_file(path: Path, vocab: dict[str, Any], source_override: Path | None = None) -> LintResult:
    r = LintResult(file=str(path))
    if not path.exists():
        r.ok = False
        r.errors.append("file not found")
        return r

    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)
    if meta is None:
        r.ok = False
        r.errors.append("no frontmatter or YAML parse failed")
        return r

    # docs/ 走精简校验：只查 retrieve opt-in 契约（D9 预算：不复用 memory 的 priority/description 强约束）
    if _is_docs_file(path):
        _check_retrieve_optin(meta, r)
        return r

    # For .proposed sidecars (frontmatter-only), borrow source .md text:
    #   body  → real H1 + intro
    #   src_meta_text → source frontmatter (description/source/tags) where
    #   English aliases like "C++" / "Unreal" / "Qt" naturally appear.
    # source_override lets the hook point a tmp file at the real source.
    src_meta_text = ""
    src = None
    if source_override is not None:
        src = source_override
    elif str(path).endswith(".proposed"):
        src = Path(str(path)[: -len(".proposed")])
    if src is not None and src.exists():
        try:
            src_text = src.read_text(encoding="utf-8", errors="replace")
            m = FM_RE.match(src_text)
            if m:
                src_meta_text = m.group(1)
                body = src_text[m.end():]
            else:
                body = src_text
        except OSError:
            pass

    # required top-level fields
    for k in REQUIRED:
        if k not in meta:
            r.ok = False
            r.errors.append(f"missing required field: {k}")

    desc = meta.get("description", "")
    if isinstance(desc, str) and len(desc) > MAX_DESC:
        r.warnings.append(f"description {len(desc)} chars > {MAX_DESC}")

    priorities = set(vocab.get("priorities", []))
    if meta.get("priority") and priorities and meta["priority"] not in priorities:
        r.ok = False
        r.errors.append(f"priority `{meta['priority']}` not in vocab {sorted(priorities)}")

    statuses = set(vocab.get("statuses", []))
    if meta.get("status") and statuses and meta["status"] not in statuses:
        r.ok = False
        r.errors.append(f"status `{meta['status']}` not in vocab {sorted(statuses)}")

    last = meta.get("last_updated")
    if last is not None and not isinstance(last, (date, datetime)):
        try:
            datetime.fromisoformat(str(last))
        except ValueError:
            r.ok = False
            r.errors.append(f"last_updated `{last}` not ISO date")

    trigger = meta.get("trigger") or {}
    if not isinstance(trigger, dict):
        r.ok = False
        r.errors.append("trigger must be a dict")
        return r

    for k in TRIGGER_REQUIRED:
        if k not in trigger:
            r.ok = False
            r.errors.append(f"trigger.{k} missing")

    keywords = trigger.get("keywords") or []
    tags = trigger.get("tags") or []
    stages = trigger.get("stages") or []

    if not isinstance(keywords, list) or not (1 <= len(keywords) <= MAX_KEYWORDS):
        r.ok = False
        r.errors.append(f"trigger.keywords must be 1-{MAX_KEYWORDS} items (got {len(keywords) if isinstance(keywords, list) else 'not-list'})")

    if isinstance(tags, list) and len(tags) > MAX_TAGS:
        r.ok = False
        r.errors.append(f"trigger.tags exceeds {MAX_TAGS} ({len(tags)})")

    # tag vocab check
    domains = set(vocab.get("domains", []))
    if domains and isinstance(tags, list):
        for t in tags:
            if isinstance(t, str) and t not in domains:
                r.ok = False
                r.errors.append(f"tag `{t}` not in domains vocab")

    # stage vocab check
    stage_vocab = set(vocab.get("stages", []))
    if stage_vocab and isinstance(stages, list):
        for s in stages:
            if isinstance(s, str) and s not in stage_vocab:
                r.ok = False
                r.errors.append(f"stage `{s}` not in stages vocab")

    # keyword namespace check
    namespaces = set(vocab.get("namespaces", []))
    if isinstance(keywords, list):
        for kw in keywords:
            if not isinstance(kw, str):
                continue
            if ":" in kw:
                ns = kw.split(":", 1)[0]
                if namespaces and ns not in namespaces:
                    r.ok = False
                    r.errors.append(f"keyword `{kw}` namespace `{ns}` not in vocab")
            else:
                r.warnings.append(f"keyword `{kw}` lacks namespace prefix (consider tool:/concept:/error:)")

    # anti-overgeneralization
    bad = check_overtagging(path, body, keywords if isinstance(keywords, list) else [],
                             tags if isinstance(tags, list) else [],
                             src_meta_text=src_meta_text)
    for b in bad:
        r.ok = False
        r.errors.append(b)

    # retrieve opt-in 契约（即便 memory 文件偶尔标了 retrieve: true 也得守约）
    _check_retrieve_optin(meta, r)

    return r


def batch(targets: list[Path], vocab: dict[str, Any],
          source_override: Path | None = None) -> list[LintResult]:
    out = []
    for p in targets:
        out.append(lint_file(p, vocab, source_override=source_override))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", type=Path, help="single file to lint")
    ap.add_argument("--batch", type=Path, help="lint all .md under dir")
    ap.add_argument("--proposed", action="store_true",
                    help="lint all .md.proposed under GLOBAL_MEMORY_DIR")
    ap.add_argument("--source", type=Path, default=None,
                    help="override source .md path for body/meta lookup "
                         "(used by hook when linting tmp content)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args(argv)

    vocab = load_vocab()
    targets: list[Path] = []
    if args.file:
        targets = [args.file]
    elif args.batch:
        targets = sorted(args.batch.rglob("*.md"))
    elif args.proposed:
        targets = sorted(MEMORY_ROOT.rglob("*.md.proposed"))
    else:
        ap.error("provide FILE, --batch DIR, or --proposed")

    results = batch(targets, vocab, source_override=args.source)
    n_pass = sum(1 for r in results if r.ok)
    n_fail = len(results) - n_pass

    if args.json:
        print(json.dumps({
            "total": len(results),
            "pass": n_pass,
            "fail": n_fail,
            "results": [asdict(r) for r in results],
        }, ensure_ascii=False, indent=2))
    else:
        for r in results:
            if args.quiet and r.ok:
                continue
            mark = "PASS" if r.ok else "FAIL"
            print(f"[{mark}] {r.file}")
            for e in r.errors:
                print(f"    ERR: {e}")
            for w in r.warnings:
                print(f"    WARN: {w}")
        print(f"\n# {n_pass}/{len(results)} pass, {n_fail} fail")

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
