#!/usr/bin/env python
"""Minimal bootstrap for global-memory single-repo layout.

支持 CLAUDE_HOME 环境变量覆盖（默认 ~/.claude），用于沙盒测试。
正式使用：直接 `python bootstrap.py install`。
"""
import io, os, sys, json, subprocess, ctypes
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Windows junction 检测：Python is_symlink() 对 junction 返回 False，
# 必须查 FILE_ATTRIBUTE_REPARSE_POINT (0x400)
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

REPO = Path(__file__).parent.absolute()
HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))

# 硬编码依赖清单（单机用，不抽象成 MANIFEST）
SKILLS = ["work", "check", "bug-locator", "cpp-tutor", "migrate-executor",
          "skill-auditor", "skill-creator", "skill-reviewer", "smoke-test"]

# settings.json hooks 部分（与现 settings.json 1:1 对齐：含 diff_backup/diff_show）
def hooks_json():
    # Claude Code 的 hook 执行层对 Windows 反斜杠路径不稳定，
    # 必须统一渲染为正斜杠绝对路径，避免 `\harness` 被吞成 `harness`。
    h = (REPO / "harness").as_posix()
    return {
        "Stop": [{"matcher": "", "hooks": [
            {"type": "command", "command": f"python {h}/post_task_hook.py --auto-fix"}]}],
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": f"python {h}/hooks/dangerous_command_blocker.py"}]},
            {"matcher": "Write|Edit", "hooks": [
                {"type": "command", "command": f"python {h}/hooks/memory_file_protector.py"},
                {"type": "command", "command": f"python {h}/hooks/doc_gate.py"},
                {"type": "command", "command": f"python {h}/hooks/diff_backup.py"}]},
        ],
        "PostToolUse": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": f"python {h}/hooks/audit_logger.py"}]},
            {"matcher": "Write|Edit", "hooks": [
                {"type": "command", "command": f"python {h}/hooks/diff_show.py"}]},
        ],
        "SubagentStart": [{"matcher": "", "hooks": [
            {"type": "command", "command": f"python {h}/hooks/subagent_logger.py"}]}],
    }


def is_junction_or_link(p: Path) -> bool:
    """Windows-aware: detects both symlink and junction (Python is_symlink misses junction)."""
    if p.is_symlink():
        return True
    if sys.platform == "win32":
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
            if attrs == 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
                return False
            return bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            return False
    return False


def junction_target(p: Path) -> str:
    """读 junction/symlink 的指向。Windows junction 用 fsutil 兜底（os.readlink 在某些 Python 上报错）。"""
    try:
        return os.readlink(str(p))
    except (OSError, NotImplementedError):
        # fsutil 兜底
        out = subprocess.check_output(["cmd", "/c", "dir", str(p.parent)], text=True,
                                       errors="ignore", stderr=subprocess.DEVNULL)
        # 简单抓 [target] 段，否则放弃
        for line in out.splitlines():
            if p.name in line and "[" in line:
                return line.split("[", 1)[1].rstrip("]").strip()
        return "(unknown)"


def remove_path(p: Path):
    """删除 p：junction/symlink 用 rmdir/unlink；真目录递归删（仅当存在 .__sandbox_safe 标记时）。"""
    if not p.exists() and not p.is_symlink():
        return
    if is_junction_or_link(p):
        # junction 必须 rmdir，symlink unlink
        try:
            p.unlink()
        except (PermissionError, IsADirectoryError, OSError):
            subprocess.check_call(["cmd", "/c", "rmdir", str(p)], shell=False)
    elif p.is_dir():
        # 真目录：用 cmd rmdir /s /q（Windows 安全）
        subprocess.check_call(["cmd", "/c", "rmdir", "/s", "/q", str(p)], shell=False)
    else:
        p.unlink()


def make_junction(target: Path, source: Path):
    """target → source（target 必须不存在，source 必须存在）"""
    if not source.exists():
        raise FileNotFoundError(f"source 不存在: {source}")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"target 已存在，需先删除: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["cmd", "/c", "mklink", "/J", str(target), str(source)],
                          shell=False, stdout=subprocess.DEVNULL)


def replace_junction(target: Path, source: Path, label: str):
    """原子语义无法保证（Windows junction 限制），但前置已 kill Claude Code，窗口期内无 hook 触发。"""
    print(f"  [{label}] {target} → {source}")
    remove_path(target)
    make_junction(target, source)


def install():
    print(f"REPO = {REPO}")
    print(f"HOME = {HOME}")
    if not (REPO / "harness").exists():
        sys.exit(f"❌ {REPO}/harness/ 不存在，bootstrap.py 必须在 repo 根。")
    HOME.mkdir(parents=True, exist_ok=True)

    # 1. skills/ 下每个 skill 独立 junction
    skills_root = HOME / "skills"
    skills_root.mkdir(exist_ok=True)
    for s in SKILLS:
        replace_junction(skills_root / s, REPO / "skills" / s / "v1", f"skill:{s}")

    # 2. agents/ 整体 junction
    replace_junction(HOME / "agents", REPO / "agents", "agents")

    # 3. scripts/ 重建 junction → harness
    replace_junction(HOME / "scripts", REPO / "harness", "scripts→harness")

    # 4. 渲染 settings.json（保留非 hooks 字段）
    settings_path = HOME / "settings.json"
    existing = {}
    if settings_path.exists():
        # 备份
        backup = HOME / "_backups" / f"settings.json.{int(__import__('time').time())}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(settings_path.read_bytes())
        print(f"  [backup] settings.json → {backup}")
        try:
            existing = json.loads(settings_path.read_text())
        except Exception:
            existing = {}
    existing["hooks"] = hooks_json()
    settings_path.write_text(json.dumps(existing, indent=2))
    print(f"  [settings] 已渲染，{sum(len(v) for v in hooks_json().values())} 组 hook")

    print("\n✅ install 完成。请运行 `python bootstrap.py check` 验证。")


def check():
    """只验证你真正在用的链路：/check, /work, Stop hook, diff_backup/diff_show + 9 个 skill junction"""
    failed = []
    # 核心 skill
    for s in ["check", "work"]:
        if not (REPO / "skills" / s / "v1" / "SKILL.md").exists():
            failed.append(f"skill 文件缺失: skills/{s}/v1/SKILL.md")
    # Stop hook
    if not (REPO / "harness" / "post_task_hook.py").exists():
        failed.append("Stop hook 文件缺失: harness/post_task_hook.py")
    # diff_backup/diff_show
    for h in ["diff_backup.py", "diff_show.py"]:
        if not (REPO / "harness" / "hooks" / h).exists():
            failed.append(f"hook 文件缺失: harness/hooks/{h}")
    # 9 个 skill junction
    for s in SKILLS:
        link = HOME / "skills" / s
        expected = REPO / "skills" / s / "v1"
        if not (link.exists() or link.is_symlink()):
            failed.append(f"junction 缺失: ~/.claude/skills/{s}")
            continue
        if not is_junction_or_link(link):
            failed.append(f"~/.claude/skills/{s} 是真目录，应为 junction")
            continue
        # 解引用比对（去 \\?\ 前缀 + 规范化路径分隔符）
        actual = junction_target(link)
        actual_norm = actual.replace("\\\\?\\", "").replace("\\", "/").rstrip("/").lower()
        expected_norm = str(expected).replace("\\", "/").rstrip("/").lower()
        if actual_norm != expected_norm and not actual_norm.endswith(expected_norm):
            failed.append(f"junction 指向错误: skills/{s} → {actual}（期望 {expected}）")
    # agents/scripts junction
    for name, src in [("agents", REPO / "agents"), ("scripts", REPO / "harness")]:
        link = HOME / name
        if not (link.exists() or link.is_symlink()):
            failed.append(f"junction 缺失: ~/.claude/{name}")
        elif not is_junction_or_link(link):
            failed.append(f"~/.claude/{name} 是真目录，应为 junction")
    # settings.json hooks
    sp = HOME / "settings.json"
    if not sp.exists():
        failed.append("settings.json 不存在")
    else:
        try:
            actual_hooks = json.loads(sp.read_text()).get("hooks", {})
            expected_hooks = hooks_json()
            if actual_hooks != expected_hooks:
                failed.append("settings.json hooks 与期望不一致")
        except Exception as e:
            failed.append(f"settings.json 解析失败: {e}")

    if failed:
        for f in failed:
            print(f"❌ {f}")
        sys.exit(1)
    print(f"✅ 全绿（{len(SKILLS)} skill junction + agents + scripts + settings + 4 关键文件）")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "install"
    {"install": install, "check": check}.get(cmd, lambda: sys.exit(f"未知子命令: {cmd}"))()
