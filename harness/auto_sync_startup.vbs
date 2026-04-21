' auto_sync_startup.vbs — 无窗口启动守护进程
' 放到 shell:startup 目录实现开机自启

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw """ & WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.claude\scripts\auto_sync_daemon.py""", 0, False
