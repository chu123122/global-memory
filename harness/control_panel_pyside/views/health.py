"""健康检测页：调 harness.health.runner --json，渲染 signal 卡片。

设计意图：把审计自动化。每个 signal 一行 + 可展开证据 + 修复提示。
点[刷新]异步重跑全部检测器。
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
    QVBoxLayout,
)

from ._base import _BasePage
from .components import section_card

STATUS_META = {
    "critical": ("danger", "🔴", "严重"),
    "warning": ("warning", "🟡", "警告"),
    "info": ("info", "🔵", "提示"),
    "ok": ("success", "🟢", "正常"),
}
STATUS_ORDER = {"critical": 0, "warning": 1, "info": 2, "ok": 3}


class HealthPage(_BasePage):
    title = "健康"
    subtitle = "harness.health.runner 全量检测；红=须修，黄=注意，蓝=可观察。"
    page_id = "health"
    auto_refresh_interval_sec = 30.0

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._summary_label: QLabel | None = None
        self._cards_container: QFrame | None = None
        self._refresh_btn: QPushButton | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()
        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        self._refresh_btn.setProperty("role", "primary")
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        summary = section_card(layout, "汇总", "按严重度排序；同一 check 可能产出多条 signal。")
        self._summary_label = QLabel("尚未刷新。")
        self._summary_label.setWordWrap(True)
        summary.layout().addWidget(self._summary_label)

        self._cards_container = QFrame()
        cards_layout = QVBoxLayout(self._cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)
        layout.addWidget(self._cards_container)

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

    def handle_result(self, result) -> None:
        if result.returncode not in (0, 1):  # runner 在有 warning/critical 时返回 1
            self._summary_label.setText(
                f"<span style='color:#c62828'>检测器异常 (exit={result.returncode})</span>"
                f"<br>stderr: <code>{escape(result.stderr[:200])}</code>"
            )
            return
        data = result.json or {}
        signals = data.get("signals", [])
        self._render_summary(signals)
        self._render_cards(signals)

    def _render_summary(self, signals: list[dict]) -> None:
        if not signals:
            self._summary_label.setText("无 signal 返回。")
            return
        counts = {k: 0 for k in STATUS_META}
        for s in signals:
            counts[s.get("status", "info")] = counts.get(s.get("status", "info"), 0) + 1
        parts = []
        for st, (_, glyph, label) in STATUS_META.items():
            if counts[st]:
                parts.append(f"{glyph} {label} {counts[st]}")
        self._summary_label.setText(
            "  ".join(parts) if parts else "全部 signal 缺 status 字段"
        )

    def _render_cards(self, signals: list[dict]) -> None:
        if not self._cards_container:
            return
        layout = self._cards_container.layout()
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        signals_sorted = sorted(
            signals, key=lambda s: (STATUS_ORDER.get(s.get("status", "info"), 9), s.get("check_id", ""))
        )
        for s in signals_sorted:
            layout.addWidget(self._build_card(s))

    def _build_card(self, signal: dict) -> QFrame:
        status = signal.get("status", "info")
        role, glyph, _label = STATUS_META.get(status, ("info", "·", "?"))

        card = QFrame()
        card.setObjectName("health-card")
        card.setProperty("role", role)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)

        title = QLabel(
            f"<b>{glyph} [{status}] {escape(signal.get('check_id',''))}</b> &nbsp; "
            f"<span style='color:#888'>{escape(signal.get('value',''))}</span>"
        )
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setWordWrap(True)
        v.addWidget(title)

        head = QLabel(escape(signal.get("headline", "")))
        head.setWordWrap(True)
        v.addWidget(head)

        evidence = signal.get("evidence", []) or []
        if evidence:
            ev_html = "<br>".join(f"&nbsp;&nbsp;· {escape(str(e))}" for e in evidence[:8])
            ev = QLabel(f"<span style='color:#666;font-family:Consolas,monospace;font-size:11px'>{ev_html}</span>")
            ev.setTextFormat(Qt.TextFormat.RichText)
            ev.setWordWrap(True)
            v.addWidget(ev)

        if signal.get("fix_hint"):
            hint = QLabel(f"<span style='color:#1565c0'>↳ {escape(signal['fix_hint'])}</span>")
            hint.setTextFormat(Qt.TextFormat.RichText)
            hint.setWordWrap(True)
            v.addWidget(hint)

        return card

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, name in self._icon_buttons:
            btn.setIcon(qta.icon(name))
