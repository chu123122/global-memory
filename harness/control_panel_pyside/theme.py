"""主题管理：pyqtdarktheme-fork 封装 + 持久化 + 主题切换信号。

设计 §7.3：主体 PyQtDarkTheme，本任务用 fork 包 pyqtdarktheme-fork（Phase 0 spike 实证）。
设计 §7.4：qtawesome icon 不会随主题反色，需主动重建 —— theme_changed 信号是触发点。

新增 hanaarashi 主题：迁博客「花と嵐」日式文学性极简调（非纯 Apple 极简）。
- 暖白底 #faf8f5 / 克制赤 #c47b6b / 灰青 #7b9bb5 / 灰绿 #8baa7d
- 衬线字体（Shippori Mincho / Noto Serif SC fallback）
- 拒绝纯黑 / 霓虹 / 高饱和
- 状态栏右下角 8% 透明度的竖排日文耳语（main_window 装配）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import qdarktheme  # 实际包名 pyqtdarktheme-fork，import 命名空间是 qdarktheme
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

ThemeName = Literal["auto", "dark", "light", "hanaarashi"]
VALID_THEMES: tuple[ThemeName, ...] = ("auto", "dark", "light", "hanaarashi")

_CONFIG_PATH = Path.home() / ".claude" / "control_panel_pyside.json"
_DEFAULT_THEME: ThemeName = "dark"


# 「花と嵐」调色（与博客同源 https://github.com/chu123122/blog redesign-astro）
HANAARASHI = {
    "bg_base": "#faf8f5",        # 暖白·纸感
    "bg_card": "#f3ede4",        # 卡片底
    "bg_card_hover": "#ebe2d4",  # hover
    "bg_input": "#fffdf9",       # 输入区·更白一点
    "ink_primary": "#2c2418",    # 暖近黑（拒绝 #000）
    "ink_secondary": "#6b5d4f",  # 暖灰
    "ink_muted": "#9a8c7a",      # 灰土
    "accent_aka": "#c47b6b",     # 克制赤·主强调色
    "accent_blue": "#7b9bb5",    # 灰青·discussion
    "accent_green": "#8baa7d",   # 灰绿·implementation
    "accent_earth": "#c8a165",   # 赭·warning
    "border": "#e0d6c4",         # 暖白底上的细线
    "border_strong": "#c4b9a6",
}


def _base_card_qss() -> str:
    """跨主题（dark / light / auto）的卡片底色 + 调试输出终端调，用 palette() 引用主题色。

    解决 view 层 setObjectName('section-card' / 'task-card') 的 QFrame 在
    qdarktheme 默认 palette 下没有可视化背景的问题。
    debug-output 用暖色终端调（#241e18），跨主题统一不再用纯黑/纯白冲突。"""
    return """
    QFrame#section-card {
        background: palette(alternate-base);
        border-radius: 6px;
    }
    QFrame#task-card {
        background: palette(alternate-base);
        border-radius: 8px;
        padding: 10px;
    }
    QFrame#task-card:hover {
        background: palette(midlight);
    }
    QPlainTextEdit#debug-output {
        background: #241e18;
        color: #d8cfc0;
        font-family: "Cascadia Mono", "JetBrains Mono", monospace;
        border: none;
        selection-background-color: #c47b6b;
        selection-color: white;
    }
    """


def _hanaarashi_qss() -> str:
    p = HANAARASHI
    serif = '"Shippori Mincho", "Zen Old Mincho", "Noto Serif SC", "Source Han Serif SC", "宋体", serif'
    sans = '"Noto Sans SC", "Source Han Sans SC", "Microsoft YaHei UI", sans-serif'
    return f"""
    /* === Base === */
    QWidget {{
        background-color: {p['bg_base']};
        color: {p['ink_primary']};
        font-family: {sans};
        font-size: 11pt;
    }}
    QMainWindow, QDialog {{ background-color: {p['bg_base']}; }}

    /* === MenuBar / Menu === */
    QMenuBar {{
        background: {p['bg_base']};
        border-bottom: 1px solid {p['border']};
        padding: 2px 4px;
    }}
    QMenuBar::item {{
        padding: 6px 12px;
        background: transparent;
        color: {p['ink_secondary']};
    }}
    QMenuBar::item:selected {{
        background: {p['bg_card']};
        color: {p['accent_aka']};
    }}
    QMenu {{
        background: {p['bg_input']};
        border: 1px solid {p['border']};
        padding: 4px 0;
    }}
    QMenu::item {{ padding: 6px 18px; }}
    QMenu::item:selected {{ background: {p['bg_card_hover']}; color: {p['accent_aka']}; }}
    QMenu::separator {{ height: 1px; background: {p['border']}; margin: 4px 8px; }}

    /* === Tab === */
    QTabWidget::pane {{
        border: none;
        background: {p['bg_base']};
    }}
    QTabBar {{
        background: {p['bg_base']};
        border-bottom: 1px solid {p['border']};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {p['ink_muted']};
        padding: 10px 18px;
        margin-right: 2px;
        border: none;
        font-family: {serif};
        font-size: 11pt;
    }}
    QTabBar::tab:hover {{
        color: {p['ink_secondary']};
    }}
    QTabBar::tab:selected {{
        color: {p['accent_aka']};
        border-bottom: 2px solid {p['accent_aka']};
    }}

    /* === Cards === */
    QFrame#section-card, QFrame#task-card {{
        background: {p['bg_card']};
        border: none;
        border-radius: 4px;
    }}
    QFrame#task-card:hover {{
        background: {p['bg_card_hover']};
    }}

    /* === Labels === */
    QLabel {{ background: transparent; color: {p['ink_primary']}; }}

    /* === Buttons === */
    QPushButton {{
        background: {p['bg_input']};
        color: {p['ink_primary']};
        border: 1px solid {p['border']};
        border-radius: 3px;
        padding: 7px 14px;
        font-family: {sans};
    }}
    QPushButton:hover {{
        background: {p['bg_card']};
        color: {p['accent_aka']};
        border-color: {p['accent_aka']};
    }}
    QPushButton:pressed {{
        background: {p['bg_card_hover']};
    }}

    /* === Inputs === */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
        background: {p['bg_input']};
        color: {p['ink_primary']};
        border: 1px solid {p['border']};
        border-radius: 3px;
        padding: 5px 8px;
        selection-background-color: {p['accent_aka']};
        selection-color: white;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border-color: {p['accent_aka']};
    }}
    QPlainTextEdit#debug-output {{
        background: #1e1814;
        color: #d8cfc0;
        font-family: "Cascadia Mono", "JetBrains Mono", monospace;
    }}

    /* === Tree / List === */
    QTreeWidget, QListWidget, QTableView {{
        background: {p['bg_base']};
        alternate-background-color: {p['bg_card']};
        border: 1px solid {p['border']};
        border-radius: 3px;
        outline: 0;
    }}
    QTreeWidget::item, QListWidget::item {{
        padding: 4px;
        border: none;
    }}
    QTreeWidget::item:hover, QListWidget::item:hover {{
        background: {p['bg_card_hover']};
    }}
    QTreeWidget::item:selected, QListWidget::item:selected {{
        background: {p['accent_aka']};
        color: white;
    }}
    QHeaderView::section {{
        background: {p['bg_card']};
        color: {p['ink_secondary']};
        border: none;
        border-right: 1px solid {p['border']};
        padding: 6px 8px;
        font-family: {serif};
    }}

    /* === ScrollBars (slim minimal) === */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {p['border_strong']};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p['accent_aka']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p['border_strong']};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {p['accent_aka']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* === StatusBar === */
    QStatusBar {{
        background: {p['bg_base']};
        border-top: 1px solid {p['border']};
        color: {p['ink_secondary']};
    }}
    QStatusBar QLabel#whisper {{
        color: {p['ink_primary']};
        font-family: {serif};
        font-size: 9pt;
    }}

    /* === Splitter handle (近不可见) === */
    QSplitter::handle {{
        background: {p['border']};
    }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    /* === Dock === */
    QDockWidget {{
        color: {p['ink_secondary']};
        titlebar-close-icon: none;
    }}
    QDockWidget::title {{
        background: {p['bg_card']};
        padding: 4px 10px;
        font-family: {serif};
    }}
    """


class ThemeManager(QObject):
    """主题管理器，发 theme_changed(str) 通知所有订阅者。

    qdarktheme 不暴露原生主题切换信号，本类是唯一可信源。
    hanaarashi 走自定义 QSS 路径，不调 qdarktheme.setup_theme（会被覆盖）。
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
        self._apply(self._current)

    def set_theme(self, theme: ThemeName) -> None:
        if theme not in VALID_THEMES:
            raise ValueError(f"invalid theme: {theme}, expected one of {VALID_THEMES}")
        if theme == self._current:
            return
        self._current = theme
        self._apply(theme)
        self._persist_theme(theme)
        self.theme_changed.emit(theme)

    def _apply(self, theme: ThemeName) -> None:
        # qdarktheme.setup_theme() 会调 QApplication.setStyleSheet() 设置整套 QSS。
        # 我们的额外 QSS 必须 append，不能 replace，否则 qdarktheme 的 widget 样式全没。
        if theme == "hanaarashi":
            qdarktheme.setup_theme("light")  # 浅色基线 palette
            base = self._app.styleSheet()
            self._app.setStyleSheet(base + _hanaarashi_qss())
        else:
            qdarktheme.setup_theme(theme)
            base = self._app.styleSheet()
            self._app.setStyleSheet(base + _base_card_qss())

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
