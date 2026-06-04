#!/usr/bin/env python3
"""quality_gate.py — risk-tiered gate for AI-generated code changes.

This is intentionally client-neutral. Claude Code hooks, Codex instructions,
pre-commit hooks, and CI can all call the same read-only verifier.
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

HARNESS_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = HARNESS_DIR.parent
DEFAULT_CONFIG = REPO_DIR / "quality_gate.yaml"
SCHEMA_VERSION = 1
REVIEW_KINDS = ("correctness", "test-quality", "risk-security", "maintainability")
REVIEW_VERDICTS = {"PASS", "WARN", "BLOCK"}
REVIEW_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
REVIEW_REQUIRED_SECTIONS = ("Blocking", "Warnings", "Missing tests", "Need human decision")
# Tier2 强证据门:test-quality review 额外必须给出非空"红证据"+"变异/测试质量结论"。
# 防 AI 写全绿假测试(mock 切错误路径、同义反复断言)。详见
# feedback/ai-test-failure-modes-four-defenses.md。可在 quality_gate.yaml
# evidence.test_quality_red_evidence: false 关闭。
REVIEW_EXTRA_REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    "test-quality": ("Red-Evidence", "Mutation"),
}


DEFAULT_CONFIG_DATA: dict[str, Any] = {
    "thresholds": {
        "tier1_max_files": 3,
        "tier1_max_lines": 200,
        "tier2_max_files": 10,
        "tier2_max_lines": 800,
    },
    "risk_paths": {
        "tier3": [
            ".claude/**",
            ".github/**",
            "harness/hooks/**",
            "harness/scripts/gate_check.py",
            "harness/scripts/quality_gate.py",
            "harness/maintain.py",
            "harness/_lib.py",
            "**/migration/**",
            "**/migrations/**",
            "**/deploy/**",
        ],
        "tier2": ["harness/**/*.py", "skills/**/*.py", "agents/**/*.md", "bootstrap.py"],
    },
    "doc_patterns": [
        "*.md",
        "docs/**",
        "feedback/**",
        "knowledge/**",
        "fixes/**",
        "decisions/**",
        "templates/**",
    ],
    "test_patterns": ["test/**", "tests/**", "harness/tests/**", "**/test_*.py", "**/*_test.py"],
    "generated_patterns": ["**/__pycache__/**", "**/*.pyc", "harness/build/**", "harness/dist/**", ".pytest_cache/**"],
    "evidence": {
        "verification_files": ["quality/verification.md", "test/测试.md"],
        "review_dir": "quality/reviews",
        "test_quality_red_evidence": True,
    },
}


@dataclass
class ChangeSet:
    files: set[str] = field(default_factory=set)
    added_lines: int = 0
    deleted_lines: int = 0
    deleted_files: set[str] = field(default_factory=set)
    untracked_files: set[str] = field(default_factory=set)

    @property
    def changed_lines(self) -> int:
        return self.added_lines + self.deleted_lines


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(base, ensure_ascii=False))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return DEFAULT_CONFIG_DATA
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            return deep_merge(DEFAULT_CONFIG_DATA, data)
    except Exception:
        pass
    return DEFAULT_CONFIG_DATA


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def parse_numstat(text: str, changes: ChangeSet) -> None:
    for raw in text.splitlines():
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        add_s, del_s, path = parts[0], parts[1], parts[-1]
        changes.files.add(normalize_path(path))
        if add_s != "-":
            changes.added_lines += int(add_s or 0)
        if del_s != "-":
            changes.deleted_lines += int(del_s or 0)


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def collect_changes(repo: Path, include_untracked: bool = True, pathspecs: list[str] | None = None) -> ChangeSet:
    changes = ChangeSet()
    path_args = ["--", *pathspecs] if pathspecs else []
    for args in (["diff", "--numstat"], ["diff", "--cached", "--numstat"]):
        args = [*args, *path_args]
        proc = run_git(repo, args)
        if proc.returncode == 0:
            parse_numstat(proc.stdout, changes)

    for args in (["diff", "--name-status"], ["diff", "--cached", "--name-status"]):
        args = [*args, *path_args]
        proc = run_git(repo, args)
        if proc.returncode != 0:
            continue
        for raw in proc.stdout.splitlines():
            parts = raw.split("\t")
            if len(parts) >= 2 and parts[0].startswith("D"):
                changes.deleted_files.add(normalize_path(parts[1]))

    if include_untracked:
        proc = run_git(repo, ["ls-files", "--others", "--exclude-standard"])
        if proc.returncode == 0:
            for raw in proc.stdout.splitlines():
                rel = normalize_path(raw)
                if not rel:
                    continue
                if pathspecs and not path_matches_pathspecs(rel, pathspecs):
                    continue
                changes.files.add(rel)
                changes.untracked_files.add(rel)
                target = repo / rel
                if target.is_file():
                    try:
                        changes.added_lines += min(1000, len(target.read_text(encoding="utf-8", errors="replace").splitlines()))
                    except Exception:
                        changes.added_lines += 1
    return changes


def path_matches_pathspecs(path: str, pathspecs: list[str]) -> bool:
    path = normalize_path(path)
    for spec in pathspecs:
        spec = normalize_path(spec).rstrip("/")
        if not spec:
            continue
        if path == spec or path.startswith(spec + "/") or fnmatch.fnmatch(path, spec):
            return True
        if any(ch in spec for ch in "*?[") and fnmatch.fnmatch(path, spec):
            return True
    return False


def match_any(path: str, patterns: list[str]) -> bool:
    path = normalize_path(path)
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        # Treat dir/**/*.ext as matching files directly under dir/ as well as
        # deeper descendants. fnmatch does not do that by default on Windows.
        if "/**/" in pattern and fnmatch.fnmatch(path, pattern.replace("/**/", "/")):
            return True
    return False


def is_generated(path: str, config: dict[str, Any]) -> bool:
    return match_any(path, list(config.get("generated_patterns", [])))


def effective_files(changes: ChangeSet, config: dict[str, Any]) -> list[str]:
    return sorted(p for p in changes.files if p and not is_generated(p, config))


def classify(changes: ChangeSet, config: dict[str, Any]) -> dict[str, Any]:
    files = effective_files(changes, config)
    thresholds = config.get("thresholds", {})
    reasons: list[str] = []
    required_reviews: list[str] = []
    required_checks: list[str] = ["verification-summary"]

    if not files:
        return {
            "tier": 0,
            "label": "no-change",
            "reasons": ["no effective changed files"],
            "required_checks": [],
            "required_reviews": [],
            "requires_test_evidence": False,
            "requires_human_decision": False,
        }

    if all(match_any(p, list(config.get("doc_patterns", []))) for p in files):
        return {
            "tier": 0,
            "label": "docs-or-text-only",
            "reasons": ["all effective files match doc/text patterns"],
            "required_checks": required_checks,
            "required_reviews": [],
            "requires_test_evidence": False,
            "requires_human_decision": False,
        }

    tier = 1
    label = "small-code-change"
    file_count = len(files)
    line_count = changes.changed_lines
    reasons.extend([f"files={file_count}", f"changed_lines={line_count}"])

    risk_paths = config.get("risk_paths", {})
    if any(match_any(p, list(risk_paths.get("tier3", []))) for p in files):
        tier = 3
        label = "high-risk-path"
        reasons.append("tier3 risk path touched")
    elif any(match_any(p, list(risk_paths.get("tier2", []))) for p in files):
        tier = max(tier, 2)
        label = "behavior-or-shared-code"
        reasons.append("tier2 risk path touched")

    if changes.deleted_files:
        tier = max(tier, 2)
        reasons.append(f"deleted_files={len(changes.deleted_files)}")

    if file_count > int(thresholds.get("tier2_max_files", 10)) or line_count > int(thresholds.get("tier2_max_lines", 800)):
        tier = 3
        label = "large-or-broad-change"
        reasons.append("exceeds tier2 threshold")
    elif file_count > int(thresholds.get("tier1_max_files", 3)) or line_count > int(thresholds.get("tier1_max_lines", 200)):
        tier = max(tier, 2)
        if label == "small-code-change":
            label = "medium-change"
        reasons.append("exceeds tier1 threshold")

    if tier >= 1:
        required_checks.append("deterministic-checks")
    if tier >= 2:
        required_checks.append("test-evidence")
        required_reviews.extend(["correctness", "test-quality"])
    if tier >= 3:
        required_checks.extend(["human-decision", "rollback-or-recovery"])
        required_reviews = list(REVIEW_KINDS)

    return {
        "tier": tier,
        "label": label,
        "reasons": reasons,
        "required_checks": required_checks,
        "required_reviews": required_reviews,
        "requires_test_evidence": tier >= 2,
        "requires_human_decision": tier >= 3,
    }


def read_text(path: Path, limit: int = 20000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def evidence_state(repo: Path, changes: ChangeSet, config: dict[str, Any], review_dir: str | None = None) -> dict[str, Any]:
    files = effective_files(changes, config)
    test_patterns = list(config.get("test_patterns", []))
    changed_tests = [p for p in files if match_any(p, test_patterns)]

    evidence_cfg = config.get("evidence", {})
    verification_files = [repo / p for p in evidence_cfg.get("verification_files", [])]
    verification_hits: list[str] = []
    verification_text = ""
    for path in verification_files:
        if path.exists():
            verification_hits.append(str(path.relative_to(repo)))
            verification_text += "\n" + read_text(path)

    review_root_arg = Path(review_dir or evidence_cfg.get("review_dir", "quality/reviews"))
    review_root = review_root_arg if review_root_arg.is_absolute() else repo / review_root_arg
    extra_required = (
        REVIEW_EXTRA_REQUIRED_SECTIONS
        if evidence_cfg.get("test_quality_red_evidence", True)
        else {}
    )
    reviews: dict[str, dict[str, Any]] = {}
    for kind in REVIEW_KINDS:
        path = review_root / f"{kind}.md"
        if path.exists():
            parsed = parse_review_result(read_text(path), extra_required.get(kind, ()))
        else:
            parsed = {
                "verdict": "",
                "confidence": "",
                "format_errors": [],
                "sections": {section: False for section in REVIEW_REQUIRED_SECTIONS},
            }
        reviews[kind] = {
            "exists": path.exists(),
            "path": display_path(path, repo),
            "verdict": parsed["verdict"],
            "confidence": parsed["confidence"],
            "format_errors": parsed["format_errors"],
            "sections": parsed["sections"],
            "has_block": parsed["verdict"] == "BLOCK",
        }

    return {
        "changed_tests": changed_tests,
        "verification_files": verification_hits,
        "verification_mentions_test": any(word in verification_text.lower() for word in ("test", "测试", "验证", "smoke", "compile")),
        "verification_mentions_human_decision": any(word in verification_text for word in ("人工裁决", "human decision", "接受风险", "accepted risk")),
        "verification_mentions_rollback": any(word in verification_text.lower() for word in ("rollback", "回滚", "恢复", "recovery")),
        "reviews": reviews,
    }


def parse_review_result(text: str, extra_required_sections: tuple[str, ...] = ()) -> dict[str, Any]:
    verdict = ""
    confidence = ""
    all_required = REVIEW_REQUIRED_SECTIONS + tuple(extra_required_sections)
    sections: dict[str, bool] = {section: False for section in all_required}
    section_lines: dict[str, list[str]] = {section: [] for section in all_required}
    current_section = ""

    for raw in text.splitlines():
        line = raw.strip()
        lower = line.lower()
        if lower.startswith("verdict:"):
            verdict = line.split(":", 1)[1].strip().upper()
            current_section = ""
            continue
        if lower.startswith("confidence:"):
            confidence = line.split(":", 1)[1].strip().upper()
            current_section = ""
            continue
        matched_section = ""
        for section in all_required:
            if lower == f"{section.lower()}:":
                matched_section = section
                break
        if matched_section:
            sections[matched_section] = True
            current_section = matched_section
            continue
        if current_section and line:
            section_lines[current_section].append(line)

    errors: list[str] = []
    if not verdict:
        errors.append("missing verdict")
    elif verdict not in REVIEW_VERDICTS:
        errors.append(f"invalid verdict `{verdict}`")

    if not confidence:
        errors.append("missing confidence")
    elif confidence not in REVIEW_CONFIDENCE:
        errors.append(f"invalid confidence `{confidence}`")

    for section, present in sections.items():
        if not present:
            errors.append(f"missing section `{section}`")

    if verdict == "BLOCK" and not has_real_section_item(section_lines["Blocking"]):
        errors.append("BLOCK verdict requires at least one Blocking item")

    # kind 专属强证据 section(如 test-quality 的 Red-Evidence/Mutation)写 none/空 = 没写。
    for section in extra_required_sections:
        if sections.get(section) and not has_concrete_evidence(section_lines[section]):
            errors.append(f"section `{section}` requires a concrete entry")

    return {
        "verdict": verdict if verdict in REVIEW_VERDICTS else "",
        "confidence": confidence if confidence in REVIEW_CONFIDENCE else "",
        "sections": sections,
        "format_errors": errors,
    }


def has_real_section_item(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped in {"-", "- ...", "..."}:
            continue
        if stripped.startswith("-") and len(stripped.strip("- ").strip()) > 0:
            return True
        if stripped.lower() not in {"none", "n/a", "无"}:
            return True
    return False


# 比 has_real_section_item 更严:`- none` 这种占位也算空。用于强证据 section
# (Red-Evidence/Mutation),那里写 none 等于没写。
def has_concrete_evidence(lines: list[str]) -> bool:
    for line in lines:
        body = line.strip().lstrip("-").strip()
        if not body or body in {"..."}:
            continue
        if body.lower() in {"none", "n/a", "无", "na", "tbd", "todo"}:
            continue
        return True
    return False


def verify_plan(plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    blocking: list[str] = []
    tier = int(plan["tier"])

    if "verification-summary" in plan["required_checks"] and not evidence["verification_files"]:
        missing.append("verification-summary")

    if plan["requires_test_evidence"]:
        has_test_evidence = bool(evidence["changed_tests"]) or evidence["verification_mentions_test"]
        if not has_test_evidence:
            missing.append("test-evidence")

    if plan["requires_human_decision"] and not evidence["verification_mentions_human_decision"]:
        missing.append("human-decision")
    if plan["requires_human_decision"] and not evidence["verification_mentions_rollback"]:
        missing.append("rollback-or-recovery")

    for kind in plan["required_reviews"]:
        item = evidence["reviews"][kind]
        if not item["exists"]:
            missing.append(f"review:{kind}")
        elif item.get("format_errors"):
            missing.append(f"review-format:{kind}")
        elif not item["verdict"]:
            missing.append(f"review:{kind}")
        elif item["has_block"]:
            blocking.append(f"review:{kind}")

    if blocking:
        verdict = "BLOCK"
    elif missing and tier >= 2:
        verdict = "BLOCK"
    elif missing:
        verdict = "WARN"
    else:
        verdict = "PASS"
    return {"verdict": verdict, "missing": missing, "blocking": blocking}


def build_report(
    repo: Path,
    config_path: Path,
    include_untracked: bool,
    review_dir: str | None = None,
    pathspecs: list[str] | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    changes = collect_changes(repo, include_untracked=include_untracked, pathspecs=pathspecs)
    files = effective_files(changes, config)
    plan = classify(changes, config)
    evidence = evidence_state(repo, changes, config, review_dir)
    verification = verify_plan(plan, evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "ai_code_quality_gate",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(repo),
        "config": str(config_path),
        "pathspecs": pathspecs or [],
        "change_summary": {
            "files": len(files),
            "changed_lines": changes.changed_lines,
            "added_lines": changes.added_lines,
            "deleted_lines": changes.deleted_lines,
            "deleted_files": sorted(changes.deleted_files),
            "untracked_files": sorted(changes.untracked_files),
            "sample_files": files[:50],
        },
        "plan": plan,
        "evidence": evidence,
        "verdict": verification["verdict"],
        "missing": verification["missing"],
        "blocking": verification["blocking"],
        "next_action": next_action(verification["verdict"], verification["missing"], plan),
    }


def next_action(verdict: str, missing: list[str], plan: dict[str, Any]) -> str:
    if verdict == "PASS":
        return "Continue; quality gate evidence is present for this risk tier."
    if missing:
        return "Add missing evidence: " + ", ".join(missing)
    if plan["tier"] >= 2:
        return "Resolve blocking review findings before continuing."
    return "Record validation evidence or accept the warning explicitly."


def emit_text(report: dict[str, Any]) -> None:
    plan = report["plan"]
    summary = report["change_summary"]
    print("=" * 64)
    print("quality_gate")
    print("=" * 64)
    print(f"verdict: {report['verdict']}")
    print(f"tier:    {plan['tier']} ({plan['label']})")
    print(f"files:   {summary['files']}  changed_lines: {summary['changed_lines']}")
    print("reasons:")
    for item in plan["reasons"]:
        print(f"  - {item}")
    if plan["required_checks"]:
        print("required checks: " + ", ".join(plan["required_checks"]))
    if plan["required_reviews"]:
        print("required reviews: " + ", ".join(plan["required_reviews"]))
    if report["missing"]:
        print("missing:")
        for item in report["missing"]:
            print(f"  - {item}")
    if report["blocking"]:
        print("blocking:")
        for item in report["blocking"]:
            print(f"  - {item}")
    print(f"next: {report['next_action']}")


def review_prompt(kind: str, report: dict[str, Any]) -> str:
    focus = {
        "correctness": "逻辑正确性、边界条件、状态流、错误处理、并发/生命周期问题",
        "test-quality": "测试 oracle、覆盖目标、路径断言、回归测试、flaky 风险",
        "risk-security": "权限、数据边界、异常路径、资源释放、降级、回滚和恢复",
        "maintainability": "架构漂移、重复实现、接口污染、文档/实现一致性和长期维护成本",
    }[kind]
    files = "\n".join(f"- {p}" for p in report["change_summary"]["sample_files"])
    # test-quality 视角强制给出红证据 + 变异结论(防全绿假测试)。
    extra_block = ""
    if kind == "test-quality":
        extra_block = """
Red-Evidence:
- 测试名 + 它对哪个错误实现/变异曾经失败过(红→绿证据)；不可写 none
- 若无法让测试先失败,说明原因 + 替代验证

Mutation:
- 关键逻辑变异是否被测试 kill(off-by-one/边界/返回码/状态翻转)
- 无变异工具则列人工识别的变异点 + 为何被现有测试覆盖；不可写 none
"""
    return f"""# {kind} review

你是严苛但建设性的代码审查员。本轮只审查一个视角：{focus}。

## 变更摘要

- Tier: {report['plan']['tier']} ({report['plan']['label']})
- Changed lines: {report['change_summary']['changed_lines']}
- Reasons: {', '.join(report['plan']['reasons'])}

## 文件样本

{files or '- (no files)'}

## 输出格式

Verdict: PASS / WARN / BLOCK

Blocking:
- file:line
- problem
- why it matters
- required fix
- required test

Warnings:
- file:line
- risk
- suggested fix

Missing tests:
- behavior
- test type
- why needed
{extra_block}
Confidence: high / medium / low
Need human decision:
- ...

注意：请填写单一 verdict 和单一 confidence，不要保留 `PASS / WARN / BLOCK` 或 `high / medium / low` 占位文本。
"""


def write_review_pack(report: dict[str, Any], out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    required = report["plan"]["required_reviews"] or list(REVIEW_KINDS)
    for kind in required:
        path = out_dir / f"{kind}.md"
        path.write_text(review_prompt(kind, report), encoding="utf-8")
        written.append(str(path))
    return written


def display_path(path: Path, repo: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--repo", default=str(REPO_DIR))
        p.add_argument("--config", default=str(DEFAULT_CONFIG))
        p.add_argument("--json", action="store_true")
        p.add_argument("--no-untracked", action="store_true", help="ignore untracked files")
        p.add_argument("--review-dir", default=None)
        p.add_argument("--path", action="append", default=[], help="limit diff scan to a pathspec; can be repeated")

    plan_p = sub.add_parser("plan", help="classify the current diff and print required checks")
    add_common(plan_p)
    verify_p = sub.add_parser("verify", help="classify and verify required evidence")
    add_common(verify_p)
    verify_p.add_argument("--enforce", action="store_true", help="return non-zero for WARN/BLOCK")
    review_p = sub.add_parser("review-pack", help="write review prompt files for the current risk tier")
    add_common(review_p)
    review_p.add_argument("--out", default="quality/review-prompts")

    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    config_path = Path(args.config).resolve()
    report = build_report(
        repo,
        config_path,
        include_untracked=not args.no_untracked,
        review_dir=args.review_dir,
        pathspecs=args.path,
    )

    if args.command == "review-pack":
        out_arg = Path(args.out)
        out_dir = out_arg if out_arg.is_absolute() else repo / out_arg
        try:
            written = write_review_pack(report, out_dir)
            report["review_pack"] = {"out": str(out_dir.resolve()), "files": written}
        except OSError as exc:
            report["verdict"] = "ERROR"
            report["review_pack"] = {"out": str(out_dir), "files": [], "error": str(exc)}
            report["next_action"] = f"Choose a writable review-pack output directory: {exc}"

    if args.command == "plan":
        report = {**report, "verdict": "PLAN"}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        emit_text(report)
        if args.command == "review-pack":
            print("review prompts:")
            for path in report["review_pack"]["files"]:
                print(f"  - {path}")

    if args.command == "verify" and args.enforce:
        return 0 if report["verdict"] == "PASS" else 1
    if args.command == "review-pack" and report["verdict"] == "ERROR":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
