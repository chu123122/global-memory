---
name: fixes-android-apk-build
description: UE 4.26.2 + Git Bash 下 Android APK 打包 / 装机 / OBB / MAGT 鉴权全流程修复记录
summary: "10 类问题：环境（NoDefault*/MAX_PATH/MSYS路径）+ 构建（Editor锁dll/4GiB OBB）+ 装机（install -r 清 OBB）+ 调用（cmd//c 失败/PSO 噪音覆盖 logcat）+ MTK MAGT verify -8 签名链路"
type: fixes
created: 2026-04-16
updated: 2026-04-22
source: 心动引擎中台 Android APK 打包实战 + Phase 1c 子线程化跨平台验证
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

## 问题 4: UE Editor 开着 → BuildPackage 链接失败 LNK1104

**现象：** 跑 BuildPackage.py 编 Android target 时报：
```
LINK : fatal error LNK1104: 无法打开文件 UE4Editor-UE_game.dll
BUILD FAILED
```

**根因：** `BuildCookRun -targetplatform=Android` 即使带也会**顺手编 Win64 editor 二进制**（用于 cook 进程）。Editor 进程开着时 .dll 被 Windows 文件锁，UBT 编完新的 .dll 写不进去。

**修复 A**：构建前关 UE Editor（最稳）。可以 `tasklist //FI "IMAGENAME eq UE4Editor.exe"` 检查。

**修复 B**：BuildCookRun 命令加 `-nocompileeditor` 跳过 editor 重编（不一定所有 build flow 都支持）。

## 问题 5: 单 OBB > 4 GiB → Stage Failed

**现象：** Build 跑到 stage 阶段报：
```
ERROR: Stage Failed. Could not build OBB ...Android_ASTC.obb. The file may be too big to fit in an OBB (4 GiB limit)
BUILD FAILED
```

**根因：** Android OBB 单文件硬上限 4 GiB（`uint32` 文件大小字段）。火炬之光 main / patch 各 ~4.0 GiB **贴红线**，cook 增量后 chunk 大小波动一点点就超线。`bAllowOverflowOBBFiles=True` 配置启用 main / patch / overflow1 / overflow2 多 OBB 模式，但 stage 时按 chunk 配置打包，chunk 划分可能让某个 chunk > 4GiB。

**修复 A**：复用上次成功的 OBB + 当次新 APK，组装 hybrid 目录装机。前提：versionCode 一致（OBB 文件名 `main.<versionCode>.<package>.obb` 匹配 APK manifest 里的 versionCode）。流程：
```bash
mkdir -p Output/_apk-comparison/Android_ASTC
cp <success-build-output>/Android_ASTC/*.obb _apk-comparison/Android_ASTC/
cp <new-build-binaries>/Android/UE_game-arm64.apk _apk-comparison/Android_ASTC/
```

**修复 B**：`BuildPackage.py` 设 `SKIPP_PAK=True` 跳 pak 步骤（前提：staged pak 还在，否则 stage 仍失败）。

**修复 C**：调整 `DefaultEngine.ini` 的 `+StreamedPakFilters=` 把大 chunk 拆小，让 main 不超线。需懂 chunk 配置语法，影响范围大。

**修复 D**：完整 cook + pak 让分块自然重新生效（不一定能修复，看 cook 出来的资源大小变化）。

## 问题 6: `adb install -r` 同 versionCode 覆盖装可能让 OBB 被 scoped storage 清

**现象：** install -r 装新 APK 后，`/sdcard/Android/obb/<package>/` 目录被清空（14.7 GB OBB 没了），app 启动报"找不到 OBB"，触发 DownloaderActivity → 工程机没装 Google Play 报"无谷歌商店钥匙"。

**根因：** Android 11+ scoped storage + 部分 ROM（K60 MIUI / MTK 工程机）实现严格：app 重装时 uid 翻新（`u0_a485 → u0_a486`），scoped storage 看 `/Android/obb/<pkg>/` 下文件 owner uid 跟新 app uid 不匹配 → 自动清理。同 versionCode 覆盖装 (`-r` 模式) 仍触发此行为。

**修复 A（最稳）**：每次 install -r 后立刻验证 OBB：
```bash
adb shell ls -la /sdcard/Android/obb/<package>/ | head
# 如果 ls 显示空目录 → 重推 OBB
```

**修复 B**：把 OBB 备份到 app 沙箱外的 `/sdcard/Download/obb_backup/`（这条路径 app uninstall 不清），install -r 后 `mv` 回 `/Android/obb/<pkg>/`。同 FS rename 瞬时，省去 14.7 GB 重推。

**修复 C**：写 `quick-install.sh` 封装 `install -r → 验 OBB → 缺则推`。本期未做，留待优化。

**关键点**：adb push 推上去的 OBB 文件 owner 是 `shell` (uid 2000) 而非 app uid，权限 `rw-rw-rw-`（644）所有人可读。**实测 owner uid 不匹配但权限可读的情况下，app 仍能 mount OBB 成功**（不会被 scoped storage 拒绝读访问），但 install 时的清理仍会发生。

## 问题 7: Git Bash 下 `cmd //c "X.bat"` 不弹 console 进交互模式

**现象：** Git Bash 里跑：
```bash
cmd //c "C:\path\to\Install.bat"
```
预期 `cmd` 执行 bat 后退出，实际 `cmd` 进入交互提示符（`C:\Users\XINDONG>`）等待输入。

**根因猜测**：`//c` 在 Git Bash MSYS 路径转换下被吃掉或转成路径，`cmd` 没收到 `/c` 参数 → 进交互模式。或者 cmd 内部对 bat 路径里的反斜杠处理不当。

**修复 A（最稳）**：用 PowerShell 调 bat：
```bash
powershell.exe -ExecutionPolicy Bypass -Command "Set-Location 'C:\path\to\dir'; & '.\Install.bat'"
```
PowerShell 的 `Set-Location` + `&` 操作符路径处理干净，不依赖 `cmd` 的 CWD 搜索行为。

**修复 B**：写 wrapper bat 用 `pushd "%~dp0"` 锁定 CWD：
```bat
@echo off
pushd "%~dp0"
call "%~dp0Install.bat" %*
popd
```
然后 Git Bash 调 wrapper：`cmd //c "C:\path\wrapper.bat"`。但仍要求 `unset NoDefaultCurrentDirectoryInExePath` 让 cmd 能在 CWD 找 Install.bat。

**修复 C**：`unset NoDefaultCurrentDirectoryInExePath` + 用相对路径 + 显式 cd：
```bash
unset NoDefaultCurrentDirectoryInExePath
cd "C:\path\to\dir"
cmd //c "Install.bat"
```
依赖 cmd 继承父进程 CWD（Git Bash 下不一定 reliably 工作）。

## 问题 8: `adb push` 后 `cp` 14.7 GB 内部慢/不稳

**现象：** Install bat 推 OBB 到 `/sdcard/Download/obb/<pkg>/` 后，跑 `adb shell cp /sdcard/Download/obb/<pkg>/* /sdcard/Android/obb/<pkg>/` 卡很久 / 报错 ERRORLEVEL=255 / 设备临时掉线。

**根因：**
1. `cp` 14.7 GB 是真复制（不是 rename），即使同 FS 也要遍历每个文件读写一遍
2. 通配符 `*` 在 adb shell 里被 shell 展开，长命令行 / 大量参数 / 特殊字符可能引发解析问题
3. 长时间 USB 通信增加掉线概率（K60 / MTK 工程机 USB 通信稳定性都差）

**修复 A（最快）**：用 `mv` 不用 `cp`。同 FS rename 瞬时（毫秒级），不复制数据：
```bash
for OBB in main patch overflow1 overflow2; do
  adb shell "mv /sdcard/Download/obb/<pkg>/$OBB.<ver>.<pkg>.obb /sdcard/Android/obb/<pkg>/$OBB.<ver>.<pkg>.obb"
done
```

**修复 B**：直接 `adb push` 到目标位置 `/sdcard/Android/obb/<pkg>/`，跳过中间 Download 目录。adb push 走 system 权限可以直接写 `/Android/obb/`。

**修复 C**：避开通配符，逐个文件操作。

## 问题 9: PSO Precompile + GMS 噪音淹 logcat，[Phase1c] 等关键日志被覆盖

**现象：** MTK MT6899 启动 app 后：
- 默认 logcat buffer ~256KB / ~1MB（看 ROM）
- 启动期 PSO Precompile 7752 个 + GMS / nativeloader / surfaceflinger 大量 D 级日志
- `OnPostEngineInit` 触发的 `[Phase1c][T0~T3]` 4 条日志在 ~30 秒后就被覆盖
- `adb logcat -d -v time | grep "Phase1c"` dump 出来一条都没有

**根因：** logcat 是内核 ring buffer，满了循环覆盖。MTK 启动期日志爆量超过默认 buffer 容量。

**修复 A**：放大 logcat buffer：
```bash
adb logcat -G 16M    # 默认 main buffer 改 16 MiB
adb logcat -g        # 检查实际生效的 buffer 大小
```

**修复 B**：用 stream 模式而非 dump 模式：
```bash
# stream 实时写文件
adb logcat -v time | grep --line-buffered -E "Phase1c|MAGT" > /tmp/phase1c_stream.log &

# 启动 app
adb shell am start -n <pkg>/<activity>

# 等够时间（看 OnPostEngineInit 触发时机，启动到第一条 D/UE4 日志可能 1+ 分钟）
sleep 240

# 看结果
cat /tmp/phase1c_stream.log
```

stream 模式从启动一开始就把匹配的行写文件，不会被后面爆量日志覆盖。

**修复 C**：smoke 脚本里找最后一次 `[T0]` 起切分（解决环形 buffer 部分覆盖时只剩 T2/T3 的歧义）：
```bash
LAST_T0_LINENO=$(echo "$LOG_RAW" | grep -n "[T0]" | tail -1 | cut -d: -f1)
T_LINES=$(echo "$LOG_RAW" | tail -n +$LAST_T0_LINENO)
```

## 问题 10: MTK MAGT init 返回 `-8` (License Check Failed) — APK 签名跟 license 注册的 cert 不匹配

**现象：** MT6899 工程机 / 商品机上跑 app，logcat 出现：
```
I/MTK-MAGT: MTK Platform With MAGT Support Initialized. SDK(0.0.0)/SERVICE(3.0.12428)
I/MAGT_SERVICE_IMPL: MAGT ServiceImpl Init() start
I/         : MAGT verify : verifyAppLicense start
I/         : MAGT verify : packagename com.xindong.torchlight 
I/         : MAGT verify : appcode = 10028, expiredTime = 0, featureCode = 65535, installCode = 65535, now = 1776850386
E/         : MAGT verify failed, for check return verify = 0
I/         : MAGT verify init = 1, ret = -8
E/MAGT_SERVICE_IMPL: [_verifyAppLicense][MAGT_APPLICENSE]:151 verify_func failed
E/MAGT_SERVICE_IMPL: MAGT ServiceImpl License Check Failed: -8
```
然后 `TryInitMAGTService` 返 false，`CreateMonitor` 走 fallback 到 `FAndroidPerfMetricsMonitor`，业务侧 GPU/CPU/Battery 等查询全 -1 兜底。

**根因：**
- MAGT license 文件 `<package>_<appcode>_pack.bytes` 里**内嵌一个 cert hash**（APK 签名证书的 SHA-1 / SHA-256）
- MAGT 系统服务（PID 1015）通过 binder IPC 拿到 caller 的实际签名 cert hash，跟 license 内嵌的对比
- 不匹配 → 返回错误码 -8（"License Check Failed" 汇总码，SDK 故意不告诉具体哪个子检查不过，防破解）
- **错码 -8 含义**：license 验证失败（具体失败原因不暴露）。-8 不是"过期"也不是"设备不支持"，是签名 cert hash 不对

**修复 A（最干净）**：用**正确的 keystore** re-sign APK。火炬之光的 MAGT license 注册的是**专门的测试 keystore `xdaperf.keystore`**（不是商店发布主签名 `torchlight.keystore`）。已知信息：
- 文件路径：Confluence 文档说在 `E:\MTK_MAGT\xdaperf.keystore`
- Store Password: `front123`
- Key Alias: `xdaperf`
- Key Password: `front123`
- 持有者：心动前端 Lingyao Gan
- 证书 SHA-1: `EE:DC:F9:C6:74:E7:30:D1:2C:B9:1A:A0:17:BE:93:A6:D4:76:BC:16`
- 证书 SHA-256: `11:4E:FD:BC:EF:56:51:D5:05:A1:89:65:0E:10:03:57:58:03:5F:F5:B0:0C:14:C1:44:14:60:89:C0:C7:59:65`
- 证书有效期：2024-12-23 ~ 2074-12-11

re-sign 流程（不重 build）：
```bash
# 拷一份 APK 到目标位置
cp UE_game-arm64.apk UE_game-arm64-resigned.apk

# 用 xdaperf keystore re-sign（apksigner 在 Android SDK build-tools 下）
"<sdk>/build-tools/<ver>/apksigner.bat" sign \
  --ks <path>/xdaperf.keystore \
  --ks-pass "pass:front123" \
  --ks-key-alias xdaperf \
  --key-pass "pass:front123" \
  UE_game-arm64-resigned.apk

# 装机（不同签名不能 install -r 覆盖，要先 uninstall）
adb uninstall com.xindong.torchlight
adb install UE_game-arm64-resigned.apk
# 推 OBB（会被 install 清，需要重推）
```

re-sign 比改 BuildPackage 重打快多了（~10 秒 + 装机时间）。

**修复 B（生产版应走的）**：跟 mt 走 license 申请流程，让 MTK 把火炬之光商店发布版的 release cert 加入 MAGT license 白名单。这样 `BuildPackage.py FOR_DISTRIBUTION=True` 用 `torchlight.keystore` 签的包也能过 verify。

**修复 C**：在 `MediaTekPerfMetricesMonitor.cpp:136` init() 调用前加调试日志看参数：
```cpp
UE_LOG(LogTemp, Warning, TEXT("LogMTK: [InitParams] MajorVersion=%d AppCode=%d FrameRate=%d RHIThreadID=%d rawDataLen=%d"),
    MajorVersion, AppCode, FrameRate, RHIThreadID, rawData.Num());
```
对比预期值，确认不是参数错误（比如 license 文件读错了 / appcode 不对）。

**注意：错误码 -8 不是"过期"或"设备未支持"**。Vendor SDK 错误码常见布局（猜测）：
- 0 = OK
- -1~-7 = INVALID_PARAM / NULL_POINTER / NOT_INITIALIZED / VERSION_MISMATCH / DEVICE_NOT_SUPPORTED / PERMISSION_DENIED / SERVICE_UNAVAILABLE
- **-8 = LICENSE_INVALID / LICENSE_VERIFY_FAILED**（实测对应这条）
- -9 = LICENSE_EXPIRED（如果有单独一档）

---

## 通用结论

Git Bash (MSYS2) 环境下跑 Windows 原生工具链（bat、adb 等）的核心坑：
1. **CWD exe 搜索被禁** — `NoDefaultCurrentDirectoryInExePath` (问题 1)
2. **路径格式转换** — MSYS 自动转 `/xxx` 为 `C:/Program Files/Git/xxx` (问题 3)
3. **subst 盘符被解析** — Python `os.path.realpath` 会还原 subst (问题 2)
4. **cmd //c 不可靠** — 用 PowerShell 替代 (问题 7)

UE 4 Android 打包流程的核心坑：
5. **Editor 锁住 dll** → `LNK1104` (问题 4)
6. **单 OBB 4 GiB 上限** → stage 失败，hybrid 拼装绕开 (问题 5)
7. **install -r 清 OBB** → scoped storage uid 翻新 (问题 6)
8. **adb 内 cp 14.7 GB 慢/不稳** → 改用 mv 或直接 push 到目标 (问题 8)
9. **logcat ring buffer 覆盖关键日志** → `-G 16M` + stream 模式 + 找最后一次起点 (问题 9)
10. **MTK MAGT verify -8** → APK 签名 cert hash ≠ license 注册的，用对应 keystore re-sign (问题 10)
