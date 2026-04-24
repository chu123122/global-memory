"""右侧结论面板：QStackedWidget 包裹的多视图。

设计 §1：右侧结论面板通过 QStackedWidget 切换视图：
  - DecisionView  : 总览/同步/体检的"现在该看什么"决策
  - TaskBriefView : 任务页选中卡片时显示长版简介

PageId 用枚举常量，避免裸 int 散落。
"""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path
import re

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .views.components import status_badge

LEVEL_ROLES = {"ok": "ok", "success": "ok", "info": "info", "warning": "warning", "error": "error"}
UI_FONT = "Noto Sans SC"
READING_FONT = "Noto Serif SC"
MONO_FONT = "Cascadia Mono"


class PageId(IntEnum):
    DECISION = 0
    TASK_BRIEF = 1


class _DecisionView(QWidget):
    """渲染 model 层 summarize_*('decision') + cards 列表。"""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("现在该看什么")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        sub = QLabel("默认只展示脚本提炼后的结论；命令行原文放在调试输出里。")
        sub.setStyleSheet("color: gray;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        self._headline = QLabel("正在读取状态...")
        self._headline.setObjectName("decision-headline")
        self._headline.setWordWrap(True)
        layout.addWidget(self._headline)

        self._next_action = QLabel("下一步：等待快速状态返回")
        self._next_action.setObjectName("decision-next")
        self._next_action.setWordWrap(True)
        layout.addWidget(self._next_action)

        self._why = QLabel("面板会根据 maintain.py 返回的数据自动整理。")
        self._why.setObjectName("decision-why")
        self._why.setWordWrap(True)
        layout.addWidget(self._why)

        cards_label = QLabel("关键数据")
        cards_label.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(cards_label)

        self._cards = QTreeWidget()
        self._cards.setColumnCount(3)
        self._cards.setHeaderLabels(["项目", "值", "级别"])
        self._cards.setRootIsDecorated(False)
        self._cards.setAlternatingRowColors(True)
        self._cards.header().setStretchLastSection(False)
        self._cards.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._cards.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._cards.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._cards, stretch=1)

    def set_decision(self, decision: dict) -> None:
        self._headline.setText(str(decision.get("headline", "暂无结论")))
        self._next_action.setText(str(decision.get("next_action", "下一步：暂无")))
        self._why.setText(str(decision.get("why", "")))
        role = LEVEL_ROLES.get(str(decision.get("level", "info")).lower(), "info")
        for widget in (self._headline, self._next_action):
            widget.setProperty("role", role)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def set_cards(self, cards: list[dict]) -> None:
        self._cards.clear()
        for card in cards:
            if not isinstance(card, dict):
                continue
            level = str(card.get("level", "info")).lower()
            item = QTreeWidgetItem([
                str(card.get("title", "")),
                str(card.get("value", "")),
                level,
            ])
            item.setForeground(2, Qt.GlobalColor.darkGray)
            self._cards.addTopLevelItem(item)


class _TaskBriefView(QWidget):
    """任务页点击卡片时显示长版简介（来自 需求分析.md / HANDOFF.md）。"""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._title = QLabel("(未选中任务)")
        self._title.setObjectName("task-brief-title")
        self._title.setFont(QFont(UI_FONT, 15, QFont.Weight.DemiBold))
        layout.addWidget(self._title)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self._stage_badge = status_badge("unknown", "unknown")
        meta_row.addWidget(self._stage_badge, 0, Qt.AlignmentFlag.AlignLeft)
        self._meta = QLabel("")
        self._meta.setObjectName("task-brief-meta")
        self._meta.setWordWrap(True)
        meta_row.addWidget(self._meta, stretch=1)
        layout.addLayout(meta_row)

        self._brief = QTextBrowser()
        self._brief.setObjectName("markdown-reader")
        self._brief.setReadOnly(True)
        self._brief.setOpenExternalLinks(False)
        self._brief.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._brief.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._brief.setFont(QFont(READING_FONT, 10))
        self._brief.document().setDocumentMargin(18)
        self._brief.document().setDefaultStyleSheet(_markdown_css())
        layout.addWidget(self._brief, stretch=1)

    def show_task(self, name: str, stage: str, path: str, brief: str) -> None:
        self._title.setText(name)
        self._stage_badge.setText(stage or "unknown")
        self._stage_badge.setProperty("role", stage or "unknown")
        self._stage_badge.style().unpolish(self._stage_badge)
        self._stage_badge.style().polish(self._stage_badge)
        self._meta.setText(path)
        long_brief = self._read_long_brief(Path(path), fallback=brief)
        # Qt Markdown 支持 GFM 子集；样式由 markdown-reader + document CSS 控制。
        self._brief.setMarkdown(long_brief)
        self._brief.verticalScrollBar().setValue(0)

    def _read_long_brief(self, task_dir: Path, fallback: str) -> str:
        """优先抽取可读摘要章节，避免把整篇 SPEC 的表格/长清单直接塞进侧栏。"""
        candidates = [
            task_dir / "需求分析.md",
            task_dir / "HANDOFF.md",
            task_dir / "SPEC.md",
            task_dir / "REQUIREMENTS.md",  # 老命名兼容
            task_dir / "DESIGN.md",
        ]
        for path in candidates:
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    extracted = _extract_readable_markdown(text)
                    if extracted:
                        return _compose_task_markdown(fallback, extracted)
                except OSError:
                    continue
        return _compose_task_markdown(fallback, "")


def _markdown_css() -> str:
    return """
    body {
        font-family: "Noto Serif SC", "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
        font-size: 14px;
        line-height: 1.68;
    }
    h1, h2, h3 {
        font-family: "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
        margin-top: 16px;
        margin-bottom: 8px;
        font-weight: 700;
    }
    h1 { font-size: 21px; }
    h2 { font-size: 18px; }
    h3 { font-size: 16px; }
    p, li { margin-top: 5px; margin-bottom: 7px; }
    ul, ol { margin-top: 5px; margin-bottom: 10px; }
    code {
        font-family: "Cascadia Mono", "JetBrains Mono", monospace;
        font-size: 12px;
        padding: 1px 4px;
    }
    pre {
        margin: 8px 0;
        padding: 10px;
    }
    table {
        border-collapse: collapse;
        margin-top: 8px;
        margin-bottom: 12px;
    }
    th, td {
        padding: 7px 9px;
        vertical-align: top;
    }
    blockquote {
        margin: 8px 0;
        padding-left: 10px;
    }
    """


def _compose_task_markdown(fallback: str, extracted: str) -> str:
    parts = []
    if fallback.strip():
        parts.append("## 摘要\n\n" + fallback.strip())
    if extracted.strip():
        parts.append(extracted.strip())
    return "\n\n---\n\n".join(parts) if parts else "(无简介)"


def _extract_readable_markdown(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(r"^---\n.*?\n---\n", "", normalized, flags=re.S)
    normalized = _simplify_markdown_for_sidebar(normalized)
    sections = _split_markdown_sections(normalized)
    preferred = (
        "摘要", "概览", "背景", "目标", "问题", "需求", "范围", "当前状态", "交接", "handoff", "summary",
    )
    for heading, body in sections:
        heading_l = heading.lower()
        if any(key in heading_l for key in preferred):
            return _trim_markdown(f"{heading}\n\n{body}")
    return _trim_markdown(normalized)


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^(#{1,3}\s+.+)$", text))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[start:end].strip()))
    return sections


def _trim_markdown(text: str, limit: int = 4200) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    cut = stripped[:limit]
    last_break = max(cut.rfind("\n## "), cut.rfind("\n\n"), cut.rfind("\n- "))
    if last_break > limit * 0.55:
        cut = cut[:last_break]
    return cut.rstrip() + "\n\n> 侧栏只显示摘要片段；完整内容请右键任务卡片打开目录查看。"


def _simplify_markdown_for_sidebar(text: str) -> str:
    """Remove wide Markdown tables that are not readable in the narrow side panel."""
    lines = text.splitlines()
    output: list[str] = []
    idx = 0
    table_notice_added = False
    while idx < len(lines):
        if _is_markdown_table_start(lines, idx):
            idx += 2
            while idx < len(lines) and "|" in lines[idx] and not lines[idx].lstrip().startswith("#"):
                idx += 1
            if not table_notice_added:
                output.append("> 侧栏已省略宽表格；右键任务卡片打开目录查看完整 Markdown。")
                table_notice_added = True
            continue
        output.append(lines[idx])
        idx += 1
    return "\n".join(output)


def _is_markdown_table_start(lines: list[str], idx: int) -> bool:
    if idx + 1 >= len(lines):
        return False
    header = lines[idx].strip()
    separator = lines[idx + 1].strip()
    if "|" not in header or "|" not in separator:
        return False
    return bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", separator))


class ConclusionPanel(QWidget):
    """右侧结论面板容器。"""

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        outer.addWidget(self._scroll)

        self._stack = QStackedWidget()
        self._scroll.setWidget(self._stack)

        self._decision = _DecisionView()
        self._task_brief = _TaskBriefView()
        self._stack.insertWidget(int(PageId.DECISION), self._decision)
        self._stack.insertWidget(int(PageId.TASK_BRIEF), self._task_brief)
        self._stack.setCurrentIndex(int(PageId.DECISION))

    @Slot(str)
    def switch_to_page(self, page_id: str) -> None:
        # 实际任务卡点击会走 show_task() 主动切换；此处只在 tab 切走时回到 Decision。
        if page_id != "tasks":
            self._stack.setCurrentIndex(int(PageId.DECISION))

    def set_decision(self, decision: dict) -> None:
        self._decision.set_decision(decision)
        self._stack.setCurrentIndex(int(PageId.DECISION))

    def set_cards(self, cards: list[dict]) -> None:
        self._decision.set_cards(cards)

    def show_task(self, name: str, stage: str, path: str, brief: str) -> None:
        self._task_brief.show_task(name, stage, path, brief)
        self._stack.setCurrentIndex(int(PageId.TASK_BRIEF))
