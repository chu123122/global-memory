"""Token filtering helpers for semantic retrieval acceptance gates."""
from __future__ import annotations

import re

# v1 heuristic stop/low-information list.  This is deliberately auditable and
# manually seeded; build-time token_df provides the data-derived high-DF guard.
LOW_INFORMATION_TOKENS = {
    "什么", "怎么", "怎样", "如何", "为何", "为什么", "今天", "明天", "昨天", "现在", "当前",
    "帮我", "我想", "请问", "这个", "那个", "这段", "那段", "可以", "能否",
    "能不", "能不能", "不能", "是不是", "有没有", "多少", "哪里", "时候", "什么时候",
    "写一", "我写", "帮我写", "一首", "一下", "修", "报", "该停", "出现", "怎么写", "么写",
    "推荐", "建议", "算法", "排序", "排序算法", "排序算", "序算法", "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "how", "what", "why", "when", "where", "is", "are", "do", "does", "can", "could", "should",
    "please", "help", "me", "write", "fix", "error", "python",
}

_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")
_ASCII_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_+-]*$")


def is_content_token(token: str) -> bool:
    t = token.strip()
    if not t:
        return False
    if t.lower() in LOW_INFORMATION_TOKENS or t in LOW_INFORMATION_TOKENS:
        return False
    # Single-character CJK and very short ASCII words are too ambiguous as acceptance evidence.
    if _CJK_RE.match(t):
        return len(t) >= 2
    if _ASCII_RE.match(t):
        return len(t) >= 4 and t.lower() not in LOW_INFORMATION_TOKENS
    # Mixed technical tokens such as KeyError are usable only if they are not generic.
    return len(t) >= 4 and t.lower() not in LOW_INFORMATION_TOKENS


def content_tokens(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if is_content_token(token) and token not in seen:
            seen.add(token)
            out.append(token)
    return out
