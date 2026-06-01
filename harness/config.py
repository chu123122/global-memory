#!/usr/bin/env python3
"""Shared path configuration for the global-memory harness.

This module is intentionally small and side-effect free. Scripts should import
these constants instead of repeating Path.home() / environment fallback logic.
"""
from __future__ import annotations

import os
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
SCRIPTS_DIR = HARNESS_DIR / "scripts"


def env_path(name: str, default: str | Path) -> Path:
    raw = os.environ.get(name)
    if raw:
        return Path(raw).expanduser()
    return Path(default).expanduser()


def claude_home() -> Path:
    """Return the configured Claude home.

    CLAUDE_HOME is the current public knob. CLAUDE_DIR is retained for older
    harness scripts that used that name.
    """
    raw = os.environ.get("CLAUDE_HOME") or os.environ.get("CLAUDE_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".claude"


MEMORY_ROOT = env_path("GLOBAL_MEMORY_DIR", REPO_DIR)
CLAUDE_HOME = claude_home()
CLAUDE_SETTINGS = CLAUDE_HOME / "settings.json"
CLAUDE_LOGS_DIR = env_path("CLAUDE_LOGS_DIR", CLAUDE_HOME / "logs")
CLAUDE_CACHE_DIR = env_path("CLAUDE_CACHE_DIR", CLAUDE_HOME / "cache")
CLAUDE_TASKS_ROOT = env_path("CLAUDE_TASKS_ROOT", CLAUDE_HOME / "tasks")
CLAUDE_TASKS_ACTIVE = env_path("CLAUDE_TASKS_ACTIVE", CLAUDE_TASKS_ROOT / "active")
CLAUDE_TASKS_ARCHIVED = env_path("CLAUDE_TASKS_ARCHIVED", CLAUDE_TASKS_ROOT / "archived")
GLOBAL_SKILLS_DIR = env_path("GLOBAL_SKILLS_DIR", MEMORY_ROOT / "skills")
GLOBAL_TEMPLATES_DIR = env_path("GLOBAL_TEMPLATES_DIR", MEMORY_ROOT / "templates")
GLOBAL_AGENTS_DIR = env_path("GLOBAL_AGENTS_DIR", MEMORY_ROOT / "agents")
GLOBAL_HARNESS_ROOT = env_path("GLOBAL_HARNESS_DIR", HARNESS_DIR)


def repo_path(*parts: str) -> Path:
    return REPO_DIR.joinpath(*parts)


def harness_path(*parts: str) -> Path:
    return HARNESS_DIR.joinpath(*parts)


def script_path(*parts: str) -> Path:
    return SCRIPTS_DIR.joinpath(*parts)


def memory_path(*parts: str) -> Path:
    return MEMORY_ROOT.joinpath(*parts)
