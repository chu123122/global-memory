"""任务总览页（v2 新增）：active + archived 任务卡片网格。

数据源：harness_status.py --tasks --json（harness-governance-v1 Phase 2-A.1 已交付）。
设计 §7.7：v2 不重复实现扫描/简介抽取/stage 解析；TaskCard 是 QFrame 子类。
"""
from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ._base import _BasePage

STAGE_COLORS = {
    "discussion": "#3B82F6",       # 蓝
    "implementation": "#10B981",   # 绿
    "archived": "#6B7280",         # 灰
    "unknown": "#6B7280",
    "missing": "#EF4444",
}


class TaskCard(QFrame):
    """单个任务卡片：标题 + stage 徽章 + 简介。

    左键 → task_selected（在右侧结论面板显示长简介）
    右键 → task_open_requested（在文件管理器打开任务目录）
    """

    task_selected = Signal(dict)
    task_open_requested = Signal(dict)

    def __init__(self, task: dict) -> None:
        super().__init__()
        self._task = task
        self.setObjectName("task-card")
        # 卡片底色由 theme.py 的 _base_card_qss / _hanaarashi_qss 提供（跨主题）
        self.setMinimumSize(QSize(280, 110))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        header = QHBoxLayout()
        name_label = QLabel(task.get("name", "(未命名)"))
        name_label.setFont(QFont("", 11, QFont.Weight.Bold))
        header.addWidget(name_label, stretch=1)

        stage = str(task.get("stage", "unknown"))
        color = STAGE_COLORS.get(stage, "#6B7280")
        badge = QLabel(stage)
        badge.setStyleSheet(
            f"background: {color}; color: white; padding: 2px 8px;"
            "border-radius: 10px; font-size: 10px;"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(badge)
        outer.addLayout(header)

        brief_text = task.get("brief", "")
        if len(brief_text) > 200:
            brief_text = brief_text[:200] + "…"
        brief = QLabel(brief_text)
        brief.setWordWrap(True)
        # palette(mid) 是 Qt 标准 palette role，跨主题都解析为合适的"次要文字"色：
        #   light/auto: 中灰；dark: 偏白灰；hanaarashi: 暖灰土 #9a8c7a
        brief.setStyleSheet("color: palette(mid); font-size: 11px;")
        outer.addWidget(brief, stretch=1)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.task_selected.emit(self._task)
        elif event.button() == Qt.MouseButton.RightButton:
            self.task_open_requested.emit(self._task)
        super().mousePressEvent(event)


def _section_label(text: str, count: int) -> QHBoxLayout:
    layout = QHBoxLayout()
    title = QLabel(text)
    title.setFont(QFont("", 12, QFont.Weight.Bold))
    layout.addWidget(title)
    counter = QLabel(f"({count})")
    counter.setStyleSheet("color: gray;")
    layout.addWidget(counter)
    layout.addStretch(1)
    return layout


class TasksPage(_BasePage):
    title = "任务总览"
    subtitle = "active + archived，点卡片打开目录 + 在右侧显示长简介"
    page_id = "tasks"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        self._active_grid: QGridLayout | None = None
        self._archived_grid: QGridLayout | None = None
        self._counter_label: QLabel | None = None
        self._loaded_once = False
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # 顶部工具条
        toolbar = QHBoxLayout()
        title = QLabel("任务总览")
        title.setFont(QFont("", 13, QFont.Weight.Bold))
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        self._counter_label = QLabel("active: ? | archived: ?")
        self._counter_label.setStyleSheet("color: gray;")
        toolbar.addWidget(self._counter_label)
        refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(refresh_btn)
        self._icon_buttons.append((refresh_btn, "fa5s.sync"))
        layout.addLayout(toolbar)

        # Active 区
        self._active_header = _section_label("Active", 0)
        layout.addLayout(self._active_header)
        self._active_container = QWidget()
        self._active_grid = QGridLayout(self._active_container)
        self._active_grid.setSpacing(10)
        layout.addWidget(self._active_container)

        # Archived 区
        self._archived_header = _section_label("Archived", 0)
        layout.addLayout(self._archived_header)
        self._archived_container = QWidget()
        self._archived_grid = QGridLayout(self._archived_container)
        self._archived_grid.setSpacing(10)
        layout.addWidget(self._archived_container)

    def _on_refresh(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="任务列表",
            cmd=self._main.py_cmd("harness_status.py", "--tasks", "--json"),
            parse_json=True,
            extras={"action": "tasks"},
        )

    @Slot(object)
    def handle_result(self, result) -> None:
        if result.extras.get("action") != "tasks":
            return
        if not isinstance(result.json, dict):
            self._main.append_debug(
                f"\n[任务列表] 退出 {result.returncode}\n{result.stderr or result.stdout}\n"
            )
            return
        active = result.json.get("active", []) or []
        archived = result.json.get("archived", []) or []
        if self._counter_label:
            self._counter_label.setText(f"active: {len(active)} | archived: {len(archived)}")
        # 更新 section 计数（重建 header 太麻烦，直接换 label 文本不好做；保持 counter 显示总数足够）
        self._populate_grid(self._active_grid, active)
        self._populate_grid(self._archived_grid, archived)

    def _populate_grid(self, grid: QGridLayout | None, tasks: list[dict]) -> None:
        if grid is None:
            return
        # 清空
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.deleteLater()
        # 重新填充：3 列
        cols = 3
        for idx, task in enumerate(tasks):
            card = TaskCard(task)
            card.task_selected.connect(self._on_task_selected)
            card.task_open_requested.connect(self._on_task_open_requested)
            grid.addWidget(card, idx // cols, idx % cols)

    @Slot(dict)
    def _on_task_selected(self, task: dict) -> None:
        """左键：仅在右侧结论面板渲染长简介，不弹文件管理器。"""
        self._main.conclusion.show_task(
            name=str(task.get("name", "")),
            stage=str(task.get("stage", "")),
            path=str(task.get("path", "")),
            brief=str(task.get("brief", "")),
        )

    @Slot(dict)
    def _on_task_open_requested(self, task: dict) -> None:
        """右键：在文件管理器打开任务目录。"""
        path_str = task.get("path")
        if path_str:
            self._main.open_path(Path(path_str))

    def refresh(self) -> None:
        if not self._loaded_once:
            self._loaded_once = True
            self._on_refresh()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
