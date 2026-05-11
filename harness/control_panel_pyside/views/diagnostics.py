"""诊断页（A2 新增，UX-REVIEW Top 2）：

把原 status.py 的 AI 时间线卡 + 5 个开发者按钮整段搬到独立页，避免：
  - 状态页 358 行装 5 个不同关注点
  - 首屏结论卡被 token saver 子问题劫持（D1，已由 A1 model 层切断）
  - "跑 /work pack / Skill audit / 记录 outcome" 这些开发者诊断动作占主面板

这页专给开发者诊断 harness 自身（token saver 接入证据、最近会话、outcome ledger）。
不参与"当前结论"——结论的数据源由 overview_verdict.build_overview_verdict 收口。
"""
from __future__ import annotations

from html import escape

import qtawesome as qta
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from ._base import _BasePage


class DiagnosticsPage(_BasePage):
    title = "诊断"
    subtitle = "AI 时间线 / 工具接入证据 / outcome ledger（开发者诊断材料，日常不需要看）"
    page_id = "diagnostics"
    auto_refresh_interval_sec = 60.0  # 不是日常 ritual，不必频繁刷

    def __init__(self, main_window) -> None:
        self._main = main_window
        self._timeline_view: QTextBrowser | None = None
        self._refresh_btn: QPushButton | None = None
        self._full_btn: QPushButton | None = None
        self._pack_btn: QPushButton | None = None
        self._audit_btn: QPushButton | None = None
        self._outcome_btn: QPushButton | None = None
        self._icon_buttons: list[tuple[QPushButton, str]] = []
        super().__init__()

    def _build_content(self, layout: QVBoxLayout) -> None:
        # Day 3：「刷新时间线」单独一行突出（其他 4 个按钮分组到下一行作 secondary 用途）
        primary_row = QHBoxLayout()
        self._refresh_btn = QPushButton(qta.icon("fa5s.sync"), "刷新时间线")
        self._refresh_btn.setProperty("role", "primary")
        self._refresh_btn.clicked.connect(self._on_refresh)
        primary_row.addWidget(self._refresh_btn)
        self._icon_buttons.append((self._refresh_btn, "fa5s.sync"))
        primary_row.addStretch(1)
        layout.addLayout(primary_row)

        # 次级开发者动作组
        secondary_row = QHBoxLayout()
        self._full_btn = QPushButton(qta.icon("fa5s.list-alt"), "完整会话")
        self._full_btn.setProperty("role", "secondary")
        self._full_btn.clicked.connect(self._on_full_clicked)
        secondary_row.addWidget(self._full_btn)
        self._icon_buttons.append((self._full_btn, "fa5s.list-alt"))

        self._pack_btn = QPushButton(qta.icon("fa5s.box-open"), "跑 /work pack")
        self._pack_btn.setProperty("role", "secondary")
        self._pack_btn.clicked.connect(self._on_work_pack_clicked)
        secondary_row.addWidget(self._pack_btn)
        self._icon_buttons.append((self._pack_btn, "fa5s.box-open"))

        self._audit_btn = QPushButton(qta.icon("fa5s.clipboard-check"), "跑 Skill audit")
        self._audit_btn.setProperty("role", "secondary")
        self._audit_btn.clicked.connect(self._on_skill_audit_clicked)
        secondary_row.addWidget(self._audit_btn)
        self._icon_buttons.append((self._audit_btn, "fa5s.clipboard-check"))

        self._outcome_btn = QPushButton(qta.icon("fa5s.plus-circle"), "记录 outcome")
        self._outcome_btn.setProperty("role", "secondary")
        self._outcome_btn.clicked.connect(self._on_outcome_clicked)
        secondary_row.addWidget(self._outcome_btn)
        self._icon_buttons.append((self._outcome_btn, "fa5s.plus-circle"))

        # D4 兜底：「问题闭环」tab 取代了健康 tab，9 项原始 signal 入口移这里
        self._health_btn = QPushButton(qta.icon("fa5s.heartbeat"), "跑健康检测")
        self._health_btn.setProperty("role", "secondary")
        self._health_btn.setToolTip("运行 harness.health.runner 看 9 项原始 signal（结果输出到调试区）")
        self._health_btn.clicked.connect(self._on_health_clicked)
        secondary_row.addWidget(self._health_btn)
        self._icon_buttons.append((self._health_btn, "fa5s.heartbeat"))

        secondary_row.addStretch(1)
        layout.addLayout(secondary_row)

        self._timeline_view = QTextBrowser()
        self._timeline_view.setObjectName("timeline-reader")
        self._timeline_view.setOpenExternalLinks(False)
        self._timeline_view.setMinimumHeight(420)
        self._timeline_view.setHtml(
            "<h3>未刷新</h3><p>点击「刷新时间线」后显示最近 AI 会话、工具接入证据、最近 outcome。</p>"
        )
        layout.addWidget(self._timeline_view)

    # -------- 行为 --------
    def refresh(self) -> None:
        self._on_refresh()

    def _on_refresh(self) -> None:
        if self._timeline_view:
            self._timeline_view.setHtml("<h3>刷新中...</h3><p>正在读取 audit / outcome 日志。</p>")
        self._main.submit_cmd(
            page=self.page_id,
            title="AI 时间线刷新",
            cmd=self._main.py_cmd("timeline_summary.py", "--json", "--days", "7"),
            parse_json=True,
            extras={"action": "timeline"},
        )

    def _on_full_clicked(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="最近完整 AI 会话",
            cmd=self._main.py_cmd("session_report.py", "--last"),
            parse_json=False,
            extras={"action": "timeline_full"},
        )

    def _on_work_pack_clicked(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="/work context pack",
            cmd=self._main.py_cmd("work_context_pack.py", "--task", "control-panel-v2-pyside", "--json"),
            parse_json=True,
            extras={"action": "timeline_work_pack"},
        )

    def _on_skill_audit_clicked(self) -> None:
        self._main.submit_cmd(
            page=self.page_id,
            title="Skill audit",
            cmd=self._main.py_cmd("audit_skill.py", "--all", "--json"),
            parse_json=True,
            extras={"action": "timeline_skill_audit"},
        )

    def _on_health_clicked(self) -> None:
        py = self._main.py_cmd("dummy.py")[0]
        cmd = [py, "-m", "harness.health.runner", "--json", "--no-log"]
        self._main.submit_cmd(
            page=self.page_id,
            title="健康 9 项 signal",
            cmd=cmd,
            parse_json=True,
            extras={"action": "health_runner"},
        )

    def _on_outcome_clicked(self) -> None:
        task, ok = QInputDialog.getText(self, "记录 outcome", "任务名：", text="control-panel-v2-pyside")
        if not ok or not task.strip():
            return
        outcome, ok = QInputDialog.getItem(
            self,
            "记录 outcome",
            "结果：",
            ["completed", "partial", "blocked", "abandoned"],
            0,
            False,
        )
        if not ok:
            return
        lesson, ok = QInputDialog.getText(self, "记录 outcome", "一句教训 / 说明（可空）：")
        if not ok:
            return
        self._main.submit_cmd(
            page=self.page_id,
            title="记录 outcome",
            cmd=self._main.py_cmd(
                "panel_api.py",
                "outcome",
                "--task",
                task.strip(),
                "--phase",
                "manual",
                "--outcome",
                outcome,
                "--lesson",
                lesson.strip(),
                "--json",
            ),
            parse_json=True,
            extras={"action": "outcome_write"},
        )

    # -------- 结果 --------
    def handle_result(self, result) -> None:
        action = result.extras.get("action")
        data = result.json
        if action == "timeline":
            if isinstance(data, dict):
                self._update_timeline_card(data)
            else:
                if self._timeline_view:
                    self._timeline_view.setHtml(
                        f"<h3>刷新失败</h3><p>timeline_summary.py exit={result.returncode}</p>"
                    )
                self._main.append_debug(
                    f"\n# AI 时间线刷新失败 exit={result.returncode}\n"
                    f"[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n",
                    reveal=True,
                )
        elif action == "timeline_full":
            output = result.stdout.strip() or "(无输出)"
            if result.stderr.strip():
                output += f"\n\n[stderr]\n{result.stderr.strip()}"
            self._main.append_debug(f"\n# 最近完整 AI 会话\n{output}\n", reveal=True)
        elif action in {"timeline_work_pack", "timeline_skill_audit"}:
            label = "/work context pack" if action == "timeline_work_pack" else "Skill audit"
            self._main.append_debug(
                f"\n# {label} exit={result.returncode}\n[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n",
                reveal=True,
            )
            self._on_refresh()
        elif action == "health_runner":
            # D4 兜底：把 9 项 signal 完整 dump 到调试区
            if isinstance(data, dict):
                signals = data.get("signals", []) or []
                lines = [f"\n# 健康 9 项 signal（共 {len(signals)} 条）"]
                for s in signals:
                    if not isinstance(s, dict):
                        continue
                    lines.append(
                        f"  [{s.get('status','?'):>8}] {s.get('check_id','?')}"
                        f" · {s.get('headline','')}"
                    )
                    if s.get("fix_hint"):
                        lines.append(f"           ↳ {s.get('fix_hint')}")
                self._main.append_debug("\n".join(lines) + "\n", reveal=True)
            else:
                self._main.append_debug(
                    f"\n# 健康检测 exit={result.returncode}\n"
                    f"[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n",
                    reveal=True,
                )
        elif action == "outcome_write":
            self._main.append_debug(
                f"\n# outcome 写入 exit={result.returncode}\n[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}\n",
                reveal=False,
            )
            self._on_refresh()

    # -------- 渲染（从 status.py 整段搬来，无业务变化） --------
    def _update_timeline_card(self, data: dict) -> None:
        """与原 status.py:_update_timeline_card 等价，但**不再调 _set_decision**。

        verdict 由 overview_verdict.build_overview_verdict 在状态页内独立计算，
        诊断页只渲染数据，不参与结论。
        """
        if not self._timeline_view:
            return

        session = data.get("latest_session")
        usage = (data.get("tracked_tool_usage") or {}).get("tools") or {}
        outcomes = data.get("latest_outcomes") or []
        recommendations = data.get("recommendations") or []

        work = usage.get("work_context_pack.py") or {}
        audit = usage.get("audit_skill.py") or {}
        work_ai = work.get("audit_recent_count", work.get("recent_count", 0))
        audit_ai = audit.get("audit_recent_count", audit.get("recent_count", 0))
        work_script = work.get("invocation_recent_count", 0)
        audit_script = audit.get("invocation_recent_count", 0)
        # verdict 仅作"诊断材料"展示，不再回写主面板结论卡
        if work_ai == 0 and audit_ai == 0 and work_script == 0 and audit_script == 0:
            verdict = "未解决：token saver / skill audit 还没有运行证据"
            verdict_class = "bad"
        elif work_ai == 0 and audit_ai == 0:
            verdict = "部分解决：脚本可运行，但还没有 AI 工作流直接调用证据"
            verdict_class = "warn"
        else:
            verdict = "部分解决：已有 AI 直接调用证据，继续观察是否稳定复用"
            verdict_class = "warn"

        if isinstance(session, dict):
            top_tools = ", ".join(
                f"{escape(str(name))}:{count}" for name, count in list((session.get("tool_counts") or {}).items())[:4]
            ) or "-"
            session_html = (
                f"<b>{escape(str(session.get('session', ''))[:12])}</b>"
                f"<span class='muted'> {escape(self._short_ts(session.get('start')))}"
                f" -> {escape(self._short_ts(session.get('end')))}</span>"
                f"<br>{session.get('tool_calls', 0)} calls · {escape(self._format_duration(session.get('duration_sec')))}"
                f" · {top_tools}"
            )
        else:
            session_html = "<span class='muted'>暂无 audit 记录</span>"

        tool_rows = []
        tool_specs = (
            ("work_context_pack.py", "/work 上下文打包", "/work 还没有实际省上下文证据"),
            ("audit_skill.py", "Skill 审计", "仍像设计文档，不像日常习惯"),
            ("check_prepare.py", "/check 预检", "有预检证据，但样本很少"),
            ("session_report.py", "会话报告", "按钮已接入面板；audit 里仍不是近期习惯"),
            ("outcomes_reader.py", "Outcome ledger", "偏维护/提交展示，不等于日常复盘"),
        )
        for script, label, meaning in tool_specs:
            item = usage.get(script) or {}
            status = str(item.get("status") or "unused")
            tool_rows.append(
                "<tr>"
                f"<td><b>{escape(label)}</b><br><span class='code'>{escape(script)}</span></td>"
                f"<td><span class='{self._tool_status_class(status)}'>{escape(self._tool_status_label(status))}</span></td>"
                f"<td>{item.get('audit_recent_count', item.get('recent_count', 0))}</td>"
                f"<td>{item.get('audit_total_count', item.get('total_count', 0))}</td>"
                f"<td>{item.get('invocation_recent_count', 0)}</td>"
                f"<td>{item.get('invocation_total_count', 0)}</td>"
                f"<td>{escape(self._short_ts(item.get('last_ts')))}</td>"
                f"<td class='muted'>{escape(meaning)}</td>"
                "</tr>"
            )

        if outcomes:
            outcome_rows = []
            for item in outcomes[:3]:
                task = str(item.get("task") or "(未命名任务)")
                outcome_rows.append(
                    "<tr>"
                    f"<td>{escape(self._short_ts(item.get('ts')))}</td>"
                    f"<td><b>{escape(task)}</b><br><span class='muted'>{escape(str(item.get('phase') or '-'))}</span></td>"
                    f"<td>{escape(str(item.get('outcome') or '-'))}</td>"
                    f"<td>{item.get('tool_calls', 0)}</td>"
                    "</tr>"
                )
            outcomes_html = (
                "<table><tr><th>时间</th><th>任务</th><th>结果</th><th>calls</th></tr>"
                + "".join(outcome_rows)
                + "</table>"
            )
        else:
            outcomes_html = "<p class='muted'>暂无 outcome 记录。</p>"

        note = " / ".join(str(item) for item in recommendations[:3]) if recommendations else str(
            data.get("source_note") or "只读汇总，无主动写入。"
        )
        # 与花と嵐主题对齐：暖调灰 + 赭色 verdict（Day 3 简化）
        html = f"""
        <style>
          body {{ font-family: "Noto Sans SC", "Microsoft YaHei UI", sans-serif; font-size: 11pt; line-height: 1.5; color: #2c2418; }}
          h4 {{ margin: 14px 0 6px 0; font-size: 12pt; color: #6b5d4f; font-weight: 600; }}
          table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
          th {{ text-align: left; color: #7a6e5e; font-weight: 600; border-bottom: 1px solid #d6c9b3; padding: 6px 6px; font-size: 10pt; }}
          td {{ vertical-align: top; border-bottom: 1px solid #ece3d3; padding: 7px 6px; }}
          .verdict {{ padding: 8px 12px; border-left: 3px solid #c47b6b; background: #f3ede4; margin-bottom: 12px; font-weight: 600; }}
          .bad  {{ border-left-color: #b94a3a; background: rgba(185,74,58,0.08); }}
          .warn {{ border-left-color: #c8a165; background: rgba(200,161,101,0.10); }}
          .ok   {{ border-left-color: #8baa7d; background: rgba(139,170,125,0.10); }}
          .muted {{ color: #9a8c7a; }}
          .code {{ font-family: "Cascadia Mono", "JetBrains Mono", monospace; color: #6b5d4f; }}
        </style>
        <div class="verdict {verdict_class}">{escape(verdict)}</div>
        <p class="muted">诊断材料，不参与主面板「当前结论」（结论由 git/daemon/doctor/health 聚合，见 overview_verdict.py）</p>
        <h4>最近会话</h4>
        <p>{session_html}</p>
        <h4>工具接入证据（AI 直接调用 vs 脚本自记录）</h4>
        <table>
          <tr><th>工具</th><th>状态</th><th>AI近7天</th><th>AI总计</th><th>脚本近7天</th><th>脚本总计</th><th>最近</th><th>含义</th></tr>
          {''.join(tool_rows)}
        </table>
        <h4>最近 outcome</h4>
        {outcomes_html}
        <p class="muted">说明：{escape(note)}</p>
        """
        self._timeline_view.setHtml(html)

    @staticmethod
    def _format_duration(value) -> str:
        if not isinstance(value, int) or value < 0:
            return "duration=?"
        if value < 60:
            return f"{value}s"
        if value < 3600:
            return f"{value // 60}m{value % 60:02d}s"
        return f"{value // 3600}h{(value % 3600) // 60:02d}m"

    @staticmethod
    def _tool_status_label(status: str) -> str:
        if status == "recent":
            return "AI近7天有"
        if status == "self-recent":
            return "脚本跑过"
        if status == "stale":
            return "仅旧记录"
        return "未接入"

    @staticmethod
    def _tool_status_class(status: str) -> str:
        if status == "recent":
            return "ok"
        if status == "self-recent":
            return "warn"
        if status == "stale":
            return "warn"
        return "bad"

    @staticmethod
    def _short_ts(value) -> str:
        text = str(value or "").strip()
        if not text:
            return "-"
        if len(text) >= 16 and text[4] == "-" and text[7] == "-":
            return text[5:10] + " " + text[11:16]
        return text[:16]

    def on_theme_changed(self, theme: str) -> None:  # noqa: ARG002
        for btn, icon_name in self._icon_buttons:
            btn.setIcon(qta.icon(icon_name))
