"""状态页（v1.3 Day 2 重排）：

UX-DESIGN-2026-04-28 方案 B 落地：
  - 删旧 4 张 section_card 纵向堆叠
  - 顶部 verdict_hero_card：22pt 衬线 headline + reason + hairline + next_action
    + 右上角 toolbar（[一键修复] + [刷新]）
  - 下方 4 子系统横排 cell（Git / Daemon / Doctor / Health），每张 left-border 跟 severity
  - Doctor 详情（6 项 check）用 QToolButton arrow 折叠，默认收起；warning/error 时自动展开

数据流：
  status --json → _latest_status → _refresh_verdict() → build_overview_verdict
                                                       → 切 hero severity + 改文案
                                                       → 切 4 cell severity + 改 summary
"""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._base import _BasePage
from .components import (
    SubsystemCell,
    VerdictHeroCard,
    subsystem_cell,
    subsystem_row,
    verdict_hero_card,
)

# overview_verdict 在 harness/ 根目录，不在包里——按现有约定 sys.path 注入
_HARNESS_DIR = Path(__file__).resolve().parent.parent.parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))
from overview_verdict import build_overview_verdict  # noqa: E402

CHECK_LABELS = {
    "git_status": "Git 状态",
    "check_health": "记忆健康",
    "bootstrap_check": "部署检查",
    "verify_prompt_system": "Prompt 系统",
    "verify_docs": "文档一致性",
    "smoke_test": "冒烟测试",
}

# 主区 4 个子系统 cell 的固定顺序（与 build_overview_verdict 输出顺序一致）
_SUBSYSTEM_ORDER = ["Git", "Daemon", "Doctor", "Health"]


class StatusPage(_BasePage):
    title = "今日状态"
    subtitle = "看头条结论 + 下一步即可。"
    page_id = "status"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._hero: VerdictHeroCard | None = None
        self._cells: dict[str, SubsystemCell] = {}
        self._doctor_detail_toggle: QToolButton | None = None
        self._doctor_detail_box: QFrame | None = None
        self._doctor_detail_labels: dict[str, QLabel] = {}
        self._fix_btn: QPushButton | None = None
        self._refresh_btn: QPushButton | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        self._fix_running = False
        # 缓存最近一次 status / doctor，给 build_overview_verdict 用
        self._latest_status: dict = {}
        self._latest_doctor_summary: dict = {}
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # ---- 结论 hero（含右上角 toolbar）----
        self._hero = verdict_hero_card(layout)
        self._hero.headline_label.setText("⌛ 正在加载...")

        self._fix_btn = QPushButton(qta.icon("fa5s.wrench"), "一键修复")
        self._fix_btn.setProperty("role", "primary")
        self._fix_btn.clicked.connect(self._on_fix_clicked)
        self._hero.toolbar_layout.addWidget(self._fix_btn)
        self._icon_buttons.append((self._fix_btn, "fa5s.wrench"))

        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        self._refresh_btn.setProperty("role", "secondary")
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._hero.toolbar_layout.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))

        # ---- 4 子系统横排 cell ----
        row = subsystem_row(layout)
        for name in _SUBSYSTEM_ORDER:
            self._cells[name] = subsystem_cell(row, name)

        # ---- Doctor 详情：可展开 6 项 check 列表 ----
        self._doctor_detail_toggle = QToolButton()
        self._doctor_detail_toggle.setObjectName("doctor-detail-toggle")
        self._doctor_detail_toggle.setCheckable(True)
        self._doctor_detail_toggle.setChecked(False)
        self._doctor_detail_toggle.setText("Doctor 6 项详情")
        self._doctor_detail_toggle.setIcon(qta.icon("fa5s.chevron-right"))
        self._doctor_detail_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._doctor_detail_toggle.setAutoRaise(True)
        self._doctor_detail_toggle.toggled.connect(self._on_doctor_detail_toggled)
        self._icon_buttons.append((self._doctor_detail_toggle, "fa5s.chevron-right"))
        layout.addWidget(self._doctor_detail_toggle)

        self._doctor_detail_box = QFrame()
        self._doctor_detail_box.setObjectName("doctor-detail-box")
        detail_layout = QVBoxLayout(self._doctor_detail_box)
        detail_layout.setContentsMargins(14, 4, 14, 8)
        detail_layout.setSpacing(4)
        for key, label in CHECK_LABELS.items():
            lbl = QLabel(f"{label}：—")
            lbl.setWordWrap(True)
            detail_layout.addWidget(lbl)
            self._doctor_detail_labels[key] = lbl
        self._doctor_detail_box.hide()
        layout.addWidget(self._doctor_detail_box)

    # -------- 行为 --------
    def _on_refresh(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="状态刷新",
            cmd=self._main.py_cmd("maintain.py", "status", "--json"),
            parse_json=True,
            extras={"action": "status"},
        )

    def _on_fix_clicked(self) -> None:
        if self._fix_running:
            return
        self._fix_running = True
        if self._fix_btn:
            self._fix_btn.setEnabled(False)
            self._fix_btn.setText("修复中...")
            self._fix_btn.setIcon(qta.icon("fa5s.spinner"))
        self._main.submit_cmd(
            page=self.page_id,
            title="一键修复",
            cmd=self._main.py_cmd("maintain.py", "fix", "--json"),
            parse_json=True,
            extras={"action": "fix"},
        )

    def _on_doctor_detail_toggled(self, checked: bool) -> None:
        if not self._doctor_detail_box or not self._doctor_detail_toggle:
            return
        self._doctor_detail_box.setVisible(checked)
        self._doctor_detail_toggle.setIcon(
            qta.icon("fa5s.chevron-down" if checked else "fa5s.chevron-right")
        )
        # 同步图标记忆，供主题切换时重建
        for i, (btn, _) in enumerate(self._icon_buttons):
            if btn is self._doctor_detail_toggle:
                self._icon_buttons[i] = (
                    btn,
                    "fa5s.chevron-down" if checked else "fa5s.chevron-right",
                )
                break

    def refresh(self) -> None:
        self._on_refresh()

    # -------- 结果 --------
    @Slot(object)
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        data = result.json
        if action == "status":
            if isinstance(data, dict):
                self._latest_status = data
                self._extract_latest_doctor_summary(data)
                self._refresh_verdict()
        elif action == "fix":
            self._on_fix_done(result)

    def _extract_latest_doctor_summary(self, data: dict) -> None:
        """从 maintain status --json 的 logs.maintain_tail 中翻最近一次 doctor 摘要。"""
        logs = (data.get("logs", {}) or {}).get("maintain_tail", []) or []
        for item in reversed(logs):
            if isinstance(item, dict) and item.get("type") == "doctor":
                self._latest_doctor_summary = {"summary": item.get("summary") or {}}
                return
        self._latest_doctor_summary = {}

    def _refresh_verdict(self) -> None:
        """跑 build_overview_verdict 重算并同步 hero + 4 cell。"""
        verdict = build_overview_verdict(
            status_json=self._latest_status,
            doctor_summary=self._latest_doctor_summary,
            health_signals=[],
        )
        self._apply_verdict(verdict)

    def _apply_verdict(self, verdict: dict) -> None:
        if not self._hero:
            return
        sev = verdict.get("severity", "info")
        self._hero.set_severity(sev)
        self._hero.headline_label.setText(verdict.get("headline", "—"))
        self._hero.reason_label.setText(verdict.get("reason", ""))
        self._hero.next_label.setText(self._format_next_action(verdict.get("next_action", "")))

        # 4 子系统 cell 同步
        for sub in verdict.get("subsystems", []) or []:
            cell = self._cells.get(sub.get("name"))
            if cell is None:
                continue
            cell.set_severity(sub.get("severity", "info"))
            cell.summary_label.setText(sub.get("summary", "—"))

        # Doctor 详情：warning/error 时若用户未手动收起，自动展开
        if sev in ("warning", "error") and self._doctor_detail_toggle:
            if not self._doctor_detail_toggle.isChecked():
                self._doctor_detail_toggle.setChecked(True)

    @staticmethod
    def _format_next_action(text: str) -> str:
        """next_action 文本里如有"终端跑：xxx"，把 xxx 包成等宽小药丸 RichText。

        这个是 view-side 文案处理，model 输出仍是纯文本。
        Qt RichText 不支持完整 CSS，但 font-family / background / padding inline style 可用。
        """
        if not text:
            return ""
        marker = "终端跑："
        if marker in text:
            prefix, cli = text.split(marker, 1)
            cli_html = (
                f'<span style="font-family: \'Cascadia Mono\', \'Consolas\', monospace;'
                f' background: rgba(196,123,107,0.10); padding: 2px 6px;'
                f' border-radius: 2px;">{escape(cli.strip())}</span>'
            )
            return f"下一步：{escape(prefix)}{marker}{cli_html}"
        return f"下一步：{escape(text)}"

    def _on_fix_done(self, result) -> None:
        self._fix_running = False
        if self._fix_btn:
            self._fix_btn.setEnabled(True)
            self._fix_btn.setText("一键修复")
            self._fix_btn.setIcon(qta.icon("fa5s.wrench"))

        data = result.json
        if isinstance(data, dict):
            summary = data.get("summary", {}) or {}
            # Doctor cell summary 直接更新（不必等下次 status）
            doctor_cell = self._cells.get("Doctor")
            if doctor_cell:
                err = int(summary.get("ERROR", 0))
                warn = int(summary.get("WARNING", 0))
                passed = int(summary.get("PASS", 0))
                if err:
                    doctor_cell.summary_label.setText(f"{err} 错 · {warn} 警告 · {passed} 通过")
                elif warn:
                    doctor_cell.summary_label.setText(f"{warn} 警告 · {passed} 通过")
                else:
                    doctor_cell.summary_label.setText(f"{passed} 项全过")

            # Doctor 6 项详情更新（用户展开时可见）
            for item in data.get("results", []) or []:
                if not isinstance(item, dict):
                    continue
                key = item.get("id")
                if key in self._doctor_detail_labels:
                    self._doctor_detail_labels[key].setText(
                        f"{CHECK_LABELS[key]}：{item.get('level')} · {item.get('summary')}"
                    )
            self._main.append_debug(
                f"\n# 一键修复 exit={result.returncode}\nsummary={summary} changed={data.get('changed')}\n",
                reveal=False,
            )
            # 把刚跑的 doctor 摘要直接喂给 verdict（不必等下次 status 刷新）
            self._latest_doctor_summary = {"summary": summary}
            self._refresh_verdict()
        else:
            doctor_cell = self._cells.get("Doctor")
            if doctor_cell:
                doctor_cell.summary_label.setText(f"修复退出码 {result.returncode}")
            self._main.append_debug(
                f"\n# 一键修复失败 exit={result.returncode}\n[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n",
                reveal=True,
            )
        # 强制再拉一次状态，把 logs.maintain_tail 中新生成的 doctor 条目刷进来
        self._on_refresh()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
