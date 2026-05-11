"""健康检测页（Day 3 重构）：

- emoji `🔴🟡🔵🟢` → unicode `✕⚠●●` 与状态页统一视觉语言（修 P1-5）
- diff 复用 widget，不再每 30s deleteLater + 重建（修 P2-2 闪烁）
- 卡片用 subsystem-cell 体系（severity property 切 left-border 颜色）
- 默认折叠"已通过"signals，仅显示非 ok 项
"""
from __future__ import annotations

from html import escape

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from ._base import _BasePage

# Day 3 统一字符指示符（与状态页/overview_verdict 语言一致）
STATUS_GLYPH = {
    "critical": "✕",
    "error": "✕",
    "warning": "⚠",
    "info": "●",
    "ok": "●",
}
# critical → error 同色，info / ok 同灰但 ok 是绿
STATUS_TO_SEVERITY = {
    "critical": "error",
    "error": "error",
    "warning": "warning",
    "info": "info",
    "ok": "ok",
}
STATUS_ORDER = {"critical": 0, "error": 0, "warning": 1, "info": 2, "ok": 3}


class HealthPage(_BasePage):
    title = "健康"
    subtitle = "harness.health.runner 全量检测；仅显示警告/严重；点开「已通过」看全部"
    page_id = "health"
    auto_refresh_interval_sec = 30.0

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._summary_label: QLabel | None = None
        self._cards_container: QFrame | None = None
        self._refresh_btn: QPushButton | None = None
        self._ok_toggle: QToolButton | None = None
        self._ok_container: QFrame | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        # Day 3 P2-2 修：维护 check_id → widget 字典，刷新时复用
        self._signal_widgets: dict[str, QFrame] = {}
        self._ok_widgets: dict[str, QFrame] = {}
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # 顶部：汇总 + 刷新
        toolbar = QHBoxLayout()
        self._summary_label = QLabel("尚未检测")
        self._summary_label.setWordWrap(True)
        toolbar.addWidget(self._summary_label, stretch=1)

        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        self._refresh_btn.setProperty("role", "secondary")
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))
        layout.addLayout(toolbar)

        # 警告/严重 signal 区（始终展示）
        self._cards_container = QFrame()
        cards_layout = QVBoxLayout(self._cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)
        layout.addWidget(self._cards_container)

        # 已通过 signals 折叠区
        self._ok_toggle = QToolButton()
        self._ok_toggle.setCheckable(True)
        self._ok_toggle.setChecked(False)
        self._ok_toggle.setText("已通过的检查")
        self._ok_toggle.setIcon(qta.icon("fa5s.chevron-right"))
        self._ok_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._ok_toggle.setAutoRaise(True)
        self._ok_toggle.toggled.connect(self._on_ok_toggled)
        layout.addWidget(self._ok_toggle)
        self._icon_buttons.append((self._ok_toggle, "fa5s.chevron-right"))

        self._ok_container = QFrame()
        ok_layout = QVBoxLayout(self._ok_container)
        ok_layout.setContentsMargins(0, 0, 0, 0)
        ok_layout.setSpacing(6)
        self._ok_container.hide()
        layout.addWidget(self._ok_container)

    # -------- 行为 --------
    def refresh(self) -> None:
        py = self._main.py_cmd("dummy.py")[0]
        cmd = [py, "-m", "harness.health.runner", "--json", "--no-log"]
        self._main.submit_cmd(
            page=self.page_id,
            title="健康检测",
            cmd=cmd,
            parse_json=True,
            extras={"action": "health"},
        )

    def _on_ok_toggled(self, checked: bool) -> None:
        if not self._ok_container or not self._ok_toggle:
            return
        self._ok_container.setVisible(checked)
        icon = "fa5s.chevron-down" if checked else "fa5s.chevron-right"
        self._ok_toggle.setIcon(qta.icon(icon))
        for i, (btn, _) in enumerate(self._icon_buttons):
            if btn is self._ok_toggle:
                self._icon_buttons[i] = (btn, icon)
                break

    def handle_result(self, result) -> None:
        # health runner 在有 warning/critical 时也返回 1，是合法信号
        if result.returncode not in (0, 1):
            if self._summary_label:
                self._summary_label.setText(
                    f"<span style='color:#b94a3a'>检测器异常 (exit={result.returncode})</span>"
                    f"<br><span style='color:gray'>stderr: <code>{escape(result.stderr[:200])}</code></span>"
                )
            return
        data = result.json or {}
        signals = data.get("signals", [])
        self._render_summary(signals)
        self._render_cards(signals)

    def _render_summary(self, signals: list[dict]) -> None:
        if not self._summary_label:
            return
        if not signals:
            self._summary_label.setText("无 signal 返回")
            return
        counts = {"critical": 0, "warning": 0, "info": 0, "ok": 0}
        for s in signals:
            st = str(s.get("status", "info"))
            if st == "error":
                st = "critical"
            counts[st] = counts.get(st, 0) + 1
        total = len(signals)
        parts = [f"共 {total} 项"]
        if counts["critical"]:
            parts.append(f"<span style='color:#b94a3a'>✕ 严重 {counts['critical']}</span>")
        if counts["warning"]:
            parts.append(f"<span style='color:#c8a165'>⚠ 警告 {counts['warning']}</span>")
        if counts["info"]:
            parts.append(f"<span style='color:#7b9bb5'>● 提示 {counts['info']}</span>")
        if counts["ok"]:
            parts.append(f"<span style='color:#8baa7d'>● 通过 {counts['ok']}</span>")
        self._summary_label.setText(" · ".join(parts))

    def _render_cards(self, signals: list[dict]) -> None:
        """Day 3 P2-2 修：diff 复用 widget，不再 deleteLater 全重建。

        新增的 check_id → 创建并 addWidget。
        消失的 check_id → hide()（不 delete，下次出现复用）。
        变化的 check_id → 复用同 widget，仅 setText + 切 severity property。
        """
        if not self._cards_container:
            return

        signals_sorted = sorted(
            signals, key=lambda s: (STATUS_ORDER.get(s.get("status", "info"), 9), s.get("check_id", ""))
        )

        non_ok = [s for s in signals_sorted if s.get("status") not in ("ok",)]
        ok_signals = [s for s in signals_sorted if s.get("status") == "ok"]

        # 顶部主区：非 ok signals
        seen_non_ok: set[str] = set()
        for s in non_ok:
            cid = str(s.get("check_id", ""))
            if not cid:
                continue
            seen_non_ok.add(cid)
            widget = self._signal_widgets.get(cid)
            if widget is None:
                widget = self._build_card_widget()
                self._cards_container.layout().addWidget(widget)
                self._signal_widgets[cid] = widget
            widget.show()
            self._update_card_widget(widget, s)
        for cid, widget in self._signal_widgets.items():
            if cid not in seen_non_ok:
                widget.hide()

        # 折叠区：ok signals
        if not self._ok_container:
            return
        seen_ok: set[str] = set()
        for s in ok_signals:
            cid = str(s.get("check_id", ""))
            if not cid:
                continue
            seen_ok.add(cid)
            widget = self._ok_widgets.get(cid)
            if widget is None:
                widget = self._build_card_widget(compact=True)
                self._ok_container.layout().addWidget(widget)
                self._ok_widgets[cid] = widget
            widget.show()
            self._update_card_widget(widget, s)
        for cid, widget in self._ok_widgets.items():
            if cid not in seen_ok:
                widget.hide()

        if self._ok_toggle:
            self._ok_toggle.setText(f"已通过的检查（{len(ok_signals)}）")

    def _build_card_widget(self, compact: bool = False) -> QFrame:
        """复用 subsystem-cell 体系的样式（统一视觉语言）。"""
        card = QFrame()
        card.setObjectName("subsystem-cell")
        card.setProperty("severity", "info")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 8 if compact else 10, 14, 8 if compact else 10)
        v.setSpacing(2 if compact else 4)

        title = QLabel("")
        title.setObjectName("subsys-name")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setWordWrap(True)
        v.addWidget(title)

        head = QLabel("")
        head.setObjectName("subsys-summary")
        head.setWordWrap(True)
        v.addWidget(head)

        evidence_label = QLabel("")
        evidence_label.setObjectName("muted")
        evidence_label.setTextFormat(Qt.TextFormat.RichText)
        evidence_label.setWordWrap(True)
        evidence_label.setVisible(not compact)
        v.addWidget(evidence_label)

        hint_label = QLabel("")
        hint_label.setTextFormat(Qt.TextFormat.RichText)
        hint_label.setWordWrap(True)
        hint_label.setVisible(not compact)
        v.addWidget(hint_label)

        # 把子 label 引用挂在 card 上，方便 _update_card_widget 拿
        card._title = title
        card._head = head
        card._evidence = evidence_label
        card._hint = hint_label
        card._compact = compact
        return card

    def _update_card_widget(self, card: QFrame, signal: dict) -> None:
        status = str(signal.get("status", "info"))
        glyph = STATUS_GLYPH.get(status, "·")
        sev = STATUS_TO_SEVERITY.get(status, "info")
        # 切 severity property → border-left 颜色重算
        card.setProperty("severity", sev)
        card.style().unpolish(card)
        card.style().polish(card)

        check_id = escape(str(signal.get("check_id", "")))
        value = escape(str(signal.get("value", "")))
        title_html = f"<b>{glyph} {check_id}</b>"
        if value:
            title_html += f" &nbsp;<span style='color:#7a6e5e'>{value}</span>"
        card._title.setText(title_html)

        card._head.setText(escape(str(signal.get("headline", ""))))

        if not getattr(card, "_compact", False):
            evidence = signal.get("evidence", []) or []
            if evidence:
                ev_html = "<br>".join(
                    f"&nbsp;&nbsp;· {escape(str(e))}" for e in evidence[:6]
                )
                card._evidence.setText(
                    f"<span style='color:#7a6e5e;font-family:Consolas,monospace;font-size:10pt'>{ev_html}</span>"
                )
                card._evidence.setVisible(True)
            else:
                card._evidence.setVisible(False)

            fix_hint = str(signal.get("fix_hint") or "")
            if fix_hint:
                card._hint.setText(f"<span style='color:#7b9bb5'>↳ {escape(fix_hint)}</span>")
                card._hint.setVisible(True)
            else:
                card._hint.setVisible(False)

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, name in self._icon_buttons:
            btn.setIcon(qta.icon(name))
