"""Deterministic policy-decision facts for retrieve_inject.

Temporary phase: make the UserPromptSubmit document injector useful for common
"can/should I do X" governance questions without relying on neural reranking.
Fail-open callers should treat any exception here as no policy hit.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

FACT_BANK_PATH = Path(__file__).resolve().parents[1] / "data" / "policy_fact_bank.json"
DECISION_TERMS = (
    "能不能", "能否", "可不可以", "可以吗", "是否可以", "要不要", "该不该", "应不应该",
    "允许", "禁止", "可以", "可以直接", "能直接", "要写", "要不要写", "能不能改", "能不能升级",
    "can i", "can we", "should i", "should we", "may i", "may we", "is it allowed",
    "allowed to", "do i need", "should this", "can this",
)
MAX_SUMMARY_CHARS = 96
MAX_EVIDENCE_PATHS = 3


@dataclass(frozen=True)
class PolicyFactMatch:
    fact_id: str
    decision: str
    confidence: str
    score: float
    summary: str
    evidence_paths: tuple[str, ...]
    matched_triggers: tuple[str, ...]

    def to_yaml_like(self) -> str:
        lines = [
            "schema_version: v1",
            "intent: policy_decision",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"fact_id: {self.fact_id}",
            f"summary: {self.summary}",
            "evidence_paths:",
        ]
        for path in self.evidence_paths[:MAX_EVIDENCE_PATHS]:
            lines.append(f"  - {path}")
        if self.matched_triggers:
            lines.append("matched_triggers:")
            for trigger in self.matched_triggers[:2]:
                lines.append(f"  - {trigger}")
        lines.append("note: Use as a rule-decision hint; cite/read evidence before changing behavior.")
        return "\n".join(lines) + "\n"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_policy_decision_query(query: str) -> bool:
    q = _normalize(query)
    if not q:
        return False
    return any(term in q for term in DECISION_TERMS)


def load_policy_facts(path: Path = FACT_BANK_PATH) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    facts = data.get("facts", []) if isinstance(data, Mapping) else []
    return [fact for fact in facts if isinstance(fact, dict)]


def _trigger_score(query: str, trigger: str) -> float:
    q = _normalize(query)
    t = _normalize(trigger)
    if not q or not t:
        return 0.0
    if t in q or q in t:
        return 10.0 + min(len(t), len(q)) / 100.0
    # Deterministic fallback for English/space-separated triggers.
    q_terms = {part for part in re.split(r"[^\w\u4e00-\u9fff]+", q) if len(part) >= 2}
    t_terms = {part for part in re.split(r"[^\w\u4e00-\u9fff]+", t) if len(part) >= 2}
    if not q_terms or not t_terms:
        return 0.0
    overlap = q_terms & t_terms
    if not overlap:
        return 0.0
    return len(overlap) / max(len(t_terms), 1)


def match_policy_fact(query: str, facts: Sequence[Mapping[str, Any]] | None = None) -> PolicyFactMatch | None:
    if not is_policy_decision_query(query):
        return None
    rows = list(facts) if facts is not None else load_policy_facts()
    best: tuple[float, Mapping[str, Any], list[str]] | None = None
    for fact in rows:
        triggers = [str(item) for item in fact.get("triggers", []) if str(item).strip()]  # type: ignore[arg-type]
        scored = [(trigger, _trigger_score(query, trigger)) for trigger in triggers]
        matched = [trigger for trigger, score in scored if score >= 1.0]
        score = max((score for _trigger, score in scored), default=0.0)
        # Keyword aliases are secondary; they should not beat explicit trigger phrase matches.
        aliases = [str(item) for item in fact.get("aliases", []) if str(item).strip()]  # type: ignore[arg-type]
        alias_hits = [alias for alias in aliases if _normalize(alias) in _normalize(query)]
        if alias_hits:
            score += min(3.0, len(alias_hits) * 0.75)
            matched.extend(alias_hits[:2])
        if score <= 0.0:
            continue
        if best is None or score > best[0]:
            best = (score, fact, matched)
    if best is None or best[0] < 1.0:
        return None
    score, fact, matched = best
    evidence = tuple(str(path) for path in fact.get("evidence_paths", []) if str(path).strip())  # type: ignore[arg-type]
    summary = str(fact.get("summary") or "").strip()
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[: MAX_SUMMARY_CHARS - 1].rstrip() + "…"
    confidence = "high" if score >= 10.0 else "medium"
    return PolicyFactMatch(
        fact_id=str(fact.get("id") or "unknown"),
        decision=str(fact.get("decision") or "unknown"),
        confidence=confidence,
        score=round(score, 3),
        summary=summary,
        evidence_paths=evidence,
        matched_triggers=tuple(dict.fromkeys(matched)),
    )
