# 心动引擎中台 · 任务板

## 当前进行中
| 任务 | 状态 | 开始日期 | 备注 |
|------|------|---------|------|
| 多线程资源加载插件 | 预研完成 | 2026-04-13 | 方案 C (Wrapper) |
| XDAdaptivePerformance 重构 | Phase 1c 进行中 | 2026-04-21 | 子线程化 init；红米 K60 baseline=27080ms。日志见 `D:/ClaudeTasks/active/xd-adaptive-performance-refactor/baseline-logs/`（`*-full.log` 完整 / `*-relevant.log` 精简） |

## 待办
| 任务 | 优先级 | 备注 |
|------|--------|------|
| | | |

## 已完成
| 任务 | 完成日期 | 总结 |
|------|---------|------|
| Android APK 打包环境 | 2026-04-21 | APK + OBB 打包跑通；红米 K60 (23013RK75C, 骁龙 8+ Gen1) 真机启动成功。ShaderCodeLibrary 闪退已解决（修复手段未沉淀，待补） |

---

## Android APK 打包 · 专项记录

### 需求背景
在本机 Windows 环境下能打出可安装、可运行的 Android APK 包，用于开发调试。
项目：《火炬之光：无限》，UE 4.26.2 源码版。

### 当前进度（已完成 · 2026-04-21）

**全流程跑通：**
- [x] 项目 Android 配置摸底（包名 com.xindong.torchlight，SDK 35，ARM64，ASTC）
- [x] 本机环境诊断（缺 Android SDK/NDK/JDK → 后已补齐）
- [x] 已有 subst 盘符映射 `Z: → Editor/`
- [x] 打包脚本 `BuildPackage.py` 跑通，产出 APK + OBB
- [x] APK 安装到真机成功（小米 Redmi，设备 645b5500 / 红米 K60 23013RK75C）
- [x] OBB 推送成功（main / patch / overflow1 / overflow2 共 4 个）
- [x] 红米 K60 真机启动成功，能进登录页 — 详见 `D:/ClaudeTasks/active/xd-adaptive-performance-refactor/baseline-logs/`

**ShaderCodeLibrary 闪退（曾卡点，已解决）：**
- 现象：`FShaderCodeLibrary::InitForRuntime` fatal — Global shader library is missing
- 崩溃位置：`Engine/Source/Runtime/RenderCore/Private/ShaderCodeLibrary.cpp:2553`
- 根因链（HANDOFF.md 已沉淀）：游戏插件未被 PluginManager 挂载 → DLL 加载失败 → Cook phase 6 失败 → 无 shader archive → 真机启动 fatal
- ⚠️ **修复手段未沉淀到 fixes/** — 需要补一份 `fixes_shader_code_library_missing.md`

### 打包环境修复记录

从 Claude Code (Git Bash) 跑打包遇到两个问题，已修复：

| 问题 | 根因 | 修复 |
|------|------|------|
| `AutomationToolLauncher.exe` 报"不是可运行的程序" (9009) | Git Bash 设 `NoDefaultCurrentDirectoryInExePath=1`，cmd.exe 不在 CWD 搜索 exe | 删除该环境变量 |
| UBT 报路径超 260 字符 | 项目根路径 72 字符太深，中间产物超 MAX_PATH | 用 `subst Z:` 短路径 + patch `os.path.realpath` |
| adb push 路径被转译 | Git Bash MSYS 自动转换 `/sdcard` → `C:/Program Files/Git/sdcard` | 设 `MSYS_NO_PATHCONV=1` |

**工具产物：** `frontend/trunk/Tools/run_build_compat.py` — 封装了以上所有修复的打包 wrapper。

### 打包脚本与参数

- 脚本：`frontend/trunk/Tools/BuildPackage.py`
- 兼容 wrapper：`frontend/trunk/Tools/run_build_compat.py`（Claude Code 专用）
- 当前参数：渠道=Test，平台=Android，编译类型=Test，烘焙=ASTC
- 产出路径：`frontend/trunk/Output/{时间戳}/Android_ASTC/`
- 产出文件：`UE_game-arm64.apk` (158M) + `main.*.obb` (1.2G)

### 关键文件位置

| 文件 | 用途 |
|------|------|
| `Editor/UE_game/Config/DefaultEngine.ini` | Android 运行时配置（SDK 版本、包名等） |
| `Editor/Engine/Build/BatchFiles/RunUAT.bat` | UE 自动化工具入口 |
| `Editor/Engine/Source/Runtime/RenderCore/Private/ShaderCodeLibrary.cpp` | 闪退崩溃位置 |
| `Editor/Engine/Programs/AutomationTool/Saved/Logs/` | 打包/Cook 日志目录 |
| `Editor/UE_game/Build/Android/` | keystore、图标、启动图等资产 |
| 手机 `/data/tombstones/tombstone_30` | 最近一次 native crash dump |
