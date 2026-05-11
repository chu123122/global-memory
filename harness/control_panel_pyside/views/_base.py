"""_BasePage：所有页签的基类。

Day 3 修复 V7：默认隐藏 page header（title 与 tab 名重复，subtitle 移到 tab 的 tooltip）。
子类如需显示标题，自行在 _build_content 内加 QLabel。

  - 内嵌 QScrollArea
  - 子类实现 _build_content(layout) 把内容塞进 scroll 区
  - 提供 refresh() 抽象方法，主窗口在切换到该页时调用
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class _BasePage(QWidget):
    title: str = "(未命名页)"
    subtitle: str = ""
    auto_refresh_interval_sec: float = 8.0

    def __init__(self) -> None:
        super().__init__()
        self._last_refresh_at = 0.0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Day 3 V7 修：默认不渲染 page header；title 由 tab bar 显示，
        # subtitle 由 main_window 设到 QTabWidget 的 tooltip
        # （子类如需特殊标题可在 _build_content 自加）

        # 内容区 QScrollArea + content widget
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(self._scroll, stretch=1)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 14, 16, 14)
        self._content_layout.setSpacing(12)
        self._scroll.setWidget(self._content)

        self._build_content(self._content_layout)
        # 末尾撑开器，避免内容少时全堆顶
        self._content_layout.addStretch(1)

    def _build_content(self, layout: QVBoxLayout) -> None:  # noqa: ARG002
        """子类必须实现：往 layout 添加该页内容。"""
        raise NotImplementedError

    def refresh(self) -> None:
        """主窗口切到该页时调用；默认 no-op，子类按需重写。"""

    def maybe_refresh(self, force: bool = False) -> None:
        """Throttle automatic refreshes caused by tab switching."""
        now = time.monotonic()
        if force or now - self._last_refresh_at >= self.auto_refresh_interval_sec:
            self._last_refresh_at = now
            self.refresh()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        """主题切换时调用；子类按需重写以重建 qtawesome 图标。"""
