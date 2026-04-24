"""AI 页：provider/mode/permission 表单 + prompt + run。"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ._base import _BasePage
from .components import action_button, section_card

PROVIDER_OPTIONS = {
    "Claude CLI": "claude",
    "Codex CLI（预留）": "codex",
    "API 提供方（预留）": "api",
}
MODE_OPTIONS = {
    "只读诊断": "diagnose",
    "计划生成": "plan",
}
PERMISSION_OPTIONS = {
    "计划模式": "plan",
    "默认模式": "default",
}


class AIPage(_BasePage):
    title = "AI"
    subtitle = "AI Runner：只读诊断或计划生成，不自动改仓库"
    page_id = "ai"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        form_card = section_card(layout, "AI Runner", "V1 只开放非交互式诊断 / 计划生成。")
        form_layout = QFormLayout()
        self._provider = QComboBox()
        self._provider.addItems(list(PROVIDER_OPTIONS.keys()))
        self._mode = QComboBox()
        self._mode.addItems(list(MODE_OPTIONS.keys()))
        self._permission = QComboBox()
        self._permission.addItems(list(PERMISSION_OPTIONS.keys()))
        form_layout.addRow("提供方", self._provider)
        form_layout.addRow("任务类型", self._mode)
        form_layout.addRow("权限模式", self._permission)
        form_card.layout().addLayout(form_layout)

        self._ctx_doctor = QCheckBox("附带体检报告")
        self._ctx_doctor.setChecked(True)
        self._ctx_diff = QCheckBox("附带 Git diff 摘要")
        self._ctx_diff.setChecked(True)
        self._ctx_docs = QCheckBox("附带 README / MAINTENANCE")
        form_card.layout().addWidget(self._ctx_doctor)
        form_card.layout().addWidget(self._ctx_diff)
        form_card.layout().addWidget(self._ctx_docs)

        prompt_card = section_card(layout, "提示词", "作为 AI 任务输入，必要时自动拼接体检 / diff / 文档上下文。")
        self._prompt = QTextEdit()
        self._prompt.setPlainText("分析当前 harness 健康状态，并给出下一步最安全的维护建议。")
        self._prompt.setMinimumHeight(140)
        prompt_card.layout().addWidget(self._prompt)

        run_btn = action_button(prompt_card, "运行 AI 诊断 / 计划", "fa5s.robot", self._on_run, role="primary")
        self._icon_buttons.append((run_btn, "fa5s.robot"))

    def _on_run(self) -> None:
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "需要提示词", "请先输入提示词。")
            return
        cmd = self._main.py_cmd(
            "ai_runner.py",
            prompt,
            "--provider", PROVIDER_OPTIONS[self._provider.currentText()],
            "--mode", MODE_OPTIONS[self._mode.currentText()],
            "--permission-mode", PERMISSION_OPTIONS[self._permission.currentText()],
            "--json",
        )
        if self._ctx_doctor.isChecked():
            cmd.append("--context-doctor")
        if self._ctx_diff.isChecked():
            cmd.append("--context-diff")
        if self._ctx_docs.isChecked():
            cmd.append("--context-docs")
        self._main.submit_cmd(
            page=self.page_id,
            title="AI 执行",
            cmd=cmd,
            parse_json=True,
            extras={"action": "ai"},
        )

    @Slot(object)
    def handle_result(self, result) -> None:
        if result.extras.get("action") != "ai":
            return
        self._main.append_debug(f"\n# AI 执行 (exit={result.returncode})\n{result.stdout}\n")
        if result.stderr:
            self._main.append_debug(f"[stderr]\n{result.stderr}\n")
        data = result.json
        headline = "AI 执行完成"
        why = ""
        if isinstance(data, dict):
            headline = str(data.get("summary") or headline)
            why = str(data.get("plan_path") or data.get("output_path") or "")
        self._main.conclusion.set_decision({
            "headline": headline,
            "next_action": "下一步：检查右侧调试输出或 plan 文件",
            "why": why,
        })

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
