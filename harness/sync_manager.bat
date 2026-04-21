@echo off
chcp 65001 >nul
echo ========================================
echo   记忆同步守护进程管理
echo ========================================
echo.
echo   1. 启动守护进程（后台）
echo   2. 停止守护进程
echo   3. 查看运行状态
echo   4. 立即同步一次
echo   5. 查看同步日志（最近 20 行）
echo   6. 设置开机自启
echo   7. 取消开机自启
echo   0. 退出
echo.
set /p choice=请选择: 

if "%choice%"=="1" (
    echo 启动中...
    start "" pythonw "%USERPROFILE%\.claude\scripts\auto_sync_daemon.py"
    timeout /t 2 >nul
    tasklist /fi "imagename eq pythonw.exe" | findstr pythonw >nul
    if %errorlevel%==0 (
        echo ✅ 守护进程已启动
    ) else (
        echo ❌ 启动失败，尝试用 python 前台运行排查：
        echo    python %USERPROFILE%\.claude\scripts\auto_sync_daemon.py
    )
    pause
    goto :eof
)

if "%choice%"=="2" (
    echo 停止中...
    taskkill /f /im pythonw.exe 2>nul
    if %errorlevel%==0 (
        echo ✅ 已停止
    ) else (
        echo ℹ️ 没有找到运行中的守护进程
    )
    pause
    goto :eof
)

if "%choice%"=="3" (
    echo.
    tasklist /fi "imagename eq pythonw.exe" 2>nul | findstr pythonw >nul
    if %errorlevel%==0 (
        echo ✅ 守护进程正在运行
        tasklist /fi "imagename eq pythonw.exe"
    ) else (
        echo ❌ 守护进程未运行
    )
    pause
    goto :eof
)

if "%choice%"=="4" (
    echo 立即同步中...
    python "%USERPROFILE%\.claude\scripts\auto_sync_daemon.py" --once
    pause
    goto :eof
)

if "%choice%"=="5" (
    echo.
    echo === 最近 20 行日志 ===
    powershell -Command "Get-Content -Tail 20 -Encoding UTF8 '%USERPROFILE%\.claude\auto_sync.log'"
    pause
    goto :eof
)

if "%choice%"=="6" (
    set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    copy /Y "%USERPROFILE%\.claude\scripts\auto_sync_startup.vbs" "%STARTUP%\auto_sync_startup.vbs" >nul 2>&1
    if exist "%STARTUP%\auto_sync_startup.vbs" (
        echo ✅ 已设置开机自启
    ) else (
        echo ❌ 设置失败，尝试手动复制：
        echo    copy "%USERPROFILE%\.claude\scripts\auto_sync_startup.vbs" "%STARTUP%\"
    )
    pause
    goto :eof
)

if "%choice%"=="7" (
    set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    del "%STARTUP%\auto_sync_startup.vbs" 2>nul
    if not exist "%STARTUP%\auto_sync_startup.vbs" (
        echo ✅ 已取消开机自启
    ) else (
        echo ❌ 取消失败
    )
    pause
    goto :eof
)

if "%choice%"=="0" goto :eof

echo 无效选择
pause
