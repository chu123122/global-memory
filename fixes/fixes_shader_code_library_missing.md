---
name: fixes-shader-code-library-missing
description: UE4 Android APK 启动闪退 ShaderCodeLibrary::InitForRuntime 的修复 — 全量 Cook 而非 minimal cook
summary: "Global shader library missing 类型闪退，根因是 minimal cook 漏掉 shader，全量 cook 即可"
type: fixes
created: 2026-04-22
updated: 2026-04-22
source: 心动引擎中台 Android APK 打包实战（红米 K60 验证通过）
access_count: 0
---

# ShaderCodeLibrary::InitForRuntime 闪退修复

> 项目：火炬之光，UE 4.26.2 源码版，Android ARM64 / ASTC

## 现象

APK 安装到真机后启动立刻闪退（不出画面），logcat 关键报错：

```
Fatal error: Failed to initialize ShaderCodeLibrary required by the project
because part of the Global shader library is missing.
```

崩溃位置：`Engine/Source/Runtime/RenderCore/Private/ShaderCodeLibrary.cpp:2553`
（`FShaderCodeLibrary::InitForRuntime`）

## 根因

Cook 阶段没有把项目所需的 shader 全量编译到 shader archive 里。运行时 `InitForRuntime` 检查 archive 完整性发现缺失，触发 fatal。

具体到我们的场景：之前为了加快迭代，在 `run_build_compat.py` 里把 cook 限制成只 cook 登录场景的地图（`-map=InitScene+LoginScene_Mobile`），导致 shader archive 不完整。即使能进登录页，`InitForRuntime` 在更早的初始化阶段就会因为 Global Shader 缺失直接 fatal。

## 修复

**去掉 minimal cook 限制，让 shader 走全量编译。**

具体：把 `run_build_compat.py` 里强行注入的 `-map=...` 参数移除（或改回 `-allmaps`），让 BuildPackage.py 走默认的全量 cook 路径。

代价是首次全量 cook 时间较长（shader 编译占大头），但增量 cook 缓存能复用，第二次起会快很多。

## 验证

✅ 红米 K60 (23013RK75C, 骁龙 8+ Gen1)，2026-04-21
- 全量 cook 完成 → 打包 → adb install + push 4 个 OBB → 启动成功，进入登录页
- baseline 日志见 `D:/ClaudeTasks/active/xd-adaptive-performance-refactor/baseline-logs/`

## 关联坑（不要混淆）

ShaderCodeLibrary 闪退在我们这个项目还有**另一条根因链**（HANDOFF 完整记录）：

```
游戏插件未被 PluginManager 挂载（.uplugin EnabledByDefault=false 且不在 .uproject）
  → 插件 DLL 加载失败
  → Cook phase 6 失败
  → shader archive 没生成
  → 同样表现为 ShaderCodeLibrary 闪退
```

两条根因**表象一样、修法不同**：
- 插件链路：在 `.uproject` Plugins 列表加 `Enabled: true`（详见 `~/.claude/projects/C--Users-XINDONG/memory/fixes_android_build.md`）
- 全量 Cook 链路：本文档

排查时按"先看 Cook ExitCode → 再看 Cook 范围"的顺序：Cook 失败 = 插件问题；Cook 成功但 shader 缺 = cook 范围问题。

## 通用经验

minimal cook（限定 map）是开发期的提速手段，**不能用来打可分发 APK**。Global Shader 不绑定具体地图，必须走全量 cook 才能保证 archive 完整。任何"只 cook 一部分"的优化都要预期会触发 ShaderCodeLibrary fatal。
