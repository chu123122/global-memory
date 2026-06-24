#!/usr/bin/env python3
"""
deploy_hooks.py — Hook 部署脚本

1. 备份 settings.json
2. 复制 hooks/*.py → ~/.claude/scripts/hooks/
3. 合并 hook 配置到 settings.json（保留已有 Stop hook 等）

幂等：重复运行结果一致。
"""

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

# ── 路径 ──
CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
BACKUP_DIR = CLAUDE_DIR / "backups"

HOOKS_SRC = Path(__file__).resolve().parent.parent / "hooks"
HOOKS_DST = CLAUDE_DIR / "scripts" / "hooks"

# Python：直接用 PATH 中的 python，避免硬编码绝对路径
# Claude Code hook 在 bash 中执行，路径必须用正斜杠
PYTHON_CMD = "python"


def make_command(script_name: str) -> str:
    """生成 hook command 字符串（bash 兼容，正斜杠）。"""
    script_path = str(HOOKS_DST / script_name).replace("\\", "/")
    return f"{PYTHON_CMD} {script_path}"


# ── 受管的 hook 定义 ──
MANAGED_HOOKS = {
    "PreToolUse": [
        {
            "matcher": "Bash",
            "hooks": [{
                "type": "command",
                "command": make_command("dangerous_command_blocker.py"),
            }]
        },
        {
            "matcher": "Write|Edit",
            "hooks": [
                {
                    "type": "command",
                    "command": make_command("memory_file_protector.py"),
                },
                {
                    "type": "command",
                    "command": make_command("spec_gate.py"),
                },
            ]
        },
    ],
    "PostToolUse": [
        {
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": make_command("audit_logger.py"),
            }]
        },
    ],
}


def backup_settings():
    """备份当前 settings.json。"""
    if not SETTINGS_FILE.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"settings_{ts}.json"
    shutil.copy2(SETTINGS_FILE, backup)
    print(f"  Backed up: {backup.name}")


def copy_hook_scripts():
    """复制 hook 脚本到部署目标。"""
    HOOKS_DST.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src_file in HOOKS_SRC.glob("*.py"):
        dst_file = HOOKS_DST / src_file.name
        shutil.copy2(src_file, dst_file)
        copied += 1
        print(f"  Deployed: {src_file.name}")
    return copied


def merge_hooks_into_settings():
    """
    合并策略：
    - 保留所有非 hooks 键
    - 保留不受管的 hook 事件（如 Stop）
    - 替换受管的 hook 事件（PreToolUse/PostToolUse）
    """
    if SETTINGS_FILE.exists():
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    else:
        settings = {}

    if "hooks" not in settings:
        settings["hooks"] = {}

    for event_name, event_hooks in MANAGED_HOOKS.items():
        settings["hooks"][event_name] = event_hooks

    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )


def verify():
    """验证部署结果。"""
    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})
    print("\n  Hook events in settings.json:")
    for event, groups in hooks.items():
        matchers = [g.get("matcher", "(all)") or "(all)" for g in groups]
        print(f"    {event}: {len(groups)} group(s) — matchers: {', '.join(matchers)}")


def main():
    print("=" * 50)
    print("  deploy_hooks.py — Hook Deployment")
    print("=" * 50)

    # 1. Backup
    print("\nStep 1: Backup")
    backup_settings()

    # 2. Copy scripts
    print("\nStep 2: Deploy hook scripts")
    count = copy_hook_scripts()
    print(f"  {count} scripts → {HOOKS_DST}")

    # 3. Merge settings
    print("\nStep 3: Update settings.json")
    merge_hooks_into_settings()
    print("  settings.json updated")

    # 4. Verify
    print("\nStep 4: Verify")
    verify()

    # 5. Create logs dir
    log_dir = CLAUDE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n  Log directory: {log_dir}")

    print("\n" + "=" * 50)
    print("  Done. Restart Claude Code to activate hooks.")
    print("=" * 50)


if __name__ == "__main__":
    main()
