---
name: fixes-android-apk-build
description: UE 4.26.2 + Git Bash 下 Android APK 打包 / 装机 / OBB / MAGT 鉴权 / Android 11+ 跨 app 可见性 / NDK API 30+ symbol 老设备兼容 全流程修复记录
summary: "12 类问题：环境（NoDefault*/MAX_PATH/MSYS路径）+ 构建（Editor锁dll/4GiB OBB）+ 装机（install -r 清 OBB）+ 调用（cmd//c 失败/PSO 噪音覆盖 logcat）+ MTK MAGT verify -8（核心是签名链/打包配置，不是 versionCode）+ Android 11+ AppsFilter 拦 bindService 跨 app + NDK API 30+ symbol 静态调用导致老设备 dlopen 失败"
type: fixes
created: 2026-04-16
updated: 2026-04-24
source: 心动引擎中台 Android APK 打包实战 + Phase 1c 子线程化跨平台验证
access_count: 0
---

# Android APK 打包修复经验（UE 4.26.2 + Git Bash）

> 项目：火炬之光，UE 4.26.2 源码版，Windows 11

## 0. 完整流程速查（AI 执行用）

> 2026-04-23 实战验证 端到端跑通流程。下次新对话直接照这跑。

### 0.1 打包

```bash
# 用户的 wrapper（封装了 subst Z: + Git Bash 兼容修复 + 最小 cook + 删 pause）
python /c/Perforce/tl_gaoxinag_01/frontend/trunk/Tools/run_build_compat.py
# 实测 22 min（最小 cook：InitScene + LoginScene_Mobile 2 张图）
```

输出位置：
- APK: `C:/Perforce/tl_gaoxinag_01/frontend/trunk/Editor/UE_game/Binaries/Android/UE_game-arm64.apk` (~168 MB)
- OBB: 同目录 `main.<ver>.<pkg>.obb` / `overflow1.<ver>` / `overflow2.<ver>` / `patch.<ver>` (4 个，~14 GB total)
- 归档：`Output/<日期>-<时间戳>/`

打包前必查：UE Editor 必须关（否则 LNK1104，问题 4）。

### 0.2 re-sign（关键步骤，跳过会撞 INSTALL_FAILED_UPDATE_INCOMPATIBLE）

2026-04-23 实机复盘后，这里的结论需要修正：**当前仓库 / 当前 MT6899 机器上的核心问题是签名链 / 打包配置偏了，不是 `versionCode`。**

项目默认配置其实是 release 签名：
- `UE_game/Config/DefaultEngine.ini`：`KeyStore=torchlight.keystore`、`KeyAlias=torchlight`
- `UE_game/Config/DefaultGame.ini`：`ForDistribution=True`

但 `Tools/BuildPackage.py` 当前写死：
- `FOR_DISTRIBUTION=False`
- `BUILD_TYPE="Development"`

也就是说，脚本打出来的包**没有稳定走项目默认的 release signing**。本次实机验证里：
- 用 `xdaperf.keystore` 的包，MAGT 一直 `License Check Failed: -8`
- 改用项目默认的 `torchlight.keystore` 重签后，`AppLicenseHubService` 正常 bind，`MAGT ServiceImpl License Check Failed: -8` 消失
- 因此这里要优先校准的是**签名链 / 打包配置**，不是怀疑 `versionCode`

当前正确的快速验证方式：

```bash
APK_NEW="C:/Perforce/tl_gaoxinag_01/frontend/trunk/Editor/UE_game/Binaries/Android/UE_game-arm64.apk"
APK_RESIGNED="/c/Users/XINDONG/Downloads/UE_game-arm64-torchlight-signed.apk"
KEYSTORE="C:/Perforce/tl_gaoxinag_01/frontend/trunk/Editor/UE_game/Build/Android/torchlight.keystore"
APKSIGNER="/c/Users/XINDONG/AppData/Local/Android/Sdk/build-tools/35.0.0/apksigner.bat"

cp "$APK_NEW" "$APK_RESIGNED"
"$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-pass pass:torchlight1234! \
  --ks-key-alias torchlight \
  --key-pass pass:torchlight1234! \
  "$APK_RESIGNED"

# verify SHA-1 应该是 67b985ce4e10c3b3e1203556c16808c09373092d
"$APKSIGNER" verify --print-certs "$APK_RESIGNED" | grep SHA-1
```

注意：如果设备上之前装的是别的签名（比如 `xdaperf`），不能直接 `install -r` 覆盖，必须先 `adb uninstall com.xindong.torchlight`，然后重新安装并补推 4 个 OBB。

### 0.3 装机

```bash
adb install -r "$APK_RESIGNED"
# Success → app uid 通常翻新
```

⚠️ install 后 OBB 大概率被 scoped storage 清（问题 6）。

### 0.4 推 OBB（4 个文件 ~14 GB，~7 min @ USB 3.0）

**铁律：直接 push 到 `/sdcard/Android/obb/<pkg>/`，不要走 `/sdcard/Download/` 中转。**

`mv` 跨这两个目录是**跨 mount cp+rm**（不是 instant rename），失败时丢源文件。
2026-04-23 实测：mv /sdcard/Download/obb_backup/ → /sdcard/Android/obb/<pkg>/ 4 个 OBB 中 2 个变 0 字节。

```bash
PKG="com.xindong.torchlight"
OBB_DIR="C:/Perforce/tl_gaoxinag_01/frontend/trunk/Editor/UE_game/Binaries/Android"  # ⚠️ Windows path（C:/...），不要用 /c/...
TARGET="/sdcard/Android/obb/$PKG"

# 顺序：先小后大，撞 USB 不稳早发现
for f in overflow2 main overflow1 patch; do
    src="$OBB_DIR/$f.<verCode>.com.xindong.torchlight.obb"
    MSYS_NO_PATHCONV=1 adb push "$src" "$TARGET/" 2>&1 | tail -2
done
```

⚠️ adb 是 Windows binary，源路径用 `C:/...`（forward slash 也 OK），不能用 Git Bash 风格 `/c/...`，否则 `cannot stat: No such file or directory`。

⚠️ adb shell 命令路径要 `MSYS_NO_PATHCONV=1` 包，否则 `/storage/emulated/0/...` 会被 Git Bash 翻译成 `C:/Program Files/Git/storage/...`。

### 0.5 跑 e2e + 抓日志

```bash
bash D:/ClaudeTasks/active/xd-adaptive-performance-refactor/scripts/e2e_test.sh -v
```

### 0.6 抓 UE 日志（**关键**：logcat 不可靠，必须拉 UE log 文件）

logcat 即便 `-G 16M` 实际 readable 也只 ~271 KiB（启动期日志爆量挤掉），插件 C++ UE_LOG 几乎全丢。
真正的全量 UE log 在设备文件：

```bash
UE_LOG_DEV="/sdcard/Android/data/com.xindong.torchlight/files/UE4Game/UE_game/UE_game/Saved/Logs/UE_game.log"
MSYS_NO_PATHCONV=1 adb pull "$UE_LOG_DEV" /c/Users/XINDONG/UE_game.log

# grep 你想看的
grep "\[Phase1c\]" /c/Users/XINDONG/UE_game.log
grep -E "TryInitMAGT|InitParams|MAGTSupportVersion" /c/Users/XINDONG/UE_game.log
```

logcat 可以看 MAGT SDK / Java 层日志（tag `MTK-MAGT`、`XDAPF` 是 ConsoleReceiver Java 类、`MAGT_SERVICE_IMPL` 是 MTK 系统服务），但**插件 C++ UE_LOG 必须从 UE_game.log 文件拉**。

### 0.7 USB 中断恢复

push 中途 `adb: error: failed to get feature set: device offline`：
1. 看手机屏幕：解锁、注意"允许 USB 调试"对话框（必选「允许」+「始终允许」）
2. `adb kill-server && adb start-server` 不一定够，物理拔插一次最稳
3. `adb devices` 确认从 `offline` 变 `device`

---

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

## 问题 10: MTK MAGT init 返回 `-8` (License Check Failed) — 核心是签名链 / 打包配置，不是 `versionCode`

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

**2026-04-23 实机修正后的根因：**
- MAGT license 文件 `<package>_<appcode>_pack.bytes` 里**内嵌一个 cert hash**（APK 签名证书的 SHA-1 / SHA-256）
- MAGT 系统服务通过 binder IPC 拿到 caller 的实际签名 cert hash，跟 license 内嵌的对比
- **真正踩坑点不是 `versionCode`，而是打包脚本没有走项目默认的 release signing**
- 当前仓库里 `UE_game/Config/DefaultEngine.ini` 配的是 `torchlight.keystore` / `torchlight`，`DefaultGame.ini` 配的是 `ForDistribution=True`
- 但 `Tools/BuildPackage.py` 当前是 `FOR_DISTRIBUTION=False`、`BUILD_TYPE="Development"`
- 结果就是：脚本产物和项目默认签名链脱节，手工再签错 keystore 时，就会稳定撞 `-8`

**这次实机验证结果：**
- `xdaperf.keystore`：`AppLicenseHubService` 能 bind，但 MAGT 仍然 `License Check Failed: -8`
- `torchlight.keystore`：重签、重装、补推 OBB 后，`MAGT ServiceImpl License Check Failed: -8` 消失，`InitGameConfig Result : 0`、`Init, Result:0. StartService:127, Result:0`
- 所以当前这条问题应记录为：**核心是签名链 / 打包配置不对，不是 `versionCode` 不对**

**修复 A（当前仓库 / 当前设备已验证通过）**：用项目默认的 `torchlight.keystore` 重签 APK。
- 文件路径：`UE_game/Build/Android/torchlight.keystore`
- Store Password: `torchlight1234!`
- Key Alias: `torchlight`
- Key Password: `torchlight1234!`
- 证书 SHA-1: `67:b9:85:ce:4e:10:c3:b3:e1:20:35:56:c1:68:08:c0:93:73:09:2d`

re-sign 流程（不重 build）：
```bash
cp UE_game-arm64.apk UE_game-arm64-torchlight-signed.apk

"<sdk>/build-tools/<ver>/apksigner.bat" sign \
  --ks UE_game/Build/Android/torchlight.keystore \
  --ks-pass "pass:torchlight1234!" \
  --ks-key-alias torchlight \
  --key-pass "pass:torchlight1234!" \
  UE_game-arm64-torchlight-signed.apk

# verify SHA-1 应该是 67b985ce4e10c3b3e1203556c16808c09373092d
"<sdk>/build-tools/<ver>/apksigner.bat" verify --print-certs UE_game-arm64-torchlight-signed.apk

# 装机（不同签名不能 install -r 覆盖，要先 uninstall）
adb uninstall com.xindong.torchlight
adb install UE_game-arm64-torchlight-signed.apk
# 然后重推 4 个 OBB
```

re-sign 比改 BuildPackage 重打快多了（~10 秒 + 装机时间），适合先做真机验证。

**修复 B（长期正确方向）**：把打包脚本改到真正走项目默认的 distribution / release signing，而不是继续依赖手工 re-sign。
- 重点不是改 `versionCode`
- 重点是让 `BuildPackage.py` 和 `DefaultEngine.ini` / `DefaultGame.ini` 的签名配置保持一致

**修复 C**：在 `MediaTekPerfMetricesMonitor.cpp:136` init() 调用前加调试日志看参数：
```cpp
UE_LOG(LogTemp, Warning, TEXT("LogMTK: [InitParams] MajorVersion=%d AppCode=%d FrameRate=%d RHIThreadID=%d rawDataLen=%d"),
    MajorVersion, AppCode, FrameRate, RHIThreadID, rawData.Num());
```
对比预期值，确认不是参数错误（比如 license 文件读错了 / appcode 不对）。

**注意：错误码 -8 不是"过期"或"设备未支持"**。它表示 license 验证失败，但当前这次实机已经证明，优先该查的是**签名链 / 打包配置是否偏离项目默认 release signing**。

---

## 问题 11: Android 11+ (targetSdk≥30) 跨 app bindService 失败 — 必须在 manifest 加 `<queries>`

**症状（混淆性极强，容易误判）**：
- `W/ActivityManager: Unable to start service Intent { ... cmp=<otherpkg>/<service> } U=0: not found`
- 看起来像"目标 service 类不存在"
- 但 `dumpsys package <otherpkg> | grep <ServiceName>` 也返回空 → 加深"class 缺失"误判

**真根因**：Android 11 (API 30) 引入 [Package Visibility](https://developer.android.com/training/package-visibility)。
- 默认情况下 app A **看不到** app B 的存在（包名 / 服务 / receiver / activity）
- A 调 `bindService` 找 B 的服务 → AppsFilter 拦截 → 返回 `not found`（即使 class 真的存在）
- `dumpsys package A` 的 `queriesPackages` 字段决定 A 能看到谁

**关键诊断信号（容易漏看）**：
```
I/AppsFilter: ... <calling_pkg> -> <target_pkg> BLOCKED
```
看到 `BLOCKED` 就是 AppsFilter 拦了，**不是** class 缺失。

**修法**：在 calling app 的 `AndroidManifest.xml` 加 `<queries>`：

```xml
<manifest ...>
    <queries>
        <package android:name="com.target.package" />
    </queries>
    <application>...</application>
</manifest>
```

**UE 项目修法（UPL 注入）**：

```xml
<!-- Plugins/<YourPlugin>/Source/ThirdParty/<Lib>/xxx_UPL.xml -->
<root xmlns:android="http://schemas.android.com/apk/res/android">
    <androidManifestUpdates>
        <addElements tag="$">
            <queries>
                <package android:name="com.target.package" />
            </queries>
        </addElements>
    </androidManifestUpdates>
</root>
```

落点选择：
- ✅ **plugin 自己的 UPL**（如 `Plugins/X/Source/ThirdParty/XLib/x_UPL.xml`）— 最稳，作用域最小
- ⚠️ 项目公共 UPL（如 `TorchLightPlatform_Android_UPL.xml`）— 影响所有平台变体，EN/CN 可能不对称

**验证**（重打包后必须三看）：
1. **本地 APK manifest 含 queries**：`Intermediate/Android/arm64/gradle/app/src/main/AndroidManifest.xml` grep `<package android:name="com.target.package"`
2. **设备 logcat BLOCKED 消失**：启动 app 后 `adb logcat -d | grep AppsFilter`
3. **运行时 bind 成功**：`adb shell dumpsys activity services | grep -A 5 <ServiceName>` 看到 caller=你的 app

⚠️ **设备侧 dumpsys 误导**：`adb shell dumpsys package <calling_pkg>` 的 `queriesPackages` 字段**有时不显示** UPL 注入的 packages，但运行时实际能 bind。**以最终 APK manifest + 运行时证据为准**，不要被 dump 输出误导。

**实测**（2026-04-23 XDAdaptivePerformance MAGT 接通）：
- 调用方：`com.xindong.torchlight`（targetSdk 30+）
- 目标：`com.mediatek.magtdevtoolkit/com.mediatek.magtext.AppLicenseHubService`
- 修前：`AppsFilter ... torchlight -> magtdevtoolkit BLOCKED` + `not found`
- 修后：BLOCKED 消失，bind 成功
- **耗时教训**：因为没看 AppsFilter log，绕了一大圈以为 toolkit APK 缺这个 class（dumpsys grep 返回空进一步加强误判），中途换过 4 个错误根因假设。**下次撞 `not found` 第一反应去看 AppsFilter，不要跳"class 缺失"**

---

## 问题 12: NDK API 30+ symbol 静态调用 → 老 Android 设备 dlopen 失败 → app 闪退装不进

**症状（影响 ALL Android 10 (API 29) 及以下设备）**：

```
java.lang.UnsatisfiedLinkError: dlopen failed:
  cannot locate symbol "AThermal_acquireManager"
  referenced by ".../lib/arm64/libUE4.so"
  at java.lang.Runtime.loadLibrary0(Runtime.java:1071)
  at com.epicgames.ue4.GameActivity.<clinit>(GameActivity.java:7136)
W ActivityTaskManager: Force finishing activity .../GameActivity
```

App 启动时 SplashActivity → GameActivity 静态初始化 → `System.loadLibrary("UE4")` → dlopen libUE4.so → 缺 NDK API 30+ symbol → unsatisfied → SO 整个 load 失败 → 类初始化崩 → app 闪退。

**真根因**：plugin C++ 直接调 NDK API 30+ symbol（如 `AThermal_acquireManager` / `AThermal_releaseManager` / `AThermal_getCurrentThermalStatus`），即使代码里有运行时 `if (ApiLevel >= 30)` 守护也**没用** —— 因为 SO 在 link 阶段就强引用 symbol，linker 在 if 之前就检查 symbol 缺失。

**典型反例代码**（XDAdaptivePerformance/AndroidPerfMetricsMonitor.cpp:290-322）：

```cpp
#if PLATFORM_ANDROID
    int ApiLevel = FAndroidMisc::GetAndroidBuildVersion();
    if (ApiLevel >= 30 && Type == EThermalType::Default)  // ← 运行时守护，但太晚
    {
        AThermalManager* Mgr = AThermal_acquireManager();  // ← 静态调用，编译时强引用
        ...
    }
#endif
```

**两种修法**：

**方案 A：weak symbol**（推荐，~5 行改动，跟 NDK header 自然兼容）

```cpp
// 在文件顶部声明 weak symbol
extern "C" __attribute__((weak)) AThermalManager* AThermal_acquireManager();
extern "C" __attribute__((weak)) void AThermal_releaseManager(AThermalManager*);
extern "C" __attribute__((weak)) AThermalStatus AThermal_getCurrentThermalStatus(AThermalManager*);

// 调用前先判 symbol 是否在
if (AThermal_acquireManager && AThermal_releaseManager && AThermal_getCurrentThermalStatus) {
    AThermalManager* Mgr = AThermal_acquireManager();
    ...
}
```

**方案 B：dlsym 动态解析**（更显式，参考已有 QualcommPerfMonitor.cpp 对 QAPE 的处理）

```cpp
static auto pfn_acquire = (AThermalManager*(*)())dlsym(RTLD_DEFAULT, "AThermal_acquireManager");
static auto pfn_release = (void(*)(AThermalManager*))dlsym(RTLD_DEFAULT, "AThermal_releaseManager");
static auto pfn_getStatus = (AThermalStatus(*)(AThermalManager*))dlsym(RTLD_DEFAULT, "AThermal_getCurrentThermalStatus");
if (pfn_acquire && pfn_release && pfn_getStatus) {
    AThermalManager* Mgr = pfn_acquire();
    ...
}
```

**3 步验证**：
1. APK 装 Android 10 (API 29) 设备 — 启动不闪退
2. logcat 没有 `UnsatisfiedLinkError` / `cannot locate symbol`
3. Android 11+ 设备依然能拿到 thermal 数据（守护逻辑还有效）

**通用规则**：plugin C++ 凡引用 NDK API ≥ 30 symbol 必须 dlsym/weak 兜底，**不能依赖运行时 if 守护**。

**实测**（2026-04-24 XDAdaptivePerformance Mi 10 测试）：
- Mi 10 (Android 10 / API 29 / Snapdragon 865) 装新 APK 启动即闪退
- logcat 完整 stacktrace 见 02-Mi10 测试报告 §4.1
- 影响：所有 API 29 及以下设备装不上 plugin（市占率不低）
- **优先级 🔴 致命** — 比 GPU counter 全 0 严重得多

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
10. **MTK MAGT verify -8** → 先查签名链 / 打包配置有没有偏离项目默认 release signing，不要先怀疑 `versionCode` (问题 10)

