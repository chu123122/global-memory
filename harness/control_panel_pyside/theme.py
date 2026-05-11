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
        border: 1px solid palette(midlight);
        border-left: 3px solid palette(highlight);
        border-radius: 6px;
    }
    QFrame#task-card {
        background: palette(alternate-base);
        border: 1px solid palette(midlight);
        border-left: 3px solid palette(highlight);
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
    QLabel#muted, QLabel#decision-why {
        color: palette(mid);
    }
    QLabel#task-brief-meta {
        color: palette(mid);
    }
    QLabel#task-brief-title {
        font-family: "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
        font-size: 15px;
        font-weight: 700;
    }
    QTextBrowser#markdown-reader {
        background: palette(base);
        border: 1px solid palette(midlight);
        border-radius: 8px;
        padding: 0;
        font-family: "Noto Serif SC", "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
        font-size: 14px;
        selection-background-color: palette(highlight);
        selection-color: palette(highlighted-text);
    }
    QTextBrowser#timeline-reader {
        background: palette(base);
        border: 1px solid palette(midlight);
        border-radius: 8px;
        padding: 2px;
        font-family: "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
        font-size: 13px;
    }
    QLabel#decision-headline, QLabel#decision-next {
        padding: 10px 12px;
        border-radius: 6px;
        font-weight: 600;
    }
    QLabel#decision-headline[role="ok"], QLabel#decision-next[role="ok"] {
        background: rgba(8, 116, 67, 0.14);
    }
    QLabel#decision-headline[role="info"], QLabel#decision-next[role="info"] {
        background: rgba(15, 61, 94, 0.12);
    }
    QLabel#decision-headline[role="warning"], QLabel#decision-next[role="warning"] {
        background: rgba(217, 119, 6, 0.16);
    }
    QLabel#decision-headline[role="error"], QLabel#decision-next[role="error"] {
        background: rgba(180, 35, 24, 0.16);
    }
    QLabel#status-badge {
        min-height: 20px;
        max-height: 20px;
        padding: 2px 8px;
        border-radius: 10px;
        color: white;
        font-size: 10px;
    }
    QLabel#status-badge[role="discussion"] { background: #3B82F6; }
    QLabel#status-badge[role="implementation"] { background: #10B981; }
    QLabel#status-badge[role="archived"] { background: #6B7280; }
    QLabel#status-badge[role="unknown"] { background: #6B7280; }
    QLabel#status-badge[role="missing"] { background: #EF4444; }
    QPushButton {
        min-height: 28px;
        padding: 6px 12px;
    }
    QPushButton[role="primary"] {
        background: palette(highlight);
        color: palette(highlighted-text);
        border: 1px solid palette(highlight);
        font-weight: 600;
    }
    /* P0-2 修：必须显式声明 primary 的 hover/pressed/disabled，
       否则被通用 QPushButton:hover（在 qdarktheme base 内）覆盖成灰底。 */
    QPushButton[role="primary"]:hover {
        background: palette(dark);
        color: palette(highlighted-text);
        border-color: palette(dark);
    }
    QPushButton[role="primary"]:pressed {
        background: palette(shadow);
        color: palette(highlighted-text);
    }
    QPushButton[role="primary"]:disabled {
        background: palette(midlight);
        color: palette(mid);
        border-color: palette(midlight);
    }
    QPushButton[role="danger"] {
        background: #a86b5e;
        color: #faf8f5;
        border: 1px solid #a86b5e;
        font-weight: 600;
    }
    QPushButton[role="danger"]:hover {
        background: #8d574b;
        color: #faf8f5;
        border-color: #8d574b;
    }

    /* === 三级卡片体系（UI-DESIGN-2026-04-28 方案 B） === */
    /* hero：结论卡，唯一视觉重心 */
    QFrame#verdict-hero {
        background: palette(base);
        border: 1px solid palette(midlight);
        border-left: 4px solid palette(highlight);
        border-radius: 2px;
    }
    QFrame#verdict-hero[severity="ok"]      { border-left-color: #8baa7d; }
    QFrame#verdict-hero[severity="info"]    { border-left-color: #7b9bb5; }
    QFrame#verdict-hero[severity="warning"] { border-left-color: #c8a165; }
    QFrame#verdict-hero[severity="error"]   { border-left-color: #b94a3a; }
    QFrame#verdict-hero QLabel#hero {
        font-size: 22pt;
        font-weight: 700;
    }
    QFrame#verdict-hero QLabel#hero-reason {
        font-size: 11pt;
        color: palette(mid);
    }
    QFrame#verdict-hero QLabel#hero-next {
        font-size: 12pt;
    }
    QFrame#verdict-hero QLabel#hero-next-cli {
        font-family: "Cascadia Mono", "JetBrains Mono", "Consolas", monospace;
        font-size: 11pt;
        color: palette(text);
    }
    QFrame#verdict-hero QFrame#hero-hairline {
        background: palette(midlight);
        max-height: 1px;
        min-height: 1px;
        border: none;
    }

    /* body：子系统 4 卡，平等 + 较小 */
    QFrame#subsystem-cell {
        background: palette(alternate-base);
        border: 1px solid palette(midlight);
        border-left: 3px solid palette(midlight);
        border-radius: 2px;
    }
    QFrame#subsystem-cell[severity="ok"]      { border-left-color: #8baa7d; }
    QFrame#subsystem-cell[severity="info"]    { border-left-color: #7b9bb5; }
    QFrame#subsystem-cell[severity="warning"] { border-left-color: #c8a165; }
    QFrame#subsystem-cell[severity="error"]   { border-left-color: #b94a3a; }
    QFrame#subsystem-cell QLabel#subsys-name {
        font-size: 11pt;
        font-weight: 600;
    }
    QFrame#subsystem-cell QLabel#subsys-summary {
        font-size: 11pt;
        color: palette(mid);
    }

    /* weak：侧栏文档项，视觉权重最低 */
    QListWidget#doc-sidebar-list {
        background: transparent;
        border: none;
        outline: 0;
    }
    QListWidget#doc-sidebar-list::item {
        padding: 6px 10px;
        color: palette(mid);
        border: none;
    }
    QListWidget#doc-sidebar-list::item:hover {
        background: palette(midlight);
        color: palette(text);
    }
    QListWidget#doc-sidebar-list::item:selected {
        background: palette(highlight);
        color: palette(highlighted-text);
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

    /* === Cards: 老 section-card 保留兼容（Day 2 view 改完会全切走） === */
    QFrame#section-card, QFrame#task-card {{
        background: {p['bg_card']};
        border: 1px solid {p['border']};
        border-left: 3px solid {p['accent_aka']};
        border-radius: 2px;
    }}
    QFrame#task-card:hover {{
        background: {p['bg_card_hover']};
    }}

    /* === 三级卡片体系（hanaarashi 定制，UI-DESIGN 方案 B） === */
    /* hero：结论卡，唯一视觉重心；衬线 + 留白 + 硬直直角 + sev 色边 */
    QFrame#verdict-hero {{
        background: {p['bg_input']};
        border: 1px solid {p['border']};
        border-left: 4px solid {p['accent_aka']};
        border-radius: 2px;
    }}
    QFrame#verdict-hero[severity="ok"]      {{ border-left-color: {p['accent_green']}; }}
    QFrame#verdict-hero[severity="info"]    {{ border-left-color: {p['accent_blue']}; }}
    QFrame#verdict-hero[severity="warning"] {{ border-left-color: {p['accent_earth']}; }}
    QFrame#verdict-hero[severity="error"]   {{ border-left-color: #b94a3a; }}
    QFrame#verdict-hero QLabel#hero {{
        font-family: {serif};
        font-size: 22pt;
        font-weight: 700;
        color: {p['ink_primary']};
    }}
    QFrame#verdict-hero QLabel#hero-reason {{
        font-family: {sans};
        font-size: 11pt;
        color: {p['ink_muted']};
    }}
    QFrame#verdict-hero QLabel#hero-next {{
        font-family: {sans};
        font-size: 12pt;
        color: {p['ink_secondary']};
    }}
    QFrame#verdict-hero QLabel#hero-next-cli {{
        font-family: "Cascadia Mono", "JetBrains Mono", "Consolas", monospace;
        font-size: 11pt;
        color: {p['ink_primary']};
        background: {p['bg_card']};
        padding: 2px 6px;
        border-radius: 2px;
    }}
    QFrame#verdict-hero QFrame#hero-hairline {{
        background: {p['border']};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}

    /* body：子系统 4 卡 */
    QFrame#subsystem-cell {{
        background: {p['bg_input']};
        border: 1px solid {p['border']};
        border-left: 3px solid {p['border_strong']};
        border-radius: 2px;
    }}
    QFrame#subsystem-cell[severity="ok"]      {{ border-left-color: {p['accent_green']}; }}
    QFrame#subsystem-cell[severity="info"]    {{ border-left-color: {p['accent_blue']}; }}
    QFrame#subsystem-cell[severity="warning"] {{ border-left-color: {p['accent_earth']}; }}
    QFrame#subsystem-cell[severity="error"]   {{ border-left-color: #b94a3a; }}
    QFrame#subsystem-cell QLabel#subsys-name {{
        font-family: {sans};
        font-size: 11pt;
        font-weight: 600;
        color: {p['ink_primary']};
    }}
    QFrame#subsystem-cell QLabel#subsys-summary {{
        font-family: {sans};
        font-size: 11pt;
        color: {p['ink_muted']};
    }}

    /* weak：侧栏文档项，纯文字 list */
    QListWidget#doc-sidebar-list {{
        background: transparent;
        border: none;
        outline: 0;
    }}
    QListWidget#doc-sidebar-list::item {{
        padding: 6px 10px;
        color: {p['ink_muted']};
        border: none;
    }}
    QListWidget#doc-sidebar-list::item:hover {{
        background: {p['bg_card']};
        color: {p['ink_primary']};
    }}
    QListWidget#doc-sidebar-list::item:selected {{
        background: {p['accent_aka']};
        color: #fffdf9;
    }}

    /* === Labels === */
    QLabel {{ background: transparent; color: {p['ink_primary']}; }}
    QLabel#muted, QLabel#decision-why, QLabel#task-brief-meta {{ color: {p['ink_muted']}; }}
    QLabel#task-brief-title {{
        font-family: {sans};
        font-size: 15px;
        font-weight: 700;
    }}
    QTextBrowser#markdown-reader {{
        background: {p['bg_input']};
        color: {p['ink_primary']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 0;
        font-family: "Noto Serif SC", "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
        font-size: 14px;
        selection-background-color: {p['accent_aka']};
        selection-color: #fffdf9;
    }}
    QTextBrowser#timeline-reader {{
        background: {p['bg_input']};
        color: {p['ink_primary']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 2px;
        font-family: "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
        font-size: 13px;
    }}
    QLabel#decision-headline, QLabel#decision-next {{
        padding: 10px 12px;
        border-radius: 6px;
        font-weight: 600;
    }}
    QLabel#decision-headline[role="ok"], QLabel#decision-next[role="ok"] {{ background: rgba(139, 170, 125, 0.22); }}
    QLabel#decision-headline[role="info"], QLabel#decision-next[role="info"] {{ background: rgba(123, 155, 181, 0.18); }}
    QLabel#decision-headline[role="warning"], QLabel#decision-next[role="warning"] {{ background: rgba(200, 161, 101, 0.22); }}
    QLabel#decision-headline[role="error"], QLabel#decision-next[role="error"] {{ background: rgba(196, 123, 107, 0.22); }}
    QLabel#status-badge {{
        min-height: 20px;
        max-height: 20px;
        padding: 2px 8px;
        border-radius: 10px;
        color: #fffdf9;
        font-size: 10px;
    }}
    QLabel#status-badge[role="discussion"] {{ background: {p['accent_blue']}; }}
    QLabel#status-badge[role="implementation"] {{ background: {p['accent_green']}; }}
    QLabel#status-badge[role="archived"], QLabel#status-badge[role="unknown"] {{ background: {p['ink_muted']}; }}
    QLabel#status-badge[role="missing"] {{ background: {p['accent_aka']}; }}

    /* === Buttons === */
    QPushButton {{
        background: {p['bg_input']};
        color: {p['ink_primary']};
        border: 1px solid {p['border']};
        border-radius: 2px;
        padding: 7px 14px;
        min-height: 30px;
        font-family: {sans};
    }}
    /* primary 改用 accent_aka 红（比 accent_blue 灰青更显眼，符合"稀缺出现的红"原则） */
    QPushButton[role="primary"] {{
        background: {p['accent_aka']};
        color: #fffdf9;
        border: 1px solid {p['accent_aka']};
        font-weight: 600;
    }}
    QPushButton[role="danger"] {{
        background: #b94a3a;
        color: #fffdf9;
        border: 1px solid #b94a3a;
        font-weight: 600;
    }}
    /* 通用 hover：仅作用于普通按钮（无 role），primary/danger 必须各自显式声明 hover */
    QPushButton:hover {{
        background: {p['bg_card']};
        color: {p['accent_aka']};
        border-color: {p['accent_aka']};
    }}
    QPushButton:pressed {{
        background: {p['bg_card_hover']};
    }}
    /* P0-2 修：primary 显式 hover/pressed/disabled，否则被通用 :hover 覆盖成米色 */
    QPushButton[role="primary"]:hover {{
        background: #b56a5a;
        color: #fffdf9;
        border-color: #b56a5a;
    }}
    QPushButton[role="primary"]:pressed {{
        background: #a05a4d;
        color: #fffdf9;
        border-color: #a05a4d;
    }}
    QPushButton[role="primary"]:disabled {{
        background: #d8c4be;
        color: #faf0ec;
        border-color: #d8c4be;
    }}
    QPushButton[role="danger"]:hover {{
        background: #a83d2e;
        color: #fffdf9;
        border-color: #a83d2e;
    }}
    QPushButton[role="danger"]:pressed {{
        background: #8e3325;
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
