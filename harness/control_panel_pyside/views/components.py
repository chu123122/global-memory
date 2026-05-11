"""Small shared widgets/helpers for PySide control-panel views."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import qtawesome as qta


def section_card(parent_layout: QVBoxLayout, title: str, subtitle: str = "") -> QFrame:
    box = QFrame()
    box.setObjectName("section-card")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("section-title")
    title_label.setFont(QFont("", 11, QFont.Weight.Bold))
    layout.addWidget(title_label)

    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        layout.addWidget(sub)

    parent_layout.addWidget(box)
    return box


def action_button(parent: QFrame, label: str, icon_name: str, on_click, role: str = "secondary") -> QPushButton:
    btn = QPushButton(qta.icon(icon_name), label)
    btn.setProperty("role", role)
    btn.clicked.connect(on_click)
    parent.layout().addWidget(btn)
    return btn


def status_badge(text: str, role: str = "info") -> QLabel:
    badge = QLabel(text)
    badge.setObjectName("status-badge")
    badge.setProperty("role", role)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    badge.setMinimumWidth(92)
    badge.setFixedHeight(24)
    return badge


# ---------- UI-DESIGN 2026-04-28 方案 B 三级卡片体系 ----------

@dataclass
class VerdictHeroCard:
    """结论 hero 卡片的 widget 引用集合。

    view 层拿到这个对象后，updateBy verdict dict 调 set_verdict()。
    Q7 锁定面板纯只读，但 hero 右上角保留 toolbar_layout 给「一键修复」+「刷新」
    （这俩是 v1.3 例外的"功能性按钮"，不算管理按钮）。
    """
    frame: QFrame
    headline_label: QLabel
    reason_label: QLabel
    next_label: QLabel
    toolbar_layout: QHBoxLayout

    def set_severity(self, severity: str) -> None:
        """切 frame 的 severity property → 触发 left-border 颜色重算。"""
        self.frame.setProperty("severity", severity)
        self.frame.style().unpolish(self.frame)
        self.frame.style().polish(self.frame)


def verdict_hero_card(parent_layout: QVBoxLayout) -> VerdictHeroCard:
    """创建结论 hero 卡：唯一视觉重心，22pt headline + reason + hairline + next。

    布局：
      ┌──────────────────────────────────────────────────────┐
      │ {headline 22pt 衬线}                       [刷新][修复]│
      │ {reason 11pt 灰}                                       │
      │ ─────────── hairline ───────────                       │
      │ 下一步  {next_action}                                  │
      └──────────────────────────────────────────────────────┘
    """
    frame = QFrame()
    frame.setObjectName("verdict-hero")
    frame.setProperty("severity", "info")  # 初始 info，refresh 后切

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(8)

    # Row 1: headline + 右侧 toolbar 同行
    row1 = QHBoxLayout()
    row1.setSpacing(12)
    headline = QLabel("正在加载...")
    headline.setObjectName("hero")
    headline.setWordWrap(True)
    row1.addWidget(headline, stretch=1)

    toolbar = QHBoxLayout()
    toolbar.setSpacing(8)
    row1.addLayout(toolbar)
    layout.addLayout(row1)

    # Row 2: reason
    reason = QLabel("")
    reason.setObjectName("hero-reason")
    reason.setWordWrap(True)
    layout.addWidget(reason)

    # Hairline
    hairline = QFrame()
    hairline.setObjectName("hero-hairline")
    hairline.setFrameShape(QFrame.Shape.NoFrame)
    layout.addWidget(hairline)

    # Row 3: next
    next_label = QLabel("")
    next_label.setObjectName("hero-next")
    next_label.setWordWrap(True)
    next_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(next_label)

    parent_layout.addWidget(frame)

    return VerdictHeroCard(
        frame=frame,
        headline_label=headline,
        reason_label=reason,
        next_label=next_label,
        toolbar_layout=toolbar,
    )


@dataclass
class SubsystemCell:
    """子系统 cell（4 横排之一）的 widget 引用集合。"""
    frame: QFrame
    name_label: QLabel
    summary_label: QLabel

    def set_severity(self, severity: str) -> None:
        self.frame.setProperty("severity", severity)
        self.frame.style().unpolish(self.frame)
        self.frame.style().polish(self.frame)


def subsystem_cell(parent_layout: QHBoxLayout, name: str = "") -> SubsystemCell:
    """创建子系统 cell：3px 左边 sev 色 + name + summary。

    parent_layout 必须是 QHBoxLayout（4 个 cell 横排）。
    """
    frame = QFrame()
    frame.setObjectName("subsystem-cell")
    frame.setProperty("severity", "info")
    frame.setMinimumHeight(78)
    frame.setMinimumWidth(180)

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(4)

    name_label = QLabel(name or "—")
    name_label.setObjectName("subsys-name")
    layout.addWidget(name_label)

    summary_label = QLabel("…")
    summary_label.setObjectName("subsys-summary")
    summary_label.setWordWrap(True)
    layout.addWidget(summary_label)

    layout.addStretch(1)

    parent_layout.addWidget(frame, stretch=1)

    return SubsystemCell(
        frame=frame,
        name_label=name_label,
        summary_label=summary_label,
    )


def subsystem_row(parent_layout: QVBoxLayout) -> QHBoxLayout:
    """创建装 4 个 subsystem_cell 的横排容器（QHBoxLayout 内嵌进 QWidget）。"""
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)
    parent_layout.addWidget(container)
    return row
