"""Small shared widgets/helpers for PySide control-panel views."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout

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
