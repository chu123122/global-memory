"""状态页（v2.1 合并 v2.0 overview/doctor/guard）：

一屏告诉用户"现在体系运转怎么样 + 有问题点一下修复"：
  - GitCard：dirty/ahead/behind/变更数（来源 maintain.py status --json）
  - DaemonCard：守护进程状态（同上）
  - DoctorCard：最近自动修复 PASS/WARN/ERROR
  - 一键修复按钮：异步跑 maintain.py fix --json，按钮 spinner，完成刷 DoctorCard
"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ._base import _BasePage
from .components import section_card

CHECK_LABELS = {
    "git_status": "Git 状态",
    "check_health": "记忆健康",
    "bootstrap_check": "部署检查",
    "verify_prompt_system": "Prompt 系统",
    "verify_docs": "文档一致性",
    "smoke_test": "冒烟测试",
}


class StatusPage(_BasePage):
    title = "状态"
    subtitle = "Git / Daemon / 最近修复一屏速览；点[一键修复]后台跑 maintain.py fix。"
    page_id = "status"

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._git_label: QLabel | None = None
        self._daemon_label: QLabel | None = None
        self._doctor_label: QLabel | None = None
        self._doctor_detail: dict[str, QLabel] = {}
        self._fix_btn: QPushButton | None = None
        self._refresh_btn: QPushButton | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        self._fix_running = False
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # 顶部动作条
        toolbar = QHBoxLayout()
        self._fix_btn = QPushButton(qta.icon("fa5s.wrench"), "一键修复")
        self._fix_btn.setProperty("role", "primary")
        self._fix_btn.clicked.connect(self._on_fix_clicked)
        toolbar.addWidget(self._fix_btn)
        self._icon_buttons.append((self._fix_btn, "fa5s.wrench"))

        toolbar.addStretch(1)

        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新")
        self._refresh_btn.setProperty("role", "secondary")
        self._refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))
        layout.addLayout(toolbar)

        # Git 卡片
        git = section_card(layout, "Git", "工作树脏污 / ahead / behind / 变更文件数")
        self._git_label = QLabel("Git：未知")
        self._git_label.setWordWrap(True)
        git.layout().addWidget(self._git_label)

        # Daemon 卡片
        daemon = section_card(layout, "Daemon", "auto_sync 守护进程：负责空闲触发同步")
        self._daemon_label = QLabel("Daemon：未知")
        self._daemon_label.setWordWrap(True)
        daemon.layout().addWidget(self._daemon_label)

        # Doctor 卡片
        doctor = section_card(layout, "最近自动修复", "maintain.py status 携带的最近一次 doctor 摘要 + 各分项状态")
        self._doctor_label = QLabel("最近修复：未知")
        self._doctor_label.setWordWrap(True)
        doctor.layout().addWidget(self._doctor_label)
        for key, label in CHECK_LABELS.items():
            lbl = QLabel(f"{label}：未知")
            lbl.setWordWrap(True)
            doctor.layout().addWidget(lbl)
            self._doctor_detail[key] = lbl

    # -------- 行为 --------
    def _on_refresh(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="状态刷新",
            cmd=self._main.py_cmd("maintain.py", "status", "--json"),
            parse_json=True,
            extras={"action": "status"},
        )

    def _on_fix_clicked(self) -> None:
        if self._fix_running:
            return
        self._fix_running = True
        if self._fix_btn:
            self._fix_btn.setEnabled(False)
            self._fix_btn.setText("修复中...")
            self._fix_btn.setIcon(qta.icon("fa5s.spinner"))
        self._main.submit_cmd(
            page=self.page_id,
            title="一键修复",
            cmd=self._main.py_cmd("maintain.py", "fix", "--json"),
            parse_json=True,
            extras={"action": "fix"},
        )

    def refresh(self) -> None:
        self._on_refresh()

    # -------- 结果 --------
    @Slot(object)
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        data = result.json
        if action == "status" and isinstance(data, dict):
            self._update_status_cards(data)
        elif action == "fix":
            self._on_fix_done(result)

    def _update_status_cards(self, data: dict) -> None:
        git = data.get("git", {}) or {}
        daemon = data.get("daemon", {}) or {}
        if self._git_label:
            self._git_label.setText(
                f"dirty={git.get('dirty')} / ahead={git.get('ahead')} / "
                f"behind={git.get('behind')} / 变更 {git.get('change_count')}"
            )
        if self._daemon_label:
            self._daemon_label.setText(
                f"running={daemon.get('running')} / processes={daemon.get('process_count')}"
            )
        # 最近修复来自 logs.maintain_tail 中类型为 doctor 的最后一条
        logs = (data.get("logs", {}) or {}).get("maintain_tail", []) or []
        latest_doctor: dict | None = None
        for item in reversed(logs):
            if isinstance(item, dict) and item.get("type") == "doctor":
                latest_doctor = item
                break
        if latest_doctor and self._doctor_label:
            summary = latest_doctor.get("summary") or {}
            self._doctor_label.setText(
                f"PASS {summary.get('PASS', 0)} / WARN {summary.get('WARNING', 0)} / "
                f"ERROR {summary.get('ERROR', 0)}（{latest_doctor.get('ts', '')}）"
            )

    def _on_fix_done(self, result) -> None:
        self._fix_running = False
        if self._fix_btn:
            self._fix_btn.setEnabled(True)
            self._fix_btn.setText("一键修复")
            self._fix_btn.setIcon(qta.icon("fa5s.wrench"))

        data = result.json
        if isinstance(data, dict):
            summary = data.get("summary", {}) or {}
            text = (
                f"刚跑：PASS {summary.get('PASS', 0)} / WARN {summary.get('WARNING', 0)} / "
                f"ERROR {summary.get('ERROR', 0)} · changed={data.get('changed')}"
            )
            if self._doctor_label:
                self._doctor_label.setText(text)
            for item in data.get("results", []) or []:
                if not isinstance(item, dict):
                    continue
                key = item.get("id")
                if key in self._doctor_detail:
                    self._doctor_detail[key].setText(
                        f"{CHECK_LABELS[key]}：{item.get('level')} - {item.get('summary')}"
                    )
            self._main.append_debug(
                f"\n# 一键修复 exit={result.returncode}\nsummary={summary} changed={data.get('changed')}\n",
                reveal=False,
            )
        else:
            if self._doctor_label:
                self._doctor_label.setText(f"修复退出码 {result.returncode}（详见调试输出）")
            self._main.append_debug(
                f"\n# 一键修复失败 exit={result.returncode}\n[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n",
                reveal=True,
            )
        # 强制再拉一次状态，把 logs.maintain_tail 中新生成的 doctor 条目刷进来
        self._on_refresh()

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
