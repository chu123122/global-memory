#!/usr/bin/env python
"""task_experience_index.py — ClaudeTasks 跨任务经验索引维护工具.

索引内容由 LLM 内容分类产出（workflow `task-experience-triage`），本脚本只做
**确定性**部分：枚举候选、检测过时（new/changed/deleted）、prune 已删条目。

为何不在这里做分类：判定"是否跨任务可复用 + 抽 keyword"需要语义理解，是 LLM 活，
脚本做不了。本脚本负责把"哪些文件需要（重新）triage"算出来，triage 本身重跑 workflow。

用法:
    python task_experience_index.py --enumerate            # 写候选清单
    python task_experience_index.py --diff                 # 报 new/changed/deleted（对比现有索引 mtime）
    python task_experience_index.py --prune                # 从索引删掉已不存在的文件
    python task_experience_index.py --build <workflow.output.json>  # 从 workflow 输出建/刷新索引
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

TASKS_ROOT = Path(r"D:\ClaudeTasks")
INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "task_experience_index.json"
CAND_PATH = Path(__file__).resolve().parent.parent / "data" / "task_experience_candidates.json"

VOCAB = {"workflow", "build", "debug", "ui", "perf", "tooling", "infra", "cpp",
         "ue", "unity", "lua", "python", "skill", "memory", "interview", "doc", "design"}
NS = ("tool:", "concept:", "error:", "cmd:", "platform:")

# 结构性流水账/脚手架：可靠按名排除
STRUCT_NOISE = {
    "HANDOFF.md", "STATUS.md", "CHANGELOG.md", "INDEX.md", "进度.md", "背景.md",
    "需求分析.md", "SPEC.md", "README.md", "WORKFLOW.md", "extract_candidates.md",
    "需求.md", "阶段 2 实际进度.md", "需求分析-v1-flat.md",
}
PATH_NOISE = ("/sandbox/", "/out/", "/test-reports/", "/captures/", "/.diff", "/node_modules/", "/_archive/")


def _is_phase(name: str) -> bool:
    return bool(re.match(r"Phase\s*\d+", name)) or name.startswith("阶段")


def enumerate_candidates() -> list[str]:
    out = []
    for area in ("active", "archived"):
        base = TASKS_ROOT / area
        if not base.is_dir():
            continue
        for f in base.rglob("*.md"):
            sp = f.as_posix()
            if any(n in sp for n in PATH_NOISE):
                continue
            if f.name in STRUCT_NOISE or _is_phase(f.name):
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")
            body = re.sub(r"^---.*?---", "", txt, flags=re.S)
            real = len(re.sub(r"\s", "", body))
            placeholder = ("待补" in txt or "待运行" in txt) and real < 300
            if real < 120 or placeholder:
                continue
            out.append(sp)
    return sorted(out)


def task_of(p: str) -> str:
    a = p.split("/")
    try:
        i = a.index("ClaudeTasks"); return a[i + 1] + "/" + a[i + 2]
    except (ValueError, IndexError):
        return "?"


def load_index() -> dict:
    if INDEX_PATH.is_file():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"schema_version": "v1", "source": "task-experience-triage", "count": 0, "entries": []}


def cmd_enumerate() -> None:
    cands = enumerate_candidates()
    CAND_PATH.parent.mkdir(parents=True, exist_ok=True)
    CAND_PATH.write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"candidates: {len(cands)} -> {CAND_PATH}")


def cmd_diff() -> None:
    cands = set(enumerate_candidates())
    idx = load_index()
    # triaged = 已过 triage 的全集（含被判不可复用的），避免把"拒掉的"反复当 new。
    triaged = set(idx.get("triaged") or [e["path"] for e in idx.get("entries", [])])
    indexed = {e["path"] for e in idx.get("entries", [])}
    new = sorted(cands - triaged)            # 从没 triage 过的
    deleted = sorted(indexed - cands)        # 索引里但文件没了 → 该 prune
    print(f"candidates={len(cands)} triaged={len(triaged)} indexed_reusable={len(indexed)} "
          f"new={len(new)} deleted={len(deleted)}")
    for p in new[:50]:
        print(f"  NEW     {p}")
    for p in deleted[:50]:
        print(f"  DELETED {p}")
    if new:
        print("-> new 需重跑 workflow triage（仅这些）")
    if deleted:
        print("-> deleted 用 --prune 清")


def cmd_prune() -> None:
    cands = set(enumerate_candidates())
    idx = load_index()
    before = len(idx.get("entries", []))
    idx["entries"] = [e for e in idx.get("entries", []) if e["path"] in cands]
    idx["count"] = len(idx["entries"])
    INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pruned {before - idx['count']} stale; remain {idx['count']}")


def cmd_promote_candidates() -> None:
    """B 升进提醒：列 pitfall/retrospective 类、与 global fixes/knowledge 关键词重合低的条目.

    普适坑应升进 global/fixes（CLAUDE.md 工作流），但常漏。本命令列出疑似漏升进的供人工 triage。
    判定：index 条目 type∈{pitfall,retrospective} 且其 keyword 与所有 global fixes/knowledge
    的 keyword 交集 < 2 → 疑似没对应 global 条目。纯启发式，最终人工判普适与否。
    """
    mem = Path(__file__).resolve().parent.parent.parent
    global_kw: list[set] = []
    for sub in ("fixes", "knowledge"):
        d = mem / sub
        if not d.is_dir():
            continue
        for f in d.glob("*.md"):
            m = re.search(r"keywords:\s*\n((?:\s*-\s*.+\n)+)", f.read_text(encoding="utf-8", errors="replace"))
            kws = set(re.findall(r"-\s*([\w:.-]+)", m.group(1))) if m else set()
            if kws:
                global_kw.append(kws)
    idx = load_index()
    cands = []
    for e in idx.get("entries", []):
        if e.get("type") not in ("pitfall", "retrospective"):
            continue
        ekw = set(e.get("keywords") or [])
        best = max((len(ekw & g) for g in global_kw), default=0)
        if best < 2:
            cands.append((best, e))
    cands.sort(key=lambda x: (x[0], -(x[1].get("confidence") or 0)))
    print(f"疑似漏升进 global/fixes 的经验条目: {len(cands)}（pitfall/retro 中 global keyword 重合<2）")
    for overlap, e in cands[:40]:
        print(f"  [overlap={overlap} conf={e.get('confidence')}] {e['task']} :: {e['path'].split('/')[-1]}")
        print(f"      {e['description'][:90]}")
    print("-> 人工判普适者升进 global/fixes；任务专属者忽略。")


def cmd_build(output_json: str) -> None:
    raw = json.loads(Path(output_json).read_text(encoding="utf-8"))
    records = raw.get("result", {}).get("records", []) if "result" in raw else raw.get("records", [])
    seen, clean, issues = set(), [], Counter()
    for r in records:
        path = (r.get("path") or "").replace("\\", "/")
        if not path or path in seen:
            issues["dup_or_empty"] += 1
            continue
        seen.add(path)
        kws = [k for k in (r.get("keywords") or []) if isinstance(k, str) and k.lower().startswith(NS)][:5]
        tags = [t for t in (r.get("tags") or []) if t in VOCAB][:5]
        desc = (r.get("description") or "").strip()[:200]
        if not kws and not desc:
            issues["no_signal"] += 1
            continue
        clean.append({"path": path, "task": task_of(path), "type": r.get("type") or "other",
                      "description": desc, "keywords": kws, "tags": tags, "confidence": r.get("confidence")})
    # triaged = 喂给 workflow 的候选全集（含被判不可复用的），供 --diff 只标真·新增。
    triaged = sorted(enumerate_candidates())
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps({"schema_version": "v1", "source": "task-experience-triage",
                                      "count": len(clean), "entries": clean, "triaged": triaged},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"built {len(clean)} entries (triaged {len(triaged)}) -> {INDEX_PATH}; "
          f"by type {dict(Counter(e['type'] for e in clean))}; issues {dict(issues)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--enumerate", action="store_true")
    g.add_argument("--diff", action="store_true")
    g.add_argument("--prune", action="store_true")
    g.add_argument("--promote-candidates", action="store_true")
    g.add_argument("--build", metavar="WORKFLOW_OUTPUT_JSON")
    args = ap.parse_args()
    if args.enumerate:
        cmd_enumerate()
    elif args.diff:
        cmd_diff()
    elif args.prune:
        cmd_prune()
    elif args.promote_candidates:
        cmd_promote_candidates()
    elif args.build:
        cmd_build(args.build)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
