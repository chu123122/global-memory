"""JSONL 增量轮询服务。

设计 §3.1 通道清单：
  - control_panel_events.jsonl   2s  主线程
  - tool_audit.jsonl             5s  主线程
  - task_outcomes.jsonl          2s  主线程（4-B reader 就绪后接入）
  - git status                  10s  QThread

设计 §3.2：panel_api.append_event 是裸 append 无锁，存在半行风险，read_incremental
必须做半行回退（末尾不以 \n 结尾的行整段丢弃，不前进 offset）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

EVENT_LOG = Path.home() / ".claude" / "logs" / "control_panel_events.jsonl"
AUDIT_LOG = Path.home() / ".claude" / "logs" / "tool_audit.jsonl"
OUTCOME_LOG = Path.home() / ".claude" / "logs" / "task_outcomes.jsonl"

EVENT_POLL_MS = 2_000
AUDIT_POLL_MS = 5_000
OUTCOME_POLL_MS = 2_000


@dataclass
class _ChannelState:
    path: Path
    offset: int = 0
    initialized: bool = False


def read_incremental(path: Path, last_offset: int) -> tuple[list[dict], int]:
    """读取 path 从 last_offset 起的新行，半行回退。

    返回 (events, new_offset)。
    - 半行（末尾无 \n）→ 不前进 offset 到该行，等下一轮重读
    - 单行 JSONDecodeError → 跳过该行但 offset 推进（避免死循环）
    - 文件被截断（size < last_offset）→ reset 到 0 重读
    """
    if not path.exists():
        return [], last_offset

    size = path.stat().st_size
    if size < last_offset:
        last_offset = 0  # 文件 rotate / 截断

    if size == last_offset:
        return [], last_offset

    new_events: list[dict] = []
    with path.open("rb") as f:
        f.seek(last_offset)
        chunk_bytes = f.read()

    try:
        chunk = chunk_bytes.decode("utf-8")
    except UnicodeDecodeError:
        chunk = chunk_bytes.decode("utf-8", errors="replace")

    lines = chunk.split("\n")
    has_trailing_newline = chunk.endswith("\n")
    if has_trailing_newline:
        # split('\n') 在以 \n 结尾时末尾会多出一个空串，丢掉它
        lines = lines[:-1]
    else:
        # 最后一行不以 \n 结尾视为半行，整段丢弃，offset 不推进到这里
        lines = lines[:-1]

    consumed_bytes = 0
    for line in lines:
        line_bytes = len(line.encode("utf-8"))
        if line.strip():
            try:
                new_events.append(json.loads(line))
            except json.JSONDecodeError:
                # 跳过损坏行，offset 仍推进，避免死循环
                pass
        consumed_bytes += line_bytes + 1  # +1 for the \n that terminated this line

    return new_events, last_offset + consumed_bytes


class PollingService(QObject):
    """三通道 JSONL 轮询。

    Signal:
      event_received(dict)    每条 control_panel_events.jsonl 新事件
      audit_received(dict)    每条 tool_audit.jsonl 新条目
      outcome_received(dict)  每条 task_outcomes.jsonl 新条目
    """

    event_received = Signal(dict)
    audit_received = Signal(dict)
    outcome_received = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._events = _ChannelState(EVENT_LOG)
        self._audit = _ChannelState(AUDIT_LOG)
        self._outcomes = _ChannelState(OUTCOME_LOG)

        self._event_timer = QTimer(self)
        self._event_timer.timeout.connect(self._poll_events)
        self._audit_timer = QTimer(self)
        self._audit_timer.timeout.connect(self._poll_audit)
        self._outcome_timer = QTimer(self)
        self._outcome_timer.timeout.connect(self._poll_outcomes)

    def start(self) -> None:
        # 初次启动：跳到文件末尾，避免历史回放
        for state in (self._events, self._audit, self._outcomes):
            if state.path.exists():
                # 回退 64KB 给"最近事件"显示一定上下文（v1 行为对齐）
                size = state.path.stat().st_size
                state.offset = max(0, size - 64_000)
            state.initialized = True

        self._event_timer.start(EVENT_POLL_MS)
        self._audit_timer.start(AUDIT_POLL_MS)
        self._outcome_timer.start(OUTCOME_POLL_MS)

        # 立即拉一次，让 UI 启动后看到最近事件
        self._poll_events()
        self._poll_audit()
        self._poll_outcomes()

    def stop(self) -> None:
        self._event_timer.stop()
        self._audit_timer.stop()
        self._outcome_timer.stop()

    def _poll_events(self) -> None:
        events, new_offset = read_incremental(self._events.path, self._events.offset)
        self._events.offset = new_offset
        for ev in events:
            self.event_received.emit(ev)

    def _poll_audit(self) -> None:
        events, new_offset = read_incremental(self._audit.path, self._audit.offset)
        self._audit.offset = new_offset
        for ev in events:
            self.audit_received.emit(ev)

    def _poll_outcomes(self) -> None:
        events, new_offset = read_incremental(self._outcomes.path, self._outcomes.offset)
        self._outcomes.offset = new_offset
        for ev in events:
            self.outcome_received.emit(ev)
