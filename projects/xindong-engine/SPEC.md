# Android APK 打包 · 需求规格

> 更新时间：2026-04-16

## 目标

在本机 Windows 11 环境下，能够完整执行《火炬之光：无限》Android APK 的**打包 → 安装 → 真机运行**全流程，支持日常开发调试。

## 项目信息

| 项目 | 值 |
|------|-----|
| 游戏名 | 火炬之光：无限 |
| 包名 | com.xindong.torchlight |
| 引擎 | UE 4.26.2（源码版，团队自定义） |
| 目标平台 | Android ARM64 |
| 纹理格式 | ASTC |
| SDK 配置 | MinSDK=21, TargetSDK=35, CompileSDK=35 |
| 渲染 | ES 3.1 + Vulkan |
| 版本管理 | Perforce |
| 本机路径 | `C:\Users\XINDONG\Perforce\tl_gaoxinag_01\frontend\trunk\` |
| 短路径映射 | `subst Z: → ...\Editor` |

## 验收标准

1. **打包成功** — `BuildPackage.py` 跑完无报错，产出 APK + OBB
2. **安装成功** — `adb install` APK 成功 + OBB 推送到正确位置
3. **启动不闪退** — 游戏进程存活 > 30 秒，渲染出画面
4. **基本可操作** — 能进入登录/主界面

## 范围

### 在范围内
- 本机打包环境配置
- 打包脚本兼容性修复（Git Bash 环境）
- 真机安装和调试
- Cook/Shader 问题排查

### 不在范围内
- CI/CD 打包流水线
- 多渠道包（仅 Test 渠道）
- iOS 打包
- Shipping 正式包（仅 Test/Development）
- 热更新流程

## 技术约束

1. **引擎版本锁定** — UE 4.26.2 源码版，团队有自定义改动（支持 SDK 35），不可升级引擎
2. **路径长度** — 必须用 `subst` 短路径，否则 UBT 报 260 字符超限
3. **Git Bash 兼容** — Claude Code 使用 Git Bash，需处理 `NoDefaultCurrentDirectoryInExePath`、MSYS 路径转换等问题
4. **SetupAndroid.bat 与项目配置不匹配** — 脚本写死 SDK 28，但项目用 SDK 35，以项目配置为准
