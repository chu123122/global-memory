"""主题管理：pyqtdarktheme-fork 封装 + 持久化 + 主题切换信号。

设计 §7.3：主体 PyQtDarkTheme，本任务用 fork 包 pyqtdarktheme-fork（Phase 0 spike 实证）。
设计 §7.4：qtawesome icon 不会随主题反色，需主动重建 —— theme_changed 信号是触发点。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import qdarktheme  # 实际包名 pyqtdarktheme-fork，import 命名空间是 qdarktheme
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

ThemeName = Literal["auto", "dark", "light"]
VALID_THEMES: tuple[ThemeName, ...] = ("auto", "dark", "light")

_CONFIG_PATH = Path.home() / ".claude" / "control_panel_pyside.json"
_DEFAULT_THEME: ThemeName = "dark"


class ThemeManager(QObject):
    """主题管理器，发 theme_changed(str) 通知所有订阅者。

    qdarktheme 不暴露原生主题切换信号，本类是唯一可信源。
    """

    theme_changed = Signal(str)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._current: ThemeName = self._load_persisted_theme()

    @property
    def current(self) -> ThemeName:
        return self._current

    def apply_initial(self) -> None:
        qdarktheme.setup_theme(self._current)

    def set_theme(self, theme: ThemeName) -> None:
        if theme not in VALID_THEMES:
            raise ValueError(f"invalid theme: {theme}, expected one of {VALID_THEMES}")
        if theme == self._current:
            return
        self._current = theme
        qdarktheme.setup_theme(theme)
        self._persist_theme(theme)
        self.theme_changed.emit(theme)

    def _load_persisted_theme(self) -> ThemeName:
        if not _CONFIG_PATH.exists():
            return _DEFAULT_THEME
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _DEFAULT_THEME
        theme = data.get("theme")
        if theme in VALID_THEMES:
            return theme  # type: ignore[return-value]
        return _DEFAULT_THEME

    def _persist_theme(self, theme: ThemeName) -> None:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing = (
                json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
                if _CONFIG_PATH.exists()
                else {}
            )
        except (OSError, json.JSONDecodeError):
            existing = {}
        existing["theme"] = theme
        _CONFIG_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
