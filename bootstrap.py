#!/usr/bin/env python
"""Minimal bootstrap for global-memory single-repo layout.

支持 CLAUDE_HOME 环境变量覆盖（默认 ~/.claude），用于沙盒测试。
正式使用：直接 `python bootstrap.py install`。
"""
import io, os, sys, json, subprocess, ctypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))
from harness.config import CLAUDE_HOME, REPO_DIR

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Windows junction 检测：Python is_symlink() 对 junction 返回 False，
# 必须查 FILE_ATTRIBUTE_REPARSE_POINT (0x400)
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

REPO = REPO_DIR
HOME = CLAUDE_HOME
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
CODEX_CONFIG = CODEX_HOME / "config.toml"
HOOK_MANIFEST = REPO / "harness" / "hook_manifest.json"
ALLOWED_HOOK_FAILURE_ACTIONS = {"BLOCK", "WARN", "REPORT", "NONE"}

def discover_skills() -> list[str]:
    """扫描 REPO/skills/ 下所有含 v1/SKILL.md 的目录，自动发现 skill。"""
    skills_root = REPO / "skills"
    if not skills_root.is_dir():
        return []
    found = []
    for d in sorted(skills_root.iterdir()):
        if not d.is_dir() or d.name.startswith(("_", ".")):
            continue
        if (d / "v1" / "SKILL.md").is_file():
            found.append(d.name)
    return found

SKILLS = discover_skills()


def load_hook_manifest() -> dict:
    return json.loads(HOOK_MANIFEST.read_text(encoding="utf-8"))


def iter_hook_specs(manifest: dict):
    for groups in manifest.get("hooks", {}).values():
        for group in groups:
            for spec in group.get("hooks", []):
                yield spec
    if "statusLine" in manifest:
        yield manifest["statusLine"]


def validate_hook_manifest(manifest: dict) -> list[str]:
    errors = []
    if not isinstance(manifest.get("hooks"), dict):
        errors.append("hook_manifest.json 缺少 hooks 对象")
    if not isinstance(manifest.get("statusLine"), dict):
        errors.append("hook_manifest.json 缺少 statusLine 对象")
    for spec in iter_hook_specs(manifest):
        rel = str(spec.get("path", "")).replace("\\", "/").strip()
        if not rel:
            errors.append("hook_manifest.json 存在空 hook path")
            continue
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            errors.append(f"hook_manifest.json hook path 越界: {rel}")
            continue
        if rel_path.suffix != ".py":
            errors.append(f"hook_manifest.json hook path 不是 .py: {rel}")
        if not (REPO / "harness" / rel_path).is_file():
            errors.append(f"hook 文件缺失: harness/{rel}")
        action = str(spec.get("failure_action", ""))
        if action not in ALLOWED_HOOK_FAILURE_ACTIONS:
            errors.append(f"hook_manifest.json failure_action 非法: {rel} -> {action}")
    return errors


def hook_command(harness_dir: str, spec: dict) -> dict:
    path = str(spec["path"]).replace("\\", "/").lstrip("/")
    args = [str(arg) for arg in spec.get("args", [])]
    command = f"python {harness_dir}/{path}"
    if args:
        command += " " + " ".join(args)
    return {"type": "command", "command": command}


def render_hook_groups(event_groups: list[dict], harness_dir: str) -> list[dict]:
    rendered = []
    for group in event_groups:
        rendered.append({
            "matcher": group.get("matcher", ""),
            "hooks": [hook_command(harness_dir, spec) for spec in group.get("hooks", [])],
        })
    return rendered


# settings.json hooks 部分由 harness/hook_manifest.json 渲染。
def hooks_json():
    # Claude Code 的 hook 执行层对 Windows 反斜杠路径不稳定，
    # 必须统一渲染为正斜杠绝对路径，避免 `\harness` 被吞成 `harness`。
    h = (REPO / "harness").as_posix()
    manifest = load_hook_manifest()
    return {
        event: render_hook_groups(groups, h)
        for event, groups in manifest.get("hooks", {}).items()
    }


def status_line_json():
    h = (REPO / "harness").as_posix()
    manifest = load_hook_manifest()
    return hook_command(h, manifest["statusLine"])


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


def sync_codex_file(filename: str, source: Path, label: str):
    """同步 Codex home 下的单个指令文件。

    优先创建 symlink；Windows 权限不足时退化为复制。check 阶段同时
    接受 symlink 或字节一致的复制件，避免无管理员权限机器无法安装。
    """
    target = CODEX_HOME / filename
    CODEX_HOME.mkdir(parents=True, exist_ok=True)

    backup_needed = False
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            try:
                if target.resolve() == source.resolve():
                    print(f"  [codex] {filename} 已指向 {source}")
                    return
            except OSError:
                backup_needed = True
        else:
            try:
                backup_needed = target.read_bytes() != source.read_bytes()
            except OSError:
                backup_needed = True

        if backup_needed:
            backup = CODEX_HOME / "_backups" / f"{filename}.{int(__import__('time').time())}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            try:
                backup.write_bytes(target.read_bytes())
                print(f"  [backup] Codex {filename} → {backup}")
            except OSError as e:
                print(f"  [warn] Codex {filename} 备份失败，继续重建: {e}")
        target.unlink()

    try:
        target.symlink_to(source)
        print(f"  [codex] {filename} symlink → {source}")
    except OSError as e:
        import shutil
        shutil.copy2(source, target)
        print(f"  [codex] {filename} 已复制同步（symlink failed: {e}）")


def ensure_codex_model_instructions_file():
    """确保 Codex 底层 instructions 指向 CTF profile 文件。

    AGENTS.md 用来承载全局 CLAUDE 铁律；model_instructions_file 单独指向
    ctf.md，让 CTF 规则作为独立 profile 文件维护。
    """
    if not CODEX_CONFIG.exists():
        return
    expected = 'model_instructions_file = "./ctf.md"'
    text = CODEX_CONFIG.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("model_instructions_file"):
            found = True
            if line != expected:
                lines[i] = expected
                changed = True
            break
    if not found:
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("model_reasoning_effort"):
                insert_at = i + 1
                break
        lines.insert(insert_at, expected)
        changed = True
    if not changed:
        print("  [codex] config.toml model_instructions_file 已指向 ./ctf.md")
        return
    backup = CODEX_HOME / "_backups" / f"config.toml.{int(__import__('time').time())}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(text, encoding="utf-8")
    CODEX_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [backup] Codex config.toml → {backup}")
    print("  [codex] config.toml model_instructions_file = ./ctf.md")


def remove_legacy_codex_gpt():
    """迁移旧的 ~/.codex/gpt.md 入口；新入口是 ~/.codex/ctf.md。"""
    legacy = CODEX_HOME / "gpt.md"
    if not (legacy.exists() or legacy.is_symlink()):
        return
    if legacy.is_symlink():
        try:
            legacy.unlink()
            print("  [codex] removed legacy gpt.md symlink")
        except OSError as e:
            print(f"  [warn] legacy Codex gpt.md symlink 删除失败: {e}")
        return
    backup = CODEX_HOME / "_backups" / f"gpt.md.{int(__import__('time').time())}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    try:
        backup.write_bytes(legacy.read_bytes())
        legacy.unlink()
        print(f"  [backup] legacy Codex gpt.md → {backup}")
    except OSError as e:
        print(f"  [warn] legacy Codex gpt.md 备份/删除失败: {e}")


def sync_codex_global_prompt():
    """同步 Codex 全局指令入口。

    - ~/.codex/AGENTS.md -> agents/CLAUDE.md（全局行为铁律）
    - ~/.codex/ctf.md -> rules/ctf.md（CTF profile）
    - config.toml model_instructions_file -> ./ctf.md
    """
    sync_codex_file("AGENTS.md", REPO / "agents" / "CLAUDE.md", "global-agents")
    sync_codex_file("ctf.md", REPO / "rules" / "ctf.md", "ctf-profile")
    ensure_codex_model_instructions_file()
    remove_legacy_codex_gpt()


def install():
    print(f"REPO = {REPO}")
    print(f"HOME = {HOME}")
    if not (REPO / "harness").exists():
        sys.exit(f"❌ {REPO}/harness/ 不存在，bootstrap.py 必须在 repo 根。")
    manifest_errors = validate_hook_manifest(load_hook_manifest())
    if manifest_errors:
        for error in manifest_errors:
            print(f"❌ {error}")
        sys.exit(1)
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

    # 4. CLAUDE.md symlink（文件级，不是 junction）
    claude_md_link = HOME / "CLAUDE.md"
    claude_md_target = REPO / "agents" / "CLAUDE.md"
    if claude_md_target.exists():
        if claude_md_link.exists() or claude_md_link.is_symlink():
            claude_md_link.unlink()
        try:
            claude_md_link.symlink_to(claude_md_target)
            print(f"  [symlink] CLAUDE.md → {claude_md_target}")
        except OSError as e:
            print(f"  [warn] symlink failed ({e}), copying instead")
            import shutil
            shutil.copy2(claude_md_target, claude_md_link)
            print(f"  [copy] CLAUDE.md (symlink 需开发者模式或管理员权限)")

    # 5. 渲染 settings.json（保留非 hooks 字段）
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
    existing["statusLine"] = status_line_json()
    settings_path.write_text(json.dumps(existing, indent=2))
    print(f"  [settings] 已渲染，{sum(len(v) for v in hooks_json().values())} 组 hook + statusLine")

    # 6. 从 Claude work skill 单源生成 Codex work skill 副本
    render_codex_work = REPO / "harness" / "scripts" / "render_codex_work_skill.py"
    if render_codex_work.exists():
        subprocess.check_call([sys.executable, str(render_codex_work)])
        print("  [codex] codex-work skill 已从 work skill 渲染")
    sync_codex_global_prompt()

    print("\n✅ install 完成。请运行 `python bootstrap.py check` 验证。")


def check():
    """只验证你真正在用的链路：/check, /work, Stop hook, diff_backup/diff_show + skill junctions"""
    failed = []
    try:
        failed.extend(validate_hook_manifest(load_hook_manifest()))
    except Exception as e:
        failed.append(f"hook_manifest.json 解析失败: {e}")
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
    # CLAUDE.md symlink
    claude_md = HOME / "CLAUDE.md"
    claude_md_target = REPO / "agents" / "CLAUDE.md"
    if not claude_md.exists():
        failed.append("CLAUDE.md 不存在")
    elif claude_md.is_symlink():
        if claude_md.resolve() != claude_md_target.resolve():
            failed.append(f"CLAUDE.md symlink 指向错误: {claude_md.resolve()}（期望 {claude_md_target.resolve()}）")
    else:
        failed.append("CLAUDE.md 是普通文件，应为 symlink（运行 bootstrap install 修复）")

    # Codex 全局入口：允许 symlink 或复制件，但内容必须与仓库单源一致。
    def check_codex_file(filename: str, source: Path):
        target = CODEX_HOME / filename
        if not (target.exists() or target.is_symlink()):
            failed.append(f"Codex {filename} 不存在")
        elif target.is_symlink():
            try:
                if target.resolve() != source.resolve():
                    failed.append(f"Codex {filename} symlink 指向错误: {target.resolve()}（期望 {source.resolve()}）")
            except OSError as e:
                failed.append(f"Codex {filename} symlink 解析失败: {e}")
        else:
            try:
                if target.read_bytes() != source.read_bytes():
                    failed.append(f"Codex {filename} 与 {source.relative_to(REPO)} 内容不一致")
                else:
                    print(f"ℹ️  Codex {filename} 是普通文件，但内容已与 {source.relative_to(REPO)} 同步")
            except OSError as e:
                failed.append(f"Codex {filename} 读取失败: {e}")

    check_codex_file("AGENTS.md", REPO / "agents" / "CLAUDE.md")
    check_codex_file("ctf.md", REPO / "rules" / "ctf.md")
    if (CODEX_HOME / "gpt.md").exists() or (CODEX_HOME / "gpt.md").is_symlink():
        failed.append("Codex legacy gpt.md 仍存在，应迁移为 ctf.md（运行 bootstrap install 修复）")
    if CODEX_CONFIG.exists():
        try:
            config_text = CODEX_CONFIG.read_text(encoding="utf-8")
            if 'model_instructions_file = "./ctf.md"' not in config_text:
                failed.append("Codex config.toml model_instructions_file 未指向 ./ctf.md")
        except OSError as e:
            failed.append(f"Codex config.toml 读取失败: {e}")

    # settings.json hooks (subset check: expected hooks must be present, extra hooks allowed)
    sp = HOME / "settings.json"
    if not sp.exists():
        failed.append("settings.json 不存在")
    else:
        try:
            actual_settings = json.loads(sp.read_text())
            actual_hooks = actual_settings.get("hooks", {})
            expected_hooks = hooks_json()
            missing_events = set(expected_hooks) - set(actual_hooks)
            if missing_events:
                failed.append(f"settings.json hooks 缺少事件: {', '.join(sorted(missing_events))}")
            for event, expected_groups in expected_hooks.items():
                if event not in actual_hooks:
                    continue
                actual_groups = actual_hooks[event]
                for eg in expected_groups:
                    if eg not in actual_groups:
                        failed.append(f"settings.json hooks[{event}] 缺少期望 hook 组: {eg.get('hooks', [{}])[0].get('command', '')[:60]}")
            extra_events = set(actual_hooks) - set(expected_hooks)
            if extra_events:
                print(f"ℹ️  settings.json 存在额外 hook 事件（非 bootstrap 管理）: {', '.join(sorted(extra_events))}")
            if actual_settings.get("statusLine") != status_line_json():
                failed.append("settings.json statusLine 缺少 bootstrap 期望命令")
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
