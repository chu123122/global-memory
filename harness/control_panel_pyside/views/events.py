"""事件页：实时显示 control_panel_events.jsonl 新事件。

订阅 PollingService.event_received(dict)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

try:
    from control_panel_model import event_key, summarize_event
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from control_panel_model import event_key, summarize_event  # type: ignore[no-redef]

from ._base import _BasePage
from .components import action_button, section_card

PANEL_EVENTS_LOG = Path.home() / ".claude" / "logs" / "control_panel_events.jsonl"
MAX_TREE_ROWS = 200

LEVEL_COLORS = {
    "success": "#087443",
    "info": "#0F3D5E",
    "warning": "#D97706",
    "error": "#B42318",
}


class EventsPage(_BasePage):
    title = "事件"
    subtitle = "外部 AI / 脚本调用 panel_api.py 后会在这里实时显示"
    page_id = "events"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._icon_buttons = []
        self._latest_labels: dict[str, QLabel] = {}
        self._seen_keys: set[str] = set()
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        section = section_card(layout, "AI / 脚本事件", "panel_api.py notify 写进来的事件。")
        for key in ("latest", "source", "level", "message"):
            lbl = QLabel("暂无事件")
            lbl.setWordWrap(True)
            section.layout().addWidget(lbl)
            self._latest_labels[key] = lbl

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["时间", "级别", "来源", "标题"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        section.layout().addWidget(self._tree)

        example = section_card(layout, "调用方式", "AI / 脚本 / 终端可用此本地 API 给面板发通知。")
        cmd_label = QLabel(
            'python harness\\panel_api.py notify --source ai --level info '
            '--title "分析完成" --message "建议先运行同步预览"'
        )
        cmd_label.setStyleSheet(
            "background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px; "
            "font-family: 'JetBrains Mono', 'Cascadia Mono', monospace;"
        )
        cmd_label.setWordWrap(True)
        example.layout().addWidget(cmd_label)

        for label, icon_name, handler in [
            ("打开事件日志", "fa5s.folder-open", self._on_open_log),
            ("清空显示列表", "fa5s.trash", self._on_clear),
        ]:
            role = "danger" if label == "清空显示列表" else "secondary"
            btn = action_button(example, label, icon_name, handler, role=role)
            self._icon_buttons.append((btn, icon_name))

    @Slot(dict)
    def on_polling_event(self, event: dict) -> None:
        key = event_key(event)
        if key in self._seen_keys:
            return
        self._seen_keys.add(key)

        summary = summarize_event(event)
        timestamp = event.get("timestamp", "")
        level = summary["level"]

        self._latest_labels["latest"].setText(f"最新事件：{timestamp} - {summary['title']}")
        self._latest_labels["source"].setText(f"来源：{summary['source']}")
        self._latest_labels["level"].setText(f"级别：{level}")
        self._latest_labels["message"].setText(f"内容：{summary['message']}")

        item = QTreeWidgetItem([
            summary["time"],
            level,
            summary["source"],
            summary["title"],
        ])
        color = LEVEL_COLORS.get(level)
        if color:
            from PySide6.QtGui import QColor
            for col in range(4):
                item.setForeground(col, QColor(color))
        self._tree.insertTopLevelItem(0, item)

        # 限制行数
        while self._tree.topLevelItemCount() > MAX_TREE_ROWS:
            self._tree.takeTopLevelItem(self._tree.topLevelItemCount() - 1)

    def _on_open_log(self) -> None:
        self._main.open_path(PANEL_EVENTS_LOG)

    def _on_clear(self) -> None:
        self._tree.clear()
        for lbl in self._latest_labels.values():
            lbl.setText("暂无事件")
        self._seen_keys.clear()

    def handle_result(self, result) -> None:  # noqa: ARG002 — 该页不发命令
        pass

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
