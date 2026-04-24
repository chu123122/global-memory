"""右侧结论面板：QStackedWidget 包裹的多视图。

设计 §1：右侧结论面板通过 QStackedWidget 切换视图：
  - DecisionView  : 总览/同步/体检的"现在该看什么"决策
  - TaskBriefView : 任务页选中卡片时显示长版简介

PageId 用枚举常量，避免裸 int 散落。
"""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

LEVEL_COLORS = {
    "ok": "#087443",
    "info": "#0F3D5E",
    "warning": "#D97706",
    "error": "#B42318",
}


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
        self._headline.setWordWrap(True)
        self._headline.setStyleSheet(
            "padding: 12px; background: rgba(15,61,94,0.12);"
            "border-radius: 4px; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(self._headline)

        self._next_action = QLabel("下一步：等待快速状态返回")
        self._next_action.setWordWrap(True)
        self._next_action.setStyleSheet(
            "padding: 8px; background: rgba(15,61,94,0.06); border-radius: 4px;"
        )
        layout.addWidget(self._next_action)

        self._why = QLabel("面板会根据 maintain.py 返回的数据自动整理。")
        self._why.setWordWrap(True)
        self._why.setStyleSheet("padding: 8px; color: gray;")
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

    def set_cards(self, cards: list[dict]) -> None:
        self._cards.clear()
        for card in cards:
            if not isinstance(card, dict):
                continue
            level = str(card.get("level", "info")).lower()
            color = LEVEL_COLORS.get(level, "#0F3D5E")
            item = QTreeWidgetItem([
                str(card.get("title", "")),
                str(card.get("value", "")),
                level,
            ])
            item.setForeground(2, Qt.GlobalColor.darkGray)
            item.setData(2, Qt.ItemDataRole.UserRole, color)
            self._cards.addTopLevelItem(item)


class _TaskBriefView(QWidget):
    """任务页点击卡片时显示长版简介（来自 需求分析.md / HANDOFF.md）。"""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._title = QLabel("(未选中任务)")
        self._title.setFont(QFont("", 14, QFont.Weight.Bold))
        layout.addWidget(self._title)

        self._meta = QLabel("")
        self._meta.setStyleSheet("color: gray;")
        layout.addWidget(self._meta)

        self._brief = QTextEdit()
        self._brief.setReadOnly(True)
        layout.addWidget(self._brief, stretch=1)

    def show_task(self, name: str, stage: str, path: str, brief: str) -> None:
        self._title.setText(name)
        self._meta.setText(f"stage: {stage}  ·  path: {path}")
        long_brief = self._read_long_brief(Path(path), fallback=brief)
        self._brief.setPlainText(long_brief)

    def _read_long_brief(self, task_dir: Path, fallback: str) -> str:
        """优先 需求分析.md §1，其次 HANDOFF.md，再次 SPEC.md，最后 fallback。"""
        candidates = [
            (task_dir / "需求分析.md", "## 1"),
            (task_dir / "HANDOFF.md", "## 30"),
            (task_dir / "SPEC.md", "## 1"),
            (task_dir / "REQUIREMENTS.md", "## 1"),  # 老命名兼容
            (task_dir / "DESIGN.md", "## 1"),
        ]
        for path, _section_hint in candidates:
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    return text[:8000]
                except OSError:
                    continue
        return fallback or "(无简介)"


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

    @Slot(int)
    def switch_to_tab(self, tab_idx: int) -> None:
        # tab idx 7（任务页）→ TaskBrief；其他 → Decision
        # 实际任务卡点击会走 show_task() 主动切换；此处只在 tab 切走时回到 Decision
        if tab_idx != 7:
            self._stack.setCurrentIndex(int(PageId.DECISION))

    def set_decision(self, decision: dict) -> None:
        self._decision.set_decision(decision)
        self._stack.setCurrentIndex(int(PageId.DECISION))

    def set_cards(self, cards: list[dict]) -> None:
        self._decision.set_cards(cards)

    def show_task(self, name: str, stage: str, path: str, brief: str) -> None:
        self._task_brief.show_task(name, stage, path, brief)
        self._stack.setCurrentIndex(int(PageId.TASK_BRIEF))
