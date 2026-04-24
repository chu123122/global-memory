#!/usr/bin/env python3
"""
verify_docs.py — 文档一致性检查

防止文档漂移：检查活跃文档里是否有对已归档 Skill 的引用，
以及 bootstrap.py 声明的 Skill 清单是否与实际部署一致。

检查项：
    DOC-01: 活跃文档中无归档 Skill 引用（doc-generator/memory-manager 等）
    DOC-02: bootstrap.py 中的 Skill 清单与 ~/.claude/skills/ 实际部署一致
    DOC-03: SYSTEM_STATUS.md 存在时，Skill 表与实际部署一致

用法：
    python verify_docs.py              # 默认检查 global-memory 单仓库
    python verify_docs.py --fix        # 输出需要修改的位置（不自动修改）
    python verify_docs.py --report     # 详细报告
"""

import importlib.util
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import AGENTS_DIR, CLAUDE_DIR, MEMORY_DIR, REPO_DIR, TEMPLATES_DIR, write_log

# 已归档的 Skill 名称（这些名字出现在活跃文档中就是漂移）
ARCHIVED_SKILLS = {"doc-generator", "memory-manager", "multi-search-engine", "workspace-init"}

# 需要检查的活跃文档
ACTIVE_DOCS = [
    MEMORY_DIR / "README.md",
    TEMPLATES_DIR / "WORKFLOW.md",
    AGENTS_DIR / "CLAUDE.md",
    AGENTS_DIR / "learning-agent.md",
    AGENTS_DIR / "work-agent.md",
]

# 豁免：归档目录自身不检查
SKIP_DIRS = {"_archived", ".git", "__pycache__"}


class CheckResult:
    def __init__(self, check_id: str, name: str):
        self.check_id = check_id
        self.name = name
        self.errors = []
        self.warnings = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    @property
    def level(self) -> str:
        if self.errors:
            return "ERROR"
        if self.warnings:
            return "WARNING"
        return "PASS"

    def print(self):
        icon = {"PASS": "✅", "WARNING": "⚠️", "ERROR": "❌"}[self.level]
        print(f"  {icon} [{self.check_id}] {self.name}: {self.level}")
        for e in self.errors:
            print(f"       ERROR: {e}")
        for w in self.warnings:
            print(f"       WARN:  {w}")


def check_archived_refs(report: bool = False) -> CheckResult:
    """DOC-01: 活跃文档中无归档 Skill 引用"""
    r = CheckResult("DOC-01", "活跃文档无归档 Skill 引用")

    for doc_path in ACTIVE_DOCS:
        if not doc_path.exists():
            continue
        try:
            rel_path = str(doc_path.relative_to(MEMORY_DIR)).replace("\\", "/")
        except ValueError:
            rel_path = str(doc_path)
        content = doc_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            for archived in ARCHIVED_SKILLS:
                # 检查非注释/非归档说明中的引用
                if archived in line and "_archived" not in line and "归档" not in line:
                    r.error(f"{rel_path}:{i} 引用了已归档 Skill `{archived}`")
                    if report:
                        print(f"          > {line.strip()}")

    return r


def load_bootstrap_skills() -> list[str]:
    bootstrap = REPO_DIR / "bootstrap.py"
    if not bootstrap.exists():
        return []
    spec = importlib.util.spec_from_file_location("global_memory_bootstrap", bootstrap)
    if spec is None or spec.loader is None:
        return []
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(getattr(mod, "SKILLS", []))


def check_skill_count(report: bool = False) -> CheckResult:
    """DOC-02: bootstrap.py Skill 清单与实际部署一致"""
    r = CheckResult("DOC-02", "Skill 数量一致性")

    # 实际部署数：~/.claude/skills/ 下的条目
    skills_deploy_dir = CLAUDE_DIR / "skills"
    if not skills_deploy_dir.exists():
        r.warn("~/.claude/skills/ 不存在，跳过部署数检查")
        return r

    deployed_names = {
        d.name for d in skills_deploy_dir.iterdir()
        if (d.is_dir() or d.is_symlink()) and not d.name.startswith("_") and (d / "SKILL.md").is_file()
    }

    expected_names = set(load_bootstrap_skills())
    if not expected_names:
        r.warn("bootstrap.py 中未找到 SKILLS 清单")
        return r

    missing = sorted(expected_names - deployed_names)
    extra = sorted(deployed_names - expected_names)
    if missing:
        r.error(
            f"bootstrap 声明 {len(expected_names)} 个 Skill，实际部署 {len(deployed_names)} 个；"
            f"缺失={missing}，额外={extra}"
        )
    elif extra:
        r.warn(
            f"bootstrap 声明 {len(expected_names)} 个 canonical Skill，实际部署 {len(deployed_names)} 个；"
            f"额外={extra}（视为本地扩展，不阻断）"
        )
    else:
        if report:
            print(f"          已部署: {sorted(deployed_names)}")

    return r


def check_system_status(report: bool = False) -> CheckResult:
    """DOC-03: SYSTEM_STATUS.md Skill 表与实际部署一致"""
    r = CheckResult("DOC-03", "SYSTEM_STATUS Skill 表一致性")

    status_path = MEMORY_DIR / "SYSTEM_STATUS.md"
    if not status_path.exists():
        return r

    content = status_path.read_text(encoding="utf-8", errors="replace")

    # 检查是否还有对归档 Skill 的正面描述（非归档说明）
    for archived in ARCHIVED_SKILLS:
        # 匹配表格里的 **skill-name** 条目（排除归档目录行）
        pattern = rf"\|\s*\*\*{re.escape(archived)}\*\*\s*\|"
        if re.search(pattern, content):
            r.error(f"SYSTEM_STATUS.md 的 Skill 表中仍有已归档 Skill `{archived}` 的条目")

    # 检查已部署 Skill 是否都在 SYSTEM_STATUS 里提到
    skills_deploy_dir = CLAUDE_DIR / "skills"
    if skills_deploy_dir.exists():
        for skill_link in skills_deploy_dir.iterdir():
            name = skill_link.name
            if name not in content:
                r.warn(f"SYSTEM_STATUS.md 未提及已部署 Skill `{name}`")

    return r


def main():
    report = "--report" in sys.argv

    print("=== verify_docs: 文档一致性检查 ===\n")
    print(f"  global-memory: {MEMORY_DIR}\n")

    results = [
        check_archived_refs(report),
        check_skill_count(report),
        check_system_status(report),
    ]

    errors = sum(len(r.errors) for r in results)
    warnings = sum(len(r.warnings) for r in results)

    for r in results:
        r.print()

    print(f"\n总结: {errors} ERROR / {warnings} WARNING / {len(results) - errors - warnings} PASS")

    if errors > 0:
        print("\n⚠️  文档存在漂移，请按上面的行号修复后重跑。")
        sys.exit(1)
    elif warnings > 0:
        print("\n🟡 有警告项，建议处理。")
        sys.exit(0)
    else:
        print("\n✅ 文档一致性检查全部通过。")
        sys.exit(0)


if __name__ == "__main__":
    write_log("verify_docs", "started")
    main()
