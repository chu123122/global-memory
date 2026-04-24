"""同步页：sync preview + change tree + 一键 sync。"""
from __future__ import annotations

import sys
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

try:
    from control_panel_model import summarize_status, summarize_sync_preview
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from control_panel_model import (  # type: ignore[no-redef]
        summarize_status,
        summarize_sync_preview,
    )

from ._base import _BasePage


def _section(parent_layout: QVBoxLayout, title: str, subtitle: str = "") -> QFrame:
    box = QFrame()
    box.setStyleSheet("background: rgba(255,255,255,0.04); border-radius: 6px;")
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


class SyncPage(_BasePage):
    title = "同步"
    subtitle = "先看预览再决定是否 checkpoint，避免误推"
    page_id = "sync"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        self._preview_labels: dict[str, QLabel] = {}
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        inspect = _section(layout, "同步前检查", "先看清楚当前改了什么，再决定是否生成 checkpoint。")
        for label, icon_name, handler in [
            ("刷新 Git 状态", "fa5s.sync", self._on_refresh_status),
            ("生成同步预览", "fa5s.eye", self._on_sync_preview),
            ("查看提交分组", "fa5s.layer-group", self._on_log),
        ]:
            btn = QPushButton(qta.icon(icon_name), label)
            btn.clicked.connect(handler)
            inspect.layout().addWidget(btn)
            self._icon_buttons.append((btn, icon_name))

        preview = _section(layout, "检查点候选", "只读预览，不运行 safe fix / stage / commit / push。")
        for key, label in {
            "summary": "摘要",
            "commit": "候选提交",
            "groups": "文件分组",
        }.items():
            lbl = QLabel(f"{label}：未知")
            lbl.setWordWrap(True)
            preview.layout().addWidget(lbl)
            self._preview_labels[key] = lbl

        changes = _section(layout, "变更文件明细", "按 Git 状态列出文件；只读展示。")
        self._change_tree = QTreeWidget()
        self._change_tree.setColumnCount(2)
        self._change_tree.setHeaderLabels(["状态", "路径"])
        self._change_tree.setRootIsDecorated(False)
        self._change_tree.setAlternatingRowColors(True)
        self._change_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._change_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        changes.layout().addWidget(self._change_tree)

        sync = _section(layout, "检查点同步", "提交并推送当前变更，适合保存维护过程中的稳定节点。")
        sync_btn = QPushButton(qta.icon("fa5s.cloud-upload-alt"), "一键同步 / 检查点推送")
        sync_btn.setStyleSheet("background: #D97706; color: white;")
        sync_btn.clicked.connect(self._on_sync)
        sync.layout().addWidget(sync_btn)
        self._icon_buttons.append((sync_btn, "fa5s.cloud-upload-alt"))

    def _on_refresh_status(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="快速状态",
            cmd=self._main.py_cmd("maintain.py", "status", "--json"),
            parse_json=True,
            extras={"action": "status"},
        )

    def _on_sync_preview(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="同步预览",
            cmd=self._main.py_cmd(
                "maintain.py", "sync", "--preview", "--source", "gui-pyside", "--json"
            ),
            parse_json=True,
            extras={"action": "sync-preview"},
        )

    def _on_log(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="提交日志",
            cmd=self._main.py_cmd("maintain.py", "log", "--json", "--limit", "40"),
            parse_json=True,
            extras={"action": "log"},
        )

    def _on_sync(self) -> None:
        ok = QMessageBox.question(
            self,
            "检查点同步",
            "把当前变更提交并推送为检查点？",
        ) == QMessageBox.StandardButton.Yes
        if ok:
            self._main.submit_cmd(
                page=self.page_id,
                title="一键同步",
                cmd=self._main.py_cmd("maintain.py", "sync", "--source", "gui-pyside", "--json"),
                parse_json=True,
                extras={"action": "sync"},
            )

    @Slot(object)
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        data = result.json
        if action == "status" and isinstance(data, dict):
            model = summarize_status(data)
            self._main.conclusion.set_decision(model["decision"])
            self._main.conclusion.set_cards(model["cards"])
            git = data.get("git", {}) or {}
            self._preview_labels["summary"].setText(
                f"摘要：当前工作区变更 {git.get('change_count', 0)} 个，dirty={git.get('dirty')}"
            )
            self._preview_labels["groups"].setText(
                self._format_groups(git.get("groups", {}) or {})
            )
            self._update_change_tree(git.get("changes", []) or [])
        elif action == "sync-preview" and isinstance(data, dict):
            model = summarize_sync_preview(data)
            self._main.conclusion.set_decision(model["decision"])
            self._main.conclusion.set_cards([
                {
                    "title": "文件数",
                    "value": len(model["changes"]),
                    "level": "warning" if model["changes"] else "ok",
                },
                {"title": "分组", "value": model["groups_text"], "level": "info"},
                {"title": "提交名", "value": model["commit"] or "(无)", "level": "info"},
            ])
            self._preview_labels["summary"].setText(
                f"摘要：{data.get('summary')}；真实同步会先 pull --rebase="
                f"{data.get('would_pull_rebase_on_real_sync')}"
            )
            self._preview_labels["commit"].setText(f"候选提交：{data.get('commit', '(无)')}")
            self._preview_labels["groups"].setText(
                self._format_groups(data.get("groups", {}) or {})
            )
            self._update_change_tree(data.get("changes", []) or [])
        elif action == "sync" and isinstance(data, dict):
            self._main.append_debug(f"\n# 一键同步结果\n{result.stdout}\n")
            self._main.conclusion.set_decision({
                "headline": "checkpoint 同步已完成",
                "next_action": "下一步：刷新 Git 状态确认 dirty=False",
                "why": str(data.get("summary", "")),
            })

    def _format_groups(self, groups: dict) -> str:
        if not groups:
            return "文件分组：无变更"
        return "文件分组：" + " / ".join(f"{g} {len(p)}" for g, p in groups.items())

    def _update_change_tree(self, changes: list[dict]) -> None:
        self._change_tree.clear()
        if not changes:
            self._change_tree.addTopLevelItem(QTreeWidgetItem(["clean", "当前无工作区变更"]))
            return
        for entry in changes:
            if not isinstance(entry, dict):
                continue
            self._change_tree.addTopLevelItem(QTreeWidgetItem([
                str(entry.get("code", "?")),
                str(entry.get("path", entry.get("raw", ""))),
            ]))

    def refresh(self) -> None:
        self._on_refresh_status()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
