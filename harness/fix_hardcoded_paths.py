#!/usr/bin/env python3
"""
fix_hardcoded_paths.py — 硬编码路径检测与修复

扫描 ~/.claude/ 下的脚本和配置文件，检测硬编码的绝对路径并修复。

用法：
  python fix_hardcoded_paths.py              # 只检查，不修改
  python fix_hardcoded_paths.py --fix        # 检测并修复
"""

import io
import json
import os
import re
import sys
from pathlib import Path

# Windows UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 环境检测 ──
HOME = Path.home()
HOME_STR = str(HOME).replace("\\", "/")  # normalized user home
USERNAME = HOME.name                       # XINDONG
CLAUDE_DIR = HOME / ".claude"
HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
MEMORY_DIR = Path(os.environ.get("GLOBAL_MEMORY_DIR", REPO_DIR))
SCRIPTS_DIR = HARNESS_DIR

# 匹配硬编码的用户主目录路径（各种格式）
# Windows, POSIX-style Windows, and Git Bash home variants.
HOME_VARIANTS = [
    str(HOME).replace("/", "\\"),   # Windows home path
    HOME_STR,                        # POSIX-style Windows home path
    f"/c/Users/{USERNAME}",          # /c/Users/XINDONG (Git Bash)
]


class Issue:
    def __init__(self, file: str, line_num: int, line: str, desc: str, fixable: bool = True):
        self.file = file
        self.line_num = line_num
        self.line = line.rstrip()
        self.desc = desc
        self.fixable = fixable

    def __str__(self):
        tag = "FIX" if self.fixable else "MANUAL"
        return f"  {self.file}:L{self.line_num}: [{tag}] {self.desc}"


def rel_path(p: Path) -> str:
    """返回短路径显示，优先相对 active repo，其次相对 ~/.claude。"""
    for base in (MEMORY_DIR, CLAUDE_DIR):
        try:
            return str(p.relative_to(base))
        except ValueError:
            continue
    return str(p)


# ── 检测器 ──

def check_python_scripts(scan_dirs: list[Path]) -> list[Issue]:
    """检查 Python 脚本中的硬编码绝对路径。"""
    issues = []
    # 匹配 Path("X:/...") 或 Path('X:/...')
    pat_path_literal = re.compile(r'Path\(["\'][A-Za-z]:/')
    # 匹配硬编码盘符路径赋值（排除注释行）
    pat_drive_letter = re.compile(r'^\s*[^#]*[=]\s*.*["\'][A-Za-z]:[/\\]')

    self_name = Path(__file__).resolve().name

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for py_file in sorted(scan_dir.rglob("*.py")):
            # 排除自身（包含检测用的旧路径映射表）
            if py_file.name == self_name:
                continue
            # 排除测试文件：守护测试常以字面量断言「某硬编码路径不应出现」
            # （如 assert 'Path("D:/...")' not in text），裸正则匹配会把
            # 守护测试本身误报成违规。测试里的 fixture 路径同理不算生产硬编码。
            parts_lower = {p.lower() for p in py_file.parts}
            if "tests" in parts_lower or "__pycache__" in parts_lower:
                continue
            if py_file.stem.startswith("test_") or py_file.stem.endswith("_test"):
                continue
            try:
                lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # 跳过纯注释行
                if stripped.startswith("#"):
                    continue
                # 跳过 docstring 中的示例路径
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                if pat_path_literal.search(line):
                    issues.append(Issue(
                        rel_path(py_file), i, line,
                        f"硬编码 Path() 路径: {pat_path_literal.search(line).group()}",
                        fixable=False,
                    ))
                elif pat_drive_letter.search(line) and "Path.home()" not in line and "expanduser" not in line:
                    # 排除已经动态的路径
                    issues.append(Issue(
                        rel_path(py_file), i, line,
                        "硬编码盘符路径赋值",
                        fixable=False,
                    ))
    return issues


def check_settings_json(settings_file: Path) -> tuple[list[Issue], dict | None]:
    """检查 settings.json 中 hook command 的路径问题。"""
    issues = []
    if not settings_file.exists():
        return issues, None

    try:
        content = settings_file.read_text(encoding="utf-8")
        settings = json.loads(content)
    except Exception as e:
        issues.append(Issue(rel_path(settings_file), 0, "", f"JSON 解析失败: {e}", fixable=False))
        return issues, None

    hooks = settings.get("hooks", {})
    modified = False

    for event_name, groups in hooks.items():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if not cmd:
                    continue

                original_cmd = cmd

                # 检查1: 绝对 python.exe 路径
                python_exe_pat = re.compile(
                    r'[A-Za-z]:[/\\].*?[/\\]python(?:3)?\.exe',
                    re.IGNORECASE
                )
                m = python_exe_pat.search(cmd)
                if m:
                    issues.append(Issue(
                        rel_path(settings_file), 0, cmd,
                        f"绝对 python.exe 路径 → python",
                    ))
                    cmd = python_exe_pat.sub("python", cmd)

                # 检查2: 反斜杠路径
                if "\\" in cmd:
                    issues.append(Issue(
                        rel_path(settings_file), 0, cmd,
                        "反斜杠路径(bash 不兼容) → 正斜杠",
                    ))
                    cmd = cmd.replace("\\", "/")

                if cmd != original_cmd:
                    hook["command"] = cmd
                    modified = True

    return issues, settings if modified else None


def check_settings_local(settings_file: Path) -> tuple[list[Issue], dict | None]:
    """检查 settings.local.json 中的过时用户路径。"""
    issues = []
    if not settings_file.exists():
        return issues, None

    try:
        content = settings_file.read_text(encoding="utf-8")
        settings = json.loads(content)
    except Exception as e:
        issues.append(Issue(rel_path(settings_file), 0, "", f"JSON 解析失败: {e}", fixable=False))
        return issues, None

    permissions = settings.get("permissions", {})
    allow_list = permissions.get("allow", [])
    modified = False

    for i, perm in enumerate(allow_list):
        original = perm

        # 检查反斜杠路径（在 bash 权限字符串中）
        # 只处理包含用户主目录的条目，系统路径(Program Files)保留
        for variant in HOME_VARIANTS:
            if variant in perm:
                # 统一为正斜杠格式
                normalized = HOME_STR
                if variant != normalized:
                    perm = perm.replace(variant, normalized)

        # 检查双反斜杠转义的用户路径 (JSON 中 C:\\Users\\XINDONG)
        escaped_home = str(HOME).replace("\\", "\\\\\\\\")
        home_double_escaped = f"C:\\\\\\\\Users\\\\\\\\{USERNAME}"
        if home_double_escaped in perm:
            # 这些是 setx 命令等 Windows 特定权限，不自动修复
            pass

        if perm != original:
            allow_list[i] = perm
            modified = True
            issues.append(Issue(
                rel_path(settings_file), 0, original,
                f"用户路径格式不一致 → 已标准化",
            ))

    return issues, settings if modified else None


def check_memory_files(memory_dirs: list[Path]) -> tuple[list[Issue], dict[Path, str]]:
    """检查记忆文件中的过时绝对路径。"""
    issues = []
    fixes: dict[Path, str] = {}

    # 旧路径 → 新路径
    legacy_d_repo = "D:" + "/global-memory"
    legacy_d_repo_win = "D:" + "\\global-memory"
    old_paths = {
        legacy_d_repo_win: "~/.claude/global-memory",
        legacy_d_repo: "~/.claude/global-memory",
        "D:\\skills-repo": "~/.claude/global-memory",
        "D:/skills-repo": "~/.claude/global-memory",
        "E:/CS-Study/Vibe/global-memory": "~/.claude/global-memory",
        "E:/CS-Study/Vibe/skills-repo": "~/.claude/global-memory",
        "E:\\CS-Study\\Vibe\\global-memory": "~/.claude/global-memory",
        "E:\\CS-Study\\Vibe\\skills-repo": "~/.claude/global-memory",
    }
    skip_parts = {"archives", "retrospectives", "test-reports", "CHANGELOG_archive", "__pycache__"}
    skip_files = {"CHANGELOG.md", "FIXLIST.md"}

    for mem_dir in memory_dirs:
        if not mem_dir.is_dir():
            continue
        for md_file in sorted(mem_dir.rglob("*.md")):
            rel_parts = set(md_file.relative_to(mem_dir).parts)
            if md_file.name in skip_files or rel_parts & skip_parts:
                continue
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            original = content
            for old, new in old_paths.items():
                if old in content:
                    issues.append(Issue(
                        rel_path(md_file), 0, "",
                        f"过时路径: {old} → {new}",
                    ))
                    content = content.replace(old, new)

            if content != original:
                fixes[md_file] = content

    return issues, fixes


def check_data_list_consistency() -> list[Issue]:
    """检查硬编码数据列表是否与文件系统一致。

    检测场景：Python 中手写列表本应与某个目录内容同步，
    但新增/删除文件后列表未更新。
    """
    issues = []
    harness = REPO_DIR / "harness"

    # ── 规则表：(描述, 列表来源文件, 提取函数, 期望来源) ──
    rules: list[tuple[str, Path, str, callable]] = []

    # 1. HOOK_NAMES vs harness/hooks/*.py
    def _extract_hook_names(path: Path) -> list[str] | None:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return None
        for i, line in enumerate(lines):
            if line.strip().startswith("HOOK_NAMES"):
                block = ""
                for j in range(i, min(i + 10, len(lines))):
                    block += lines[j]
                    if "]" in lines[j]:
                        break
                import ast
                try:
                    expr = block.split("=", 1)[1].strip()
                    return ast.literal_eval(expr)
                except Exception:
                    return None
        return None

    def _actual_hooks() -> set[str]:
        hooks_dir = harness / "hooks"
        if not hooks_dir.is_dir():
            return set()
        return {
            f.stem for f in hooks_dir.iterdir()
            if f.suffix == ".py" and not f.name.startswith("_")
        }

    status_py = harness / "harness_status.py"
    if status_py.is_file():
        listed = _extract_hook_names(status_py)
        if listed is not None:
            actual = _actual_hooks()
            listed_set = set(listed)
            missing = actual - listed_set
            extra = listed_set - actual - {"post_task_hook"}  # post_task_hook 在 harness/ 根
            if missing:
                issues.append(Issue(
                    rel_path(status_py), 38, f"HOOK_NAMES = [...]",
                    f"HOOK_NAMES 缺少实际存在的 hook: {', '.join(sorted(missing))}",
                    fixable=False,
                ))
            if extra:
                issues.append(Issue(
                    rel_path(status_py), 38, f"HOOK_NAMES = [...]",
                    f"HOOK_NAMES 含已不存在的 hook: {', '.join(sorted(extra))}",
                    fixable=False,
                ))

    # 2. TOPIC_DIRS vs global-memory 一级目录
    def _extract_topic_dirs(path: Path) -> list[str] | None:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return None
        for line in lines:
            if "TOPIC_DIRS" in line and "=" in line and "[" in line:
                import ast
                try:
                    expr = line.split("=", 1)[1].strip()
                    return ast.literal_eval(expr)
                except Exception:
                    return None
        return None

    def _actual_topic_dirs() -> set[str]:
        # TOPIC_DIRS 只管活跃记忆分类，归档/报告目录不算
        non_topic = {"archives", "retrospectives", "test-reports", "projects",
                     "skills", "agents", "harness", "templates", ".git",
                     "__pycache__", ".workbuddy", "CHANGELOG_archive"}
        if not REPO_DIR.is_dir():
            return set()
        return {
            d.name for d in REPO_DIR.iterdir()
            if d.is_dir() and d.name not in non_topic and not d.name.startswith(".")
        }

    lib_py = harness / "_lib.py"
    if lib_py.is_file():
        listed = _extract_topic_dirs(lib_py)
        if listed is not None:
            actual = _actual_topic_dirs()
            listed_set = set(listed)
            missing = actual - listed_set
            if missing:
                issues.append(Issue(
                    rel_path(lib_py), 37, f"TOPIC_DIRS = [...]",
                    f"TOPIC_DIRS 缺少实际存在的目录: {', '.join(sorted(missing))}",
                    fixable=False,
                ))

    # 3. ACTIVE_DOCS — 列出的文件是否实际存在
    verify_docs_py = harness / "verify_docs.py"
    if verify_docs_py.is_file():
        try:
            lines = verify_docs_py.read_text(encoding="utf-8", errors="replace").splitlines()
            in_block = False
            doc_paths_raw = []
            for line in lines:
                if "ACTIVE_DOCS" in line and "=" in line:
                    in_block = True
                if in_block:
                    # 提取路径片段
                    for part in ["README.md", "CLAUDE.md",
                                 "learning-agent.md", "work-agent.md"]:
                        if part in line:
                            doc_paths_raw.append(part)
                    if "]" in line and in_block:
                        break
            for doc_name in doc_paths_raw:
                # 在几个已知目录中搜索
                found = False
                for search_dir in [REPO_DIR, REPO_DIR / "agents", REPO_DIR / "templates"]:
                    if (search_dir / doc_name).is_file():
                        found = True
                        break
                if not found:
                    issues.append(Issue(
                        rel_path(verify_docs_py), 31, f"ACTIVE_DOCS: {doc_name}",
                        f"ACTIVE_DOCS 引用的文件不存在: {doc_name}",
                        fixable=False,
                    ))
        except Exception:
            pass

    return issues


# ── 主流程 ──

def main():
    fix_mode = "--fix" in sys.argv

    print("=" * 55)
    print("  fix_hardcoded_paths.py — 硬编码路径检测")
    print("=" * 55)
    print(f"\n  当前环境: {HOME_STR}")
    print(f"  用户名:   {USERNAME}")
    print(f"  模式:     {'--fix (修复)' if fix_mode else '--check (只检查)'}")
    print()

    all_issues: dict[str, list[Issue]] = {}
    total_fixed = 0
    total_manual = 0

    # 1. Python 脚本检查
    print("[1/5] 扫描 Python 脚本...")
    py_scan_dirs = [
        SCRIPTS_DIR,
        MEMORY_DIR / "skills",
        MEMORY_DIR / "agents",
    ]
    py_issues = check_python_scripts(py_scan_dirs)
    if py_issues:
        all_issues["Python 脚本"] = py_issues
        print(f"  发现 {len(py_issues)} 个问题")
    else:
        print("  ✅ 无硬编码路径")

    # 2. settings.json 检查
    print("\n[2/5] 扫描 settings.json...")
    settings_file = CLAUDE_DIR / "settings.json"
    sj_issues, sj_fixed = check_settings_json(settings_file)
    if sj_issues:
        all_issues["settings.json"] = sj_issues
        print(f"  发现 {len(sj_issues)} 个问题")
        if fix_mode and sj_fixed:
            settings_file.write_text(
                json.dumps(sj_fixed, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8"
            )
            total_fixed += len(sj_issues)
            print("  ✅ 已修复")
    else:
        print("  ✅ 无问题")

    # 3. settings.local.json 检查
    print("\n[3/5] 扫描 settings.local.json...")
    local_file = CLAUDE_DIR / "settings.local.json"
    sl_issues, sl_fixed = check_settings_local(local_file)
    if sl_issues:
        all_issues["settings.local.json"] = sl_issues
        print(f"  发现 {len(sl_issues)} 个问题")
        if fix_mode and sl_fixed:
            local_file.write_text(
                json.dumps(sl_fixed, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8"
            )
            total_fixed += len(sl_issues)
            print("  ✅ 已修复")
    else:
        print("  ✅ 无问题")

    # 4. 记忆文件检查
    print("\n[4/5] 扫描记忆文件...")
    mem_dirs = [
        MEMORY_DIR,
    ]
    # 扫描 projects/*/memory/ 目录
    projects_dir = CLAUDE_DIR / "projects"
    if projects_dir.is_dir():
        for proj in projects_dir.iterdir():
            mem = proj / "memory"
            if mem.is_dir():
                mem_dirs.append(mem)

    md_issues, md_fixes = check_memory_files(mem_dirs)
    if md_issues:
        all_issues["记忆文件"] = md_issues
        print(f"  发现 {len(md_issues)} 个问题")
        if fix_mode and md_fixes:
            for fpath, content in md_fixes.items():
                fpath.write_text(content, encoding="utf-8")
            total_fixed += len(md_issues)
            print("  ✅ 已修复")
    else:
        print("  ✅ 无问题")

    # 5. 数据列表一致性
    print("\n[5/5] 数据列表一致性...")
    dl_issues = check_data_list_consistency()
    if dl_issues:
        all_issues["数据列表"] = dl_issues
        print(f"  发现 {len(dl_issues)} 个问题")
    else:
        print("  ✅ 列表与文件系统一致")

    # ── 汇总 ──
    print("\n" + "=" * 55)
    total_issues = sum(len(v) for v in all_issues.values())

    if total_issues == 0:
        print("  ✅ 未发现硬编码路径问题")
    else:
        print(f"  发现 {total_issues} 个问题\n")
        for section, issues in all_issues.items():
            print(f"  [{section}]")
            for issue in issues:
                print(f"    {issue}")
            print()

        if fix_mode:
            total_manual = sum(1 for v in all_issues.values() for i in v if not i.fixable)
            print(f"  已修复: {total_fixed} | 需手动处理: {total_manual}")
        else:
            fixable = sum(1 for v in all_issues.values() for i in v if i.fixable)
            manual = sum(1 for v in all_issues.values() for i in v if not i.fixable)
            print(f"  可自动修复: {fixable} | 需手动处理: {manual}")
            if fixable > 0:
                print("  运行 --fix 修复可自动处理的问题")

    print("=" * 55)
    return 1 if total_issues > 0 and not fix_mode else 0


if __name__ == "__main__":
    sys.exit(main())
