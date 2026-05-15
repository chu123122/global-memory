"""
Section classifier for md2html: rule engine + Haiku fallback.
Maps heading text → component type for rich HTML rendering.
"""

import re
import os
import json

COMPONENT_TYPES = [
    "prose",
    "priority-cards",
    "comparison-table",
    "info-grid",
    "scope-table",
    "risk-cards",
    "criteria-table",
    "timeline",
    "phase-cards",
    "flow-diagram",
    "code-compare",
    "metric-cards",
]

RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"背景|Why|概述|简介|目标|动机|摘要|总结|Summary|Overview|边界|错误处理|兼容|数据模型|接口|Schema|算法|状态机|测试策略|平台|迁移", re.I), "prose"),
    (re.compile(r"问题|痛点|现状|缺陷|挑战|Challenge|Problem", re.I), "priority-cards"),
    (re.compile(r"方案|选定|对比|候选|备选|Alternative|Comparison|选型", re.I), "comparison-table"),
    (re.compile(r"环境|设备|配置|参数|测试环境|硬件|软件|Environment|Config", re.I), "info-grid"),
    (re.compile(r"范围与?验收|Scope|包含|不包含|In.?Scope|Out.?Scope", re.I), "scope-table"),
    (re.compile(r"风险|回滚|Risk|降级|Rollback|Mitigation", re.I), "risk-cards"),
    (re.compile(r"验收|标准|Acceptance|Criteria|Definition.?of.?Done|DoD", re.I), "criteria-table"),
    (re.compile(r"里程碑|进度|Milestone|Progress|排期|Schedule|计划", re.I), "timeline"),
    (re.compile(r"阶段|Phase|划分|Stage|步骤|Step", re.I), "phase-cards"),
    (re.compile(r"架构|时序|流程|调用链|Arch|Flow|Sequence|Pipeline|组件图", re.I), "flow-diagram"),
    (re.compile(r"前后|Before.*After|对比代码|diff|改造前|改造后", re.I), "code-compare"),
    (re.compile(r"指标|性能|Metric|KPI|基线|Baseline|数据|耗时|延迟|吞吐", re.I), "metric-cards"),
]

CONTENT_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"P[012]\s*[：:|(（]", re.I), "priority-cards"),
    (re.compile(r"Phase\s*\d|第[一二三四五]阶段", re.I), "phase-cards"),
    (re.compile(r"\b\d+\s*(ms|fps|MB|KB|%|秒|毫秒)\b", re.I), "metric-cards"),
    (re.compile(r"```(mermaid|plantuml|graph|sequenceDiagram)", re.I), "flow-diagram"),
    (re.compile(r"✅|❌|⚠️|🔴|🟢|🟡", re.I), "comparison-table"),
    # A1: new body-level content hints
    (re.compile(r"<table", re.I), "comparison-table"),
    (re.compile(r"(<li>.*?</li>.*){5,}", re.S), "info-grid"),
    (re.compile(r"(<pre>.*?</pre>.*){2,}", re.S), "code-compare"),
    (re.compile(r"(<h3.*?</h3>.*){3,}", re.S), "phase-cards"),
]


def classify_by_rules(heading: str, content: str = "") -> str | None:
    # A2: heading match → candidate (may be overridden by content hint)
    heading_match: str | None = None
    for pattern, comp_type in RULES:
        if pattern.search(heading):
            heading_match = comp_type
            break

    content_hint: str | None = None
    if content:
        for pattern, comp_type in CONTENT_HINTS:
            if pattern.search(content[:2000]):
                content_hint = comp_type
                break

    # Priority logic: content hint beats heading-only-prose
    if heading_match and content_hint:
        # If heading says prose but content hint is more specific → use content hint
        if heading_match == "prose" and content_hint != "prose":
            return content_hint
        # Otherwise heading match wins (it's based on domain semantics)
        return heading_match
    if heading_match:
        return heading_match
    if content_hint:
        return content_hint

    return None


def classify_by_haiku(heading: str, body_text: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "prose"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        # A3: improved prompt — include body text, reduce prose bias
        snippet = body_text[:500] if body_text else ""
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": (
                    f'Classify this document section into exactly one type.\n'
                    f'Types: {", ".join(COMPONENT_TYPES)}\n'
                    f'Rules:\n'
                    f'- If content is mainly a table → comparison-table\n'
                    f'- If content has 2+ code blocks → code-compare\n'
                    f'- If content has 5+ list items → info-grid\n'
                    f'- If content has 3+ h3 sub-headings → phase-cards\n'
                    f'- If content has numeric metrics (ms/MB/fps/%) → metric-cards\n'
                    f'- prose is the LAST resort, only for pure narrative paragraphs with no structure\n'
                    f'Heading: "{heading}"\n'
                    f'Body text (first 500 chars): "{snippet}"\n'
                    f'Reply with JSON only: {{"type": "..."}}'
                ),
            }],
        )
        text = resp.content[0].text.strip()
        match = re.search(r'"type"\s*:\s*"([^"]+)"', text)
        if match and match.group(1) in COMPONENT_TYPES:
            return match.group(1)
    except Exception:
        pass

    return "prose"


def classify(heading: str, content: str = "", use_ai: bool = True) -> str:
    result = classify_by_rules(heading, content)
    if result:
        return result

    if use_ai:
        # A3: pass stripped body text (not just first line)
        body_text = re.sub(r"<[^>]+>", "", content).strip() if content else ""
        return classify_by_haiku(heading, body_text)

    return "prose"
