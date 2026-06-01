#!/usr/bin/env python
"""check_trigger_coverage.py — Verify frontmatter trigger coverage and vocab compliance.

Exit codes:
  0 OK
  1 coverage below threshold (default 90%) when --strict
  2 vocab violation when --strict
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness_retrieve import parse_frontmatter  # noqa: E402

DEFAULT_ROOT = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2])))
DEFAULT_VOCAB = Path(__file__).parent / "triggers_vocab.yaml"
SUBS = ("feedback", "knowledge", "fixes", "decisions")


def load_vocab(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    p.add_argument("--vocab", default=str(DEFAULT_VOCAB))
    p.add_argument("--threshold", type=float, default=0.90)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.root)
    vocab = load_vocab(Path(args.vocab))
    allowed_tags = set(vocab.get("domains", []) + vocab.get("stages", []))
    allowed_ns = set(vocab.get("namespaces", []))

    total = 0
    with_trigger = 0
    violations: list[str] = []

    for sub in SUBS:
        d = root / sub
        if not d.exists():
            continue
        for md in sorted(d.glob("*.md")):
            total += 1
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            meta, _ = parse_frontmatter(text)
            trigger = meta.get("trigger") if isinstance(meta, dict) else None
            if not isinstance(trigger, dict):
                continue
            kws = trigger.get("keywords", []) or []
            tags = trigger.get("tags", []) or []
            if not (kws or tags):
                continue
            with_trigger += 1

            for kw in kws:
                if not isinstance(kw, str) or ":" not in kw:
                    continue
                ns = kw.split(":", 1)[0]
                if allowed_ns and ns not in allowed_ns:
                    violations.append(f"{md}: bad namespace `{ns}` in keyword `{kw}`")
            for tag in tags:
                if allowed_tags and tag not in allowed_tags:
                    violations.append(f"{md}: tag `{tag}` not in vocab")

    coverage = with_trigger / total if total else 0
    print(f"total={total} with_trigger={with_trigger} coverage={coverage:.2%}")
    for v in violations[:20]:
        print(f"  VIOLATION {v}")
    if len(violations) > 20:
        print(f"  ... {len(violations) - 20} more")

    rc = 0
    if args.strict:
        if coverage < args.threshold:
            rc = 1
        if violations:
            rc = max(rc, 2)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
