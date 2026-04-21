#!/usr/bin/env python3
"""
verify_conventions.py — 跨项目规范硬检查脚本

对照 global-memory/decisions/conventions.md 中标注 🔒 的规范，
对指定项目目录执行自动化检查。

用法：
  python verify_conventions.py <project_dir>          # 检查项目规范
  python verify_conventions.py --memory               # 检查记忆系统规范
  python verify_conventions.py <project_dir> --all    # 检查全部（项目+记忆）

设计原则：
  - 检查 conventions.md 中的规范（🔒 标注的为硬约束/ERROR，其余为软约束/WARNING）
  - 输出 PASS / WARNING / ERROR
  - 可被 verify_all.py 调用
"""

import os
import sys
import io
import re
import subprocess
from pathlib import Path
from datetime import datetime

# 修复 Windows 终端编码
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CLAUDE_DIR = Path.home() / ".claude"
MEMORY_DIR = CLAUDE_DIR / "global-memory"

class ConventionChecker:
    def __init__(self):
        self.results = []  # [(rule_id, status, message)]

    def record(self, rule_id, status, message):
        icon = {"PASS": "✅", "WARNING": "⚠️", "ERROR": "❌", "SKIP": "⏭️"}[status]
        self.results.append((rule_id, status, message))
        print(f"  {icon} [{rule_id}] {message}")

    # ══════════════════════════════════════════════════
    #  文档规范检查（需要 project_dir）
    # ══════════════════════════════════════════════════

    def check_doc01_spec_handoff(self, project_dir):
        """DOC-01: 项目必须有 SPEC + HANDOFF"""
        docs = project_dir / "docs"
        spec = docs / "SPEC.md"
        handoff = docs / "HANDOFF.md"

        if not docs.exists():
            self.record("DOC-01", "ERROR", f"docs/ 目录不存在: {project_dir}")
            return

        if not spec.exists():
            self.record("DOC-01", "WARNING", "缺少 docs/SPEC.md")
        else:
            self.record("DOC-01", "PASS", f"SPEC.md 存在 ({spec.stat().st_size} bytes)")

        if not handoff.exists():
            self.record("DOC-01", "WARNING", "缺少 docs/HANDOFF.md（交接时需要）")
        else:
            self.record("DOC-01", "PASS", f"HANDOFF.md 存在 ({handoff.stat().st_size} bytes)")

    def check_doc02_handoff_decisions(self, project_dir):
        """DOC-02: HANDOFF 必须包含已确定的设计决策"""
        handoff = project_dir / "docs" / "HANDOFF.md"
        if not handoff.exists():
            self.record("DOC-02", "SKIP", "HANDOFF.md 不存在，跳过")
            return

        content = handoff.read_text(encoding="utf-8", errors="replace").lower()
        has_decisions = ("已确定" in content or "设计决策" in content
                        or "design decision" in content or "决策" in content)

        if has_decisions:
            self.record("DOC-02", "PASS", "HANDOFF.md 包含设计决策区块")
        else:
            self.record("DOC-02", "WARNING", "HANDOFF.md 中未找到'设计决策'相关内容")

    def check_doc03_progress(self, project_dir):
        """DOC-03: 多 Phase 项目必须有 PROGRESS.md"""
        docs = project_dir / "docs"
        dev_log = docs / "dev-log"

        # 判断是否是多 Phase 项目
        has_multi_phase = False
        if dev_log.exists():
            phase_files = list(dev_log.glob("phase*.md"))
            has_multi_phase = len(phase_files) > 1

        if not has_multi_phase:
            self.record("DOC-03", "SKIP", "非多 Phase 项目，跳过")
            return

        progress = docs / "PROGRESS.md"
        if progress.exists():
            self.record("DOC-03", "PASS", f"PROGRESS.md 存在 ({len(list(dev_log.glob('phase*.md')))} 个 Phase)")
        else:
            self.record("DOC-03", "WARNING", "多 Phase 项目缺少 PROGRESS.md")

    def check_doc05_plan_and_design(self, project_dir):
        """DOC-05: 开发前必须有计划文档（SPEC + TECHNICAL_DESIGN），开发中必须有进度文档"""
        docs = project_dir / "docs"
        if not docs.exists():
            self.record("DOC-05", "SKIP", "docs/ 不存在")
            return

        spec = docs / "SPEC.md"
        design = docs / "TECHNICAL_DESIGN.md"

        if not spec.exists():
            self.record("DOC-05", "WARNING", "缺少 docs/SPEC.md（开发前的计划文档）")
        elif not design.exists():
            self.record("DOC-05", "WARNING", "缺少 docs/TECHNICAL_DESIGN.md（架构设计文档）")
        else:
            self.record("DOC-05", "PASS", "SPEC.md + TECHNICAL_DESIGN.md 均存在")

    # ══════════════════════════════════════════════════
    #  代码规范检查
    # ══════════════════════════════════════════════════

    def check_code02_cs_namespace(self, project_dir):
        """CODE-02: C# 文件必须有 namespace"""
        cs_files = list(project_dir.rglob("*.cs"))
        if not cs_files:
            self.record("CODE-02", "SKIP", "无 .cs 文件")
            return

        violations = []
        for f in cs_files:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if "namespace " not in content:
                    violations.append(f.relative_to(project_dir))
            except Exception:
                pass

        if violations:
            self.record("CODE-02", "WARNING",
                        f"{len(violations)} 个 .cs 文件缺少 namespace: {', '.join(str(v) for v in violations[:5])}")
        else:
            self.record("CODE-02", "PASS", f"全部 {len(cs_files)} 个 .cs 文件都有 namespace")

    def check_code03_hpp_guard(self, project_dir):
        """CODE-03: C++ header 必须有 include guard"""
        hpp_files = list(project_dir.rglob("*.hpp")) + list(project_dir.rglob("*.h"))
        # 排除 Unity 自动生成的
        hpp_files = [f for f in hpp_files if ".git" not in str(f)]
        if not hpp_files:
            self.record("CODE-03", "SKIP", "无 .hpp/.h 文件")
            return

        violations = []
        for f in hpp_files:
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").split("\n")[:10]
                header_text = "\n".join(lines).lower()
                if "#pragma once" not in header_text and "#ifndef" not in header_text:
                    violations.append(f.relative_to(project_dir))
            except Exception:
                pass

        if violations:
            self.record("CODE-03", "WARNING",
                        f"{len(violations)} 个头文件缺少 include guard: {', '.join(str(v) for v in violations[:5])}")
        else:
            self.record("CODE-03", "PASS", f"全部 {len(hpp_files)} 个头文件都有 include guard")

    # ══════════════════════════════════════════════════
    #  Git 规范检查
    # ══════════════════════════════════════════════════

    def check_git01_conventional_commits(self, project_dir):
        """GIT-01: commit message 使用 conventional commits"""
        try:
            result = subprocess.run(
                ["git", "--no-pager", "log", "--oneline", "-10"],
                capture_output=True, text=True, cwd=project_dir, encoding="utf-8"
            )
            if result.returncode != 0:
                self.record("GIT-01", "SKIP", "非 Git 仓库")
                return

            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            if not lines:
                self.record("GIT-01", "SKIP", "无 commit 历史")
                return

            pattern = re.compile(r"^[a-f0-9]+ (feat|fix|docs|refactor|test|chore|add|improve|init)[\(:]")
            violations = []
            for line in lines:
                if not pattern.match(line):
                    violations.append(line[:60])

            if violations:
                self.record("GIT-01", "WARNING",
                            f"{len(violations)}/{len(lines)} 条 commit 不符合 conventional commits 格式")
            else:
                self.record("GIT-01", "PASS",
                            f"最近 {len(lines)} 条 commit 全部符合格式")
        except Exception as e:
            self.record("GIT-01", "SKIP", f"Git 检查失败: {e}")

    # ══════════════════════════════════════════════════
    #  Harness 规范检查
    # ══════════════════════════════════════════════════

    def check_doc04_phase_devlog(self, project_dir):
        """DOC-04: 每个 Phase 完成后写 dev-log"""
        docs = project_dir / "docs"
        progress = docs / "PROGRESS.md"
        dev_log = docs / "dev-log"

        if not progress.exists():
            self.record("DOC-04", "SKIP", "无 PROGRESS.md，跳过 dev-log 检查")
            return

        # 从 PROGRESS.md 中检测已完成的 Phase
        content = progress.read_text(encoding="utf-8", errors="replace").lower()
        completed_phases = []
        for i in range(1, 20):
            markers = [f"phase {i}", f"phase{i}", f"阶段 {i}", f"阶段{i}"]
            for marker in markers:
                if marker in content and ("完成" in content or "✅" in content or "done" in content):
                    completed_phases.append(i)
                    break

        if not completed_phases:
            self.record("DOC-04", "SKIP", "未检测到已完成的 Phase")
            return

        missing_logs = []
        for phase_num in completed_phases:
            log_file = dev_log / f"phase{phase_num}.md"
            if not log_file.exists():
                missing_logs.append(f"phase{phase_num}.md")

        if missing_logs:
            self.record("DOC-04", "WARNING",
                        f"已完成的 Phase 缺少 dev-log: {', '.join(missing_logs)}")
        else:
            self.record("DOC-04", "PASS",
                        f"{len(completed_phases)} 个已完成 Phase 均有 dev-log")

    def check_git02_feature_branch(self, project_dir):
        """GIT-02: 特性开发用独立分支，不直接改 main"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, cwd=project_dir, encoding="utf-8"
            )
            if result.returncode != 0:
                self.record("GIT-02", "SKIP", "非 Git 仓库")
                return

            branch = result.stdout.strip()
            if branch in ("main", "master"):
                # 检查是否有未提交的代码变更（不含文档）
                r2 = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True, cwd=project_dir, encoding="utf-8"
                )
                code_changes = [
                    l for l in r2.stdout.strip().splitlines()
                    if l.strip() and not l.strip().endswith(".md")
                ]
                if code_changes:
                    self.record("GIT-02", "WARNING",
                                f"在 {branch} 上有 {len(code_changes)} 个代码变更，建议用特性分支")
                else:
                    self.record("GIT-02", "PASS",
                                f"在 {branch} 分支，但无代码变更")
            else:
                self.record("GIT-02", "PASS", f"使用独立分支: {branch}")
        except Exception as e:
            self.record("GIT-02", "SKIP", f"Git 检查失败: {e}")

    def check_harness01_spec_first(self, project_dir):
        """HARNESS-01: 项目开始前写 SPEC"""
        spec = project_dir / "docs" / "SPEC.md"
        if spec.exists():
            self.record("HARNESS-01", "PASS", "SPEC.md 存在")
        else:
            self.record("HARNESS-01", "WARNING", "缺少 docs/SPEC.md（应在编码前创建）")

    def check_harness02_review(self, project_dir):
        """HARNESS-02: 项目完成后填 HARNESS_REVIEW"""
        docs = project_dir / "docs"
        review = docs / "HARNESS_REVIEW.md"
        # 只有存在 HANDOFF.md（说明项目已交付过）时才检查
        handoff = docs / "HANDOFF.md"
        if not handoff.exists():
            self.record("HARNESS-02", "SKIP", "无 HANDOFF.md，项目可能未到交付阶段")
            return

        if review.exists():
            self.record("HARNESS-02", "PASS", "HARNESS_REVIEW.md 存在")
        else:
            self.record("HARNESS-02", "WARNING",
                        "项目已有 HANDOFF 但缺少 HARNESS_REVIEW.md（做完后应复盘）")

    # ══════════════════════════════════════════════════
    #  记忆系统规范检查（不需要 project_dir）
    # ══════════════════════════════════════════════════

    def check_mem01_changelog(self):
        """MEM-01: CHANGELOG 存在性与基本健康检查（不验证 git diff 关联）"""
        changelog = MEMORY_DIR / "CHANGELOG.md"
        if not changelog.exists():
            self.record("MEM-01", "ERROR", "CHANGELOG.md 不存在！")
            return

        content = changelog.read_text(encoding="utf-8", errors="replace")
        entry_count = content.count("### 20")  # 统计变更条目数
        self.record("MEM-01", "PASS", f"CHANGELOG.md 存在，{entry_count} 条记录")

    def check_mem03_index_sync(self):
        """MEM-03: 记忆索引同步"""
        memory_md = MEMORY_DIR / "MEMORY.md"
        if not memory_md.exists():
            self.record("MEM-03", "ERROR", "MEMORY.md 不存在！")
            return

        content = memory_md.read_text(encoding="utf-8", errors="replace")

        # 收集 MEMORY.md 中引用的文件
        referenced = set()
        for match in re.finditer(r'\[.*?\]\((.*?\.md)\)', content):
            referenced.add(match.group(1))

        # 收集实际存在的 topic 文件（递归扫描子目录）
        actual = set()
        for subdir in ["feedback", "knowledge", "fixes", "decisions", "interview", "projects"]:
            d = MEMORY_DIR / subdir
            if d.exists():
                for f in d.rglob("*.md"):
                    if f.name != ".gitkeep":
                        rel = str(f.relative_to(MEMORY_DIR)).replace("\\", "/")
                        actual.add(rel)

        # 根目录的特殊文件（如 CHANGELOG.md）
        for f in MEMORY_DIR.glob("*.md"):
            if f.name not in ("MEMORY.md", "README.md"):
                actual.add(f.name)

        # 比对
        in_index_not_exist = referenced - actual
        exist_not_in_index = actual - referenced

        if in_index_not_exist:
            self.record("MEM-03", "WARNING",
                        f"索引中有但实际不存在: {', '.join(in_index_not_exist)}")
        if exist_not_in_index:
            self.record("MEM-03", "WARNING",
                        f"实际存在但索引中没有: {', '.join(exist_not_in_index)}")
        if not in_index_not_exist and not exist_not_in_index:
            self.record("MEM-03", "PASS",
                        f"索引与实际文件同步（{len(actual)} 个 topic 文件）")

    # ══════════════════════════════════════════════════
    #  入口
    # ══════════════════════════════════════════════════

    def run_project_checks(self, project_dir):
        """运行所有项目级检查"""
        project_dir = Path(project_dir).resolve()
        print(f"\n{'='*60}")
        print(f"  项目规范检查: {project_dir.name}")
        print(f"{'='*60}\n")

        self.check_doc01_spec_handoff(project_dir)
        self.check_doc02_handoff_decisions(project_dir)
        self.check_doc03_progress(project_dir)
        self.check_doc04_phase_devlog(project_dir)
        self.check_doc05_plan_and_design(project_dir)
        self.check_code02_cs_namespace(project_dir)
        self.check_code03_hpp_guard(project_dir)
        self.check_git01_conventional_commits(project_dir)
        self.check_git02_feature_branch(project_dir)
        self.check_harness01_spec_first(project_dir)
        self.check_harness02_review(project_dir)

    def run_memory_checks(self):
        """运行所有记忆系统检查"""
        print(f"\n{'='*60}")
        print(f"  记忆系统规范检查")
        print(f"{'='*60}\n")

        self.check_mem01_changelog()
        self.check_mem03_index_sync()

    def summary(self):
        """输出汇总"""
        print(f"\n{'='*60}")
        print(f"  汇总")
        print(f"{'='*60}\n")

        counts = {"PASS": 0, "WARNING": 0, "ERROR": 0, "SKIP": 0}
        for _, status, _ in self.results:
            counts[status] += 1

        print(f"  ✅ PASS: {counts['PASS']}")
        print(f"  ⚠️  WARNING: {counts['WARNING']}")
        print(f"  ❌ ERROR: {counts['ERROR']}")
        print(f"  ⏭️  SKIP: {counts['SKIP']}")
        print()

        if counts["ERROR"] > 0:
            print("  ❌ 存在 ERROR，必须修复！")
            return 1
        elif counts["WARNING"] > 0:
            print("  ⚠️  存在 WARNING，建议修复")
            return 0
        else:
            print("  ✅ 全部通过")
            return 0


def main():
    checker = ConventionChecker()

    if len(sys.argv) < 2:
        print("用法:")
        print("  python verify_conventions.py <project_dir>          # 项目检查")
        print("  python verify_conventions.py --memory               # 记忆检查")
        print("  python verify_conventions.py <project_dir> --all    # 全部检查")
        sys.exit(1)

    if sys.argv[1] == "--memory":
        checker.run_memory_checks()
    elif "--all" in sys.argv:
        project_dir = sys.argv[1]
        checker.run_project_checks(project_dir)
        checker.run_memory_checks()
    else:
        project_dir = sys.argv[1]
        checker.run_project_checks(project_dir)

    return checker.summary()


if __name__ == "__main__":
    sys.exit(main())
