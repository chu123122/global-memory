---
description: UE 4.26 Android cook AV at GetOutdatedTypes 真因是 FShaderMapBase::Content 裸指针未初始化（注册到全局容器但未 AssignContent）
priority: high
status: active
trigger:
  keywords:
    - error:cook_av
    - error:shader
    - concept:shadermap
    - platform:android
    - concept:null_pointer
  tags:
    - build
    - debug
    - ue
  stages:
    - debug
last_updated: 2026-05-24
---

# UE 4.26 Android Cook AV at GetOutdatedTypes 真因是 FShaderMapBase::Content 未初始化

## 现象

UE 4.26 Android 全量 cook 在 `SaveGlobalShaderMapFiles` 初始化阶段稳定 AV，60-120s 内 fatal：

```
Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x0000000000000038
[Callstack] UE4Editor-RenderCore.dll!FShaderMapContent::GetOutdatedTypes() ShaderMap.cpp:632
[Callstack] UE4Editor-Engine.dll!FMaterialShaderMap::GetAllOutdatedTypes() MaterialShader.cpp:1387
[Callstack] UE4Editor-Engine.dll!GetOutdatedShaderTypes() ShaderCompiler.cpp:4522
[Callstack] UE4Editor-Engine.dll!RecompileShadersForRemote() ShaderCompiler.cpp:5466
[Callstack] UE4Editor-UnrealEd.dll!UCookOnTheFlyServer::SaveGlobalShaderMapFiles() CookOnTheFlyServer.cpp:6493
```

AutomationTool 把 cook 失败转成 `WARNING: Ignoring cook failure` + outer `ExitCode=0`，pipeline 继续 stage→sign→install，APK 产出但缺 GlobalShaderMap，启动闪退 `Failed to initialize ShaderCodeLibrary`。

## 根因（W5 实证后修正，2026-05-24）

报错行 `for (FShader* Shader : Shaders)` **不是** Shader entry 为 null，也**不是** dangling 指针。

是 `FShaderMapBase::Content` 裸指针**未初始化**就被使用。

### 关键代码路径

```cpp
// ShaderMap.cpp:34
FShaderMapBase::FShaderMapBase(const FTypeLayoutDesc& InContentTypeLayout)
    : ContentTypeLayout(InContentTypeLayout)
    , PointerTable(nullptr)
    , Content(nullptr)           // ← 裸指针，ctor 初始化 nullptr
    , FrozenContentSize(0u)
    , NumFrozenShaders(0u)
{}

// ShaderMap.cpp:60
void FShaderMapBase::AssignContent(...) {
    Content = ...;               // ← 必须显式调才会设值
}

// Shader.h:1925 (inline)
void GetOutdatedTypes(...) const {
    Content->GetOutdatedTypes(*this, ...);   // ← 盲 deref，无 null 检查
}
```

部分 `FMaterialShaderMap` 实例在 ctor 中注册到 `FMaterialShaderMap::AllMaterialShaderMaps` 全局容器（`MaterialShader.cpp:1387` 的 `for (const FMaterialShaderMap* ShaderMap : AllMaterialShaderMaps)`），但**从未调** `AssignContent()` → `GetOutdatedTypes` 盲 deref `Content->...` → AV at offset 0x38（= `Shaders` 字段在 FShaderMapContent 中的偏移）。

### W5 patch 实证证据链

W5 patch（MaterialShader.cpp）给 CTOR / DTOR / `GetAllOutdatedTypes` 迭代加 ADD/REMOVE/ITER log：

- 116 ADD events / **0 REMOVE events**（说明不是 lifetime 问题）
- crash 在 ITER[85/116]
- 罪魁 `0x1CB0886E080` ADD 在 log line 7061（05:38:10.154），crash 在 line 11754（05:38:37.388），间隔 27s
- 指针仍活，但其 Content 字段为 null

**改 patch 让首个访问字段从 `Shaders` 换成 `GetShaderPlatform()` 后，AV 偏移从 0x38 变 0x58**（= EShaderPlatform 字段偏移）→ 确证 deref 的是同一个 null 对象的不同字段。

## 排除清单（试过没用，别再走）

| 假设 | 证据 |
|---|---|
| DDC 损坏 | 清三层 DDC（项目 Boot.ddc+VT / `$LOCALAPPDATA/UnrealEngine/Common` / `$LOCALAPPDATA/UnrealEngine/4.26`）后同 AV |
| 单材质损坏 | quarantine 嫌疑材质后 cook 继续，揭出大量基底材质相同失败，问题面不局限 |
| 引擎源/资产新引入 | 引擎源 + 嫌疑材质 P4 rev 均早于上次跑通日 |
| Shader entry 为 null | W4 patch 实测 77 次调用 0 个 null Shader 命中（W4 patch 在 ShaderMap.cpp） |
| dangling FMaterialShaderMap | W5 patch ADD=116 / REMOVE=0，指针没被释放 |
| minimal cook 绕开 | `SaveGlobalShaderMapFiles` 在 cook 初始化先于 map 加载，minimal cook 同 AV |

## 修复（W6，2026-05-24）

防御性 fix：在 `FMaterialShaderMap::GetAllOutdatedTypes` 迭代前判 Content null 跳过。

```cpp
// Engine/Source/Runtime/Engine/Private/Materials/MaterialShader.cpp
#if WITH_EDITOR
void FMaterialShaderMap::GetAllOutdatedTypes(
    TArray<const FShaderType*>& OutdatedShaderTypes,
    TArray<const FShaderPipelineType*>& OutdatedShaderPipelineTypes,
    TArray<const FVertexFactoryType*>& OutdatedFactoryTypes)
{
#if ALLOW_SHADERMAP_DEBUG_DATA
    FScopeLock AllMatSMAccess(&AllMaterialShaderMapsGuard);
    const int32 XD_Total_W5 = AllMaterialShaderMaps.Num();
    int32 XD_SkippedNullContent = 0;
    for (const FMaterialShaderMap* ShaderMap : AllMaterialShaderMaps)
    {
        if (!ShaderMap || !ShaderMap->GetContent())
        {
            ++XD_SkippedNullContent;
            continue;
        }
        ShaderMap->GetOutdatedTypes(OutdatedShaderTypes, OutdatedShaderPipelineTypes, OutdatedFactoryTypes);
    }
    if (XD_SkippedNullContent > 0)
    {
        UE_LOG(LogTemp, Warning, TEXT("XD_FIX_W6 GetAllOutdatedTypes skipped %d/%d entries with null Content"), XD_SkippedNullContent, XD_Total_W5);
    }
#endif
}
#endif
```

**性质**：
- 防御性，不修上游真因（为啥某些 FMaterialShaderMap 被注册到全局容器却没 AssignContent）
- 仅 `#if WITH_EDITOR + ALLOW_SHADERMAP_DEBUG_DATA` 范围，不影响 runtime
- 真因属中间件/资产生命周期问题，需后续追

## 验证

R3 full cook 实测：
- `XD_FIX_W6 GetAllOutdatedTypes skipped 8/116 entries with null Content` 出现
- 0 Fatal / 0 AV
- cook 推进 6400/173856 包稳定（之前 100% 卡在 SaveGlobalShaderMapFiles 初始化阶段）

判定 cook 是否真出问题（不能只看 BuildPackage.py exit code）：

```bash
grep -E "Fatal error|Ignoring cook failure|UE4Editor-Cmd.exe.*ExitCode=3" build.log
```

任一命中 = APK 残缺，必须装机跑 e2e 确认主菜单可加载。

## 关联

- 同步：`~/.claude/global-memory/fixes/fix_uat_silent_cook_failure.md`
- 任务：`D:/ClaudeTasks/active/android-cook-shadermap-dangling/ops/坑点.md`
- 旧调查：`D:/ClaudeTasks/archived/xd-adaptive-performance-refactor/INVESTIGATION.md`
