"""Corpus scanning and markdown chunking for the semantic retrieval PoC."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from harness.scripts.harness_retrieve import parse_frontmatter


@dataclass(frozen=True)
class Authority:
    tier: str


@dataclass(frozen=True)
class MarkdownChunk:
    chunk_id: str
    rel_path: str
    heading_path: str
    text: str
    ordinal: int
    content_hash: str = ""
    source_mtime: float = 0.0
    metadata_keywords: list[str] = field(default_factory=list)
    metadata_tags: list[str] = field(default_factory=list)

    @property
    def embedding_text(self) -> str:
        return self.text


@dataclass(frozen=True)
class MarkdownDocument:
    rel_path: str
    meta: dict[str, Any]
    description: str
    retrieve_summary: str
    keywords: list[str]
    tags: list[str]
    authority: Authority
    chunks: list[MarkdownChunk] = field(default_factory=list)


def authority_for_path(rel_path: str) -> Authority:
    normalized = rel_path.replace("\\", "/").lstrip("/")
    first = normalized.split("/", 1)[0]
    if normalized == "AGENTS.md" or first in {"rules", "agents"}:
        return Authority("T1")
    if first in {"feedback", "fixes", "decisions"}:
        return Authority("T2")
    if first == "knowledge":
        return Authority("T3")
    if first == "docs":
        return Authority("T4")
    return Authority("T3")


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value).strip()
    return [raw] if raw else []


def _extract_trigger(meta: dict[str, Any]) -> tuple[list[str], list[str]]:
    trigger = meta.get("trigger")
    if isinstance(trigger, dict):
        return _as_str_list(trigger.get("keywords")), _as_str_list(trigger.get("tags"))
    return _as_str_list(meta.get("keywords")), _as_str_list(meta.get("tags"))


def normalize_relative_path(memory_root: Path, path: Path) -> str:
    root = memory_root.resolve()
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path is outside MEMORY_ROOT: {path}") from exc
    rel_text = rel.as_posix()
    if rel_text.startswith("../") or rel_text == ".." or rel.is_absolute():
        raise ValueError(f"Unsafe relative path: {rel_text}")
    return rel_text


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def file_content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    paragraphs = text.split("\n\n")
    for para in paragraphs:
        para_len = len(para) + 2
        if current and current_len + para_len > max_chars:
            parts.append("\n\n".join(current).strip())
            current = []
            current_len = 0
        if para_len > max_chars:
            for start in range(0, len(para), max_chars):
                chunk = para[start : start + max_chars].strip()
                if chunk:
                    parts.append(chunk)
        else:
            current.append(para)
            current_len += para_len
    if current:
        parts.append("\n\n".join(current).strip())
    return [p for p in parts if p]


def split_heading_chunks(
    rel_path: str,
    body: str,
    *,
    source_mtime: float = 0.0,
    metadata_keywords: list[str] | None = None,
    metadata_tags: list[str] | None = None,
    min_chars: int = 20,
    max_chars: int = 2400,
) -> list[MarkdownChunk]:
    """Split markdown into bounded chunks at #/##/### headings."""
    sections: list[tuple[str, str]] = []
    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_heading = ""

    def flush() -> None:
        nonlocal current_lines, current_heading
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((current_heading, text))
        current_lines = []

    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            marker, _, title = stripped.partition(" ")
            if 1 <= len(marker) <= 3 and set(marker) == {"#"} and title.strip():
                flush()
                level = len(marker)
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(title.strip())
                current_heading = " > ".join(heading_stack)
                current_lines = [line]
                continue
        current_lines.append(line)
    flush()
    if not sections and body.strip():
        sections.append(("", body.strip()))

    merged: list[tuple[str, str]] = []
    for heading, text in sections:
        if merged and len(text) < min_chars:
            prev_heading, prev_text = merged[-1]
            merged[-1] = (prev_heading or heading, f"{prev_text}\n\n{text}".strip())
        else:
            merged.append((heading, text))

    chunks: list[MarkdownChunk] = []
    keywords = list(metadata_keywords or [])
    tags = list(metadata_tags or [])
    for heading, text in merged:
        for part in _split_long_text(text, max_chars):
            chunks.append(
                MarkdownChunk(
                    chunk_id=f"{rel_path}#{len(chunks)}",
                    rel_path=rel_path,
                    heading_path=heading,
                    text=part,
                    ordinal=len(chunks),
                    content_hash=_hash_text(part),
                    source_mtime=source_mtime,
                    metadata_keywords=keywords,
                    metadata_tags=tags,
                )
            )
    return chunks


def parse_markdown_document(memory_root: Path, path: Path) -> MarkdownDocument:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta_raw, body = parse_frontmatter(text)
    meta = meta_raw if isinstance(meta_raw, dict) else {}
    rel_path = normalize_relative_path(memory_root, path)
    keywords, tags = _extract_trigger(meta)
    description = str(meta.get("description") or "")
    retrieve_summary = str(meta.get("retrieve_summary") or description or "")
    chunks = split_heading_chunks(
        rel_path,
        body,
        source_mtime=path.stat().st_mtime,
        metadata_keywords=keywords,
        metadata_tags=tags,
    )
    if not chunks:
        chunks = split_heading_chunks(
            rel_path,
            path.name,
            source_mtime=path.stat().st_mtime,
            metadata_keywords=keywords,
            metadata_tags=tags,
        )
    return MarkdownDocument(
        rel_path=rel_path,
        meta=meta,
        description=description,
        retrieve_summary=retrieve_summary,
        keywords=keywords,
        tags=tags,
        authority=authority_for_path(rel_path),
        chunks=chunks,
    )


def corpus_markdown_paths(memory_root: Path) -> Iterable[Path]:
    for subdir in ("feedback", "knowledge", "fixes", "decisions", "docs", "rules", "agents"):
        root = memory_root / subdir
        if root.exists():
            yield from sorted(root.rglob("*.md"))
    root_agents = memory_root / "AGENTS.md"
    if root_agents.exists():
        yield root_agents


def scan_corpus(memory_root: Path) -> list[MarkdownDocument]:
    docs: list[MarkdownDocument] = []
    for path in corpus_markdown_paths(memory_root):
        try:
            doc = parse_markdown_document(memory_root, path)
        except Exception:
            raise
        status = str(doc.meta.get("status") or "active").strip().lower()
        if status == "deprecated":
            continue
        docs.append(doc)
    return docs
