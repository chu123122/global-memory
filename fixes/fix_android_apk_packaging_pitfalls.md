---
description: UE4 Android APK 打包/重签名/OBB/真机 5 类复发性致命坑 + Git Bash 路径陷阱
priority: high
status: active
trigger:
  keywords:
    - platform:android
    - concept:packaging
    - concept:obb
    - concept:resign
  tags:
    - build
    - ue
    - tooling
  stages:
    - debug
last_updated: 2026-06-01
---

# UE4 Android APK 打包 / 重签名 / OBB / 真机测试复发坑

> 跨 task 复用的安卓打包经验。完整可执行 runbook（打包→重签名→装机→OBB→e2e→采集，含路径速查表）见
> `C:/Users/XINDONG/.claude/projects/C--Users-XINDONG/memory/procedure_android_build_and_test.md`。
> 本条只收**会反复踩的平台级坑**（中文查询经 alias 桥到 platform:android 命中）。
> 注：经验采集于 2026-04，版本相关行号可能漂移；平台行为类坑稳定。

## 5 类致命坑

### 1. MTK 设备 MAGT License -8 → 必须重签名
**现象**：`MAGT ServiceImpl License Check Failed: -8`，MAGT init 返 -8 降级 fallback monitor。
**根因**：APK 签名 cert hash 不匹配（**不是** versionCode 问题）。MTK MAGT SDK 校验 cert hash。
**修**：用 `torchlight.keystore`（`Z:/UE_game/Build/Android/`）重签，apksigner 校验 SHA-1。签名配置来源 `Z:/UE_game/Config/DefaultEngine.ini`。

### 2. Android 10 装上即闪退（AThermal 强引用）
**现象**：A10 闪退，logcat `cannot locate symbol "AThermal_acquireManager"`。
**根因**：NDK API 30+ symbol 静态调用，SO link 阶段强引用，运行时 `if` 守护无效。
**修**：改 dlsym 动态加载（已修 2026-04-24）。

### 3. Android 11+ bindService 失败（AppsFilter）
**现象**：`Unable to start service ... not found`，貌似 class 缺失。
**根因**：Package Visibility 限制，app 看不到目标 package。
**诊断**：`adb logcat -d | grep AppsFilter` 看 `BLOCKED`。
**修**：UPL 加 `<queries><package android:name="com.mediatek.magtdevtoolkit"/></queries>`。

### 4. OBB 丢失（scoped storage）
**现象**：install 后 OBB 被 scoped storage 清掉。
**根因**：uid 翻新，scoped storage owner 不匹配。
**修**：每次 install 后验证 `adb shell ls -la /sdcard/Android/obb/com.xindong.torchlight/`，缺则重推。

### 5. OBB 推送铁律
**现象**：push 到 Download 再 `mv` 到 obb 目录会丢文件。
**根因**：跨 mount 的 cp+rm 不可靠。
**修**：`adb push` **直接推到目标路径** `/sdcard/Android/obb/<pkg>/`，不中转。

## Git Bash 路径陷阱（adb 是 Windows binary）
- 源路径用 `C:/...`，**不能**用 `/c/...`。
- 目标路径加 `MSYS_NO_PATHCONV=1`，否则 MSYS 把 `/sdcard` 转成 `C:/Program Files/Git/sdcard`。

## 抓日志要点
- `UE_game.log`（C++ UE_LOG 全量）**必须从设备 pull**——logcat ring buffer 会被启动期 PSO Precompile + GMS 噪音挤掉。
- 设备路径 `/sdcard/Android/data/com.xindong.torchlight/files/UE4Game/UE_game/UE_game/Saved/Logs/UE_game.log`。

## 其他前置坑
- UE Editor 必须关，否则打包 LNK1104 dll 锁死。
- `run_build_compat.py` 当前用 minimal cook（只 cook 登录场景），真机完整运行需去 minimal 限制走全量 cook，否则 Global Shader 缺失闪退。
