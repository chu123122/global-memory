"""关键文档常驻侧栏（v2.1 新增）：固定 4-6 个跳转按钮，点击=系统默认编辑器打开。"""
from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

GM_ROOT = Path.home() / ".claude" / "global-memory"

# (label, icon, path) — 写死 6 个；动态"当前任务 SPEC/HANDOFF" 暂不做，
# 用户需要看具体任务文档可走"任务"tab → 卡片 → 文件管理器
DOC_LINKS: list[tuple[str, str, Path]] = [
    ("MEMORY.md", "fa5s.brain", GM_ROOT / "MEMORY.md"),
    ("CHANGELOG.md", "fa5s.history", GM_ROOT / "CHANGELOG.md"),
    ("conventions.md", "fa5s.book", GM_ROOT / "decisions" / "conventions.md"),
    ("MAINTENANCE.md", "fa5s.wrench", GM_ROOT / "MAINTENANCE.md"),
    ("FIXLIST.md", "fa5s.tasks", GM_ROOT / "FIXLIST.md"),
    ("CONTROL_PANEL.md", "fa5s.sliders-h", GM_ROOT / "CONTROL_PANEL.md"),
]


class DocSidebar(QFrame):
    """常驻右侧固定宽度侧栏。"""

    def __init__(self, main_window) -> None:
        super().__init__()
        self._main = main_window
        self.setObjectName("doc-sidebar")
        self.setFixedWidth(220)
        self._buttons: list[tuple[QPushButton, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("关键文档")
        title.setObjectName("section-title")
        layout.addWidget(title)

        for label, icon_name, path in DOC_LINKS:
            btn = QPushButton(qta.icon(icon_name), label)
            btn.setProperty("role", "secondary")
            btn.setEnabled(path.exists())
            if not path.exists():
                btn.setToolTip(f"未找到：{path}")
            else:
                btn.setToolTip(str(path))
            btn.clicked.connect(lambda _checked=False, p=path: self._main.open_path(p))
            layout.addWidget(btn)
            self._buttons.append((btn, icon_name))

        layout.addStretch(1)

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._buttons:
            btn.setIcon(qta.icon(icon_name))
