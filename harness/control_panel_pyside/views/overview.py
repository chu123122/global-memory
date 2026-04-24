"""总览页：快速状态 + Doctor 明细 + 常用入口。"""
from __future__ import annotations

import sys
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

try:
    from control_panel_model import (
        summarize_doctor,
        summarize_log,
        summarize_status,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from control_panel_model import (  # type: ignore[no-redef]
        summarize_doctor,
        summarize_log,
        summarize_status,
    )

from ._base import _BasePage

CHECK_LABELS = {
    "git_status": "Git 状态",
    "check_health": "记忆健康",
    "bootstrap_check": "部署检查",
    "verify_prompt_system": "Prompt 系统",
    "verify_docs": "文档一致性",
    "smoke_test": "冒烟测试",
}


def _section(parent_layout: QVBoxLayout, title: str, subtitle: str = "") -> QFrame:
    box = QFrame()
    box.setObjectName("section-card")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    title_label = QLabel(title)
    title_label.setFont(QFont("", 11, QFont.Weight.Bold))
    layout.addWidget(title_label)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setStyleSheet("color: gray;")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    parent_layout.addWidget(box)
    return box


def _action_button(parent: QFrame, label: str, icon_name: str, on_click) -> QPushButton:
    btn = QPushButton(qta.icon(icon_name), label)
    btn.clicked.connect(on_click)
    parent.layout().addWidget(btn)
    return btn


class OverviewPage(_BasePage):
    title = "总览"
    subtitle = "Git / Daemon / 提交 / Doctor 状态快照 + 常用入口"
    page_id = "overview"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._quick_labels: dict[str, QLabel] = {}
        self._summary_labels: dict[str, QLabel] = {}
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # 快速状态
        quick = _section(layout, "快速状态", "轻量状态快照：不运行深度体检，不写文件。")
        for key, label in {
            "git": "Git",
            "daemon": "Daemon",
            "commits": "最近提交",
            "doctor": "最近体检",
        }.items():
            lbl = QLabel(f"{label}：未知")
            lbl.setWordWrap(True)
            quick.layout().addWidget(lbl)
            self._quick_labels[key] = lbl

        # Doctor 明细
        doctor = _section(layout, "Doctor 明细", "体检会聚合 Git / 记忆健康 / 部署 / Prompt / 文档 / 冒烟。")
        for key, label in CHECK_LABELS.items():
            lbl = QLabel(f"{label}：未知")
            lbl.setWordWrap(True)
            doctor.layout().addWidget(lbl)
            self._summary_labels[key] = lbl

        # 常用入口
        actions = _section(layout, "常用入口", "平时优先从这里判断当前体系是否健康。")
        for label, icon_name, handler in [
            ("刷新快速状态", "fa5s.sync", self._on_refresh_status),
            ("运行完整体检", "fa5s.heartbeat", self._on_run_doctor),
            ("生成维护报告", "fa5s.file-alt", self._on_run_report),
            ("查看最近提交", "fa5s.history", self._on_run_log),
            ("打开日志目录", "fa5s.folder-open", self._on_open_logs),
        ]:
            btn = _action_button(actions, label, icon_name, handler)
            self._icon_buttons.append((btn, icon_name))

    # --- 动作 ---
    def _on_refresh_status(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="快速状态",
            cmd=self._main.py_cmd("maintain.py", "status", "--json"),
            parse_json=True,
            extras={"action": "status"},
        )

    def _on_run_doctor(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="主控体检",
            cmd=self._main.py_cmd("maintain.py", "doctor", "--json"),
            parse_json=True,
            extras={"action": "doctor"},
        )

    def _on_run_report(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="维护报告",
            cmd=self._main.py_cmd("maintain.py", "report", "--markdown"),
            extras={"action": "report"},
        )

    def _on_run_log(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="提交日志",
            cmd=self._main.py_cmd("maintain.py", "log", "--json", "--limit", "40"),
            parse_json=True,
            extras={"action": "log"},
        )

    def _on_open_logs(self) -> None:
        self._main.open_path(Path.home() / ".claude" / "logs")

    # --- 结果回调 ---
    @Slot(object)
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        data = result.json
        if action == "status" and isinstance(data, dict):
            model = summarize_status(data)
            self._main.conclusion.set_decision(model["decision"])
            self._main.conclusion.set_cards(model["cards"])
            self._update_quick_from_status(data)
        elif action == "doctor" and isinstance(data, dict):
            model = summarize_doctor(data)
            self._main.conclusion.set_decision(model["decision"])
            cards = [
                {"title": item["id"], "value": item["summary"], "level": str(item["level"]).lower()}
                for item in model["checks"]
            ]
            self._main.conclusion.set_cards(cards)
            summary = data.get("summary", {})
            self._quick_labels["doctor"].setText(
                f"最近体检：PASS {summary.get('PASS', 0)} / WARNING {summary.get('WARNING', 0)} / "
                f"ERROR {summary.get('ERROR', 0)}"
            )
            for item in data.get("results", []):
                if isinstance(item, dict):
                    key = item.get("id")
                    if key in self._summary_labels:
                        label = CHECK_LABELS[key]
                        self._summary_labels[key].setText(
                            f"{label}：{item.get('level')} - {item.get('summary')}"
                        )
        elif action == "log" and isinstance(data, dict):
            model = summarize_log(data)
            self._quick_labels["commits"].setText(
                f"最近提交：语义 {model['semantic']} / 检查点 {model['checkpoint']} / 总计 {model['total']}"
            )
            self._main.conclusion.set_decision({
                "headline": f"最近 {model['total']} 个提交里有 {model['checkpoint']} 个检查点",
                "next_action": "下一步：如果检查点太多，考虑合并或补语义提交",
                "why": f"语义提交 {model['semantic']} 个，checkpoint {model['checkpoint']} 个。",
            })
        elif action == "report":
            self._main.append_debug(f"\n# 维护报告\n{result.stdout}\n")

    def _update_quick_from_status(self, data: dict) -> None:
        git = data.get("git", {}) or {}
        daemon = data.get("daemon", {}) or {}
        recent = (data.get("recent_commits", {}) or {}).get("summary", {}) or {}
        logs = (data.get("logs", {}) or {}).get("maintain_tail", []) or []
        self._quick_labels["git"].setText(
            f"Git：dirty={git.get('dirty')} / ahead={git.get('ahead')} / "
            f"behind={git.get('behind')} / 变更 {git.get('change_count')}"
        )
        self._quick_labels["daemon"].setText(
            f"Daemon：running={daemon.get('running')} / processes={daemon.get('process_count')}"
        )
        self._quick_labels["commits"].setText(
            f"最近提交：语义 {recent.get('semantic', 0)} / 检查点 {recent.get('checkpoint', 0)} / "
            f"总计 {recent.get('total', 0)}"
        )
        for item in reversed(logs):
            if isinstance(item, dict) and item.get("type") == "doctor":
                summary = item.get("summary") or {}
                self._quick_labels["doctor"].setText(
                    f"最近体检：PASS {summary.get('PASS', 0)} / "
                    f"WARNING {summary.get('WARNING', 0)} / ERROR {summary.get('ERROR', 0)}"
                )
                break

    def refresh(self) -> None:
        self._on_refresh_status()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
