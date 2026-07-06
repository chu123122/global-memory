#!/usr/bin/env python3
"""
verify_all.py — 总验证脚本（一键跑所有检查 + 基线对比）

原理：
  1. 按顺序执行所有注册的检查项
  2. 每项输出 PASS / WARNING / ERROR
  3. 跑完后与上次基线对比，确保"只升不降"
  4. 生成结构化报告

用法：
  python verify_all.py [目标目录]              # 全量检查
  python verify_all.py [目标目录] --save       # 检查并保存为新基线
  python verify_all.py --status                # 查看上次基线
  python verify_all.py --checks                # 列出所有检查项

设计原则（来自光子 Harness Engineering）：
  - Error 必须修复
  - Warning 必须告知
  - 基线只升不降（新代码不能引入新 Error）
"""

import sys
import io
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime

# 修复 Windows 终端 GBK 编码问题
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 配置（无硬编码路径） ──
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import (  # noqa: E402
    AGENTS_DIR,
    CLAUDE_DIR,
    MEMORY_DIR,
    SKILLS_DIR,
)

BASELINE_FILE = CLAUDE_DIR / ".verify_baseline.json"

# ── 检查项注册 ──
# 每个检查项：(名称, 类型, 检查函数)
# 类型：file_check / script_check / content_check


class CheckResult:
    """单项检查结果"""
    def __init__(self, name, level, message, details=None):
        self.name = name          # 检查项名称
        self.level = level        # PASS / WARNING / ERROR
        self.message = message    # 一行摘要
        self.details = details    # 可选的详细信息

    def to_dict(self):
        return {
            "name": self.name,
            "level": self.level,
            "message": self.message,
        }


def check_claude_md():
    """检查 CLAUDE.md 存在且行数合理"""
    f = CLAUDE_DIR / "CLAUDE.md"
    if not f.is_file():
        f = AGENTS_DIR / "CLAUDE.md"
    if not f.is_file():
        return CheckResult("CLAUDE.md", "ERROR", "CLAUDE.md 不存在")
    lines = f.read_text(encoding="utf-8").splitlines()
    n = len(lines)
    if n > 60:
        return CheckResult("CLAUDE.md", "WARNING", f"CLAUDE.md {n} 行，建议 ≤60")
    return CheckResult("CLAUDE.md", "PASS", f"{n} 行")


def check_memory_index():
    """检查 MEMORY.md 索引存在且引用的文件都存在"""
    mem_dir = MEMORY_DIR
    idx = mem_dir / "MEMORY.md"
    if not idx.is_file():
        return CheckResult("MEMORY.md", "ERROR", "MEMORY.md 索引不存在")
    content = idx.read_text(encoding="utf-8")
    # 提取所有 markdown 链接中的路径
    import re
    links = re.findall(r'\[.*?\]\((.*?\.md)\)', content)
    missing = []
    for link in links:
        target = mem_dir / link
        if not target.is_file():
            missing.append(link)
    if missing:
        return CheckResult("MEMORY.md", "WARNING",
                           f"索引引用了 {len(missing)} 个不存在的文件",
                           missing)
    return CheckResult("MEMORY.md", "PASS", f"索引完整，{len(links)} 个引用")


def check_skills_symlinks():
    """检查 skills/ 软链接是否指向有效目标"""
    skills_dir = CLAUDE_DIR / "skills"
    if not skills_dir.is_dir():
        return CheckResult("Skills 软链接", "ERROR", "skills/ 目录不存在")
    broken = []
    total = 0
    for item in skills_dir.iterdir():
        if item.is_symlink() or item.is_dir():
            total += 1
            skill_md = item / "SKILL.md"
            if not skill_md.is_file():
                broken.append(item.name)
    if broken:
        return CheckResult("Skills 软链接", "WARNING",
                           f"{len(broken)}/{total} 个 Skill 缺少 SKILL.md",
                           broken)
    return CheckResult("Skills 软链接", "PASS", f"{total} 个 Skill 均完整")


def check_skill_line_limits():
    """检查所有 SKILL.md 是否超过 500 行限制"""
    if not SKILLS_DIR.is_dir():
        return CheckResult("SKILL.md 行数", "WARNING", "skills/ 不存在")
    over = []
    total = 0
    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        total += 1
        lines = len(skill_md.read_text(encoding="utf-8").splitlines())
        if lines > 500:
            over.append(f"{skill_md.parent.parent.name}: {lines} 行")
    if over:
        return CheckResult("SKILL.md 行数", "WARNING",
                           f"{len(over)} 个 SKILL.md 超过 500 行", over)
    return CheckResult("SKILL.md 行数", "PASS", f"{total} 个 SKILL.md 均 ≤500 行")


def check_git_status(repo_name, repo_dir=None):
    """检查 Git 仓库是否有未提交的变更"""
    if repo_dir is None:
        repo_dir = MEMORY_DIR
    repo_dir = Path(repo_dir)
    if not (repo_dir / ".git").is_dir():
        return CheckResult(f"Git:{repo_name}", "ERROR", f"{repo_name} 不是 Git 仓库")
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(repo_dir)
        )
        changes = r.stdout.strip()
        if changes:
            n = len(changes.splitlines())
            return CheckResult(f"Git:{repo_name}", "WARNING",
                               f"{n} 个未提交的变更")
        return CheckResult(f"Git:{repo_name}", "PASS", "工作区干净")
    except Exception as e:
        return CheckResult(f"Git:{repo_name}", "ERROR", str(e))


def check_agents():
    """检查 Agent 配置文件存在"""
    agents_dir = CLAUDE_DIR / "agents"
    if not agents_dir.is_dir():
        agents_dir = AGENTS_DIR
    required = ["work-agent.md"]
    missing = [f for f in required if not (agents_dir / f).is_file()]
    if missing:
        return CheckResult("Agent 配置", "ERROR",
                           f"缺少: {', '.join(missing)}")
    return CheckResult("Agent 配置", "PASS", "Agent 配置存在")


def check_scripts_exist():
    """检查核心脚本是否存在"""
    scripts = SCRIPTS_DIR
    required = [
        "verify_output.sh", "check_lua_syntax.sh", "check_cpp_syntax.sh",
        "format_check.sh", "memory_cleanup.sh", "sync_memory.sh",
        "skill_regression_test.sh", "auto_sync_daemon.py"
    ]
    missing = [s for s in required if not (scripts / s).is_file()]
    found = len(required) - len(missing)
    if missing:
        return CheckResult("核心脚本", "WARNING",
                           f"{found}/{len(required)} 个脚本存在",
                           [f"缺少: {s}" for s in missing])
    return CheckResult("核心脚本", "PASS", f"全部 {len(required)} 个脚本存在")


def check_memory_health():
    """检查记忆文件的健康度"""
    mem_dir = MEMORY_DIR
    if not mem_dir.is_dir():
        return CheckResult("记忆健康度", "ERROR", "global-memory/ 不存在")
    topic_dirs = ["feedback", "knowledge", "fixes", "decisions", "interview"]
    total_files = 0
    empty_files = []
    for d in topic_dirs:
        dir_path = mem_dir / d
        if not dir_path.is_dir():
            continue
        for f in dir_path.glob("*.md"):
            if f.name == ".gitkeep":
                continue
            total_files += 1
            content = f.read_text(encoding="utf-8").strip()
            # 如果除了 YAML 头和标题外没有实质内容（<15 行非空非---）
            lines = [l for l in content.splitlines()
                     if l.strip() and l.strip() != "---"
                     and not l.startswith("name:")
                     and not l.startswith("description:")
                     and not l.startswith("type:")
                     and not l.startswith("created:")
                     and not l.startswith("updated:")
                     and not l.startswith("source:")
                     and not l.startswith("access_count:")]
            if len(lines) < 10:
                empty_files.append(f.name)
    if empty_files:
        return CheckResult("记忆健康度", "WARNING",
                           f"{len(empty_files)}/{total_files} 个 Topic 文件内容不足",
                           empty_files[:5])
    return CheckResult("记忆健康度", "PASS", f"{total_files} 个 Topic 文件健康")


def check_auto_sync():
    """检查自动同步守护进程是否在运行（跨平台）"""
    try:
        if sys.platform == "win32":
            # Windows: PowerShell Get-CimInstance（wmic 在 Win11 新版已移除）
            # encoding=utf-8 + errors=replace：兜底其他进程 CommandLine 含 cp936 字节，
            # 否则 subprocess reader 线程会抛 UnicodeDecodeError 污染 stderr
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe' or name='python.exe'\" | Select-Object -ExpandProperty CommandLine"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
            )
            if "auto_sync_daemon" in r.stdout:
                return CheckResult("自动同步", "PASS", "守护进程运行中")
            if "pythonw" in r.stdout:
                return CheckResult("自动同步", "WARNING",
                                   "有 pythonw 进程但无法确认是 auto_sync_daemon")
            # 回退：用 tasklist
            r2 = subprocess.run(
                ["tasklist", "/fi", "imagename eq pythonw.exe", "/fo", "csv", "/nh"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
            )
            if "pythonw.exe" in r2.stdout:
                return CheckResult("自动同步", "WARNING",
                                   "有 pythonw 进程但无法确认是 auto_sync_daemon")
        else:
            # macOS / Linux: ps + grep
            r = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, errors="replace", timeout=10
            )
            if "auto_sync_daemon" in r.stdout:
                return CheckResult("自动同步", "PASS", "守护进程运行中")
        return CheckResult("自动同步", "WARNING", "守护进程未运行")
    except Exception:
        return CheckResult("自动同步", "WARNING", "无法检查进程状态")


def check_skill_yaml_fields():
    """检查所有 SKILL.md 是否有必需的 YAML 字段（name + description）"""
    if not SKILLS_DIR.is_dir():
        return CheckResult("SKILL.md YAML", "WARNING", "skills/ 不存在")
    missing = []
    total = 0
    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        total += 1
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            # 检查 YAML frontmatter
            import re as _re
            match = _re.match(r"^---\s*\n(.*?)\n---", content, _re.DOTALL)
            if not match:
                missing.append(f"{skill_md.parent.parent.name}: 无 YAML 头")
                continue
            yaml_block = match.group(1)
            has_name = any(l.strip().startswith("name:") for l in yaml_block.splitlines())
            has_desc = any(l.strip().startswith("description:") for l in yaml_block.splitlines())
            if not has_name or not has_desc:
                lacks = []
                if not has_name: lacks.append("name")
                if not has_desc: lacks.append("description")
                missing.append(f"{skill_md.parent.parent.name}: 缺 {'+'.join(lacks)}")
        except Exception:
            pass
    if missing:
        return CheckResult("SKILL.md YAML", "WARNING",
                           f"{len(missing)} 个 SKILL.md YAML 字段不完整", missing)
    return CheckResult("SKILL.md YAML", "PASS", f"{total} 个 SKILL.md YAML 字段完整")


def check_skill_examples():
    """统计 Skill examples；examples 不是当前单仓库的阻断项。"""
    if not SKILLS_DIR.is_dir():
        return CheckResult("Skill examples", "WARNING", "skills/ 不存在")
    with_examples = 0
    total = 0
    # 只检查有实质 SKILL.md 的 Skill（排除 _bootstrap/_templates）
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        # 找 v1/SKILL.md 或 SKILL.md
        has_skill = (skill_dir / "v1" / "SKILL.md").is_file() or (skill_dir / "SKILL.md").is_file()
        if not has_skill:
            continue
        total += 1
        examples_dir = skill_dir / "examples"
        v1_examples = skill_dir / "v1" / "examples"
        has_examples = False
        for d in [examples_dir, v1_examples]:
            if d.is_dir() and any(d.iterdir()):
                has_examples = True
                break
        if not has_examples:
            continue
        with_examples += 1
    return CheckResult("Skill examples", "PASS", f"examples 可选；{with_examples}/{total} 个 Skill 已提供")


def check_docs_consistency():
    """调用 verify_docs.py 检查文档一致性（DOC-01/02/03）"""
    verify_docs = SCRIPTS_DIR / "verify" / "verify_docs.py"
    if not verify_docs.is_file():
        return CheckResult("文档一致性", "WARNING", "verify_docs.py 不存在，跳过")
    try:
        r = subprocess.run(
            [sys.executable, str(verify_docs)],
            capture_output=True, text=True, encoding="utf-8", timeout=30
        )
        if r.returncode == 0:
            return CheckResult("文档一致性", "PASS", "DOC-01/02/03 全部通过")
        # 解析错误行
        errors = [l for l in r.stdout.splitlines() if "ERROR:" in l]
        warnings = [l for l in r.stdout.splitlines() if "WARN:" in l]
        if errors:
            return CheckResult("文档一致性", "ERROR",
                               f"{len(errors)} 处文档漂移", errors[:3])
        return CheckResult("文档一致性", "WARNING",
                           f"{len(warnings)} 处文档警告", warnings[:3])
    except Exception as e:
        return CheckResult("文档一致性", "WARNING", f"verify_docs 执行失败: {e}")


def check_codex_work_skill_drift():
    """检查 Codex work skill 是否由 Claude work skill 单源生成且无漂移"""
    script = SCRIPTS_DIR / "scripts" / "render_codex_work_skill.py"
    if not script.is_file():
        return CheckResult("Codex work skill", "WARNING", "render_codex_work_skill.py 不存在，跳过")
    try:
        r = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )
        if r.returncode == 0:
            return CheckResult("Codex work skill", "PASS", "生成物与 work skill 单源同步")
        detail = (r.stderr or r.stdout or "").strip()
        return CheckResult(
            "Codex work skill",
            "ERROR",
            "生成物漂移，请运行 render_codex_work_skill.py",
            [detail] if detail else None,
        )
    except Exception as e:
        return CheckResult("Codex work skill", "WARNING", f"漂移检查执行失败: {e}")


# ── PowerShell 兼容性检查 ──
# 默认 shell 为 PowerShell（见 CLAUDE.md 环境）。SKILL.md 里 ```bash 块的示例
# 应可直接复制运行；POSIX-only 习语在 PowerShell 下会失败。排除备份/归档副本，
# 避免误报旧快照（_backups / archived 等）。
_BACKUP_MARKERS = ("_backup", "backup", "archived", "_archive", ".bak")

# 上游 vendored skill：源自第三方仓库（如官方 anthropics/skills 的 skill-creator），
# 其 bash 示例随上游，本地不强制 PowerShell，跳过避免噪音 WARN。
_VENDORED_SKILLS = ("skill-creator",)

_POSIX_PATTERNS = [
    (re.compile(r"date\s+\+"), "date +FMT → Get-Date -Format"),
    (re.compile(r"echo\s+-n\b"), "echo -n → Set-Content -NoNewline"),
    (re.compile(r"/dev/null"), "/dev/null → $null"),
    (re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*=(?!=)"), "bash 变量赋值 NAME= → $NAME ="),
]


def _is_backup_path(p):
    """路径任一段含备份/归档标记 → 跳过（防审计误读旧副本）。"""
    return any(any(m in seg.lower() for m in _BACKUP_MARKERS) for seg in p.parts)


def check_powershell_compat():
    """扫 SKILL.md 的 ```bash/```sh 块，flag PowerShell 跑不了的 POSIX 习语。"""
    if not SKILLS_DIR.is_dir():
        return CheckResult("PowerShell 兼容", "WARNING", "skills/ 不存在")
    hits = []
    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        if _is_backup_path(skill_md):
            continue
        if any(seg in _VENDORED_SKILLS for seg in skill_md.parts):
            continue
        try:
            lines = skill_md.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        in_sh = False
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith("```"):
                in_sh = s[3:].strip().lower() in ("bash", "sh", "shell")
                continue
            if not in_sh:
                continue
            for rx, why in _POSIX_PATTERNS:
                if rx.search(line):
                    hits.append(f"{skill_md.relative_to(SKILLS_DIR)}:{i} {why}")
                    break
    if hits:
        return CheckResult("PowerShell 兼容", "WARNING",
                           f"{len(hits)} 处 POSIX 习语在 ```bash 块（默认 shell 为 PowerShell）",
                           hits)
    return CheckResult("PowerShell 兼容", "PASS", "SKILL.md 无 PowerShell 不兼容习语")


# ── 检查项列表 ──
ALL_CHECKS = [
    ("CLAUDE.md 身份层", check_claude_md),
    ("PowerShell 兼容", check_powershell_compat),
    ("MEMORY.md 索引", check_memory_index),
    ("Skills 软链接", check_skills_symlinks),
    ("SKILL.md 行数限制", check_skill_line_limits),
    ("SKILL.md YAML 字段", check_skill_yaml_fields),
    ("Codex work skill", check_codex_work_skill_drift),
    ("Skill examples", check_skill_examples),
    ("Agent 配置", check_agents),
    ("核心脚本", check_scripts_exist),
    ("记忆健康度", check_memory_health),
    ("文档一致性", check_docs_consistency),
    ("Git:global-memory", lambda: check_git_status("global-memory", MEMORY_DIR)),
    ("自动同步", check_auto_sync),
]


# ── 基线管理 ──
def load_baseline():
    if BASELINE_FILE.is_file():
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return None


def save_baseline(results):
    data = {
        "timestamp": datetime.now().isoformat(),
        "results": [r.to_dict() for r in results],
        "summary": {
            "pass": sum(1 for r in results if r.level == "PASS"),
            "warning": sum(1 for r in results if r.level == "WARNING"),
            "error": sum(1 for r in results if r.level == "ERROR"),
        }
    }
    BASELINE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    return data


def compare_baseline(current_results, baseline):
    """对比当前结果和基线，返回退化项"""
    if not baseline:
        return []
    base_map = {r["name"]: r["level"] for r in baseline["results"]}
    regressions = []
    severity = {"PASS": 0, "WARNING": 1, "ERROR": 2}
    for r in current_results:
        old = base_map.get(r.name)
        if old and severity.get(r.level, 0) > severity.get(old, 0):
            regressions.append(f"{r.name}: {old} → {r.level}")
    return regressions


# ── 主逻辑 ──
def run_all():
    print("=" * 60)
    print("  verify_all.py — 系统健康检查")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    results = []
    for name, check_fn in ALL_CHECKS:
        try:
            result = check_fn()
        except Exception as e:
            result = CheckResult(name, "ERROR", f"检查异常: {e}")
        results.append(result)

        icon = {"PASS": "✅", "WARNING": "⚠️", "ERROR": "❌"}[result.level]
        print(f"  {icon} [{result.level:7s}] {result.name}: {result.message}")
        if result.details:
            for d in result.details[:3]:
                print(f"              └─ {d}")

    # 统计
    counts = {"PASS": 0, "WARNING": 0, "ERROR": 0}
    for r in results:
        counts[r.level] += 1

    print()
    print("-" * 60)
    print(f"  结果: {counts['PASS']} PASS / {counts['WARNING']} WARNING / {counts['ERROR']} ERROR")

    # 基线对比
    baseline = load_baseline()
    if baseline:
        regressions = compare_baseline(results, baseline)
        base_time = baseline.get("timestamp", "未知")
        old_summary = baseline.get("summary", {})
        print(f"  基线: {base_time}")
        print(f"  基线: {old_summary.get('pass',0)} PASS / "
              f"{old_summary.get('warning',0)} WARNING / "
              f"{old_summary.get('error',0)} ERROR")
        if regressions:
            print()
            print("  🔴 检测到退化:")
            for reg in regressions:
                print(f"     ↓ {reg}")
        else:
            print("  🟢 无退化（只升不降 ✓）")
    else:
        print("  ℹ️  无基线记录。用 --save 保存当前结果为基线。")

    print("=" * 60)
    return results, counts


def main():
    if "--checks" in sys.argv:
        print("注册的检查项:")
        for i, (name, _) in enumerate(ALL_CHECKS, 1):
            print(f"  {i:2d}. {name}")
        return

    if "--status" in sys.argv:
        baseline = load_baseline()
        if baseline:
            print(f"基线时间: {baseline['timestamp']}")
            s = baseline["summary"]
            print(f"结果: {s['pass']} PASS / {s['warning']} WARNING / {s['error']} ERROR")
            for r in baseline["results"]:
                icon = {"PASS": "✅", "WARNING": "⚠️", "ERROR": "❌"}[r["level"]]
                print(f"  {icon} {r['name']}: {r['message']}")
        else:
            print("无基线记录。")
        return

    results, counts = run_all()

    if "--save" in sys.argv:
        data = save_baseline(results)
        print(f"\n  💾 基线已保存到 {BASELINE_FILE}")

    # 退出码：有 ERROR 则非零
    sys.exit(1 if counts["ERROR"] > 0 else 0)


if __name__ == "__main__":
    main()
