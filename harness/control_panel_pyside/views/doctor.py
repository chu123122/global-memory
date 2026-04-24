"""修复页：safe fix + bootstrap check/install。"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout

from ._base import _BasePage
from .components import action_button, section_card


class DoctorPage(_BasePage):
    title = "修复"
    subtitle = "本地安全修复 + Bootstrap 部署管理"
    page_id = "doctor"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        safe = section_card(layout, "安全修复", "只修改本地文件，不会提交或推送。适合处理索引、统计和路径漂移。")
        btn = action_button(safe, "安全修复：索引 / 统计 / 路径", "fa5s.tools", self._on_run_fix)
        self._icon_buttons.append((btn, "fa5s.tools"))

        deploy = section_card(layout, "部署链路", "Bootstrap 负责 junction、settings 和关键入口文件。重新部署属于高风险动作。")
        check_btn = action_button(deploy, "检查 Bootstrap 部署", "fa5s.search", self._on_bootstrap_check)
        self._icon_buttons.append((check_btn, "fa5s.search"))

        install_btn = action_button(deploy, "重新部署 Bootstrap（高风险）", "fa5s.exclamation-triangle", self._on_bootstrap_install, role="danger")
        self._icon_buttons.append((install_btn, "fa5s.exclamation-triangle"))

    def _on_run_fix(self) -> None:
        ok = QMessageBox.question(
            self,
            "确认修复",
            "运行本地安全修复？这可能修改已跟踪文件，但不会提交或推送。",
        ) == QMessageBox.StandardButton.Yes
        if ok:
            self._main.submit_cmd(
                page=self.page_id,
                title="安全修复",
                cmd=self._main.py_cmd("maintain.py", "fix", "--json"),
                parse_json=True,
                extras={"action": "fix"},
            )

    def _on_bootstrap_check(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="Bootstrap 检查",
            cmd=self._main.py_cmd_repo("bootstrap.py", "check"),
            extras={"action": "bootstrap-check"},
        )

    def _on_bootstrap_install(self) -> None:
        ok = QMessageBox.warning(
            self,
            "高风险操作",
            "bootstrap install 会重写 ~/.claude 设置和 junction 链接。确定继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes
        if ok:
            self._main.submit_cmd(
                page=self.page_id,
                title="Bootstrap 重新部署",
                cmd=self._main.py_cmd_repo("bootstrap.py", "install"),
                extras={"action": "bootstrap-install"},
            )

    @Slot(object)
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        if action in {"bootstrap-check", "bootstrap-install"}:
            self._main.append_debug(f"\n# {result.title}\nexit={result.returncode}\n{result.stdout}\n")
            if result.stderr:
                self._main.append_debug(f"[stderr]\n{result.stderr}\n")
        elif action == "fix" and isinstance(result.json, dict):
            self._main.append_debug(f"\n# 安全修复\n{result.stdout}\n")
            self._main.conclusion.set_decision({
                "headline": "安全修复已运行",
                "next_action": "下一步：去同步页生成预览检查变更",
                "why": "fix 仅触碰本地文件，不会自动 commit/push。",
            })

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
