"""问题闭环页（D3 新建，feedback-loop-v1 V1）：

设计文档：D:/ClaudeTasks/active/feedback-loop-v1/设计文档.md §7
SPEC：V6 验收（3 桶 + 纯只读 + 无任何动作按钮）

数据流：
  ~/.claude/logs/issues.jsonl（issue_tracker 写）
    → 按 issue_id 聚合到 last event
    → 分到 3 桶（待你处理 / 自动处理中 / 已处理）

UI 原则（Q7 锁定）：
  - 纯只读 dashboard，无任何动作按钮
  - 所有 transition 走 CLI（用户复制粘贴到终端）
  - 每张卡片显示"建议下一步 CLI"，用户复制即可
  - 点击卡片展开 evidence + history events 时间轴

3 桶：
  - 待你处理（detected + reopened）：主区，每条卡片完全展开
  - 自动处理中（fixing）：V1 几乎为空，预留位置
  - 已处理（fixed + archived）：默认折叠，"X 项已处理 ▸"
"""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt
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

# 复用 issue_tracker 的数据加载逻辑（不动 model 层）
_HARNESS_DIR = Path(__file__).resolve().parent.parent.parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))
from issue_tracker import (  # noqa: E402
    DEFAULT_ISSUES_PATH,
    _last_event_by_id,
    _last_record_by_id,
)

# 状态 → 桶映射
_BUCKET_ACTIVE = {"detected", "reopened"}
_BUCKET_FIXING = {"fixing"}
_BUCKET_DONE = {"fixed", "archived"}

# severity → unicode 字符（与状态页/health 页统一）
_SEV_GLYPH = {
    "critical": "✕",
    "error": "✕",
    "warning": "⚠",
    "info": "●",
    "ok": "●",
}
_SEV_TO_PROPERTY = {
    "critical": "error",
    "error": "error",
    "warning": "warning",
    "info": "info",
    "ok": "ok",
}


class IssueLoopPage(_BasePage):
    title = "问题闭环"
    subtitle = "issue_tracker 维护的问题生命周期；纯只读，所有操作走 CLI"
    page_id = "issue_loop"
    auto_refresh_interval_sec = 30.0

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._summary_label: QLabel | None = None
        self._refresh_btn: QPushButton | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []

        # 3 个桶的容器 + toggle
        self._bucket_active_box: QFrame | None = None
        self._bucket_active_toggle: QToolButton | None = None
        self._bucket_fixing_box: QFrame | None = None
        self._bucket_fixing_toggle: QToolButton | None = None
        self._bucket_done_box: QFrame | None = None
        self._bucket_done_toggle: QToolButton | None = None

        # diff 复用：issue_id → 卡 QFrame（按桶分开）
        self._cards_active: dict[str, QFrame] = {}
        self._cards_fixing: dict[str, QFrame] = {}
        self._cards_done: dict[str, QFrame] = {}

        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # 顶部：汇总 + 刷新
        toolbar = QHBoxLayout()
        self._summary_label = QLabel("加载中...")
        self._summary_label.setWordWrap(True)
        toolbar.addWidget(self._summary_label, stretch=1)

        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        self._refresh_btn.setProperty("role", "secondary")
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))
        layout.addLayout(toolbar)

        # 桶 1：待你处理（detected + reopened）—— 默认展开
        (
            self._bucket_active_toggle,
            self._bucket_active_box,
        ) = self._make_bucket(layout, "待你处理", "fa5s.exclamation-circle", default_open=True)

        # 桶 2：自动处理中（fixing）—— V1 几乎为空
        (
            self._bucket_fixing_toggle,
            self._bucket_fixing_box,
        ) = self._make_bucket(layout, "自动处理中", "fa5s.cog", default_open=False)

        # 桶 3：已处理（fixed + archived）—— 默认折叠
        (
            self._bucket_done_toggle,
            self._bucket_done_box,
        ) = self._make_bucket(layout, "已处理", "fa5s.check-circle", default_open=False)

    def _make_bucket(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        icon_name: str,
        default_open: bool,
    ) -> tuple[QToolButton, QFrame]:
        toggle = QToolButton()
        toggle.setCheckable(True)
        toggle.setChecked(default_open)
        toggle.setText(f"{title} (...)")
        toggle.setIcon(
            qta.icon("fa5s.chevron-down" if default_open else "fa5s.chevron-right")
        )
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setAutoRaise(True)
        toggle.setObjectName(f"bucket-toggle-{title}")
        parent_layout.addWidget(toggle)
        self._icon_buttons.append((toggle, "fa5s.chevron-down" if default_open else "fa5s.chevron-right"))

        box = QFrame()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(8)
        box.setVisible(default_open)
        parent_layout.addWidget(box)

        toggle.toggled.connect(lambda checked, b=box, t=toggle: self._on_bucket_toggled(checked, b, t))
        return toggle, box

    def _on_bucket_toggled(self, checked: bool, box: QFrame, toggle: QToolButton) -> None:
        box.setVisible(checked)
        icon = "fa5s.chevron-down" if checked else "fa5s.chevron-right"
        toggle.setIcon(qta.icon(icon))
        # 同步 _icon_buttons 记忆
        for i, (btn, _) in enumerate(self._icon_buttons):
            if btn is toggle:
                self._icon_buttons[i] = (btn, icon)
                break

    # -------- 行为 --------
    def refresh(self) -> None:
        """直接读 issues.jsonl 渲染（不走 submit_cmd 异步——文件读取很轻）。"""
        records = self._load_records()
        buckets = self._aggregate(records)
        self._render(buckets)

    def _load_records(self) -> dict[str, dict]:
        """读 issues.jsonl，按 issue_id 取最后一条完整记录。"""
        return _last_record_by_id(DEFAULT_ISSUES_PATH)

    def _aggregate(self, records: dict[str, dict]) -> dict[str, list[dict]]:
        """按 last event 分到 3 桶。每个 record 带上 last_event 字段。"""
        last_events = _last_event_by_id(DEFAULT_ISSUES_PATH)
        active: list[dict] = []
        fixing: list[dict] = []
        done: list[dict] = []
        for iid, rec in records.items():
            ev = last_events.get(iid, "detected")
            r = dict(rec)
            r["_last_event"] = ev
            if ev in _BUCKET_ACTIVE:
                active.append(r)
            elif ev in _BUCKET_FIXING:
                fixing.append(r)
            elif ev in _BUCKET_DONE:
                done.append(r)
        # 按 severity 排序（critical 在前）
        sev_order = {"critical": 0, "error": 0, "warning": 1, "info": 2, "ok": 3}
        for arr in (active, fixing, done):
            arr.sort(key=lambda r: (sev_order.get(r.get("severity", "info"), 9), r.get("issue_id", "")))
        return {"active": active, "fixing": fixing, "done": done}

    def _render(self, buckets: dict[str, list[dict]]) -> None:
        active = buckets["active"]
        fixing = buckets["fixing"]
        done = buckets["done"]

        # 顶部汇总
        if self._summary_label:
            crit = sum(1 for r in active if r.get("severity") in ("critical", "error"))
            warn = sum(1 for r in active if r.get("severity") == "warning")
            info = sum(1 for r in active if r.get("severity") == "info")
            self._summary_label.setText(
                f"待处理 {len(active)}（"
                f"<span style='color:#b94a3a'>✕ {crit}</span> · "
                f"<span style='color:#c8a165'>⚠ {warn}</span> · "
                f"<span style='color:#7b9bb5'>● {info}</span>）"
                f" · 自动处理中 {len(fixing)} · 已处理 {len(done)}"
            )

        # 更新 toggle 文字（含计数）
        if self._bucket_active_toggle:
            self._bucket_active_toggle.setText(f"待你处理 ({len(active)})")
        if self._bucket_fixing_toggle:
            self._bucket_fixing_toggle.setText(f"自动处理中 ({len(fixing)})")
        if self._bucket_done_toggle:
            self._bucket_done_toggle.setText(f"已处理 ({len(done)})")

        # 渲染 3 桶
        self._render_bucket(self._bucket_active_box, self._cards_active, active, compact=False)
        self._render_bucket(self._bucket_fixing_box, self._cards_fixing, fixing, compact=False)
        self._render_bucket(self._bucket_done_box, self._cards_done, done, compact=True)

    def _render_bucket(
        self,
        box: QFrame | None,
        cache: dict[str, QFrame],
        records: list[dict],
        *,
        compact: bool,
    ) -> None:
        """diff 复用 widget：seen 的 show + update，未 seen 的 hide。"""
        if box is None:
            return
        if not records:
            # 空桶时显示一行提示
            self._set_empty_message(box, cache, compact)
            return
        else:
            # 删 empty 占位（如有）
            self._clear_empty_message(box, cache)

        seen: set[str] = set()
        for rec in records:
            iid = rec.get("issue_id", "")
            if not iid:
                continue
            seen.add(iid)
            card = cache.get(iid)
            if card is None:
                card = self._build_card(compact=compact)
                box.layout().addWidget(card)
                cache[iid] = card
            card.show()
            self._update_card(card, rec)

        for iid, card in cache.items():
            if iid not in seen and not iid.startswith("__empty__"):
                card.hide()

    def _set_empty_message(self, box: QFrame, cache: dict[str, QFrame], compact: bool) -> None:
        """空桶时显示一行 muted 提示。用 cache key '__empty__' 复用。"""
        existing = cache.get("__empty__")
        if existing is not None:
            existing.show()
            return
        # 隐藏其他卡（之前可能有数据）
        for k, c in cache.items():
            if k != "__empty__":
                c.hide()
        empty_card = QFrame()
        empty_layout = QVBoxLayout(empty_card)
        empty_layout.setContentsMargins(14, 8, 14, 8)
        msg = QLabel("（空）")
        msg.setObjectName("muted")
        empty_layout.addWidget(msg)
        box.layout().addWidget(empty_card)
        cache["__empty__"] = empty_card

    def _clear_empty_message(self, box: QFrame, cache: dict[str, QFrame]) -> None:
        empty = cache.get("__empty__")
        if empty is not None:
            empty.hide()

    def _build_card(self, compact: bool = False) -> QFrame:
        """单张 issue 卡片。复用 subsystem-cell 视觉体系。"""
        card = QFrame()
        card.setObjectName("subsystem-cell")
        card.setProperty("severity", "info")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 10 if compact else 12, 14, 10 if compact else 12)
        v.setSpacing(4)

        title_label = QLabel("")
        title_label.setObjectName("subsys-name")
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setWordWrap(True)
        v.addWidget(title_label)

        headline_label = QLabel("")
        headline_label.setObjectName("subsys-summary")
        headline_label.setWordWrap(True)
        v.addWidget(headline_label)

        hint_label = QLabel("")
        hint_label.setObjectName("muted")
        hint_label.setTextFormat(Qt.TextFormat.RichText)
        hint_label.setWordWrap(True)
        hint_label.setVisible(not compact)
        v.addWidget(hint_label)

        cli_label = QLabel("")
        cli_label.setObjectName("issue-card-cli")
        cli_label.setTextFormat(Qt.TextFormat.RichText)
        cli_label.setWordWrap(True)
        cli_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cli_label.setVisible(not compact)
        v.addWidget(cli_label)

        # 引用挂卡上方便 _update_card 拿
        card._title = title_label
        card._headline = headline_label
        card._hint = hint_label
        card._cli = cli_label
        card._compact = compact
        return card

    def _update_card(self, card: QFrame, rec: dict) -> None:
        sev = str(rec.get("severity", "info"))
        glyph = _SEV_GLYPH.get(sev, "·")
        sev_property = _SEV_TO_PROPERTY.get(sev, "info")
        card.setProperty("severity", sev_property)
        card.style().unpolish(card)
        card.style().polish(card)

        iid = str(rec.get("issue_id", ""))
        last_event = str(rec.get("_last_event", "detected"))
        ts_short = self._short_ts(rec.get("ts", ""))
        # 头：glyph severity · check_id 末段 · last_event ts
        check_id_short = iid.split(".", 2)[1] if iid.count(".") >= 2 else iid
        title_html = (
            f"<b>{glyph} {sev}</b> · "
            f"<span style='color:#7a6e5e'>{escape(check_id_short)}</span> · "
            f"<span style='color:#9a8c7a'>{escape(last_event)} {escape(ts_short)}</span>"
        )
        card._title.setText(title_html)

        card._headline.setText(escape(str(rec.get("title", ""))))

        if not getattr(card, "_compact", False):
            fix_hint = str(rec.get("fix_hint") or "")
            if fix_hint:
                card._hint.setText(f"↳ {escape(fix_hint)}")
                card._hint.setVisible(True)
            else:
                card._hint.setVisible(False)

            # 建议 CLI：用户复制粘贴到终端
            cli = self._suggest_cli(iid, last_event)
            if cli:
                card._cli.setText(
                    f"<span style='color:#7a6e5e;font-size:10pt'>→ 终端跑：</span>"
                    f"<span style='font-family: \"Cascadia Mono\", monospace;"
                    f" background: rgba(196,123,107,0.10); padding: 2px 6px;"
                    f" border-radius: 2px;'>{escape(cli)}</span>"
                )
                card._cli.setVisible(True)
            else:
                card._cli.setVisible(False)

    @staticmethod
    def _suggest_cli(issue_id: str, last_event: str) -> str:
        """每张卡只给一个最有用的 CLI（"每个状态只给一个最明显主操作"原则）。"""
        if last_event in ("detected", "reopened", "fixing"):
            # 提示：手动归档（认为不痛 / 已修过）
            return f'python -m harness.issue_tracker --archive {issue_id} --note "..."'
        if last_event == "fixed":
            # 已自动 fixed，可手动 archive 沉淀
            return f'python -m harness.issue_tracker --archive {issue_id}'
        if last_event == "archived":
            # 如果发现又出现，可手动 reopen
            return f'python -m harness.issue_tracker --reopen {issue_id}'
        return ""

    @staticmethod
    def _short_ts(ts: str) -> str:
        """ISO 时间戳 → MM-DD HH:MM。"""
        ts = str(ts)
        if len(ts) >= 16 and ts[4] == "-" and ts[7] == "-":
            return ts[5:10] + " " + ts[11:16]
        return ts[:16]

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, name in self._icon_buttons:
            btn.setIcon(qta.icon(name))
