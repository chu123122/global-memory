"""In-memory rule lookup backend for gm.rule."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from harness.config import REPO_DIR

RULES_PATH = Path(__file__).with_name("rules.yaml")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}")


@dataclass(frozen=True)
class RuleSource:
    source_path: str
    anchor_text: str


@dataclass(frozen=True)
class RuleEntry:
    rule_id: str
    title: str
    verdict: str
    topics: tuple[str, ...]
    aliases: tuple[str, ...]
    summary: str
    sources: tuple[RuleSource, ...]


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    out = {item for item in TOKEN_RE.findall(lowered) if len(item) >= 2}
    for run in re.findall(r"[\u4e00-\u9fff]{3,}", lowered):
        for size in (2, 3, 4):
            for start in range(0, max(len(run) - size + 1, 0)):
                out.add(run[start : start + size])
    return out


def _load_yaml(path: Path = RULES_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"rules registry must be a mapping: {path}")
    return data


def _parse_rule(item: dict[str, Any]) -> RuleEntry:
    sources = tuple(
        RuleSource(source_path=str(src["source_path"]), anchor_text=str(src["anchor_text"]))
        for src in item.get("sources", [])
    )
    return RuleEntry(
        rule_id=str(item["rule_id"]),
        title=str(item["title"]),
        verdict=str(item.get("verdict") or "informational"),
        topics=tuple(str(x) for x in item.get("topics", [])),
        aliases=tuple(str(x) for x in item.get("aliases", [])),
        summary=str(item.get("summary") or ""),
        sources=sources,
    )


def _validate_sources(rules: tuple[RuleEntry, ...]) -> None:
    missing: list[str] = []
    for rule in rules:
        for source in rule.sources:
            path = REPO_DIR / source.source_path
            if not path.is_file():
                missing.append(f"{rule.rule_id}: missing {source.source_path}")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if source.anchor_text not in text:
                missing.append(f"{rule.rule_id}: anchor not found in {source.source_path}: {source.anchor_text}")
    if missing:
        raise ValueError("invalid gm.rule registry anchors:\n" + "\n".join(missing))


@lru_cache(maxsize=1)
def load_rules() -> tuple[RuleEntry, ...]:
    data = _load_yaml()
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("rules registry must contain a non-empty rules list")
    rules = tuple(_parse_rule(item) for item in raw_rules if isinstance(item, dict))
    _validate_sources(rules)
    return rules


def _score_rule(rule: RuleEntry, query: str, query_tokens: set[str]) -> float:
    haystack = " ".join([rule.rule_id, rule.title, rule.summary, *rule.topics, *rule.aliases]).lower()
    score = 0.0
    lowered = query.lower()
    for alias in rule.aliases:
        alias_l = alias.lower()
        if alias_l and alias_l in lowered:
            score += 8.0 + min(len(alias_l) / 10.0, 2.0)
    for topic in rule.topics:
        topic_l = topic.lower()
        if topic_l and topic_l in lowered:
            score += 5.0
    if rule.rule_id.lower() in lowered:
        score += 10.0
    score += len(query_tokens & _tokens(haystack)) * 1.25
    return score


def _has_direct_rule_context(rule: RuleEntry, query: str) -> bool:
    lowered = query.lower()
    if rule.rule_id.lower() in lowered:
        return True
    for alias in rule.aliases:
        alias_l = alias.lower().strip()
        if alias_l and alias_l in lowered:
            return True
    for topic in rule.topics:
        topic_l = topic.lower().strip()
        if topic_l and topic_l in lowered:
            return True
    return False


def _verdict(rule: RuleEntry, query: str, score: float) -> tuple[str, str]:
    if score > 0 and _has_direct_rule_context(rule, query):
        return rule.verdict, "direct_rule_text"
    return "informational", "informational"


def _snippet(source: RuleSource, *, max_chars: int = 220) -> str:
    text = (REPO_DIR / source.source_path).read_text(encoding="utf-8", errors="replace")
    idx = text.find(source.anchor_text)
    if idx < 0:
        return source.anchor_text
    start = max(0, idx - 80)
    end = min(len(text), idx + len(source.anchor_text) + 140)
    compact = " ".join(text[start:end].split())
    if len(compact) > max_chars:
        return compact[: max_chars - 1] + "…"
    return compact


def lookup_rule(query: str, *, top: int = 3) -> dict[str, Any]:
    start = time.perf_counter()
    clean = query.strip()
    if not clean:
        raise ValueError("query/action must not be empty")
    top = max(1, min(int(top), 10))
    rules = load_rules()
    q_tokens = _tokens(clean)
    scored = sorted(
        ((_score_rule(rule, clean, q_tokens), rule) for rule in rules),
        key=lambda item: (-item[0], item[1].rule_id),
    )
    matches = [item for item in scored if item[0] > 0][:top]
    if not matches:
        matches = [(0.0, rule) for rule in rules[: min(top, len(rules))]]
    results = []
    for score, rule in matches:
        verdict, verdict_basis = _verdict(rule, clean, score)
        sources = [
            {
                "source_path": source.source_path,
                "anchor_text": source.anchor_text,
                "rule_text": _snippet(source),
            }
            for source in rule.sources
        ]
        results.append(
            {
                "rule_id": rule.rule_id,
                "title": rule.title,
                "verdict": verdict,
                "verdict_basis": verdict_basis,
                "summary": rule.summary,
                "score": round(score, 3),
                "sources": sources,
            }
        )
    confidence = min(1.0, matches[0][0] / 10.0) if matches else 0.0
    return {
        "tool": "gm.rule",
        "query": clean,
        "hit": bool(matches and matches[0][0] > 0),
        "count": len(results),
        "confidence": round(confidence, 3),
        "low_confidence": confidence < 0.62,
        "results": results,
        "diagnostics": {
            "backend": "rules_yaml_in_memory",
            "registry_path": str(RULES_PATH),
            "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
        },
    }


def log_summary(result: dict[str, Any]) -> dict[str, Any]:
    results = result.get("results") or []
    top_ids = [str(item.get("rule_id")) for item in results[:3] if isinstance(item, dict)]
    top_refs: list[str] = []
    for item in results[:3]:
        if not isinstance(item, dict):
            continue
        sources = item.get("sources") or []
        if sources and isinstance(sources[0], dict):
            top_refs.append(str(sources[0].get("source_path")))
    summary = "; ".join(
        f"{item.get('rule_id')}: {item.get('summary')}" for item in results[:2] if isinstance(item, dict)
    )
    return {
        "hit": bool(result.get("hit")),
        "count": int(result.get("count") or 0),
        "top_refs": top_refs,
        "top_ids": top_ids,
        "confidence": float(result.get("confidence") or 0.0),
        "low_confidence": bool(result.get("low_confidence")),
        "returned_summary": summary[:500],
    }
