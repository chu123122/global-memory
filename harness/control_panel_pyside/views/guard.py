"""守护页：daemon 状态 / 启停 / auto_sync.log 查看。"""
from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout

from ._base import _BasePage
from .components import action_button, section_card

AUTO_SYNC_LOG = Path.home() / ".claude" / "auto_sync.log"


class GuardPage(_BasePage):
    title = "守护"
    subtitle = "auto_sync 守护进程：负责空闲触发，真正的 Git 同步交给 maintain.py"
    page_id = "guard"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        self._status_label: QLabel | None = None
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        section = section_card(layout, "自动同步守护进程", "守护只触发，不直接 push。")

        self._status_label = QLabel("状态：未知")
        self._status_label.setWordWrap(True)
        section.layout().addWidget(self._status_label)

        for label, icon_name, handler, role in [
            ("刷新守护进程状态", "fa5s.sync", self._on_status, "secondary"),
            ("启动守护进程（后台）", "fa5s.play", self._on_start, "primary"),
            ("停止守护进程", "fa5s.stop", self._on_stop, "danger"),
            ("查看 auto_sync.log", "fa5s.file-alt", self._on_view_log, "secondary"),
        ]:
            btn = action_button(section, label, icon_name, handler, role=role)
            self._icon_buttons.append((btn, icon_name))

    def _on_status(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="守护进程状态",
            cmd=self._main.py_cmd("maintain.py", "daemon", "status", "--json"),
            parse_json=True,
            extras={"action": "daemon-status"},
        )

    def _on_start(self) -> None:
        ok = QMessageBox.question(self, "启动守护进程", "在后台启动自动同步守护进程？") \
            == QMessageBox.StandardButton.Yes
        if ok:
            self._main.submit_cmd(
                page=self.page_id,
                title="启动守护进程",
                cmd=self._main.py_cmd("maintain.py", "daemon", "start", "--json"),
                parse_json=True,
                extras={"action": "daemon-start"},
            )

    def _on_stop(self) -> None:
        ok = QMessageBox.question(self, "停止守护进程", "停止正在运行的自动同步守护进程？") \
            == QMessageBox.StandardButton.Yes
        if ok:
            self._main.submit_cmd(
                page=self.page_id,
                title="停止守护进程",
                cmd=self._main.py_cmd("maintain.py", "daemon", "stop", "--json"),
                parse_json=True,
                extras={"action": "daemon-stop"},
            )

    def _on_view_log(self) -> None:
        if not AUTO_SYNC_LOG.exists():
            self._main.append_debug("\n未找到 auto_sync.log\n")
            return
        try:
            text = AUTO_SYNC_LOG.read_text(encoding="utf-8", errors="replace")
            tail = "\n".join(text.splitlines()[-120:])
            self._main.append_debug(f"\n# auto_sync.log（最后 120 行）\n{tail}\n")
        except OSError as exc:
            self._main.append_debug(f"\n[auto_sync.log 读取失败] {exc}\n")

    @Slot(object)
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        data = result.json
        if action == "daemon-status" and isinstance(data, dict):
            running = data.get("running")
            count = len(data.get("processes", []) or [])
            self._status_label.setText(  # type: ignore[union-attr]
                f"状态：running={running} / processes={count}"
            )
            self._main.conclusion.set_decision({
                "headline": f"守护进程 {'运行中' if running else '已停止'}",
                "next_action": "下一步：" + ("可继续工作" if running else "如需自动同步请启动"),
                "why": f"processes={count}",
            })
        elif action in {"daemon-start", "daemon-stop"} and isinstance(data, dict):
            self._status_label.setText(  # type: ignore[union-attr]
                f"状态：{data.get('summary', '已变更')}"
            )

    def refresh(self) -> None:
        self._on_status()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
