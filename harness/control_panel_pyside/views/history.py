"""历史页：最近提交 / 维护报告 / 日志路径。"""
from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QPushButton, QVBoxLayout

from ._base import _BasePage
from .components import action_button, section_card

LOG_DIR = Path.home() / ".claude" / "logs"


class HistoryPage(_BasePage):
    title = "历史"
    subtitle = "查看最近提交，以及主控和 AI adapter 写入的 JSONL 日志"
    page_id = "history"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        section = section_card(layout, "运行历史", "")
        for label, icon_name, handler in [
            ("最近提交", "fa5s.history", self._on_recent_commits),
            ("生成维护报告", "fa5s.file-alt", self._on_report),
            ("打开 maintain 运行日志", "fa5s.folder-open", lambda: self._main.open_path(LOG_DIR / "maintain.jsonl")),
            ("打开 AI 运行日志", "fa5s.folder-open", lambda: self._main.open_path(LOG_DIR / "ai_runner.jsonl")),
            ("打开日志目录", "fa5s.folder-open", lambda: self._main.open_path(LOG_DIR)),
        ]:
            role = "primary" if label == "生成维护报告" else "secondary"
            btn = action_button(section, label, icon_name, handler, role=role)
            self._icon_buttons.append((btn, icon_name))

    def _on_recent_commits(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="提交日志",
            cmd=self._main.py_cmd("maintain.py", "log", "--json", "--limit", "40"),
            parse_json=True,
            extras={"action": "log"},
        )

    def _on_report(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="维护报告",
            cmd=self._main.py_cmd("maintain.py", "report", "--markdown"),
            extras={"action": "report"},
        )

    @Slot(object)
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        if action == "log":
            data = result.json
            if isinstance(data, dict):
                summary = data.get("summary", {})
                self._main.conclusion.set_decision({
                    "headline": f"最近 {summary.get('total', 0)} 个提交",
                    "next_action": "下一步：可生成维护报告或继续工作",
                    "why": (
                        f"语义 {summary.get('semantic', 0)} / "
                        f"检查点 {summary.get('checkpoint', 0)}"
                    ),
                })
                self._main.append_debug(f"\n# 最近提交\n{result.stdout}\n")
        elif action == "report":
            self._main.append_debug(f"\n# 维护报告\n{result.stdout}\n")

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
