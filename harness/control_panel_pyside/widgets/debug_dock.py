"""底部折叠调试输出区（v2.1 新增）：默认折叠，标题栏一行；展开后显示 CLI 原始输出。

替代 v2.0 的 QDockWidget+菜单切换：
  - 默认折叠 → 用户察觉不到，认知负担为零
  - 出问题手动展开看 stdout/stderr
"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

MAX_BLOCKS = 500
COLLAPSED_HEIGHT = 28
EXPANDED_HEIGHT = 220


class DebugDock(QWidget):
    """折叠/展开切换的底部调试区。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("debug-dock")
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 标题栏（始终可见）
        header = QWidget()
        header.setObjectName("debug-dock-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 2, 8, 2)
        header_layout.setSpacing(6)

        self._toggle_btn = QToolButton()
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.setText("调试输出")
        self._toggle_btn.setIcon(qta.icon("fa5s.chevron-right"))
        self._toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle_btn.setAutoRaise(True)
        self._toggle_btn.toggled.connect(self._on_toggled)
        header_layout.addWidget(self._toggle_btn)

        header_layout.addStretch(1)
        self._hint = QLabel("（出问题展开看 CLI 原始输出）")
        self._hint.setObjectName("muted")
        header_layout.addWidget(self._hint)
        outer.addWidget(header)

        # 文本区（折叠时隐藏）
        self._text = QPlainTextEdit()
        self._text.setObjectName("debug-output")
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(MAX_BLOCKS)
        self._text.hide()
        outer.addWidget(self._text)

        self.setFixedHeight(COLLAPSED_HEIGHT)

    # ---- 行为 ----
    def _on_toggled(self, checked: bool) -> None:
        self._expanded = checked
        if checked:
            self._toggle_btn.setIcon(qta.icon("fa5s.chevron-down"))
            self._text.show()
            self.setFixedHeight(EXPANDED_HEIGHT)
        else:
            self._toggle_btn.setIcon(qta.icon("fa5s.chevron-right"))
            self._text.hide()
            self.setFixedHeight(COLLAPSED_HEIGHT)

    def append(self, text: str, reveal: bool = False) -> None:
        self._text.appendPlainText(text.rstrip("\n"))
        if reveal and not self._expanded:
            self._toggle_btn.setChecked(True)

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        # 重建 chevron 图标（与 _on_toggled 当前态保持一致）
        if self._expanded:
            self._toggle_btn.setIcon(qta.icon("fa5s.chevron-down"))
        else:
            self._toggle_btn.setIcon(qta.icon("fa5s.chevron-right"))
