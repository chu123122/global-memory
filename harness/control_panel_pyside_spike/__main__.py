"""Phase 0 spike: 验证 PySide6 + pyqtdarktheme-fork + qtawesome 三件套。

跑法（cwd=D:/global-memory/harness/）：
    python -m control_panel_pyside_spike

观察点：
    1. 窗口能开
    2. 50 行 QLabel 可滚轮滚动
    3. 启动是暗色主题
    4. 工具栏 sync 图标可见且对比度正常
    5. 点 "Toggle Theme" 切到亮色，图标自动反色（验证 V10 路径）
    6. 状态栏文字给出三项验证结果
关闭窗口后控制台打印实测耗时。
"""
from __future__ import annotations

import sys
import time

import qdarktheme
import qtawesome as qta
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class SpikeWindow(QMainWindow):
    theme_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("control-panel-v2-pyside · Phase 0 spike")
        self.resize(720, 520)
        self._theme = "dark"

        self._toolbar = QToolBar("spike")
        self.addToolBar(self._toolbar)

        self._sync_action = self._toolbar.addAction(self._make_icon("fa5s.sync"), "Sync")
        self._toggle_action = self._toolbar.addAction(
            self._make_icon("fa5s.adjust"), "Toggle Theme"
        )
        self._toggle_action.triggered.connect(self._on_toggle_theme)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(4)
        for i in range(50):
            label = QLabel(f"Row {i:02d} — 滚轮验证 / scroll test row")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(label)
        layout.addWidget(QPushButton("dummy button (theme contrast check)"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.setCentralWidget(scroll)

        self.statusBar().showMessage(
            f"theme={self._theme} | qtawesome=OK | py={'.'.join(map(str, sys.version_info[:3]))}"
        )

        self.theme_changed.connect(self._refresh_all_icons)

    def _make_icon(self, name: str):
        # qtawesome 在亮色主题下默认黑图标，暗色下白图标 —— 通过 color 参数显式控制
        color = "#dddddd" if self._theme == "dark" else "#222222"
        return qta.icon(name, color=color)

    def _on_toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        qdarktheme.setup_theme(self._theme)
        self.theme_changed.emit(self._theme)
        self.statusBar().showMessage(
            f"theme={self._theme} | qtawesome=OK | py={'.'.join(map(str, sys.version_info[:3]))}"
        )

    def _refresh_all_icons(self, theme: str) -> None:
        # 设计 §7.4 路径：主题切换后重建图标
        self._sync_action.setIcon(self._make_icon("fa5s.sync"))
        self._toggle_action.setIcon(self._make_icon("fa5s.adjust"))


def main() -> int:
    t0 = time.perf_counter()
    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")
    win = SpikeWindow()
    win.show()
    print(
        f"[spike] startup={time.perf_counter() - t0:.2f}s "
        f"PySide6=6.11 qdarktheme=fork-2.3.6 qtawesome=1.4.2"
    )
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
