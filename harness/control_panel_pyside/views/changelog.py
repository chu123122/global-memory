"""变更页（v2.1 新增）：读 ~/.claude/global-memory/CHANGELOG.md 倒序展示最近 N 条。

每条以 `### [YYYY-MM-DD HH:MM]` 开头；切到本页或点[刷新]时拉一次，不轮询。
"""
from __future__ import annotations

import re
import sys
import subprocess
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from ._base import _BasePage

CHANGELOG_PATH = Path.home() / ".claude" / "global-memory" / "CHANGELOG.md"
MAX_ENTRIES = 20
HEADER_RE = re.compile(r"^### \[(?P<ts>[^\]]+)\] +(?P<rest>.*)$")


def _parse_entries(text: str, limit: int = MAX_ENTRIES) -> list[dict]:
    """切分 CHANGELOG.md 为条目列表（顶部为最新）。

    每条 = 从一个 `### [ts] ...` 头开始，到下一条 `### ` 之前。
    返回 list[{ts, header, body}]。
    """
    def _finalize(entry: dict) -> dict:
        entry["body"] = "\n".join(entry.pop("body_lines"))
        return entry

    lines = text.splitlines()
    entries: list[dict] = []
    cur: dict | None = None
    for line in lines:
        m = HEADER_RE.match(line)
        if m:
            if cur is not None:
                entries.append(_finalize(cur))
                if len(entries) >= limit:
                    return entries
            cur = {
                "ts": m.group("ts"),
                "header": m.group("rest").strip(),
                "body_lines": [line],
            }
        elif cur is not None:
            cur["body_lines"].append(line)
    if cur is not None and len(entries) < limit:
        entries.append(_finalize(cur))
    return entries


class ChangelogPage(_BasePage):
    title = "变更"
    subtitle = f"~/.claude/global-memory/CHANGELOG.md 最近 {MAX_ENTRIES} 条"
    page_id = "changelog"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._list: QListWidget | None = None
        self._detail: QTextBrowser | None = None
        self._refresh_btn: QPushButton | None = None
        self._open_btn: QPushButton | None = None
        self._info_label: QLabel | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        self._entries: list[dict] = []
        self._loaded_once = False
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()
        self._info_label = QLabel("变更记录（未加载）")
        self._info_label.setFont(QFont("", 11))
        toolbar.addWidget(self._info_label)
        toolbar.addStretch(1)

        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        self._refresh_btn.setProperty("role", "secondary")
        self._refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))

        self._open_btn = QPushButton(qta.icon("fa5s.external-link-alt"), "打开完整 CHANGELOG")
        self._open_btn.setProperty("role", "secondary")
        self._open_btn.clicked.connect(self._on_open_full)
        toolbar.addWidget(self._open_btn)
        self._icon_buttons.append((self._open_btn, "fa5s.external-link-alt"))
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self._list)

        self._detail = QTextBrowser()
        self._detail.setOpenExternalLinks(True)
        splitter.addWidget(self._detail)
        splitter.setSizes([220, 320])
        layout.addWidget(splitter, stretch=1)

    # -------- 行为 --------
    def _on_refresh(self) -> None:
        if not CHANGELOG_PATH.exists():
            if self._info_label:
                self._info_label.setText(f"未找到：{CHANGELOG_PATH}")
            return
        try:
            text = CHANGELOG_PATH.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            if self._info_label:
                self._info_label.setText(f"读取失败：{type(exc).__name__}: {exc}")
            return
        self._entries = _parse_entries(text, limit=MAX_ENTRIES)
        if self._list is None:
            return
        self._list.clear()
        for entry in self._entries:
            display = f"[{entry['ts']}]  {entry['header']}"
            item = QListWidgetItem(display)
            self._list.addItem(item)
        if self._info_label:
            self._info_label.setText(
                f"变更记录（最近 {len(self._entries)} 条 / 文件 {CHANGELOG_PATH.stat().st_size // 1024} KB）"
            )
        if self._entries:
            self._list.setCurrentRow(0)

    def _on_select(self) -> None:
        if self._list is None or self._detail is None:
            return
        row = self._list.currentRow()
        if 0 <= row < len(self._entries):
            self._detail.setMarkdown(self._entries[row]["body"])

    def _on_open_full(self) -> None:
        if not CHANGELOG_PATH.exists():
            QMessageBox.warning(self, "未找到", str(CHANGELOG_PATH))
            return
        self._main.open_path(CHANGELOG_PATH)

    def refresh(self) -> None:
        # 第一次切到本页时拉一次；之后只在点刷新时拉
        if not self._loaded_once:
            self._loaded_once = True
            self._on_refresh()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
