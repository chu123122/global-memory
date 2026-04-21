---
name: fixes-android-apk-build
description: UE 4.26.2 + Git Bash 下 Android APK 打包的兼容性修复记录
summary: "已记录 AutomationToolLauncher 9009、MAX_PATH、adb push 路径转译 3 类问题"
type: fixes
created: 2026-04-16
updated: 2026-04-21
source: 心动引擎中台 Android APK 打包实战
access_count: 0
---

# Android APK 打包修复经验（UE 4.26.2 + Git Bash）

> 项目：火炬之光，UE 4.26.2 源码版，Windows 11

## 问题 1: AutomationToolLauncher.exe 找不到 (错误码 9009)

**现象：** `RunUAT.bat` 执行到 `pushd Binaries\DotNET && AutomationToolLauncher.exe` 时报"不是可运行的程序"，但 exe 确实存在于该目录。

**根因：** Git Bash 设置了 `NoDefaultCurrentDirectoryInExePath=1`，这个 Windows 环境变量禁止 cmd.exe 在当前目录搜索可执行文件。正常 cmd.exe 默认会搜索 CWD，但 Git Bash 出于安全考虑禁用了。

**修复：** `os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)`

**验证方式：** 在 bat 文件里用 `.\AutomationToolLauncher.exe`（加 `.\` 前缀）也能解决，但这需要改引擎文件。

## 问题 2: 路径超过 260 字符

**现象：** UBT 报 `The following output paths are longer than 260 characters. Please move the engine to a directory with a shorter path.`

**根因：** 项目路径 `C:\Users\XINDONG\Perforce\tl_gaoxinag_01\frontend\trunk\Editor\` (72字符) + UBT 中间产物路径（ContentBrowserAssetDataSource 等长名插件）超过 MAX_PATH。UBT 自己检查路径长度，开 Windows LongPathsEnabled 注册表无效。

**修复：** 使用 `subst Z: C:\...\Editor` 映射短盘符。需配合 patch `os.path.realpath` → `os.path.abspath`（Python 3.8+ 的 `realpath` 会解析 subst 回原路径）。

## 问题 3: adb push 路径被 MSYS 转译

**现象：** `adb push xxx /sdcard/...` 的 `/sdcard` 被 Git Bash 自动转换为 `C:/Program Files/Git/sdcard`。

**根因：** MSYS2 自动路径转换。

**修复：** `export MSYS_NO_PATHCONV=1`

## 通用结论

Git Bash (MSYS2) 环境下跑 Windows 原生工具链（bat、adb 等）有三类常见坑：
1. **CWD exe 搜索被禁** — `NoDefaultCurrentDirectoryInExePath`
2. **路径格式转换** — MSYS 自动转 `/xxx` 为 `C:/Program Files/Git/xxx`
3. **subst 盘符被解析** — Python `os.path.realpath` 会还原 subst
