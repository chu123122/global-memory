#!/usr/bin/env python
"""harness_retrieve.py — Context Brief 生成器（方向 B 骨干）

按 task + user_msg + stage 路由出 top-N 指针。
不注入正文，AI 拿到指针后自行 Read。

schema_version: v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "v2"  # v2: pointer 可携 summary（docs/ opt-in 召回摘要）
DEFAULT_MEMORY_ROOT = Path("D:/global-memory")
DEFAULT_CACHE_DIR = Path.home() / ".claude" / "cache"
RETRIEVE_SUMMARY_MAX = 200  # docs/ retrieve_summary 字数上限（lint 同步约束）


def _cache_path_for(memory_root: Path, base: Path = DEFAULT_CACHE_DIR) -> Path:
    h = hashlib.md5(str(memory_root.resolve()).encode("utf-8")).hexdigest()[:8]
    return base / f"triggers_{h}.json"


DEFAULT_CACHE_PATH = _cache_path_for(DEFAULT_MEMORY_ROOT)
DEFAULT_TASK_ROOT = Path("D:/ClaudeTasks/active")
DEFAULT_ALIASES_PATH = Path(__file__).resolve().parent / "triggers_aliases.yaml"
DEFAULT_LOG_PATH = Path.home() / ".claude" / "logs" / "retrieve_calls.jsonl"
MAX_LOGGED_QUERY = 200
MAX_BRIEF_BYTES = 8192          # ~2K token 上限（粗算 4 字节/token）
MAX_POINTERS = 2  # 2026-05-22 D5-B1：P1 数据 pointer_rate 0.7%，砍 60% 注入 token
HANDOFF_EXCERPT_LINES = 30
SELF_EXCLUDE_PATTERNS = ("/harness/scripts/", "/harness/hooks/")
DOWNRANK_CONFIG_ENV = "HARNESS_RETRIEVE_DOWNRANK_CONFIG"
TASK_CONTEXT_FALLBACK_CONFIG_ENV = "HARNESS_RETRIEVE_TASK_CONTEXT_FALLBACK_CONFIG"
_ALIAS_CACHE: list[tuple[list[str], str]] | None = None


@dataclass
class Pointer:
    path: str
    why: str
    score: float = 0.0
    summary: str = ""  # 仅 docs/ opt-in 条目带（retrieve_summary，AI 直接吃，免 Read 全文）

    def to_brief(self) -> dict[str, str]:
        out = {"path": self.path, "why": self.why}
        if self.summary:
            out["summary"] = self.summary
        return out


@dataclass
class ContextBrief:
    schema_version: str = SCHEMA_VERSION
    task: str = ""
    stage: str | None = None
    handoff_path: str = ""
    relevant_pointers: list[dict[str, str]] = field(default_factory=list)
    load_strategy: str = "just_in_time"
    warnings: list[str] = field(default_factory=list)

    def to_yaml_like(self) -> str:
        lines = [
            f"schema_version: {self.schema_version}",
            f"task: {self.task}",
            f"stage: {self.stage or 'unknown'}",
            f"handoff_path: {self.handoff_path or '(none)'}",
        ]
        lines.append("relevant_pointers:")
        if self.relevant_pointers:
            for p in self.relevant_pointers:
                lines.append(f"  - path: {p['path']}")
                lines.append(f"    why: {p['why']}")
                if p.get("summary"):
                    lines.append(f"    summary: {p['summary']}")
        else:
            lines.append("  []")
        lines.append(f"load_strategy: {self.load_strategy}")
        if self.warnings:
            lines.append("warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines) + "\n"


def normalize_path(p: str | Path) -> str:
    """Windows 反斜杠 → 正斜杠，保证 Read 工具一致输入。"""
    return str(p).replace("\\", "/")


def normalize_path_key(p: str | Path) -> str:
    return normalize_path(p).strip().lower()


def is_self_excluded(path: str) -> bool:
    p = normalize_path(path)
    return any(pat in p for pat in SELF_EXCLUDE_PATTERNS)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter. Tolerant fallback if pyyaml not present or yaml malformed."""
    if not text.startswith("---"):
        return {}, text
    end_idx = text.find("\n---", 3)
    if end_idx == -1:
        return {}, text
    fm_raw = text[3:end_idx].strip()
    body = text[end_idx + 4 :].lstrip("\n")
    try:
        import yaml  # type: ignore
        meta = yaml.safe_load(fm_raw) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = _fallback_parse(fm_raw)
    return meta, body


def _fallback_parse(raw: str) -> dict[str, Any]:
    """Naive line-based parser, last resort for broken yaml."""
    out: dict[str, Any] = {}
    current_key = None
    for line in raw.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        m = re.match(r"^([\w_-]+):\s*(.*)$", stripped)
        if m:
            key, val = m.group(1), m.group(2)
            current_key = key
            if val:
                out[key] = val
            else:
                out[key] = []
        elif current_key and stripped.lstrip().startswith("- "):
            v = stripped.lstrip()[2:].strip()
            if isinstance(out.get(current_key), list):
                out[current_key].append(v)
    return out


def scan_trigger_files(memory_root: Path) -> list[dict[str, Any]]:
    """扫 feedback/knowledge/fixes/decisions 全部 md + docs/ 中 opt-in 条目。

    docs/ 默认不进库（避免 200 行 reference 污染召回，见复盘 § 2.2）。
    docs/*.md 仅当 frontmatter 同时含 `retrieve: true` + `retrieve_summary: "<≤200 字>"`
    时才入索引；入索引后召回返回 summary 而非 path，AI 直接吃免再 Read。
    """
    results: list[dict[str, Any]] = []
    for sub in ("feedback", "knowledge", "fixes", "decisions"):
        d = memory_root / sub
        if not d.exists():
            continue
        for md in sorted(d.glob("*.md")):
            if is_self_excluded(str(md)):
                continue
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            meta, _ = parse_frontmatter(text)
            status = (meta.get("status") if isinstance(meta, dict) else None) or "active"
            if status == "deprecated":
                continue
            results.append(
                {
                    "path": normalize_path(md),
                    "meta": meta if isinstance(meta, dict) else {},
                    "description": (meta.get("description") if isinstance(meta, dict) else "") or "",
                }
            )
    # docs/ opt-in: 必须显式 retrieve: true + retrieve_summary 才进库
    docs_dir = memory_root / "docs"
    if docs_dir.exists():
        for md in sorted(docs_dir.glob("*.md")):
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            meta, _ = parse_frontmatter(text)
            if not isinstance(meta, dict):
                continue
            if meta.get("retrieve") is not True:
                continue
            summary = meta.get("retrieve_summary") or ""
            if not isinstance(summary, str) or not summary.strip():
                continue
            summary = summary.strip()[:RETRIEVE_SUMMARY_MAX]
            results.append(
                {
                    "path": normalize_path(md),
                    "meta": meta,
                    "description": meta.get("description") or "",
                    "retrieve_summary": summary,
                }
            )
    return results


def load_trigger_cache(cache_path: Path, memory_root: Path) -> list[dict[str, Any]]:
    """带 mtime 检查的缓存。任一文件 mtime > cache mtime 则重扫。
    Sanity check: entry path must live under memory_root; otherwise rebuild
    (guards against stale cache from prior test run pointing at tmp paths)."""
    if not cache_path.exists():
        return _rebuild_cache(cache_path, memory_root)
    cache_mtime = cache_path.stat().st_mtime
    for sub in ("feedback", "knowledge", "fixes", "decisions", "docs"):
        d = memory_root / sub
        if not d.exists():
            continue
        for md in d.glob("*.md"):
            if md.stat().st_mtime > cache_mtime:
                return _rebuild_cache(cache_path, memory_root)
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return _rebuild_cache(cache_path, memory_root)
    root_str = normalize_path(memory_root.resolve()).lower()
    for e in cached:
        p = normalize_path(e.get("path", "")).lower()
        if not p.startswith(root_str):
            return _rebuild_cache(cache_path, memory_root)
    return cached


def _rebuild_cache(cache_path: Path, memory_root: Path) -> list[dict[str, Any]]:
    data = scan_trigger_files(memory_root)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    return data


def load_aliases(path: Path = DEFAULT_ALIASES_PATH, force: bool = False) -> list[tuple[list[str], str]]:
    """Load alias table (patterns→map_to). Tolerant: missing file = empty list."""
    global _ALIAS_CACHE
    if _ALIAS_CACHE is not None and not force:
        return _ALIAS_CACHE
    out: list[tuple[list[str], str]] = []
    if not path.exists():
        _ALIAS_CACHE = out
        return out
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        _ALIAS_CACHE = out
        return out
    for item in data.get("aliases", []) or []:
        pats = item.get("patterns") or []
        target = item.get("map_to") or ""
        if not pats or not target:
            continue
        out.append(([str(p).lower() for p in pats], str(target)))
    _ALIAS_CACHE = out
    return out


def _levenshtein_le1(a: str, b: str) -> bool:
    """True if edit distance ≤ 1. Cheap & specialized — avoids full DP."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = sum(1 for x, y in zip(a, b) if x != y)
        return diff == 1
    short, long = (a, b) if la < lb else (b, a)
    i = j = 0
    skipped = False
    while i < len(short) and j < len(long):
        if short[i] != long[j]:
            if skipped:
                return False
            skipped = True
            j += 1
        else:
            i += 1
            j += 1
    return True


def expand_query(query: str, aliases: list[tuple[list[str], str]] | None = None) -> tuple[str, list[str]]:
    """Expand query via alias table. Returns (augmented_query, matched_targets).

    Lookup is case-insensitive substring match. Augmented query = original + all
    matched map_to tokens appended (space-separated) so downstream substring
    matcher catches expanded keywords. Original tokens are preserved.
    """
    if not query:
        return query, []
    if aliases is None:
        aliases = load_aliases()
    q_lower = query.lower()
    matched: list[str] = []
    seen: set[str] = set()
    for patterns, target in aliases:
        for pat in patterns:
            if pat and pat in q_lower:
                if target not in seen:
                    matched.append(target)
                    seen.add(target)
                break
    if not matched:
        return query, []
    return query + " " + " ".join(matched), matched


def _fuzzy_token_match(q_tokens: set[str], kw_text: str) -> bool:
    """True if any query token is within edit distance 1 of kw_text (len ≥4)."""
    if not kw_text or len(kw_text) < 4:
        return False
    for t in q_tokens:
        if not t or len(t) < 4:
            continue
        if abs(len(t) - len(kw_text)) > 1:
            continue
        if _levenshtein_le1(t, kw_text):
            return True
    return False


def _kw_namespace_warn(query: str, brief: ContextBrief) -> None:
    """多义词检测：常见 ambiguous 词 → warning（不阻塞）。"""
    AMBIG = {"diff", "lock", "cache", "build", "test"}
    tokens = re.findall(r"[\w-]+", query.lower())
    hits = [t for t in tokens if t in AMBIG]
    if hits:
        brief.warnings.append(
            f"ambiguous_keyword:{','.join(hits)} (namespace prefix recommended: tool:/concept:)"
        )


def _score_entry(entry: dict[str, Any], query: str, stage: str | None, task_tags: list[str]) -> tuple[float, str]:
    """对每个 entry 算 score + why。score=0 表示不推。"""
    trace = score_entry_trace(entry, query, stage, task_tags)
    return float(trace["final_score"]), str(trace["why"])


def score_entry_trace(entry: dict[str, Any], query: str, stage: str | None, task_tags: list[str]) -> dict[str, Any]:
    """Return score plus itemized contributions for retrieve trace tooling."""
    meta = entry.get("meta", {})
    desc = (entry.get("description") or "").lower()
    q_lower = (query or "").lower()
    q_tokens = set(re.findall(r"[\w-]+", q_lower))

    trigger = meta.get("trigger") if isinstance(meta, dict) else None
    trigger = trigger if isinstance(trigger, dict) else {}

    keywords = trigger.get("keywords", []) or []
    tags = trigger.get("tags", []) or []
    stages = trigger.get("stages", []) or []
    priority = (meta.get("priority") if isinstance(meta, dict) else None) or "medium"

    score = 0.0
    reasons: list[str] = []
    contributions: list[dict[str, Any]] = []

    for kw in keywords:
        if not isinstance(kw, str):
            continue
        kw_full = kw.lower()
        kw_text = kw.split(":", 1)[-1].lower()
        if not kw_text:
            continue
        if kw_full in q_lower or kw_text in q_lower:
            score += 2.0
            reasons.append(f"kw:{kw}")
            contributions.append({"kind": "keyword", "match": kw, "delta": 2.0})
        elif _fuzzy_token_match(q_tokens, kw_text):
            score += 1.4
            reasons.append(f"fuzzy:{kw}")
            contributions.append({"kind": "fuzzy", "match": kw, "delta": 1.4})

    for tag in tags:
        if not isinstance(tag, str):
            continue
        if tag in task_tags:
            score += 1.5
            reasons.append(f"tag:{tag}")
            contributions.append({"kind": "tag", "match": tag, "delta": 1.5})

    if stage and stage in stages:
        score += 1.0
        reasons.append(f"stage:{stage}")
        contributions.append({"kind": "stage", "match": stage, "delta": 1.0})

    pre_priority_score = score
    if priority == "high":
        score *= 1.2
        if pre_priority_score:
            contributions.append({"kind": "priority", "match": priority, "factor": 1.2, "before": pre_priority_score, "after": score})
    elif priority == "low":
        score *= 0.8
        if pre_priority_score:
            contributions.append({"kind": "priority", "match": priority, "factor": 0.8, "before": pre_priority_score, "after": score})

    if score == 0 and desc:
        for t in q_tokens:
            if t and t in desc:
                score += 0.3
                reasons.append("desc-token")
                contributions.append({"kind": "description", "match": t, "delta": 0.3})
                break

    return {
        "path": entry.get("path", ""),
        "description": entry.get("description", "") or "",
        "priority": priority,
        "raw_score": score,
        "final_score": score,
        "why": ", ".join(reasons[:3]) or "no signal",
        "reasons": reasons,
        "contributions": contributions,
    }


def extract_handoff_path(task_dir: Path) -> str:
    """Return normalized HANDOFF.md path if exists, else empty string.

    Replaces full-content excerpt (caused per-turn ~3KB context pollution).
    AI Reads file on demand — same JIT contract as relevant_pointers.
    """
    for rel in ("core/HANDOFF.md", "HANDOFF.md"):
        handoff = task_dir / rel
        if handoff.exists():
            return normalize_path(handoff)
    return ""


def _extract_section(text: str, candidates: list[str]) -> str:
    lines = text.splitlines()
    out: list[str] = []
    capture = False
    for ln in lines:
        m = re.match(r"^#{1,6}\s+(.+)$", ln)
        if m:
            heading = m.group(1).strip()
            if capture:
                break
            if any(c in heading for c in candidates):
                capture = True
                out.append(ln)
                continue
        if capture:
            out.append(ln)
    return "\n".join(out).strip()


def _first_useful_text(path: Path, limit: int) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---" or re.match(r"^[\w_-]+:\s*", stripped):
            continue
        lines.append(stripped)
        if len(" ".join(lines)) >= limit:
            break
    return re.sub(r"\s+", " ", " ".join(lines)).strip()[:limit]


def build_task_context_query(
    user_msg: str,
    task_name: str,
    task_root: Path,
    *,
    context_limit: int = 600,
) -> tuple[str, int, list[str]]:
    task_dir = task_root / task_name
    parts = [f"task:{task_name}"]
    sources: list[str] = []
    for rel in ("core/HANDOFF.md", "HANDOFF.md", "core/STATUS.md", "STATUS.md"):
        snippet = _first_useful_text(task_dir / rel, context_limit)
        if not snippet:
            continue
        parts.append(f"{rel}:{snippet}")
        sources.append(rel)
        if len(" ".join(parts)) >= context_limit:
            break
    context = re.sub(r"\s+", " ", " ".join(parts)).strip()[:context_limit]
    if not context:
        return user_msg, 0, []
    expanded = f"{user_msg}\n\n[task_context]\n{context}"
    return expanded, len(expanded) - len(user_msg), sources


MIN_SCORE_DEFAULT = 1.0


def load_downrank_config(config_path: Path | None) -> tuple[set[str], float, str]:
    """Load an opt-in retrieve downrank experiment config.

    Default retrieve behavior is unchanged unless a config is explicitly passed
    or HARNESS_RETRIEVE_DOWNRANK_CONFIG is set. Supported JSON shapes:

      {"enabled": true, "factor": 0.5, "paths": ["..."]}
      {"enabled": true, "factor": 0.5, "candidate_downrank": [{"path": "..."}]}
    """
    raw_path = str(config_path or os.environ.get(DOWNRANK_CONFIG_ENV, "")).strip()
    if not raw_path:
        return set(), 1.0, ""
    path = Path(raw_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("enabled") is False:
        return set(), 1.0, str(path)
    factor = float(data.get("factor", data.get("penalty_factor", 1.0)))
    if factor <= 0 or factor > 1:
        raise ValueError(f"downrank factor must be >0 and <=1, got {factor}")
    raw_paths = data.get("paths")
    if raw_paths is None:
        raw_paths = [item.get("path") for item in data.get("candidate_downrank", []) if isinstance(item, dict)]
    paths = {normalize_path_key(p) for p in raw_paths or [] if p}
    return paths, factor, str(path)


def load_task_context_fallback_config(config_path: Path | None) -> tuple[bool, int, set[str], str]:
    """Load an explicit task-context fallback config.

    Default retrieve behavior is unchanged unless a config is explicitly passed
    or HARNESS_RETRIEVE_TASK_CONTEXT_FALLBACK_CONFIG is set.
    """
    raw_path = str(config_path or os.environ.get(TASK_CONTEXT_FALLBACK_CONFIG_ENV, "")).strip()
    if not raw_path:
        return False, 600, set(), ""
    path = Path(raw_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("enabled") is not True:
        return False, 600, set(), str(path)
    context_limit = int(data.get("context_limit", 600))
    if context_limit < 100 or context_limit > 2000:
        raise ValueError(f"context_limit must be between 100 and 2000, got {context_limit}")
    allow = {str(x) for x in data.get("allowed_tasks", []) if str(x).strip()}
    return True, context_limit, allow, str(path)


def load_task_level_fallback_config(task_root: Path, task_name: str) -> tuple[bool, int, str]:
    """Load task-scoped retrieve fallback from <task>/core/CONFIG.json.

    This is intentionally narrower than the runtime experiment config:
    only the current task can enable itself, and it never creates a global
    allowlist.
    """
    if not task_name:
        return False, 600, ""
    path = task_root / task_name / "core" / "CONFIG.json"
    if not path.is_file():
        return False, 600, ""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False, 600, str(path)
    retrieve_cfg = data.get("retrieve")
    if not isinstance(retrieve_cfg, dict):
        return False, 600, str(path)
    fallback_cfg = retrieve_cfg.get("task_context_fallback")
    if fallback_cfg is True:
        enabled = True
        context_limit = 600
    elif isinstance(fallback_cfg, dict):
        enabled = fallback_cfg.get("enabled") is True
        context_limit = int(fallback_cfg.get("context_limit", 600))
    else:
        return False, 600, str(path)
    if context_limit < 100 or context_limit > 2000:
        raise ValueError(f"task-level context_limit must be between 100 and 2000, got {context_limit}")
    return enabled, context_limit, str(path)


def score_entries(
    entries: list[dict[str, Any]],
    query: str,
    *,
    stage: str | None,
    task_tags: list[str],
    min_score: float,
    downrank_paths: set[str],
    downrank_factor: float,
) -> list[Pointer]:
    scored: list[Pointer] = []
    for e in entries:
        s, why = _score_entry(e, query, stage, task_tags or [])
        if s >= min_score and downrank_paths and normalize_path_key(e["path"]) in downrank_paths:
            old = s
            s *= downrank_factor
            why = f"{why}, downrank_experiment:{old:.2f}->{s:.2f}"
        if s >= min_score:
            scored.append(Pointer(
                path=e["path"], why=why, score=s,
                summary=e.get("retrieve_summary", "") or "",
            ))
    scored.sort(key=lambda p: p.score, reverse=True)
    return scored


def write_retrieve_log(
    task_name: str,
    user_msg: str,
    brief: "ContextBrief",
    elapsed_ms: float,
    log_path: Path = DEFAULT_LOG_PATH,
    extras: dict | None = None,
) -> None:
    """Append one JSONL record per retrieve call.

    Failure must never break retrieve. Set env HARNESS_RETRIEVE_LOG=0 to disable.
    """
    if os.environ.get("HARNESS_RETRIEVE_LOG", "1") == "0":
        return
    _dbg = Path.home() / ".claude" / "logs" / "retrieve_inject_debug.log"
    try:
        _dbg.parent.mkdir(parents=True, exist_ok=True)
        with _dbg.open("a", encoding="utf-8") as _df:
            _df.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} ENTER write_retrieve_log task={task_name!r} log_path={log_path!s}\n")
    except Exception:
        pass
    try:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "task": task_name,
            "stage": brief.stage,
            "query": (user_msg or "")[:MAX_LOGGED_QUERY],
            "query_len": len(user_msg or ""),
            "elapsed_ms": round(elapsed_ms, 1),
            "hit_count": len(brief.relevant_pointers),
            "top1_path": brief.relevant_pointers[0]["path"] if brief.relevant_pointers else None,
            "top1_why": brief.relevant_pointers[0]["why"] if brief.relevant_pointers else None,
            "all_hits": [
                {"path": p["path"], "why": p["why"]}
                for p in brief.relevant_pointers
            ],
            "warnings": list(brief.warnings),
        }
        if extras:
            record.update(extras)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        pretty_path = log_path.with_suffix(".pretty.log")
        _zh_key = {
            "ts": "时间", "task": "任务", "stage": "阶段",
            "query": "查询", "query_len": "查询长度",
            "elapsed_ms": "耗时毫秒", "hit_count": "命中数",
            "top1_path": "首位路径", "top1_why": "首位原因",
            "all_hits": "全部命中", "warnings": "警告",
            "source": "来源", "min_score": "最低分", "top_n": "取前N",
            "path": "路径", "why": "原因",
        }
        def _zh(obj):
            if isinstance(obj, dict):
                return {_zh_key.get(k, k): _zh(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_zh(x) for x in obj]
            return obj
        with pretty_path.open("a", encoding="utf-8") as f:
            f.write(f"--- {record.get('ts','?')} 来源={record.get('source','-')} 命中={record.get('hit_count')} 耗时={record.get('elapsed_ms')}ms ---\n")
            f.write(json.dumps(_zh(record), ensure_ascii=False, indent=2) + "\n\n")
    except Exception as _e:
        try:
            import traceback as _tb
            with _dbg.open("a", encoding="utf-8") as _df:
                _df.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} INNER write_retrieve_log raised: {_e!r}\n")
                _df.write(_tb.format_exc())
                _df.write("\n")
        except Exception:
            pass


def retrieve(
    task_name: str,
    user_msg: str,
    stage: str | None = None,
    memory_root: Path = DEFAULT_MEMORY_ROOT,
    task_root: Path = DEFAULT_TASK_ROOT,
    cache_path: Path = DEFAULT_CACHE_PATH,
    task_tags: list[str] | None = None,
    top_n: int = MAX_POINTERS,
    min_score: float = MIN_SCORE_DEFAULT,
    downrank_config: Path | None = None,
    task_context_fallback_config: Path | None = None,
    task_level_fallback_enabled: bool = True,
) -> ContextBrief:
    brief = ContextBrief(task=task_name, stage=stage)

    task_dir = task_root / task_name
    brief.handoff_path = extract_handoff_path(task_dir)

    _kw_namespace_warn(user_msg, brief)

    aliases = load_aliases()
    expanded_msg, matched_aliases = expand_query(user_msg, aliases)
    if matched_aliases:
        brief.warnings.append(f"alias_expanded:{','.join(matched_aliases)}")

    entries = load_trigger_cache(cache_path, memory_root)
    downrank_paths: set[str] = set()
    downrank_factor = 1.0
    downrank_source = ""
    try:
        downrank_paths, downrank_factor, downrank_source = load_downrank_config(downrank_config)
    except Exception as exc:
        brief.warnings.append(f"downrank_config_ignored:{exc}")

    scored = score_entries(
        entries,
        expanded_msg,
        stage=stage,
        task_tags=task_tags or [],
        min_score=min_score,
        downrank_paths=downrank_paths,
        downrank_factor=downrank_factor,
    )
    if downrank_paths:
        brief.warnings.append(
            f"downrank_experiment:factor={downrank_factor},paths={len(downrank_paths)},source={downrank_source}"
        )

    fallback_enabled = False
    fallback_limit = 600
    fallback_allow: set[str] = set()
    fallback_source = ""
    try:
        fallback_enabled, fallback_limit, fallback_allow, fallback_source = load_task_context_fallback_config(
            task_context_fallback_config
        )
    except Exception as exc:
        brief.warnings.append(f"task_context_fallback_config_ignored:{exc}")
    if not fallback_enabled and task_context_fallback_config is None and task_level_fallback_enabled:
        try:
            task_enabled, task_limit, task_source = load_task_level_fallback_config(task_root, task_name)
            if task_enabled:
                fallback_enabled = True
                fallback_limit = task_limit
                fallback_allow = {task_name}
                fallback_source = task_source
        except Exception as exc:
            brief.warnings.append(f"task_context_fallback_task_config_ignored:{exc}")

    if (
        not scored
        and fallback_enabled
        and user_msg.strip()
        and (not fallback_allow or task_name in fallback_allow)
    ):
        context_msg, context_chars, sources = build_task_context_query(
            user_msg,
            task_name,
            task_root,
            context_limit=fallback_limit,
        )
        if context_chars > 0:
            context_expanded_msg, context_aliases = expand_query(context_msg, aliases)
            scored = score_entries(
                entries,
                context_expanded_msg,
                stage=stage,
                task_tags=task_tags or [],
                min_score=min_score,
                downrank_paths=downrank_paths,
                downrank_factor=downrank_factor,
            )
            if scored:
                brief.warnings.append(
                    "task_context_fallback:"
                    f"source={fallback_source},context_chars={context_chars},docs={','.join(sources)}"
                )
                if context_aliases:
                    brief.warnings.append(f"task_context_fallback_alias_expanded:{','.join(context_aliases)}")
    elif not scored and fallback_enabled and fallback_allow and task_name not in fallback_allow:
        brief.warnings.append(f"task_context_fallback_skipped:task_not_allowed:{task_name}")

    if user_msg.strip() and len(user_msg.strip()) < 4 and not scored:
        brief.warnings.append("query_too_short: pointers empty, fallback to handoff only")

    brief.relevant_pointers = [p.to_brief() for p in scored[:top_n]]

    out = brief.to_yaml_like()
    if len(out.encode("utf-8")) > MAX_BRIEF_BYTES:
        brief.relevant_pointers = brief.relevant_pointers[: max(1, top_n // 2)]
        brief.warnings.append("brief_truncated: exceeded MAX_BRIEF_BYTES")
    return brief


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Context Brief generator")
    p.add_argument("--task", required=True)
    p.add_argument("--query", default="")
    p.add_argument("--stage", default=None)
    p.add_argument("--memory-root", default=str(DEFAULT_MEMORY_ROOT))
    p.add_argument("--task-root", default=str(DEFAULT_TASK_ROOT))
    p.add_argument("--cache", default=None,
                   help="cache file (default: derived from --memory-root)")
    p.add_argument("--tags", default="", help="comma-separated task tags")
    p.add_argument("--top", type=int, default=MAX_POINTERS)
    p.add_argument("--min-score", type=float, default=MIN_SCORE_DEFAULT,
                   help="drop pointers below this score (default 1.0; <0.3 disables filter)")
    p.add_argument("--downrank-config", default=None,
                   help="opt-in experiment config; default behavior is unchanged")
    p.add_argument("--task-context-fallback-config", default=None,
                   help="explicit opt-in task-context fallback config; default behavior is unchanged")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--benchmark", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    t0 = time.perf_counter()
    mroot = Path(args.memory_root)
    cache_path = Path(args.cache) if args.cache else _cache_path_for(mroot)
    brief = retrieve(
        task_name=args.task,
        user_msg=args.query,
        stage=args.stage,
        memory_root=mroot,
        task_root=Path(args.task_root),
        cache_path=cache_path,
        task_tags=[t.strip() for t in args.tags.split(",") if t.strip()],
        top_n=args.top,
        min_score=args.min_score,
        downrank_config=Path(args.downrank_config) if args.downrank_config else None,
        task_context_fallback_config=Path(args.task_context_fallback_config) if args.task_context_fallback_config else None,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    write_retrieve_log(
        task_name=args.task,
        user_msg=args.query,
        brief=brief,
        elapsed_ms=elapsed_ms,
        extras={
            "min_score": args.min_score,
            "top_n": args.top,
            "downrank_config": args.downrank_config,
            "task_context_fallback_config": args.task_context_fallback_config,
        },
    )

    if args.benchmark:
        sys.stderr.write(f"retrieve_ms={elapsed_ms:.1f}\n")
    if args.json:
        sys.stdout.write(json.dumps(asdict(brief), ensure_ascii=False, indent=2, default=str))
        sys.stdout.write("\n")
    elif args.dry_run:
        sys.stdout.write(brief.to_yaml_like())
    else:
        sys.stdout.write(brief.to_yaml_like())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
