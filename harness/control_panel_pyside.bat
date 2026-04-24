@echo off
REM PySide6 主控台启动入口（开发期）。
REM 设计 §8.1：先静默装依赖，再启动模块。

setlocal
cd /d "%~dp0"

python -m pip install -r control_panel_pyside\requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [warning] requirements 安装非 0 退出，仍尝试启动...
)

python -m control_panel_pyside %*
endlocal
