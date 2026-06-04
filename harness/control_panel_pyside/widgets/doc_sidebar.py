"""关键文档常驻侧栏（Day 3 弱化）：QListWidget 纯文字列表，视觉权重低于主区。"""
from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

GM_ROOT = Path.home() / ".claude" / "global-memory"

# (label, icon, path) — 写死 6 个
DOC_LINKS: list[tuple[str, str, Path]] = [
    ("MEMORY.md", "fa5s.brain", GM_ROOT / "MEMORY.md"),
    ("CHANGELOG.md", "fa5s.history", GM_ROOT / "CHANGELOG.md"),
    ("conventions.md", "fa5s.book", GM_ROOT / "decisions" / "conventions.md"),
    ("MAINTENANCE.md", "fa5s.wrench", GM_ROOT / "docs" / "guide" / "MAINTENANCE.md"),
    ("FIXLIST.md", "fa5s.tasks", GM_ROOT / "FIXLIST.md"),
    ("CONTROL_PANEL.md", "fa5s.sliders-h", GM_ROOT / "docs" / "guide" / "CONTROL_PANEL.md"),
]


class DocSidebar(QFrame):
    """常驻右侧侧栏：QListWidget + 弱化样式（无边框、缩字号、灰色 hover）。"""

    def __init__(self, main_window) -> None:
        super().__init__()
        self._main = main_window
        self.setObjectName("doc-sidebar")
        # Day 3：220 → 180，让出主区视觉权重
        self.setFixedWidth(180)
        self._items_with_path: list[tuple[Path, str]] = []  # (path, icon_name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        title = QLabel("关键文档")
        title.setObjectName("doc-sidebar-title")
        title.setFont(QFont("", 9, QFont.Weight.DemiBold))
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setObjectName("doc-sidebar-list")
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.itemActivated.connect(self._on_item_activated)
        self._list.itemClicked.connect(self._on_item_activated)

        for label, icon_name, path in DOC_LINKS:
            item = QListWidgetItem(qta.icon(icon_name), label)
            if not path.exists():
                item.setToolTip(f"未找到：{path}")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                item.setToolTip(str(path))
            self._list.addItem(item)
            self._items_with_path.append((path, icon_name))

        layout.addWidget(self._list, stretch=1)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        idx = self._list.row(item)
        if 0 <= idx < len(self._items_with_path):
            path, _ = self._items_with_path[idx]
            if path.exists():
                self._main.open_path(path)

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for idx, (_path, icon_name) in enumerate(self._items_with_path):
            item = self._list.item(idx)
            if item:
                item.setIcon(qta.icon(icon_name))
