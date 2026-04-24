"""主窗口：QMainWindow + QSplitter + QTabWidget + 菜单栏 + 调试输出 dock。

Signal 全链路（设计 §7.2）：
  ThemeManager.theme_changed(str)
    → MainWindow._on_theme_changed
      → tab icon refresh (qtawesome 重建)
      → 各 page.on_theme_changed(theme)

  PollingService.event_received(dict)
    → EventsPage.on_polling_event

  CommandRunner.result_ready(CommandResult)
    → MainWindow._dispatch_result
      → page.handle_result()
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
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTabWidget,
)

from .cli_invoke import CommandResult, CommandRunner
from .conclusion_panel import ConclusionPanel
from .polling import PollingService
from .theme import ThemeManager, ThemeName
from .views._base import _BasePage
from .views.ai import AIPage
from .views.doctor import DoctorPage
from .views.events import EventsPage
from .views.guard import GuardPage
from .views.history import HistoryPage
from .views.overview import OverviewPage
from .views.sync import SyncPage
from .views.tasks import TasksPage

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = HARNESS_DIR.parent

# tab idx → (Page 类, qtawesome 图标)
TAB_SPEC = [
    ("总览", OverviewPage, "fa5s.tachometer-alt"),
    ("修复", DoctorPage, "fa5s.tools"),
    ("同步", SyncPage, "fa5s.cloud-upload-alt"),
    ("守护", GuardPage, "fa5s.heartbeat"),
    ("AI", AIPage, "fa5s.robot"),
    ("事件", EventsPage, "fa5s.bell"),
    ("历史", HistoryPage, "fa5s.history"),
    ("任务", TasksPage, "fa5s.tasks"),
]


class MainWindow(QMainWindow):
    def __init__(self, theme_mgr: ThemeManager) -> None:
        super().__init__()
        self.setWindowTitle("global-memory Harness 主控台 (PySide6)")
        self.resize(1280, 820)
        self.setMinimumSize(1000, 650)

        self._theme_mgr = theme_mgr
        self._theme_mgr.theme_changed.connect(self._on_theme_changed)

        # 命令运行器（QThreadPool 异步）
        self._runner = CommandRunner(default_cwd=REPO_DIR)
        self._runner.result_ready.connect(self._dispatch_result)
        self._request_seq = 0
        self._latest_request_by_page: dict[str, int] = {}

        # JSONL 轮询服务
        self._polling = PollingService(self)

        # 中央：QSplitter(左 QTabWidget + 右 ConclusionPanel)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        self._tabs = QTabWidget()
        splitter.addWidget(self._tabs)

        self.conclusion = ConclusionPanel()
        splitter.addWidget(self.conclusion)
        splitter.setSizes([720, 560])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # 装载 8 张页签
        self._pages: dict[str, _BasePage] = {}
        for label, PageCls, _icon_name in TAB_SPEC:
            page = PageCls(self)
            self._pages[page.page_id] = page  # type: ignore[attr-defined]
            self._tabs.addTab(page, label)

        # 初次设置 tab 图标
        self._refresh_tab_icons()

        # tab 切换：触发该页 refresh + 联动结论面板
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # 事件页订阅 polling
        events_page = self._pages["events"]
        if isinstance(events_page, EventsPage):
            self._polling.event_received.connect(events_page.on_polling_event)

        # 调试输出 dock（默认隐藏）
        self._debug_dock = QDockWidget("调试输出（原始命令输出）", self)
        self._debug_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self._debug_text = QPlainTextEdit()
        self._debug_text.setObjectName("debug-output")
        self._debug_text.setReadOnly(True)
        # 配色由 theme.py 统一供（_base_card_qss / _hanaarashi_qss）
        self._debug_dock.setWidget(self._debug_text)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._debug_dock)
        self._debug_dock.hide()

        # 状态栏 + 右下角耳语（hanaarashi 主题下显形，其他主题不可见）
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"就绪 · theme={self._theme_mgr.current}")
        from PySide6.QtWidgets import QLabel  # 局部 import 避免顶上文件太挤
        self._whisper = QLabel("春の花びらが風に散る")
        self._whisper.setObjectName("whisper")
        # 默认全主题都显，但通过 opacity 控制；hanaarashi QSS 已为 #whisper 提供配色
        self._whisper.setStyleSheet("color: rgba(150,140,120,0.18); padding-right: 12px;")
        self.statusBar().addPermanentWidget(self._whisper)

        # 菜单栏（View → Theme / Debug）
        self._build_menus()

        # 启动轮询
        self._polling.start()

        # 初次加载：第一页主动 refresh
        first_page = self._tabs.widget(0)
        if isinstance(first_page, _BasePage):
            first_page.maybe_refresh(force=True)

    # ---------------- 菜单 ----------------
    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("视图(&V)")

        # Theme 子菜单
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

        view_menu.addSeparator()
        debug_act = QAction("显示调试输出(&D)", self, checkable=True)
        debug_act.toggled.connect(self._toggle_debug)
        view_menu.addAction(debug_act)

        help_menu = menu_bar.addMenu("帮助(&H)")
        about_act = QAction("关于(&A)", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于",
            "global-memory Harness 主控台 (PySide6 v2)\n\n"
            "把 v1 Tkinter 重写为 PySide6，model 层零改动。\n"
            "设计文档：projects/control-panel-v2-pyside/设计文档.md",
        )

    def _toggle_debug(self, checked: bool) -> None:
        self._debug_dock.setVisible(checked)

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
        if page_id and page_id != self._current_page_id():
            self._append_ignored_result(result, reason=f"后台页结果已暂存 ({page_id})")
            return
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
        # hanaarashi 主题下耳语显形（warm ink），其他主题保持 18% 透明度
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
            self.conclusion.switch_to_page(page.page_id)

    # ---------------- 调试输出 ----------------
    def append_debug(self, text: str, reveal: bool = True) -> None:
        self._debug_text.appendPlainText(text.rstrip("\n"))
        if reveal:
            self._debug_dock.show()

    def _current_page_id(self) -> str | None:
        page = self._tabs.currentWidget()
        return getattr(page, "page_id", None)

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
        self._polling.stop()
        super().closeEvent(event)
