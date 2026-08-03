"""Source registry helpers for semantic corpus scanning."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from harness.config import HARNESS_DIR, MEMORY_ROOT

DEFAULT_SOURCE_MANIFEST = HARNESS_DIR / "semantic" / "sources.yaml"


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    root: Path
    enabled: bool = True
    source_type: str = "canonical_memory"
    priority: int = 100
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "root": str(self.root),
            "enabled": self.enabled,
            "source_type": self.source_type,
            "priority": self.priority,
            "include": list(self.include),
            "exclude": list(self.exclude),
        }


@dataclass(frozen=True)
class SourceFile:
    source: SourceDefinition
    path: Path
    source_rel_path: str


def default_global_memory_source(memory_root: Path = MEMORY_ROOT) -> SourceDefinition:
    return SourceDefinition(
        id="global-memory",
        root=memory_root,
        enabled=True,
        source_type="canonical_memory",
        priority=100,
        include=(
            "feedback/**/*.md",
            "knowledge/**/*.md",
            "fixes/**/*.md",
            "decisions/**/*.md",
            "docs/**/*.md",
            "rules/**/*.md",
            "agents/**/*.md",
            "AGENTS.md",
        ),
        exclude=("**/_archive/**", "**/.git/**"),
    )


def _as_pattern_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).replace("\\", "/").strip() for item in value if str(item).strip())
    text = str(value).replace("\\", "/").strip()
    return (text,) if text else ()


def _source_from_raw(raw: dict[str, Any], *, fallback_root: Path) -> SourceDefinition:
    source_id = str(raw.get("id") or "").strip()
    if not source_id:
        raise ValueError("source id is required")
    root_raw = raw.get("root") or fallback_root
    return SourceDefinition(
        id=source_id,
        root=Path(str(root_raw)).expanduser(),
        enabled=bool(raw.get("enabled", True)),
        source_type=str(raw.get("source_type") or "external_docs"),
        priority=int(raw.get("priority", 0)),
        include=_as_pattern_tuple(raw.get("include")),
        exclude=_as_pattern_tuple(raw.get("exclude")),
    )


def load_source_registry(
    *,
    memory_root: Path = MEMORY_ROOT,
    manifest_path: Path | None = None,
) -> list[SourceDefinition]:
    """Load semantic sources.

    The default call remains backward-compatible for tests and callers that pass
    a temporary memory_root: only the real MEMORY_ROOT reads the repository
    manifest automatically. Explicit manifest_path always opts into manifest
    loading.
    """
    explicit_manifest = manifest_path is not None
    manifest = manifest_path or DEFAULT_SOURCE_MANIFEST
    use_manifest = manifest.exists() and (explicit_manifest or memory_root.resolve() == MEMORY_ROOT.resolve())
    if not use_manifest:
        return [default_global_memory_source(memory_root)]
    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    raw_sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(raw_sources, list):
        raise ValueError(f"source manifest must contain a sources list: {manifest}")
    return [_source_from_raw(raw, fallback_root=memory_root) for raw in raw_sources if isinstance(raw, dict)]


def write_source_registry(sources: Iterable[SourceDefinition], *, manifest_path: Path = DEFAULT_SOURCE_MANIFEST) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"sources": [source.to_dict() for source in sources]}
    manifest_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def add_source_to_manifest(
    *,
    source_id: str,
    root: Path,
    include: Iterable[str],
    manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
    enabled: bool = True,
    source_type: str = "external_docs",
    priority: int = 50,
    exclude: Iterable[str] = (),
) -> list[SourceDefinition]:
    sources = load_source_registry(manifest_path=manifest_path) if manifest_path.exists() else [default_global_memory_source(MEMORY_ROOT)]
    if any(source.id == source_id for source in sources):
        raise ValueError(f"duplicate source id: {source_id}")
    updated = [
        *sources,
        SourceDefinition(
            id=source_id,
            root=root,
            enabled=enabled,
            source_type=source_type,
            priority=priority,
            include=tuple(include),
            exclude=tuple(exclude),
        ),
    ]
    write_source_registry(updated, manifest_path=manifest_path)
    return updated


def _matches(pattern: str, rel_path: str) -> bool:
    pattern = pattern.replace("\\", "/")
    candidates = [pattern]
    if pattern.startswith("**/"):
        candidates.append(pattern[3:])
    return any(fnmatch.fnmatchcase(rel_path, candidate) for candidate in candidates)


def matches_any(patterns: Iterable[str], rel_path: str) -> bool:
    return any(_matches(pattern, rel_path) for pattern in patterns)


def source_rel_path(source: SourceDefinition, path: Path) -> str:
    # Keep the registry path logical instead of resolving reparse points.  Some
    # task directories under D:/ClaudeTasks/active are junctions; resolving them
    # can point outside the source root even though the served path is still in
    # scope.  Paths arrive from root.glob(), so lexical containment is the
    # stable contract we want to preserve in the index pointer.
    rel = path.absolute().relative_to(source.root.absolute()).as_posix()
    if rel.startswith("../") or rel == "..":
        raise ValueError(f"Unsafe source relative path: {rel}")
    return rel


def scan_source_files(sources: Iterable[SourceDefinition]) -> list[SourceFile]:
    files: dict[tuple[str, str], SourceFile] = {}
    for source in sources:
        if not source.enabled or not source.include:
            continue
        root = source.root
        if not root.exists():
            continue
        for pattern in source.include:
            for path in root.glob(pattern):
                if not path.is_file():
                    continue
                rel = source_rel_path(source, path)
                if matches_any(source.exclude, rel):
                    continue
                files[(source.id, rel)] = SourceFile(source=source, path=path, source_rel_path=rel)
    return [files[key] for key in sorted(files)]


def validate_source_registry(sources: Iterable[SourceDefinition]) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    source_rows: list[dict[str, object]] = []
    for source in sources:
        if source.id in seen:
            errors.append(f"duplicate source id: {source.id}")
        seen.add(source.id)
        if not source.root.exists():
            errors.append(f"source root does not exist: {source.id} -> {source.root}")
        if source.enabled and not source.include:
            errors.append(f"enabled source has empty include: {source.id}")
        if not source.enabled:
            warnings.append(f"source disabled: {source.id}")
        source_rows.append(source.to_dict())
    return {"ok": not errors, "errors": errors, "warnings": warnings, "sources": source_rows}
