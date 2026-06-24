#!/usr/bin/env python3
"""
generate_catalog.py — 自动生成各子目录的 README.md（组件目录）。

从 .py docstring 第一行和 .md YAML frontmatter 抓取描述，
输出 agents/README.md、skills/README.md、harness/README.md。

用法：
  python generate_catalog.py              # 生成并写入
  python generate_catalog.py --dry-run    # 只输出不写
  python generate_catalog.py --check --json  # 只读检查自动目录是否新鲜
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent


def extract_py_desc(path):
    """从 Python 文件的 module docstring 提取第一行描述。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'"""(.+?)"""', text, re.DOTALL)
        if m:
            first_line = m.group(1).strip().split("\n")[0].strip()
            return first_line
    except Exception:
        pass
    return ""


def extract_md_frontmatter(path):
    """从 .md YAML frontmatter 提取 name 和 description。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = re.match(r"^---\s*\n(.+?)\n---", text, re.DOTALL)
        if not fm:
            return "", ""
        block = fm.group(1)
        name = ""
        desc = ""
        for line in block.split("\n"):
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip('"')
            if line.startswith("description:"):
                raw = line.split(":", 1)[1].strip().strip('"')
                if raw and raw != ">":
                    desc = raw
        if not desc:
            lines = block.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("description:") and line.strip().endswith(">"):
                    if i + 1 < len(lines):
                        desc = lines[i + 1].strip()
                    break
        return name, desc
    except Exception:
        return "", ""


def generate_agents_readme():
    agents_dir = REPO / "agents"
    lines = ["# Agents 目录\n"]
    lines.append("| Agent | 描述 |")
    lines.append("|-------|------|")
    for f in sorted(agents_dir.glob("*.md")):
        if f.name == "README.md":
            continue
        name, desc = extract_md_frontmatter(f)
        display = name or f.stem
        if not desc:
            desc = f"（见 {f.name}）"
        if len(desc) > 100:
            desc = desc[:97] + "..."
        lines.append(f"| **{display}** | {desc} |")
    lines.append(f"\n> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。\n")
    return "\n".join(lines)


def generate_skills_readme():
    skills_dir = REPO / "skills"
    lines = ["# Skills 目录\n"]
    lines.append("| Skill | 描述 |")
    lines.append("|-------|------|")
    for d in sorted(skills_dir.iterdir()):
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        name, desc = extract_md_frontmatter(skill_md)
        display = name or d.name
        if not desc:
            desc = f"（见 {d.name}/SKILL.md）"
        if len(desc) > 100:
            desc = desc[:97] + "..."
        lines.append(f"| **{display}** | {desc} |")
    lines.append(f"\n> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。\n")
    return "\n".join(lines)


def generate_harness_readme():
    harness_dir = REPO / "harness"
    sections = [
        ("核心脚本", harness_dir, "*.py"),
        ("上下文治理脚本", harness_dir / "scripts", "*.py"),
        ("Hooks", harness_dir / "hooks", "*.py"),
        ("验证器", harness_dir / "verify", "*.py"),
        ("健康检查", harness_dir / "health" / "checks", "*.py"),
    ]
    lines = ["# Harness 目录\n"]
    for title, directory, pattern in sections:
        if not directory.exists():
            continue
        entries = []
        for f in sorted(directory.glob(pattern)):
            if f.name.startswith("__"):
                continue
            desc = extract_py_desc(f)
            if not desc:
                desc = "—"
            if len(desc) > 80:
                desc = desc[:77] + "..."
            entries.append((f.name, desc))
        if not entries:
            continue
        lines.append(f"\n## {title}\n")
        lines.append("| 文件 | 描述 |")
        lines.append("|------|------|")
        for name, desc in entries:
            lines.append(f"| `{name}` | {desc} |")
    lines.append(f"\n> 自动生成，勿手动编辑。运行 `python harness/generate_catalog.py` 更新。\n")
    return "\n".join(lines)


def catalog_targets():
    return [
        (REPO / "agents" / "README.md", generate_agents_readme),
        (REPO / "skills" / "README.md", generate_skills_readme),
        (REPO / "harness" / "README.md", generate_harness_readme),
    ]


def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def build_check_report():
    targets = []
    findings = []
    fresh = 0
    stale = 0
    missing = 0
    for path, gen_fn in catalog_targets():
        relpath = str(path.relative_to(REPO)).replace("\\", "/")
        expected = gen_fn()
        exists = path.exists()
        actual = path.read_text(encoding="utf-8", errors="replace") if exists else ""
        is_fresh = exists and normalize_newlines(actual) == normalize_newlines(expected)
        if is_fresh:
            fresh += 1
        elif not exists:
            missing += 1
            findings.append({"path": relpath, "issue": "missing_catalog"})
        else:
            stale += 1
            findings.append({
                "path": relpath,
                "issue": "stale_catalog",
                "expected_lines": len(expected.splitlines()),
                "actual_lines": len(actual.splitlines()),
            })
        targets.append({
            "path": relpath,
            "exists": exists,
            "fresh": is_fresh,
            "expected_lines": len(expected.splitlines()),
            "actual_lines": len(actual.splitlines()) if exists else 0,
        })
    return {
        "schema_version": 1,
        "kind": "catalog_freshness_check",
        "repo": str(REPO),
        "verdict": "ok" if not findings else "stale",
        "summary": {
            "targets": len(targets),
            "fresh": fresh,
            "stale": stale,
            "missing": missing,
            "findings": len(findings),
        },
        "targets": targets,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print generated catalogs without writing")
    parser.add_argument("--check", action="store_true", help="read-only freshness check")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON with --check")
    args = parser.parse_args()

    if args.check:
        report = build_check_report()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            summary = report["summary"]
            print("generate_catalog.py --check")
            print(f"verdict={report['verdict']} targets={summary['targets']} stale={summary['stale']} missing={summary['missing']}")
            for finding in report["findings"]:
                print(f"- {finding['path']}: {finding['issue']}")
        return 0 if report["verdict"] == "ok" else 1

    targets = catalog_targets()
    for path, gen_fn in targets:
        content = gen_fn()
        if args.dry_run:
            print(f"=== {path.relative_to(REPO)} ===")
            print(content)
            print()
        else:
            path.write_text(content, encoding="utf-8")
            print(f"  ✅ {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
