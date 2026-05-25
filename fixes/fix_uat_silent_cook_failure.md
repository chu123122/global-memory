---
description: UE 4.26 UAT BuildCookRun 默认把 cook commandlet 失败转 ExitCode=0，APK 残缺却被打包成功，必须 grep log 才能识破
priority: high
status: active
trigger:
  keywords:
    - error:cook_av
    - error:silent_failure
    - tool:uat
    - tool:buildpackage
    - platform:android
  tags:
    - build
    - debug
    - ue
  stages:
    - debug
    - delivery
last_updated: 2026-05-22
---

# UAT BuildPackage.py exit=0 不代表 cook 成功

## 现象

- `run_build_compat.py` / `BuildPackage.py` 跑完返回 `exit=0`
- 表面上 stage / sign / install 全部走完，APK 文件生成
- 装机后启动闪退 `Failed to initialize ShaderCodeLibrary required by the project ... Global shader library is missing`
- 或：APK 安装失败、PAK 缺资产、shader 编译错误等延后表现

## 根因

UAT (AutomationTool) 内部对 cook commandlet 失败有默认容错：cook 阶段进程 crash → `Took 62.4s to run UE4Editor-Cmd.exe, ExitCode=3` → 紧接一句 `WARNING: Ignoring cook failure` → 外层 BuildCookRun 继续走 stage→package→archive。

整个 pipeline 退出码 `0`，但实际产物残缺。BuildPackage.py 包装层 + run_build_compat.py 包装层都没有补救这个静默吞错。

## 修复

不要只看 `BuildPackage.py exit=0`。每次出包必走两步：

1. grep build log：
   ```bash
   grep -E "Fatal error|Ignoring cook failure|UE4Editor-Cmd\.exe.*ExitCode=3|EXCEPTION_ACCESS_VIOLATION" build_*.log
   ```
   任一命中 → 视为打包失败，APK 不可用

2. 装机后跑 e2e（不能只看 `adb install` 成功）：
   - 启动 APK
   - 等 30s 看主菜单是否出现
   - `adb logcat | grep -E "FATAL|AndroidRuntime"` 看是否闪退

可选硬化方向（未实施）：在 `run_build_compat.py` 末尾自动 grep log，命中 cook 失败标志时主动 exit 非零。

## 验证

模拟 cook 失败 → BuildPackage.py 应该 exit 非零；当前实测 exit=0 = 包装层有漏洞。

## 关联

- `D:/global-memory/fixes/fix_cook_av_dangling_shadermap.md`：触发 UAT 静默吞错的真实 cook AV 案例
- `C:/Perforce/tl_gaoxiang1_Main/frontend/trunk/Tools/run_build_compat.py`：当前包装层
