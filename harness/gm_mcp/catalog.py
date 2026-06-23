"""Structured catalog and Python symbol index for gm_mcp navigation tools."""
from __future__ import annotations

import argparse
import ast
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import yaml

from harness.config import CLAUDE_HOME, CLAUDE_TASKS_ACTIVE, REPO_DIR
from harness.gm_mcp import rules as gm_rules

DATA_DIR = REPO_DIR / "harness" / "data"
CATALOG_PATH = DATA_DIR / "gm_catalog.json"
SYMBOLS_PATH = DATA_DIR / "gm_symbols.json"
TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+|[\u4e00-\u9fff]{2,}")
SKIP_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tmp", "build", "dist"}


def _rel(path: Path, repo_dir: Path = REPO_DIR) -> str:
    try:
        return path.resolve().relative_to(repo_dir.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    out = {item for item in TOKEN_RE.findall(lowered) if len(item) >= 2}
    for run in re.findall(r"[\u4e00-\u9fff]{3,}", lowered):
        for size in (2, 3, 4):
            for start in range(0, max(len(run) - size + 1, 0)):
                out.add(run[start : start + size])
    return out


def _read_text(path: Path, max_chars: int = 24000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _heading(path: Path) -> str:
    text = _read_text(path, max_chars=8000)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem


def _frontmatter_description(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end < 0:
        return ""
    try:
        data = yaml.safe_load(text[3:end])
    except Exception:
        return ""
    if isinstance(data, dict):
        return str(data.get("description") or data.get("name") or "")
    return ""


def _entry(
    *,
    type_: str,
    id_: str,
    name: str,
    path: str,
    title: str,
    summary: str,
    authority: str,
    keywords: Iterable[str] = (),
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "type": type_,
        "id": id_,
        "name": name,
        "path": path,
        "title": title,
        "summary": summary,
        "authority": authority,
        "keywords": sorted({str(x) for x in keywords if str(x).strip()}),
    }
    if extra:
        item.update(extra)
    return item


def _load_capability_manifest(repo_dir: Path) -> dict[str, Any]:
    path = repo_dir / "harness" / "capability_manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tasks_root() -> Path:
    registry = CLAUDE_HOME / "projects" / "project_registry.json"
    if registry.is_file():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
            raw = data.get("tasks_root")
            if raw:
                return Path(raw).expanduser()
        except Exception:
            pass
    return CLAUDE_TASKS_ACTIVE


def _module_entries(repo_dir: Path) -> list[dict[str, Any]]:
    specs = [
        ("rules", "Rules", "行为规则与分层契约；入口 rules/接入索引.md。", "rules/接入索引.md", ["规则", "契约", "rule"]),
        ("skills", "Skills", "可调用技能；每个 skill 的入口是 SKILL.md。", "skills/README.md", ["skill", "技能"]),
        ("harness", "Harness", "确定性脚本、hooks、MCP server、测试与治理工具。", "harness/README.md", ["script", "tool", "mcp", "测试"]),
        ("docs", "Docs", "人类可读说明、registry、capability 和生命周期文档。", "docs/scripts-registry.md", ["文档", "registry", "capability"]),
        ("agents", "Agents", "Agent 行为合同与角色说明。", "agents/CLAUDE.md", ["agent", "CLAUDE", "AGENTS"]),
        ("knowledge", "Knowledge", "沉淀知识与跨项目经验材料。", "knowledge", ["经验", "旧结论", "knowledge"]),
        ("quality", "Quality", "质量门、变更包和多视角 review 输出。", "quality", ["quality", "review", "gate"]),
    ]
    out = []
    for id_, title, summary, rel_path, keywords in specs:
        p = repo_dir / rel_path
        out.append(_entry(type_="module", id_=id_, name=id_, path=rel_path, title=title, summary=summary, authority="module_map", keywords=keywords, extra={"exists": p.exists()}))
    return out


def build_catalog(repo_dir: Path = REPO_DIR) -> dict[str, Any]:
    """Build a structured navigation catalog from authoritative repo files."""
    start = time.perf_counter()
    entries: list[dict[str, Any]] = []
    entries.extend(_module_entries(repo_dir))

    manifest = _load_capability_manifest(repo_dir)
    script_to_caps: dict[str, list[str]] = {}
    for cap in manifest.get("capabilities", []) if isinstance(manifest.get("capabilities"), list) else []:
        if not isinstance(cap, dict):
            continue
        cap_id = str(cap.get("id") or "")
        title = str(cap.get("title") or cap_id)
        boundary = str(cap.get("boundary") or cap.get("external_story") or "")
        entries.append(_entry(
            type_="capability",
            id_=cap_id,
            name=cap_id,
            path="harness/capability_manifest.json",
            title=title,
            summary=boundary,
            authority="capability_manifest",
            keywords=[cap_id, title, str(cap.get("status") or "")],
            extra={"status": cap.get("status"), "release_scope": cap.get("release_scope")},
        ))
        for script in cap.get("scripts", []) or []:
            script_rel = str(script)
            script_to_caps.setdefault(script_rel, []).append(cap_id)

    for script_rel, caps in sorted(script_to_caps.items()):
        p = repo_dir / "harness" / script_rel
        if not p.exists():
            p = repo_dir / script_rel
        entries.append(_entry(
            type_="script",
            id_=script_rel,
            name=Path(script_rel).name,
            path=_rel(p, repo_dir) if p.exists() else f"harness/{script_rel}",
            title=Path(script_rel).name,
            summary=f"Harness script registered under capabilities: {', '.join(caps)}.",
            authority="capability_manifest",
            keywords=[script_rel, Path(script_rel).stem, *caps],
            extra={"capabilities": caps, "exists": p.exists()},
        ))

    registry_path = repo_dir / "docs" / "scripts-registry.md"
    if registry_path.is_file():
        entries.append(_entry(
            type_="doc",
            id_="scripts-registry",
            name="scripts-registry",
            path="docs/scripts-registry.md",
            title="Scripts Registry",
            summary="harness/ 下脚本登记入口；新增 harness 脚本必须同步此表和 capability manifest。",
            authority="docs/scripts-registry.md",
            keywords=["新增 harness 脚本", "登记", "registry", "capability_manifest", "script"],
        ))

    capabilities_doc = repo_dir / "docs" / "capabilities.md"
    if capabilities_doc.is_file():
        entries.append(_entry(
            type_="doc",
            id_="capabilities-doc",
            name="capabilities",
            path="docs/capabilities.md",
            title="Capabilities",
            summary="capability_manifest 的人类可读入口。",
            authority="docs/capabilities.md",
            keywords=["capabilities", "能力", "manifest", "release_scope"],
        ))

    task_lifecycle = repo_dir / "docs" / "task-lifecycle.md"
    if task_lifecycle.is_file():
        entries.append(_entry(
            type_="doc",
            id_="task-lifecycle",
            name="task-lifecycle",
            path="docs/task-lifecycle.md",
            title="Task Lifecycle",
            summary="work task 创建、继续、归档和 v2 结构的生命周期入口。",
            authority="docs/task-lifecycle.md",
            keywords=["work", "继续任务", "task", "生命周期", "HANDOFF", "STATUS"],
        ))

    for skill_md in sorted((repo_dir / "skills").glob("*/SKILL.md")):
        text = _read_text(skill_md, max_chars=12000)
        name = skill_md.parent.name
        desc = _frontmatter_description(text) or _heading(skill_md)
        entries.append(_entry(
            type_="skill",
            id_=name,
            name=name,
            path=_rel(skill_md, repo_dir),
            title=_heading(skill_md),
            summary=desc,
            authority="skill_entrypoint",
            keywords=[name, desc, "skill", "SKILL.md"],
        ))

    for rule_doc in sorted((repo_dir / "rules").glob("*.md")):
        entries.append(_entry(
            type_="rule_doc",
            id_=rule_doc.stem,
            name=rule_doc.stem,
            path=_rel(rule_doc, repo_dir),
            title=_heading(rule_doc),
            summary=f"规则文档：{_heading(rule_doc)}。",
            authority="rules_doc",
            keywords=[rule_doc.stem, "规则", "rule", _heading(rule_doc)],
        ))

    for agent_doc in sorted((repo_dir / "agents").glob("*.md")):
        entries.append(_entry(
            type_="agent",
            id_=agent_doc.stem,
            name=agent_doc.stem,
            path=_rel(agent_doc, repo_dir),
            title=_heading(agent_doc),
            summary=f"Agent 入口：{_heading(agent_doc)}。",
            authority="agent_doc",
            keywords=[agent_doc.stem, "agent", _heading(agent_doc)],
        ))

    try:
        for rule in gm_rules.load_rules():
            entries.append(_entry(
                type_="rule",
                id_=rule.rule_id,
                name=rule.rule_id,
                path="harness/gm_mcp/rules.yaml",
                title=rule.title,
                summary=rule.summary,
                authority="rules_yaml",
                keywords=[rule.rule_id, rule.title, *rule.topics, *rule.aliases],
                extra={"verdict": rule.verdict, "sources": [s.source_path for s in rule.sources]},
            ))
    except Exception:
        pass

    root = _tasks_root()
    if root.is_dir():
        for task_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
            reads = [task_dir / "core" / x for x in ("INDEX.md", "STATUS.md", "HANDOFF.md")]
            existing = [p for p in reads if p.is_file()]
            summary = "Active work task."
            for p in existing:
                h = _heading(p)
                if h:
                    summary = h
                    break
            entries.append(_entry(
                type_="task",
                id_=task_dir.name,
                name=task_dir.name,
                path=str(task_dir),
                title=task_dir.name,
                summary=summary,
                authority="project_registry/tasks_root",
                keywords=[task_dir.name, "task", "HANDOFF", "STATUS"],
                extra={"min_reads": [str(p) for p in existing[:3]], "exists": True},
            ))

    elapsed = round((time.perf_counter() - start) * 1000.0, 3)
    return {
        "schema_version": 1,
        "kind": "gm_catalog",
        "repo_dir": str(repo_dir),
        "generated_at_ms": elapsed,
        "entries": entries,
        "diagnostics": {"entry_count": len(entries), "catalog_path": str(CATALOG_PATH)},
    }


def save_catalog(path: Path = CATALOG_PATH, repo_dir: Path = REPO_DIR) -> dict[str, Any]:
    payload = build_catalog(repo_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return payload


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    # Build live so uncommitted task/skill changes are visible; data file is a reproducible cache artifact.
    return build_catalog(REPO_DIR)


def catalog_summary(result: dict[str, Any]) -> dict[str, Any]:
    items = result.get("min_reads") or result.get("results") or []
    top_refs = [str(item.get("path")) for item in items[:3] if isinstance(item, dict)]
    top_ids = [str(item.get("id") or item.get("name")) for item in items[:3] if isinstance(item, dict)]
    return {
        "hit": bool(result.get("hit")),
        "count": int(result.get("count") or len(items)),
        "top_refs": top_refs,
        "top_ids": top_ids,
        "confidence": float(result.get("confidence") or 0.0),
        "low_confidence": bool(result.get("low_confidence")),
        "returned_summary": str(result.get("summary") or "")[:500],
    }


def _score_entry(entry: dict[str, Any], query: str, q_tokens: set[str]) -> float:
    hay = " ".join(str(entry.get(k) or "") for k in ("id", "name", "title", "summary", "path", "type"))
    hay += " " + " ".join(str(x) for x in entry.get("keywords") or [])
    tokens = _tokens(hay)
    score = len(q_tokens & tokens) * 2.0
    lowered = query.lower()
    for key in [entry.get("id"), entry.get("name"), entry.get("title")]:
        key_l = str(key or "").lower()
        if key_l and key_l in lowered:
            score += 8.0
    path_l = str(entry.get("path") or "").lower()
    if any(tok in path_l for tok in q_tokens):
        score += 1.5
    return score


def _curated_locate_boost(entry: dict[str, Any], query: str) -> float:
    q = query.lower()
    path = str(entry.get("path") or "").lower()
    id_ = str(entry.get("id") or "").lower()
    score = 0.0
    if ("work" in q or "任务" in q) and ("继续" in q or "handoff" in q or "status" in q):
        if id_ == "work" and entry.get("type") == "skill":
            score += 20
        if path == "docs/task-lifecycle.md":
            score += 14
        if path.endswith("work_context_pack.py"):
            score += 10
    if ("新增" in q or "new" in q) and ("harness" in q or "脚本" in q or "script" in q):
        if path == "docs/scripts-registry.md":
            score += 20
        if path == "harness/capability_manifest.json":
            score += 18
        if path == "docs/capabilities.md":
            score += 12
    if "核心模块" in q or "有哪些模块" in q or "module" in q:
        if entry.get("type") == "module":
            score += 12
    return score


def locate(query: str, *, kind: str | None = None, max_reads: int = 3) -> dict[str, Any]:
    start = time.perf_counter()
    clean = query.strip()
    if not clean:
        raise ValueError("query must not be empty")
    max_reads = max(1, min(int(max_reads), 10))
    catalog = load_catalog()
    entries = [e for e in catalog.get("entries", []) if isinstance(e, dict)]
    if kind:
        entries = [e for e in entries if str(e.get("type")) == kind]
    q_tokens = _tokens(clean)
    scored = []
    for entry in entries:
        score = _score_entry(entry, clean, q_tokens) + _curated_locate_boost(entry, clean)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("path")), str(item[1].get("id"))))
    min_reads = []
    seen_paths: set[str] = set()
    for score, entry in scored:
        path = str(entry.get("path") or "")
        if not path or path in seen_paths:
            continue
        p = Path(path)
        exists = p.exists() if p.is_absolute() else (REPO_DIR / path).exists()
        min_reads.append({
            "type": entry.get("type"),
            "id": entry.get("id"),
            "title": entry.get("title"),
            "path": path,
            "summary": entry.get("summary"),
            "authority": entry.get("authority"),
            "reason": f"catalog score {round(score, 3)} for query terms",
            "exists": exists,
        })
        seen_paths.add(path)
        if len(min_reads) >= max_reads:
            break
    confidence = min(1.0, scored[0][0] / 12.0) if scored else 0.0
    return {
        "tool": "gm.locate",
        "query": clean,
        "kind": kind,
        "hit": bool(min_reads),
        "count": len(min_reads),
        "confidence": round(confidence, 3),
        "low_confidence": confidence < 0.4,
        "authority": "catalog",
        "fallback_used": False,
        "min_reads": min_reads,
        "summary": f"{len(min_reads)} minimal read(s) from structured catalog.",
        "diagnostics": {"entry_count": len(entries), "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3)},
    }


@dataclass
class _Symbol:
    name: str
    qualname: str
    kind: str
    path: str
    start_line: int
    end_line: int
    signature: str
    docstring: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualname": self.qualname,
            "kind": self.kind,
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "location": f"{self.path}:{self.start_line}-{self.end_line}",
            "docstring": self.docstring,
            "exists": (REPO_DIR / self.path).is_file(),
        }


def _skip_path(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _signature(node: ast.AST) -> str:
    if isinstance(node, ast.ClassDef):
        bases = [ast.unparse(base) for base in node.bases]
        return f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        try:
            args = ast.unparse(node.args)
        except Exception:
            args = "..."
        return f"{prefix} {node.name}({args})"
    return ""


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, repo_dir: Path):
        self.path = path
        self.repo_dir = repo_dir
        self.stack: list[str] = []
        self.items: list[_Symbol] = []

    def _add(self, node: ast.AST, kind: str, name: str) -> None:
        qual = ".".join([*self.stack, name]) if self.stack else name
        self.items.append(_Symbol(
            name=name,
            qualname=qual,
            kind=kind,
            path=_rel(self.path, self.repo_dir),
            start_line=int(getattr(node, "lineno", 1)),
            end_line=int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
            signature=_signature(node),
            docstring=ast.get_docstring(node) or "",
        ))

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._add(node, "class", node.name)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        kind = "method" if self.stack else "function"
        self._add(node, kind, node.name)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        kind = "async_method" if self.stack else "async_function"
        self._add(node, kind, node.name)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def build_symbols(repo_dir: Path = REPO_DIR) -> dict[str, Any]:
    start = time.perf_counter()
    symbols: list[dict[str, Any]] = []
    for path in sorted(repo_dir.rglob("*.py")):
        if _skip_path(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        visitor = _SymbolVisitor(path, repo_dir)
        visitor.visit(tree)
        symbols.extend(item.as_dict() for item in visitor.items)
    return {
        "schema_version": 1,
        "kind": "gm_symbols",
        "repo_dir": str(repo_dir),
        "symbols": symbols,
        "diagnostics": {"symbol_count": len(symbols), "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3), "symbols_path": str(SYMBOLS_PATH)},
    }


def save_symbols(path: Path = SYMBOLS_PATH, repo_dir: Path = REPO_DIR) -> dict[str, Any]:
    payload = build_symbols(repo_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return payload


@lru_cache(maxsize=1)
def load_symbols() -> dict[str, Any]:
    return build_symbols(REPO_DIR)


def symbol(name: str, *, kind: str | None = None, module: str | None = None) -> dict[str, Any]:
    start = time.perf_counter()
    clean = name.strip()
    if not clean:
        raise ValueError("symbol name must not be empty")
    payload = load_symbols()
    items = [s for s in payload.get("symbols", []) if isinstance(s, dict)]
    if kind:
        items = [s for s in items if str(s.get("kind")) == kind]
    if module:
        mod_l = module.lower()
        items = [s for s in items if mod_l in str(s.get("path") or "").lower()]
    exact = [s for s in items if clean in {str(s.get("name")), str(s.get("qualname"))}]
    matches = exact or [s for s in items if clean.lower() in str(s.get("qualname") or "").lower()]
    matches = sorted(matches, key=lambda s: (str(s.get("path")), int(s.get("start_line") or 0)))[:20]
    return {
        "tool": "gm.symbol",
        "query": clean,
        "kind": kind,
        "module": module,
        "hit": bool(matches),
        "count": len(matches),
        "authority": "python_ast",
        "fallback_used": False,
        "results": matches,
        "summary": f"{len(matches)} Python symbol match(es).",
        "diagnostics": {"symbol_count": len(items), "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3)},
    }


def inspect_object(type_: str, *, name: str | None = None, id_: str | None = None) -> dict[str, Any]:
    start = time.perf_counter()
    clean_type = type_.strip()
    key = (id_ or name or "").strip()
    if not clean_type:
        raise ValueError("type must not be empty")
    entries = [e for e in load_catalog().get("entries", []) if isinstance(e, dict) and str(e.get("type")) == clean_type]
    if key:
        key_l = key.lower()
        matches = [e for e in entries if key_l in {str(e.get("id") or "").lower(), str(e.get("name") or "").lower()}]
        if not matches:
            matches = [e for e in entries if key_l in " ".join(str(e.get(k) or "") for k in ("id", "name", "title", "path")).lower()]
    else:
        matches = entries[:20]
    results = []
    for e in matches[:20]:
        path = str(e.get("path") or "")
        p = Path(path)
        exists = p.exists() if p.is_absolute() else (REPO_DIR / path).exists()
        results.append({**e, "exists": exists})
    return {
        "tool": "gm.inspect",
        "query": f"{clean_type}:{key}" if key else clean_type,
        "type": clean_type,
        "name": name,
        "id": id_,
        "hit": bool(results),
        "count": len(results),
        "authority": "catalog",
        "fallback_used": False,
        "results": results,
        "summary": f"{len(results)} catalog object(s) for type={clean_type}.",
        "diagnostics": {"elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3)},
    }


def map_modules() -> dict[str, Any]:
    entries = [e for e in load_catalog().get("entries", []) if isinstance(e, dict) and e.get("type") == "module"]
    modules = [{
        "id": e.get("id"),
        "title": e.get("title"),
        "path": e.get("path"),
        "summary": e.get("summary"),
        "authority": e.get("authority"),
        "exists": e.get("exists"),
    } for e in entries]
    return {
        "tool": "gm.map",
        "query": "global-memory modules",
        "hit": True,
        "count": len(modules),
        "authority": "module_map",
        "fallback_used": False,
        "modules": modules,
        "summary": "Top-level global-memory module map from structured catalog.",
        "diagnostics": {"entry_count": len(entries)},
    }


def validate_catalog_paths(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = catalog or load_catalog()
    missing = []
    checked = 0
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if not path:
            continue
        if path.startswith("D:/") or re.match(r"^[A-Za-z]:", path):
            p = Path(path)
        else:
            p = REPO_DIR / path
        checked += 1
        if not p.exists():
            missing.append(path)
    return {"checked": checked, "missing": missing, "ok": not missing}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.gm_mcp.catalog")
    parser.add_argument("--write", action="store_true", help="write harness/data/gm_catalog.json and gm_symbols.json")
    parser.add_argument("--validate", action="store_true", help="validate catalog paths")
    args = parser.parse_args(argv)
    if args.write:
        catalog = save_catalog()
        symbols = save_symbols()
        print(json.dumps({"catalog_entries": len(catalog["entries"]), "symbols": len(symbols["symbols"]), "catalog_path": str(CATALOG_PATH), "symbols_path": str(SYMBOLS_PATH)}, ensure_ascii=False, indent=2))
        return 0
    if args.validate:
        print(json.dumps(validate_catalog_paths(), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"catalog": build_catalog()["diagnostics"], "symbols": build_symbols()["diagnostics"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
