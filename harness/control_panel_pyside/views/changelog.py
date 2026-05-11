"""变更页（v2.1 新增）：读 ~/.claude/global-memory/CHANGELOG.md 倒序展示最近 N 条。

每条以 `### [YYYY-MM-DD HH:MM]` 开头；切到本页或点[刷新]时拉一次，不轮询。
"""
from __future__ import annotations

import re
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
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
PARSE_LIMIT = 100
HEADER_RE = re.compile(r"^### \[(?P<ts>[^\]]+)\] +(?P<rest>.*)$")
KIND_RE = re.compile(r"^\[(?P<kind>[A-Z][A-Z0-9_-]*)\]\s+(?P<title>.*)$")


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
                "kind": _entry_kind(m.group("rest").strip()),
                "project": _entry_project(m.group("rest").strip()),
                "body_lines": [line],
            }
        elif cur is not None:
            cur["body_lines"].append(line)
    if cur is not None and len(entries) < limit:
        entries.append(_finalize(cur))
    return entries


def _entry_kind(header: str) -> str:
    m = KIND_RE.match(header)
    return m.group("kind") if m else "OTHER"


def _entry_project(header: str) -> str:
    title = KIND_RE.match(header).group("title") if KIND_RE.match(header) else header
    for sep in (" ", "：", ":"):
        if sep in title:
            title = title.split(sep, 1)[0]
            break
    return title.strip() or "未分类"


class ChangelogPage(_BasePage):
    title = "变更"
    subtitle = f"最近 {MAX_ENTRIES} 条 CHANGELOG 记录"
    page_id = "changelog"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._list: QListWidget | None = None
        self._detail: QTextBrowser | None = None
        self._refresh_btn: QPushButton | None = None
        self._open_btn: QPushButton | None = None
        self._info_label: QLabel | None = None
        self._project_filter: QComboBox | None = None
        self._kind_filter: QComboBox | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        self._all_entries: list[dict] = []
        self._entries: list[dict] = []
        self._loaded_once = False
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # 顶部信息行
        info_row = QHBoxLayout()
        self._info_label = QLabel("加载中...")
        self._info_label.setObjectName("muted")
        info_row.addWidget(self._info_label, stretch=1)

        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        self._refresh_btn.setProperty("role", "secondary")
        self._refresh_btn.clicked.connect(self._on_refresh)
        info_row.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))

        self._open_btn = QPushButton(qta.icon("fa5s.external-link-alt"), "打开完整 CHANGELOG")
        self._open_btn.setProperty("role", "secondary")
        self._open_btn.clicked.connect(self._on_open_full)
        info_row.addWidget(self._open_btn)
        self._icon_buttons.append((self._open_btn, "fa5s.external-link-alt"))
        layout.addLayout(info_row)

        # 过滤行（Day 3：移到独立一行避免拥挤）
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("项目"))
        self._project_filter = QComboBox()
        self._project_filter.setMinimumWidth(190)
        self._project_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._project_filter)

        filter_row.addSpacing(12)
        filter_row.addWidget(QLabel("类型"))
        self._kind_filter = QComboBox()
        self._kind_filter.setMinimumWidth(120)
        self._kind_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._kind_filter)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._list = QListWidget()
        self._list.setWordWrap(True)
        self._list.setMinimumWidth(330)
        self._list.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self._list)

        # detail 走主面板 markdown-reader QSS（Day 3：移除内嵌 defaultStyleSheet 让全局 QSS 接管）
        self._detail = QTextBrowser()
        self._detail.setObjectName("markdown-reader")
        self._detail.setOpenExternalLinks(True)
        self._detail.setMinimumWidth(460)
        splitter.addWidget(self._detail)
        splitter.setSizes([360, 620])
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
        self._all_entries = _parse_entries(text, limit=PARSE_LIMIT)
        self._refresh_filter_options()
        self._apply_filters()
        self._update_info()

    def _refresh_filter_options(self) -> None:
        if self._project_filter is None or self._kind_filter is None:
            return
        current_project = self._project_filter.currentData() or "*"
        current_kind = self._kind_filter.currentData() or "*"
        projects = sorted({entry.get("project", "未分类") for entry in self._all_entries})
        kinds = sorted({entry.get("kind", "OTHER") for entry in self._all_entries})

        self._project_filter.blockSignals(True)
        self._kind_filter.blockSignals(True)
        self._project_filter.clear()
        self._project_filter.addItem("全部项目", "*")
        for project in projects:
            self._project_filter.addItem(project, project)
        self._kind_filter.clear()
        self._kind_filter.addItem("全部类型", "*")
        for kind in kinds:
            self._kind_filter.addItem(kind, kind)
        self._set_combo_by_data(self._project_filter, current_project)
        self._set_combo_by_data(self._kind_filter, current_kind)
        self._project_filter.blockSignals(False)
        self._kind_filter.blockSignals(False)

    def _apply_filters(self) -> None:
        project = self._project_filter.currentData() if self._project_filter else "*"
        kind = self._kind_filter.currentData() if self._kind_filter else "*"
        entries = []
        for entry in self._all_entries:
            if project not in (None, "*") and entry.get("project") != project:
                continue
            if kind not in (None, "*") and entry.get("kind") != kind:
                continue
            entries.append(entry)
        self._entries = entries[:MAX_ENTRIES]
        if self._list is None:
            return
        self._list.clear()
        for entry in self._entries:
            display = f"{entry['ts']}\n{entry['header']}"
            item = QListWidgetItem(display)
            item.setToolTip(f"[{entry['ts']}] {entry['header']}")
            item.setSizeHint(QSize(320, 58))
            self._list.addItem(item)
        self._update_info()
        if self._detail is not None:
            self._detail.clear()
        if self._info_label:
            self._update_info()
        if self._entries:
            self._list.setCurrentRow(0)

    @staticmethod
    def _set_combo_by_data(combo: QComboBox, value: str) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value:
                combo.setCurrentIndex(idx)
                return
        combo.setCurrentIndex(0)

    def _update_info(self) -> None:
        if self._info_label is None:
            return
        size_kb = CHANGELOG_PATH.stat().st_size // 1024 if CHANGELOG_PATH.exists() else 0
        self._info_label.setText(
            f"显示 {len(self._entries)} 条 · 已解析 {len(self._all_entries)} 条 · 文件 {size_kb} KB"
        )

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
