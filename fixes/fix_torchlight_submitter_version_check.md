---
description: TorchlightSubmitter 版本号检查失败 sync 主干无效，因 P4V 跑的是 C:/submitter_log 旧副本
priority: high
status: active
trigger:
  keywords:
    - error:版本号检查失败
    - tool:p4v
    - tool:TorchlightSubmitter
    - concept:perforce
  tags:
    - build
    - debug
  stages:
    - debug
last_updated: 2026-06-01
---

# TorchlightSubmitter 版本号检查失败，更新主干仍报错

## 现象
P4V 右键 TorchlightSubmitter 提交弹 WARNING：
`版本号检查失败：当前版本号为 1.7.17，最新版本号为 1.7.18，请到主干更新版本！`
`p4 sync` 更新主干后仍报同样错。复发性问题（每次版本 bump 都可能踩）。

## 根因
- `cur_tool_version` 是**编译进 exe 的常量**（`src_frame_window.py:main()`），不是读本地文件。
- 校验逻辑 `src_wx_ui_func.py: check_if_this_version_valid` → `get_latest_client_version()` 用 urllib 拉
  `http://172.26.144.45:8081/zjj_setting_files/AutoTestLog/version_control/submit_tool_version.txt`
  得 latest，与常量 strip `\r\n` 后字符串比对，不等即阻断。
- P4V 实际跑的是 `C:/submitter_log/submitter/TorchlightSubmitter.exe`（`add_p4_plugin.py` 装插件时把该绝对路径写进 `~/.p4qt/customtools.xml`）。
- `p4 sync` 主干只更新 **trunk 工作区** 那份 exe，**不动** `C:/submitter_log/submitter/` 的运行副本 → 运行副本永远停在旧版本。

## 修复
跑 trunk `frontend/trunk/Tools/p4Submitter/update_submitter.bat`（调 `update_plugin.py`）：
kill TorchlightSubmitter 进程 → 把新 exe 从 trunk 拷进 `C:/submitter_log/submitter/`。
依赖 `pip install psutil` + python 在 PATH。
口诀：版本 bump 时 sync 主干不够，必须重跑 update_submitter.bat 刷新运行副本。

## 验证
重跑 update_submitter.bat 后重开 P4V 提交，WARNING 消失即修复。
取证手法：`pyinstxtractor.py` 解 exe CArchive 拿 main（含 cur_tool_version 常量）；
PYZ 层用 pip `pyinstxtractor-ng`；`uncompyle6` 整模块崩时用 `xdis.load_module` 读单函数 co_consts 取证。
