"""subprocess 封装 + QThread 异步执行。

设计 §3.1：git status / harness_status.py / maintain.py 等阻塞调用走 QThread，
避免主线程冻结。回调通过 Qt Signal 自动跨线程派发到 UI 线程。
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


@dataclass
class CommandResult:
    title: str
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    json: dict | list | None = None
    extras: dict = field(default_factory=dict)


class _RunnerSignals(QObject):
    finished = Signal(object)  # CommandResult


class _CommandRunnable(QRunnable):
    def __init__(
        self,
        title: str,
        cmd: list[str],
        cwd: Path | None,
        parse_json: bool,
        extras: dict,
        signals: _RunnerSignals,
    ) -> None:
        super().__init__()
        self._title = title
        self._cmd = cmd
        self._cwd = cwd
        self._parse_json = parse_json
        self._extras = extras
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 — Qt API
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run(
                self._cmd,
                cwd=str(self._cwd) if self._cwd else None,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            data = None
            if self._parse_json and proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout)
                except json.JSONDecodeError as exc:
                    data = None
                    parse_error = (
                        f"JSON parse failed for {self._title}: "
                        f"{exc.msg} at line {exc.lineno} column {exc.colno}"
                    )
                else:
                    parse_error = ""
            else:
                parse_error = ""
            stderr = proc.stderr or ""
            if parse_error:
                stderr = (stderr.rstrip() + "\n" if stderr else "") + parse_error
            result = CommandResult(
                title=self._title,
                cmd=self._cmd,
                returncode=proc.returncode,
                stdout=proc.stdout or "",
                stderr=stderr,
                json=data,
                extras=self._extras,
            )
        except subprocess.TimeoutExpired as exc:
            result = CommandResult(
                title=self._title,
                cmd=self._cmd,
                returncode=124,
                stdout="",
                stderr=f"timeout after {exc.timeout}s",
                json=None,
                extras=self._extras,
            )
        except Exception as exc:  # noqa: BLE001 — 兜底
            result = CommandResult(
                title=self._title,
                cmd=self._cmd,
                returncode=1,
                stdout="",
                stderr=f"{type(exc).__name__}: {exc}",
                json=None,
                extras=self._extras,
            )
        try:
            self._signals.finished.emit(result)
        except RuntimeError:
            # 关闭竞态：CommandRunner 已被 GC，runnable 仍跑完 —— 安全丢弃结果
            pass


class CommandRunner(QObject):
    """通过 QThreadPool 异步跑 subprocess，结果通过 result_ready(CommandResult) 派发。"""

    result_ready = Signal(object)  # CommandResult

    def __init__(self, default_cwd: Path | None = None) -> None:
        super().__init__()
        self._default_cwd = default_cwd
        self._pool = QThreadPool.globalInstance()
        self._signals = _RunnerSignals()
        self._signals.finished.connect(self._on_finished)

    def run(
        self,
        title: str,
        cmd: list[str],
        parse_json: bool = False,
        cwd: Path | None = None,
        extras: dict | None = None,
    ) -> None:
        runnable = _CommandRunnable(
            title=title,
            cmd=cmd,
            cwd=cwd or self._default_cwd,
            parse_json=parse_json,
            extras=extras or {},
            signals=self._signals,
        )
        self._pool.start(runnable)

    @Slot(object)
    def _on_finished(self, result: CommandResult) -> None:
        self.result_ready.emit(result)
