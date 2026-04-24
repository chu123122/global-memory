#!/usr/bin/env python3
"""
control_panel.py - Tkinter desktop control panel for global-memory harness.

The GUI is intentionally a thin orchestrator:
- maintenance actions call maintain.py
- AI actions call ai_runner.py
- no direct low-level script orchestration lives here
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

try:
    from .control_panel_model import (
        summarize_doctor,
        summarize_event,
        summarize_log,
        summarize_status,
        summarize_sync_preview,
    )
except ImportError:
    from control_panel_model import (
        summarize_doctor,
        summarize_event,
        summarize_log,
        summarize_status,
        summarize_sync_preview,
    )

HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = HARNESS_DIR.parent
CLAUDE_DIR = Path.home() / ".claude"
LOG_DIR = CLAUDE_DIR / "logs"
AUTO_SYNC_LOG = CLAUDE_DIR / "auto_sync.log"
PANEL_EVENTS_LOG = LOG_DIR / "control_panel_events.jsonl"
AUTO_REFRESH_MS = 10_000
EVENT_POLL_MS = 2_000

PALETTE = {
    "bg": "#EEF2F6",
    "panel": "#FFFFFF",
    "panel_soft": "#F8FAFC",
    "ink": "#132238",
    "muted": "#64748B",
    "line": "#D8E0EA",
    "brand": "#0F3D5E",
    "brand_light": "#E1F0F7",
    "accent": "#D97706",
    "danger": "#B42318",
    "ok": "#087443",
    "log_bg": "#101827",
    "log_fg": "#E8EEF7",
}

CHECK_LABELS = {
    "git_status": "Git 状态",
    "check_health": "记忆健康",
    "bootstrap_check": "部署检查",
    "verify_prompt_system": "Prompt 系统",
    "verify_docs": "文档一致性",
    "smoke_test": "冒烟测试",
}

PROVIDER_OPTIONS = {
    "Claude CLI": "claude",
    "Codex CLI（预留）": "codex",
    "API 提供方（预留）": "api",
}

MODE_OPTIONS = {
    "只读诊断": "diagnose",
    "计划生成": "plan",
}

PERMISSION_OPTIONS = {
    "计划模式": "plan",
    "默认模式": "default",
}


class CommandRunner:
    def __init__(self, app: "HarnessControlPanel") -> None:
        self.app = app
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

    def run(self, title: str, cmd: list[str], parse_json: bool = False, quiet: bool = False) -> None:
        if not quiet:
            self.app.set_busy(True, title)
        if not quiet:
            self.app.append_output(f"\n$ {' '.join(cmd)}\n")
        thread = threading.Thread(target=self._worker, args=(title, cmd, parse_json, quiet), daemon=True)
        thread.start()

    def _worker(self, title: str, cmd: list[str], parse_json: bool, quiet: bool) -> None:
        try:
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_DIR),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            data = None
            if parse_json and proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout)
                except Exception:
                    data = None
            self.events.put(("result", {
                "title": title,
                "cmd": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout or "",
                "stderr": proc.stderr or "",
                "json": data,
                "quiet": quiet,
            }))
        except Exception as exc:
            self.events.put(("result", {
                "title": title,
                "cmd": cmd,
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
                "json": None,
                "quiet": quiet,
            }))


class HarnessControlPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("global-memory Harness 主控台")
        self.geometry("1180x760")
        self.minsize(1000, 650)
        self.configure(bg=PALETTE["bg"])

        self.runner = CommandRunner(self)
        self.status_var = tk.StringVar(value="就绪")
        self.summary_vars: dict[str, tk.StringVar] = {}
        self.quick_vars: dict[str, tk.StringVar] = {}
        self.sync_preview_vars: dict[str, tk.StringVar] = {}
        self.event_vars: dict[str, tk.StringVar] = {}
        self.decision_vars: dict[str, tk.StringVar] = {}
        self.event_log_offset = 0
        self.seen_event_keys: set[str] = set()
        self.raw_output_visible = tk.BooleanVar(value=False)
        self.busy_count = 0

        self._setup_style()
        self._build_ui()
        self.after(200, self._poll_runner)
        self.after(EVENT_POLL_MS, self._poll_panel_events)
        self.after(AUTO_REFRESH_MS, self._auto_refresh_status)
        self.run_status()

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        font = ("Microsoft YaHei UI", 10)
        style.configure(".", font=font, background=PALETTE["bg"], foreground=PALETTE["ink"])
        style.configure("Root.TFrame", background=PALETTE["bg"])
        style.configure("Panel.TFrame", background=PALETTE["panel"])
        style.configure("Soft.TFrame", background=PALETTE["panel_soft"])
        style.configure("Header.TFrame", background=PALETTE["brand"])
        style.configure("HeaderTitle.TLabel", background=PALETTE["brand"], foreground="#FFFFFF", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("HeaderSub.TLabel", background=PALETTE["brand"], foreground="#CFE2EE", font=("Microsoft YaHei UI", 9))
        style.configure("Status.TLabel", background=PALETTE["brand_light"], foreground=PALETTE["brand"], padding=(12, 6), font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("SectionTitle.TLabel", background=PALETTE["panel"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("SectionSub.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Card.TFrame", background=PALETTE["panel"], relief="flat")
        style.configure("Summary.TLabel", background=PALETTE["panel_soft"], foreground=PALETTE["ink"], padding=(10, 8))
        style.configure("Event.TLabel", background=PALETTE["brand_light"], foreground=PALETTE["brand"], padding=(10, 8))
        style.configure("Decision.TLabel", background=PALETTE["brand"], foreground="#FFFFFF", padding=(14, 12), font=("Microsoft YaHei UI", 15, "bold"))
        style.configure("DecisionSub.TLabel", background=PALETTE["brand_light"], foreground=PALETTE["brand"], padding=(12, 9), font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("OutputTitle.TLabel", background=PALETTE["panel"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("TNotebook", background=PALETTE["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 9), background=PALETTE["panel_soft"], foreground=PALETTE["muted"])
        style.map("TNotebook.Tab", background=[("selected", PALETTE["panel"])], foreground=[("selected", PALETTE["brand"])])
        style.configure("TButton", padding=(12, 8), background=PALETTE["panel_soft"], foreground=PALETTE["ink"], borderwidth=1)
        style.map("TButton", background=[("active", "#E8EEF5")])
        style.configure("Primary.TButton", background=PALETTE["brand"], foreground="#FFFFFF")
        style.map("Primary.TButton", background=[("active", "#155174")], foreground=[("active", "#FFFFFF")])
        style.configure("Accent.TButton", background=PALETTE["accent"], foreground="#FFFFFF")
        style.map("Accent.TButton", background=[("active", "#B86504")], foreground=[("active", "#FFFFFF")])
        style.configure("Danger.TButton", background=PALETTE["danger"], foreground="#FFFFFF")
        style.map("Danger.TButton", background=[("active", "#8F1D14")], foreground=[("active", "#FFFFFF")])
        style.configure("TCombobox", padding=(6, 4))
        style.configure("Treeview", rowheight=26, fieldbackground=PALETTE["panel"], background=PALETTE["panel"], foreground=PALETTE["ink"])
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background=PALETTE["panel_soft"], foreground=PALETTE["ink"])

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(root, padding=(18, 14), style="Header.TFrame")
        top.pack(fill=tk.X)
        title_box = ttk.Frame(top, style="Header.TFrame")
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text="global-memory Harness 主控台", style="HeaderTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(title_box, text="维护工具、自动同步、健康检查和 AI 诊断/计划的统一入口", style="HeaderSub.TLabel").pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(top, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.RIGHT)

        body = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        left = ttk.Frame(body, style="Root.TFrame")
        right = ttk.Frame(body, padding=12, style="Panel.TFrame")
        body.add(left, weight=1)
        body.add(right, weight=2)

        self.tabs = ttk.Notebook(left)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        self._build_dashboard_tab()
        self._build_fix_tab()
        self._build_sync_tab()
        self._build_daemon_tab()
        self._build_ai_tab()
        self._build_events_tab()
        self._build_tasks_tab()
        self._build_history_tab()

        ttk.Label(right, text="现在该看什么", style="OutputTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(right, text="默认只展示脚本提炼后的结论；命令行原文放在调试输出里。", style="SectionSub.TLabel").pack(anchor=tk.W, pady=(2, 8))

        self.decision_vars["headline"] = tk.StringVar(value="正在读取状态...")
        self.decision_vars["next_action"] = tk.StringVar(value="下一步：等待快速状态返回")
        self.decision_vars["why"] = tk.StringVar(value="面板会自动整理 maintain.py 返回的数据。")
        ttk.Label(right, textvariable=self.decision_vars["headline"], style="Decision.TLabel", wraplength=620).pack(fill=tk.X, pady=(4, 6))
        ttk.Label(right, textvariable=self.decision_vars["next_action"], style="DecisionSub.TLabel", wraplength=620).pack(fill=tk.X, pady=(0, 4))
        ttk.Label(right, textvariable=self.decision_vars["why"], style="Summary.TLabel", wraplength=620).pack(fill=tk.X, pady=(0, 10))

        ttk.Label(right, text="关键数据", style="OutputTitle.TLabel").pack(anchor=tk.W, pady=(8, 4))
        self.insight_tree = ttk.Treeview(right, columns=("item", "value", "level"), show="headings", height=8)
        self.insight_tree.heading("item", text="项目")
        self.insight_tree.heading("value", text="值")
        self.insight_tree.heading("level", text="级别")
        self.insight_tree.column("item", width=110, stretch=False)
        self.insight_tree.column("value", width=390, stretch=True)
        self.insight_tree.column("level", width=70, stretch=False, anchor=tk.CENTER)
        self.insight_tree.tag_configure("ok", foreground=PALETTE["ok"])
        self.insight_tree.tag_configure("info", foreground=PALETTE["brand"])
        self.insight_tree.tag_configure("warning", foreground=PALETTE["accent"])
        self.insight_tree.tag_configure("error", foreground=PALETTE["danger"])
        self.insight_tree.pack(fill=tk.X, pady=(0, 10))

        controls = ttk.Frame(right, style="Panel.TFrame")
        controls.pack(fill=tk.X, pady=(0, 6))
        ttk.Checkbutton(
            controls,
            text="显示原始命令输出（调试用）",
            variable=self.raw_output_visible,
            command=self._toggle_raw_output,
        ).pack(anchor=tk.W)

        self.debug_frame = ttk.Frame(right, style="Panel.TFrame")
        ttk.Label(self.debug_frame, text="原始命令输出", style="OutputTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(self.debug_frame, text="一般不用看；只有排查脚本异常时打开。", style="SectionSub.TLabel").pack(anchor=tk.W, pady=(2, 8))
        self.output = scrolledtext.ScrolledText(self.debug_frame, wrap=tk.WORD, height=14)
        self.output.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.output.configure(
            font=("Cascadia Mono", 10),
            background=PALETTE["log_bg"],
            foreground=PALETTE["log_fg"],
            insertbackground=PALETTE["log_fg"],
            selectbackground="#31506B",
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=10,
        )

    def _section(self, parent: ttk.Frame, title: str, subtitle: str = "") -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(frame, text=title, style="SectionTitle.TLabel").pack(anchor=tk.W)
        if subtitle:
            ttk.Label(frame, text=subtitle, style="SectionSub.TLabel", wraplength=410).pack(anchor=tk.W, pady=(4, 10))
        else:
            ttk.Separator(frame).pack(fill=tk.X, pady=8)
        return frame

    def _action_button(self, parent: ttk.Frame, text: str, command, style: str = "TButton") -> None:
        ttk.Button(parent, text=text, command=command, style=style).pack(fill=tk.X, pady=4)

    def _scroll_tab(self, title: str) -> ttk.Frame:
        outer = ttk.Frame(self.tabs, style="Root.TFrame")
        self.tabs.add(outer, text=title)
        canvas = tk.Canvas(outer, background=PALETTE["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, padding=12, style="Root.TFrame")
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def configure_content(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_canvas(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event: tk.Event) -> str:
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-3, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(3, "units")
            else:
                delta = int(-1 * (event.delta / 120))
                canvas.yview_scroll(delta * 3, "units")
            return "break"

        def bind_mousewheel(_event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_mousewheel)
            canvas.bind_all("<Button-5>", on_mousewheel)

        def unbind_mousewheel(_event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        content.bind("<Configure>", configure_content)
        canvas.bind("<Configure>", configure_canvas)
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)
        content.bind("<Enter>", bind_mousewheel)
        content.bind("<Leave>", unbind_mousewheel)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        return content

    def _build_dashboard_tab(self) -> None:
        tab = self._scroll_tab("总览")

        quick_card = self._section(tab, "快速状态", "轻量状态快照：不运行深度体检，不写文件。")
        for key, label in {
            "git": "Git",
            "daemon": "Daemon",
            "commits": "最近提交",
            "doctor": "最近体检",
        }.items():
            self.quick_vars[key] = tk.StringVar(value=f"{label}：未知")
            ttk.Label(quick_card, textvariable=self.quick_vars[key], style="Summary.TLabel", wraplength=420).pack(fill=tk.X, pady=3)

        status_card = self._section(tab, "Doctor 明细", "体检会聚合 Git、记忆健康、部署、Prompt、文档和冒烟测试。")
        for key in CHECK_LABELS:
            self.summary_vars[key] = tk.StringVar(value=f"{CHECK_LABELS[key]}：未知")
            ttk.Label(status_card, textvariable=self.summary_vars[key], style="Summary.TLabel", wraplength=420).pack(fill=tk.X, pady=3)

        actions = self._section(tab, "常用入口", "平时优先从这里判断当前体系是否健康。")
        self._action_button(actions, "刷新快速状态", self.run_status, "Primary.TButton")
        self._action_button(actions, "运行完整体检", self.run_doctor)
        self._action_button(actions, "生成维护报告", self.run_report)
        self._action_button(actions, "查看最近提交", self.run_log)
        self._action_button(actions, "打开面板说明", lambda: self.open_path(REPO_DIR / "CONTROL_PANEL.md"))
        self._action_button(actions, "打开日志目录", lambda: self.open_path(LOG_DIR))
        self._action_button(actions, "打开 MAINTENANCE.md", lambda: self.open_path(REPO_DIR / "MAINTENANCE.md"))

    def _build_fix_tab(self) -> None:
        tab = self._scroll_tab("修复")
        safe = self._section(tab, "安全修复", "只修改本地文件，不会提交或推送。适合处理索引、统计和路径漂移。")
        self._action_button(safe, "安全修复：索引 / 统计 / 路径", self.run_fix, "Primary.TButton")

        deploy = self._section(tab, "部署链路", "Bootstrap 负责 junction、settings 和关键入口文件。重新部署属于高风险动作。")
        self._action_button(deploy, "检查 Bootstrap 部署", self.run_bootstrap_check)
        self._action_button(deploy, "重新部署 Bootstrap（高风险）", self.run_bootstrap_install, "Danger.TButton")

    def _build_sync_tab(self) -> None:
        tab = self._scroll_tab("同步")
        inspect = self._section(tab, "同步前检查", "先看清楚当前改了什么，再决定是否生成 checkpoint。")
        self._action_button(inspect, "刷新 Git 状态", self.run_status, "Primary.TButton")
        self._action_button(inspect, "生成同步预览", self.run_sync_preview)
        self._action_button(inspect, "提交分组日志", self.run_log)

        preview = self._section(tab, "检查点候选", "这里展示只读预览，不会运行 safe fix、stage、commit 或 push。")
        for key, label in {
            "summary": "摘要",
            "commit": "候选提交",
            "groups": "文件分组",
        }.items():
            self.sync_preview_vars[key] = tk.StringVar(value=f"{label}：未知")
            ttk.Label(preview, textvariable=self.sync_preview_vars[key], style="Summary.TLabel", wraplength=420).pack(fill=tk.X, pady=3)

        changes = self._section(tab, "变更文件明细", "按 Git 状态列出文件；这里仍然只是只读展示。")
        self.change_tree = ttk.Treeview(changes, columns=("status", "path"), show="headings", height=10)
        self.change_tree.heading("status", text="状态")
        self.change_tree.heading("path", text="路径")
        self.change_tree.column("status", width=70, stretch=False, anchor=tk.CENTER)
        self.change_tree.column("path", width=330, stretch=True)
        self.change_tree.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        sync = self._section(tab, "检查点同步", "会提交并推送当前变更；适合保存维护过程中的稳定节点。")
        self._action_button(sync, "一键同步 / 检查点推送", self.run_sync, "Accent.TButton")

    def _build_daemon_tab(self) -> None:
        tab = self._scroll_tab("守护")
        daemon = self._section(tab, "自动同步守护进程", "守护进程只负责空闲触发，真正的 Git 同步统一交给 maintain.py。")
        self._action_button(daemon, "刷新守护进程状态", self.run_daemon_status, "Primary.TButton")
        self._action_button(daemon, "启动守护进程（后台）", self.run_daemon_start, "Accent.TButton")
        self._action_button(daemon, "停止守护进程", self.run_daemon_stop, "Danger.TButton")
        self._action_button(daemon, "查看 auto_sync.log", self.show_auto_sync_log)

    def _build_ai_tab(self) -> None:
        tab = self._scroll_tab("AI")

        form_card = self._section(tab, "AI Runner", "V1 只开放非交互式诊断和计划生成，不自动修改仓库文件。")
        form = ttk.Frame(form_card, style="Panel.TFrame")
        form.pack(fill=tk.X)
        self.provider_var = tk.StringVar(value="Claude CLI")
        self.mode_var = tk.StringVar(value="只读诊断")
        self.permission_var = tk.StringVar(value="计划模式")
        ttk.Label(form, text="提供方", style="SectionSub.TLabel").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(form, textvariable=self.provider_var, values=list(PROVIDER_OPTIONS), state="readonly", width=18).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=4)
        ttk.Label(form, text="任务类型", style="SectionSub.TLabel").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(form, textvariable=self.mode_var, values=list(MODE_OPTIONS), state="readonly", width=18).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=4)
        ttk.Label(form, text="权限模式", style="SectionSub.TLabel").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(form, textvariable=self.permission_var, values=list(PERMISSION_OPTIONS), state="readonly", width=18).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        self.context_doctor = tk.BooleanVar(value=True)
        self.context_diff = tk.BooleanVar(value=True)
        self.context_docs = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_card, text="附带体检报告", variable=self.context_doctor).pack(anchor=tk.W, pady=(10, 0))
        ttk.Checkbutton(form_card, text="附带 Git diff 摘要", variable=self.context_diff).pack(anchor=tk.W)
        ttk.Checkbutton(form_card, text="附带 README / MAINTENANCE", variable=self.context_docs).pack(anchor=tk.W)

        prompt_card = self._section(tab, "提示词", "这里会作为 AI 任务输入，必要时自动拼接体检、diff 和文档上下文。")
        self.ai_prompt = scrolledtext.ScrolledText(prompt_card, wrap=tk.WORD, height=8)
        self.ai_prompt.pack(fill=tk.BOTH, expand=True)
        self.ai_prompt.configure(
            font=("Microsoft YaHei UI", 10),
            background=PALETTE["panel_soft"],
            foreground=PALETTE["ink"],
            insertbackground=PALETTE["ink"],
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=8,
        )
        self.ai_prompt.insert("1.0", "分析当前 harness 健康状态，并给出下一步最安全的维护建议。")
        self._action_button(prompt_card, "运行 AI 诊断 / 计划", self.run_ai, "Primary.TButton")

    def _build_events_tab(self) -> None:
        tab = self._scroll_tab("事件")
        events = self._section(tab, "AI / 脚本事件", "外部 AI 或脚本调用 panel_api.py 后，会在这里自动出现。")
        for key in ("latest", "source", "level", "message"):
            self.event_vars[key] = tk.StringVar(value="暂无事件")
            ttk.Label(events, textvariable=self.event_vars[key], style="Event.TLabel", wraplength=420).pack(fill=tk.X, pady=3)
        self.event_tree = ttk.Treeview(events, columns=("time", "level", "source", "title"), show="headings", height=9)
        self.event_tree.heading("time", text="时间")
        self.event_tree.heading("level", text="级别")
        self.event_tree.heading("source", text="来源")
        self.event_tree.heading("title", text="标题")
        self.event_tree.column("time", width=118, stretch=False)
        self.event_tree.column("level", width=64, stretch=False, anchor=tk.CENTER)
        self.event_tree.column("source", width=90, stretch=False)
        self.event_tree.column("title", width=180, stretch=True)
        self.event_tree.tag_configure("success", foreground=PALETTE["ok"])
        self.event_tree.tag_configure("warning", foreground=PALETTE["accent"])
        self.event_tree.tag_configure("error", foreground=PALETTE["danger"])
        self.event_tree.tag_configure("info", foreground=PALETTE["brand"])
        self.event_tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        example = self._section(tab, "调用方式", "AI、脚本或终端可以用这个本地 API 给面板发通知。")
        ttk.Label(
            example,
            text='python harness\\panel_api.py notify --source ai --level info --title "分析完成" --message "建议先运行同步预览"',
            style="Summary.TLabel",
            wraplength=420,
        ).pack(fill=tk.X, pady=3)
        self._action_button(example, "刷新外部事件", self.show_recent_panel_events, "Primary.TButton")
        self._action_button(example, "打开事件日志", lambda: self.open_path(PANEL_EVENTS_LOG))

    def _build_history_tab(self) -> None:
        tab = self._scroll_tab("历史")
        history = self._section(tab, "运行历史", "查看最近提交，以及主控和 AI adapter 写入的 JSONL 日志。")
        self._action_button(history, "最近提交", self.run_log, "Primary.TButton")
        self._action_button(history, "生成维护报告", self.run_report)
        self._action_button(history, "打开 maintain 运行日志", lambda: self.open_path(LOG_DIR / "maintain.jsonl"))
        self._action_button(history, "打开 AI 运行日志", lambda: self.open_path(LOG_DIR / "ai_runner.jsonl"))

    def _build_tasks_tab(self) -> None:
        """任务总览页(2026-04-24 用户提需求)。
        调用 harness_status.py --tasks --json 取数据,显示 active + archived。
        双击行 → 在文件管理器打开该任务目录。
        """
        tab = self._scroll_tab("任务")
        section = self._section(tab, "任务总览", "活跃 + 归档任务清单,简介从各任务的需求/HANDOFF/SPEC 自动抽取。双击打开任务目录。")

        self._action_button(section, "🔄 刷新任务列表", lambda: self._refresh_tasks_tree(), "Primary.TButton")

        # Treeview: kind / stage / name / brief
        tree_frame = ttk.Frame(section, style="Root.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=8)

        cols = ("kind", "stage", "name", "brief")
        self.tasks_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        self.tasks_tree.heading("kind", text="状态")
        self.tasks_tree.heading("stage", text="阶段")
        self.tasks_tree.heading("name", text="任务名")
        self.tasks_tree.heading("brief", text="简介")
        self.tasks_tree.column("kind", width=80, anchor="center")
        self.tasks_tree.column("stage", width=120, anchor="center")
        self.tasks_tree.column("name", width=240, anchor="w")
        self.tasks_tree.column("brief", width=560, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tasks_tree.yview)
        self.tasks_tree.configure(yscrollcommand=vsb.set)
        self.tasks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tasks_tree.bind("<Double-1>", self._on_task_double_click)

        # 任务路径映射,双击时使用
        self._tasks_path_map: dict[str, str] = {}

        # 初次加载
        self._refresh_tasks_tree()

    def _refresh_tasks_tree(self) -> None:
        """运行 harness_status.py --tasks --json 并渲染到 Treeview"""
        if not hasattr(self, "tasks_tree"):
            return
        for iid in self.tasks_tree.get_children():
            self.tasks_tree.delete(iid)
        self._tasks_path_map.clear()

        try:
            proc = subprocess.run(
                [sys.executable, str(HARNESS_DIR / "harness_status.py"), "--tasks", "--json"],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            if proc.returncode != 0:
                self.tasks_tree.insert("", "end", values=("❌", "ERR", "(脚本调用失败)", proc.stderr[:200]))
                return
            data = json.loads(proc.stdout)
        except Exception as e:
            self.tasks_tree.insert("", "end", values=("❌", "ERR", "(数据加载失败)", str(e)[:200]))
            return

        stage_emoji = {
            "discussion": "🟢", "implementation": "🔵",
            "archived": "⚪", "unknown": "⚪", "missing": "❌",
        }

        for t in data.get("active", []):
            iid = self.tasks_tree.insert(
                "", "end",
                values=("🟡 active", f"{stage_emoji.get(t['stage'], '⚪')} {t['stage']}", t["name"], t["brief"][:300]),
            )
            self._tasks_path_map[iid] = t["path"]

        for t in data.get("archived", []):
            iid = self.tasks_tree.insert(
                "", "end",
                values=("⚫ archived", f"{stage_emoji.get(t['stage'], '⚪')} {t['stage']}", t["name"], t["brief"][:300]),
            )
            self._tasks_path_map[iid] = t["path"]

    def _on_task_double_click(self, _event) -> None:
        """双击行 → 在文件管理器打开任务目录"""
        sel = self.tasks_tree.selection()
        if not sel:
            return
        path = self._tasks_path_map.get(sel[0])
        if path:
            self.open_path(Path(path))

    def command(self, *parts: str) -> list[str]:
        return [sys.executable, *parts]

    def run_status(self, quiet: bool = False) -> None:
        self.runner.run("快速状态", self.command(str(HARNESS_DIR / "maintain.py"), "status", "--json"), parse_json=True, quiet=quiet)

    def run_doctor(self) -> None:
        self.runner.run("主控体检", self.command(str(HARNESS_DIR / "maintain.py"), "doctor", "--json"), parse_json=True)

    def run_fix(self) -> None:
        if messagebox.askyesno("确认修复", "运行本地安全修复？这可能修改已跟踪文件，但不会提交或推送。"):
            self.runner.run("安全修复", self.command(str(HARNESS_DIR / "maintain.py"), "fix", "--json"), parse_json=True)

    def run_bootstrap_check(self) -> None:
        self.runner.run("Bootstrap 检查", self.command(str(REPO_DIR / "bootstrap.py"), "check"))

    def run_bootstrap_install(self) -> None:
        if messagebox.askyesno("高风险操作", "bootstrap install 会重写 ~/.claude 设置和 junction 链接。确定继续？"):
            self.runner.run("Bootstrap 重新部署", self.command(str(REPO_DIR / "bootstrap.py"), "install"))

    def run_git_status(self) -> None:
        self.run_status()

    def run_sync_preview(self) -> None:
        self.runner.run(
            "同步预览",
            self.command(str(HARNESS_DIR / "maintain.py"), "sync", "--preview", "--source", "gui", "--json"),
            parse_json=True,
        )

    def run_sync(self) -> None:
        if messagebox.askyesno("检查点同步", "把当前变更提交并推送为检查点？"):
            self.runner.run("一键同步", self.command(str(HARNESS_DIR / "maintain.py"), "sync", "--source", "gui", "--json"), parse_json=True)

    def run_log(self) -> None:
        self.runner.run("提交日志", self.command(str(HARNESS_DIR / "maintain.py"), "log", "--json", "--limit", "40"), parse_json=True)

    def run_report(self) -> None:
        self.runner.run("维护报告", self.command(str(HARNESS_DIR / "maintain.py"), "report", "--markdown"))

    def run_daemon_status(self) -> None:
        self.runner.run("守护进程状态", self.command(str(HARNESS_DIR / "maintain.py"), "daemon", "status", "--json"), parse_json=True)

    def run_daemon_start(self) -> None:
        if messagebox.askyesno("启动守护进程", "在后台启动自动同步守护进程？"):
            self.runner.run("启动守护进程", self.command(str(HARNESS_DIR / "maintain.py"), "daemon", "start", "--json"), parse_json=True)

    def run_daemon_stop(self) -> None:
        if messagebox.askyesno("停止守护进程", "停止正在运行的自动同步守护进程？"):
            self.runner.run("停止守护进程", self.command(str(HARNESS_DIR / "maintain.py"), "daemon", "stop", "--json"), parse_json=True)

    def run_ai(self) -> None:
        prompt = self.ai_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("需要提示词", "请先输入提示词。")
            return
        cmd = self.command(
            str(HARNESS_DIR / "ai_runner.py"),
            prompt,
            "--provider", PROVIDER_OPTIONS[self.provider_var.get()],
            "--mode", MODE_OPTIONS[self.mode_var.get()],
            "--permission-mode", PERMISSION_OPTIONS[self.permission_var.get()],
            "--json",
        )
        if self.context_doctor.get():
            cmd.append("--context-doctor")
        if self.context_diff.get():
            cmd.append("--context-diff")
        if self.context_docs.get():
            cmd.append("--context-docs")
        self.runner.run("AI 执行", cmd, parse_json=True)

    def show_auto_sync_log(self) -> None:
        if AUTO_SYNC_LOG.exists():
            text = AUTO_SYNC_LOG.read_text(encoding="utf-8", errors="replace")
            self.append_output("\n# auto_sync.log\n" + "\n".join(text.splitlines()[-120:]) + "\n")
        else:
            self.append_output("\n未找到 auto_sync.log\n")

    def show_recent_panel_events(self) -> None:
        if not PANEL_EVENTS_LOG.exists():
            self.append_output("\n未找到 control_panel_events.jsonl\n")
            return
        text = PANEL_EVENTS_LOG.read_text(encoding="utf-8", errors="replace")
        self.append_output("\n# control_panel_events.jsonl\n" + "\n".join(text.splitlines()[-80:]) + "\n")

    def open_path(self, path: Path) -> None:
        try:
            if not path.exists():
                messagebox.showwarning("未找到", str(path))
                return
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def set_busy(self, busy: bool, title: str = "") -> None:
        if busy:
            self.busy_count += 1
        else:
            self.busy_count = max(0, self.busy_count - 1)
        self.status_var.set(f"正在运行：{title}..." if busy else "就绪")

    def append_output(self, text: str) -> None:
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def _toggle_raw_output(self) -> None:
        if self.raw_output_visible.get():
            self.debug_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        else:
            self.debug_frame.pack_forget()

    def _set_decision(self, decision: dict) -> None:
        self.decision_vars["headline"].set(str(decision.get("headline", "暂无结论")))
        self.decision_vars["next_action"].set(str(decision.get("next_action", "下一步：暂无")))
        self.decision_vars["why"].set(str(decision.get("why", "")))

    def _set_insights(self, cards: list[dict]) -> None:
        if not hasattr(self, "insight_tree"):
            return
        self.insight_tree.delete(*self.insight_tree.get_children())
        for card in cards:
            if not isinstance(card, dict):
                continue
            level = str(card.get("level", "info"))
            self.insight_tree.insert(
                "",
                tk.END,
                values=(card.get("title", ""), card.get("value", ""), level),
                tags=(level,),
            )

    def _poll_runner(self) -> None:
        try:
            while True:
                kind, payload = self.runner.events.get_nowait()
                if kind == "result":
                    self._handle_result(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        self.after(200, self._poll_runner)

    def _handle_result(self, result: dict) -> None:
        quiet = bool(result.get("quiet"))
        if not quiet:
            self.set_busy(False)
        title = result["title"]
        code = result["returncode"]
        stdout = result["stdout"]
        stderr = result["stderr"]
        data = result.get("json")
        if not quiet:
            self.append_output(f"\n# {title} 结束，退出码 {code}\n")
        if data is not None:
            if not quiet:
                self.append_output(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            self._update_summary_from_json(data)
        else:
            if code != 0:
                self._set_decision({
                    "headline": f"{title} 运行失败",
                    "next_action": "下一步：打开原始命令输出查看错误",
                    "why": stderr.strip()[:240] if stderr else "脚本没有返回结构化 JSON。",
                })
            if stdout and not quiet:
                self.append_output(stdout + "\n")
            if stderr and not quiet:
                self.append_output("[错误输出]\n" + stderr + "\n")

    def _auto_refresh_status(self) -> None:
        if self.busy_count == 0:
            self.run_status(quiet=True)
        self.after(AUTO_REFRESH_MS, self._auto_refresh_status)

    def _poll_panel_events(self) -> None:
        try:
            if PANEL_EVENTS_LOG.exists():
                if self.event_log_offset == 0:
                    size = PANEL_EVENTS_LOG.stat().st_size
                    self.event_log_offset = max(0, size - 64_000)
                with PANEL_EVENTS_LOG.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(self.event_log_offset)
                    lines = f.readlines()
                    self.event_log_offset = f.tell()
                for line in lines[-20:]:
                    self._handle_panel_event_line(line)
        except Exception as exc:
            self.append_output(f"\n[外部事件读取失败]\n{exc}\n")
        self.after(EVENT_POLL_MS, self._poll_panel_events)

    def _handle_panel_event_line(self, line: str) -> None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        summary = summarize_event(event)
        if summary["key"] in self.seen_event_keys:
            return
        self.seen_event_keys.add(summary["key"])
        title = summary["title"]
        message = summary["message"]
        source = summary["source"]
        level = summary["level"]
        timestamp = event.get("timestamp", "")
        if "latest" in self.event_vars:
            self.event_vars["latest"].set(f"最新事件：{timestamp} - {title}")
            self.event_vars["source"].set(f"来源：{source}")
            self.event_vars["level"].set(f"级别：{level}")
            self.event_vars["message"].set(f"内容：{message}")
        if hasattr(self, "event_tree"):
            self.event_tree.insert("", 0, values=(summary["time"], level, source, title), tags=(level,))
            children = self.event_tree.get_children()
            for item in children[200:]:
                self.event_tree.delete(item)
        self.append_output(f"\n# 外部事件 [{level}] {title}\n来源：{source}\n{message}\n")

    def _update_summary_from_json(self, data: object) -> None:
        if not isinstance(data, dict):
            return
        mode = data.get("mode")
        if mode == "status":
            self._update_status_from_json(data)
        elif mode == "sync-preview":
            self._update_sync_preview_from_json(data)
        elif mode == "doctor":
            model = summarize_doctor(data)
            self._set_decision(model["decision"])
            self._set_insights([
                {"title": item["id"], "value": item["summary"], "level": str(item["level"]).lower()}
                for item in model["checks"]
            ])
            summary = data.get("summary", {})
            if "doctor" in self.quick_vars:
                self.quick_vars["doctor"].set(
                    f"最近体检：PASS {summary.get('PASS', 0)} / WARNING {summary.get('WARNING', 0)} / ERROR {summary.get('ERROR', 0)}"
                )
            for item in data.get("results", []):
                if isinstance(item, dict):
                    key = item.get("id")
                    if key in self.summary_vars:
                        label = CHECK_LABELS[key]
                        self.summary_vars[key].set(f"{label}：{item.get('level')} - {item.get('summary')}")
        elif "entries" in data:
            model = summarize_log(data)
            summary = data.get("summary", {})
            if "commits" in self.quick_vars:
                self.quick_vars["commits"].set(
                    f"最近提交：语义 {model['semantic']} / 检查点 {model['checkpoint']} / 总计 {model['total']}"
                )
            self._set_decision({
                "headline": f"最近 {model['total']} 个提交里有 {model['checkpoint']} 个检查点",
                "next_action": "下一步：如果检查点太多，后续考虑合并或补语义提交",
                "why": f"语义提交 {model['semantic']} 个，checkpoint {model['checkpoint']} 个。",
            })
            self._set_insights([
                {"title": "语义提交", "value": model["semantic"], "level": "ok"},
                {"title": "检查点", "value": model["checkpoint"], "level": "info"},
                {"title": "总计", "value": model["total"], "level": "info"},
            ])
            self.append_output(f"语义提交={model['semantic']} 检查点提交={model['checkpoint']}\n")
        elif "running" in data:
            if "daemon" in self.quick_vars:
                self.quick_vars["daemon"].set(
                    f"Daemon：running={data.get('running')} / processes={len(data.get('processes', []) or [])}"
                )
        elif "started" in data or "stopped" in data:
            if "daemon" in self.quick_vars:
                self.quick_vars["daemon"].set(f"Daemon：{data.get('summary', '状态已变更')}")

    def _format_groups(self, groups: dict) -> str:
        if not groups:
            return "文件分组：无变更"
        parts = [f"{group} {len(paths)}" for group, paths in groups.items()]
        return "文件分组：" + " / ".join(parts)

    def _update_status_from_json(self, data: dict) -> None:
        model = summarize_status(data)
        self._set_decision(model["decision"])
        self._set_insights(model["cards"])
        git_info = data.get("git", {})
        daemon = data.get("daemon", {})
        recent = data.get("recent_commits", {}).get("summary", {})
        logs = data.get("logs", {}).get("maintain_tail", [])
        if "git" in self.quick_vars:
            self.quick_vars["git"].set(
                f"Git：dirty={git_info.get('dirty')} / ahead={git_info.get('ahead')} / behind={git_info.get('behind')} / 变更 {git_info.get('change_count')}"
            )
        if "daemon" in self.quick_vars:
            self.quick_vars["daemon"].set(
                f"Daemon：running={daemon.get('running')} / processes={daemon.get('process_count')}"
            )
        if "commits" in self.quick_vars:
            self.quick_vars["commits"].set(
                f"最近提交：语义 {recent.get('semantic', 0)} / 检查点 {recent.get('checkpoint', 0)} / 总计 {recent.get('total', 0)}"
            )
        doctor = None
        for item in reversed(logs):
            if item.get("type") == "doctor":
                doctor = item
                break
        if doctor and "doctor" in self.quick_vars:
            summary = doctor.get("summary") or {}
            self.quick_vars["doctor"].set(
                f"最近体检：PASS {summary.get('PASS', 0)} / WARNING {summary.get('WARNING', 0)} / ERROR {summary.get('ERROR', 0)}"
            )
        if "summary" in self.sync_preview_vars:
            self.sync_preview_vars["summary"].set(
                f"摘要：当前工作区变更 {git_info.get('change_count', 0)} 个，dirty={git_info.get('dirty')}"
            )
        if "groups" in self.sync_preview_vars:
            self.sync_preview_vars["groups"].set(self._format_groups(git_info.get("groups", {})))
        self._update_change_tree(git_info.get("changes", []))

    def _update_sync_preview_from_json(self, data: dict) -> None:
        model = summarize_sync_preview(data)
        self._set_decision(model["decision"])
        self._set_insights([
            {"title": "文件数", "value": len(model["changes"]), "level": "warning" if model["changes"] else "ok"},
            {"title": "分组", "value": model["groups_text"], "level": "info"},
            {"title": "提交名", "value": model["commit"] or "(无)", "level": "info"},
        ])
        if "summary" in self.sync_preview_vars:
            self.sync_preview_vars["summary"].set(
                f"摘要：{data.get('summary')}；真实同步会先 pull --rebase={data.get('would_pull_rebase_on_real_sync')}"
            )
        if "commit" in self.sync_preview_vars:
            self.sync_preview_vars["commit"].set(f"候选提交：{data.get('commit', '(无)')}")
        if "groups" in self.sync_preview_vars:
            self.sync_preview_vars["groups"].set(self._format_groups(data.get("groups", {})))
        self._update_change_tree(data.get("changes", []))

    def _update_change_tree(self, changes: list[dict]) -> None:
        if not hasattr(self, "change_tree"):
            return
        self.change_tree.delete(*self.change_tree.get_children())
        if not changes:
            self.change_tree.insert("", tk.END, values=("clean", "当前无工作区变更"))
            return
        for entry in changes:
            if not isinstance(entry, dict):
                continue
            self.change_tree.insert(
                "",
                tk.END,
                values=(entry.get("code", "?"), entry.get("path", entry.get("raw", ""))),
            )


def main() -> int:
    app = HarnessControlPanel()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
