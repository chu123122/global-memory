"""入口：QApplication + 主题初始化 + 主窗口装配。

跑法（cwd=$env:GLOBAL_MEMORY_DIR/harness/）：
    python -m control_panel_pyside
"""
from __future__ import annotations

import sys
import time

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import ThemeManager


def main() -> int:
    t0 = time.perf_counter()
    app = QApplication(sys.argv)
    app.setApplicationName("global-memory Harness 主控台 (PySide6)")
    app.setOrganizationName("global-memory")

    theme_mgr = ThemeManager(app)
    theme_mgr.apply_initial()

    win = MainWindow(theme_mgr)
    win.show()
    print(f"[control_panel_pyside] startup={time.perf_counter() - t0:.2f}s theme={theme_mgr.current}")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
