#!/usr/bin/env python3
"""
_prompt_loader.py — hook 提示文案加载器

集中管理 hook 拦截/警告时的提示文案。文案存于 hook-prompts.md，按
`<!-- hook: section-id -->` ... `<!-- hook-end -->` 分段。

让 hook 脚本只关心拦截逻辑，文案改动零代码。
"""

import re
from pathlib import Path

_PROMPTS_FILE = Path(__file__).resolve().parent / "hook-prompts.md"
_cache = None

_SECTION_RE = re.compile(
    r'<!--\s*hook:\s*([^\s]+)\s*-->\s*\n(.*?)\n<!--\s*hook-end\s*-->',
    re.DOTALL,
)


def _parse() -> dict:
    """解析 hook-prompts.md，返回 {section_id: content} 字典。"""
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    if not _PROMPTS_FILE.exists():
        return _cache
    try:
        text = _PROMPTS_FILE.read_text(encoding="utf-8")
    except Exception:
        return _cache
    for match in _SECTION_RE.finditer(text):
        section_id = match.group(1)
        content = match.group(2).strip()
        _cache[section_id] = content
    return _cache


def get_prompt(section_id: str) -> str:
    """按 section ID 取提示文案。未配置返回空串。"""
    return _parse().get(section_id, "")
