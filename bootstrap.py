#!/usr/bin/env python
"""Minimal bootstrap for global-memory single-repo layout.

支持 CLAUDE_HOME 环境变量覆盖（默认 ~/.claude），用于沙盒测试。
正式使用：直接 `python bootstrap.py install`。
"""
import importlib.util
import io, os, sys, json, subprocess, ctypes, shutil, urllib.error, urllib.request
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
CODEX_SKILLS_ROOT = CODEX_HOME / "skills"
CLAUDE_JSON = Path(os.environ.get("CLAUDE_CONFIG_FILE", Path.home() / ".claude.json")).expanduser()
HOOK_MANIFEST = REPO / "harness" / "hook_manifest.json"
REQUIREMENTS = REPO / "requirements.txt"
SEMANTIC_INDEX = REPO / "harness" / "data" / "semantic_index.sqlite"
GM_MCP_NAME = "global-memory"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_MODEL = "bge-m3"
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


def path_points_to(p: Path, expected: Path) -> bool:
    r"""Return True when a junction/symlink textually resolves to expected.

    Mirrors the check() comparison: tolerate Windows \\?\ prefixes and either
    absolute normalized equality or suffix equality for junction_target()
    variants returned by fsutil/cmd.
    """
    if not (p.exists() or p.is_symlink()) or not is_junction_or_link(p):
        return False
    actual = junction_target(p)
    actual_norm = actual.replace("\\\\?\\", "").replace("\\", "/").rstrip("/").lower()
    expected_norm = str(expected).replace("\\", "/").rstrip("/").lower()
    return actual_norm == expected_norm or actual_norm.endswith(expected_norm)


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
    if path_points_to(target, source):
        print(f"  [{label}] 已指向 {source}，跳过")
        return
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


def _same_file_bytes(a: Path, b: Path) -> bool:
    try:
        return a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def _backup_codex_skill_dir(target: Path) -> Path:
    """Move a pre-existing Codex skill directory aside instead of deleting it."""
    import time

    backup = CODEX_HOME / "_backups" / f"skill-{target.name}.{int(time.time())}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    suffix = 1
    final_backup = backup
    while final_backup.exists():
        suffix += 1
        final_backup = backup.with_name(f"{backup.name}.{suffix}")
    target.rename(final_backup)
    print(f"  [backup] Codex skill {target.name} → {final_backup}")
    return final_backup


def sync_codex_skill(skill_name: str):
    """Expose a repo skill under CODEX_HOME/skills.

    Prefer a symlink/junction so Codex sees current repo content. If the platform
    cannot create directory links, fall back to a copied directory. Existing real
    directories are moved to _backups before replacement; they are never deleted.
    """
    source = REPO / "skills" / skill_name / "v1"
    target = CODEX_SKILLS_ROOT / skill_name
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"skill source missing: {source / 'SKILL.md'}")

    CODEX_SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if is_junction_or_link(target):
            try:
                if target.resolve() == source.resolve():
                    print(f"  [codex:skill] {skill_name} 已指向 {source}")
                    return
            except OSError:
                pass
            remove_path(target)
        elif target.is_dir():
            if _same_file_bytes(target / "SKILL.md", source / "SKILL.md"):
                print(f"  [codex:skill] {skill_name} 普通目录内容已同步")
                return
            _backup_codex_skill_dir(target)
        else:
            import time

            backup = CODEX_HOME / "_backups" / f"skill-{target.name}.{int(time.time())}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
            print(f"  [backup] Codex skill file {target.name} → {backup}")

    try:
        target.symlink_to(source, target_is_directory=True)
        print(f"  [codex:skill] {skill_name} symlink → {source}")
        return
    except OSError as e:
        if sys.platform == "win32":
            try:
                make_junction(target, source)
                print(f"  [codex:skill] {skill_name} junction → {source}")
                return
            except (OSError, subprocess.CalledProcessError) as junction_error:
                print(f"  [warn] Codex skill {skill_name} junction failed: {junction_error}")
        import shutil

        shutil.copytree(source, target)
        print(f"  [codex:skill] {skill_name} 已复制同步（symlink failed: {e}）")


def sync_codex_repo_skills():
    for skill_name in SKILLS:
        sync_codex_skill(skill_name)


def ensure_codex_model_instructions_file():
    """确保 Codex 底层 instructions 指向 CTF profile 文件。

    AGENTS.md 用来承载全局 CLAUDE 铁律；model_instructions_file 单独指向
    ctf.md，让 CTF 规则作为独立 profile 文件维护。
    """
    expected = 'model_instructions_file = "./ctf.md"'
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    text = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""
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
    if CODEX_CONFIG.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(text, encoding="utf-8")
        print(f"  [backup] Codex config.toml → {backup}")
    CODEX_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
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


def _backup_file(path: Path, *, backup_root: Path, label: str) -> Path | None:
    if not path.exists():
        return None
    backup = backup_root / "_backups" / f"{path.name}.{int(__import__('time').time())}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(path.read_bytes())
    print(f"  [backup] {label} → {backup}")
    return backup


def _toml_literal(value: str | Path) -> str:
    text = str(value)
    if "'" not in text:
        return f"'{text}'"
    return json.dumps(text, ensure_ascii=False)


def _expected_codex_mcp_block() -> str:
    return "\n".join([
        f"[mcp_servers.{GM_MCP_NAME}]",
        f"command = {_toml_literal(sys.executable)}",
        'args = ["-m", "harness.gm_mcp.server"]',
        "startup_timeout_sec = 120",
        "",
        f"[mcp_servers.{GM_MCP_NAME}.env]",
        f"PYTHONPATH = {_toml_literal(REPO)}",
        "",
    ])


def _without_codex_mcp_block(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    skipping = False
    target_headers = {
        f"[mcp_servers.{GM_MCP_NAME}]",
        f"[mcp_servers.{GM_MCP_NAME}.env]",
    }
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            skipping = stripped in target_headers
        if not skipping:
            kept.append(line)
    return "\n".join(kept).rstrip()


def ensure_codex_mcp_registration():
    """Idempotently register gm_search MCP server for Codex config.toml."""
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    old_text = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""
    base = _without_codex_mcp_block(old_text)
    expected = _expected_codex_mcp_block()
    new_text = (base + "\n\n" if base else "") + expected
    if old_text.rstrip() == new_text.rstrip():
        print("  [codex:mcp] global-memory 已注册且配置一致")
        return
    if CODEX_CONFIG.exists():
        _backup_file(CODEX_CONFIG, backup_root=CODEX_HOME, label="Codex config.toml")
    CODEX_CONFIG.write_text(new_text, encoding="utf-8")
    print("  [codex:mcp] 已写入 [mcp_servers.global-memory]")


def _normalize_path_text(text: str | Path) -> str:
    return str(text).replace("\\", "/").replace("\\\\?/", "").rstrip("/").lower()


def _claude_mcp_get() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["claude", "mcp", "get", GM_MCP_NAME],
        text=True,
        capture_output=True,
        errors="replace",
    )


def _claude_mcp_output_matches(output: str) -> bool:
    normalized = _normalize_path_text(output)
    return (
        _normalize_path_text(sys.executable) in normalized
        and "-m harness.gm_mcp.server" in output
        and f"pythonpath={_normalize_path_text(REPO)}" in normalized
    )


def ensure_claude_mcp_registration():
    """Register gm_search MCP for Claude Code via its CLI; never hand-edit ~/.claude.json."""
    if shutil.which("claude") is None:
        sys.exit("❌ Claude Code CLI 未找到。请先安装/登录 Claude Code，并确保 `claude` 在 PATH 中。")
    existing = _claude_mcp_get()
    combined = (existing.stdout or "") + (existing.stderr or "")
    if existing.returncode == 0 and _claude_mcp_output_matches(combined):
        print("  [claude:mcp] global-memory 已注册且配置一致")
        return
    backed_up = False
    def backup_once() -> None:
        nonlocal backed_up
        if not backed_up:
            _backup_file(CLAUDE_JSON, backup_root=HOME, label="Claude Code ~/.claude.json")
            backed_up = True
    if existing.returncode == 0:
        backup_once()
        subprocess.check_call(["claude", "mcp", "remove", GM_MCP_NAME, "-s", "user"])
        print("  [claude:mcp] 已移除旧 global-memory 注册")
    elif "not found" not in combined.lower() and "no server" not in combined.lower() and "不存在" not in combined:
        print(f"  [warn] claude mcp get 返回非零，继续尝试 add: {combined.strip()}")
    backup_once()
    subprocess.check_call([
        "claude", "mcp", "add", "-s", "user", GM_MCP_NAME,
        "-e", f"PYTHONPATH={REPO}",
        "--", sys.executable, "-m", "harness.gm_mcp.server",
    ])
    print("  [claude:mcp] 已注册 global-memory")


def check_preflight_requirements():
    """Fail loud for system-level prerequisites; bootstrap does not install them."""
    errors: list[str] = []
    if sys.platform != "win32":
        errors.append("当前 bootstrap portability 仅支持 Windows→Windows。")
    if sys.version_info < (3, 12):
        errors.append(
            f"Python 版本过低: {sys.version.split()[0]}。请安装 Python 3.12: winget install -e --id Python.Python.3.12"
        )
    if shutil.which("git") is None:
        errors.append("git 未找到。请安装 Git for Windows: winget install -e --id Git.Git")
    if shutil.which("ollama") is None:
        errors.append("Ollama 未找到。请安装 Ollama: winget install -e --id Ollama.Ollama")
    if errors:
        for error in errors:
            print(f"❌ {error}")
        sys.exit(1)
    print("  [preflight] git / Python 3.12 / Ollama OK")


def install_runtime_dependencies():
    if not REQUIREMENTS.exists():
        sys.exit(f"❌ requirements.txt 不存在: {REQUIREMENTS}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)], cwd=str(REPO))
    print("  [deps] runtime requirements 已安装")


def _ollama_tags(timeout: float = 5.0) -> dict:
    req = urllib.request.Request(OLLAMA_TAGS_URL, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _ollama_has_model(tags: dict, model: str = OLLAMA_MODEL) -> bool:
    for item in tags.get("models", []):
        name = str(item.get("name", ""))
        if name == model or name.startswith(f"{model}:"):
            return True
    return False


def ensure_ollama_model():
    try:
        tags = _ollama_tags()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        sys.exit(f"❌ Ollama API 不可用: {exc}。请先启动 Ollama（例如 `ollama serve` 或打开 Ollama 应用）。")
    if _ollama_has_model(tags):
        print(f"  [ollama] {OLLAMA_MODEL} 已存在")
        return
    print(f"  [ollama] {OLLAMA_MODEL} 缺失，开始 ollama pull {OLLAMA_MODEL}")
    subprocess.check_call(["ollama", "pull", OLLAMA_MODEL])
    print(f"  [ollama] {OLLAMA_MODEL} 已拉取")


def build_semantic_index():
    subprocess.check_call([sys.executable, "-m", "harness.semantic.cli", "build"], cwd=str(REPO))
    print("  [semantic] index 已构建/刷新")


def _module_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def check_runtime_dependencies(failed: list[str]):
    for module, package in [("mcp", "mcp"), ("yaml", "PyYAML")]:
        if not _module_available(module):
            failed.append(f"Python 依赖缺失: {package}（运行 bootstrap install 安装）")


def check_ollama_model(failed: list[str]):
    try:
        tags = _ollama_tags()
    except Exception as exc:
        failed.append(f"Ollama API 不可用或未启动: {exc}")
        return
    if not _ollama_has_model(tags):
        failed.append(f"Ollama 模型缺失: {OLLAMA_MODEL}（运行 `ollama pull {OLLAMA_MODEL}` 或 bootstrap install）")


def check_semantic_index(failed: list[str]):
    if not SEMANTIC_INDEX.exists():
        failed.append(f"语义索引缺失: {SEMANTIC_INDEX}（运行 python -m harness.semantic.cli build）")
        return
    try:
        from harness.semantic.index import status_path

        status = status_path(SEMANTIC_INDEX)
        if not status.get("ok"):
            failed.append(f"语义索引状态异常: {status}")
    except Exception as exc:
        failed.append(f"语义索引读取失败: {exc}")


def check_codex_mcp_registration(failed: list[str]):
    if not CODEX_CONFIG.exists():
        failed.append("Codex config.toml 不存在，缺少 MCP 注册")
        return
    text = CODEX_CONFIG.read_text(encoding="utf-8")
    required = [
        f"[mcp_servers.{GM_MCP_NAME}]",
        f"command = {_toml_literal(sys.executable)}",
        'args = ["-m", "harness.gm_mcp.server"]',
        f"[mcp_servers.{GM_MCP_NAME}.env]",
        f"PYTHONPATH = {_toml_literal(REPO)}",
    ]
    for item in required:
        if item not in text:
            failed.append(f"Codex MCP 注册不一致，缺少: {item}")


def check_claude_mcp_registration(failed: list[str]):
    if shutil.which("claude") is None:
        failed.append("Claude Code CLI 未找到，无法检查 user-scope MCP 注册")
        return
    result = _claude_mcp_get()
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        failed.append(f"Claude MCP global-memory 未注册: {output.strip()}")
        return
    if not _claude_mcp_output_matches(output):
        failed.append("Claude MCP global-memory 注册存在但 command/args/PYTHONPATH 与当前 repo 不一致")


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


def sync_claude_settings():
    """Render bootstrap-managed settings keys idempotently.

    Only hooks/statusLine are owned by bootstrap. If those two keys already
    match the rendered values, leave the file untouched and do not create a
    backup. Any drift in managed keys is backed up then refreshed.
    """
    settings_path = HOME / "settings.json"
    existing: dict = {}
    old_text: bytes | None = None
    if settings_path.exists():
        old_text = settings_path.read_bytes()
        try:
            existing = json.loads(old_text.decode("utf-8"))
        except Exception:
            existing = {}

    expected_hooks = hooks_json()
    expected_status_line = status_line_json()
    if settings_path.exists() and existing.get("hooks") == expected_hooks and existing.get("statusLine") == expected_status_line:
        print("  [settings] hooks/statusLine 已一致，跳过")
        return

    if settings_path.exists() and old_text is not None:
        backup = HOME / "_backups" / f"settings.json.{int(__import__('time').time())}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(old_text)
        print(f"  [backup] settings.json → {backup}")

    existing["hooks"] = expected_hooks
    existing["statusLine"] = expected_status_line
    settings_path.write_text(json.dumps(existing, indent=2))
    print(f"  [settings] 已渲染，{sum(len(v) for v in expected_hooks.values())} 组 hook + statusLine")


def install():
    print(f"REPO = {REPO}")
    print(f"HOME = {HOME}")
    if not (REPO / "harness").exists():
        sys.exit(f"❌ {REPO}/harness/ 不存在，bootstrap.py 必须在 repo 根。")
    check_preflight_requirements()
    manifest_errors = validate_hook_manifest(load_hook_manifest())
    if manifest_errors:
        for error in manifest_errors:
            print(f"❌ {error}")
        sys.exit(1)
    install_runtime_dependencies()
    ensure_ollama_model()
    build_semantic_index()
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

    # 5. 渲染 settings.json（保留非 hooks 字段；hooks/statusLine 幂等）
    sync_claude_settings()

    # 6. 从 Claude work skill 单源生成 Codex work skill 副本
    render_codex_work = REPO / "harness" / "scripts" / "render_codex_work_skill.py"
    if render_codex_work.exists():
        subprocess.check_call([sys.executable, str(render_codex_work)])
        print("  [codex] codex-work skill 已从 work skill 渲染")
    sync_codex_global_prompt()
    sync_codex_repo_skills()
    ensure_codex_mcp_registration()
    ensure_claude_mcp_registration()

    print("\n✅ install 完成。请运行 `python bootstrap.py check` 验证。")


def check():
    """只验证你真正在用的链路：/check, /work, Stop hook, diff_backup + skill junctions"""
    failed = []
    check_runtime_dependencies(failed)
    check_ollama_model(failed)
    check_semantic_index(failed)
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
    # diff_backup remains runtime; diff_show.py is retained but no longer registered.
    for h in ["diff_backup.py"]:
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
    for s in SKILLS:
        target = CODEX_SKILLS_ROOT / s
        source = REPO / "skills" / s / "v1"
        if not (target.exists() or target.is_symlink()):
            failed.append(f"Codex skill 缺失: {target}")
            continue
        if is_junction_or_link(target):
            try:
                if target.resolve() != source.resolve():
                    failed.append(f"Codex skill {s} link 指向错误: {target.resolve()}（期望 {source.resolve()}）")
            except OSError as e:
                failed.append(f"Codex skill {s} link 解析失败: {e}")
        elif not target.is_dir():
            failed.append(f"Codex skill {s} 不是目录或 link: {target}")
        elif not _same_file_bytes(target / "SKILL.md", source / "SKILL.md"):
            failed.append(f"Codex skill {s} 与 skills/{s}/v1/SKILL.md 内容不一致")
    if (CODEX_HOME / "gpt.md").exists() or (CODEX_HOME / "gpt.md").is_symlink():
        failed.append("Codex legacy gpt.md 仍存在，应迁移为 ctf.md（运行 bootstrap install 修复）")
    if CODEX_CONFIG.exists():
        try:
            config_text = CODEX_CONFIG.read_text(encoding="utf-8")
            if 'model_instructions_file = "./ctf.md"' not in config_text:
                failed.append("Codex config.toml model_instructions_file 未指向 ./ctf.md")
        except OSError as e:
            failed.append(f"Codex config.toml 读取失败: {e}")
    check_codex_mcp_registration(failed)
    check_claude_mcp_registration(failed)

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
    print(f"✅ 全绿（{len(SKILLS)} skill junction + agents + scripts + settings + 4 关键文件 + gm_search MCP + semantic index）")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "install"
    {"install": install, "check": check}.get(cmd, lambda: sys.exit(f"未知子命令: {cmd}"))()
