"""主窗口（v2.1 收窄）：QMainWindow + QSplitter（主区 + DocSidebar）+ DebugDock。

3 tab：状态 / 变更 / 任务。
- 状态页（合并 v2.0 总览/守护/修复）含[一键修复]按钮
- 变更页读 CHANGELOG.md
- 任务页保留 v2.0 设计，点卡片直接打开任务目录（不再触发右侧面板）

右侧 DocSidebar 常驻；底部 DebugDock 默认折叠。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .cli_invoke import CommandResult, CommandRunner
from .theme import ThemeManager
from .views._base import _BasePage
from .views.changelog import ChangelogPage
from .views.status import StatusPage
from .views.tasks import TasksPage
from .widgets.debug_dock import DebugDock
from .widgets.doc_sidebar import DocSidebar

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = HARNESS_DIR.parent

# tab idx → (Page 类, qtawesome 图标)
TAB_SPEC = [
    ("状态", StatusPage, "fa5s.tachometer-alt"),
    ("变更", ChangelogPage, "fa5s.history"),
    ("任务", TasksPage, "fa5s.tasks"),
]


class MainWindow(QMainWindow):
    def __init__(self, theme_mgr: ThemeManager) -> None:
        super().__init__()
        self.setWindowTitle("global-memory Harness 主控台 (PySide6 v2.1)")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        self._theme_mgr = theme_mgr
        self._theme_mgr.theme_changed.connect(self._on_theme_changed)

        # 命令运行器（QThreadPool 异步）
        self._runner = CommandRunner(default_cwd=REPO_DIR)
        self._runner.result_ready.connect(self._dispatch_result)
        self._request_seq = 0
        self._latest_request_by_page: dict[str, int] = {}

        # ----- 中央装配 -----
        central = QWidget()
        self.setCentralWidget(central)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        central_layout.addWidget(splitter, stretch=1)

        # 左：3 tab 主区
        self._tabs = QTabWidget()
        splitter.addWidget(self._tabs)

        # 右：常驻文档侧栏
        self._doc_sidebar = DocSidebar(self)
        splitter.addWidget(self._doc_sidebar)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([960, 220])

        # 底部：折叠调试区
        self._debug = DebugDock()
        central_layout.addWidget(self._debug)

        # ----- 装载 3 张页签 -----
        self._pages: dict[str, _BasePage] = {}
        for label, PageCls, _icon_name in TAB_SPEC:
            page = PageCls(self)
            self._pages[page.page_id] = page  # type: ignore[attr-defined]
            self._tabs.addTab(page, label)

        self._refresh_tab_icons()
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # 状态栏 + 右下角耳语（hanaarashi 主题下显形）
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"就绪 · theme={self._theme_mgr.current}")
        self._whisper = QLabel("春の花びらが風に散る")
        self._whisper.setObjectName("whisper")
        self._whisper.setStyleSheet("color: rgba(150,140,120,0.18); padding-right: 12px;")
        self.statusBar().addPermanentWidget(self._whisper)

        # 菜单栏
        self._build_menus()

        # 初次加载：第一页主动 refresh
        first_page = self._tabs.widget(0)
        if isinstance(first_page, _BasePage):
            first_page.maybe_refresh(force=True)

    # ---------------- 菜单 ----------------
    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("视图(&V)")

        theme_menu = view_menu.addMenu("主题(&T)")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        theme_labels = {
            "auto": "Auto（跟随系统）",
            "dark": "Dark",
            "light": "Light",
            "hanaarashi": "花と嵐（日式文学）",
        }
        for theme, label in theme_labels.items():
            act = QAction(label, self, checkable=True)
            act.setData(theme)
            act.setChecked(theme == self._theme_mgr.current)
            act.triggered.connect(lambda _checked=False, t=theme: self._theme_mgr.set_theme(t))
            theme_group.addAction(act)
            theme_menu.addAction(act)

        help_menu = menu_bar.addMenu("帮助(&H)")
        about_act = QAction("关于(&A)", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于",
            "global-memory Harness 主控台 (PySide6 v2.1)\n\n"
            "v2.1 范围收窄：8 tab → 3 tab（状态/变更/任务）+ 文档侧栏 + 折叠调试区。\n"
            "设计文档：projects/control-panel-v2-pyside/设计文档.md",
        )

    # ---------------- 命令转发 ----------------
    def py_cmd(self, harness_script: str, *args: str) -> list[str]:
        return [sys.executable, str(HARNESS_DIR / harness_script), *args]

    def py_cmd_repo(self, repo_script: str, *args: str) -> list[str]:
        return [sys.executable, str(REPO_DIR / repo_script), *args]

    def submit_cmd(
        self,
        page: str,
        title: str,
        cmd: list[str],
        parse_json: bool = False,
        extras: dict | None = None,
    ) -> None:
        merged_extras = dict(extras or {})
        merged_extras["page"] = page
        self._request_seq += 1
        merged_extras["request_id"] = self._request_seq
        self._latest_request_by_page[page] = self._request_seq
        self.statusBar().showMessage(f"正在运行：{title}...")
        self.append_debug(f"\n$ {' '.join(cmd)}\n", reveal=False)
        self._runner.run(title, cmd, parse_json=parse_json, extras=merged_extras)

    @Slot(object)
    def _dispatch_result(self, result: CommandResult) -> None:
        self.statusBar().showMessage(f"完成：{result.title} (exit={result.returncode})")
        page_id = result.extras.get("page")
        request_id = result.extras.get("request_id")
        if page_id and request_id != self._latest_request_by_page.get(page_id):
            self._append_ignored_result(result, reason="已忽略过期结果")
            return
        # 注意：v2.1 不再因"页未在前台"就丢弃结果——页较少，全转给目标页处理
        if page_id and page_id in self._pages:
            self._pages[page_id].handle_result(result)  # type: ignore[attr-defined]
        if result.returncode != 0:
            self.append_debug(
                f"\n# {result.title} 退出码 {result.returncode}\n"
                f"[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n",
                reveal=True,
            )

    # ---------------- 主题切换 ----------------
    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._refresh_tab_icons()
        for page in self._pages.values():
            page.on_theme_changed(theme)
        self._doc_sidebar.on_theme_changed(theme)
        self._debug.on_theme_changed(theme)
        if theme == "hanaarashi":
            self._whisper.setStyleSheet("color: rgba(44,36,24,0.42); padding-right: 12px;")
        else:
            self._whisper.setStyleSheet("color: rgba(150,140,120,0.18); padding-right: 12px;")
        self.statusBar().showMessage(f"主题已切换：{theme}")

    def _refresh_tab_icons(self) -> None:
        for idx, (_label, _PageCls, icon_name) in enumerate(TAB_SPEC):
            self._tabs.setTabIcon(idx, qta.icon(icon_name))

    # ---------------- tab 切换 ----------------
    @Slot(int)
    def _on_tab_changed(self, idx: int) -> None:
        page = self._tabs.widget(idx)
        if isinstance(page, _BasePage):
            page.maybe_refresh()

    # ---------------- 调试输出 ----------------
    def append_debug(self, text: str, reveal: bool = True) -> None:
        self._debug.append(text, reveal=reveal)

    def _append_ignored_result(self, result: CommandResult, reason: str) -> None:
        reveal = result.returncode != 0 or bool(result.stderr)
        text = f"\n# {reason}：{result.title} (exit={result.returncode})\n"
        if reveal:
            text += f"[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n"
        self.append_debug(text, reveal=reveal)

    # ---------------- 文件 / 目录打开 ----------------
    def open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "未找到", str(path))
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", f"{type(exc).__name__}: {exc}")

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().closeEvent(event)
